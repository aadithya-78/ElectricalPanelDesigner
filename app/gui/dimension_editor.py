"""
Step 4 / Dimension Editor Dialog.
Supports Method A (Manual), Method B (SQLite Library), and Method C (STEP Model Import).
"""
import os
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QDoubleSpinBox, QPushButton, QGroupBox, QGridLayout, 
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QTabWidget, QWidget
)
from PySide6.QtCore import Qt

from app.models.component import Component, MountingType
from app.database.component_database import ComponentDatabase
from app.geometry.step_importer import STEPImporter


class DimensionEditorDialog(QDialog):
    def __init__(self, component: Component, db: ComponentDatabase, parent=None):
        super().__init__(parent)
        self.component = component
        self.db = db
        self.setWindowTitle(f"3D Physical Dimension Editor — {component.name}")
        self.setMinimumSize(600, 480)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # Header
        title = QLabel(f"<b>Component:</b> {self.component.name}")
        title.setStyleSheet("font-size: 16px; color: #4fc3f7;")
        main_layout.addWidget(title)

        sub = QLabel(f"Manufacturer: {self.component.manufacturer} | Part No: {self.component.part_number or 'Unverified'}")
        sub.setStyleSheet("color: #9e9e9e;")
        main_layout.addWidget(sub)

        # Tab Widget for Methods A, B, C
        tabs = QTabWidget()

        # --- METHOD A: MANUAL ENTRY ---
        tab_manual = QWidget()
        manual_layout = QVBoxLayout(tab_manual)

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(16)

        grid.addWidget(QLabel("<b>Width X (mm):</b>"), 0, 0)
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(1.0, 5000.0)
        self.spin_x.setMinimumHeight(38)
        self.spin_x.setValue(self.component.width_mm)
        grid.addWidget(self.spin_x, 0, 1)

        grid.addWidget(QLabel("<b>Height Y (mm):</b>"), 1, 0)
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(1.0, 5000.0)
        self.spin_y.setMinimumHeight(38)
        self.spin_y.setValue(self.component.height_mm)
        grid.addWidget(self.spin_y, 1, 1)

        grid.addWidget(QLabel("<b>Depth Z (mm):</b>"), 2, 0)
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(1.0, 3000.0)
        self.spin_z.setMinimumHeight(38)
        self.spin_z.setValue(self.component.depth_mm)
        grid.addWidget(self.spin_z, 2, 1)

        # Clearances
        grid.addWidget(QLabel("<b>Top Clearance (mm):</b>"), 3, 0)
        self.spin_clr_top = QDoubleSpinBox()
        self.spin_clr_top.setRange(0.0, 500.0)
        self.spin_clr_top.setMinimumHeight(38)
        self.spin_clr_top.setValue(self.component.clearance_top_mm)
        grid.addWidget(self.spin_clr_top, 3, 1)

        grid.addWidget(QLabel("<b>Bottom Clearance (mm):</b>"), 4, 0)
        self.spin_clr_bot = QDoubleSpinBox()
        self.spin_clr_bot.setRange(0.0, 500.0)
        self.spin_clr_bot.setMinimumHeight(38)
        self.spin_clr_bot.setValue(self.component.clearance_bottom_mm)
        grid.addWidget(self.spin_clr_bot, 4, 1)

        grid.addWidget(QLabel("<b>Side Clearance (mm):</b>"), 5, 0)
        self.spin_clr_side = QDoubleSpinBox()
        self.spin_clr_side.setRange(0.0, 500.0)
        self.spin_clr_side.setMinimumHeight(38)
        self.spin_clr_side.setValue(self.component.clearance_sides_mm)
        grid.addWidget(self.spin_clr_side, 5, 1)

        manual_layout.addLayout(grid)
        manual_layout.addStretch()
        tabs.addTab(tab_manual, "Method A: Manual Dimensions")

        # --- METHOD B: COMPONENT LIBRARY DATABASE ---
        tab_db = QWidget()
        db_layout = QVBoxLayout(tab_db)

        search_layout = QHBoxLayout()
        self.db_search_input = QLineEdit()
        self.db_search_input.setPlaceholderText("Search database (e.g. ATV630, NSX100, CTS35, HDR-60)...")
        search_layout.addWidget(self.db_search_input)

        btn_search = QPushButton("Search Library")
        btn_search.clicked.connect(self._search_library)
        search_layout.addWidget(btn_search)
        db_layout.addLayout(search_layout)

        self.db_list = QListWidget()
        self.db_list.itemDoubleClicked.connect(self._apply_library_item)
        db_layout.addWidget(self.db_list)

        btn_apply_db = QPushButton("Apply Selected Database Dimensions")
        btn_apply_db.setProperty("class", "secondary")
        btn_apply_db.clicked.connect(self._apply_selected_db)
        db_layout.addWidget(btn_apply_db)

        tabs.addTab(tab_db, "Method B: Component Library (SQLite)")

        # --- METHOD C: STEP CAD IMPORT ---
        tab_step = QWidget()
        step_layout = QVBoxLayout(tab_step)

        step_info = QLabel(
            "Import 3D STEP (.step / .stp) model to automatically calculate accurate "
            "bounding box Width (X), Height (Y), and Depth (Z)."
        )
        step_info.setWordWrap(True)
        step_info.setStyleSheet("color: #616365;")
        step_layout.addWidget(step_info)

        btn_import_step = QPushButton("Select STEP / STP CAD File...")
        btn_import_step.setStyleSheet("padding: 10px; font-weight: bold; background-color: #FF9A4E; color: #111C24;")
        btn_import_step.clicked.connect(self._import_step_file)
        step_layout.addWidget(btn_import_step)

        self.step_status_lbl = QLabel("Ready for STEP file import.")
        self.step_status_lbl.setWordWrap(True)
        self.step_status_lbl.setStyleSheet("color: #111C24; padding: 10px; background-color: #F8F9FA; border: 1px solid #8A8C8D; border-radius: 4px;")
        step_layout.addWidget(self.step_status_lbl)

        step_layout.addStretch()
        tabs.addTab(tab_step, "Method C: STEP CAD Import")

        main_layout.addWidget(tabs)

        # Bottom Actions: Save to Library & OK/Cancel
        bottom_layout = QHBoxLayout()
        self.save_to_db_check = QPushButton("Save to SQLite Library")
        self.save_to_db_check.setProperty("class", "secondary")
        self.save_to_db_check.clicked.connect(self._save_to_library)
        bottom_layout.addWidget(self.save_to_db_check)

        bottom_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply Dimensions")
        btn_apply.setProperty("class", "accent")
        btn_apply.clicked.connect(self._apply_and_accept)
        bottom_layout.addWidget(btn_apply)

        main_layout.addLayout(bottom_layout)

        # Trigger initial DB search based on component name
        self.db_search_input.setText(self.component.part_number or self.component.name.split()[0])
        self._search_library()

    def _search_library(self):
        query = self.db_search_input.text().strip()
        results = self.db.find_by_part_or_name(query)
        self.db_list.clear()
        self.current_db_results = results

        for idx, r in enumerate(results):
            text = f"{r['name']} ({r['manufacturer']}) — {r['width_mm']}x{r['height_mm']}x{r['depth_mm']} mm"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, idx)
            self.db_list.addItem(item)

    def _apply_library_item(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        if 0 <= idx < len(self.current_db_results):
            data = self.current_db_results[idx]
            self.spin_x.setValue(data["width_mm"])
            self.spin_y.setValue(data["height_mm"])
            self.spin_z.setValue(data["depth_mm"])
            self.spin_clr_top.setValue(data["clearance_top_mm"])
            self.spin_clr_bot.setValue(data["clearance_bottom_mm"])
            self.spin_clr_side.setValue(data["clearance_sides_mm"])
            QMessageBox.information(self, "Applied", f"Applied dimensions from {data['name']}.")

    def _apply_selected_db(self):
        cur = self.db_list.currentItem()
        if cur:
            self._apply_library_item(cur)
        else:
            QMessageBox.warning(self, "Selection Needed", "Please select an item from the database list.")

    def _import_step_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select STEP CAD Model", "", "STEP Files (*.step *.stp);;All Files (*.*)"
        )
        if not file_path:
            return

        result = STEPImporter.import_step_dimensions(file_path)
        if result["success"]:
            self.spin_x.setValue(result["width_mm"])
            self.spin_y.setValue(result["height_mm"])
            self.spin_z.setValue(result["depth_mm"])
            self.step_status_lbl.setText(
                f"[Success] {result['message']}\nApplied dimensions: {result['width_mm']} x {result['height_mm']} x {result['depth_mm']} mm"
            )
        else:
            self.step_status_lbl.setText(f"[Notice] {result['error']}")
            QMessageBox.warning(self, "CAD Backend Info", result["error"])

    def _save_to_library(self):
        comp_dict = {
            "name": self.component.name,
            "category": self.component.category.value if hasattr(self.component.category, "value") else str(self.component.category),
            "manufacturer": self.component.manufacturer,
            "part_number": self.component.part_number,
            "description": self.component.description,
            "width_mm": self.spin_x.value(),
            "height_mm": self.spin_y.value(),
            "depth_mm": self.spin_z.value(),
            "mounting_type": self.component.mounting_type.value if hasattr(self.component.mounting_type, "value") else str(self.component.mounting_type),
            "clearance_top_mm": self.spin_clr_top.value(),
            "clearance_bottom_mm": self.spin_clr_bot.value(),
            "clearance_sides_mm": self.spin_clr_side.value(),
            "heat_loss_watts": self.component.heat_loss_watts,
            "unit_price": self.component.unit_price,
            "verified": 1
        }
        self.db.add_component(comp_dict)
        QMessageBox.information(self, "Saved", f"Saved {self.component.name} to local component database.")

    def _apply_and_accept(self):
        self.component.width_mm = self.spin_x.value()
        self.component.height_mm = self.spin_y.value()
        self.component.depth_mm = self.spin_z.value()
        self.component.clearance_top_mm = self.spin_clr_top.value()
        self.component.clearance_bottom_mm = self.spin_clr_bot.value()
        self.component.clearance_sides_mm = self.spin_clr_side.value()
        self.accept()

