"""PyInstaller entry point: launches the Streamlit app bundled as an exe."""
import os
import sys

from streamlit.web import cli as stcli


def resource_path(relative_path):
    # PyInstaller onefile extracts bundled data next to this launcher under sys._MEIPASS
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        resource_path("bank_usd_rate_compare.py"),
        "--global.developmentMode=false",
        "--server.headless=false",
    ]
    sys.exit(stcli.main())
