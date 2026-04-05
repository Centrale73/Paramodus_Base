import atexit
import webview
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from database import init_db
from api.bridge import ApiBridge
from local_model.manager import bonsai


def _on_exit():
    """Ensure llama-server is terminated when Paramodus closes."""
    bonsai.stop_server()


if __name__ == '__main__':
    init_db()

    # Register cleanup — fires on normal exit, Ctrl-C, and most exceptions
    atexit.register(_on_exit)

    api = ApiBridge()

    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    html_path = os.path.join(base_path, "ui", "index.html")

    window = webview.create_window(
        "Agentic Workspace",
        html_path,
        js_api=api,
        width=1100,
        height=850,
        background_color="#180079"
    )
    api.set_window(window)

    # Also stop on window close (fires before atexit in most cases)
    window.events.closed += _on_exit

    webview.start(debug=True)
