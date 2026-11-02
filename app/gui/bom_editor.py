"""
Step 2 GUI: AI-Generated Editable Engineering Bill of Materials (BOM) Table.
Features Excel-like inline cell editing, Add / Duplicate / Delete / Custom item creation,
explicit X/Y/Z dimensions in millimeters, and instantaneous summary updates.
"""
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, 
    QFileDialog, QInputDialog, QComboBox, QDialog, QFormLayout, 
    QLineEdit, QDoubleSpinBox, QSpinBox, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from app.models.component import Component, MountingType, ComponentCategory, ValidationStatus
from app.models.bom import BOM
from app.database.component_database import ComponentDatabase
from app.gui.dimension_editor import DimensionEditorDialog
from app.gui.component_3d_preview import Component3DPreviewWidget
from app.export.excel_export import ExcelBOMExporter


class AddCustomComponentDialog(QDialog):
    """Clean modal dialog to add a completely custom electrical device to the BOM."""
    def __init__(self, item_no: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Electrical Component")
        self.setMinimumWidth(440)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        self.name_edit = QLineEdit("Custom Device")
        form.addRow("Component Name:", self.name_edit)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Power", "Control", "Accessories", "Wiring"])
        form.addRow("Category:", self.cat_combo)

        self.mfr_edit = QLineEdit("Generic Industrial")
        form.addRow("Manufacturer:", self.mfr_edit)

        self.part_edit = QLineEdit("CUST-001")
        form.addRow("Part Number:", self.part_edit)

        self.desc_edit = QLineEdit("Auxiliary control component")
        form.addRow("Description:", self.desc_edit)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 999)
        self.qty_spin.setValue(1)
        self.qty_spin.setMinimumHeight(38)
        form.addRow("Quantity:", self.qty_spin)

        self.w_spin = QDoubleSpinBox()
        self.w_spin.setRange(5.0, 2000.0)
        self.w_spin.setValue(80.0)
        self.w_spin.setSuffix(" mm")
        self.w_spin.setMinimumHeight(38)
        form.addRow("Width X (mm):", self.w_spin)

        self.h_spin = QDoubleSpinBox()
        self.h_spin.setRange(5.0, 2000.0)
        self.h_spin.setValue(100.0)
        self.h_spin.setSuffix(" mm")
        self.h_spin.setMinimumHeight(38)
        form.addRow("Height Y (mm):", self.h_spin)

        self.d_spin = QDoubleSpinBox()
        self.d_spin.setRange(5.0, 1000.0)
        self.d_spin.setValue(75.0)
        self.d_spin.setSuffix(" mm")
        self.d_spin.setMinimumHeight(38)
        form.addRow("Depth Z (mm):", self.d_spin)

        self.mount_combo = QComboBox()
        self.mount_combo.addItems(["Plate", "DIN Rail", "Door"])
        form.addRow("Mounting:", self.mount_combo)

        self.surf_combo = QComboBox()
        self.surf_combo.addItems(["Mounting Plate (Z)", "Panel Door (Z+1)"])
        form.addRow("Surface View:", self.surf_combo)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Add to BOM")
        btn_ok.setMinimumHeight(38)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.setMinimumHeight(38)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        layout.addLayout(btn_box)

        self.item_no = item_no

    def get_component(self) -> Component:
        cat_map = {
            "Power": ComponentCategory.POWER,
            "Control": ComponentCategory.CONTROL,
            "Accessories": ComponentCategory.ACCESSORIES,
            "Wiring": ComponentCategory.WIRING
        }
        mount_str = self.mount_combo.currentText()
        if mount_str == "DIN Rail":
            mount_val = MountingType.DIN
        elif mount_str == "Door":
            mount_val = MountingType.DOOR
        else:
            mount_val = MountingType.PLATE

        is_door = (self.surf_combo.currentIndex() == 1 or mount_val == MountingType.DOOR)
        return Component(
            item_no=self.item_no,
            category=cat_map.get(self.cat_combo.currentText(), ComponentCategory.CONTROL),
            name=self.name_edit.text().strip(),
            manufacturer=self.mfr_edit.text().strip(),
            part_number=self.part_edit.text().strip(),
            part_number_verified=True,
            description=self.desc_edit.text().strip(),
            quantity=self.qty_spin.value(),
            width_mm=self.w_spin.value(),
            height_mm=self.h_spin.value(),
            depth_mm=self.d_spin.value(),
            mounting_type=MountingType.DOOR if is_door else mount_val,
            surface="Z+1" if is_door else "Z",
            clearance_top_mm=10.0,
            clearance_bottom_mm=10.0,
            clearance_sides_mm=5.0
        )


