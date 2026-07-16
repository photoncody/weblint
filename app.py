import os
import uuid
import json
import hmac
from flask import Flask, render_template, request, redirect, url_for, flash, session

def is_safe_url(target):
    return target and target.startswith('/') and not target.startswith('//') and not target.startswith('\\\\')
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)

secret_key = os.environ.get('SECRET_KEY')
if not secret_key or secret_key == 'CHANGE_ME' or secret_key == 'weblint_secret':
    raise ValueError("No secure SECRET_KEY set. Please set the SECRET_KEY environment variable.")
app.secret_key = secret_key

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

@app.context_processor
def inject_auth_status():
    return dict(auth_enabled=auth_enabled)

@app.before_request
def require_login():
    if not auth_enabled:
        return
    if request.endpoint == 'static': # Allow static files
        return
    if request.endpoint == 'login': # Allow login page
        return
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.url))

base_dir = '/data' if os.path.exists('/data') else os.path.join(os.getcwd(), 'data')
os.makedirs(base_dir, exist_ok=True)
db_path = os.path.join(base_dir, 'snippets.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Snippet(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    parsing_mode = db.Column(db.String(50), default='weblint')
    notes = db.Column(db.Text, nullable=True)
    parts = db.Column(db.Text, nullable=True)  # JSON array of {name, content, type} when multi-part

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

    # Automatic Database Migration for Missing Columns
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

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error checking/migrating schema: {e}")

    json_file = '/data/snippets.json'
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
            (Snippet.title.ilike(f'%{query}%')) | 
            (Snippet.content.ilike(f'%{query}%'))
        ).order_by(Snippet.title).all()
    else:
        snippets = Snippet.query.order_by(Snippet.title).all()
    
    recent_snippets = []
    if 'recent_snippets' in session:
        # Fetch the snippets in the order of the IDs in the session
        for snippet_id in session['recent_snippets']:
            snippet = db.session.get(Snippet, snippet_id)
            if snippet:
                recent_snippets.append(snippet)

    return render_template('index.html', snippets=snippets, query=query, recent_snippets=recent_snippets)

@app.route('/new', methods=['GET', 'POST'])
def new_snippet():
    if request.method == 'POST':
        parts = parts_from_form(request.form)
        if not any(p['content'].strip() for p in parts):
            flash('At least one part must have content.')
            return render_template('editor.html', snippet=None, form_parts=parts), 400

        new_snip = Snippet(
            title=request.form['title'],
            content=parts[0]['content'],
            type=parts[0]['type'],
            parsing_mode=request.form.get('parsing_mode', 'weblint'),
            notes=request.form.get('notes')
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
        from flask import abort
        abort(404)
    
    if request.method == 'POST':
        parts = parts_from_form(request.form)
        if not any(p['content'].strip() for p in parts):
            flash('At least one part must have content.')
            return render_template('editor.html', snippet=snippet, form_parts=parts), 400

        snippet.title = request.form['title']
        snippet.parsing_mode = request.form.get('parsing_mode', 'weblint')
        snippet.notes = request.form.get('notes')
        apply_parts_to_snippet(snippet, parts)
        db.session.commit()
        return redirect(url_for('view_snippet', s_id=s_id))
        
    return render_template('editor.html', snippet=snippet, form_parts=get_snippet_parts(snippet))

@app.route('/view/<s_id>')
def view_snippet(s_id):
    snippet = db.session.get(Snippet, s_id)
    if not snippet:
        from flask import abort
        abort(404)

    recent_snippets = session.get('recent_snippets', [])
    if s_id in recent_snippets:
        recent_snippets.remove(s_id)
    recent_snippets.insert(0, s_id)
    session['recent_snippets'] = recent_snippets[:5]

    parts = get_snippet_parts(snippet)
    return render_template('view.html', snippet=snippet, parts=parts)

@app.route('/delete/<s_id>')
def delete_snippet(s_id):
    snippet = db.session.get(Snippet, s_id)
    if not snippet:
        from flask import abort
        abort(404)

    recent_snippets = session.get('recent_snippets', [])
    if s_id in recent_snippets:
        recent_snippets.remove(s_id)
        session['recent_snippets'] = recent_snippets

    db.session.delete(snippet)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not auth_enabled:
         return redirect(url_for('index'))
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if hmac.compare_digest(username, auth_user) and hmac.compare_digest(password, auth_pass):
            login_user(User())
            next_page = request.args.get('next')
            if not is_safe_url(next_page):
                next_page = url_for('index')
            return redirect(next_page)
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)