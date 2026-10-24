"""Start the local app: python -m cardiac_imaging.app [--port 8765] [--no-browser]."""
import argparse
import webbrowser

from .. import config
from .server import make_server


def main():
    """Serve the run history on localhost and (optionally) open it in the browser."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=config.APP_PORT)
    p.add_argument('--no-browser', action='store_true', help="don't open a browser tab")
    args = p.parse_args()
    server = make_server(args.port)
    url = f'http://localhost:{server.server_address[1]}/'
    print(f"Cardiac imaging runs: {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
