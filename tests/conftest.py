import os
import secrets
import pytest
import tempfile

# We must set these environment variables before importing app
os.environ['SECRET_KEY'] = 'test_secret_key'
os.environ['WEBLINT_USERNAME'] = 'admin'
os.environ['WEBLINT_PASSWORD'] = 'adminpass'

from app import app as flask_app, db as _db


def _rebind_engine(uri):
    """
    Flask-SQLAlchemy 3 caches engines at init time; updating
    SQLALCHEMY_DATABASE_URI alone does not rebind. Recreate the default engine
    so tests use an isolated DB instead of data/snippets.db.
    """
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = uri
    engines = _db._app_engines.setdefault(flask_app, {})
    for eng in list(engines.values()):
        eng.dispose()
    engines.clear()

    options = dict(_db._engine_options)
    options.update(flask_app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {})
    options['url'] = uri
    _db._apply_driver_defaults(options, flask_app)
    engines[None] = _db._make_engine(None, options, flask_app)


@pytest.fixture
def app():
    """Use an isolated temp-file SQLite DB per test session fixture."""
    fd, db_path = tempfile.mkstemp(suffix='.weblint-test.db')
    os.close(fd)
    uri = f'sqlite:///{db_path}'

    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': uri,
    })

    with flask_app.app_context():
        _db.session.remove()
        _rebind_engine(uri)
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()
        # Dispose test engine; leave unbound so the next fixture rebinds cleanly.
        engines = _db._app_engines.get(flask_app)
        if engines:
            for eng in list(engines.values()):
                eng.dispose()
            engines.clear()

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


def ensure_csrf(client, data=None):
    """Merge a valid session CSRF token into form data for POST requests."""
    payload = dict(data or {})
    with client.session_transaction() as sess:
        token = sess.get('_csrf_token')
        if not token:
            token = secrets.token_hex(32)
            sess['_csrf_token'] = token
    payload['csrf_token'] = token
    return payload


def login(client, username='admin', password='adminpass'):
    """Authenticate the test client with CSRF."""
    return client.post('/login', data=ensure_csrf(client, {
        'username': username,
        'password': password,
    }))
