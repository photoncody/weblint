import os
import sys
import uuid
import json
import hmac
import time
import secrets
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

def is_safe_url(target):
    """Allow only relative same-origin paths (no scheme/host, no backslash tricks)."""
    if not target or not isinstance(target, str):
        return False
    target = target.strip()
    if not target.startswith('/') or target.startswith('//'):
        return False
    if '\\' in target or '\n' in target or '\r' in target or '\0' in target:
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc

def is_frozen():
    """True when running as a PyInstaller (or similar) bundled executable."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def is_desktop_mode():
    """Desktop/local packaged mode: auto secret key, local data dir, browser launch."""
    if is_frozen():
        return True
    return os.environ.get('WEBLINT_DESKTOP', '').lower() in ('1', 'true', 'yes')

def resource_root():
    """Directory that contains templates/ and static/ (bundle dir when frozen)."""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def resolve_data_dir():
    """Where SQLite and optional secret.key live."""
    if is_frozen():
        # Keep data next to the executable so installs are portable and easy to find.
        return os.path.join(os.path.dirname(sys.executable), 'data')
    if os.path.exists('/data'):
        return '/data'
    return os.path.join(os.getcwd(), 'data')

def resolve_secret_key(data_dir):
    """
    Prefer SECRET_KEY from the environment.
    In desktop/frozen mode, persist an auto-generated key under data/ so users
    do not need to configure env vars to run locally.
    """
    secret_key = os.environ.get('SECRET_KEY')
    if secret_key and secret_key not in ('CHANGE_ME', 'weblint_secret'):
        return secret_key

    if is_desktop_mode():
        os.makedirs(data_dir, exist_ok=True)
        key_path = os.path.join(data_dir, 'secret.key')
        if os.path.isfile(key_path):
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
            with open(key_path, 'r', encoding='utf-8') as f:
                stored = f.read().strip()
            if stored:
                return stored
        generated = secrets.token_hex(32)
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(generated)
        return generated

    raise ValueError("No secure SECRET_KEY set. Please set the SECRET_KEY environment variable.")

def migrate_schema(db_path):
    """Add missing columns to the snippet table (idempotent)."""
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(snippet)")
        columns = [info[1] for info in c.fetchall()]

        if 'parsing_mode' not in columns:
            print("Adding 'parsing_mode' column to snippet table...")
            c.execute("ALTER TABLE snippet ADD COLUMN parsing_mode TEXT DEFAULT 'weblint'")

        if 'notes' not in columns:
            print("Adding 'notes' column to snippet table...")
            c.execute("ALTER TABLE snippet ADD COLUMN notes TEXT")

        if 'parts' not in columns:
            print("Adding 'parts' column to snippet table...")
            c.execute("ALTER TABLE snippet ADD COLUMN parts TEXT")

        if 'archived' not in columns:
            print("Adding 'archived' column to snippet table...")
            c.execute("ALTER TABLE snippet ADD COLUMN archived INTEGER DEFAULT 0 NOT NULL")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error checking/migrating schema: {e}")

_root = resource_root()
app = Flask(
    __name__,
    template_folder=os.path.join(_root, 'templates'),
    static_folder=os.path.join(_root, 'static'),
)

base_dir = resolve_data_dir()
os.makedirs(base_dir, exist_ok=True)
db_path = os.path.join(base_dir, 'snippets.db')

app.secret_key = resolve_secret_key(base_dir)

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Only force Secure cookies when explicitly requested (keeps HTTP LAN/desktop working)
if os.environ.get('WEBLINT_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes'):
    app.config['SESSION_COOKIE_SECURE'] = True
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

# Auth configuration
auth_user = os.environ.get('WEBLINT_USERNAME')
auth_pass = os.environ.get('WEBLINT_PASSWORD')
auth_enabled = bool(auth_user and auth_pass)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    id = "admin"

@login_manager.user_loader
def load_user(user_id):
    if auth_enabled and user_id == "admin":
        return User()
    return None

def generate_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_hex(32)
        session['_csrf_token'] = token
    return token

def validate_csrf_token():
    token = request.form.get('csrf_token', '')
    expected = session.get('_csrf_token', '')
    if not expected or not token or not hmac.compare_digest(str(token), str(expected)):
        abort(400)

def _secure_str_eq(a, b):
    if a is None or b is None:
        return False
    try:
        return hmac.compare_digest(str(a).encode('utf-8'), str(b).encode('utf-8'))
    except Exception:
        return False

# Simple in-memory login rate limiting (per remote address)
_login_attempts = {}
_LOGIN_MAX_FAILURES = 10
_LOGIN_WINDOW_SECONDS = 300

def _login_is_rate_limited(addr):
    now = time.time()
    failures = [t for t in _login_attempts.get(addr, []) if now - t < _LOGIN_WINDOW_SECONDS]
    _login_attempts[addr] = failures
    return len(failures) >= _LOGIN_MAX_FAILURES

def _login_record_failure(addr):
    now = time.time()
    failures = [t for t in _login_attempts.get(addr, []) if now - t < _LOGIN_WINDOW_SECONDS]
    failures.append(now)
    _login_attempts[addr] = failures

def _login_reset_failures(addr):
    _login_attempts.pop(addr, None)

@app.context_processor
def inject_auth_status():
    return dict(auth_enabled=auth_enabled, csrf_token=generate_csrf_token())

@app.before_request
def require_login():
    if not auth_enabled:
        return
    if request.endpoint == 'static': # Allow static files
        return
    if request.endpoint == 'login': # Allow login page
        return
    if not current_user.is_authenticated:
        next_target = request.full_path
        if next_target.endswith('?') and not request.query_string:
            next_target = request.path
        return redirect(url_for('login', next=next_target))

@app.after_request
def set_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return response

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'check_same_thread': False, 'timeout': 30},
}

db = SQLAlchemy(app)

class Snippet(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    parsing_mode = db.Column(db.String(50), default='weblint')
    notes = db.Column(db.Text, nullable=True)
    parts = db.Column(db.Text, nullable=True)  # JSON array of {name, content, type} when multi-part
    archived = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def part_list(self):
        return get_snippet_parts(self)

    @property
    def part_count(self):
        return len(get_snippet_parts(self))

def get_snippet_parts(snippet):
    """Return a normalized list of parts for a snippet (legacy single-part or multi-part)."""
    if snippet.parts:
        try:
            parsed = json.loads(snippet.parts)
            if isinstance(parsed, list) and len(parsed) >= 2:
                normalized = [
                    {
                        'name': (p.get('name') or f'Part {i + 1}').strip() or f'Part {i + 1}',
                        'content': p.get('content', ''),
                        'type': p.get('type', 'plain') if p.get('type') in ('plain', 'markdown', 'html') else 'plain',
                    }
                    for i, p in enumerate(parsed)
                    if isinstance(p, dict)
                ]
                if len(normalized) >= 2:
                    return normalized
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
    return [{
        'name': '',
        'content': snippet.content or '',
        'type': snippet.type if snippet.type in ('plain', 'markdown', 'html') else 'plain',
    }]

def parts_from_form(form):
    """Build parts list from editor form fields (part_* arrays or legacy content/type)."""
    contents = form.getlist('part_content')
    if contents:
        names = form.getlist('part_name')
        types = form.getlist('part_type')
        parts = []
        for i, content in enumerate(contents):
            name = names[i].strip() if i < len(names) and names[i] else f'Part {i + 1}'
            ptype = types[i] if i < len(types) and types[i] in ('plain', 'markdown', 'html') else 'plain'
            parts.append({'name': name, 'content': content, 'type': ptype})
        return parts

    # Legacy single-field form
    return [{
        'name': 'Part 1',
        'content': form.get('content', ''),
        'type': form.get('type', 'plain') if form.get('type') in ('plain', 'markdown', 'html') else 'plain',
    }]

def apply_parts_to_snippet(snippet, parts):
    """Persist parts on a snippet; sync content/type to the first part; clear parts when single."""
    if not parts:
        parts = [{'name': 'Part 1', 'content': '', 'type': 'plain'}]

    snippet.content = parts[0]['content']
    snippet.type = parts[0]['type']

    if len(parts) >= 2:
        snippet.parts = json.dumps(parts)
    else:
        snippet.parts = None

with app.app_context():
    db.create_all()
    migrate_schema(db_path)

    json_file = os.path.join(base_dir, 'snippets.json')
    if os.path.exists(json_file) and Snippet.query.count() == 0:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    snippets_to_insert = [
                        {
                            'id': item.get('id', str(uuid.uuid4())),
                            'title': item.get('title', 'Untitled'),
                            'content': item.get('content', ''),
                            'type': item.get('type', 'plain')
                        }
                        for item in data
                    ]
                    db.session.bulk_insert_mappings(Snippet, snippets_to_insert)
                    db.session.commit()
                    print(f"Successfully migrated {len(data)} snippets from JSON to SQLite.")
                    os.rename(json_file, json_file + '.bak')
        except Exception as e:
            print(f"Error migrating JSON data: {e}")

@app.route('/')
def index():
    query = request.args.get('q', '').lower()
    
    if query:
        snippets = Snippet.query.filter(
            Snippet.archived == False,
            (Snippet.title.ilike(f'%{query}%')) |
            (Snippet.content.ilike(f'%{query}%')) |
            (Snippet.notes.ilike(f'%{query}%')) |
            (Snippet.parts.ilike(f'%{query}%'))
        ).order_by(Snippet.title).all()
    else:
        snippets = Snippet.query.filter_by(archived=False).order_by(Snippet.title).all()
    
    recent_snippets = []
    if 'recent_snippets' in session:
        # Fetch the snippets in the order of the IDs in the session
        for snippet_id in session['recent_snippets']:
            snippet = db.session.get(Snippet, snippet_id)
            if snippet and not snippet.archived:
                recent_snippets.append(snippet)

    return render_template('index.html', snippets=snippets, query=query, recent_snippets=recent_snippets)

@app.route('/new', methods=['GET', 'POST'])
def new_snippet():
    if request.method == 'POST':
        validate_csrf_token()
        title = request.form.get('title', '').strip()
        notes = request.form.get('notes')
        parsing_mode = request.form.get('parsing_mode', 'weblint')
        parts = parts_from_form(request.form)

        if not title:
            flash('Title is required.')
            return render_template(
                'editor.html',
                snippet=None,
                form_parts=parts,
                form_title=title,
                form_notes=notes,
                form_parsing_mode=parsing_mode,
            ), 400

        if not any(p['content'].strip() for p in parts):
            flash('At least one part must have content.')
            return render_template(
                'editor.html',
                snippet=None,
                form_parts=parts,
                form_title=title,
                form_notes=notes,
                form_parsing_mode=parsing_mode,
            ), 400

        new_snip = Snippet(
            title=title,
            content=parts[0]['content'],
            type=parts[0]['type'],
            parsing_mode=parsing_mode,
            notes=notes
        )
        apply_parts_to_snippet(new_snip, parts)
        db.session.add(new_snip)
        db.session.commit()
        return redirect(url_for('view_snippet', s_id=new_snip.id))
    return render_template('editor.html', snippet=None, form_parts=None)

@app.route('/edit/<s_id>', methods=['GET', 'POST'])
def edit_snippet(s_id):
    snippet = db.session.get(Snippet, s_id)
    if not snippet:
        abort(404)
    
    if request.method == 'POST':
        validate_csrf_token()
        title = request.form.get('title', '').strip()
        notes = request.form.get('notes')
        parsing_mode = request.form.get('parsing_mode', 'weblint')
        parts = parts_from_form(request.form)

        if not title:
            flash('Title is required.')
            return render_template(
                'editor.html',
                snippet=snippet,
                form_parts=parts,
                form_title=title,
                form_notes=notes,
                form_parsing_mode=parsing_mode,
            ), 400

        if not any(p['content'].strip() for p in parts):
            flash('At least one part must have content.')
            return render_template(
                'editor.html',
                snippet=snippet,
                form_parts=parts,
                form_title=title,
                form_notes=notes,
                form_parsing_mode=parsing_mode,
            ), 400

        snippet.title = title
        snippet.parsing_mode = parsing_mode
        snippet.notes = notes
        apply_parts_to_snippet(snippet, parts)
        db.session.commit()
        return redirect(url_for('view_snippet', s_id=s_id))
        
    return render_template('editor.html', snippet=snippet, form_parts=get_snippet_parts(snippet))

@app.route('/view/<s_id>')
def view_snippet(s_id):
    snippet = db.session.get(Snippet, s_id)
    if not snippet:
        abort(404)

    if not snippet.archived:
        recent_snippets = session.get('recent_snippets', [])
        if s_id in recent_snippets:
            recent_snippets.remove(s_id)
        recent_snippets.insert(0, s_id)
        session['recent_snippets'] = recent_snippets[:5]

    parts = get_snippet_parts(snippet)
    return render_template('view.html', snippet=snippet, parts=parts)

@app.route('/archive/<s_id>', methods=['POST'])
def archive_snippet(s_id):
    validate_csrf_token()
    snippet = db.session.get(Snippet, s_id)
    if not snippet:
        abort(404)

    recent_snippets = session.get('recent_snippets', [])
    if s_id in recent_snippets:
        recent_snippets.remove(s_id)
        session['recent_snippets'] = recent_snippets

    snippet.archived = True
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/unarchive/<s_id>', methods=['POST'])
def unarchive_snippet(s_id):
    validate_csrf_token()
    snippet = db.session.get(Snippet, s_id)
    if not snippet:
        abort(404)

    snippet.archived = False
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/archived')
def archived_snippets():
    snippets = Snippet.query.filter_by(archived=True).order_by(Snippet.title).all()
    return render_template('archived.html', snippets=snippets)

@app.route('/delete/<s_id>', methods=['POST'])
def delete_snippet(s_id):
    validate_csrf_token()
    snippet = db.session.get(Snippet, s_id)
    if not snippet:
        abort(404)

    was_archived = snippet.archived

    recent_snippets = session.get('recent_snippets', [])
    if s_id in recent_snippets:
        recent_snippets.remove(s_id)
        session['recent_snippets'] = recent_snippets

    db.session.delete(snippet)
    db.session.commit()
    if was_archived:
        return redirect(url_for('archived_snippets'))
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not auth_enabled:
         return redirect(url_for('index'))
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        validate_csrf_token()
        addr = request.remote_addr or 'unknown'
        if _login_is_rate_limited(addr):
            flash('Too many failed login attempts. Please try again in a few minutes.')
            return render_template('login.html'), 429

        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if _secure_str_eq(username, auth_user) and _secure_str_eq(password, auth_pass):
            _login_reset_failures(addr)
            login_user(User())
            next_page = request.args.get('next')
            if not is_safe_url(next_page):
                next_page = url_for('index')
            return redirect(next_page)
        else:
            _login_record_failure(addr)
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    validate_csrf_token()
    logout_user()
    return redirect(url_for('login'))

def run_server(host=None, port=None, open_browser=False):
    """Start the Flask development server (used by __main__ and browser fallback)."""
    host = host or os.environ.get('WEBLINT_HOST', '127.0.0.1' if is_desktop_mode() else '0.0.0.0')
    port = int(port or os.environ.get('WEBLINT_PORT', '5000'))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Prefer the native desktop window; only auto-open a browser as an explicit fallback.
    should_open_browser = open_browser or (
        is_desktop_mode()
        and os.environ.get('WEBLINT_USE_BROWSER', '').lower() in ('1', 'true', 'yes')
    )
    if should_open_browser:
        import threading
        import webbrowser
        url = f'http://127.0.0.1:{port}/'
        print(f'Weblint is starting at {url}')
        print(f'Data directory: {base_dir}')
        print('Press Ctrl+C to stop.')
        threading.Timer(1.25, lambda: webbrowser.open(url)).start()
    elif is_desktop_mode():
        print(f'Weblint server listening on http://{host}:{port}/')
        print(f'Data directory: {base_dir}')
        print('Tip: run desktop.py for a native app window, or set WEBLINT_USE_BROWSER=1.')

    app.run(host=host, port=port, debug=debug_mode, use_reloader=False)

if __name__ == '__main__':
    # When launched as `python app.py` in desktop mode, prefer the native window.
    if is_desktop_mode() and os.environ.get('WEBLINT_USE_BROWSER', '').lower() not in ('1', 'true', 'yes'):
        from desktop import main as desktop_main
        desktop_main()
    else:
        run_server()
