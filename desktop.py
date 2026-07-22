"""
Entry point for the standalone Weblint desktop app (PyInstaller).

Starts the embedded Flask server on a local port and opens a native
application window (via pywebview) instead of the system browser.
"""
import os
import socket
import sys
import threading
import time
import traceback


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _wait_for_server(host, port, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _log_exception(data_dir, exc):
    try:
        os.makedirs(data_dir, exist_ok=True)
        log_path = os.path.join(data_dir, 'weblint.log')
        with open(log_path, 'a', encoding='utf-8') as fh:
            fh.write('\n--- Weblint desktop error ---\n')
            fh.write(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        return log_path
    except OSError:
        return None


def _resolve_window_icon(resource_root):
    """
    Prefer platform-native icon formats for the title bar / dock / taskbar.
    Falls back across formats so source runs and frozen builds both work.
    """
    static_dir = os.path.join(resource_root, 'static')
    if sys.platform == 'win32':
        preferred = ['weblint.ico', 'weblint.png']
    elif sys.platform == 'darwin':
        preferred = ['weblint.icns', 'weblint.png', 'weblint.ico']
    else:
        preferred = ['weblint.png', 'weblint.ico']

    for name in preferred:
        path = os.path.join(static_dir, name)
        if os.path.isfile(path):
            return path
    return None


def _prepare_native_identity(icon_path):
    """
    Make the native window identify as Weblint (not python/desktop.py) and
    install the brand icon before the GUI toolkit creates the window.
    """
    # Linux/GTK: without this, many WMs show the generic Python icon because
    # WM_CLASS becomes "desktop.py" / "python3" when running from source.
    if sys.platform.startswith('linux'):
        try:
            import gi
            gi.require_version('GLib', '2.0')
            from gi.repository import GLib
            GLib.set_prgname('weblint')
        except Exception:
            pass
        try:
            import gi
            gi.require_version('Gdk', '3.0')
            from gi.repository import Gdk
            Gdk.set_program_class('Weblint')
        except Exception:
            pass
        if icon_path:
            try:
                import gi
                gi.require_version('Gtk', '3.0')
                from gi.repository import Gtk
                Gtk.Window.set_default_icon_from_file(icon_path)
            except Exception as exc:
                print(f'Warning: could not set GTK window icon: {exc}', flush=True)
            # Register under the freedesktop icon theme as "weblint" so window
            # managers that resolve icons by WM_CLASS find our brand mark.
            try:
                import shutil
                icon_dir = os.path.join(os.path.dirname(icon_path), 'icons')
                size_sources = {
                    '16x16': os.path.join(icon_dir, 'weblint-16.png'),
                    '32x32': os.path.join(icon_dir, 'weblint-32.png'),
                    '48x48': os.path.join(icon_dir, 'weblint-48.png'),
                    '256x256': os.path.join(icon_dir, 'weblint-256.png'),
                }
                for size_name, source in size_sources.items():
                    if not os.path.isfile(source):
                        source = icon_path
                    dest_dir = os.path.join(
                        os.path.expanduser('~'),
                        '.local', 'share', 'icons', 'hicolor', size_name, 'apps',
                    )
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(source, os.path.join(dest_dir, 'weblint.png'))
            except Exception as exc:
                print(f'Warning: could not install theme icon: {exc}', flush=True)


def main():
    # Must be set before importing app so secret-key / data-dir logic applies.
    os.environ.setdefault('WEBLINT_DESKTOP', '1')

    from app import app, base_dir, resource_root, run_server

    host = os.environ.get('WEBLINT_HOST', '127.0.0.1')
    port_env = os.environ.get('WEBLINT_PORT', '').strip()
    port = int(port_env) if port_env else _find_free_port()
    url = f'http://{host}:{port}/'

    # Escape hatch: force the old "open in system browser" behavior.
    use_browser = os.environ.get('WEBLINT_USE_BROWSER', '').lower() in ('1', 'true', 'yes')

    if use_browser:
        run_server(host=host, port=port, open_browser=True)
        return

    def _serve():
        # threaded=True so the UI can make concurrent requests while rendering.
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

    server = threading.Thread(target=_serve, name='weblint-flask', daemon=True)
    server.start()

    if not _wait_for_server(host, port):
        raise RuntimeError(f'Weblint failed to start local server at {url}')

    try:
        import webview
    except ImportError as exc:
        # Fall back to browser if pywebview is missing (e.g. source run without desktop deps).
        print('pywebview is not installed; opening the system browser instead.')
        print('Install desktop deps with: pip install -r requirements-desktop.txt')
        log_path = _log_exception(base_dir, exc)
        if log_path:
            print(f'Details written to {log_path}')
        import webbrowser
        webbrowser.open(url)
        server.join()
        return

    print(f'Weblint desktop UI: {url}', flush=True)
    print(f'Data directory: {base_dir}', flush=True)

    icon_path = _resolve_window_icon(resource_root())
    if icon_path:
        print(f'Window icon: {icon_path}', flush=True)
    _prepare_native_identity(icon_path)

    # text_select=True is required: pywebview defaults to False and blocks selecting
    # (and thus copying) preview/output text in the native window.
    webview.create_window(
        title='Weblint',
        url=url,
        width=1280,
        height=860,
        min_size=(900, 640),
        text_select=True,
    )
    # Blocks until the user closes the window; daemon Flask thread exits with the process.
    # icon= sets the native title-bar / dock icon (GTK/Qt; also used by WinForms when present).
    webview.start(icon=icon_path)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - top-level desktop catch for windowed builds
        # Windowed builds have no console; persist the error for troubleshooting.
        try:
            os.environ.setdefault('WEBLINT_DESKTOP', '1')
            from app import base_dir
        except Exception:  # noqa: BLE001
            base_dir = os.path.join(os.path.expanduser('~'), '.weblint')
        log_path = _log_exception(base_dir, exc)
        message = f'Weblint failed to start: {exc}'
        if log_path:
            message += f'\nSee log: {log_path}'
        # Best-effort native error dialog when available.
        try:
            import webview
            from app import resource_root
            icon_path = _resolve_window_icon(resource_root())
            webview.create_window(
                'Weblint',
                html=f'<h3>Weblint error</h3><pre>{message}</pre>',
                width=640,
                height=360,
                text_select=True,
            )
            webview.start(icon=icon_path)
        except Exception:  # noqa: BLE001
            print(message, file=sys.stderr)
            raise SystemExit(1) from exc
