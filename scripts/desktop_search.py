"""Run the pinned desktop SearXNG copy through its existing WSGI interface."""

import os
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / "vendor/searxng"
sys.path.insert(0, str(SOURCE))


def main() -> None:
    from searx.webapp import app
    from waitress import serve

    serve(app, host="127.0.0.1", port=int(os.environ["EDUNOVA_SEARCH_PORT"]), threads=4)


if __name__ == "__main__":
    main()
