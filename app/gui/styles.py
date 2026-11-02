"""
Modern Industrial White-Orange-Grey Engineering Theme Stylesheet for PySide6 GUI.
Strictly follows the industrial palette:
- Primary Background: #FFFFFF (Crisp Pure White)
- Primary Dark / Text: #111C24 (Ink Black / Charcoal Navy)
- Secondary Dark / Muted: #616365 (Charcoal Grey)
- Border / Gridlines / Divider: #8A8C8D (Slate / Silver Grey)
- Primary Accent / Highlights / CTA: #FF9A4E (Warm Industrial Orange)
Zero emojis or stickers throughout the application.
"""

DARK_THEME_QSS = """
/* Global Window & Base Controls */
QMainWindow, QDialog, QWidget {
    background-color: #FFFFFF;
    color: #111C24;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    font-size: 12px;
}

/* Ensure labels inside cards never inherit unwanted borders */
QLabel {
    border: none;
    background: transparent;
    color: #111C24;
}

/* Group Boxes & Cards */
QGroupBox {
    border: 1.5px solid #8A8C8D;
    border-radius: 8px;
    margin-top: 22px;
    padding: 18px 14px 14px 14px;
    font-weight: 700;
    font-size: 12px;
    color: #111C24;
    background-color: #FFFFFF;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    background-color: #FFFFFF;
    border-radius: 4px;
    color: #111C24;
}

/* Text Inputs, Multi-line Editors */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #FFFFFF;
    border: 1.5px solid #8A8C8D;
    border-radius: 6px;
    color: #111C24;
    padding: 5px 10px;
    min-height: 32px;
    font-size: 12px;
    selection-background-color: #FF9A4E;
    selection-color: #111C24;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1.5px solid #FF9A4E;
    background-color: #FFFFFF;
}

/* SpinBox & DoubleSpinBox - Clean Native Controls with Visible Arrows */
QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1.5px solid #8A8C8D;
    border-radius: 6px;
    color: #111C24;
    padding: 3px 6px;
    min-height: 32px;
    font-size: 12px;
    font-weight: 600;
    selection-background-color: #FF9A4E;
    selection-color: #111C24;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #FF9A4E;
    background-color: #FFFFFF;
}

/* Dropdown Combos - Black text on white background at all times */
QComboBox {
    background-color: #FFFFFF;
    border: 1.5px solid #8A8C8D;
    border-radius: 6px;
    color: #000000;
    padding: 5px 30px 5px 10px;
    min-height: 34px;
    height: 34px;
    font-size: 12px;
    font-weight: 600;
}

QComboBox:editable {
    background-color: #FFFFFF;
    color: #000000;
}

QComboBox:focus, QComboBox:on, QComboBox:hover {
    border: 1.5px solid #FF9A4E;
    background-color: #FFFFFF;
    color: #000000;
}

QComboBox:disabled {
    background-color: #F3F4F6;
    color: #8A8C8D;
    border-color: #D1D5DB;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #8A8C8D;
    background: #F4F5F7;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1.5px solid #FF9A4E;
    border-radius: 6px;
    color: #000000;
    selection-background-color: #FFEADB;
    selection-color: #000000;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    background-color: #FFFFFF;
    color: #000000;
    min-height: 28px;
    padding: 4px 8px;
}

QComboBox QAbstractItemView::item:selected, QComboBox QAbstractItemView::item:hover {
    background-color: #FFEADB;
    color: #000000;
}

/* Primary Action Buttons */
QPushButton {
    background-color: #FF9A4E;
    color: #111C24;
    border: 1px solid #E88536;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 700;
    font-size: 11px;
    min-height: 28px;
    text-align: center;
}

QPushButton:hover {
    background-color: #F08738;
    color: #111C24;
    border-color: #616365;
}

QPushButton:pressed {
    background-color: #D47426;
    color: #FFFFFF;
}

QPushButton:disabled {
    background-color: #F3F4F6;
    border-color: #8A8C8D;
    color: #8A8C8D;
}

/* Secondary Button Style */
QPushButton.secondary {
    background-color: #FFFFFF;
    border: 1.5px solid #8A8C8D;
    color: #111C24;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton.secondary:hover {
    background-color: #F5F6F7;
    border-color: #FF9A4E;
    color: #111C24;
}

QPushButton.secondary:pressed {
    background-color: #E5E7EB;
}

/* Accent Warm Orange Button */
QPushButton.accent {
    background-color: #FF9A4E;
    border: 1px solid #E88536;
    color: #111C24;
    font-weight: 700;
}

QPushButton.accent:hover {
    background-color: #F08738;
}

/* Danger Soft Red Button */
QPushButton.danger {
    background-color: #EF4444;
    border: 1px solid #DC2626;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton.danger:hover {
    background-color: #DC2626;
}

/* Modern Tables - Crisp White with Charcoal Headers and Orange Highlights */
QTableWidget, QTableView {
    background-color: #FFFFFF;
    alternate-background-color: #F9FAFB;
    gridline-color: #E2E4E7;
    border: 1.5px solid #8A8C8D;
    border-radius: 6px;
    color: #111C24;
    selection-background-color: #FFEADB;
    selection-color: #111C24;
    font-size: 12px;
}

/* Horizontal Table Headers: Charcoal Navy with crisp white text */
QHeaderView::section:horizontal {
    background-color: #111C24;
    color: #FFFFFF;
    padding: 7px 10px;
    border: 1px solid #8A8C8D;
    font-weight: 700;
    font-size: 11px;
    min-height: 28px;
}

/* Vertical Table Headers: Clean visible row numbers (1., 2., 3...) */
QHeaderView::section:vertical {
    background-color: #F4F5F7;
    color: #111C24;
    padding: 2px 6px;
    border: 1px solid #8A8C8D;
    font-weight: 700;
    font-size: 11px;
    min-width: 38px;
    text-align: center;
}

/* List Widgets (Component Palettes) */
QListWidget {
    background-color: #FFFFFF;
    border: 1.5px solid #8A8C8D;
    border-radius: 6px;
    color: #111C24;
    padding: 4px;
    font-size: 12px;
}

QListWidget::item {
    padding: 7px 10px;
    border-radius: 5px;
    margin-bottom: 3px;
    background-color: #F8F9FA;
    border: 1px solid #E2E4E7;
    color: #111C24;
}

QListWidget::item:hover {
    background-color: #F0F2F5;
    border-color: #FF9A4E;
}

QListWidget::item:selected {
    background-color: #FFEADB;
    color: #111C24;
    font-weight: 700;
    border: 1.5px solid #FF9A4E;
}

/* Tabs */
QTabWidget::pane {
    border: 1.5px solid #8A8C8D;
    background: #FFFFFF;
    border-radius: 6px;
}

QTabBar::tab {
    background: #F4F5F7;
    color: #616365;
    border: 1px solid #8A8C8D;
    border-bottom: none;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 11px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    color: #111C24;
    border-top: 2.5px solid #FF9A4E;
    border-bottom: 1px solid #FFFFFF;
    font-weight: 700;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #F4F5F7;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #8A8C8D;
    min-height: 28px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #FF9A4E;
}

QScrollBar:horizontal {
    border: none;
    background: #F4F5F7;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #8A8C8D;
    min-width: 28px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #FF9A4E;
}

/* Tooltips */
QToolTip {
    background-color: #111C24;
    color: #FFFFFF;
    border: 1px solid #FF9A4E;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 11px;
}

/* Splitters */
QSplitter::handle {
    background-color: #E2E4E7;
}

QSplitter::handle:hover {
    background-color: #FF9A4E;
}

/* Checkboxes */
QCheckBox {
    color: #111C24;
    font-size: 12px;
    font-weight: 500;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #8A8C8D;
    border-radius: 4px;
    background: #FFFFFF;
}

QCheckBox::indicator:hover {
    border-color: #FF9A4E;
}

QCheckBox::indicator:checked {
    background-color: #FF9A4E;
    border-color: #FF9A4E;
}
"""
