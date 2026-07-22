import json
import os
import pytest
from app import Snippet, get_snippet_parts
from conftest import ensure_csrf, login

def test_index_unauthenticated(client):
    """Test that index redirects to login when not authenticated."""
    response = client.get('/')
    assert response.status_code == 302
    assert '/login' in response.headers.get('Location', '')

def test_login_get(client):
    """Test getting the login page."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login' in response.data

def test_login_post_success(client):
    """Test logging in with valid credentials."""
    response = client.post('/login', data=ensure_csrf(client, {
        'username': 'admin',
        'password': 'adminpass'
    }), follow_redirects=True)
    assert response.status_code == 200
    # The index page should render now
    assert b'WebLint' in response.data or b'No snippets found' in response.data

def test_login_post_failure(client):
    """Test logging in with invalid credentials."""
    response = client.post('/login', data=ensure_csrf(client, {
        'username': 'wrong',
        'password': 'password'
    }), follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data

def test_index_authenticated(client):
    """Test accessing index while authenticated."""
    login(client)
    response = client.get('/')
    assert response.status_code == 200

def test_create_snippet(client, db):
    """Test creating a new snippet."""
    login(client)
    response = client.post('/new', data=ensure_csrf(client, {
        'title': 'Test Snippet',
        'content': 'This is a test snippet.',
        'type': 'plain',
        'parsing_mode': 'weblint',
        'notes': 'Test notes'
    }), follow_redirects=True)

    assert response.status_code == 200
    assert b'Test Snippet' in response.data

    # Verify in DB
    snippet = Snippet.query.filter_by(title='Test Snippet').first()
    assert snippet is not None
    assert snippet.content == 'This is a test snippet.'
    assert snippet.type == 'plain'
    assert snippet.parsing_mode == 'weblint'

def test_edit_snippet(client, db):
    """Test editing an existing snippet."""
    login(client)

    # Create snippet first
    snippet = Snippet(
        title='Original Title',
        content='Original content',
        type='plain',
        parsing_mode='weblint'
    )
    db.session.add(snippet)
    db.session.commit()

    snippet_id = snippet.id

    # Edit snippet
    response = client.post(f'/edit/{snippet_id}', data=ensure_csrf(client, {
        'title': 'Updated Title',
        'content': 'Updated content',
        'type': 'markdown',
        'parsing_mode': 'batch',
        'notes': 'Updated notes'
    }), follow_redirects=True)

    assert response.status_code == 200
    assert b'Updated Title' in response.data

    # Verify in DB
    updated_snippet = db.session.get(Snippet, snippet_id)
    assert updated_snippet.title == 'Updated Title'
    assert updated_snippet.content == 'Updated content'
    assert updated_snippet.type == 'markdown'
    assert updated_snippet.parsing_mode == 'batch'

def test_edit_snippet_not_found(client):
    """Test editing a non-existent snippet returns 404."""
    login(client)
    # Test GET
    response = client.get('/edit/non-existent-id')
    assert response.status_code == 404
    # Test POST
    response = client.post('/edit/non-existent-id', data=ensure_csrf(client, {
        'title': 'New Title',
        'content': 'New content',
        'type': 'plain'
    }))
    assert response.status_code == 404

def test_delete_snippet(client, db):
    """Test deleting a snippet."""
    login(client)

    # Create snippet first
    snippet = Snippet(
        title='To be deleted',
        content='Delete me',
        type='plain',
        parsing_mode='weblint'
    )
    db.session.add(snippet)
    db.session.commit()

    snippet_id = snippet.id

    # Delete snippet
    response = client.post(f'/delete/{snippet_id}', data=ensure_csrf(client), follow_redirects=True)

    assert response.status_code == 200

    # Verify in DB
    deleted_snippet = db.session.get(Snippet, snippet_id)
    assert deleted_snippet is None

def test_delete_snippet_not_found(client):
    """Test deleting a non-existent snippet returns 404."""
    login(client)
    response = client.post('/delete/non-existent-id', data=ensure_csrf(client))
    assert response.status_code == 404

def test_view_snippet(client, db):
    """Test viewing a snippet."""
    login(client)

    # Create snippet first
    snippet = Snippet(
        title='View Me',
        content='Content to view',
        type='plain',
        parsing_mode='weblint'
    )
    db.session.add(snippet)
    db.session.commit()

    # View snippet
    response = client.get(f'/view/{snippet.id}')

    assert response.status_code == 200
    assert b'View Me' in response.data

def test_view_snippet_not_found(client):
    """Test viewing a non-existent snippet returns 404."""
    login(client)
    response = client.get('/view/non-existent-id')
    assert response.status_code == 404

def test_search_snippets(client, db):
    """Test searching snippets."""
    login(client)

    # Create snippets
    db.session.add(Snippet(title='Apple Snippet', content='Apple content', type='plain', parsing_mode='weblint'))
    db.session.add(Snippet(title='Banana Snippet', content='Banana content', type='plain', parsing_mode='weblint'))
    db.session.commit()

    # Search for Apple
    response = client.get('/?q=apple')
    assert response.status_code == 200
    assert b'Apple Snippet' in response.data
    assert b'Banana Snippet' not in response.data

    # Search for Banana content
    response = client.get('/?q=banana')
    assert response.status_code == 200
    assert b'Banana Snippet' in response.data
    assert b'Apple Snippet' not in response.data

def test_logout(client):
    """Test logout."""
    login(client)

    response = client.post('/logout', data=ensure_csrf(client), follow_redirects=True)
    assert response.status_code == 200
    assert b'Login' in response.data

    # Verify logged out by accessing protected route
    response = client.get('/')
    assert response.status_code == 302

def test_recent_snippets(client, db):
    """Test recent snippets logic."""
    login(client)

    # Create snippets
    s1 = Snippet(title='Snippet 1', content='Content 1', type='plain', parsing_mode='weblint')
    s2 = Snippet(title='Snippet 2', content='Content 2', type='plain', parsing_mode='weblint')
    db.session.add(s1)
    db.session.add(s2)
    db.session.commit()

    # Access snippet 1
    client.get(f'/view/{s1.id}')

    # Check index for recent snippet 1
    response = client.get('/')
    assert response.status_code == 200
    assert b'Recently Selected' in response.data
    assert b'Snippet 1' in response.data

    # Access snippet 2
    client.get(f'/view/{s2.id}')

    with client.session_transaction() as sess:
        assert sess['recent_snippets'][0] == s2.id
        assert sess['recent_snippets'][1] == s1.id

    # Check index for both
    response = client.get('/')
    assert b'Recently Selected' in response.data

    # Delete snippet 1
    client.post(f'/delete/{s1.id}', data=ensure_csrf(client))

    with client.session_transaction() as sess:
        assert s1.id not in sess['recent_snippets']
        assert s2.id in sess['recent_snippets']

def test_archive_snippet(client, db):
    """Test archiving a snippet moves it off the index and onto /archived."""
    login(client)

    snippet = Snippet(
        title='To be archived',
        content='Archive me',
        type='plain',
        parsing_mode='weblint'
    )
    db.session.add(snippet)
    db.session.commit()
    snippet_id = snippet.id

    response = client.get('/')
    assert b'To be archived' in response.data

    response = client.post(f'/archive/{snippet_id}', data=ensure_csrf(client), follow_redirects=True)
    assert response.status_code == 200

    archived = db.session.get(Snippet, snippet_id)
    assert archived is not None
    assert archived.archived is True

    response = client.get('/')
    assert b'To be archived' not in response.data

    response = client.get('/archived')
    assert response.status_code == 200
    assert b'To be archived' in response.data
    assert b'Archived Snippets' in response.data

def test_unarchive_snippet(client, db):
    """Test unarchiving restores a snippet to the index."""
    login(client)

    snippet = Snippet(
        title='Restore Me',
        content='Unarchive me',
        type='plain',
        parsing_mode='weblint',
        archived=True
    )
    db.session.add(snippet)
    db.session.commit()
    snippet_id = snippet.id

    response = client.post(f'/unarchive/{snippet_id}', data=ensure_csrf(client), follow_redirects=True)
    assert response.status_code == 200

    restored = db.session.get(Snippet, snippet_id)
    assert restored is not None
    assert restored.archived is False

    response = client.get('/')
    assert b'Restore Me' in response.data

    response = client.get('/archived')
    assert b'Restore Me' not in response.data

def test_search_excludes_archived(client, db):
    """Test search on the index excludes archived snippets."""
    login(client)

    db.session.add(Snippet(title='Active Apple', content='Apple content', type='plain', parsing_mode='weblint'))
    db.session.add(Snippet(
        title='Archived Apple',
        content='Apple content archived',
        type='plain',
        parsing_mode='weblint',
        archived=True
    ))
    db.session.commit()

    response = client.get('/?q=apple')
    assert response.status_code == 200
    assert b'Active Apple' in response.data
    assert b'Archived Apple' not in response.data

def test_archive_removes_from_recent(client, db):
    """Test archiving removes a snippet from the recent list."""
    login(client)

    snippet = Snippet(title='Recent Archive', content='Content', type='plain', parsing_mode='weblint')
    db.session.add(snippet)
    db.session.commit()

    client.get(f'/view/{snippet.id}')
    with client.session_transaction() as sess:
        assert snippet.id in sess['recent_snippets']

    client.post(f'/archive/{snippet.id}', data=ensure_csrf(client))

    with client.session_transaction() as sess:
        assert snippet.id not in sess['recent_snippets']

    response = client.get('/')
    assert b'Recent Archive' not in response.data
    assert b'Recently Selected' not in response.data

def test_view_archived_snippet(client, db):
    """Test viewing an archived snippet still works and does not add it to recent."""
    login(client)

    snippet = Snippet(
        title='Archived View',
        content='Still viewable',
        type='plain',
        parsing_mode='weblint',
        archived=True
    )
    db.session.add(snippet)
    db.session.commit()

    response = client.get(f'/view/{snippet.id}')
    assert response.status_code == 200
    assert b'Archived View' in response.data
    assert b'Unarchive' in response.data

    with client.session_transaction() as sess:
        assert snippet.id not in sess.get('recent_snippets', [])

def test_archive_snippet_not_found(client):
    """Test archiving a non-existent snippet returns 404."""
    login(client)
    response = client.post('/archive/non-existent-id', data=ensure_csrf(client))
    assert response.status_code == 404

def test_unarchive_snippet_not_found(client):
    """Test unarchiving a non-existent snippet returns 404."""
    login(client)
    response = client.post('/unarchive/non-existent-id', data=ensure_csrf(client))
    assert response.status_code == 404

def test_delete_archived_snippet_redirects_to_archived(client, db):
    """Deleting an archived snippet redirects back to the archived list."""
    login(client)

    snippet = Snippet(
        title='Delete Archived',
        content='Gone',
        type='plain',
        parsing_mode='weblint',
        archived=True
    )
    db.session.add(snippet)
    db.session.commit()
    snippet_id = snippet.id

    response = client.post(f'/delete/{snippet_id}', data=ensure_csrf(client), follow_redirects=False)
    assert response.status_code == 302
    assert '/archived' in response.headers.get('Location', '')

    assert db.session.get(Snippet, snippet_id) is None

def test_create_multipart_snippet(client, db):
    """Test creating a multi-part snippet with shared-variable parts."""
    login(client)
    response = client.post('/new', data=ensure_csrf(client, {
        'title': 'Site Edge Stack',
        'parsing_mode': 'weblint',
        'notes': 'Shared IPs across devices',
        'part_name': ['Fortigate', 'Cisco Router', 'Cisco Switch'],
        'part_content': [
            'set ip [[Input=WAN_IP|1.2.3.4]]',
            'ip address [[Input=WAN_IP|1.2.3.4]]',
            'vlan ip [[Input=LAN_IP|10.0.0.1]]',
        ],
        'part_type': ['plain', 'plain', 'plain'],
    }), follow_redirects=True)

    assert response.status_code == 200
    assert b'Site Edge Stack' in response.data
    assert b'Fortigate' in response.data
    assert b'Cisco Router' in response.data
    assert b'Cisco Switch' in response.data

    snippet = Snippet.query.filter_by(title='Site Edge Stack').first()
    assert snippet is not None
    assert snippet.parts is not None
    parts = json.loads(snippet.parts)
    assert len(parts) == 3
    assert parts[0]['name'] == 'Fortigate'
    assert parts[1]['name'] == 'Cisco Router'
    assert parts[2]['name'] == 'Cisco Switch'
    # content/type synced to first part
    assert snippet.content == 'set ip [[Input=WAN_IP|1.2.3.4]]'
    assert snippet.type == 'plain'
    assert snippet.part_count == 3
    assert snippet.archived is False
def test_create_single_part_clears_parts_column(client, db):
    """Single-part create should leave parts null (legacy mode)."""
    login(client)
    client.post('/new', data=ensure_csrf(client, {
        'title': 'Single Part',
        'parsing_mode': 'weblint',
        'part_name': ['Only'],
        'part_content': ['Hello [[Input=Name|World]]'],
        'part_type': ['markdown'],
    }), follow_redirects=True)

    snippet = Snippet.query.filter_by(title='Single Part').first()
    assert snippet is not None
    assert snippet.parts is None
    assert snippet.content == 'Hello [[Input=Name|World]]'
    assert snippet.type == 'markdown'
    assert snippet.part_count == 1
    assert get_snippet_parts(snippet)[0]['content'] == snippet.content

def test_edit_multipart_snippet(client, db):
    """Test editing into and within multi-part snippets."""
    login(client)

    snippet = Snippet(
        title='Device Pack',
        content='Original',
        type='plain',
        parsing_mode='weblint'
    )
    db.session.add(snippet)
    db.session.commit()
    snippet_id = snippet.id

    response = client.post(f'/edit/{snippet_id}', data=ensure_csrf(client, {
        'title': 'Device Pack Updated',
        'parsing_mode': 'weblint',
        'notes': 'Updated',
        'part_name': ['Firewall', 'Switch'],
        'part_content': ['fw [[Input=IP|10.0.0.1]]', 'sw [[Input=IP|10.0.0.1]]'],
        'part_type': ['plain', 'html'],
    }), follow_redirects=True)

    assert response.status_code == 200
    assert b'Device Pack Updated' in response.data
    assert b'Firewall' in response.data
    assert b'Switch' in response.data

    updated = db.session.get(Snippet, snippet_id)
    assert updated.title == 'Device Pack Updated'
    assert updated.part_count == 2
    parts = json.loads(updated.parts)
    assert parts[1]['type'] == 'html'
    assert updated.content == 'fw [[Input=IP|10.0.0.1]]'

def test_view_legacy_single_part_still_works(client, db):
    """Legacy snippets without parts JSON still render one preview."""
    login(client)
    snippet = Snippet(
        title='Legacy Snippet',
        content='Hi [[Input=Name|Ada]]',
        type='plain',
        parsing_mode='weblint',
        parts=None
    )
    db.session.add(snippet)
    db.session.commit()

    response = client.get(f'/view/{snippet.id}')
    assert response.status_code == 200
    assert b'Legacy Snippet' in response.data
    assert b'Live Preview' in response.data
    assert b'parts-data' in response.data

def test_multipart_badge_on_index(client, db):
    """Index shows a parts count for multi-part snippets."""
    login(client)
    snippet = Snippet(
        title='Multi Badge',
        content='a',
        type='plain',
        parsing_mode='weblint',
        parts=json.dumps([
            {'name': 'A', 'content': 'a', 'type': 'plain'},
            {'name': 'B', 'content': 'b', 'type': 'plain'},
        ])
    )
    db.session.add(snippet)
    db.session.commit()

    response = client.get('/')
    assert response.status_code == 200
    assert b'Multi Badge' in response.data
    assert b'2 parts' in response.data


def test_desktop_secret_key_persists(tmp_path, monkeypatch):
    """Desktop mode auto-generates and reuses a secret key under the data dir."""
    from app import resolve_secret_key

    monkeypatch.setenv('WEBLINT_DESKTOP', '1')
    monkeypatch.delenv('SECRET_KEY', raising=False)

    data_dir = tmp_path / 'data'
    key1 = resolve_secret_key(str(data_dir))
    key2 = resolve_secret_key(str(data_dir))

    assert key1
    assert key1 == key2
    key_file = data_dir / 'secret.key'
    assert key_file.read_text(encoding='utf-8').strip() == key1
    assert (key_file.stat().st_mode & 0o777) == 0o600


def test_resolve_secret_key_requires_env_outside_desktop(tmp_path, monkeypatch):
    """Non-desktop mode still requires an explicit SECRET_KEY."""
    from app import resolve_secret_key

    monkeypatch.delenv('WEBLINT_DESKTOP', raising=False)
    monkeypatch.delenv('SECRET_KEY', raising=False)
    monkeypatch.setattr('app.is_frozen', lambda: False)

    with pytest.raises(ValueError, match='SECRET_KEY'):
        resolve_secret_key(str(tmp_path))


def test_resource_root_includes_templates():
    """Templates resolve from the source tree (and from the bundle when frozen)."""
    from app import resource_root
    import os

    root = resource_root()
    assert os.path.isdir(os.path.join(root, 'templates'))
    assert os.path.isfile(os.path.join(root, 'templates', 'index.html'))


def test_find_free_port_and_wait_helpers():
    """Desktop helpers can bind a free port and detect a listening server."""
    import socket
    import threading
    from desktop import _find_free_port, _wait_for_server

    port = _find_free_port()
    assert isinstance(port, int)
    assert 0 < port < 65536

    # Nothing listening yet
    assert _wait_for_server('127.0.0.1', port, timeout=0.3) is False

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', port))
    srv.listen(1)

    def _accept():
        try:
            conn, _ = srv.accept()
            conn.close()
        except OSError:
            pass

    t = threading.Thread(target=_accept, daemon=True)
    t.start()
    try:
        assert _wait_for_server('127.0.0.1', port, timeout=2.0) is True
    finally:
        srv.close()


def test_resolve_window_icon_prefers_platform_asset():
    """Desktop icon resolver finds the Weblint brand icon next to the favicon."""
    import os
    from desktop import _resolve_window_icon
    from app import resource_root

    root = resource_root()
    icon = _resolve_window_icon(root)
    assert icon is not None
    assert os.path.isfile(icon)
    assert os.path.basename(icon).startswith('weblint.')
    # Source tree should also still ship the web favicon used to generate these.
    assert os.path.isfile(os.path.join(root, 'static', 'favicon.svg'))


def test_desktop_create_window_enables_text_select():
    """
    pywebview defaults text_select=False, which blocks selecting and copying text
    in the native desktop window. Both the main UI and error dialog must opt in.
    """
    import ast
    from pathlib import Path

    tree = ast.parse(Path('desktop.py').read_text(encoding='utf-8'))
    create_window_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        if name != 'create_window':
            continue
        kwargs = {
            kw.arg: kw.value
            for kw in node.keywords
            if kw.arg is not None
        }
        create_window_calls.append(kwargs)

    assert create_window_calls, 'expected webview.create_window calls in desktop.py'
    for kwargs in create_window_calls:
        assert 'text_select' in kwargs, 'create_window must pass text_select'
        value = kwargs['text_select']
        assert isinstance(value, ast.Constant) and value.value is True


def test_is_safe_url_rejects_open_redirects():
    """Relative paths are allowed; protocol-relative and backslash tricks are not."""
    from app import is_safe_url

    assert is_safe_url('/view/abc')
    assert is_safe_url('/view/abc?x=1')
    assert not is_safe_url('//evil.com')
    assert not is_safe_url('/\\evil.com')
    assert not is_safe_url('https://evil.com')
    assert not is_safe_url('\\\\evil.com')
    assert not is_safe_url(None)
    assert not is_safe_url('')


def test_login_preserves_safe_next(client):
    """After login, relative next targets are honored."""
    response = client.post('/login?next=/archived', data=ensure_csrf(client, {
        'username': 'admin',
        'password': 'adminpass',
    }), follow_redirects=False)
    assert response.status_code == 302
    assert response.headers.get('Location', '').endswith('/archived')


def test_login_rejects_unsafe_next(client):
    """Unsafe next targets fall back to the index."""
    response = client.post('/login?next=//evil.com', data=ensure_csrf(client, {
        'username': 'admin',
        'password': 'adminpass',
    }), follow_redirects=False)
    assert response.status_code == 302
    location = response.headers.get('Location', '')
    assert 'evil.com' not in location
    assert location.endswith('/')


def test_login_rate_limit_shared_storage(client, app):
    """Failed logins are persisted and enforce the shared per-IP limit."""
    from app import (
        _LOGIN_MAX_FAILURES,
        _login_is_rate_limited,
        _login_record_failure,
        _login_reset_failures,
        _login_attempts_db_path,
    )

    addr = '127.0.0.1'  # Flask test client default remote_addr
    _login_reset_failures(addr)
    assert not _login_is_rate_limited(addr)
    assert os.path.isfile(_login_attempts_db_path())

    for _ in range(_LOGIN_MAX_FAILURES):
        _login_record_failure(addr)
    assert _login_is_rate_limited(addr)

    # Endpoint should reject further attempts while limited.
    response = client.post('/login', data=ensure_csrf(client, {
        'username': 'admin',
        'password': 'wrong',
    }))
    assert response.status_code == 429
    assert b'Too many failed login attempts' in response.data

    # Successful path is blocked until the window clears / reset.
    response = client.post('/login', data=ensure_csrf(client, {
        'username': 'admin',
        'password': 'adminpass',
    }))
    assert response.status_code == 429

    _login_reset_failures(addr)
    response = client.post('/login', data=ensure_csrf(client, {
        'username': 'admin',
        'password': 'adminpass',
    }), follow_redirects=False)
    assert response.status_code == 302
    assert not _login_is_rate_limited(addr)


def test_auth_redirect_uses_relative_next(client):
    """require_login should pass a relative next path, not an absolute URL."""
    response = client.get('/archived', follow_redirects=False)
    assert response.status_code == 302
    location = response.headers.get('Location', '')
    assert '/login' in location
    assert 'next=' in location
    # Relative path only (no scheme://host)
    assert 'http://' not in location
    assert 'https://' not in location


def test_state_changing_get_routes_rejected(client, db):
    """Archive/delete/logout must not mutate state via GET."""
    login(client)
    snippet = Snippet(title='Protected', content='x', type='plain', parsing_mode='weblint')
    db.session.add(snippet)
    db.session.commit()
    snippet_id = snippet.id

    assert client.get(f'/delete/{snippet_id}').status_code == 405
    assert client.get(f'/archive/{snippet_id}').status_code == 405
    assert client.get(f'/unarchive/{snippet_id}').status_code == 405
    assert client.get('/logout').status_code == 405
    assert db.session.get(Snippet, snippet_id) is not None
    assert db.session.get(Snippet, snippet_id).archived is False


def test_csrf_required_on_mutating_posts(client, db):
    """POSTs without a valid CSRF token are rejected."""
    login(client)
    snippet = Snippet(title='CSRF Guard', content='x', type='plain', parsing_mode='weblint')
    db.session.add(snippet)
    db.session.commit()

    assert client.post(f'/delete/{snippet.id}', data={}).status_code == 400
    assert client.post(f'/archive/{snippet.id}', data={'csrf_token': 'bogus'}).status_code == 400
    assert db.session.get(Snippet, snippet.id) is not None


def test_security_headers_present(client):
    """Basic hardening headers are set on responses."""
    response = client.get('/login')
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


def test_search_includes_notes_and_parts(client, db):
    """Search matches notes and non-first part content."""
    login(client)
    db.session.add(Snippet(
        title='Hidden Title',
        content='first part only',
        type='plain',
        parsing_mode='weblint',
        notes='unique-note-token-xyz',
        parts=json.dumps([
            {'name': 'A', 'content': 'first part only', 'type': 'plain'},
            {'name': 'B', 'content': 'unique-part-token-xyz', 'type': 'plain'},
        ]),
    ))
    db.session.commit()

    response = client.get('/?q=unique-note-token-xyz')
    assert b'Hidden Title' in response.data

    response = client.get('/?q=unique-part-token-xyz')
    assert b'Hidden Title' in response.data


def test_create_requires_title(client, db):
    """Empty title is rejected without creating a snippet."""
    login(client)
    response = client.post('/new', data=ensure_csrf(client, {
        'title': '   ',
        'content': 'has content',
        'type': 'plain',
        'parsing_mode': 'weblint',
    }))
    assert response.status_code == 400
    assert Snippet.query.filter_by(content='has content').first() is None


def test_tests_use_isolated_temp_db(app):
    """Regression: the test suite must not bind to ./data/snippets.db."""
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    assert 'weblint-test.db' in uri
    assert '/data/snippets.db' not in uri
