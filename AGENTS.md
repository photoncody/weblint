# AGENTS.md

## Cursor Cloud specific instructions

Weblint is a single Python/Flask web app (server-rendered Jinja2 + embedded SQLite, no
separate backing services). Standard setup/run commands live in `README.md` and
`.github/workflows/tests.yml`; only the non-obvious caveats are captured below.

### Dependencies
- Python deps are installed system-wide with `pip install --break-system-packages` (the VM's
  Python is PEP 668 externally-managed). The update script handles this on startup, so no
  venv is used. Console scripts land in `~/.local/bin` (not on PATH) — invoke tools via
  `python3 -m` (e.g. `python3 -m pytest`).
- `pytest`/`pytest-cov` are NOT in `requirements.txt`; they are installed by the update script.

### Running the app (dev)
- `SECRET_KEY` is REQUIRED: `app.py` raises `ValueError` at startup if it is unset or equals
  `CHANGE_ME`/`weblint_secret`. Run with e.g. `SECRET_KEY=$(openssl rand -hex 32) python3 app.py`.
- Dev server listens on `0.0.0.0:5000`. Set `FLASK_DEBUG=true` for auto-reload.
- Auth is opt-in: it is only enabled when BOTH `WEBLINT_USERNAME` and `WEBLINT_PASSWORD` are
  set. Without them every page is publicly accessible (index returns 200, no login redirect).
- SQLite DB lives at `/data/snippets.db` if `/data` exists, else `./data/snippets.db` (the
  `data/` dir is gitignored). Schema is auto-created and auto-migrated on startup.

### Testing
- Unit tests: `PYTHONPATH=. python3 -m pytest tests/`. `tests/conftest.py` sets `SECRET_KEY`
  and auth env vars, so no env setup is needed to run them.
- Gotcha: the tests' attempt to switch to in-memory SQLite does not take effect (Flask-SQLAlchemy
  3.x binds the engine from config at `init_app` time), so the suite actually runs against the
  real `data/snippets.db` and its teardown `drop_all()` DROPS its tables. If you run the tests
  while a local dev server is up, the running app will start returning HTTP 500
  (`no such table: snippet`) until it is restarted (restart re-runs `db.create_all()`).
- `tests/test_docker.sh` is a Docker-based end-to-end test and requires Docker (not installed
  by default in this environment).

### Notes
- Despite the name "Weblint", there is NO linter configured in this repo.