class BOMEditorPage(QWidget):
    bom_approved = Signal(object) # Emits BOM instance
    bom_modified = Signal(object) # Emits BOM instance on any row/field change

    COLUMNS = [
        "Item", "Category", "Component Name", "Manufacturer", "Part Number",
        "Description", "Qty", "X: Width (mm)", "Y: Height (mm)", "Z: Depth (mm)",
        "Mounting", "Surface View", "Heat Loss (W)", "Unit Price ($ / ₹)", "Total Price ($ / ₹)"
    ]

    def __init__(self, db: ComponentDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.bom = BOM()
        self.undo_manager = None
        self._is_updating = False

        self._init_ui()

    def set_bom_items(self, items_data: List[Dict[str, Any]]):
        self.bom = BOM.from_list(items_data)
        self._refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 1. Header Banner
        header_lbl = QLabel("Step 2: Bill of Materials Verification & 3D Component Inspection")
        header_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #FFFFFF;")
        layout.addWidget(header_lbl)

        sub_lbl = QLabel(
            "Review electrical parameters, customize dimensions, and inspect true-scale 3D models. "
            "Select any component row to view its 3D rendering. Seamlessly toggle components between "
            "Mounting Plate (Z View) and Panel Door (Z+1 View)."
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.4;")
        layout.addWidget(sub_lbl)

        # 2. Main Splitter: Left Table (60%) + Right 3D Inspection (40%)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Toolbar Buttons
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_add_custom = QPushButton("+ Add Custom Item")
        btn_add_custom.setMinimumHeight(34)
        btn_add_custom.clicked.connect(self._add_custom_component)
        toolbar.addWidget(btn_add_custom)

        btn_dup = QPushButton("Duplicate")
        btn_dup.setProperty("class", "secondary")
        btn_dup.setMinimumHeight(34)
        btn_dup.clicked.connect(self._duplicate_component)
        toolbar.addWidget(btn_dup)

        btn_del = QPushButton("Delete")
        btn_del.setProperty("class", "danger")
        btn_del.setMinimumHeight(34)
        btn_del.clicked.connect(self._delete_component)
        toolbar.addWidget(btn_del)

        btn_toggle_surf = QPushButton("Switch Surface (Z / Z+1)")
        btn_toggle_surf.setProperty("class", "secondary")
        btn_toggle_surf.setMinimumHeight(34)
        btn_toggle_surf.setToolTip("Toggle selected item between Mounting Plate (Z) and Outer Door (Z+1)")
        btn_toggle_surf.clicked.connect(self._toggle_selected_surface)
        toolbar.addWidget(btn_toggle_surf)

        btn_dims = QPushButton("Edit 3D Dimensions")
        btn_dims.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                color: #111C24;
                border: 1px solid #E88536;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 10px;
                min-height: 28px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        btn_dims.clicked.connect(self._open_dimension_editor)
        toolbar.addWidget(btn_dims)

        toolbar.addStretch()

        btn_export = QPushButton("Export to Excel")
        btn_export.setProperty("class", "secondary")
        btn_export.setMinimumHeight(34)
        btn_export.clicked.connect(self._export_excel)
        toolbar.addWidget(btn_export)

        left_layout.addLayout(toolbar)

        # BOM Table with Excel-like inline editing & comfortable rows
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.currentCellChanged.connect(lambda r, c, pr, pc: self._on_table_selection_changed())
        left_layout.addWidget(self.table)

        main_splitter.addWidget(left_container)

        # Right: 3D Component Inspection Preview
        self.preview_3d = Component3DPreviewWidget(self)
        self.preview_3d.setMinimumWidth(360)
        main_splitter.addWidget(self.preview_3d)

        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 4)
        layout.addWidget(main_splitter, stretch=1)

        # 4. Summary Bar
        summary_layout = QHBoxLayout()
        self.lbl_instances = QLabel("Physical Units: 0")
        self.lbl_instances.setStyleSheet("color: #111C24; font-weight: 700; font-size: 13px;")
        summary_layout.addWidget(self.lbl_instances)

        self.lbl_cost = QLabel("Total Cost: $0.00 / ₹0")
        self.lbl_cost.setStyleSheet("color: #FF9A4E; font-weight: 700; font-size: 13px; margin-left: 20px;")
        summary_layout.addWidget(self.lbl_cost)

        self.lbl_heat = QLabel("Total Heat Dissipation: 0.0 W")
        self.lbl_heat.setStyleSheet("color: #616365; font-weight: 700; font-size: 13px; margin-left: 20px;")
        summary_layout.addWidget(self.lbl_heat)

        summary_layout.addStretch()

        btn_proceed = QPushButton("Proceed to Step 3: Panel Sizing")
        btn_proceed.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                color: #111C24;
                border: 1px solid #E88536;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 700;
                min-height: 38px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        btn_proceed.clicked.connect(self._proceed_to_placement)
        summary_layout.addWidget(btn_proceed)

        layout.addLayout(summary_layout)

    def _refresh_table(self):
        self._is_updating = True
        self.table.setRowCount(len(self.bom.items))

        for row, item in enumerate(self.bom.items):
            header_item = QTableWidgetItem(f"{row + 1}.")
            header_item.setTextAlignment(Qt.AlignCenter)
            self.table.setVerticalHeaderItem(row, header_item)

            # 0. Item No (non-editable)
            item_no_widget = QTableWidgetItem(str(item.item_no))
            item_no_widget.setFlags(item_no_widget.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_no_widget)

            # 1. Category
            self.table.setItem(row, 1, QTableWidgetItem(item.category.value if hasattr(item.category, "value") else str(item.category)))

            # 2. Component Name
            self.table.setItem(row, 2, QTableWidgetItem(item.name))

            # 3. Manufacturer
            self.table.setItem(row, 3, QTableWidgetItem(item.manufacturer))
            
            # 4. Part Number
            part_display = item.part_number if item.part_number else "NOT SPECIFIED"
            p_item = QTableWidgetItem(part_display)
            if not item.part_number:
                p_item.setForeground(QColor("#F59E0B"))
            self.table.setItem(row, 4, p_item)

            # 5. Description
            self.table.setItem(row, 5, QTableWidgetItem(item.description))

            # 6. Qty
            self.table.setItem(row, 6, QTableWidgetItem(str(item.quantity)))

            # 7. X Width
            self.table.setItem(row, 7, QTableWidgetItem(str(item.width_mm)))

            # 8. Y Height
            self.table.setItem(row, 8, QTableWidgetItem(str(item.height_mm)))

            # 9. Z Depth
            self.table.setItem(row, 9, QTableWidgetItem(str(item.depth_mm)))

            # 10. Mounting
            self.table.setItem(row, 10, QTableWidgetItem(item.mounting_type.value if hasattr(item.mounting_type, "value") else str(item.mounting_type)))

            # 11. Surface View: Z vs Z+1
            surf = getattr(item, "surface", "Z").upper()
            surf_text = "Door (Z+1)" if surf == "Z+1" else "Mounting Plate (Z)"
            surf_item = QTableWidgetItem(surf_text)
            if surf == "Z+1":
                surf_item.setForeground(QColor("#FB923C"))
            else:
                surf_item.setForeground(QColor("#E5E7EB"))
            self.table.setItem(row, 11, surf_item)

            # 12. Heat Loss
            self.table.setItem(row, 12, QTableWidgetItem(str(item.heat_loss_watts)))

            # 13. Unit Price
            self.table.setItem(row, 13, QTableWidgetItem(f"${item.unit_price:.2f} (₹{item.unit_price * 83.0:,.0f})"))

            # 14. Total Price (non-editable)
            tot_item = QTableWidgetItem(f"${item.total_price:.2f} (₹{item.total_price * 83.0:,.0f})")
            tot_item.setFlags(tot_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 14, tot_item)

        self._is_updating = False
        self._update_summaries()

        if self.bom.items:
            curr_r = max(0, self.table.currentRow())
            if curr_r < len(self.bom.items):
                self.table.selectRow(curr_r)
                self.preview_3d.set_component(self.bom.items[curr_r])
        else:
            self.preview_3d.set_component(None)

    def _on_table_selection_changed(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.bom.items):
            comp = self.bom.items[row]
            self.preview_3d.set_component(comp)

    def _toggle_selected_surface(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.bom.items):
            QMessageBox.information(self, "Selection Required", "Please select a component row to toggle its surface.")
            return

        comp = self.bom.items[row]
        cur_surf = getattr(comp, "surface", "Z").upper()
        if cur_surf == "Z+1":
            comp.surface = "Z"
            if comp.mounting_type == MountingType.DOOR:
                comp.mounting_type = MountingType.PLATE
        else:
            comp.surface = "Z+1"
            comp.mounting_type = MountingType.DOOR

        if self.undo_manager:
            self.undo_manager.push_state()
        self._refresh_table()
        self.table.selectRow(row)
        self.preview_3d.set_component(comp)
        self.bom_modified.emit(self.bom)

    def _update_summaries(self):
        instances = self.bom.expand_to_instances()
        self.lbl_instances.setText(f"Physical Units: {len(instances)}")
        cost = self.bom.total_cost()
        self.lbl_cost.setText(f"Total Cost: ${cost:,.2f} / ₹{cost * 83.0:,.0f}")
        self.lbl_heat.setText(f"Total Heat Loss: {self.bom.total_heat_loss():.1f} W")

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._is_updating:
            return

        row = item.row()
        col = item.column()
        if row >= len(self.bom.items):
            return

        comp = self.bom.items[row]
        val = item.text().strip()

        try:
            if col == 2:
                comp.name = val
            elif col == 3:
                comp.manufacturer = val
            elif col == 4:
                comp.part_number = val if "NOT SPECIFIED" not in val else None
                comp.part_number_verified = bool(comp.part_number)
            elif col == 5:
                comp.description = val
            elif col == 6:
                comp.quantity = max(1, int(val))
                comp.calculate_total_price()
                tot_item = self.table.item(row, 14)
                if tot_item:
                    self._is_updating = True
                    tot_item.setText(f"${comp.total_price:.2f} (₹{comp.total_price * 83.0:,.0f})")
                    self._is_updating = False
            elif col == 7:
                comp.width_mm = max(1.0, float(val))
            elif col == 8:
                comp.height_mm = max(1.0, float(val))
            elif col == 9:
                comp.depth_mm = max(1.0, float(val))
            elif col == 11:
                # Surface column
                if "z+1" in val.lower() or "door" in val.lower():
                    comp.surface = "Z+1"
                    comp.mounting_type = MountingType.DOOR
                else:
                    comp.surface = "Z"
            elif col == 12:
                comp.heat_loss_watts = max(0.0, float(val))
            elif col == 13:
                clean_val = val.replace("$", "").replace("₹", "").split("/")[0].split("(")[0].replace(",", "").strip()
                comp.unit_price = max(0.0, float(clean_val))
                comp.calculate_total_price()
                self._is_updating = True
                item.setText(f"${comp.unit_price:.2f} (₹{comp.unit_price * 83.0:,.0f})")
                tot_item = self.table.item(row, 14)
                if tot_item:
                    tot_item.setText(f"${comp.total_price:.2f} (₹{comp.total_price * 83.0:,.0f})")
                self._is_updating = False
        except ValueError:
            pass

        self._update_summaries()
        self.preview_3d.set_component(comp)
        if self.undo_manager and not getattr(self.undo_manager, "_is_undoing_redoing", False):
            self.undo_manager.push_state()
        self.bom_modified.emit(self.bom)

    def _open_dimension_editor(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.bom.items):
            QMessageBox.information(self, "Selection Required", "Please select a component row to edit its 3D dimensions.")
            return

        comp = self.bom.items[row]
        pre_snap = self.undo_manager.capture_snapshot() if self.undo_manager else None
        dialog = DimensionEditorDialog(comp, self.db, self)
        if dialog.exec():
            if self.undo_manager and pre_snap:
                self.undo_manager.push_state(pre_snap)
            self._refresh_table()
            self.preview_3d.set_component(comp)
            self.bom_modified.emit(self.bom)

    def _add_custom_component(self):
        dlg = AddCustomComponentDialog(len(self.bom.items) + 1, self)
        if dlg.exec():
            if self.undo_manager:
                self.undo_manager.push_state()
            comp = dlg.get_component()
            self.bom.items.append(comp)
            self._refresh_table()
            self.bom_modified.emit(self.bom)

    def _duplicate_component(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.bom.items):
            QMessageBox.information(self, "Selection Required", "Please select a component row to duplicate.")
            return

        orig = self.bom.items[row]
        new_item = Component(
            item_no=len(self.bom.items) + 1,
            category=orig.category,
            name=f"{orig.name} (Copy)",
            manufacturer=orig.manufacturer,
            part_number=orig.part_number,
            part_number_verified=orig.part_number_verified,
            description=orig.description,
            quantity=orig.quantity,
            width_mm=orig.width_mm,
            height_mm=orig.height_mm,
            depth_mm=orig.depth_mm,
            mounting_type=orig.mounting_type,
            surface=getattr(orig, "surface", "Z"),
            voltage=getattr(orig, "voltage", ""),
            rated_current_a=getattr(orig, "rated_current_a", 0.0),
            power_kw=getattr(orig, "power_kw", 0.0),
            frequency_hz=getattr(orig, "frequency_hz", 50.0),
            clearance_top_mm=orig.clearance_top_mm,
            clearance_bottom_mm=orig.clearance_bottom_mm,
            clearance_sides_mm=orig.clearance_sides_mm,
            heat_loss_watts=orig.heat_loss_watts,
            unit_price=orig.unit_price,
            total_price=orig.total_price
        )
        if self.undo_manager:
            self.undo_manager.push_state()
        self.bom.items.append(new_item)
        self._refresh_table()
        self.bom_modified.emit(self.bom)

    def _delete_component(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.bom.items):
            QMessageBox.information(self, "Selection Required", "Please select a component row to delete.")
            return

        comp = self.bom.items[row]
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to remove '{comp.name}' from the BOM?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.undo_manager:
                self.undo_manager.push_state()
            self.bom.items.pop(row)
            for idx, item in enumerate(self.bom.items):
                item.item_no = idx + 1
            self._refresh_table()
            self.bom_modified.emit(self.bom)

    def _export_excel(self):
        if not self.bom.items:
            QMessageBox.warning(self, "Empty BOM", "No components available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export BOM to Excel", "electrical_bom.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                ExcelBOMExporter.export_bom(self.bom, file_path)
                QMessageBox.information(self, "Export Complete", f"Successfully exported BOM to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export Excel file: {str(e)}")

    def _proceed_to_placement(self):
        if not self.bom.items:
            QMessageBox.warning(self, "Empty BOM", "Please add at least one component before proceeding.")
            return
        self.bom_approved.emit(self.bom)
