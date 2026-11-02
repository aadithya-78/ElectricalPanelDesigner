"""
Step 2 GUI: Professional Manufacturer Selection Interface.
Enterprise soft blue & white design with generous table row heights.
"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, 
    QButtonGroup, QGroupBox, QTableWidget, QTableWidgetItem, 
    QComboBox, QPushButton, QProgressBar, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QThread


MANUFACTURER_OPTIONS = {
    "VFD": ["Schneider Electric", "Siemens", "ABB", "Delta", "Danfoss"],
    "MCCB": ["Schneider Electric", "Siemens", "ABB", "L&T"],
    "MCB": ["Schneider Electric", "Siemens", "ABB", "Legrand"],
    "Contactor": ["Schneider Electric", "Siemens", "ABB", "L&T"],
    "Relay": ["Omron", "Finder", "Schneider Electric"],
    "SMPS": ["Mean Well", "Phoenix Contact", "Siemens"],
    "Terminal Blocks": ["Connectwell", "Phoenix Contact", "Weidmüller"],
    "Enclosure": ["Rittal", "Schneider Electric", "Local Fabrication"],
    "DIN Rail": ["Phoenix Contact", "Schneider Electric", "Generic"],
    "Wire Duct": ["Panduit", "Phoenix Contact", "Generic"],
    "Cooling Fan": ["Rittal", "Schneider Electric", "Generic"]
}


class BOMGenerationWorker(QThread):
    finished_signal = Signal(list)
    error_signal = Signal(str)

    def __init__(self, gemini_client, requirement_data: Dict[str, Any], mfr_selections: Dict[str, str]):
        super().__init__()
        self.gemini_client = gemini_client
        self.requirement_data = requirement_data
        self.mfr_selections = mfr_selections

    def run(self):
        try:
            bom_items = self.gemini_client.generate_bom(self.requirement_data, self.mfr_selections)
            self.finished_signal.emit(bom_items)
        except Exception as e:
            self.error_signal.emit(str(e))


class ManufacturerPage(QWidget):
    bom_generated = Signal(list, dict)

    def __init__(self, gemini_client, parent=None):
        super().__init__(parent)
        self.gemini_client = gemini_client
        self.requirement_data: Dict[str, Any] = {}
        self.worker: Optional[BOMGenerationWorker] = None
        self.category_combos: Dict[str, QComboBox] = {}

        self._init_ui()

    def set_requirement_data(self, data: Dict[str, Any]):
        self.requirement_data = data
        pref_vfd = data.get("preferred_brands", {}).get("vfd")
        if pref_vfd and "VFD" in self.category_combos:
            for i in range(self.category_combos["VFD"].count()):
                if pref_vfd.lower() in self.category_combos["VFD"].itemText(i).lower():
                    self.category_combos["VFD"].setCurrentIndex(i)
                    break

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        header_lbl = QLabel("Step 2: Component Manufacturer Selection")
        header_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: #F8FAFC;")
        layout.addWidget(header_lbl)

        sub_lbl = QLabel(
            "Select vendor preference strategy or configure specific brands for each component category. "
            "You can choose a single brand ecosystem, best-of-breed mixed vendors, or custom brand pairing."
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.4;")
        layout.addWidget(sub_lbl)

        # Strategy Radio Buttons
        strategy_group = QGroupBox("Vendor Sourcing Strategy")
        strat_layout = QHBoxLayout(strategy_group)
        strat_layout.setContentsMargins(18, 20, 18, 16)
        strat_layout.setSpacing(24)
        self.btn_group = QButtonGroup(self)

        self.radio_single = QRadioButton("Single Manufacturer (Schneider / Siemens ecosystem)")
        self.radio_mixed = QRadioButton("Mixed Manufacturer (Best-of-breed industrial standard)")
        self.radio_ai = QRadioButton("AI-Recommended Vendors")

        self.radio_mixed.setChecked(True)
        self.btn_group.addButton(self.radio_single, 1)
        self.btn_group.addButton(self.radio_mixed, 2)
        self.btn_group.addButton(self.radio_ai, 3)

        strat_layout.addWidget(self.radio_single)
        strat_layout.addWidget(self.radio_mixed)
        strat_layout.addWidget(self.radio_ai)
        layout.addWidget(strategy_group)

        self.btn_group.idClicked.connect(self._on_strategy_changed)

        # Manufacturer Category Table with generous row height
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Component Category", "Selected Vendor", "Alternative Options"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setRowCount(len(MANUFACTURER_OPTIONS))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46) # Generous row height

        for row_idx, (cat, options) in enumerate(MANUFACTURER_OPTIONS.items()):
            cat_item = QTableWidgetItem(f"  {cat}")
            cat_item.setFlags(Qt.ItemIsEnabled)
            cat_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.table.setItem(row_idx, 0, cat_item)

            combo = QComboBox()
            combo.setEditable(True)
            combo.setMinimumHeight(36)
            combo.addItems(options)
            self.category_combos[cat] = combo
            self.table.setCellWidget(row_idx, 1, combo)

            alts_item = QTableWidgetItem(", ".join(options[1:]))
            alts_item.setFlags(Qt.ItemIsEnabled)
            alts_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            alts_item.setForeground(Qt.gray)
            self.table.setItem(row_idx, 2, alts_item)

        layout.addWidget(self.table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("border-radius: 4px; background-color: #1E293B;")
        layout.addWidget(self.progress_bar)

        # Generate Complete BOM Button
        btn_layout = QHBoxLayout()
        self.gen_btn = QPushButton("Generate Complete BOM")
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #2563EB);
                color: #FFFFFF;
                border: 1px solid #38BDF8;
                padding: 12px 28px;
                font-size: 14px;
                font-weight: 700;
                min-height: 42px;
            }
        """)
        self.gen_btn.clicked.connect(self._generate_bom)
        btn_layout.addWidget(self.gen_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _on_strategy_changed(self, strategy_id: int):
        if strategy_id == 1:
            for cat, combo in self.category_combos.items():
                if "Schneider Electric" in [combo.itemText(i) for i in range(combo.count())]:
                    combo.setCurrentText("Schneider Electric")
        elif strategy_id == 2:
            defaults = {
                "VFD": "Schneider Electric",
                "MCCB": "Schneider Electric",
                "MCB": "Schneider Electric",
                "Contactor": "Schneider Electric",
                "Relay": "Omron",
                "SMPS": "Mean Well",
                "Terminal Blocks": "Connectwell",
                "Enclosure": "Rittal",
                "DIN Rail": "Phoenix Contact",
                "Wire Duct": "Panduit",
                "Cooling Fan": "Rittal"
            }
            for cat, default_brand in defaults.items():
                if cat in self.category_combos:
                    self.category_combos[cat].setCurrentText(default_brand)

    def _generate_bom(self):
        mfr_selections = {cat: combo.currentText().strip() for cat, combo in self.category_combos.items()}
        self.gen_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        self.worker = BOMGenerationWorker(self.gemini_client, self.requirement_data, mfr_selections)
        self.worker.finished_signal.connect(self._on_bom_finished)
        self.worker.error_signal.connect(self._on_bom_error)
        self.worker.start()

    def _on_bom_finished(self, bom_items: list):
        self.gen_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        mfr_selections = {cat: combo.currentText().strip() for cat, combo in self.category_combos.items()}
        self.bom_generated.emit(bom_items, mfr_selections)

    def _on_bom_error(self, err: str):
        self.gen_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "BOM Generation Error", f"Failed to generate BOM: {err}")
