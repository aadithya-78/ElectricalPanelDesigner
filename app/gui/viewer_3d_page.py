"""
Step 5 GUI: 3D Visualization & Verification Page.
Renders 3D enclosure and components converted directly from the 2D mounting plate layout.
Used strictly for visualization, verification, and inspection.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal

from app.models.project import ProjectData
from app.gui.enclosure_3d_widget import Enclosure3DWidget


class Viewer3DPage(QWidget):
    back_to_2d_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Optional[ProjectData] = None

        self._init_ui()

    def load_project(self, project: ProjectData):
        self.project = project
        self._sync_3d_view()
        self._update_status()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Top Action Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        btn_back = QPushButton("Back to 2D Layout")
        btn_back.setProperty("class", "secondary")
        btn_back.setMinimumHeight(34)
        btn_back.clicked.connect(self.back_to_2d_requested.emit)
        top_bar.addWidget(btn_back)

        title = QLabel("Step 5: 3D Visualization & Physical Inspection")
        title.setStyleSheet("font-size: 15px; font-weight: 800; color: #111C24;")
        top_bar.addWidget(title)

        sub = QLabel("(Converted directly from 2D Front-View Layout)")
        sub.setStyleSheet("color: #616365; font-size: 12px;")
        top_bar.addWidget(sub)

        top_bar.addStretch()

        btn_export = QPushButton("Export Project Deliverables")
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                color: #111C24;
                border: 1px solid #E88536;
                font-weight: 700;
                font-size: 11px;
                padding: 5px 16px;
                min-height: 28px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        btn_export.clicked.connect(self.export_requested.emit)
        top_bar.addWidget(btn_export)

        layout.addLayout(top_bar)

        # Center 3D PyVista Viewer
        self.viewer_3d = Enclosure3DWidget()
        layout.addWidget(self.viewer_3d, stretch=1)

        # Bottom Verification Info Bar
        status_frame = QFrame()
        status_frame.setStyleSheet("background-color: #FFFFFF; border: 1.5px solid #8A8C8D; border-radius: 6px; padding: 6px 14px;")
        status_layout = QHBoxLayout(status_frame)

        self.lbl_dims = QLabel("Enclosure: 800 × 1200 × 400 mm (IP54)")
        self.lbl_dims.setStyleSheet("font-weight: 700; color: #111C24; font-size: 13px;")
        status_layout.addWidget(self.lbl_dims)

        self.lbl_depth_clearance = QLabel("Usable Depth: 323 mm | Max Component Depth: 232 mm (Adequate Clearance)")
        self.lbl_depth_clearance.setStyleSheet("color: #FF9A4E; font-size: 12px; margin-left: 20px; font-weight: 700;")
        status_layout.addWidget(self.lbl_depth_clearance)

        self.lbl_heat = QLabel("Total Heat Loss: 0.0 W")
        self.lbl_heat.setStyleSheet("color: #616365; font-size: 12px; margin-left: 20px; font-weight: 600;")
        status_layout.addWidget(self.lbl_heat)

        status_layout.addStretch()
        layout.addWidget(status_frame)

    def _sync_3d_view(self):
        if not self.project:
            return

        for inst in self.project.physical_instances:
            if inst.is_placed and not inst.is_external:
                surf = getattr(inst, "surface", "Z").upper()
                mnt = inst.mounting_type.value if hasattr(inst.mounting_type, "value") else str(inst.mounting_type)
                if surf == "Z+1" or mnt == "Door":
                    inst.z = self.project.enclosure.depth - 5.0
                elif mnt == "DIN Rail":
                    inst.z = 7.5
                else:
                    inst.z = 0.0

        self.viewer_3d.update_scene(
            self.project.enclosure,
            self.project.physical_instances,
            self.project.din_rails,
            self.project.wiring_ducts
        )

    def _update_status(self):
        if not self.project:
            return
        enc = self.project.enclosure
        self.lbl_dims.setText(f"Enclosure: {int(enc.width)} × {int(enc.height)} × {int(enc.depth)} mm ({enc.ip_rating})")
        
        placed = [i for i in self.project.physical_instances if i.is_placed and not i.is_external]
        max_d = max([i.depth for i in placed], default=0.0)
        usable_d = enc.internal_depth

        if max_d > usable_d:
            self.lbl_depth_clearance.setText(f"Usable Depth: {int(usable_d)}mm | Max Comp Depth: {int(max_d)}mm (EXCEEDS ENCLOSURE DEPTH!)")
            self.lbl_depth_clearance.setStyleSheet("color: #F43F5E; font-weight: 700; font-size: 12px; margin-left: 20px;")
        else:
            self.lbl_depth_clearance.setText(f"Usable Depth: {int(usable_d)}mm | Max Comp Depth: {int(max_d)}mm (Adequate Door Clearance)")
            self.lbl_depth_clearance.setStyleSheet("color: #2DD4BF; font-size: 12px; margin-left: 20px;")

        if self.project.bom:
            self.lbl_heat.setText(f"Total Heat Loss: {self.project.bom.total_heat_loss():.1f} W")
