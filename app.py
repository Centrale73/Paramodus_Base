import webview
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from database import init_db
from api.bridge import ApiBridge

if __name__ == '__main__':
    init_db()
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
    webview.start(debug=True)
