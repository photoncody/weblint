Weblint — local desktop binary
==============================

1. Double-click (or run from a terminal) the weblint binary.
2. Your browser should open to http://127.0.0.1:5000/
3. Snippets are stored in a "data" folder next to the binary.
4. Press Ctrl+C in the console/terminal window to stop the server.

Optional environment variables:

  WEBLINT_PORT=5000
  WEBLINT_HOST=127.0.0.1
  WEBLINT_USERNAME / WEBLINT_PASSWORD   (enable login)
  SECRET_KEY                           (override the auto-generated key)

Docker and reverse-proxy hosting remain the recommended option for shared
or always-on deployments. These binaries are meant for single-user local use.
