import os
import pytest
import tempfile

# We must set these environment variables before importing app
os.environ['SECRET_KEY'] = 'test_secret_key'
os.environ['WEBLINT_USERNAME'] = 'admin'
os.environ['WEBLINT_PASSWORD'] = 'adminpass'

from app import app as flask_app, db as _db

@pytest.fixture
def app():
    # Update config to use an in-memory database and enable testing mode
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })

    with flask_app.app_context():
        # Ensure all tables are created in the memory database
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db(app):
    with app.app_context():
        yield _db
