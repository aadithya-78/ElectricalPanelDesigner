"""
Step 1 GUI: Natural Language Requirement Input and Automated BOM Generation.
Enterprise design with soft blue + white accents, high contrast typography,
and direct generation without intermediate manufacturer selection.
"""
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QPushButton, QGroupBox, QGridLayout, QComboBox, QScrollArea,
    QProgressBar, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread


class RequirementToBOMWorker(QThread):
    finished_signal = Signal(list, dict) # Emits (bom_items, req_data)
    error_signal = Signal(str)

    def __init__(self, gemini_client, requirement_text: str):
        super().__init__()
        self.gemini_client = gemini_client
        self.requirement_text = requirement_text

    def run(self):
        try:
            # 1. Analyze requirement
            req_data = self.gemini_client.analyze_requirement(self.requirement_text)
            
            # 2. Extract brand preference from requirement or default to standard
            text_upper = self.requirement_text.upper()
            mfr_pref = {
                "vfd": "Schneider Electric",
                "mccb": "Schneider Electric",
                "mcb": "Schneider Electric",
                "contactor": "Schneider Electric",
                "relays": "Phoenix Contact",
                "terminals": "Phoenix Contact",
                "smps": "Mean Well",
                "enclosure": "Rittal",
                "cooling": "Pfannenberg"
            }
            if "SIEMENS" in text_upper:
                mfr_pref["vfd"] = "Siemens"
                mfr_pref["mccb"] = "Siemens"
                mfr_pref["mcb"] = "Siemens"
                mfr_pref["contactor"] = "Siemens"
            elif "ABB" in text_upper:
                mfr_pref["vfd"] = "ABB"
                mfr_pref["mccb"] = "ABB"
                mfr_pref["mcb"] = "ABB"
                mfr_pref["contactor"] = "ABB"

            # 3. Generate BOM directly
            bom_items = self.gemini_client.generate_bom(req_data, mfr_pref)
            self.finished_signal.emit(bom_items, req_data)
        except Exception as e:
            self.error_signal.emit(str(e))


