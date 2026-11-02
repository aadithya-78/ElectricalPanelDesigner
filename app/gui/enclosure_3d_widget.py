"""
Interactive 3D Electrical Enclosure Viewer using PyVista and PyVistaQt.
Renders enclosure, mounting plate, DIN rails, wiring ducts, and electrical cuboids with labels.
Accurately maps 2D top-left coordinates to 3D Cartesian coordinates.
"""
from typing import List, Dict, Any, Optional
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QCheckBox, QComboBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from app.models.component import PhysicalInstance, MountingType
from app.models.enclosure import Enclosure, DINRail, WiringDuct


class Enclosure3DWidget(QWidget):
    component_selected = Signal(str) # Emits instance_id when selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enclosure = Enclosure()
        self.instances: List[PhysicalInstance] = []
        self.din_rails: List[DINRail] = []
        self.wiring_ducts: List[WiringDuct] = []
        self.selected_instance_id: Optional[str] = None
        
        self.show_enclosure_frame = True
        self.show_labels = True
        self.show_clearance_boxes = False
        self.show_door = True

        self._actor_map: Dict[str, str] = {} # Map actor name to instance ID

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 3D View Toolbar
        tb = QHBoxLayout()
        tb.setContentsMargins(8, 6, 8, 4)
        tb.setSpacing(6)

        btn_front = QPushButton("Front View")
        btn_front.setProperty("class", "secondary")
        btn_front.setStyleSheet("padding: 5px 12px; font-size: 12px; min-height: 28px;")
        btn_front.clicked.connect(self.view_front)
        tb.addWidget(btn_front)

        btn_iso = QPushButton("Isometric")
        btn_iso.setProperty("class", "secondary")
        btn_iso.setStyleSheet("padding: 5px 12px; font-size: 12px; min-height: 28px;")
        btn_iso.clicked.connect(self.view_isometric)
        tb.addWidget(btn_iso)

        btn_top = QPushButton("Top View")
        btn_top.setProperty("class", "secondary")
        btn_top.setStyleSheet("padding: 5px 12px; font-size: 12px; min-height: 28px;")
        btn_top.clicked.connect(self.view_top)
        tb.addWidget(btn_top)

        btn_side = QPushButton("Side View")
        btn_side.setProperty("class", "secondary")
        btn_side.setStyleSheet("padding: 5px 12px; font-size: 12px; min-height: 28px;")
        btn_side.clicked.connect(self.view_side)
        tb.addWidget(btn_side)

        btn_reset = QPushButton("Reset Camera")
        btn_reset.setProperty("class", "secondary")
        btn_reset.setStyleSheet("padding: 5px 12px; font-size: 12px; min-height: 28px;")
        btn_reset.clicked.connect(self.reset_camera)
        tb.addWidget(btn_reset)

        tb.addStretch()

        self.chk_enc = QCheckBox("Show Enclosure")
        self.chk_enc.setChecked(True)
        self.chk_enc.stateChanged.connect(self._toggle_enclosure)
        tb.addWidget(self.chk_enc)

        self.chk_door = QCheckBox("Show Door (Z+1)")
        self.chk_door.setChecked(True)
        self.chk_door.stateChanged.connect(self._toggle_door)
        tb.addWidget(self.chk_door)

        self.chk_labels = QCheckBox("Show Labels")
        self.chk_labels.setChecked(True)
        self.chk_labels.stateChanged.connect(self._toggle_labels)
        tb.addWidget(self.chk_labels)

        self.chk_clearance = QCheckBox("Show Clearances")
        self.chk_clearance.setChecked(False)
        self.chk_clearance.stateChanged.connect(self._toggle_clearance)
        tb.addWidget(self.chk_clearance)

        layout.addLayout(tb)

        # PyVistaQt Interactor
        self.plotter = QtInteractor(self)
        self.plotter.set_background("#FFFFFF", top="#F4F5F7")
        layout.addWidget(self.plotter.interactor)

        # Render axes orientation marker
        self.plotter.add_axes()
        self.view_isometric()

    def _toggle_door(self, state):
        self.show_door = bool(state)
        self.update_scene(self.enclosure, self.instances, self.din_rails, self.wiring_ducts)

    def update_scene(
        self,
        enclosure: Enclosure,
        instances: List[PhysicalInstance],
        din_rails: List[DINRail],
        wiring_ducts: List[WiringDuct]
    ):
        """Re-render the entire 3D panel scene."""
        self.enclosure = enclosure
        self.instances = instances
        self.din_rails = din_rails
        self.wiring_ducts = wiring_ducts

        self.plotter.clear()
        self._actor_map.clear()

        plate_w = enclosure.mounting_plate_width
        plate_h = enclosure.mounting_plate_height
        enc_w = enclosure.width
        enc_h = enclosure.height
        enc_d = enclosure.depth

        x_min = -enclosure.side_margin
        x_max = x_min + enc_w
        y_min = -enclosure.gland_plate_height
        y_max = y_min + enc_h
        z_min = -enclosure.plate_standoff
        z_max = z_min + enc_d

        # 1. Back Mounting Plate (Galvanized zinc steel)
        plate_mesh = pv.Box(bounds=(0, plate_w, 0, plate_h, -3.0, 0.0))
        self.plotter.add_mesh(
            plate_mesh,
            color="#CBD5E1",
            opacity=0.95,
            show_edges=True,
            edge_color="#475569",
            name="mounting_plate"
        )

        # 2. Outer Door Sheet (Z+1 Surface)
        if getattr(self, "show_door", True):
            is_double = (getattr(enclosure, "door_type", "SINGLE") == "DOUBLE_VERTICAL")
            if is_double:
                mid_x = (x_min + x_max) / 2.0
                left_leaf = pv.Box(bounds=(x_min, mid_x - 1.0, y_min, y_max, z_max - 2.0, z_max))
                right_leaf = pv.Box(bounds=(mid_x + 1.0, x_max, y_min, y_max, z_max - 2.0, z_max))
                self.plotter.add_mesh(
                    left_leaf,
                    color="#CBD5E1",
                    opacity=0.30,
                    show_edges=True,
                    edge_color="#38BDF8",
                    line_width=1.5,
                    name="door_left_mesh"
                )
                self.plotter.add_mesh(
                    right_leaf,
                    color="#CBD5E1",
                    opacity=0.30,
                    show_edges=True,
                    edge_color="#38BDF8",
                    line_width=1.5,
                    name="door_right_mesh"
                )
            else:
                door_sheet = pv.Box(bounds=(x_min, x_max, y_min, y_max, z_max - 2.0, z_max))
                self.plotter.add_mesh(
                    door_sheet,
                    color="#CBD5E1",
                    opacity=0.25,
                    show_edges=True,
                    edge_color="#38BDF8",
                    line_width=2,
                    name="door_sheet_mesh"
                )

        # 3. Transparent Enclosure Body with visible structural frame
        if self.show_enclosure_frame:
            enc_mesh = pv.Box(bounds=(x_min, x_max, y_min, y_max, z_min, z_max))
            self.plotter.add_mesh(
                enc_mesh,
                color="#38BDF8",
                opacity=0.15,
                style="wireframe",
                line_width=2,
                name="enclosure_wireframe"
            )

            # Solid semi-transparent walls
            self.plotter.add_mesh(
                enc_mesh,
                color="#1E293B",
                opacity=0.08,
                name="enclosure_solid"
            )

        # 4. Physical DIN Rails (DIN EN 60715 35mm profile on mounting plate)
        for rail in self.din_rails:
            # Map top-left Y to 3D Cartesian Y
            y_3d = plate_h - rail.y - rail.height
            rail_mesh = pv.Box(bounds=(
                rail.x, rail.x + rail.length,
                y_3d, y_3d + rail.height,
                rail.z, rail.z + rail.depth
            ))
            self.plotter.add_mesh(
                rail_mesh,
                color="#ECEFF1",
                show_edges=True,
                edge_color="#90A4AE",
                name=f"mesh_{rail.id}"
            )

        # 5. Slotted Wiring Ducts (Trunking on mounting plate)
        for duct in self.wiring_ducts:
            is_vert = duct.orientation.upper() == "VERTICAL" or int(getattr(duct, "rotation", 0)) in (90, 270)
            duct_w = duct.width if is_vert else duct.length
            # Visual height along Y
            duct_h = duct.length if is_vert else (duct.height if 0 < duct.height <= 80 else 40.0)
            # Profile depth along Z (into panel)
            duct_d = duct.height if is_vert else (duct.width if 0 < duct.width <= 80 else 40.0)

            y_3d = plate_h - duct.y - duct_h
            duct_mesh = pv.Box(bounds=(
                duct.x, duct.x + duct_w,
                y_3d, y_3d + duct_h,
                duct.z, duct.z + duct_d
            ))

            self.plotter.add_mesh(
                duct_mesh,
                color=duct.color,
                opacity=0.75,
                show_edges=True,
                edge_color="#334155",
                name=f"mesh_{duct.id}"
            )

        # 6. Electrical Components (3D Cuboids on both Z Mounting Plate and Z+1 Door)
        label_points = []
        label_texts = []

        for inst in self.instances:
            if not inst.is_placed or inst.is_external:
                continue
            if any(k in inst.name.lower() for k in ["enclosure", "cabinet"]):
                continue
            if getattr(inst, "category", "").lower() in ["enclosure", "enclosures", "cabinet", "cabinets"]:
                continue
            if getattr(inst, "is_enclosure", False):
                continue

            eff_w = inst.height if int(inst.rotation) in (90, 270) else inst.width
            eff_h = inst.width if int(inst.rotation) in (90, 270) else inst.height
            is_door_item = (getattr(inst, "surface", "Z").upper() == "Z+1")

            if is_door_item:
                if not getattr(self, "show_door", True):
                    continue
                # Map Door (Z+1) coordinates
                x_3d = x_min + inst.x
                y_3d = y_min + (enc_h - inst.y - eff_h)
                z_comp_min = z_max - min(inst.depth * 0.7, 45.0)
                z_comp_max = z_max + max(6.0, inst.depth * 0.3)

                comp_mesh = pv.Box(bounds=(
                    x_3d, x_3d + eff_w,
                    y_3d, y_3d + eff_h,
                    z_comp_min, z_comp_max
                ))
                label_pt = [x_3d + eff_w / 2.0, y_3d + eff_h / 2.0, z_comp_max + 5.0]
            else:
                # Map Mounting Plate (Z) coordinates
                y_3d = plate_h - inst.y - eff_h
                comp_mesh = pv.Box(bounds=(
                    inst.x, inst.x + eff_w,
                    y_3d, y_3d + eff_h,
                    inst.z, inst.z + inst.depth
                ))
                label_pt = [inst.x + eff_w / 2.0, y_3d + eff_h / 2.0, inst.z + inst.depth + 5.0]

            is_selected = (inst.id == self.selected_instance_id)
            color = "#FACC15" if is_selected else inst.color

            actor_name = f"mesh_{inst.id}"
            self._actor_map[actor_name] = inst.id

            self.plotter.add_mesh(
                comp_mesh,
                color=color,
                opacity=0.95,
                show_edges=True,
                edge_color="#0F172A" if not is_selected else "#F59E0B",
                line_width=3 if is_selected else 1,
                name=actor_name
            )

            # Optional Clearance Boxes
            if self.show_clearance_boxes and not is_door_item:
                c_box = inst.clearance_box
                c_y_3d = plate_h - c_box["max_y"]
                c_h = c_box["max_y"] - c_box["min_y"]
                clr_mesh = pv.Box(bounds=(
                    c_box["min_x"], c_box["max_x"],
                    c_y_3d, c_y_3d + c_h,
                    c_box["min_z"], c_box["max_z"]
                ))
                self.plotter.add_mesh(
                    clr_mesh,
                    color="#FF9800",
                    opacity=0.15,
                    style="wireframe",
                    line_width=1,
                    name=f"clr_{inst.id}"
                )

            label_points.append(label_pt)
            label_texts.append(inst.name)

        # 6. Component Text Labels
        if self.show_labels and label_points:
            import numpy as np
            points = np.array(label_points)
            self.plotter.add_point_labels(
                points,
                label_texts,
                point_size=0,
                font_size=10,
                text_color="#111C24",
                fill_shape=False,
                always_visible=True,
                name="component_labels"
            )

        self.plotter.render()

    def view_front(self):
        """Set camera to front view directly facing mounting plate."""
        plate_w = self.enclosure.mounting_plate_width
        plate_h = self.enclosure.mounting_plate_height
        center = [plate_w / 2.0, plate_h / 2.0, self.enclosure.depth / 2.0]
        dist = max(plate_w, plate_h) * 2.2
        self.plotter.camera_position = [
            (center[0], center[1], center[2] + dist),
            center,
            (0, 1, 0)
        ]

    def view_top(self):
        """Set camera to top view looking down."""
        plate_w = self.enclosure.mounting_plate_width
        plate_h = self.enclosure.mounting_plate_height
        center = [plate_w / 2.0, plate_h / 2.0, self.enclosure.depth / 2.0]
        dist = max(plate_w, plate_h) * 2.2
        self.plotter.camera_position = [
            (center[0], center[1] + dist, center[2]),
            center,
            (0, 0, -1)
        ]

    def view_side(self):
        """Set camera to side view."""
        plate_w = self.enclosure.mounting_plate_width
        plate_h = self.enclosure.mounting_plate_height
        center = [plate_w / 2.0, plate_h / 2.0, self.enclosure.depth / 2.0]
        dist = max(plate_w, plate_h) * 2.2
        self.plotter.camera_position = [
            (center[0] + dist, center[1], center[2]),
            center,
            (0, 1, 0)
        ]

    def view_isometric(self):
        """Set camera to standard isometric engineering view."""
        plate_w = self.enclosure.mounting_plate_width
        plate_h = self.enclosure.mounting_plate_height
        center = [plate_w / 2.0, plate_h / 2.0, self.enclosure.depth / 2.0]
        dist = max(plate_w, plate_h) * 1.8
        self.plotter.camera_position = [
            (center[0] + dist * 0.8, center[1] - dist * 0.6, center[2] + dist * 0.9),
            center,
            (0, 1, 0)
        ]

    def reset_camera(self):
        self.view_isometric()

    def _toggle_enclosure(self, state: int):
        self.show_enclosure_frame = bool(state)
        self.update_scene(self.enclosure, self.instances, self.din_rails, self.wiring_ducts)

    def _toggle_labels(self, state: int):
        self.show_labels = bool(state)
        self.update_scene(self.enclosure, self.instances, self.din_rails, self.wiring_ducts)

    def _toggle_clearance(self, state: int):
        self.show_clearance_boxes = bool(state)
        self.update_scene(self.enclosure, self.instances, self.din_rails, self.wiring_ducts)
