"""
Electrical Panel Designer
Main Entry Point.
"""
import sys
import os

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from app.gui.main_window import MainWindow


def main():
    # Set high DPI policy for modern Windows 10 / 11 displays
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setApplicationName("Electrical Panel Designer")
    app.setOrganizationName("Industrial Automation Engineering")
    app.setFont(QFont("Segoe UI", 9))

    # Set Application & Window Icon
    def _find_icon(icon_name="epd_logo.png"):
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "app", "resources", "icons", icon_name))
            candidates.append(os.path.join(sys._MEIPASS, "resources", "icons", icon_name))
            candidates.append(os.path.join(sys._MEIPASS, icon_name))
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "app", "resources", "icons", icon_name))
        candidates.append(os.path.join(exe_dir, "resources", "icons", icon_name))
        candidates.append(os.path.join(exe_dir, icon_name))
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(script_dir, "app", "resources", "icons", icon_name))
        candidates.append(os.path.join(os.getcwd(), "app", "resources", "icons", icon_name))
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    icon_path = _find_icon("epd_logo.png")
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