class RequirementPage(QWidget):
    bom_ready = Signal(list, dict) # Emits (bom_items, requirement_data)

    def __init__(self, gemini_client, parent=None):
        super().__init__(parent)
        self.gemini_client = gemini_client
        self.worker: Optional[RequirementToBOMWorker] = None
        self.extracted_data: Dict[str, Any] = {}
        self.generated_bom: List[Dict[str, Any]] = []

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(18)

        # 1. Header
        header_lbl = QLabel("Step 1: Industrial Requirement & Automated BOM Generation")
        header_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: #FFFFFF;")
        main_layout.addWidget(header_lbl)

        sub_lbl = QLabel(
            "Enter your electrical panel requirements in plain English. The AI engine automatically extracts "
            "technical ratings, standard motor FLA, required protective switchgear, and generates an editable BOM."
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.5;")
        main_layout.addWidget(sub_lbl)

        # 2. Quick Example Template Chips
        examples_layout = QHBoxLayout()
        examples_layout.setSpacing(8)
        examples_lbl = QLabel("Quick Templates:")
        examples_lbl.setStyleSheet("font-weight: 700; color: #38BDF8; font-size: 12px;")
        examples_layout.addWidget(examples_lbl)

        templates = [
            ("18 kW ATV630 Drive", "Create an 18 kW motor drive panel using Schneider ATV630."),
            ("7.5 kW DOL Starter", "Create a 7.5 kW DOL starter panel with contactor and overload relay."),
            ("15 kW VFD with PLC", "Design a 15 kW VFD panel with PLC, emergency stop and local/remote control."),
            ("30 kW Siemens Panel", "Create a 30 kW motor control panel with Siemens components.")
        ]

        for title, text in templates:
            btn = QPushButton(title)
            btn.setProperty("class", "secondary")
            btn.setStyleSheet("""
                QPushButton {
                    background: #1E293B;
                    color: #E2E8F0;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 500;
                    min-height: 28px;
                }
                QPushButton:hover {
                    background: #334155;
                    border-color: #38BDF8;
                    color: #FFFFFF;
                }
            """)
            btn.clicked.connect(lambda checked=False, t=text: self.text_input.setText(t))
            examples_layout.addWidget(btn)

        examples_layout.addStretch()
        main_layout.addLayout(examples_layout)

        # 3. Natural Language Input Box
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("e.g. Create an 18 kW motor drive panel using Schneider ATV630...")
        self.text_input.setText("Create an 18 kW motor drive panel using Schneider ATV630.")
        self.text_input.setMinimumHeight(110)
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A;
                border: 1.5px solid #334155;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 12px;
                font-size: 14px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border-color: #38BDF8;
                background-color: #0C1A38;
            }
        """)
        main_layout.addWidget(self.text_input)

        # 4. Action Buttons & Progress Bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.generate_btn = QPushButton("Generate Engineering BOM")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:0.5 #2563EB, stop:1 #0284C7);
                color: #FFFFFF;
                border: 1px solid #38BDF8;
                border-radius: 6px;
                padding: 10px 28px;
                font-size: 14px;
                font-weight: 700;
                min-height: 42px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:0.5 #3B82F6, stop:1 #38BDF8);
                border-color: #93C5FD;
            }
        """)
        self.generate_btn.clicked.connect(self._start_generation)
        btn_layout.addWidget(self.generate_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("border-radius: 4px; background-color: #1E293B;")
        btn_layout.addWidget(self.progress_bar)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # 5. Technical Details Card (Optional Preview)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll_content = QWidget()
        self.results_layout = QVBoxLayout(scroll_content)
        self.results_layout.setSpacing(14)

        # Parameters Card
        self.params_group = QGroupBox("Extracted Engineering Parameters")
        self.params_layout = QGridLayout(self.params_group)
        self.params_layout.setVerticalSpacing(12)
        self.params_layout.setHorizontalSpacing(18)
        self.params_group.setVisible(False)
        self.results_layout.addWidget(self.params_group)

        # Assumptions Card
        self.assumptions_group = QGroupBox("Provisional Engineering Assumptions (IEC 61439)")
        self.assumptions_layout = QVBoxLayout(self.assumptions_group)
        self.assumptions_layout.setSpacing(8)
        self.assumptions_group.setVisible(False)
        self.results_layout.addWidget(self.assumptions_group)

        self.results_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _start_generation(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Input", "Please enter panel requirements to generate the BOM.")
            return

        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        self.worker = RequirementToBOMWorker(self.gemini_client, text)
        self.worker.finished_signal.connect(self._on_generation_finished)
        self.worker.error_signal.connect(self._on_generation_error)
        self.worker.start()

    def _on_generation_finished(self, bom_items: List[Dict[str, Any]], req_data: Dict[str, Any]):
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.extracted_data = req_data
        self.generated_bom = bom_items
        self._populate_results(req_data)
        
        # Directly emit signal to proceed to Step 2: Editable BOM
        self.bom_ready.emit(bom_items, req_data)

    def _on_generation_error(self, err_msg: str):
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Generation Error", f"Failed to generate BOM: {err_msg}")

    def _populate_results(self, data: Dict[str, Any]):
        for i in reversed(range(self.params_layout.count())): 
            w = self.params_layout.itemAt(i).widget()
            if w: w.setParent(None)
        for i in reversed(range(self.assumptions_layout.count())): 
            w = self.assumptions_layout.itemAt(i).widget()
            if w: w.setParent(None)

        params = [
            ("Application:", str(data.get("application", "VFD Panel"))),
            ("Motor Rating:", f"{data.get('motor_kw', 18.5)} kW ({data.get('motor_kw_note', '')})"),
            ("Supply Voltage:", f"{data.get('supply_voltage', 415)}V AC, {data.get('phases', 3)}-Phase, {data.get('frequency_hz', 50)}Hz"),
            ("Drive / Starter:", str(data.get("drive_type", "Schneider ATV630"))),
            ("Estimated FLA:", f"{data.get('full_load_current_amps', 38.0)} A"),
            ("Control Scheme:", str(data.get("control_type", "Local/Remote"))),
            ("Ingress Protection:", str(data.get("ip_rating", "IP54"))),
            ("Cable Entry:", str(data.get("cable_entry", "Bottom Entry")))
        ]

        row = 0
        col = 0
        for label, val in params:
            lbl_key = QLabel(f"<b>{label}</b>")
            lbl_key.setStyleSheet("color: #38BDF8; font-size: 12px;")
            lbl_val = QLabel(val)
            lbl_val.setStyleSheet("color: #FFFFFF; background-color: #0F172A; padding: 6px 10px; border-radius: 4px; border: 1px solid #334155;")
            self.params_layout.addWidget(lbl_key, row, col * 2)
            self.params_layout.addWidget(lbl_val, row, col * 2 + 1)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        self.params_group.setVisible(True)

        assumptions = data.get("provisional_assumptions", [])
        for a in assumptions:
            lbl = QLabel(f"• {a}")
            lbl.setStyleSheet("color: #38BDF8; font-size: 13px; padding: 2px 0;")
            lbl.setWordWrap(True)
            self.assumptions_layout.addWidget(lbl)
        self.assumptions_group.setVisible(True)
