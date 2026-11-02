"""
Dialogs for Thermal Analysis, Application Settings, and STEP CAD Export.
"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, 
    QLineEdit, QPushButton, QComboBox, QGroupBox, QGridLayout, 
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt

from app.models.project import ProjectData
from app.engineering.thermal_calculator import ThermalCalculator
from app.geometry.step_exporter import STEPExporter


class ThermalDialog(QDialog):
    def __init__(self, project: ProjectData, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Industrial Thermal & Cooling Balance Analysis")
        self.setMinimumSize(540, 420)
        self.setStyleSheet("background-color: #FFFFFF; color: #111C24;")

        self._init_ui()
        self._calculate()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Electrical Enclosure Heat Dissipation Analysis")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #111C24;")
        layout.addWidget(title)

        # Environmental parameters
        input_group = QGroupBox("Operating Ambient Conditions")
        input_layout = QGridLayout(input_group)

        input_layout.addWidget(QLabel("Maximum Ambient Temperature (°C):"), 0, 0)
        self.spin_amb = QDoubleSpinBox()
        self.spin_amb.setRange(0.0, 70.0)
        self.spin_amb.setValue(35.0)
        self.spin_amb.valueChanged.connect(self._calculate)
        input_layout.addWidget(self.spin_amb, 0, 1)

        input_layout.addWidget(QLabel("Target Maximum Internal Temperature (°C):"), 1, 0)
        self.spin_int = QDoubleSpinBox()
        self.spin_int.setRange(20.0, 70.0)
        self.spin_int.setValue(45.0)
        self.spin_int.valueChanged.connect(self._calculate)
        input_layout.addWidget(self.spin_int, 1, 1)

        layout.addWidget(input_group)

        # Thermal Results Card
        res_group = QGroupBox("Heat Load & Cooling Requirements")
        self.res_layout = QGridLayout(res_group)

        self.lbl_total_heat = QLabel("0.0 W")
        self.lbl_nat_heat = QLabel("0.0 W")
        self.lbl_excess_heat = QLabel("0.0 W")
        self.lbl_airflow = QLabel("0.0 m³/h")
        self.lbl_rec = QLabel("Evaluating...")
        self.lbl_rec.setWordWrap(True)
        self.lbl_rec.setStyleSheet("font-weight: bold; color: #FF9A4E;")

        self.res_layout.addWidget(QLabel("Total Internal Installed Heat Loss:"), 0, 0)
        self.res_layout.addWidget(self.lbl_total_heat, 0, 1)

        self.res_layout.addWidget(QLabel("Natural Surface Dissipation (Sheet Steel):"), 1, 0)
        self.res_layout.addWidget(self.lbl_nat_heat, 1, 1)

        self.res_layout.addWidget(QLabel("Net Excess Thermal Load:"), 2, 0)
        self.res_layout.addWidget(self.lbl_excess_heat, 2, 1)

        self.res_layout.addWidget(QLabel("Required Forced Airflow:"), 3, 0)
        self.res_layout.addWidget(self.lbl_airflow, 3, 1)

        self.res_layout.addWidget(QLabel("Cooling Recommendation:"), 4, 0)
        self.res_layout.addWidget(self.lbl_rec, 4, 1)

        layout.addWidget(res_group)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _calculate(self):
        amb = self.spin_amb.value()
        target = self.spin_int.value()
        results = ThermalCalculator.calculate(self.project.bom, self.project.enclosure, amb, target)

        self.lbl_total_heat.setText(f"{results['total_heat_loss_watts']:.1f} W")
        self.lbl_nat_heat.setText(f"{results['natural_dissipation_watts']:.1f} W")
        self.lbl_excess_heat.setText(f"{results['excess_heat_watts']:.1f} W")
        self.lbl_airflow.setText(f"{results['required_airflow_m3h']:.1f} m³/h")
        self.lbl_rec.setText(results['cooling_recommendation'])


class SettingsDialog(QDialog):
    def __init__(self, gemini_client, parent=None):
        super().__init__(parent)
        self.gemini_client = gemini_client
        self.setWindowTitle("AI & Engine Settings")
        self.setMinimumSize(500, 320)
        self.setStyleSheet("background-color: #FFFFFF; color: #111C24;")

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("AI Configuration & Model Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #111C24;")
        layout.addWidget(title)

        grid = QGridLayout()

        grid.addWidget(QLabel("Gemini API Key:"), 0, 0)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setText(self.gemini_client.api_key)
        grid.addWidget(self.key_input, 0, 1)

        grid.addWidget(QLabel("Model Selection:"), 1, 0)
        self.model_combo = QComboBox()
        models = self.gemini_client.get_available_models()
        self.model_combo.addItems(models)
        if self.gemini_client.model_name in models:
            self.model_combo.setCurrentText(self.gemini_client.model_name)
        grid.addWidget(self.model_combo, 1, 1)

        layout.addLayout(grid)

        btn_test = QPushButton("Test API Connection")
        btn_test.setProperty("class", "secondary")
        btn_test.clicked.connect(self._test_api)
        layout.addWidget(btn_test)

        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save Settings")
        btn_save.setProperty("class", "accent")
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _test_api(self):
        key = self.key_input.text().strip()
        model = self.model_combo.currentText().strip()
        try:
            from google import genai
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(model=model, contents="Ping")
            QMessageBox.information(self, "API Test Succeeded", f"Connected to {model} successfully!")
        except Exception as e:
            QMessageBox.critical(self, "API Test Failed", f"Could not connect: {str(e)}")

    def _save_settings(self):
        key = self.key_input.text().strip()
        model = self.model_combo.currentText().strip()
        self.gemini_client.update_settings(key, model)
        self.accept()

