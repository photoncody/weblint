"""
Entry point for the standalone Weblint desktop binary (PyInstaller).

Sets desktop mode so SECRET_KEY is auto-managed and the default browser opens.
"""
import os

# Must be set before importing app so secret-key / data-dir logic applies.
os.environ.setdefault('WEBLINT_DESKTOP', '1')

from app import run_server  # noqa: E402


if __name__ == '__main__':
    run_server(open_browser=True)
