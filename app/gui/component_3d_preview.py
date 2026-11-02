"""
Interactive 3D Component Preview Widget for BOM verification.
Renders an accurate 3D cuboid of the selected electrical component with
dimensions (X=Width, Y=Height, Z=Depth in mm), category coloring, terminal styling,
and electrical specifications overlay.
"""
from typing import Optional, Dict, Any
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QGridLayout
)
from PySide6.QtCore import Qt
from app.models.component import Component, PhysicalInstance, get_component_color


class Component3DPreviewWidget(QWidget):
    """3D viewport displaying an individual electrical component in true scale."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_comp: Optional[Component] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header Title Card
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1.5px solid #8A8C8D;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(4, 4, 4, 4)

        t_lbl = QLabel("3D Component Preview")
        t_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #111C24;")
        h_layout.addWidget(t_lbl)

        h_layout.addStretch()

        self.surface_badge = QLabel("Surface: Z (Mounting Plate)")
        self.surface_badge.setStyleSheet("""
            background: #F4F5F7;
            color: #111C24;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid #8A8C8D;
        """)
        h_layout.addWidget(self.surface_badge)
        layout.addWidget(header_frame)

        # PyVistaQt 3D Viewport
        self.plotter = QtInteractor(self)
        self.plotter.set_background("#FFFFFF", top="#F4F5F7")
        layout.addWidget(self.plotter.interactor, stretch=1)

        # View Angle Quick Buttons
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)

        b_iso = QPushButton("Isometric")
        b_iso.setProperty("class", "secondary")
        b_iso.setStyleSheet("padding: 3px 8px; font-size: 11px; min-height: 24px;")
        b_iso.clicked.connect(self.view_isometric)
        btn_bar.addWidget(b_iso)

        b_front = QPushButton("Front (X/Y)")
        b_front.setProperty("class", "secondary")
        b_front.setStyleSheet("padding: 3px 8px; font-size: 11px; min-height: 24px;")
        b_front.clicked.connect(self.view_front)
        btn_bar.addWidget(b_front)

        b_side = QPushButton("Side (Y/Z)")
        b_side.setProperty("class", "secondary")
        b_side.setStyleSheet("padding: 3px 8px; font-size: 11px; min-height: 24px;")
        b_side.clicked.connect(self.view_side)
        btn_bar.addWidget(b_side)

        b_top = QPushButton("Top (X/Z)")
        b_top.setProperty("class", "secondary")
        b_top.setStyleSheet("padding: 3px 8px; font-size: 11px; min-height: 24px;")
        b_top.clicked.connect(self.view_top)
        btn_bar.addWidget(b_top)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # Specifications Card
        self.spec_card = QFrame()
        self.spec_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1.5px solid #8A8C8D;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QLabel {
                color: #616365;
                font-size: 11px;
            }
        """)
        grid = QGridLayout(self.spec_card)
        grid.setSpacing(6)
        grid.setContentsMargins(6, 6, 6, 6)

        self.lbl_name = QLabel("Select a component to inspect in 3D")
        self.lbl_name.setStyleSheet("font-weight: 800; color: #111C24; font-size: 12px;")
        grid.addWidget(self.lbl_name, 0, 0, 1, 2)

        self.lbl_part = QLabel("P/N: —")
        self.lbl_part.setStyleSheet("color: #FF9A4E; font-weight: 700;")
        grid.addWidget(self.lbl_part, 1, 0)

        self.lbl_mfr = QLabel("Manufacturer: —")
        grid.addWidget(self.lbl_mfr, 1, 1)

        self.lbl_dims = QLabel("Dimensions: — × — × — mm")
        self.lbl_dims.setStyleSheet("font-weight: 700; color: #111C24;")
        grid.addWidget(self.lbl_dims, 2, 0)

        self.lbl_mounting = QLabel("Mounting: —")
        grid.addWidget(self.lbl_mounting, 2, 1)

        self.lbl_elec = QLabel("Ratings: —")
        self.lbl_elec.setStyleSheet("color: #F97316; font-weight: 600;")
        grid.addWidget(self.lbl_elec, 3, 0, 1, 2)

        layout.addWidget(self.spec_card)

        # Initial axes
        self.plotter.add_axes()
        self.view_isometric()

    def set_component(self, comp: Optional[Component]):
        """Render the 3D model of the specified BOM component."""
        self.current_comp = comp
        self.plotter.clear()

        if not comp:
            self.lbl_name.setText("Select a component to inspect in 3D")
            self.lbl_part.setText("P/N: —")
            self.lbl_mfr.setText("Manufacturer: —")
            self.lbl_dims.setText("Dimensions: — × — × — mm")
            self.lbl_mounting.setText("Mounting: —")
            self.lbl_elec.setText("Ratings: —")
            self.surface_badge.setText("Surface: —")
            self.plotter.render()
            return

        w = max(5.0, comp.width_mm)
        h = max(5.0, comp.height_mm)
        d = max(5.0, comp.depth_mm)

        # Update labels
        self.lbl_name.setText(comp.name)
        self.lbl_part.setText(f"P/N: {comp.part_number or 'Standard'}")
        self.lbl_mfr.setText(f"Mfr: {comp.manufacturer}")
        self.lbl_dims.setText(f"X: {int(w)}mm × Y: {int(h)}mm × Z: {int(d)}mm")
        mnt_val = comp.mounting_type.value if hasattr(comp.mounting_type, 'value') else str(comp.mounting_type)
        self.lbl_mounting.setText(f"Mounting: {mnt_val}")

        # Electrical ratings string
        elec_parts = []
        if getattr(comp, "voltage", ""):
            elec_parts.append(str(comp.voltage))
        if getattr(comp, "rated_current_a", 0.0) > 0:
            elec_parts.append(f"{comp.rated_current_a}A")
        if getattr(comp, "power_kw", 0.0) > 0:
            elec_parts.append(f"{comp.power_kw} kW")
        if comp.heat_loss_watts > 0:
            elec_parts.append(f"Heat: {comp.heat_loss_watts}W")

        self.lbl_elec.setText(f"Ratings: {' | '.join(elec_parts) if elec_parts else 'Standard Industrial'}")

        # Surface badge
        surf = getattr(comp, "surface", "Z").upper()
        if surf == "Z+1" or mnt_val == "Door":
            self.surface_badge.setText("Surface: Z+1 (Door Mounted)")
            self.surface_badge.setStyleSheet("background-color: #FF9A4E; color: #111C24; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #E88536;")
        else:
            self.surface_badge.setText("Surface: Z (Mounting Plate)")
            self.surface_badge.setStyleSheet("background-color: #F4F5F7; color: #111C24; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #8A8C8D;")

        # 1. Main Component Cuboid Mesh (Centered in X and Y, base at Z=0)
        bounds = (-w / 2.0, w / 2.0, -h / 2.0, h / 2.0, 0.0, d)
        box_mesh = pv.Box(bounds=bounds)

        cat_val = comp.category.value if hasattr(comp.category, 'value') else str(comp.category)
        color = get_component_color(comp.name, cat_val)

        self.plotter.add_mesh(
            box_mesh,
            color=color,
            opacity=0.95,
            show_edges=True,
            edge_color="#0F172A",
            line_width=2,
            name="comp_body"
        )

        # 2. Terminal Blocks / Face Accent
        is_door = (surf == "Z+1" or mnt_val == "Door")
        if is_door and any(k in comp.name.lower() for k in ["hmi", "touch", "panel", "display"]):
            # Add blue/black display glass inset on front face (Z=d)
            disp_w = w * 0.82
            disp_h = h * 0.72
            disp_mesh = pv.Box(bounds=(-disp_w / 2.0, disp_w / 2.0, -disp_h / 2.0, disp_h / 2.0, d - 1.0, d + 1.5))
            self.plotter.add_mesh(disp_mesh, color="#0A0F1D", opacity=0.99, show_edges=True, edge_color="#38BDF8", name="hmi_screen")
        elif is_door and any(k in comp.name.lower() for k in ["push", "button", "switch", "lamp", "led"]):
            # Cylindrical button/indicator head on front
            r = min(w, h) * 0.38
            cyl = pv.Cylinder(center=(0, 0, d + 8.0), direction=(0, 0, 1), radius=r, height=16.0)
            btn_color = "#EF4444" if "red" in comp.name.lower() or "e-stop" in comp.name.lower() else ("#22C55E" if "green" in comp.name.lower() else "#F59E0B")
            self.plotter.add_mesh(cyl, color=btn_color, show_edges=True, name="button_head")
        else:
            # Top & Bottom electrical terminal blocks
            term_h = min(15.0, h * 0.15)
            # Top terminals
            top_term = pv.Box(bounds=(-w * 0.45, w * 0.45, h / 2.0 - term_h, h / 2.0, d * 0.2, d * 0.8))
            self.plotter.add_mesh(top_term, color="#1E293B", show_edges=True, edge_color="#64748B", name="top_term")
            # Bottom terminals
            bot_term = pv.Box(bounds=(-w * 0.45, w * 0.45, -h / 2.0, -h / 2.0 + term_h, d * 0.2, d * 0.8))
            self.plotter.add_mesh(bot_term, color="#1E293B", show_edges=True, edge_color="#64748B", name="bot_term")

        # 3. 3D Dimension Annotation Labels
        import numpy as np
        dim_pts = np.array([
            [0.0, -h / 2.0 - 15.0, 0.0],          # Width label below
            [w / 2.0 + 15.0, 0.0, 0.0],           # Height label right
            [-w / 2.0 - 15.0, 0.0, d / 2.0]        # Depth label left
        ])
        dim_texts = [
            f"W (X): {int(w)} mm",
            f"H (Y): {int(h)} mm",
            f"D (Z): {int(d)} mm"
        ]
        self.plotter.add_point_labels(
            dim_pts,
            dim_texts,
            font_size=10,
            text_color="#F8FAFC",
            fill_shape=True,
            shape_color="#0F172A",
            shape_opacity=0.8,
            always_visible=True,
            name="dimension_labels"
        )

        self.reset_camera()

    def view_isometric(self):
        if not self.current_comp:
            return
        w = max(5.0, self.current_comp.width_mm)
        h = max(5.0, self.current_comp.height_mm)
        d = max(5.0, self.current_comp.depth_mm)
        span = max(w, h, d) * 2.2
        self.plotter.camera_position = [
            (span * 0.9, -span * 0.7, span * 0.8),
            (0, 0, d / 2.0),
            (0, 1, 0)
        ]

    def view_front(self):
        if not self.current_comp:
            return
        w = max(5.0, self.current_comp.width_mm)
        h = max(5.0, self.current_comp.height_mm)
        d = max(5.0, self.current_comp.depth_mm)
        span = max(w, h, d) * 2.5
        self.plotter.camera_position = [
            (0, 0, span),
            (0, 0, d / 2.0),
            (0, 1, 0)
        ]

    def view_side(self):
        if not self.current_comp:
            return
        w = max(5.0, self.current_comp.width_mm)
        h = max(5.0, self.current_comp.height_mm)
        d = max(5.0, self.current_comp.depth_mm)
        span = max(w, h, d) * 2.5
        self.plotter.camera_position = [
            (span, 0, d / 2.0),
            (0, 0, d / 2.0),
            (0, 1, 0)
        ]

    def view_top(self):
        if not self.current_comp:
            return
        w = max(5.0, self.current_comp.width_mm)
        h = max(5.0, self.current_comp.height_mm)
        d = max(5.0, self.current_comp.depth_mm)
        span = max(w, h, d) * 2.5
        self.plotter.camera_position = [
            (0, span, d / 2.0),
            (0, 0, d / 2.0),
            (0, 0, -1)
        ]

    def reset_camera(self):
        self.view_isometric()

