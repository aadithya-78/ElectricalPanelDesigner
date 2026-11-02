"""
Step 1 GUI: Component Selection & BOM Builder.
User-focused workflow where the Project BOM is the primary, prominent view.
The master catalog is never dumped as an entire raw table; instead, smart recommendations
appear dynamically only when the user types in the search box.
"""
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, 
    QSpinBox, QFrame, QMessageBox, QHeaderView, QAbstractItemView,
    QSizePolicy
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, Signal

from app.database.catalog_manager import CatalogManager
from app.models.component import Component, ComponentCategory, MountingType, ValidationStatus
from app.gui.bom_editor import AddCustomComponentDialog


class ComponentSelectionPage(QWidget):
    bom_ready = Signal(list, dict) # Emits (list_of_dict, summary_dict)

    REC_COLS = [
        "Part Number", "Description", "Manufacturer", "Category",
        "Surface", "Dimensions (W×H×D mm)", "Ratings", "Unit Price ($ / ₹)", "Action"
    ]

    BOM_COLS = [
        "Item #", "Part Number", "Description", "Manufacturer", 
        "Category", "Surface Layer", "Qty", "Dimensions (W×H×D mm)", 
        "Ratings", "Unit Price ($ / ₹)", "Total ($ / ₹)", "Remove", "Switch Surface"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog_mgr = CatalogManager.get_instance()
        self.selected_components: List[Component] = []
        self._current_rec_records: List[Dict[str, Any]] = []

        self._init_ui()

    @property
    def selected_items(self) -> List[Component]:
        return self.selected_components

    def set_selected_components(self, components: List[Component]):
        """Populate the BOM selection table from an external list (e.g. when loading project JSON)."""
        self.selected_components = list(components)
        self._refresh_bom_table()

    def clear_selection(self):
        """Clear all components from the project BOM and refresh."""
        self.selected_components.clear()
        self._refresh_bom_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # 1. Header Banner
        header_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        header_lbl = QLabel("Step 1: Industrial Control Panel BOM Builder")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #FFFFFF;")
        title_box.addWidget(header_lbl)

        sub_lbl = QLabel(
            "Search components to get instant catalog recommendations, build your custom BOM, or load standard panel templates."
        )
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        title_box.addWidget(sub_lbl)
        header_box.addLayout(title_box)
        header_box.addStretch()

        layout.addLayout(header_box)

        # 2. Quick Search & Add Bar
        search_card = QFrame()
        search_card.setObjectName("searchCard")
        search_card.setStyleSheet("""
            QFrame#searchCard {
                background: #FFFFFF;
                border: 1.5px solid #8A8C8D;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        s_layout = QHBoxLayout(search_card)
        s_layout.setSpacing(10)
        s_layout.setContentsMargins(4, 4, 4, 4)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type part number or equipment to search (e.g. ATV630, MCCB, MCB, KTP700, Pilot Lamp, Pushbutton, SMPS, Choke)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumHeight(34)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.returnPressed.connect(self._add_first_recommended_item)
        s_layout.addWidget(self.search_edit, stretch=5)

        lbl_qty = QLabel("Qty:")
        lbl_qty.setStyleSheet("color: #111C24; font-weight: 700; font-size: 12px; border: none; background: transparent;")
        s_layout.addWidget(lbl_qty)

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 999)
        self.spin_qty.setValue(1)
        self.spin_qty.setMinimumHeight(34)
        self.spin_qty.setFixedWidth(75)
        self.spin_qty.setAlignment(Qt.AlignCenter)
        s_layout.addWidget(self.spin_qty)

        btn_custom = QPushButton("Custom Item")
        btn_custom.setProperty("class", "secondary")
        btn_custom.setStyleSheet("min-height: 30px; font-size: 11px; padding: 5px 12px;")
        btn_custom.clicked.connect(self._add_custom_item)
        s_layout.addWidget(btn_custom)

        layout.addWidget(search_card)

        # 3. Dynamic Recommendations Card (HIDDEN WHEN SEARCH IS EMPTY)
        self.rec_card = QFrame()
        self.rec_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1.5px solid #FF9A4E;
                border-radius: 6px;
                padding: 8px 10px;
            }
        """)
        rec_layout = QVBoxLayout(self.rec_card)
        rec_layout.setContentsMargins(6, 6, 6, 6)
        rec_layout.setSpacing(6)

        rec_header_box = QHBoxLayout()
        self.lbl_rec_title = QLabel("Catalog Recommendations (Double-click or click 'Add' to include in Project BOM):")
        self.lbl_rec_title.setStyleSheet("color: #111C24; font-weight: 700; font-size: 12px;")
        rec_header_box.addWidget(self.lbl_rec_title)
        rec_header_box.addStretch()

        btn_close_rec = QPushButton("Close Suggestions")
        btn_close_rec.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #616365;
                border: 1.5px solid #8A8C8D;
                font-size: 10px;
                padding: 3px 8px;
                min-height: 22px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #F5F6F7;
                color: #111C24;
                border-color: #FF9A4E;
            }
        """)
        btn_close_rec.clicked.connect(lambda: self.rec_card.setVisible(False))
        rec_header_box.addWidget(btn_close_rec)
        rec_layout.addLayout(rec_header_box)

        # Recommendations Table
        self.rec_table = QTableWidget()
        self.rec_table.setColumnCount(len(self.REC_COLS))
        self.rec_table.setHorizontalHeaderLabels(self.REC_COLS)
        self.rec_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.rec_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.rec_table.verticalHeader().setDefaultSectionSize(32)
        self.rec_table.verticalHeader().setMinimumSectionSize(28)
        self.rec_table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.rec_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rec_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rec_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rec_table.setMaximumHeight(180)
        self.rec_table.doubleClicked.connect(self._add_selected_recommendation)
        rec_layout.addWidget(self.rec_table)

        # By default, recommendations card is HIDDEN
        self.rec_card.setVisible(False)
        layout.addWidget(self.rec_card)

        # 4. PRIMARY VIEW: Project Bill of Materials (BOM)
        bom_header_box = QHBoxLayout()
        self.lbl_bom_title = QLabel("Project Bill of Materials (BOM): 0 Items (0 Units)")
        self.lbl_bom_title.setStyleSheet("font-weight: 800; color: #111C24; font-size: 14px;")
        bom_header_box.addWidget(self.lbl_bom_title)

        bom_header_box.addStretch()

        btn_clear = QPushButton("Clear BOM")
        btn_clear.setProperty("class", "secondary")
        btn_clear.setStyleSheet("min-height: 28px; font-size: 11px; padding: 4px 12px;")
        btn_clear.clicked.connect(self._clear_all_selection)
        bom_header_box.addWidget(btn_clear)

        layout.addLayout(bom_header_box)

        # Main BOM Table
        self.bom_table = QTableWidget()
        self.bom_table.setColumnCount(len(self.BOM_COLS))
        self.bom_table.setHorizontalHeaderLabels(self.BOM_COLS)
        self.bom_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.bom_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.bom_table.verticalHeader().setDefaultSectionSize(32)
        self.bom_table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.bom_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bom_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.bom_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.bom_table, stretch=1)

        # 5. Summary & Proceed Footer Bar
        footer = QHBoxLayout()
        footer.setSpacing(14)

        self.lbl_summary = QLabel("Total: 0 Items | 0 Physical Units | Total Power: 0.0 kW | Total Cost: $0.00 / ₹0")
        self.lbl_summary.setStyleSheet("font-size: 12px; font-weight: 700; color: #111C24;")
        footer.addWidget(self.lbl_summary)

        footer.addStretch()

        self.btn_proceed = QPushButton("Proceed to BOM Verification & 3D Preview")
        self.btn_proceed.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                border: 1px solid #E88536;
                color: #111C24;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 18px;
                min-height: 32px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        self.btn_proceed.clicked.connect(self._proceed_to_bom)
        footer.addWidget(self.btn_proceed)

        layout.addLayout(footer)

    def _on_search_text_changed(self, text: str):
        query = text.strip()
        if not query:
            self.rec_card.setVisible(False)
            self._current_rec_records = []
            return

        results = self.catalog_mgr.search(query=query)
        self._current_rec_records = results[:25] # Show top 25 matches

        if not self._current_rec_records:
            self.lbl_rec_title.setText(f"No catalog items found matching '{query}'. You can add it as a Custom Item.")
            self.rec_table.setRowCount(0)
            self.rec_card.setVisible(True)
            return

        self.lbl_rec_title.setText(f"Found {len(self._current_rec_records)} matching catalog items (Double-click or click 'Add' to include):")
        self._populate_recommendations_table(self._current_rec_records)
        self.rec_card.setVisible(True)

    def _populate_recommendations_table(self, records: List[Dict[str, Any]]):
        self.rec_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            header_item = QTableWidgetItem(f"{row + 1}.")
            header_item.setTextAlignment(Qt.AlignCenter)
            self.rec_table.setVerticalHeaderItem(row, header_item)

            self.rec_table.setItem(row, 0, QTableWidgetItem(rec.get("Part_Number", "")))
            self.rec_table.setItem(row, 1, QTableWidgetItem(rec.get("Name", "") or rec.get("Description", "")))
            self.rec_table.setItem(row, 2, QTableWidgetItem(rec.get("Manufacturer", "")))
            self.rec_table.setItem(row, 3, QTableWidgetItem(rec.get("Category", "")))

            surf = rec.get("Default_Surface", "Z").upper()
            surf_item = QTableWidgetItem("Door (Z+1)" if surf == "Z+1" else "Mounting Plate (Z)")
            if surf == "Z+1":
                surf_item.setForeground(QColor("#FF9A4E"))
            else:
                surf_item.setForeground(QColor("#111C24"))
            self.rec_table.setItem(row, 4, surf_item)

            dims = f"{int(rec.get('Width_mm', 0))}×{int(rec.get('Height_mm', 0))}×{int(rec.get('Depth_mm', 0))}"
            self.rec_table.setItem(row, 5, QTableWidgetItem(dims))

            v = rec.get("Voltage_V", "")
            kw = rec.get("Power_kW", 0.0)
            a = rec.get("Rated_Current_A", 0.0)
            spec_str = f"{v}"
            if kw and float(kw) > 0:
                spec_str += f" | {kw}kW"
            if a and float(a) > 0:
                spec_str += f" | {a}A"
            self.rec_table.setItem(row, 6, QTableWidgetItem(spec_str))

            price = rec.get("Unit_Price_USD", 0.0)
            price_inr = price * 83.0
            self.rec_table.setItem(row, 7, QTableWidgetItem(f"${price:.2f} / ₹{price_inr:,.0f}"))

            # Action button
            btn_add = QPushButton("Add")
            btn_add.setStyleSheet("""
                QPushButton {
                    background-color: #FF9A4E;
                    color: #111C24;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 3px 10px;
                    min-height: 24px;
                    border-radius: 4px;
                    border: 1px solid #E88536;
                }
                QPushButton:hover {
                    background-color: #F08738;
                }
            """)
            btn_add.clicked.connect(lambda checked=False, r=rec: self._add_component_record(r))
            self.rec_table.setCellWidget(row, 8, btn_add)

    def _add_first_recommended_item(self):
        if self._current_rec_records:
            self._add_component_record(self._current_rec_records[0])
            self.search_edit.clear()

    def _add_selected_recommendation(self):
        row = self.rec_table.currentRow()
        if 0 <= row < len(self._current_rec_records):
            self._add_component_record(self._current_rec_records[row])

    def _add_component_record(self, record: Dict[str, Any]):
        qty = self.spin_qty.value()
        comp = self.catalog_mgr.create_component_from_record(
            record,
            item_no=len(self.selected_components) + 1,
            quantity=qty
        )
        self.selected_components.append(comp)
        self._refresh_bom_table()

    def _add_custom_item(self):
        dlg = AddCustomComponentDialog(len(self.selected_components) + 1, self)
        if dlg.exec():
            comp = dlg.get_component()
            self.selected_components.append(comp)
            self._refresh_bom_table()

    def _load_18kw_starter_pack(self):
        """Populate standard 18 kW motor drive starter components."""
        starter_queries = [
            ("ATV630D18N4", 1),         # VFD 18.5kW
            ("LV429630", 1),            # MCCB 50A
            ("VW3A4555", 1),            # Line Choke 18.5kW
            ("6AV2123-2GB03-0AX0", 1),   # Siemens KTP700 HMI (Door)
            ("XB4BVB3", 2),             # Green Pilot Lamp (Door)
            ("XB4BVB4", 1),             # Red Pilot Lamp (Door)
            ("XB4BA31", 1),             # Green Pushbutton (Door)
            ("XB4BA42", 1),             # Red Pushbutton (Door)
            ("XB4BS542", 1),            # E-Stop Mushroom (Door)
            ("XB4BD33", 1),             # 3-Pos Selector Switch (Door)
            ("2904601", 1),             # Phoenix Contact 24V 10A SMPS
            ("A9F74216", 2),            # 2P 16A MCB
            ("A9F74316", 2),            # 3P 16A MCB
            ("3044076", 20),            # UT 2.5 Terminal Blocks
            ("3044092", 5)              # UT 2.5 Ground Blocks
        ]

        added_count = 0
        for pn, qty in starter_queries:
            results = self.catalog_mgr.search(query=pn)
            if results:
                comp = self.catalog_mgr.create_component_from_record(
                    results[0],
                    item_no=len(self.selected_components) + 1,
                    quantity=qty
                )
                self.selected_components.append(comp)
                added_count += 1

        self._refresh_bom_table()
        QMessageBox.information(
            self,
            "Starter Pack Added",
            f"Successfully added 18 kW Drive Panel starter kit ({added_count} equipment lines) to your Project BOM!"
        )

    def _remove_bom_item(self, row: int):
        if 0 <= row < len(self.selected_components):
            self.selected_components.pop(row)
            for idx, comp in enumerate(self.selected_components, 1):
                comp.item_no = idx
            self._refresh_bom_table()

    def _switch_surface_item(self, row: int):
        if 0 <= row < len(self.selected_components):
            comp = self.selected_components[row]
            curr = getattr(comp, "surface", "Z").upper()
            new_surf = "Z" if curr == "Z+1" else "Z+1"
            comp.surface = new_surf
            if new_surf == "Z+1":
                comp.mounting_type = MountingType.DOOR
            else:
                if comp.mounting_type == MountingType.DOOR:
                    comp.mounting_type = MountingType.PLATE
            self._refresh_bom_table()

    def _clear_all_selection(self):
        if not self.selected_components:
            return
        reply = QMessageBox.question(
            self,
            "Clear Project BOM",
            "Are you sure you want to remove all components from the Project BOM?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.clear_selection()

    def _refresh_bom_table(self):
        self.bom_table.setRowCount(len(self.selected_components))
        total_units = 0
        total_cost = 0.0
        total_power = 0.0
        total_heat = 0.0

        for row, comp in enumerate(self.selected_components):
            header_item = QTableWidgetItem(f"{row + 1}.")
            header_item.setTextAlignment(Qt.AlignCenter)
            self.bom_table.setVerticalHeaderItem(row, header_item)

            total_units += comp.quantity
            total_cost += comp.total_price
            if getattr(comp, "power_kw", 0.0):
                total_power += float(comp.power_kw) * comp.quantity
            if getattr(comp, "heat_loss_w", 0.0):
                total_heat += float(comp.heat_loss_w) * comp.quantity

            self.bom_table.setItem(row, 0, QTableWidgetItem(str(comp.item_no)))
            self.bom_table.setItem(row, 1, QTableWidgetItem(comp.part_number or "-"))
            self.bom_table.setItem(row, 2, QTableWidgetItem(comp.name))
            self.bom_table.setItem(row, 3, QTableWidgetItem(comp.manufacturer))
            self.bom_table.setItem(row, 4, QTableWidgetItem(comp.category.value if hasattr(comp.category, "value") else str(comp.category)))

            surf_val = getattr(comp, "surface", "Z").upper()
            surf_item = QTableWidgetItem("Outer Door (Z+1)" if surf_val == "Z+1" else "Mounting Plate (Z)")
            if surf_val == "Z+1":
                surf_item.setForeground(QColor("#FF9A4E"))
            else:
                surf_item.setForeground(QColor("#111C24"))
            self.bom_table.setItem(row, 5, surf_item)

            self.bom_table.setItem(row, 6, QTableWidgetItem(str(comp.quantity)))
            self.bom_table.setItem(row, 7, QTableWidgetItem(f"{int(comp.width_mm)} × {int(comp.height_mm)} × {int(comp.depth_mm)} mm"))

            v = getattr(comp, "voltage", "") or ""
            kw = getattr(comp, "power_kw", 0.0) or 0.0
            a = getattr(comp, "rated_current_a", 0.0) or 0.0
            spec = f"{v}"
            if kw > 0:
                spec += f" | {kw}kW"
            if a > 0:
                spec += f" | {a}A"
            self.bom_table.setItem(row, 8, QTableWidgetItem(spec))

            self.bom_table.setItem(row, 9, QTableWidgetItem(f"${comp.unit_price:.2f} / ₹{comp.unit_price * 83.0:,.0f}"))
            self.bom_table.setItem(row, 10, QTableWidgetItem(f"${comp.total_price:.2f} / ₹{comp.total_price * 83.0:,.0f}"))

            # Remove action button
            btn_del = QPushButton("Remove")
            btn_del.setToolTip("Remove this item from BOM")
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: #EF4444;
                    color: #FFFFFF;
                    border: 1px solid #DC2626;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 8px;
                    min-height: 24px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #DC2626;
                }
            """)
            btn_del.clicked.connect(lambda checked=False, r=row: self._remove_bom_item(r))
            self.bom_table.setCellWidget(row, 11, btn_del)

            # Switch Surface action button
            btn_sw = QPushButton("Switch Z / Z+1")
            btn_sw.setToolTip("Toggle placement surface between Plate (Z) and Door (Z+1)")
            btn_sw.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #111C24;
                    border: 1.5px solid #8A8C8D;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 2px 8px;
                    min-height: 24px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #F5F6F7;
                    border-color: #FF9A4E;
                }
            """)
            btn_sw.clicked.connect(lambda checked=False, r=row: self._switch_surface_item(r))
            self.bom_table.setCellWidget(row, 12, btn_sw)

        self.lbl_bom_title.setText(f"Project Bill of Materials (BOM): {len(self.selected_components)} Items ({total_units} Physical Units)")
        self.lbl_summary.setText(
            f"Total: {len(self.selected_components)} Items | {total_units} Units | Total Power: {total_power:.1f} kW | Dissipation: {total_heat:.0f} W | Est. Cost: ${total_cost:,.2f} / ₹{total_cost * 83.0:,.0f}"
        )

    def set_initial_selection(self, components: List[Component]):
        """Populate initial components."""
        self.selected_components = list(components)
        self._refresh_bom_table()

    def _proceed_to_bom(self):
        if not self.selected_components:
            QMessageBox.warning(
                self,
                "Empty Project BOM",
                "Your Project BOM is currently empty. Please search and add at least one component, or click '18kW Drive Starter Pack' before proceeding."
            )
            return

        summary_data = {
            "total_items": len(self.selected_components),
            "total_units": sum(c.quantity for c in self.selected_components),
            "total_cost": sum(c.total_price for c in self.selected_components)
        }
        self.bom_ready.emit([c.to_dict() for c in self.selected_components], summary_data)
