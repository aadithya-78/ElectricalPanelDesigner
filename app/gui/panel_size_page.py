"""
Step 3 GUI: Panel Size Recommendation and Enclosure Dimensions Selection.
Calculates mathematical panel sizing using local algorithms (IEC 61439).
Displays minimum estimated dimensions, recommended dimensions, maximum component depth,
and space utilization percentage, with manual override capabilities and clear mounting plate distinction.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, 
    QPushButton, QGroupBox, QGridLayout, QComboBox, QFrame, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal

from app.models.enclosure import Enclosure
from app.models.project import ProjectData
from app.engineering.enclosure_sizing import EnclosureSizingEngine


class PanelSizePage(QWidget):
    panel_size_confirmed = Signal(object) # Emits Enclosure instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Optional[ProjectData] = None
        self.sizing_data = {}

        self._init_ui()

    def set_project(self, project: ProjectData):
        self.project = project
        if project and project.enclosure and project.enclosure.width > 0:
            enc = project.enclosure
            self.spin_w.setValue(enc.width)
            self.spin_h.setValue(enc.height)
            self.spin_d.setValue(enc.depth)
            
            for i in range(self.combo_ip.count()):
                if enc.ip_rating in self.combo_ip.itemText(i):
                    self.combo_ip.setCurrentIndex(i)
                    break
            
            if getattr(enc, "door_type", "SINGLE") == "DOUBLE_VERTICAL":
                self.combo_door.setCurrentIndex(1)
            else:
                self.combo_door.setCurrentIndex(0)
            self._update_preview()
        else:
            self._calculate_minimums()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(20)

        # 1. Header
        header_lbl = QLabel("Step 3: Automatic Panel Size Recommendation & Enclosure Sizing")
        header_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: #111C24;")
        layout.addWidget(header_lbl)

        sub_lbl = QLabel(
            "Panel dimensions are mathematically computed from component footprints, required IEC clearances, "
            "inter-component trunking, and mounting plate margins. You can accept the recommended standard enclosure "
            "or manually enter custom dimensions."
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("color: #616365; font-size: 13px; line-height: 1.5;")
        layout.addWidget(sub_lbl)

        # 2. Mathematical Recommendation Card
        self.rec_card = QFrame()
        self.rec_card.setObjectName("recCard")
        self.rec_card.setStyleSheet("""
            QFrame#recCard {
                background: #FFFFFF;
                border: 1.5px solid #FF9A4E;
                border-radius: 8px;
                padding: 16px 20px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        rec_layout = QVBoxLayout(self.rec_card)
        rec_layout.setSpacing(10)

        lbl_rec_title = QLabel("MATHEMATICAL PACKING & ENGINEERING SIZING (IEC 61439)")
        lbl_rec_title.setStyleSheet("font-weight: 800; color: #111C24; font-size: 12px; letter-spacing: 0.5px;")
        rec_layout.addWidget(lbl_rec_title)

        # Metrics Grid (4 Key Indicators)
        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(24)
        metrics_grid.setVerticalSpacing(8)

        # 1. Min Estimated Plate
        lbl_min_title = QLabel("Minimum Usable Plate:")
        lbl_min_title.setStyleSheet("color: #616365; font-size: 12px; font-weight: 600;")
        self.lbl_min_val = QLabel("700 × 900 mm")
        self.lbl_min_val.setStyleSheet("color: #111C24; font-size: 14px; font-weight: 700;")
        metrics_grid.addWidget(lbl_min_title, 0, 0)
        metrics_grid.addWidget(self.lbl_min_val, 1, 0)

        # 2. Recommended Enclosure
        lbl_rec_title_2 = QLabel("Recommended Standard Enclosure:")
        lbl_rec_title_2.setStyleSheet("color: #616365; font-size: 12px; font-weight: 600;")
        self.lbl_rec_val = QLabel("800 × 1200 × 400 mm")
        self.lbl_rec_val.setStyleSheet("color: #FF9A4E; font-size: 15px; font-weight: 800;")
        metrics_grid.addWidget(lbl_rec_title_2, 0, 1)
        metrics_grid.addWidget(self.lbl_rec_val, 1, 1)

        # 3. Max Component Depth
        lbl_depth_title = QLabel("Max Component Depth:")
        lbl_depth_title.setStyleSheet("color: #616365; font-size: 12px; font-weight: 600;")
        self.lbl_depth_val = QLabel("232 mm")
        self.lbl_depth_val.setStyleSheet("color: #111C24; font-size: 14px; font-weight: 700;")
        metrics_grid.addWidget(lbl_depth_title, 0, 2)
        metrics_grid.addWidget(self.lbl_depth_val, 1, 2)

        # 4. Space Utilization
        lbl_util_title = QLabel("Estimated Space Utilization:")
        lbl_util_title.setStyleSheet("color: #616365; font-size: 12px; font-weight: 600;")
        self.lbl_util_val = QLabel("48.5%")
        self.lbl_util_val.setStyleSheet("color: #FF9A4E; font-size: 14px; font-weight: 800;")
        metrics_grid.addWidget(lbl_util_title, 0, 3)
        metrics_grid.addWidget(self.lbl_util_val, 1, 3)

        rec_layout.addLayout(metrics_grid)
        layout.addWidget(self.rec_card)

        # 3. Enclosure Dimensions Input Group
        input_group = QGroupBox("Enclosure External Dimensions Envelope")
        grid = QGridLayout(input_group)
        grid.setVerticalSpacing(16)
        grid.setHorizontalSpacing(24)
        grid.setContentsMargins(20, 24, 20, 20)

        # Width
        lbl_w = QLabel("Enclosure External Width (mm):")
        lbl_w.setStyleSheet("color: #53728f; font-size: 13px; font-weight: 600;")
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(300.0, 4000.0)
        self.spin_w.setValue(800.0)
        self.spin_w.setSingleStep(50.0)
        self.spin_w.setMinimumHeight(40)
        self.spin_w.valueChanged.connect(self._update_preview)
        grid.addWidget(lbl_w, 0, 0)
        grid.addWidget(self.spin_w, 0, 1)

        # Height
        lbl_h = QLabel("Enclosure External Height (mm):")
        lbl_h.setStyleSheet("color: #53728f; font-size: 13px; font-weight: 600;")
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(400.0, 4000.0)
        self.spin_h.setValue(1200.0)
        self.spin_h.setSingleStep(50.0)
        self.spin_h.setMinimumHeight(40)
        self.spin_h.valueChanged.connect(self._update_preview)
        grid.addWidget(lbl_h, 1, 0)
        grid.addWidget(self.spin_h, 1, 1)

        # Depth
        lbl_d = QLabel("Enclosure External Depth (mm):")
        lbl_d.setStyleSheet("color: #53728f; font-size: 13px; font-weight: 600;")
        self.spin_d = QDoubleSpinBox()
        self.spin_d.setRange(150.0, 2000.0)
        self.spin_d.setValue(400.0)
        self.spin_d.setSingleStep(50.0)
        self.spin_d.setMinimumHeight(40)
        self.spin_d.valueChanged.connect(self._update_preview)
        grid.addWidget(lbl_d, 2, 0)
        grid.addWidget(self.spin_d, 2, 1)

        # IP Rating
        lbl_ip = QLabel("Ingress Protection Rating:")
        lbl_ip.setStyleSheet("color: #53728f; font-size: 13px; font-weight: 600;")
        self.combo_ip = QComboBox()
        self.combo_ip.addItems(["IP54 (Industrial Indoor)", "IP55 (Dust & Water Jet Resistant)", "IP65 (Outdoor Weatherproof)"])
        self.combo_ip.setMinimumHeight(40)
        self.combo_ip.setStyleSheet("color: #000000; background-color: #FFFFFF; font-size: 13px; font-weight: 600;")
        grid.addWidget(lbl_ip, 3, 0)
        grid.addWidget(self.combo_ip, 3, 1)

        # Door Configuration (Single Door vs Double Door)
        lbl_door = QLabel("Door Configuration:")
        lbl_door.setStyleSheet("color: #53728f; font-size: 13px; font-weight: 600;")
        self.combo_door = QComboBox()
        self.combo_door.addItems(["Single Door", "Double Door (Vertical Split)"])
        self.combo_door.setMinimumHeight(40)
        self.combo_door.setStyleSheet("color: #000000; background-color: #FFFFFF; font-size: 13px; font-weight: 600;")
        self.combo_door.currentIndexChanged.connect(self._update_preview)
        grid.addWidget(lbl_door, 4, 0)
        grid.addWidget(self.combo_door, 4, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        layout.addWidget(input_group)

        # 4. Standard Industrial Enclosure Presets
        presets_group = QGroupBox("Standard Industrial Catalog Sizes (Rittal / Schneider / Eldon)")
        presets_layout = QGridLayout(presets_group)
        presets_layout.setContentsMargins(16, 20, 16, 16)
        presets_layout.setSpacing(10)

        presets = [
            ("500 x 700 x 250", 500, 700, 250, "SINGLE"),
            ("600 x 800 x 250", 600, 800, 250, "SINGLE"),
            ("800 x 1000 x 300", 800, 1000, 300, "SINGLE"),
            ("800 x 1200 x 400", 800, 1200, 400, "SINGLE"),
            ("1000 x 1200 x 400 (Double Door)", 1000, 1200, 400, "DOUBLE_VERTICAL"),
            ("1200 x 1800 x 500 (Double Door)", 1200, 1800, 500, "DOUBLE_VERTICAL")
        ]

        for idx, (text, w, h, d, dtype) in enumerate(presets):
            btn = QPushButton(f"{text} mm" if "Door" not in text else f"{text}")
            btn.setProperty("class", "secondary")
            btn.setMinimumHeight(38)
            btn.setStyleSheet("font-size: 12px; font-weight: 600; padding: 6px 12px;")
            btn.clicked.connect(lambda checked=False, pw=w, ph=h, pd=d, dt=dtype: self._apply_preset(pw, ph, pd, dt))
            presets_layout.addWidget(btn, idx // 3, idx % 3)

        layout.addWidget(presets_group)

        # 5. Clear Distinction: Enclosure vs Usable Mounting Plate
        self.preview_card = QFrame()
        self.preview_card.setObjectName("prevCard")
        self.preview_card.setStyleSheet("""
            QFrame#prevCard {
                background: #F8F9FA;
                border: 1.5px dashed #FF9A4E;
                border-radius: 8px;
                padding: 16px 20px;
            }
        """)
        prev_lay = QVBoxLayout(self.preview_card)
        prev_lay.setSpacing(6)

        self.lbl_plate_preview = QLabel("Usable Mounting Plate Surface: 740 × 1060 mm  |  Usable Interior Depth: 323 mm")
        self.lbl_plate_preview.setStyleSheet("color: #111C24; font-weight: 700; font-size: 13px;")
        prev_lay.addWidget(self.lbl_plate_preview)

        self.lbl_plate_note = QLabel(
            "Mounting plate area excludes 30mm side borders and 100mm bottom cable entry reserve. "
            "All 2D component placement will occur strictly within this usable plate surface."
        )
        self.lbl_plate_note.setStyleSheet("color: #616365; font-size: 12px;")
        prev_lay.addWidget(self.lbl_plate_note)

        layout.addWidget(self.preview_card)

        # 6. Proceed Action Button
        btn_layout = QHBoxLayout()
        self.btn_proceed = QPushButton("Proceed to Step 4: 2D Front-View Layout Editor")
        self.btn_proceed.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                color: #111C24;
                border: 1px solid #E88536;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 700;
                min-height: 38px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        self.btn_proceed.clicked.connect(self._confirm_and_proceed)
        btn_layout.addWidget(self.btn_proceed)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        self._update_preview()

    def _calculate_minimums(self):
        if not self.project:
            return

        instances = self.project.physical_instances or self.project.bom.expand_to_instances()
        active = [i for i in instances if not i.is_external]
        if not active:
            return

        sizing = EnclosureSizingEngine.calculate_required_space(active)
        self.sizing_data = sizing

        self.lbl_min_val.setText(f"{int(sizing['min_internal_w'])} × {int(sizing['min_internal_h'])} mm")
        self.lbl_rec_val.setText(f"{int(sizing['recommended_w'])} × {int(sizing['recommended_h'])} × {int(sizing['recommended_d'])} mm")
        self.lbl_depth_val.setText(f"{int(sizing['max_comp_depth'])} mm")
        self.lbl_util_val.setText(f"{sizing['space_utilization_pct']}%")

        self.spin_w.setValue(sizing["recommended_w"])
        self.spin_h.setValue(sizing["recommended_h"])
        self.spin_d.setValue(sizing["recommended_d"])
        self._update_preview()

    def _apply_preset(self, w: float, h: float, d: float, door_type: str = "SINGLE"):
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)
        self.spin_d.setValue(d)
        if door_type == "DOUBLE_VERTICAL" or w >= 1000.0:
            self.combo_door.setCurrentIndex(1)
        else:
            self.combo_door.setCurrentIndex(0)
        self._update_preview()

    def _update_preview(self):
        w = self.spin_w.value()
        h = self.spin_h.value()
        d = self.spin_d.value()

        plate_w = max(100.0, w - 60.0)
        plate_h = max(100.0, h - 140.0)
        usable_d = max(50.0, d - 77.0)

        is_double = (self.combo_door.currentIndex() == 1)
        door_str = f"Double Door (2x {int(w/2)} x {int(h)} mm, Vertical Split)" if is_double else f"Single Door ({int(w)} x {int(h)} mm)"

        self.lbl_plate_preview.setText(
            f"Mounting Plate: {int(plate_w)} x {int(plate_h)} mm  |  Door: {door_str}  |  Usable Depth: {int(usable_d)} mm"
        )

    def _confirm_and_proceed(self):
        w = self.spin_w.value()
        h = self.spin_h.value()
        d = self.spin_d.value()
        ip = self.combo_ip.currentText().split()[0]
        door_type = "DOUBLE_VERTICAL" if self.combo_door.currentIndex() == 1 else "SINGLE"

        enc = Enclosure(
            width=w,
            height=h,
            depth=d,
            ip_rating=ip,
            door_type=door_type,
            manufacturer="Standard Industrial",
            model_name=f"Industrial Enclosure {int(w)}x{int(h)}x{int(d)}"
        )

        self.panel_size_confirmed.emit(enc)
