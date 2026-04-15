import pytest
from app import Snippet

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
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'adminpass'
    }, follow_redirects=True)
    assert response.status_code == 200
    # The index page should render now
    assert b'WebLint' in response.data or b'No snippets found' in response.data

def test_login_post_failure(client):
    """Test logging in with invalid credentials."""
    response = client.post('/login', data={
        'username': 'wrong',
        'password': 'password'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data

def test_index_authenticated(client):
    """Test accessing index while authenticated."""
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})
    response = client.get('/')
    assert response.status_code == 200

def test_create_snippet(client, db):
    """Test creating a new snippet."""
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})
    response = client.post('/new', data={
        'title': 'Test Snippet',
        'content': 'This is a test snippet.',
        'type': 'plain',
        'parsing_mode': 'weblint',
        'notes': 'Test notes'
    }, follow_redirects=True)

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
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})

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
    response = client.post(f'/edit/{snippet_id}', data={
        'title': 'Updated Title',
        'content': 'Updated content',
        'type': 'markdown',
        'parsing_mode': 'batch',
        'notes': 'Updated notes'
    }, follow_redirects=True)

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
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})
    # Test GET
    response = client.get('/edit/non-existent-id')
    assert response.status_code == 404
    # Test POST
    response = client.post('/edit/non-existent-id', data={
        'title': 'New Title',
        'content': 'New content',
        'type': 'plain'
    })
    assert response.status_code == 404

def test_delete_snippet(client, db):
    """Test deleting a snippet."""
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})

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
    response = client.get(f'/delete/{snippet_id}', follow_redirects=True)

    assert response.status_code == 200

    # Verify in DB
    deleted_snippet = db.session.get(Snippet, snippet_id)
    assert deleted_snippet is None

def test_delete_snippet_not_found(client):
    """Test deleting a non-existent snippet returns 404."""
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})
    response = client.get('/delete/non-existent-id')
    assert response.status_code == 404

def test_view_snippet(client, db):
    """Test viewing a snippet."""
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})

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
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})
    response = client.get('/view/non-existent-id')
    assert response.status_code == 404

def test_search_snippets(client, db):
    """Test searching snippets."""
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})

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
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})

    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b'Login' in response.data

    # Verify logged out by accessing protected route
    response = client.get('/')
    assert response.status_code == 302

def test_recent_snippets(client, db):
    """Test recent snippets logic."""
    client.post('/login', data={'username': 'admin', 'password': 'adminpass'})

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
    client.get(f'/delete/{s1.id}')

    with client.session_transaction() as sess:
        assert s1.id not in sess['recent_snippets']
        assert s2.id in sess['recent_snippets']
