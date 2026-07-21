Weblint — local desktop app
===========================

1. Double-click (or run from a terminal) the weblint binary / Weblint.app.
2. A native Weblint window opens with the full UI (no browser required).
3. Snippets are stored in a "data" folder next to the binary.
4. Close the window to quit.

Linux note: the app uses the system WebKitGTK webview. Most desktops already
have it; if the window fails to open, install your distro's webkit2gtk package
(e.g. `sudo apt install libwebkit2gtk-4.1-0`).

Optional environment variables:

  WEBLINT_PORT=5000
  WEBLINT_HOST=127.0.0.1
  WEBLINT_USERNAME / WEBLINT_PASSWORD   (enable login)
  SECRET_KEY                           (override the auto-generated key)
  WEBLINT_USE_BROWSER=1                (open the system browser instead of a native window)

Docker and reverse-proxy hosting remain the recommended option for shared
or always-on deployments. These binaries are meant for single-user local use.
