"""
Step 5 GUI: Full Panel Layout Designer (Manual & Automatic Modes).
Coordinates Left Palette, Center 3D PyVista Canvas, Right Properties Panel, and Bottom Status.
"""
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QSplitter, QFrame, QMessageBox, 
    QProgressBar, QScrollArea, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from app.models.project import ProjectData
from app.models.component import PhysicalInstance, MountingType
from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.geometry.auto_layout import AutoLayoutEngine
from app.geometry.collision_detector import CollisionDetector
from app.engineering.thermal_calculator import ThermalCalculator
from app.gui.enclosure_3d_widget import Enclosure3DWidget
from app.gui.properties_panel import PropertiesPanel


class PanelDesignerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Optional[ProjectData] = None

        self._init_ui()

    def load_project(self, project: ProjectData):
        self.project = project
        self._refresh_palette()
        self._sync_3d_scene()
        self._update_status_bar()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Top Mode Selector Banner
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        lbl_mode = QLabel("<b>Panel Design Mode:</b>")
        lbl_mode.setStyleSheet("font-size: 14px; color: #111C24;")
        top_bar.addWidget(lbl_mode)

        self.btn_auto = QPushButton("AUTOMATIC DESIGN (Optimal Sizing & Layout)")
        self.btn_auto.setProperty("class", "accent")
        self.btn_auto.setStyleSheet("padding: 10px 20px; font-weight: bold; background-color: #FF9A4E; color: #111C24; font-size: 13px;")
        self.btn_auto.clicked.connect(self._run_automatic_design)
        top_bar.addWidget(self.btn_auto)

        self.btn_manual = QPushButton("MANUAL DESIGN (Free Placement)")
        self.btn_manual.setProperty("class", "secondary")
        self.btn_manual.setStyleSheet("padding: 10px 20px; font-weight: bold; font-size: 13px;")
        self.btn_manual.clicked.connect(self._set_manual_mode)
        top_bar.addWidget(self.btn_manual)

        top_bar.addStretch()

        btn_auto_clear = QPushButton("Reset / Clear All Placements")
        btn_auto_clear.setProperty("class", "danger")
        btn_auto_clear.clicked.connect(self._clear_all_placements)
        top_bar.addWidget(btn_auto_clear)

        main_layout.addLayout(top_bar)

        # 2. Main 3-Pane Splitter (Left: Palette | Center: 3D View | Right: Properties)
        splitter = QSplitter(Qt.Horizontal)

        # LEFT PANE: Component Palette
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        palette_title = QLabel("BOM Physical Components Palette")
        palette_title.setStyleSheet("font-weight: bold; color: #4fc3f7; padding: 4px;")
        left_layout.addWidget(palette_title)

        palette_info = QLabel("Click an unplaced item to add to panel or select placed item:")
        palette_info.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        palette_info.setWordWrap(True)
        left_layout.addWidget(palette_info)

        self.palette_list = QListWidget()
        self.palette_list.setStyleSheet("background-color: #252526; border: 1px solid #333333;")
        self.palette_list.itemClicked.connect(self._on_palette_item_clicked)
        left_layout.addWidget(self.palette_list)

        splitter.addWidget(left_widget)

        # CENTER PANE: 3D Enclosure Viewer
        self.viewer_3d = Enclosure3DWidget()
        splitter.addWidget(self.viewer_3d)

        # RIGHT PANE: Properties Panel
        self.prop_panel = PropertiesPanel()
        self.prop_panel.property_changed.connect(self._on_property_modified)
        self.prop_panel.delete_requested.connect(self._on_delete_instance)
        splitter.addWidget(self.prop_panel)

        # Set splitter proportions: Left 20%, Center 60%, Right 20%
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 6)
        splitter.setStretchFactor(2, 2)

        main_layout.addWidget(splitter, stretch=1)

        # 3. Bottom Status & Engineering Metrics Bar
        status_frame = QFrame()
        status_frame.setStyleSheet("background-color: #252526; border: 1px solid #333333; border-radius: 4px; padding: 6px;")
        status_layout = QHBoxLayout(status_frame)

        self.lbl_enc_size = QLabel("Enclosure: 800 x 1200 x 400 mm (IP54)")
        self.lbl_enc_size.setStyleSheet("font-weight: bold; color: #4fc3f7; font-size: 13px;")
        status_layout.addWidget(self.lbl_enc_size)

        self.lbl_usable = QLabel("Mounting Plate: 740 x 1060 mm | Depth: 323 mm")
        self.lbl_usable.setStyleSheet("color: #b0bec5; font-size: 12px; margin-left: 15px;")
        status_layout.addWidget(self.lbl_usable)

        self.lbl_progress = QLabel("Placed: 0 / 0 instances (0%)")
        self.lbl_progress.setStyleSheet("color: #81c784; font-weight: bold; font-size: 12px; margin-left: 15px;")
        status_layout.addWidget(self.lbl_progress)

        self.lbl_collisions = QLabel("Collisions: 0")
        self.lbl_collisions.setStyleSheet("color: #e57373; font-weight: bold; font-size: 12px; margin-left: 15px;")
        status_layout.addWidget(self.lbl_collisions)

        status_layout.addStretch()
        main_layout.addWidget(status_frame)

    def _refresh_palette(self):
        if not self.project:
            return

        self.palette_list.clear()
        for inst in self.project.physical_instances:
            status_icon = "[Placed]" if inst.is_placed else "[Unplaced]"
            text = f"{status_icon} {inst.name} ({int(inst.width)}x{int(inst.height)} mm) [{inst.mounting_type.value}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, inst.id)
            if not inst.is_placed:
                item.setForeground(QColor("#FF9A4E"))
            self.palette_list.addItem(item)

    def _sync_3d_scene(self):
        if not self.project:
            return
        self.viewer_3d.update_scene(
            self.project.enclosure,
            self.project.physical_instances,
            self.project.din_rails,
            self.project.wiring_ducts
        )

    def _update_status_bar(self):
        if not self.project:
            return

        enc = self.project.enclosure
        self.lbl_enc_size.setText(f"Enclosure: {int(enc.width)} x {int(enc.height)} x {int(enc.depth)} mm ({enc.ip_rating})")
        self.lbl_usable.setText(f"Mounting Plate: {int(enc.mounting_plate_width)} x {int(enc.mounting_plate_height)} mm | Usable Depth: {int(enc.internal_depth)} mm")

        placed_count = sum(1 for i in self.project.physical_instances if i.is_placed and not i.is_external)
        total_count = sum(1 for i in self.project.physical_instances if not i.is_external)
        pct = int((placed_count / total_count * 100)) if total_count > 0 else 0
        self.lbl_progress.setText(f"Placed: {placed_count} / {total_count} instances ({pct}%)")

        # Check collisions
        violations = CollisionDetector.check_all_collisions(self.project.physical_instances)
        collision_count = sum(1 for _, _, msg in violations if "PHYSICAL COLLISION" in msg)
        clearance_count = sum(1 for _, _, msg in violations if "CLEARANCE VIOLATION" in msg)

        if collision_count > 0:
            self.lbl_collisions.setText(f"Collisions: {collision_count} | Clearance Violations: {clearance_count}")
            self.lbl_collisions.setStyleSheet("color: #ff5252; font-weight: bold; font-size: 12px; margin-left: 15px;")
        elif clearance_count > 0:
            self.lbl_collisions.setText(f"Clearance Warnings: {clearance_count}")
            self.lbl_collisions.setStyleSheet("color: #FF9A4E; font-weight: bold; font-size: 12px; margin-left: 15px;")
        else:
            self.lbl_collisions.setText("Collisions: 0 (Clean Layout)")
            self.lbl_collisions.setStyleSheet("color: #81c784; font-weight: bold; font-size: 12px; margin-left: 15px;")

    def _run_automatic_design(self):
        if not self.project:
            return

        # 1. Expand BOM items into physical instances if not already expanded
        if not self.project.physical_instances:
            self.project.physical_instances = self.project.bom.expand_to_instances()

        # 2. Run AutoLayout Engine
        enc, placed_instances, rails, ducts, warnings = AutoLayoutEngine.generate_layout(
            self.project.physical_instances
        )

        self.project.enclosure = enc
        self.project.physical_instances = placed_instances
        self.project.din_rails = rails
        self.project.wiring_ducts = ducts
        self.project.layout_mode = "AUTOMATIC"

        # 3. Calculate thermal data
        self.project.thermal_data = ThermalCalculator.calculate(self.project.bom, self.project.enclosure)

        # 4. Refresh Views
        self._refresh_palette()
        self._sync_3d_scene()
        self._update_status_bar()

        QMessageBox.information(
            self,
            "Automatic Layout Completed",
            f"Successfully arranged all components inside standard enclosure:\n"
            f"Dimensions: {int(enc.width)} x {int(enc.height)} x {int(enc.depth)} mm ({enc.ip_rating})\n"
            f"Created {len(rails)} physical DIN rails and {len(ducts)} wiring ducts.\n"
            f"Total Heat Loss: {self.project.bom.total_heat_loss():.1f} W."
        )

    def _set_manual_mode(self):
        if self.project:
            self.project.layout_mode = "MANUAL"
            QMessageBox.information(
                self,
                "Manual Design Mode",
                "Manual mode active. Click any component from the left palette to place or reposition it on the mounting plate. Use the right sidebar to adjust coordinates."
            )

    def _clear_all_placements(self):
        if not self.project:
            return
        reply = QMessageBox.question(
            self, "Clear Placements", "Are you sure you want to unplace all components?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for inst in self.project.physical_instances:
                inst.is_placed = False
                inst.x = 0.0
                inst.y = 0.0
                inst.din_rail_id = None
            self._refresh_palette()
            self._sync_3d_scene()
            self._update_status_bar()

    def _on_palette_item_clicked(self, item: QListWidgetItem):
        inst_id = item.data(Qt.UserRole)
        inst = next((i for i in self.project.physical_instances if i.id == inst_id), None)
        if not inst:
            return

        if not inst.is_placed:
            # Place onto mounting plate in a free area
            inst.is_placed = True
            inst.x = 100.0
            inst.y = 300.0
            inst.z = 0.0
            self._refresh_palette()

        self.viewer_3d.select_component(inst_id)
        self.prop_panel.load_instance(inst)
        self._sync_3d_scene()
        self._update_status_bar()

    def _on_property_modified(self, instance_id: str):
        self._sync_3d_scene()
        self._update_status_bar()

    def _on_delete_instance(self, instance_id: str):
        inst = next((i for i in self.project.physical_instances if i.id == instance_id), None)
        if inst:
            inst.is_placed = False
            self.prop_panel.load_instance(None)
            self._refresh_palette()
            self._sync_3d_scene()
            self._update_status_bar()

