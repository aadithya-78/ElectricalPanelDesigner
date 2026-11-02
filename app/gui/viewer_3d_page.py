"""
Step 5 GUI: 3D Visualization & Verification Page.
Renders 3D enclosure and components converted directly from the 2D mounting plate layout.
Used strictly for visualization, verification, and inspection.
Includes built-in mobile Augmented Reality (AR) server for 1:1 real-world physical inspection.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QDialog, QApplication
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QImage, QPixmap, QDesktopServices

from app.models.project import ProjectData
from app.gui.enclosure_3d_widget import Enclosure3DWidget
from app.export.ar_server import get_ar_server, generate_qr_png_bytes


class ARViewDialog(QDialog):
    """Dialog showing QR Code and network URL for mobile camera AR viewing."""

    def __init__(self, url: str, metadata: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mobile AR View - Electrical Panel (1:1 Physical Scale)")
        self.setFixedWidth(460)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                color: #111C24;
            }
            QLabel {
                color: #111C24;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # Header Title + Scale Badge
        h_layout = QHBoxLayout()
        title = QLabel("Mobile Augmented Reality (AR) View")
        title.setStyleSheet("font-size: 15px; font-weight: 800; color: #111C24;")
        h_layout.addWidget(title)

        badge = QLabel("1:1 ACTUAL SCALE")
        badge.setStyleSheet("background-color: #FF9A4E; color: #111C24; font-weight: 800; font-size: 10px; padding: 3px 8px; border-radius: 4px;")
        h_layout.addWidget(badge)
        h_layout.addStretch()
        layout.addLayout(h_layout)

        desc = QLabel(
            "Scan this QR code with your mobile phone camera (iPhone Camera or Android Google Lens / Chrome) "
            "to view and inspect this electrical panel in your room at actual 1:1 physical size."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #616365; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        # QR Code Card
        qr_frame = QFrame()
        qr_frame.setStyleSheet("background-color: #F8FAFC; border: 1.5px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setAlignment(Qt.AlignCenter)

        self.lbl_qr = QLabel()
        self.lbl_qr.setAlignment(Qt.AlignCenter)
        qr_bytes = generate_qr_png_bytes(url)
        qimg = QImage()
        qimg.loadFromData(qr_bytes)
        pix = QPixmap.fromImage(qimg)
        self.lbl_qr.setPixmap(pix.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_layout.addWidget(self.lbl_qr)
        layout.addWidget(qr_frame)

        # URL Frame with Copy and Open buttons
        url_frame = QFrame()
        url_frame.setStyleSheet("background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px 10px;")
        url_layout = QHBoxLayout(url_frame)
        url_layout.setContentsMargins(4, 4, 4, 4)

        lbl_url = QLabel(url)
        lbl_url.setStyleSheet("font-family: monospace; font-size: 12px; font-weight: 700; color: #0284C7;")
        lbl_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        url_layout.addWidget(lbl_url, stretch=1)

        btn_copy = QPushButton("Copy Link")
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        btn_copy.clicked.connect(lambda: self._copy_url(url, btn_copy))
        url_layout.addWidget(btn_copy)

        btn_open = QPushButton("Open in Browser")
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        url_layout.addWidget(btn_open)

        layout.addWidget(url_frame)

        # Panel Dimension Info
        w = int(metadata.get("width_mm", 800))
        h = int(metadata.get("height_mm", 1200))
        d = int(metadata.get("depth_mm", 400))
        lbl_meta = QLabel(f"Panel: {w} × {h} × {d} mm ({w/1000.0:.2f} × {h/1000.0:.2f} × {d/1000.0:.2f} m) | {metadata.get('component_count', 0)} Placed Components")
        lbl_meta.setStyleSheet("color: #616365; font-size: 11px; font-weight: 600;")
        lbl_meta.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_meta)

        # Quick Mobile Instructions
        inst_box = QLabel(
            "<b>Quick Steps:</b><br>"
            "1. Connect your phone to the same Wi-Fi network as this PC.<br>"
            "2. Point phone camera at QR code to open the web link.<br>"
            "3. Tap <b>'View in AR (Actual Size)'</b> to project the panel onto your floor."
        )
        inst_box.setStyleSheet("background-color: #FFFBEB; border: 1px solid #FDE68A; border-radius: 6px; padding: 8px 12px; font-size: 11px; color: #92400E; line-height: 1.4;")
        inst_box.setWordWrap(True)
        layout.addWidget(inst_box)

        # Done button
        btn_done = QPushButton("Close")
        btn_done.setStyleSheet("""
            QPushButton {
                background-color: #111C24;
                color: #FFFFFF;
                padding: 7px 16px;
                font-weight: 700;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2A3945;
            }
        """)
        btn_done.clicked.connect(self.accept)
        layout.addWidget(btn_done)

    def _copy_url(self, url: str, btn: QPushButton):
        QApplication.clipboard().setText(url)
        btn.setText("Copied!")
        QTimer.singleShot(1800, lambda: btn.setText("Copy Link"))


class Viewer3DPage(QWidget):
    back_to_2d_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Optional[ProjectData] = None
        self.ar_server = get_ar_server()
        self.current_ar_url: str = ""

        self._init_ui()

    def load_project(self, project: ProjectData):
        self.project = project
        self._sync_3d_view()
        self._update_status()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Top Action Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        btn_back = QPushButton("Back to 2D Layout")
        btn_back.setProperty("class", "secondary")
        btn_back.setMinimumHeight(32)
        btn_back.clicked.connect(self.back_to_2d_requested.emit)
        top_bar.addWidget(btn_back)

        title = QLabel("Step 5: 3D Visualization & Physical Inspection")
        title.setStyleSheet("font-size: 15px; font-weight: 800; color: #111C24;")
        top_bar.addWidget(title)

        sub = QLabel("(Converted directly from 2D Front-View Layout)")
        sub.setStyleSheet("color: #616365; font-size: 12px;")
        top_bar.addWidget(sub)

        top_bar.addStretch()

        # AR View Control Box: Button on top, URL directly below the button
        ar_box = QVBoxLayout()
        ar_box.setSpacing(2)
        ar_box.setAlignment(Qt.AlignCenter)

        self.btn_ar_view = QPushButton("AR View")
        self.btn_ar_view.setToolTip("Start AR Web Server & view panel in mobile camera at 1:1 scale")
        self.btn_ar_view.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                border: 1px solid #0369A1;
                font-weight: 800;
                font-size: 11px;
                padding: 4px 18px;
                min-height: 26px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
        """)
        self.btn_ar_view.clicked.connect(self._on_ar_view_clicked)
        ar_box.addWidget(self.btn_ar_view)

        self.lbl_ar_url = QLabel("AR URL: Click 'AR View' to start")
        self.lbl_ar_url.setStyleSheet("font-size: 11px; color: #64748B; font-weight: 600;")
        self.lbl_ar_url.setAlignment(Qt.AlignCenter)
        self.lbl_ar_url.setOpenExternalLinks(True)
        ar_box.addWidget(self.lbl_ar_url)

        top_bar.addLayout(ar_box)

        # Export Deliverables Button
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

    def _on_ar_view_clicked(self):
        """Starts local AR web server, updates 3D GLB model, updates URL label below button, and displays QR popup."""
        if not self.project:
            return

        # Start server if not running
        url = self.ar_server.start()
        self.current_ar_url = url

        # Generate and update latest 3D GLB model
        self.ar_server.update_model(
            self.project.enclosure,
            self.project.physical_instances,
            self.project.din_rails,
            self.project.wiring_ducts,
            show_door=getattr(self.viewer_3d, "show_door", True)
        )

        # Display URL link directly below the AR View button
        self.lbl_ar_url.setText(f"<a href='{url}' style='color: #0284C7; font-weight: 700;'>{url}</a>")

        # Open QR code popup dialog for instant mobile phone scanning
        dlg = ARViewDialog(url, self.ar_server.panel_metadata, parent=self)
        dlg.exec_()

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

        # If AR server is active, keep mobile AR model in sync
        if self.ar_server and self.ar_server.is_running:
            self.ar_server.update_model(
                self.project.enclosure,
                self.project.physical_instances,
                self.project.din_rails,
                self.project.wiring_ducts,
                show_door=getattr(self.viewer_3d, "show_door", True)
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
