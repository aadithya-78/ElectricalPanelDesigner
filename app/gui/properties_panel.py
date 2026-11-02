"""
Right Sidebar: Selected Component Properties Panel.
Spacious enterprise UI with guaranteed minimum heights for all spinboxes,
clean grid spacing, and modern soft blue / white styling.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, 
    QCheckBox, QPushButton, QComboBox, QGroupBox, QGridLayout, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal

from app.models.component import PhysicalInstance, MountingType


class PropertiesPanel(QWidget):
    property_changed = Signal(str) # Emits instance_id when modified
    delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_instance: Optional[PhysicalInstance] = None
        self._updating = False

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        # Header
        title = QLabel("Component Properties")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #111C24;")
        layout.addWidget(title)

        # Basic Info Card
        info_group = QGroupBox("Identification")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(6)
        info_layout.setContentsMargins(14, 20, 14, 14)

        self.lbl_name = QLabel("No component selected")
        self.lbl_name.setStyleSheet("font-weight: 700; color: #111C24; font-size: 13px;")
        self.lbl_name.setWordWrap(True)
        info_layout.addWidget(self.lbl_name)

        self.lbl_mfr = QLabel("Select an item on the plate or palette")
        self.lbl_mfr.setStyleSheet("color: #616365; font-size: 11px;")
        self.lbl_mfr.setWordWrap(True)
        info_layout.addWidget(self.lbl_mfr)
        layout.addWidget(info_group)

        # 3D Coordinates (X, Y, Z)
        pos_group = QGroupBox("Placement Coordinates (mm)")
        pos_layout = QGridLayout(pos_group)
        pos_layout.setVerticalSpacing(12)
        pos_layout.setHorizontalSpacing(10)
        pos_layout.setContentsMargins(14, 20, 14, 14)

        lbl_x = QLabel("X (Left):")
        lbl_x.setStyleSheet("font-weight: 500;")
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(-2000.0, 5000.0)
        self.spin_x.setSingleStep(5.0)
        self.spin_x.setMinimumHeight(38)
        self.spin_x.valueChanged.connect(self._on_pos_changed)
        pos_layout.addWidget(lbl_x, 0, 0)
        pos_layout.addWidget(self.spin_x, 0, 1)

        lbl_y = QLabel("Y (Bottom):")
        lbl_y.setStyleSheet("font-weight: 500;")
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(-2000.0, 5000.0)
        self.spin_y.setSingleStep(5.0)
        self.spin_y.setMinimumHeight(38)
        self.spin_y.valueChanged.connect(self._on_pos_changed)
        pos_layout.addWidget(lbl_y, 1, 0)
        pos_layout.addWidget(self.spin_y, 1, 1)

        lbl_z = QLabel("Z (Elevation):")
        lbl_z.setStyleSheet("font-weight: 500;")
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(-500.0, 2000.0)
        self.spin_z.setSingleStep(5.0)
        self.spin_z.setMinimumHeight(38)
        self.spin_z.valueChanged.connect(self._on_pos_changed)
        pos_layout.addWidget(lbl_z, 2, 0)
        pos_layout.addWidget(self.spin_z, 2, 1)

        pos_layout.setColumnStretch(0, 1)
        pos_layout.setColumnStretch(1, 2)
        layout.addWidget(pos_group)

        # Physical Dimensions
        dim_group = QGroupBox("Dimensions & Rotation (mm)")
        dim_layout = QGridLayout(dim_group)
        dim_layout.setVerticalSpacing(12)
        dim_layout.setHorizontalSpacing(10)
        dim_layout.setContentsMargins(14, 20, 14, 14)

        lbl_w = QLabel("Width (X):")
        lbl_w.setStyleSheet("font-weight: 500;")
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(1.0, 3000.0)
        self.spin_w.setMinimumHeight(38)
        self.spin_w.valueChanged.connect(self._on_dim_changed)
        dim_layout.addWidget(lbl_w, 0, 0)
        dim_layout.addWidget(self.spin_w, 0, 1)

        lbl_h = QLabel("Height (Y):")
        lbl_h.setStyleSheet("font-weight: 500;")
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(1.0, 3000.0)
        self.spin_h.setMinimumHeight(38)
        self.spin_h.valueChanged.connect(self._on_dim_changed)
        dim_layout.addWidget(lbl_h, 1, 0)
        dim_layout.addWidget(self.spin_h, 1, 1)

        lbl_d = QLabel("Depth (Z):")
        lbl_d.setStyleSheet("font-weight: 500;")
        self.spin_d = QDoubleSpinBox()
        self.spin_d.setRange(1.0, 2000.0)
        self.spin_d.setMinimumHeight(38)
        self.spin_d.valueChanged.connect(self._on_dim_changed)
        dim_layout.addWidget(lbl_d, 2, 0)
        dim_layout.addWidget(self.spin_d, 2, 1)

        lbl_rot = QLabel("Orientation:")
        lbl_rot.setStyleSheet("font-weight: 500;")
        self.combo_rot = QComboBox()
        self.combo_rot.addItems(["0° Standard", "90° Rotated"])
        self.combo_rot.setMinimumHeight(38)
        self.combo_rot.currentIndexChanged.connect(self._on_rotation_changed)
        dim_layout.addWidget(lbl_rot, 3, 0)
        dim_layout.addWidget(self.combo_rot, 3, 1)

        dim_layout.setColumnStretch(0, 1)
        dim_layout.setColumnStretch(1, 2)
        layout.addWidget(dim_group)

        # Controls & Snapping
        ctrl_group = QGroupBox("Alignment & Position Locking")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.setSpacing(10)
        ctrl_layout.setContentsMargins(14, 20, 14, 14)
        
        self.chk_locked = QCheckBox("Lock Position on Plate")
        self.chk_locked.stateChanged.connect(self._on_lock_changed)
        ctrl_layout.addWidget(self.chk_locked)

        snap_layout = QHBoxLayout()
        snap_layout.setSpacing(8)
        btn_snap_grid = QPushButton("Snap to 10mm")
        btn_snap_grid.setProperty("class", "secondary")
        btn_snap_grid.setMinimumHeight(36)
        btn_snap_grid.clicked.connect(self._snap_to_grid)
        snap_layout.addWidget(btn_snap_grid)

        btn_snap_rail = QPushButton("Snap to Rail")
        btn_snap_rail.setProperty("class", "secondary")
        btn_snap_rail.setMinimumHeight(36)
        btn_snap_rail.clicked.connect(self._snap_to_rail)
        snap_layout.addWidget(btn_snap_rail)
        ctrl_layout.addLayout(snap_layout)

        layout.addWidget(ctrl_group)

        # Delete Action Button
        self.btn_del = QPushButton("Remove from Mounting Plate")
        self.btn_del.setProperty("class", "danger")
        self.btn_del.setMinimumHeight(38)
        self.btn_del.clicked.connect(self._on_delete)
        layout.addWidget(self.btn_del)

        layout.addStretch()

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        self.setEnabled(False)

    def load_instance(self, instance: Optional[PhysicalInstance]):
        self.current_instance = instance
        if not instance:
            self.lbl_name.setText("No component selected")
            self.lbl_mfr.setText("Select an item on the plate or palette")
            self.setEnabled(False)
            return

        self._updating = True
        self.setEnabled(True)

        self.lbl_name.setText(instance.name)
        self.lbl_mfr.setText(f"{instance.manufacturer}  •  {instance.part_number or 'Part No. Unverified'} ({instance.category})")

        self.spin_x.setValue(instance.x)
        self.spin_y.setValue(instance.y)
        self.spin_z.setValue(instance.z)

        self.spin_w.setValue(instance.width)
        self.spin_h.setValue(instance.height)
        self.spin_d.setValue(instance.depth)

        self.combo_rot.setCurrentIndex(1 if instance.rotation == 90 else 0)
        self.chk_locked.setChecked(instance.is_locked)

        self._updating = False

    def _on_pos_changed(self):
        if self._updating or not self.current_instance:
            return
        self.current_instance.x = self.spin_x.value()
        self.current_instance.y = self.spin_y.value()
        self.current_instance.z = self.spin_z.value()
        self.property_changed.emit(self.current_instance.id)

    def _on_dim_changed(self):
        if self._updating or not self.current_instance:
            return
        self.current_instance.width = self.spin_w.value()
        self.current_instance.height = self.spin_h.value()
        self.current_instance.depth = self.spin_d.value()
        self.property_changed.emit(self.current_instance.id)

    def _on_rotation_changed(self, idx: int):
        if self._updating or not self.current_instance:
            return
        self.current_instance.rotation = 90.0 if idx == 1 else 0.0
        self.property_changed.emit(self.current_instance.id)

    def _on_lock_changed(self, state):
        if self._updating or not self.current_instance:
            return
        self.current_instance.is_locked = bool(state)

    def _snap_to_grid(self):
        if not self.current_instance:
            return
        grid_step = 10.0
        self.spin_x.setValue(round(self.current_instance.x / grid_step) * grid_step)
        self.spin_y.setValue(round(self.current_instance.y / grid_step) * grid_step)

    def _snap_to_rail(self):
        if not self.current_instance:
            return
        self.spin_z.setValue(7.5) # Standard 35x7.5mm rail surface

    def _on_delete(self):
        if self.current_instance:
            self.delete_requested.emit(self.current_instance.id)
