"""
Step 4 GUI: Dimensionally Accurate 2D Front-View Mounting Plate Layout Editor.
Features:
- Dual Placement Modes: Automatic Placement (1-click engineering layout) and Manual Placement (drag-and-drop / double-click)
- Top-left origin (0,0) with X increasing right, Y increasing down (in mm)
- KiCad-style component double-click properties dialog
- Interactive left sidebar with search/filter, physical dimensions, placed/remaining counts
- Strict boundary enforcement with position rollback and red highlights
- Strict collision detection with position rollback (DIN-mounted on DIN rail allowed)
- Rulers, grid lines, and physical dimension indicators
- Fit to Panel button and dynamic panel resizing with non-destructive validation
"""
from typing import List, Dict, Any, Optional, Tuple, Union
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QSplitter, QFrame, QMessageBox, 
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsItem, QGraphicsLineItem, QComboBox, QCheckBox, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox, QTabWidget, QMenu
)
from PySide6.QtGui import QBrush, QPen, QColor, QFont, QPainter, QTransform, QDrag, QKeySequence
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer, QMimeData

from app.models.project import ProjectData
from app.models.component import PhysicalInstance, MountingType
from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.geometry.collision_detector import CollisionDetector
from app.geometry.auto_layout import AutoLayoutEngine


class KiCadPropertiesDialog(QDialog):
    """
    Unified properties editor dialog for 2D workspace objects:
    Supports PhysicalInstance (BOM components), DINRail, and WiringDuct.
    Allows editing Reference/Name, Dimensions (X, Y, Z in mm),
    Position (X, Y in mm), Rotation (0°, 90°, 180°, 270°), and Position Lock.
    Supports deletion / removal from the workspace.
    """
    def __init__(self, target_item: Union[PhysicalInstance, DINRail, WiringDuct], editor, parent=None):
        super().__init__(parent)
        self.item = target_item
        self.editor = editor
        
        self.is_instance = isinstance(target_item, PhysicalInstance)
        self.is_rail = isinstance(target_item, DINRail)
        self.is_duct = isinstance(target_item, WiringDuct)

        name = self.item.name
        self.setWindowTitle(f"Properties — {name}")
        self.setMinimumWidth(460)
        self.setStyleSheet("""
            QDialog {
                background-color: #111C33;
                color: #FFFFFF;
            }
            QLabel {
                color: #F1F5F9;
                font-weight: 600;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        type_header = "BOM Component Footprint" if self.is_instance else ("Workspace Object: DIN Rail" if self.is_rail else "Workspace Object: Wiring Duct")
        title_lbl = QLabel(f"{type_header}: {name}")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #38BDF8;")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        self.name_edit = QLineEdit(name)
        form.addRow("Reference / Name:", self.name_edit)

        if self.is_instance:
            self.mfr_lbl = QLabel(f"{self.item.manufacturer}  |  {self.item.part_number or 'Standard'}")
            self.mfr_lbl.setStyleSheet("color: #94A3B8; font-weight: 500;")
            form.addRow("Part Details:", self.mfr_lbl)
        elif self.is_rail:
            self.type_lbl = QLabel("Standard DIN EN 60715 35mm Mounting Rail")
            self.type_lbl.setStyleSheet("color: #94A3B8; font-weight: 500;")
            form.addRow("Object Type:", self.type_lbl)
        else:
            self.type_lbl = QLabel("Slotted PVC Control Wiring Trunking / Duct")
            self.type_lbl.setStyleSheet("color: #94A3B8; font-weight: 500;")
            form.addRow("Object Type:", self.type_lbl)

        # Coordinates
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(0.0, 5000.0)
        self.spin_x.setValue(self.item.x)
        self.spin_x.setSuffix(" mm")
        self.spin_x.setMinimumHeight(38)
        form.addRow("Position X (Left):", self.spin_x)

        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(0.0, 5000.0)
        self.spin_y.setValue(self.item.y)
        self.spin_y.setSuffix(" mm")
        self.spin_y.setMinimumHeight(38)
        form.addRow("Position Y (Top):", self.spin_y)

        # Orientation / Rotation
        self.combo_rot = QComboBox()
        self.combo_rot.addItems(["0°", "90°", "180°", "270°"])
        curr_rot = str(int(getattr(self.item, "rotation", 0.0))) + "°"
        idx = self.combo_rot.findText(curr_rot)
        if idx >= 0:
            self.combo_rot.setCurrentIndex(idx)
        self.combo_rot.setMinimumHeight(38)
        form.addRow("Orientation / Rotation:", self.combo_rot)

        # Dimensions: Width (X), Height (Y), Depth (Z)
        if self.is_instance:
            val_w = self.item.width
            val_h = self.item.height
            val_d = self.item.depth
            label_w = "Width X (mm):"
            label_h = "Height Y (mm):"
            label_d = "Depth Z (mm):"
        elif self.is_rail:
            val_w = self.item.length
            val_h = self.item.height
            val_d = self.item.depth
            label_w = "Rail Length (Span X):"
            label_h = "Profile Height Y (mm):"
            label_d = "Profile Depth Z (mm):"
        else: # duct
            val_w = self.item.length
            val_h = self.item.width
            val_d = self.item.height
            label_w = "Duct Length (Span):"
            label_h = "Duct Width (mm):"
            label_d = "Duct Depth/Height (mm):"

        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(1.0, 4000.0)
        self.spin_w.setValue(val_w)
        self.spin_w.setSuffix(" mm")
        self.spin_w.setMinimumHeight(38)
        form.addRow(label_w, self.spin_w)

        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(1.0, 4000.0)
        self.spin_h.setValue(val_h)
        self.spin_h.setSuffix(" mm")
        self.spin_h.setMinimumHeight(38)
        form.addRow(label_h, self.spin_h)

        self.spin_d = QDoubleSpinBox()
        self.spin_d.setRange(1.0, 2000.0)
        self.spin_d.setValue(val_d)
        self.spin_d.setSuffix(" mm")
        self.spin_d.setMinimumHeight(38)
        form.addRow(label_d, self.spin_d)

        self.chk_lock = QCheckBox("Lock Position (prevent mouse dragging)")
        self.chk_lock.setChecked(getattr(self.item, "is_locked", False))
        form.addRow("", self.chk_lock)

        if self.is_instance:
            self.combo_surface = QComboBox()
            self.combo_surface.addItems(["Mounting Plate (Z View)", "Outer Door (Z+1 View)"])
            curr_surf = getattr(self.item, "surface", "Z").upper()
            self.combo_surface.setCurrentIndex(1 if curr_surf == "Z+1" else 0)
            self.combo_surface.setMinimumHeight(38)
            form.addRow("Surface Layer:", self.combo_surface)

        layout.addLayout(form)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        del_label = "Remove from Panel" if self.is_instance else "Delete Workspace Object"
        btn_delete = QPushButton(del_label)
        btn_delete.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                color: #FFFFFF;
                border: 1px solid #DC2626;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: 600;
                min-height: 38px;
            }
            QPushButton:hover {
                background: #DC2626;
            }
        """)
        btn_delete.clicked.connect(self._delete_or_remove)
        btn_box.addWidget(btn_delete)

        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.setMinimumHeight(38)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_ok = QPushButton("Apply Changes")
        btn_ok.setMinimumHeight(38)
        btn_ok.clicked.connect(self._validate_and_apply)
        btn_box.addWidget(btn_ok)

        layout.addLayout(btn_box)

    def _delete_or_remove(self):
        if self.is_instance:
            self.editor.unplace_instance(self.item)
        elif self.is_rail:
            self.editor.delete_din_rail(self.item)
        elif self.is_duct:
            self.editor.delete_wiring_duct(self.item)
        self.accept()

    def _validate_and_apply(self):
        new_x = self.spin_x.value()
        new_y = self.spin_y.value()
        new_rot = float(self.combo_rot.currentText().replace("°", ""))
        new_w = self.spin_w.value()
        new_h = self.spin_h.value()
        new_d = self.spin_d.value()

        enc = self.editor.project.enclosure
        plate_w = enc.mounting_plate_width
        plate_h = enc.mounting_plate_height

        if self.is_instance:
            orig_x, orig_y, orig_rot = self.item.x, self.item.y, self.item.rotation
            orig_w, orig_h, orig_d = self.item.width, self.item.height, self.item.depth
            orig_surf = getattr(self.item, "surface", "Z")

            target_surf = "Z+1" if self.combo_surface.currentIndex() == 1 else "Z"
            self.item.surface = target_surf
            if target_surf == "Z+1":
                self.item.mounting_type = MountingType.DOOR
                bound_w = enc.width
                bound_h = enc.height
            else:
                if self.item.mounting_type == MountingType.DOOR:
                    self.item.mounting_type = MountingType.PLATE
                bound_w = plate_w
                bound_h = plate_h

            self.item.x = new_x
            self.item.y = new_y
            self.item.rotation = new_rot
            self.item.width = new_w
            self.item.height = new_h
            self.item.depth = new_d

            is_valid, reason = CollisionDetector.validate_position(
                self.item,
                self.editor.project.physical_instances,
                bound_w,
                bound_h
            )

            if not is_valid:
                self.item.x, self.item.y, self.item.rotation = orig_x, orig_y, orig_rot
                self.item.width, self.item.height, self.item.depth = orig_w, orig_h, orig_d
                self.item.surface = orig_surf
                QMessageBox.warning(self, "Invalid Placement", f"Cannot apply changes:\n{reason}")
                return

            self.item.name = self.name_edit.text().strip()
            self.item.is_locked = self.chk_lock.isChecked()

            # If surface changed, ensure active view matches or editor scene is rebuilt
            if orig_surf != target_surf:
                self.editor.set_active_surface(target_surf)

            self.accept()

        elif self.is_rail:
            eff_w = new_h if int(new_rot) in (90, 270) else new_w
            eff_h = new_w if int(new_rot) in (90, 270) else new_h

            if new_x < 0 or new_x + eff_w > plate_w or new_y < 0 or new_y + eff_h > plate_h:
                QMessageBox.warning(
                    self,
                    "Boundary Violation",
                    f"DIN rail extends beyond mounting plate boundaries ({int(plate_w)}×{int(plate_h)} mm)."
                )
                return

            self.item.name = self.name_edit.text().strip()
            self.item.x = new_x
            self.item.y = new_y
            self.item.rotation = new_rot
            self.item.length = new_w
            self.item.height = new_h
            self.item.depth = new_d
            self.item.orientation = "VERTICAL" if int(new_rot) in (90, 270) else "HORIZONTAL"
            self.item.is_locked = self.chk_lock.isChecked()
            self.accept()

        else: # wiring duct
            eff_w = new_h if int(new_rot) in (90, 270) else new_w
            eff_h = new_w if int(new_rot) in (90, 270) else new_h

            if new_x < 0 or new_x + eff_w > plate_w or new_y < 0 or new_y + eff_h > plate_h:
                QMessageBox.warning(
                    self,
                    "Boundary Violation",
                    f"Wiring duct extends beyond mounting plate boundaries ({int(plate_w)}×{int(plate_h)} mm)."
                )
                return

            self.item.name = self.name_edit.text().strip()
            self.item.x = new_x
            self.item.y = new_y
            self.item.rotation = new_rot
            self.item.length = new_w
            self.item.width = new_h
            self.item.height = new_d
            self.item.orientation = "VERTICAL" if int(new_rot) in (90, 270) else "HORIZONTAL"
            self.item.is_locked = self.chk_lock.isChecked()
            self.accept()


class DINRail2DItem(QGraphicsRectItem):
    """
    Interactive DIN rail on 2D mounting plate.
    Supports mouse dragging, selection highlighting, boundary enforcement,
    and double-click properties editing.
    """
    def __init__(self, rail: DINRail, editor, parent=None):
        eff_w = rail.height if int(rail.rotation) in (90, 270) or rail.orientation == "VERTICAL" else rail.length
        eff_h = rail.length if int(rail.rotation) in (90, 270) or rail.orientation == "VERTICAL" else rail.height
        super().__init__(0, 0, eff_w, eff_h, parent)
        self.rail = rail
        self.editor = editor
        self.last_valid_x = rail.x
        self.last_valid_y = rail.y

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(3)
        self.setPos(rail.x, rail.y)
        self._update_appearance()

    def _update_appearance(self):
        eff_w = self.rail.height if int(self.rail.rotation) in (90, 270) or self.rail.orientation == "VERTICAL" else self.rail.length
        eff_h = self.rail.length if int(self.rail.rotation) in (90, 270) or self.rail.orientation == "VERTICAL" else self.rail.height
        self.setRect(0, 0, eff_w, eff_h)

        if self.isSelected():
            self.setBrush(QBrush(QColor("#E2E8F0")))
            self.setPen(QPen(QColor("#38BDF8"), 2.5, Qt.SolidLine))
        else:
            self.setBrush(QBrush(QColor("#CBD5E1")))
            self.setPen(QPen(QColor("#64748B"), 1.5, Qt.SolidLine))

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.rect()
        painter.setPen(QPen(QColor("#94A3B8"), 1, Qt.DashLine))
        is_vert = int(self.rail.rotation) in (90, 270) or self.rail.orientation == "VERTICAL"
        if is_vert:
            painter.drawLine(rect.width() / 2.0, 0, rect.width() / 2.0, rect.height())
        else:
            painter.drawLine(0, rect.height() / 2.0, rect.width(), rect.height() / 2.0)

        painter.setPen(QColor("#1E293B"))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        text = f"{self.rail.name} ({int(self.rail.length)}mm)"
        painter.drawText(rect.adjusted(8, 2, -8, -2), Qt.AlignVCenter | Qt.AlignLeft, text)

    def mousePressEvent(self, event):
        self._pre_drag_snapshot = self.editor.undo_manager.capture_snapshot() if (self.editor and getattr(self.editor, 'undo_manager', None)) else None
        self._pre_drag_pos = (self.pos().x(), self.pos().y())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Open Properties Dialog on double click."""
        pre_snap = self.editor.undo_manager.capture_snapshot() if (self.editor and getattr(self.editor, 'undo_manager', None)) else None
        dlg = KiCadPropertiesDialog(self.rail, self.editor, parent=self.editor)
        if dlg.exec():
            if self.rail in self.editor.project.din_rails:
                if self.editor and getattr(self.editor, 'undo_manager', None) and pre_snap:
                    self.editor.undo_manager.push_state(pre_snap)
                    self.editor._update_undo_redo_ui()
                self.setPos(self.rail.x, self.rail.y)
                self.last_valid_x = self.rail.x
                self.last_valid_y = self.rail.y
                self._update_appearance()
                self.editor._revalidate_and_highlight()
                self.editor._update_status_bar()
        event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.rail.is_locked:
            self.setPos(self.last_valid_x, self.last_valid_y)
            return

        pos = self.pos()
        target_x = pos.x()
        target_y = pos.y()

        if self.editor.grid_snap_enabled:
            step = self.editor.grid_step
            target_x = round(target_x / step) * step
            target_y = round(target_y / step) * step

        plate_w = self.editor.project.enclosure.mounting_plate_width
        plate_h = self.editor.project.enclosure.mounting_plate_height
        eff_w = self.rail.height if int(self.rail.rotation) in (90, 270) or self.rail.orientation == "VERTICAL" else self.rail.length
        eff_h = self.rail.length if int(self.rail.rotation) in (90, 270) or self.rail.orientation == "VERTICAL" else self.rail.height

        if target_x < 0 or target_x + eff_w > plate_w or target_y < 0 or target_y + eff_h > plate_h:
            self.setPos(self.last_valid_x, self.last_valid_y)
            self.editor.show_status_message(f"DIN rail placed outside mounting plate ({int(plate_w)}×{int(plate_h)} mm). Position reverted.", is_warning=True)
            return

        self.rail.x = target_x
        self.rail.y = target_y
        self.last_valid_x = target_x
        self.last_valid_y = target_y
        self.setPos(target_x, target_y)
        self.editor.show_status_message(f"Positioned {self.rail.name} at ({int(target_x)}, {int(target_y)}) mm.")

        if (target_x, target_y) != getattr(self, "_pre_drag_pos", (None, None)):
            if self.editor and getattr(self.editor, 'undo_manager', None) and getattr(self, "_pre_drag_snapshot", None):
                self.editor.undo_manager.push_state(self._pre_drag_snapshot)
                self.editor._update_undo_redo_ui()


class WireDuct2DItem(QGraphicsRectItem):
    """
    Interactive slotted wiring duct on 2D mounting plate.
    Supports mouse dragging, selection highlighting, boundary enforcement,
    and double-click properties editing.
    """
    def __init__(self, duct: WiringDuct, editor, parent=None):
        eff_w = duct.width if duct.orientation == "VERTICAL" or int(duct.rotation) in (90, 270) else duct.length
        eff_h = duct.length if duct.orientation == "VERTICAL" or int(duct.rotation) in (90, 270) else duct.height
        super().__init__(0, 0, eff_w, eff_h, parent)
        self.duct = duct
        self.editor = editor
        self.last_valid_x = duct.x
        self.last_valid_y = duct.y

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(4)
        self.setPos(duct.x, duct.y)
        self._update_appearance()

    def _update_appearance(self):
        eff_w = self.duct.width if self.duct.orientation == "VERTICAL" or int(self.duct.rotation) in (90, 270) else self.duct.length
        eff_h = self.duct.length if self.duct.orientation == "VERTICAL" or int(self.duct.rotation) in (90, 270) else self.duct.height
        self.setRect(0, 0, eff_w, eff_h)

        if self.isSelected():
            self.setBrush(QBrush(QColor("#475569")))
            self.setPen(QPen(QColor("#38BDF8"), 2.5, Qt.SolidLine))
        else:
            self.setBrush(QBrush(QColor("#334155")))
            self.setPen(QPen(QColor("#1E293B"), 1.5, Qt.SolidLine))

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.rect()
        painter.setPen(QPen(QColor("#64748B"), 1))
        is_vert = self.duct.orientation == "VERTICAL" or int(self.duct.rotation) in (90, 270)
        if is_vert:
            for y in range(0, int(rect.height()), 16):
                painter.drawLine(0, y, 6, y)
                painter.drawLine(rect.width() - 6, y, rect.width(), y)
        else:
            for x in range(0, int(rect.width()), 16):
                painter.drawLine(x, 0, x, 6)
                painter.drawLine(x, rect.height() - 6, x, rect.height())

        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(rect.adjusted(6, 2, -6, -2), Qt.AlignVCenter | Qt.AlignLeft, f"{self.duct.name}")

    def mousePressEvent(self, event):
        self._pre_drag_snapshot = self.editor.undo_manager.capture_snapshot() if (self.editor and getattr(self.editor, 'undo_manager', None)) else None
        self._pre_drag_pos = (self.pos().x(), self.pos().y())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Open Properties Dialog on double click."""
        pre_snap = self.editor.undo_manager.capture_snapshot() if (self.editor and getattr(self.editor, 'undo_manager', None)) else None
        dlg = KiCadPropertiesDialog(self.duct, self.editor, parent=self.editor)
        if dlg.exec():
            if self.duct in self.editor.project.wiring_ducts:
                if self.editor and getattr(self.editor, 'undo_manager', None) and pre_snap:
                    self.editor.undo_manager.push_state(pre_snap)
                    self.editor._update_undo_redo_ui()
                self.setPos(self.duct.x, self.duct.y)
                self.last_valid_x = self.duct.x
                self.last_valid_y = self.duct.y
                self._update_appearance()
                self.editor._revalidate_and_highlight()
                self.editor._update_status_bar()
        event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.duct.is_locked:
            self.setPos(self.last_valid_x, self.last_valid_y)
            return

        pos = self.pos()
        target_x = pos.x()
        target_y = pos.y()

        if self.editor.grid_snap_enabled:
            step = self.editor.grid_step
            target_x = round(target_x / step) * step
            target_y = round(target_y / step) * step

        plate_w = self.editor.project.enclosure.mounting_plate_width
        plate_h = self.editor.project.enclosure.mounting_plate_height
        eff_w = self.duct.width if self.duct.orientation == "VERTICAL" or int(self.duct.rotation) in (90, 270) else self.duct.length
        eff_h = self.duct.length if self.duct.orientation == "VERTICAL" or int(self.duct.rotation) in (90, 270) else self.duct.height

        if target_x < 0 or target_x + eff_w > plate_w or target_y < 0 or target_y + eff_h > plate_h:
            self.setPos(self.last_valid_x, self.last_valid_y)
            self.editor.show_status_message(f"Wiring duct placed outside mounting plate ({int(plate_w)}×{int(plate_h)} mm). Position reverted.", is_warning=True)
            return

        self.duct.x = target_x
        self.duct.y = target_y
        self.last_valid_x = target_x
        self.last_valid_y = target_y
        self.setPos(target_x, target_y)
        self.editor.show_status_message(f"Positioned {self.duct.name} at ({int(target_x)}, {int(target_y)}) mm.")

        if (target_x, target_y) != getattr(self, "_pre_drag_pos", (None, None)):
            if self.editor and getattr(self.editor, 'undo_manager', None) and getattr(self, "_pre_drag_snapshot", None):
                self.editor.undo_manager.push_state(self._pre_drag_snapshot)
                self.editor._update_undo_redo_ui()


class Component2DItem(QGraphicsRectItem):
    """
    Interactive 2D footprint item on the mounting plate.
    Handles mouse dragging with strict boundary checks, collision detection,
    and automatic position rollback on violation.
    """
    def __init__(self, instance: PhysicalInstance, editor, parent=None):
        eff_w = instance.height if int(instance.rotation) in (90, 270) else instance.width
        eff_h = instance.width if int(instance.rotation) in (90, 270) else instance.height
        
        super().__init__(0, 0, eff_w, eff_h, parent)
        self.instance = instance
        self.editor = editor

        self.last_valid_x = instance.x
        self.last_valid_y = instance.y

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        self.setPos(instance.x, instance.y)
        self.is_flashing_red = False
        self._update_appearance()

    def _update_appearance(self, is_colliding: bool = False):
        eff_w = self.instance.height if int(self.instance.rotation) in (90, 270) else self.instance.width
        eff_h = self.instance.width if int(self.instance.rotation) in (90, 270) else self.instance.height
        self.setRect(0, 0, eff_w, eff_h)

        base_color = QColor(self.instance.color)

        if self.is_flashing_red or is_colliding:
            brush = QBrush(QColor("#7F1D1D")) # Deep red fill
            pen = QPen(QColor("#EF4444"), 2.5, Qt.DashLine) # Bright red border
        elif self.isSelected():
            brush = QBrush(base_color.lighter(130))
            pen = QPen(QColor("#38BDF8"), 3, Qt.SolidLine) # Cyan border
        else:
            brush = QBrush(base_color)
            pen = QPen(QColor("#0F172A"), 1.5, Qt.SolidLine)

        self.setBrush(brush)
        self.setPen(pen)

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        
        rect = self.rect()
        if rect.width() >= 24 and rect.height() >= 16:
            painter.setPen(QColor("#FFFFFF"))
            font = QFont("Segoe UI", 8, QFont.Bold)
            painter.setFont(font)

            name_text = self.instance.name
            if len(name_text) > 18 and rect.width() < 120:
                name_text = name_text[:16] + ".."
            dim_text = f"{int(self.instance.width)}×{int(self.instance.height)}mm"

            painter.drawText(
                rect.adjusted(4, 3, -4, -3),
                Qt.AlignTop | Qt.AlignLeft,
                f"{name_text}\n{dim_text}"
            )

    def mousePressEvent(self, event):
        self._pre_drag_snapshot = self.editor.undo_manager.capture_snapshot() if (self.editor and getattr(self.editor, 'undo_manager', None)) else None
        self._pre_drag_pos = (self.pos().x(), self.pos().y())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """KiCad-style: double-click opens Properties Dialog."""
        pre_snap = self.editor.undo_manager.capture_snapshot() if (self.editor and getattr(self.editor, 'undo_manager', None)) else None
        dlg = KiCadPropertiesDialog(self.instance, self.editor)
        if dlg.exec():
            if self.instance in self.editor.project.physical_instances:
                if self.editor and getattr(self.editor, 'undo_manager', None) and pre_snap:
                    self.editor.undo_manager.push_state(pre_snap)
                    self.editor._update_undo_redo_ui()
                self.setPos(self.instance.x, self.instance.y)
                self.last_valid_x = self.instance.x
                self.last_valid_y = self.instance.y
                self._update_appearance()
                self.editor.on_item_updated(self.instance)
        event.accept()

    def contextMenuEvent(self, event):
        """Right-click context menu: quick surface transfer and object commands."""
        menu = QMenu()
        cur_surf = getattr(self.instance, "surface", "Z").upper()
        if cur_surf == "Z+1":
            act_transfer = menu.addAction("Move to Mounting Plate (Z View)")
            act_transfer.triggered.connect(lambda: self.editor.transfer_instance_surface(self.instance, "Z"))
        else:
            act_transfer = menu.addAction("Move to Outer Door (Z+1 View)")
            act_transfer.triggered.connect(lambda: self.editor.transfer_instance_surface(self.instance, "Z+1"))

        menu.addSeparator()
        act_props = menu.addAction("Properties...")
        act_props.triggered.connect(self._open_properties)

        act_unplace = menu.addAction("Remove from Panel")
        act_unplace.triggered.connect(lambda: self.editor.unplace_instance(self.instance))

        menu.exec(event.screenPos())
        event.accept()

    def _open_properties(self):
        pre_snap = self.editor.undo_manager.capture_snapshot() if (self.editor and getattr(self.editor, 'undo_manager', None)) else None
        dlg = KiCadPropertiesDialog(self.instance, self.editor)
        if dlg.exec():
            if self.instance in self.editor.project.physical_instances:
                if self.editor and getattr(self.editor, 'undo_manager', None) and pre_snap:
                    self.editor.undo_manager.push_state(pre_snap)
                    self.editor._update_undo_redo_ui()
                self.setPos(self.instance.x, self.instance.y)
                self.last_valid_x = self.instance.x
                self.last_valid_y = self.instance.y
                self._update_appearance()
                self.editor.on_item_updated(self.instance)

    def mouseReleaseEvent(self, event):
        """Validate on mouse release: enforce strict boundary and collision rollback."""
        super().mouseReleaseEvent(event)

        if self.instance.is_locked:
            self.setPos(self.last_valid_x, self.last_valid_y)
            return

        pos = self.pos()
        target_x = pos.x()
        target_y = pos.y()

        # Grid snap if enabled
        if self.editor.grid_snap_enabled:
            step = self.editor.grid_step
            target_x = round(target_x / step) * step
            target_y = round(target_y / step) * step

        # Snap to DIN rail: DIN rail must ALWAYS be in the middle (component centered vertically)
        if getattr(self.instance, "surface", "Z") != "Z+1":
            eff_h = self.instance.effective_height
            eff_w = self.instance.effective_width
            comp_center_y = target_y + (eff_h / 2.0)
            comp_center_x = target_x + (eff_w / 2.0)

            for other in getattr(self.editor.project, "din_rails", []):
                is_horiz = other.orientation.upper() == "HORIZONTAL"
                if is_horiz:
                    rail_h = getattr(other, "effective_height", getattr(other, "height", 35.0))
                    rail_center_y = other.y + (rail_h / 2.0)
                    rail_x1 = other.x - 25.0
                    rail_x2 = other.x + getattr(other, "effective_width", getattr(other, "length", 600.0)) + 25.0

                    if abs(comp_center_y - rail_center_y) < 35.0 and (rail_x1 <= comp_center_x <= rail_x2):
                        # Center component vertically on the DIN rail (rail in the middle)
                        target_y = rail_center_y - (eff_h / 2.0)
                        self.instance.din_rail_id = other.id
                        break
                else:
                    rail_w = getattr(other, "effective_width", getattr(other, "height", 35.0))
                    rail_center_x = other.x + (rail_w / 2.0)
                    rail_y1 = other.y - 25.0
                    rail_y2 = other.y + getattr(other, "effective_height", getattr(other, "length", 600.0)) + 25.0

                    if abs(comp_center_x - rail_center_x) < 35.0 and (rail_y1 <= comp_center_y <= rail_y2):
                        target_x = rail_center_x - (eff_w / 2.0)
                        self.instance.din_rail_id = other.id
                        break

        # Always ensure surface matches the active 2D editor surface
        self.instance.surface = self.editor.active_surface
        if self.editor.active_surface == "Z+1":
            self.instance.mounting_type = MountingType.DOOR

        # Candidate test
        orig_x = self.instance.x
        orig_y = self.instance.y
        self.instance.x = target_x
        self.instance.y = target_y

        enc = self.editor.project.enclosure
        is_door = (self.editor.active_surface == "Z+1")
        bound_w = enc.width if is_door else enc.mounting_plate_width
        bound_h = enc.height if is_door else enc.mounting_plate_height

        # Collect any other items currently selected and moved in this drag
        selected = self.scene().selectedItems() if self.scene() else []
        saved_positions = {}
        if len(selected) > 1:
            for it in selected:
                if it is not self and hasattr(it, "instance"):
                    saved_positions[it.instance.id] = (it.instance.x, it.instance.y)
                    it.instance.x = it.pos().x()
                    it.instance.y = it.pos().y()

        is_valid, reason = CollisionDetector.validate_position(
            self.instance,
            self.editor.project.physical_instances,
            bound_w,
            bound_h
        )

        if not is_valid:
            # Rollback to last valid position
            self.instance.x = self.last_valid_x
            self.instance.y = self.last_valid_y
            self.setPos(self.last_valid_x, self.last_valid_y)
            if len(selected) > 1:
                for it in selected:
                    if it is not self and hasattr(it, "instance") and it.instance.id in saved_positions:
                        old_x, old_y = saved_positions[it.instance.id]
                        it.instance.x = old_x
                        it.instance.y = old_y
                        it.setPos(it.last_valid_x, it.last_valid_y)
            self._flash_red_and_notify(reason)
        else:
            # Valid: commit
            self.setPos(target_x, target_y)
            self.last_valid_x = target_x
            self.last_valid_y = target_y

            # Sync any other co-selected items moved during multi-drag
            if len(selected) > 1:
                for it in selected:
                    if it is not self:
                        it_pos = it.pos()
                        if hasattr(it, "last_valid_x"):
                            it.last_valid_x = it_pos.x()
                            it.last_valid_y = it_pos.y()
                        if hasattr(it, "instance"):
                            it.instance.x = it_pos.x()
                            it.instance.y = it_pos.y()
                        elif hasattr(it, "rail"):
                            it.rail.x = it_pos.x()
                            it.rail.y = it_pos.y()
                        elif hasattr(it, "duct"):
                            it.duct.x = it_pos.x()
                            it.duct.y = it_pos.y()

            self.editor.on_item_updated(self.instance)
            if (target_x, target_y) != getattr(self, "_pre_drag_pos", (None, None)):
                if self.editor and getattr(self.editor, 'undo_manager', None) and getattr(self, "_pre_drag_snapshot", None):
                    self.editor.undo_manager.push_state(self._pre_drag_snapshot)
                    self.editor._update_undo_redo_ui()

    def _flash_red_and_notify(self, message: str):
        self.is_flashing_red = True
        self._update_appearance()
        self.editor.show_status_message(message, is_warning=True)

        def reset_color():
            self.is_flashing_red = False
            self._update_appearance()

        QTimer.singleShot(900, reset_color)


class Panel2DView(QGraphicsView):
    """
    QGraphicsView with smooth wheel zooming, drag-and-drop support, middle-click panning,
    rubber band box dragging for selecting all enclosed items, and Delete key handling.
    """
    def __init__(self, scene, editor, parent=None):
        super().__init__(scene, parent)
        self.editor = editor
        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self._pan_start = None

    def mousePressEvent(self, event):
        if self.editor and getattr(self.editor, "measure_mode_active", False):
            if event.button() == Qt.LeftButton:
                scene_pos = self.mapToScene(event.pos())
                self.editor.handle_measure_click(scene_pos)
                event.accept()
                return
            elif event.button() == Qt.RightButton:
                self.editor.btn_measure.setChecked(False)
                event.accept()
                return

        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.editor and getattr(self.editor, "measure_mode_active", False):
            scene_pos = self.mapToScene(event.pos())
            self.editor.update_measure_hover(scene_pos)
            event.accept()
            return

        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.editor and getattr(self.editor, "measure_mode_active", False):
            event.accept()
            return

        if self._pan_start is not None:
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self.editor:
            self.editor._apply_selection_filter()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_M and not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            if self.editor and hasattr(self.editor, "btn_measure"):
                self.editor.btn_measure.toggle()
                event.accept()
                return
        elif event.key() == Qt.Key_Escape:
            if self.editor and getattr(self.editor, "measure_mode_active", False):
                self.editor.btn_measure.setChecked(False)
                event.accept()
                return
        if event.matches(QKeySequence.Undo):
            self.editor.undo()
            event.accept()
        elif event.matches(QKeySequence.Redo):
            self.editor.redo()
            event.accept()
        elif event.matches(QKeySequence.SelectAll):
            self.editor.select_all()
            event.accept()
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.editor.delete_selected_items()
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            # Zoom
            factor = 1.15 if event.angleDelta().y() > 0 else 0.87
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-component-id") or event.mimeData().hasFormat("application/x-workspace-object"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-component-id") or event.mimeData().hasFormat("application/x-workspace-object"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        if event.mimeData().hasFormat("application/x-component-id"):
            inst_id = event.mimeData().data("application/x-component-id").data().decode("utf-8")
            self.editor.place_instance_at(inst_id, scene_pos.x(), scene_pos.y())
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-workspace-object"):
            obj_type = event.mimeData().data("application/x-workspace-object").data().decode("utf-8")
            self.editor.add_workspace_object(obj_type, scene_pos.x(), scene_pos.y())
            event.acceptProposedAction()
        else:
            event.ignore()


class ComponentPaletteList(QListWidget):
    """Sidebar palette list supporting drag-and-drop of component instances."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if item:
                inst_id = item.data(Qt.UserRole)
                if inst_id:
                    drag = QDrag(self)
                    mime = QMimeData()
                    mime.setData("application/x-component-id", inst_id.encode("utf-8"))
                    drag.setMimeData(mime)
                    drag.exec(Qt.CopyAction)
                    return
        super().mousePressEvent(event)


class WorkspaceObjectPaletteList(QListWidget):
    """Sidebar palette list supporting drag-and-drop of workspace objects (DIN rail & ducts)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if item:
                obj_type = item.data(Qt.UserRole)
                if obj_type:
                    drag = QDrag(self)
                    mime = QMimeData()
                    mime.setData("application/x-workspace-object", obj_type.encode("utf-8"))
                    drag.setMimeData(mime)
                    drag.exec(Qt.CopyAction)
                    return
        super().mousePressEvent(event)


class PanelResizeDialog(QDialog):
    """Dialog to adjust panel dimensions directly from the 2D workspace."""
    def __init__(self, enclosure: Enclosure, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resize Panel Enclosure")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(12)

        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(400.0, 4000.0)
        self.spin_w.setValue(enclosure.width)
        self.spin_w.setSingleStep(50.0)
        self.spin_w.setSuffix(" mm")
        self.spin_w.setMinimumHeight(38)
        form.addRow("Enclosure Width:", self.spin_w)

        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(400.0, 4000.0)
        self.spin_h.setValue(enclosure.height)
        self.spin_h.setSingleStep(50.0)
        self.spin_h.setSuffix(" mm")
        self.spin_h.setMinimumHeight(38)
        form.addRow("Enclosure Height:", self.spin_h)

        self.spin_d = QDoubleSpinBox()
        self.spin_d.setRange(150.0, 2000.0)
        self.spin_d.setValue(enclosure.depth)
        self.spin_d.setSingleStep(50.0)
        self.spin_d.setSuffix(" mm")
        self.spin_d.setMinimumHeight(38)
        form.addRow("Enclosure Depth:", self.spin_d)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_apply = QPushButton("Apply Dimensions")
        btn_apply.setMinimumHeight(38)
        btn_apply.clicked.connect(self.accept)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.setMinimumHeight(38)
        btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_apply)
        layout.addLayout(btn_box)

    def get_dimensions(self) -> Tuple[float, float, float]:
        return self.spin_w.value(), self.spin_h.value(), self.spin_d.value()


class Panel2DEditor(QWidget):
    generate_3d_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Optional[ProjectData] = None
        self.undo_manager = None
        self.active_surface = "Z" # "Z" for Mounting Plate, "Z+1" for Outer Door
        self.grid_snap_enabled = True
        self.grid_step = 10.0
        self._item_map: Dict[str, Component2DItem] = {}
        self._rail_map: Dict[str, DINRail2DItem] = {}
        self._duct_map: Dict[str, WireDuct2DItem] = {}

        # Measure Tool Attributes
        self.measure_mode_active: bool = False
        self.measure_start_point: Optional[QPointF] = None
        self.measure_start_label: str = ""
        self.measure_items: List[QGraphicsItem] = []
        self.measure_preview_items: List[QGraphicsItem] = []

        self._init_ui()

    def load_project(self, project: ProjectData):
        self.project = project

        # Ensure physical instances exist and reconcile with BOM non-destructively
        if not self.project.physical_instances and self.project.bom:
            self.project.physical_instances = self.project.bom.expand_to_instances()
        else:
            self.project.reconcile_instances_with_bom()

        self._rebuild_scene()
        self._refresh_palette()
        self._update_status_bar()
        self._update_undo_redo_ui()
        QTimer.singleShot(100, self._fit_view)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # 1. Top Toolbar Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        lbl_mode = QLabel("2D Layout Workspace:")
        lbl_mode.setStyleSheet("font-size: 15px; font-weight: 800; color: #111C24;")
        top_bar.addWidget(lbl_mode)

        # Layer Switcher: Mounting Plate (Z) vs Outer Door (Z+1)
        self.btn_view_z = QPushButton("Mounting Plate (Z)")
        self.btn_view_z.setCheckable(True)
        self.btn_view_z.setChecked(True)
        self.btn_view_z.setMinimumHeight(34)
        self.btn_view_z.setToolTip("View & Edit internal Mounting Plate (Z View) — components, DIN rails, wiring ducts")
        self.btn_view_z.clicked.connect(lambda: self.set_active_surface("Z"))
        top_bar.addWidget(self.btn_view_z)

        self.btn_view_z1 = QPushButton("Outer Door (Z+1)")
        self.btn_view_z1.setCheckable(True)
        self.btn_view_z1.setChecked(False)
        self.btn_view_z1.setMinimumHeight(34)
        self.btn_view_z1.setToolTip("View & Edit Enclosure Outer Door (Z+1 View) — HMI, pushbuttons, switches, indicator lamps")
        self.btn_view_z1.clicked.connect(lambda: self.set_active_surface("Z+1"))
        top_bar.addWidget(self.btn_view_z1)

        self._update_surface_buttons_ui()

        top_bar.addSpacing(6)

        # Undo & Redo Buttons
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setProperty("class", "secondary")
        self.btn_undo.setMinimumHeight(34)
        self.btn_undo.setToolTip("Undo last action (Ctrl+Z) - up to 5 steps")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_undo.setEnabled(False)
        top_bar.addWidget(self.btn_undo)

        self.btn_redo = QPushButton("Redo")
        self.btn_redo.setProperty("class", "secondary")
        self.btn_redo.setMinimumHeight(34)
        self.btn_redo.setToolTip("Redo last undone action (Ctrl+Y / Ctrl+Shift+Z) - up to 5 steps")
        self.btn_redo.clicked.connect(self.redo)
        self.btn_redo.setEnabled(False)
        top_bar.addWidget(self.btn_redo)

        top_bar.addSpacing(4)

        # Automatic Placement Button
        self.btn_auto_place = QPushButton("Automatic Placement")
        self.btn_auto_place.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                border: 1.5px solid #E88536;
                color: #111C24;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 12px;
                min-height: 28px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        self.btn_auto_place.setToolTip("Automatically position and fit all components optimally onto the mounting plate")
        self.btn_auto_place.clicked.connect(self._run_auto_layout)
        top_bar.addWidget(self.btn_auto_place)

        # Clear / Manual Reset Button
        self.btn_clear_layout = QPushButton("Clear All Placed")
        self.btn_clear_layout.setProperty("class", "secondary")
        self.btn_clear_layout.setMinimumHeight(34)
        self.btn_clear_layout.setToolTip("Move all placed components back to the unplaced sidebar for manual placement")
        self.btn_clear_layout.clicked.connect(self._unplace_all)
        top_bar.addWidget(self.btn_clear_layout)

        top_bar.addSpacing(6)

        # Snap Settings
        self.chk_snap = QCheckBox("Grid Snap (10mm)")
        self.chk_snap.setChecked(True)
        self.chk_snap.setStyleSheet("color: #111C24; font-size: 12px; font-weight: 500;")
        self.chk_snap.stateChanged.connect(lambda s: setattr(self, "grid_snap_enabled", bool(s)))
        top_bar.addWidget(self.chk_snap)

        top_bar.addSpacing(6)

        # Zoom & Fit Controls
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setProperty("class", "secondary")
        btn_zoom_in.setFixedSize(34, 34)
        btn_zoom_in.setToolTip("Zoom In (or Ctrl + Wheel)")
        btn_zoom_in.clicked.connect(lambda: self.view.scale(1.2, 1.2))
        top_bar.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setProperty("class", "secondary")
        btn_zoom_out.setFixedSize(34, 34)
        btn_zoom_out.setToolTip("Zoom Out (or Ctrl + Wheel)")
        btn_zoom_out.clicked.connect(lambda: self.view.scale(0.83, 0.83))
        top_bar.addWidget(btn_zoom_out)

        btn_fit = QPushButton("Fit to Panel")
        btn_fit.setProperty("class", "secondary")
        btn_fit.setMinimumHeight(34)
        btn_fit.clicked.connect(self._fit_view)
        top_bar.addWidget(btn_fit)

        # Resize Panel Enclosure Button
        btn_resize = QPushButton("Resize Panel...")
        btn_resize.setProperty("class", "secondary")
        btn_resize.setMinimumHeight(34)
        btn_resize.clicked.connect(self._open_resize_dialog)
        top_bar.addWidget(btn_resize)

        top_bar.addStretch()

        # Generate 3D View Button
        self.btn_gen_3d = QPushButton("Generate 3D View")
        self.btn_gen_3d.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                color: #111C24;
                border: 1px solid #E88536;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 14px;
                min-height: 28px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        self.btn_gen_3d.clicked.connect(self._on_generate_3d)
        top_bar.addWidget(self.btn_gen_3d)

        main_layout.addLayout(top_bar)

        # 1.5 Selection & Alignment Toolbar
        align_bar = QHBoxLayout()
        align_bar.setSpacing(6)

        lbl_filter = QLabel("Selection Filter:")
        lbl_filter.setStyleSheet("font-size: 11px; font-weight: 700; color: #111C24;")
        align_bar.addWidget(lbl_filter)

        self.combo_select_filter = QComboBox()
        self.combo_select_filter.addItems(["All Objects", "Components Only", "DIN Rails Only", "Wiring Ducts Only"])
        self.combo_select_filter.setMinimumHeight(28)
        self.combo_select_filter.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.combo_select_filter.setToolTip("Filter which object types can be selected with mouse box-drag or click")
        self.combo_select_filter.currentIndexChanged.connect(self._apply_selection_filter)
        align_bar.addWidget(self.combo_select_filter)

        btn_select_all = QPushButton("Select All")
        btn_select_all.setProperty("class", "secondary")
        btn_select_all.setMinimumHeight(28)
        btn_select_all.setStyleSheet("font-size: 11px; padding: 3px 10px; font-weight: 600;")
        btn_select_all.setToolTip("Select all visible objects matching filter on active surface (Ctrl+A)")
        btn_select_all.clicked.connect(self.select_all)
        align_bar.addWidget(btn_select_all)

        align_bar.addSpacing(10)

        lbl_align = QLabel("Align:")
        lbl_align.setStyleSheet("font-size: 11px; font-weight: 700; color: #111C24;")
        align_bar.addWidget(lbl_align)

        btn_align_top = QPushButton("Top")
        btn_align_top.setProperty("class", "secondary")
        btn_align_top.setMinimumHeight(28)
        btn_align_top.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_align_top.setToolTip("Align top edges of all selected items")
        btn_align_top.clicked.connect(self.align_selected_top)
        align_bar.addWidget(btn_align_top)

        btn_align_bot = QPushButton("Bottom")
        btn_align_bot.setProperty("class", "secondary")
        btn_align_bot.setMinimumHeight(28)
        btn_align_bot.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_align_bot.setToolTip("Align bottom edges of all selected items")
        btn_align_bot.clicked.connect(self.align_selected_bottom)
        align_bar.addWidget(btn_align_bot)

        btn_align_left = QPushButton("Left")
        btn_align_left.setProperty("class", "secondary")
        btn_align_left.setMinimumHeight(28)
        btn_align_left.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_align_left.setToolTip("Align left edges of all selected items")
        btn_align_left.clicked.connect(self.align_selected_left)
        align_bar.addWidget(btn_align_left)

        btn_align_right = QPushButton("Right")
        btn_align_right.setProperty("class", "secondary")
        btn_align_right.setMinimumHeight(28)
        btn_align_right.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_align_right.setToolTip("Align right edges of all selected items")
        btn_align_right.clicked.connect(self.align_selected_right)
        align_bar.addWidget(btn_align_right)

        btn_align_h = QPushButton("H-Center")
        btn_align_h.setProperty("class", "secondary")
        btn_align_h.setMinimumHeight(28)
        btn_align_h.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_align_h.setToolTip("Align horizontal centers of all selected items")
        btn_align_h.clicked.connect(self.align_selected_horizontal)
        align_bar.addWidget(btn_align_h)

        btn_align_v = QPushButton("V-Center")
        btn_align_v.setProperty("class", "secondary")
        btn_align_v.setMinimumHeight(28)
        btn_align_v.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_align_v.setToolTip("Align vertical centers of all selected items")
        btn_align_v.clicked.connect(self.align_selected_vertical)
        align_bar.addWidget(btn_align_v)

        align_bar.addSpacing(10)

        lbl_dist = QLabel("Distribute:")
        lbl_dist.setStyleSheet("font-size: 11px; font-weight: 700; color: #111C24;")
        align_bar.addWidget(lbl_dist)

        btn_dist_h = QPushButton("H-Space")
        btn_dist_h.setProperty("class", "secondary")
        btn_dist_h.setMinimumHeight(28)
        btn_dist_h.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_dist_h.setToolTip("Distribute 3 or more selected items evenly horizontally")
        btn_dist_h.clicked.connect(self.distribute_selected_horizontally)
        align_bar.addWidget(btn_dist_h)

        btn_dist_v = QPushButton("V-Space")
        btn_dist_v.setProperty("class", "secondary")
        btn_dist_v.setMinimumHeight(28)
        btn_dist_v.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        btn_dist_v.setToolTip("Distribute 3 or more selected items evenly vertically")
        btn_dist_v.clicked.connect(self.distribute_selected_vertically)
        align_bar.addWidget(btn_dist_v)

        align_bar.addSpacing(14)

        lbl_tools = QLabel("Tools:")
        lbl_tools.setStyleSheet("font-size: 11px; font-weight: 700; color: #111C24;")
        align_bar.addWidget(lbl_tools)

        self.btn_measure = QPushButton("Measure (M)")
        self.btn_measure.setCheckable(True)
        self.btn_measure.setProperty("class", "secondary")
        self.btn_measure.setMinimumHeight(28)
        self.btn_measure.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                padding: 3px 10px;
                font-weight: 700;
                background-color: #FFFFFF;
                color: #111C24;
                border: 1.5px solid #8A8C8D;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #FF9A4E;
                color: #111C24;
                border-color: #E88536;
            }
            QPushButton:hover {
                border-color: #FF9A4E;
            }
        """)
        self.btn_measure.setToolTip("Measure distance between any edge or center of components (Press M or click)")
        self.btn_measure.toggled.connect(self.toggle_measure_tool)
        align_bar.addWidget(self.btn_measure)

        self.btn_clear_measure = QPushButton("Clear Measure")
        self.btn_clear_measure.setProperty("class", "secondary")
        self.btn_clear_measure.setMinimumHeight(28)
        self.btn_clear_measure.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.btn_clear_measure.setToolTip("Clear all measurement lines and callouts from canvas")
        self.btn_clear_measure.clicked.connect(self.clear_measurements)
        align_bar.addWidget(self.btn_clear_measure)

        align_bar.addStretch()
        main_layout.addLayout(align_bar)

        # 2. Main Splitter: Left Sidebar + Center 2D Canvas
        splitter = QSplitter(Qt.Horizontal)

        # LEFT SIDEBAR: Interactive Palette (Components + Workspace Objects)
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.palette_tabs = QTabWidget()
        self.palette_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1E293B;
                background: #0B1120;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #111C33;
                color: #94A3B8;
                border: 1px solid #1E293B;
                border-bottom: none;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 11px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 105px;
            }
            QTabBar::tab:selected {
                background: #0F172A;
                color: #38BDF8;
                border-color: #38BDF8;
            }
        """)

        # TAB 1: BOM Components
        tab_components = QWidget()
        tab_comp_layout = QVBoxLayout(tab_components)
        tab_comp_layout.setContentsMargins(8, 8, 8, 8)
        tab_comp_layout.setSpacing(6)

        # Search / Filter Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search components...")
        self.search_edit.setMinimumHeight(32)
        self.search_edit.textChanged.connect(self._refresh_palette)
        tab_comp_layout.addWidget(self.search_edit)

        # Category Filter Dropdown
        self.cat_filter = QComboBox()
        self.cat_filter.addItems(["All Categories", "Power", "Control", "Accessories", "Wiring"])
        self.cat_filter.setMinimumHeight(32)
        self.cat_filter.currentIndexChanged.connect(self._refresh_palette)
        tab_comp_layout.addWidget(self.cat_filter)

        self.palette_list = ComponentPaletteList()
        self.palette_list.itemDoubleClicked.connect(self._on_palette_double_clicked)
        tab_comp_layout.addWidget(self.palette_list)

        btn_place_selected = QPushButton("Place Selected Item")
        btn_place_selected.setProperty("class", "secondary")
        btn_place_selected.setMinimumHeight(32)
        btn_place_selected.clicked.connect(self._place_selected_from_palette)
        tab_comp_layout.addWidget(btn_place_selected)

        btn_auto_side = QPushButton("Auto-Place All Components")
        btn_auto_side.setStyleSheet("""
            QPushButton {
                background-color: #FF9A4E;
                border: 1px solid #E88536;
                color: #111C24;
                font-weight: 700;
                font-size: 11px;
                min-height: 28px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F08738;
            }
        """)
        btn_auto_side.clicked.connect(self._run_auto_layout)
        tab_comp_layout.addWidget(btn_auto_side)

        btn_clear_side = QPushButton("Clear / Unplace All")
        btn_clear_side.setProperty("class", "secondary")
        btn_clear_side.setMinimumHeight(30)
        btn_clear_side.clicked.connect(self._unplace_all)
        tab_comp_layout.addWidget(btn_clear_side)

        self.palette_tabs.addTab(tab_components, "BOM Components")

        # TAB 2: Workspace Objects (DIN Rails & Ducts)
        tab_misc = QWidget()
        tab_misc_layout = QVBoxLayout(tab_misc)
        tab_misc_layout.setContentsMargins(8, 8, 8, 8)
        tab_misc_layout.setSpacing(8)

        misc_desc = QLabel("Drag & drop items onto mounting plate, or use buttons below.\n(Workspace objects only, excluded from BOM)")
        misc_desc.setWordWrap(True)
        misc_desc.setStyleSheet("color: #616365; font-size: 11px;")
        tab_misc_layout.addWidget(misc_desc)

        self.misc_list = WorkspaceObjectPaletteList()
        self._populate_misc_palette()
        self.misc_list.itemDoubleClicked.connect(self._on_misc_double_clicked)
        tab_misc_layout.addWidget(self.misc_list)

        btn_add_din = QPushButton("Add DIN Rail 35mm")
        btn_add_din.setProperty("class", "secondary")
        btn_add_din.setMinimumHeight(32)
        btn_add_din.clicked.connect(lambda: self.add_workspace_object("din_rail"))
        tab_misc_layout.addWidget(btn_add_din)

        btn_add_duct_h = QPushButton("Add Horizontal Wiring Duct")
        btn_add_duct_h.setProperty("class", "secondary")
        btn_add_duct_h.setMinimumHeight(32)
        btn_add_duct_h.clicked.connect(lambda: self.add_workspace_object("wire_duct_h"))
        tab_misc_layout.addWidget(btn_add_duct_h)

        btn_add_duct_v = QPushButton("Add Vertical Wiring Duct")
        btn_add_duct_v.setProperty("class", "secondary")
        btn_add_duct_v.setMinimumHeight(32)
        btn_add_duct_v.clicked.connect(lambda: self.add_workspace_object("wire_duct_v"))
        tab_misc_layout.addWidget(btn_add_duct_v)

        tab_misc_layout.addStretch()

        self.palette_tabs.addTab(tab_misc, "Workspace Objects")
        left_layout.addWidget(self.palette_tabs)
        splitter.addWidget(left_box)

        # CENTER: Dimensionally Accurate 2D Mounting Plate Canvas
        self.scene = QGraphicsScene()
        self.view = Panel2DView(self.scene, self)
        self.view.setStyleSheet("background-color: #FFFFFF; border: 1.5px solid #8A8C8D; border-radius: 6px;")
        splitter.addWidget(self.view)

        left_box.setMinimumWidth(280)
        left_box.setMaximumWidth(360)
        self.view.setMinimumWidth(600)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 8)
        main_layout.addWidget(splitter, stretch=1)

        # 3. Bottom Status Bar
        status_frame = QFrame()
        status_frame.setStyleSheet("background-color: #FFFFFF; border: 1.5px solid #8A8C8D; border-radius: 6px; padding: 6px 14px;")
        status_layout = QHBoxLayout(status_frame)

        self.lbl_panel_dims = QLabel("Enclosure: 800 × 1200 × 400 mm")
        self.lbl_panel_dims.setStyleSheet("font-weight: 700; color: #111C24; font-size: 13px;")
        status_layout.addWidget(self.lbl_panel_dims)

        self.lbl_plate_dims = QLabel("Mounting Plate: 740 × 1060 mm")
        self.lbl_plate_dims.setStyleSheet("color: #616365; font-size: 12px; margin-left: 15px;")
        status_layout.addWidget(self.lbl_plate_dims)

        self.lbl_placed_count = QLabel("Placed: 0 / 0 instances")
        self.lbl_placed_count.setStyleSheet("color: #FF9A4E; font-weight: 700; font-size: 12px; margin-left: 15px;")
        status_layout.addWidget(self.lbl_placed_count)

        self.lbl_collision_status = QLabel("Layout: Ready (Use Automatic Placement or drag manually)")
        self.lbl_collision_status.setStyleSheet("color: #111C24; font-weight: 600; font-size: 12px; margin-left: 15px;")
        status_layout.addWidget(self.lbl_collision_status)

        status_layout.addStretch()
        main_layout.addWidget(status_frame)

    def set_active_surface(self, surface: str):
        """Seamlessly toggle between Mounting Plate (Z View) and Outer Door (Z+1 View)."""
        if surface not in ("Z", "Z+1"):
            surface = "Z"
        self.active_surface = surface
        self._update_surface_buttons_ui()
        self._rebuild_scene()
        self._refresh_palette()
        self._update_status_bar()
        QTimer.singleShot(60, self._fit_view)

    def _update_surface_buttons_ui(self):
        if not hasattr(self, 'btn_view_z') or not hasattr(self, 'btn_view_z1'):
            return
        if self.active_surface == "Z":
            self.btn_view_z.setChecked(True)
            self.btn_view_z1.setChecked(False)
            self.btn_view_z.setStyleSheet("""
                QPushButton {
                    background-color: #FF9A4E;
                    color: #111C24;
                    border: 1.5px solid #E88536;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-weight: 700;
                    font-size: 11px;
                    min-height: 28px;
                }
            """)
            self.btn_view_z1.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #616365;
                    border: 1.5px solid #8A8C8D;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-weight: 600;
                    font-size: 11px;
                    min-height: 28px;
                }
                QPushButton:hover {
                    background-color: #F5F6F7;
                    color: #111C24;
                    border-color: #FF9A4E;
                }
            """)
        else:
            self.btn_view_z.setChecked(False)
            self.btn_view_z1.setChecked(True)
            self.btn_view_z.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #616365;
                    border: 1.5px solid #8A8C8D;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-weight: 600;
                    font-size: 11px;
                    min-height: 28px;
                }
                QPushButton:hover {
                    background-color: #F5F6F7;
                    color: #111C24;
                    border-color: #FF9A4E;
                }
            """)
            self.btn_view_z1.setStyleSheet("""
                QPushButton {
                    background-color: #FF9A4E;
                    color: #111C24;
                    border: 1.5px solid #E88536;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-weight: 700;
                    font-size: 11px;
                    min-height: 28px;
                }
            """)

    def transfer_instance_surface(self, instance: PhysicalInstance, target_surface: str):
        """Transfer an instance between Mounting Plate (Z) and Door (Z+1)."""
        if self.undo_manager:
            self.undo_manager.push_state()
        instance.surface = target_surface
        enc = self.project.enclosure
        if target_surface == "Z+1":
            instance.mounting_type = MountingType.DOOR
            instance.x = max(50.0, min(instance.x, enc.width - instance.width - 50.0))
            instance.y = max(50.0, min(instance.y, enc.height - instance.height - 50.0))
            instance.z = enc.depth - 5.0
        else:
            if instance.mounting_type == MountingType.DOOR:
                instance.mounting_type = MountingType.PLATE
            instance.x = max(20.0, min(instance.x, enc.mounting_plate_width - instance.width - 20.0))
            instance.y = max(20.0, min(instance.y, enc.mounting_plate_height - instance.height - 20.0))
            instance.z = 0.0

        self.set_active_surface(target_surface)
        surf_str = "Outer Door (Z+1 View)" if target_surface == "Z+1" else "Mounting Plate (Z View)"
        self.show_status_message(f"Moved '{instance.name}' to {surf_str}.")
        self._update_undo_redo_ui()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Undo):
            self.undo()
            event.accept()
        elif event.matches(QKeySequence.Redo):
            self.redo()
            event.accept()
        else:
            super().keyPressEvent(event)

    def undo(self):
        if self.undo_manager:
            if self.undo_manager.undo():
                self.show_status_message("Undone (Ctrl+Z) - restored previous state.")
                self._update_undo_redo_ui()

    def redo(self):
        if self.undo_manager:
            if self.undo_manager.redo():
                self.show_status_message("Redone (Ctrl+Y) - re-applied state.")
                self._update_undo_redo_ui()

    def _update_undo_redo_ui(self):
        if self.undo_manager:
            can_u = self.undo_manager.can_undo()
            can_r = self.undo_manager.can_redo()
            self.btn_undo.setEnabled(can_u)
            self.btn_redo.setEnabled(can_r)

    def sync_instances_from_project(self):
        """
        Synchronizes 2D canvas items with self.project.physical_instances non-destructively:
        - Removes 2D items for instances that were deleted (e.g. from BOM).
        - Keeps all existing placed components, DIN rails, and wiring ducts untouched at their exact positions.
        - Refreshes unplaced sidebar palette.
        """
        if not self.project:
            return

        current_inst_ids = {inst.id: inst for inst in self.project.physical_instances}

        # 1. Remove graphic items for deleted instances
        for inst_id in list(self._item_map.keys()):
            if inst_id not in current_inst_ids:
                item = self._item_map.pop(inst_id)
                if item.scene() == self.scene:
                    self.scene.removeItem(item)

        # 2. Update remaining items
        for inst_id, item in list(self._item_map.items()):
            inst = current_inst_ids.get(inst_id)
            if not inst or not inst.is_placed:
                # Became unplaced or removed
                if item.scene() == self.scene:
                    self.scene.removeItem(item)
                self._item_map.pop(inst_id, None)
            else:
                # Update item geometry in case dimensions or rotation changed
                eff_w = inst.height if int(inst.rotation) in (90, 270) else inst.width
                eff_h = inst.width if int(inst.rotation) in (90, 270) else inst.height
                item.setRect(0, 0, eff_w, eff_h)
                item.setPos(inst.x, inst.y)
                item._update_appearance()

        # 3. Add any placed instance that doesn't have a 2D item yet
        for inst in self.project.physical_instances:
            if inst.is_placed and not inst.is_external and inst.id not in self._item_map:
                new_item = Component2DItem(inst, self)
                self.scene.addItem(new_item)
                self._item_map[inst.id] = new_item

        # 4. Refresh palette & status bar
        self._refresh_palette()
        self._revalidate_and_highlight()
        self._apply_selection_filter()
        self._update_status_bar()
        self._update_undo_redo_ui()

    def _populate_misc_palette(self):
        self.misc_list.clear()

        item1 = QListWidgetItem("DIN Rail (35mm EN 60715)\nStandard TS35 steel mounting rail")
        item1.setData(Qt.UserRole, "din_rail")
        item1.setForeground(QColor("#E2E8F0"))
        self.misc_list.addItem(item1)

        item2 = QListWidgetItem("Wiring Duct — Horizontal (40×60mm)\nSlotted PVC trunking for cable routing")
        item2.setData(Qt.UserRole, "wire_duct_h")
        item2.setForeground(QColor("#E2E8F0"))
        self.misc_list.addItem(item2)

        item3 = QListWidgetItem("Wiring Duct — Vertical (40×60mm)\nVertical side cable trunking")
        item3.setData(Qt.UserRole, "wire_duct_v")
        item3.setForeground(QColor("#E2E8F0"))
        self.misc_list.addItem(item3)

    def _on_misc_double_clicked(self, item: QListWidgetItem):
        obj_type = item.data(Qt.UserRole)
        if obj_type:
            self.add_workspace_object(obj_type)

    def add_workspace_object(self, obj_type: str, scene_x: Optional[float] = None, scene_y: Optional[float] = None):
        """Add a DIN rail or wiring duct workspace object to the 2D mounting plate."""
        if not self.project or not self.project.enclosure:
            return

        if self.undo_manager:
            self.undo_manager.push_state()

        plate_w = self.project.enclosure.mounting_plate_width
        plate_h = self.project.enclosure.mounting_plate_height

        import uuid
        uid = uuid.uuid4().hex[:6]

        if obj_type == "din_rail":
            rail_len = min(600.0, max(200.0, plate_w - 120.0))
            pos_x = scene_x if scene_x is not None else 60.0
            pos_y = scene_y if scene_y is not None else (plate_h * 0.7)
            pos_x = max(0.0, min(pos_x, plate_w - rail_len))
            pos_y = max(0.0, min(pos_y, plate_h - 35.0))
            if self.grid_snap_enabled:
                pos_x = round(pos_x / self.grid_step) * self.grid_step
                pos_y = round(pos_y / self.grid_step) * self.grid_step

            rail = DINRail(
                id=f"rail_{uid}",
                name=f"DIN Rail 35mm #{len(self.project.din_rails) + 1}",
                x=pos_x,
                y=pos_y,
                z=0.0,
                length=rail_len,
                height=35.0,
                depth=7.5,
                orientation="HORIZONTAL",
                rotation=0.0
            )
            self.project.din_rails.append(rail)
            item = DINRail2DItem(rail, self)
            self.scene.addItem(item)
            self._rail_map[rail.id] = item
            self.scene.clearSelection()
            item.setSelected(True)
            self.show_status_message(f"Added {rail.name} at ({int(pos_x)}, {int(pos_y)}) mm. Drag to move, double-click to edit.")

        elif obj_type in ("wire_duct_h", "wire_duct_v", "wiring_duct"):
            is_vert = (obj_type == "wire_duct_v")
            duct_len = min(600.0, max(200.0, (plate_h - 100.0) if is_vert else (plate_w - 120.0)))
            pos_x = scene_x if scene_x is not None else (60.0 if not is_vert else 20.0)
            pos_y = scene_y if scene_y is not None else (plate_h * 0.6 if not is_vert else 60.0)

            eff_w = 40.0 if is_vert else duct_len
            eff_h = duct_len if is_vert else 60.0
            pos_x = max(0.0, min(pos_x, plate_w - eff_w))
            pos_y = max(0.0, min(pos_y, plate_h - eff_h))
            if self.grid_snap_enabled:
                pos_x = round(pos_x / self.grid_step) * self.grid_step
                pos_y = round(pos_y / self.grid_step) * self.grid_step

            duct = WiringDuct(
                id=f"duct_{uid}",
                name=f"Wiring Duct ({'V' if is_vert else 'H'}) #{len(self.project.wiring_ducts) + 1}",
                x=pos_x,
                y=pos_y,
                z=0.0,
                width=40.0,
                height=60.0,
                length=duct_len,
                orientation="VERTICAL" if is_vert else "HORIZONTAL",
                rotation=90.0 if is_vert else 0.0
            )
            self.project.wiring_ducts.append(duct)
            item = WireDuct2DItem(duct, self)
            self.scene.addItem(item)
            self._duct_map[duct.id] = item
            self.scene.clearSelection()
            item.setSelected(True)
            self.show_status_message(f"Added {duct.name} at ({int(pos_x)}, {int(pos_y)}) mm. Drag to move, double-click to edit.")

        self._update_undo_redo_ui()

    def delete_din_rail(self, rail: DINRail):
        if self.undo_manager:
            self.undo_manager.push_state()
        if rail in self.project.din_rails:
            self.project.din_rails.remove(rail)
        item = self._rail_map.pop(rail.id, None)
        if item and item.scene() == self.scene:
            self.scene.removeItem(item)
        self.show_status_message(f"Deleted {rail.name} from workspace.")
        self._update_undo_redo_ui()

    def delete_wiring_duct(self, duct: WiringDuct):
        if self.undo_manager:
            self.undo_manager.push_state()
        if duct in self.project.wiring_ducts:
            self.project.wiring_ducts.remove(duct)
        item = self._duct_map.pop(duct.id, None)
        if item and item.scene() == self.scene:
            self.scene.removeItem(item)
        self.show_status_message(f"Deleted {duct.name} from workspace.")
        self._update_undo_redo_ui()

    def unplace_instance(self, instance: PhysicalInstance):
        if self.undo_manager:
            self.undo_manager.push_state()
        instance.is_placed = False
        item = self._item_map.pop(instance.id, None)
        if item and item.scene() == self.scene:
            self.scene.removeItem(item)
        self._refresh_palette()
        self._revalidate_and_highlight()
        self._apply_selection_filter()
        self._update_status_bar()
        self.show_status_message(f"Removed {instance.name} from mounting plate.")
        self._update_undo_redo_ui()

    def delete_selected_items(self):
        """Delete currently selected workspace items (components, DIN rails, or wiring ducts)."""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return

        if self.undo_manager:
            self.undo_manager.push_state()

        deleted_names = []
        for item in selected_items:
            if isinstance(item, Component2DItem):
                item.instance.is_placed = False
                self.scene.removeItem(item)
                if item.instance.id in self._item_map:
                    del self._item_map[item.instance.id]
                deleted_names.append(item.instance.name)
            elif isinstance(item, DINRail2DItem):
                if item.rail in self.project.din_rails:
                    self.project.din_rails.remove(item.rail)
                self.scene.removeItem(item)
                if item.rail.id in self._rail_map:
                    del self._rail_map[item.rail.id]
                deleted_names.append(item.rail.name)
            elif isinstance(item, WireDuct2DItem):
                if item.duct in self.project.wiring_ducts:
                    self.project.wiring_ducts.remove(item.duct)
                self.scene.removeItem(item)
                if item.duct.id in self._duct_map:
                    del self._duct_map[item.duct.id]
                deleted_names.append(item.duct.name)

        self._refresh_palette()
        self._revalidate_and_highlight()
        self._apply_selection_filter()
        self._update_status_bar()
        self._update_undo_redo_ui()
        if deleted_names:
            self.show_status_message(f"Removed from workspace: {', '.join(deleted_names[:3])}")

    def _apply_selection_filter(self):
        """Enforce the active selection filter so only matching object types can be selected."""
        mode = self.combo_select_filter.currentText() if hasattr(self, "combo_select_filter") else "All Objects"
        for item in self.scene.items():
            if not isinstance(item, (Component2DItem, DINRail2DItem, WireDuct2DItem)):
                continue
            allowed = True
            if "Component" in mode and not isinstance(item, Component2DItem):
                allowed = False
            elif "DIN Rail" in mode and not isinstance(item, DINRail2DItem):
                allowed = False
            elif "Wiring Duct" in mode and not isinstance(item, WireDuct2DItem):
                allowed = False

            item.setFlag(QGraphicsItem.ItemIsSelectable, allowed)
            if not allowed and item.isSelected():
                item.setSelected(False)

    def select_all(self):
        """Select all items on active surface matching current selection filter (Ctrl+A)."""
        mode = self.combo_select_filter.currentText() if hasattr(self, "combo_select_filter") else "All Objects"
        count = 0
        for item in self.scene.items():
            if not isinstance(item, (Component2DItem, DINRail2DItem, WireDuct2DItem)):
                continue
            if isinstance(item, Component2DItem):
                if getattr(item.instance, "surface", "Z").upper() != self.active_surface:
                    continue
            if "Component" in mode and not isinstance(item, Component2DItem):
                continue
            if "DIN Rail" in mode and not isinstance(item, DINRail2DItem):
                continue
            if "Wiring Duct" in mode and not isinstance(item, WireDuct2DItem):
                continue

            item.setSelected(True)
            count += 1
        self.show_status_message(f"Selected {count} item(s) on {self.active_surface} view.")

    def _get_selected_design_items(self) -> List[QGraphicsRectItem]:
        """Return list of selected movable design items (components, rails, ducts)."""
        return [
            item for item in self.scene.selectedItems()
            if isinstance(item, (Component2DItem, DINRail2DItem, WireDuct2DItem))
        ]

    def _move_item_to(self, item, new_x: float, new_y: float):
        """Move item to new coordinates and sync backing models."""
        item.setPos(new_x, new_y)
        item.last_valid_x = new_x
        item.last_valid_y = new_y
        if isinstance(item, Component2DItem):
            item.instance.x = new_x
            item.instance.y = new_y
        elif isinstance(item, DINRail2DItem):
            item.rail.x = new_x
            item.rail.y = new_y
        elif isinstance(item, WireDuct2DItem):
            item.duct.x = new_x
            item.duct.y = new_y

    def _after_alignment(self, msg: str):
        self._revalidate_and_highlight()
        self._apply_selection_filter()
        self._update_status_bar()
        self._update_undo_redo_ui()
        self.show_status_message(msg)

    def align_selected_top(self):
        items = self._get_selected_design_items()
        if len(items) < 2:
            self.show_status_message("Select at least 2 items to align to top.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        min_y = min(item.pos().y() for item in items)
        for item in items:
            self._move_item_to(item, item.pos().x(), min_y)
        self._after_alignment(f"Aligned {len(items)} items to Top (Y={min_y:.0f}mm)")

    def align_selected_bottom(self):
        items = self._get_selected_design_items()
        if len(items) < 2:
            self.show_status_message("Select at least 2 items to align to bottom.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        max_bot = max(item.pos().y() + item.rect().height() for item in items)
        for item in items:
            new_y = max_bot - item.rect().height()
            self._move_item_to(item, item.pos().x(), new_y)
        self._after_alignment(f"Aligned {len(items)} items to Bottom (Y={max_bot:.0f}mm)")

    def align_selected_left(self):
        items = self._get_selected_design_items()
        if len(items) < 2:
            self.show_status_message("Select at least 2 items to align to left.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        min_x = min(item.pos().x() for item in items)
        for item in items:
            self._move_item_to(item, min_x, item.pos().y())
        self._after_alignment(f"Aligned {len(items)} items to Left (X={min_x:.0f}mm)")

    def align_selected_right(self):
        items = self._get_selected_design_items()
        if len(items) < 2:
            self.show_status_message("Select at least 2 items to align to right.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        max_r = max(item.pos().x() + item.rect().width() for item in items)
        for item in items:
            new_x = max_r - item.rect().width()
            self._move_item_to(item, new_x, item.pos().y())
        self._after_alignment(f"Aligned {len(items)} items to Right (X={max_r:.0f}mm)")

    def align_selected_horizontal(self):
        items = self._get_selected_design_items()
        if len(items) < 2:
            self.show_status_message("Select at least 2 items to align horizontally.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        avg_cy = sum(item.pos().y() + item.rect().height() / 2.0 for item in items) / len(items)
        for item in items:
            new_y = avg_cy - item.rect().height() / 2.0
            self._move_item_to(item, item.pos().x(), new_y)
        self._after_alignment(f"Aligned {len(items)} items to Horizontal Center (Y={avg_cy:.0f}mm)")

    def align_selected_vertical(self):
        items = self._get_selected_design_items()
        if len(items) < 2:
            self.show_status_message("Select at least 2 items to align vertically.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        avg_cx = sum(item.pos().x() + item.rect().width() / 2.0 for item in items) / len(items)
        for item in items:
            new_x = avg_cx - item.rect().width() / 2.0
            self._move_item_to(item, new_x, item.pos().y())
        self._after_alignment(f"Aligned {len(items)} items to Vertical Center (X={avg_cx:.0f}mm)")

    def distribute_selected_horizontally(self):
        items = self._get_selected_design_items()
        if len(items) < 3:
            self.show_status_message("Select at least 3 items to distribute horizontally.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        items.sort(key=lambda it: it.pos().x())
        left_x = items[0].pos().x()
        right_end = items[-1].pos().x() + items[-1].rect().width()
        total_items_w = sum(it.rect().width() for it in items)
        total_span = right_end - left_x
        free_space = total_span - total_items_w
        gap = max(0.0, free_space / (len(items) - 1))
        cur_x = left_x
        for item in items:
            self._move_item_to(item, cur_x, item.pos().y())
            cur_x += item.rect().width() + gap
        self._after_alignment(f"Distributed {len(items)} items horizontally (gap={gap:.1f}mm)")

    def distribute_selected_vertically(self):
        items = self._get_selected_design_items()
        if len(items) < 3:
            self.show_status_message("Select at least 3 items to distribute vertically.", is_warning=True)
            return
        if self.undo_manager:
            self.undo_manager.push_state()
        items.sort(key=lambda it: it.pos().y())
        top_y = items[0].pos().y()
        bottom_end = items[-1].pos().y() + items[-1].rect().height()
        total_items_h = sum(it.rect().height() for it in items)
        total_span = bottom_end - top_y
        free_space = total_span - total_items_h
        gap = max(0.0, free_space / (len(items) - 1))
        cur_y = top_y
        for item in items:
            self._move_item_to(item, item.pos().x(), cur_y)
            cur_y += item.rect().height() + gap
        self._after_alignment(f"Distributed {len(items)} items vertically (gap={gap:.1f}mm)")

    def _rebuild_scene(self):
        if not self.project or not self.project.enclosure:
            return

        self.scene.clear()
        self._item_map.clear()
        self._rail_map.clear()
        self._duct_map.clear()

        enc = self.project.enclosure
        is_door_view = (self.active_surface == "Z+1")

        canvas_w = enc.width if is_door_view else enc.mounting_plate_width
        canvas_h = enc.height if is_door_view else enc.mounting_plate_height

        # Margin around canvas for rulers and exterior frame
        r_offset = 50.0
        self.scene.setSceneRect(-r_offset - 10, -r_offset - 10, canvas_w + r_offset * 2 + 20, canvas_h + r_offset * 2 + 20)

        # 1. Outer Perimeter Background
        outer_bg = self.scene.addRect(
            -r_offset, -r_offset, canvas_w + r_offset * 2, canvas_h + r_offset * 2,
            QPen(Qt.NoPen),
            QBrush(QColor("#FFFFFF"))
        )
        outer_bg.setZValue(-2)

        if not is_door_view:
            # 2a. Bright Galvanized Steel Mounting Plate
            plate_rect = self.scene.addRect(
                0, 0, canvas_w, canvas_h,
                QPen(QColor("#8A8C8D"), 2.0),
                QBrush(QColor("#E5E7EB")) # Galvanized zinc finish
            )
            plate_rect.setZValue(0)

            # Header text
            dim_top = self.scene.addText(f"Mounting Plate (Z View) — Usable Surface: {int(canvas_w)} × {int(canvas_h)} mm", QFont("Segoe UI", 9, QFont.Bold))
            dim_top.setDefaultTextColor(QColor("#111C24"))
            dim_top.setPos(canvas_w / 2.0 - 160, -42)
            dim_top.setZValue(4)

            # DIN Rails
            for rail in self.project.din_rails:
                rail_item = DINRail2DItem(rail, self)
                self.scene.addItem(rail_item)
                self._rail_map[rail.id] = rail_item

            # Wiring Ducts
            for duct in self.project.wiring_ducts:
                duct_item = WireDuct2DItem(duct, self)
                self.scene.addItem(duct_item)
                self._duct_map[duct.id] = duct_item
        else:
            # 2b. Industrial Powder-Coated Outer Door Sheet (RAL 7035)
            is_double = (getattr(enc, "door_type", "SINGLE") == "DOUBLE_VERTICAL")

            if is_double:
                # DOUBLE DOOR (VERTICAL SPLIT)
                mid_x = canvas_w / 2.0

                # Left Door Leaf
                left_leaf = self.scene.addRect(
                    0, 0, mid_x - 1.0, canvas_h,
                    QPen(QColor("#8A8C8D"), 2.0),
                    QBrush(QColor("#F3F4F6"))
                )
                left_leaf.setZValue(0)

                # Right Door Leaf
                right_leaf = self.scene.addRect(
                    mid_x + 1.0, 0, mid_x - 1.0, canvas_h,
                    QPen(QColor("#8A8C8D"), 2.0),
                    QBrush(QColor("#F3F4F6"))
                )
                right_leaf.setZValue(0)

                # Center Seam Divider (Meeting Stile / Vertical Split)
                seam_line = self.scene.addLine(
                    mid_x, 0, mid_x, canvas_h,
                    QPen(QColor("#FF9A4E"), 2.5, Qt.DashLine)
                )
                seam_line.setZValue(2)

                # Inner bevel for Left Leaf
                left_bevel = self.scene.addRect(
                    16, 16, mid_x - 32, canvas_h - 32,
                    QPen(QColor("#8A8C8D"), 1.2, Qt.DashLine),
                    QBrush(Qt.NoBrush)
                )
                left_bevel.setZValue(1)

                # Inner bevel for Right Leaf
                right_bevel = self.scene.addRect(
                    mid_x + 16, 16, mid_x - 32, canvas_h - 32,
                    QPen(QColor("#8A8C8D"), 1.2, Qt.DashLine),
                    QBrush(Qt.NoBrush)
                )
                right_bevel.setZValue(1)

                # Center Dual Lock Mechanism at mid_x
                lock_plate = self.scene.addRect(
                    mid_x - 12, canvas_h / 2.0 - 24, 24, 48,
                    QPen(QColor("#111C24"), 1.5),
                    QBrush(QColor("#616365"))
                )
                lock_plate.setZValue(3)

                lock_handle = self.scene.addRect(
                    mid_x - 4, canvas_h / 2.0 - 10, 8, 20,
                    QPen(QColor("#111C24"), 1),
                    QBrush(QColor("#111C24"))
                )
                lock_handle.setZValue(4)

                # Left Hinges on Left Outer Edge
                for hy in (70.0, canvas_h / 2.0, canvas_h - 70.0):
                    hinge_l = self.scene.addRect(
                        0, hy - 18, 6, 36,
                        QPen(QColor("#616365"), 1.2),
                        QBrush(QColor("#8A8C8D"))
                    )
                    hinge_l.setZValue(2)

                # Right Hinges on Right Outer Edge
                for hy in (70.0, canvas_h / 2.0, canvas_h - 70.0):
                    hinge_r = self.scene.addRect(
                        canvas_w - 6, hy - 18, 6, 36,
                        QPen(QColor("#616365"), 1.2),
                        QBrush(QColor("#8A8C8D"))
                    )
                    hinge_r.setZValue(2)

                # Door leaf labels
                lbl_left = self.scene.addText(f"Left Door Leaf ({int(mid_x)} x {int(canvas_h)} mm)", QFont("Segoe UI", 8, QFont.Bold))
                lbl_left.setDefaultTextColor(QColor("#616365"))
                lbl_left.setPos(mid_x / 2.0 - 80, 20)
                lbl_left.setZValue(2)

                lbl_right = self.scene.addText(f"Right Door Leaf ({int(mid_x)} x {int(canvas_h)} mm)", QFont("Segoe UI", 8, QFont.Bold))
                lbl_right.setDefaultTextColor(QColor("#616365"))
                lbl_right.setPos(mid_x + mid_x / 2.0 - 80, 20)
                lbl_right.setZValue(2)

                # Header text
                dim_top = self.scene.addText(
                    f"Outer Door (Z+1 View) — Double Door (Vertical Split) | 2x {int(mid_x)} x {int(canvas_h)} mm",
                    QFont("Segoe UI", 9, QFont.Bold)
                )
                dim_top.setDefaultTextColor(QColor("#111C24"))
                dim_top.setPos(canvas_w / 2.0 - 200, -42)
                dim_top.setZValue(4)

            else:
                # SINGLE DOOR
                door_rect = self.scene.addRect(
                    0, 0, canvas_w, canvas_h,
                    QPen(QColor("#8A8C8D"), 2.5),
                    QBrush(QColor("#F3F4F6")) # Powder-coat light grey door
                )
                door_rect.setZValue(0)

                # Inner door frame bevel
                inner_bevel = self.scene.addRect(
                    16, 16, canvas_w - 32, canvas_h - 32,
                    QPen(QColor("#8A8C8D"), 1.5, Qt.DashLine),
                    QBrush(Qt.NoBrush)
                )
                inner_bevel.setZValue(1)

                # Quarter-turn industrial door lock mechanism
                lock_plate = self.scene.addRect(
                    canvas_w - 42, canvas_h / 2.0 - 24, 18, 48,
                    QPen(QColor("#111C24"), 1.5),
                    QBrush(QColor("#616365"))
                )
                lock_plate.setZValue(2)

                lock_handle = self.scene.addRect(
                    canvas_w - 36, canvas_h / 2.0 - 8, 6, 16,
                    QPen(QColor("#111C24"), 1),
                    QBrush(QColor("#111C24"))
                )
                lock_handle.setZValue(3)

                # Door hinges on right edge
                for hy in (70.0, canvas_h / 2.0, canvas_h - 70.0):
                    hinge = self.scene.addRect(
                        canvas_w - 6, hy - 18, 6, 36,
                        QPen(QColor("#616365"), 1.2),
                        QBrush(QColor("#8A8C8D"))
                    )
                    hinge.setZValue(2)

                # Header text
                dim_top = self.scene.addText(
                    f"Enclosure Outer Door (Z+1 View) — Face Dimensions: {int(canvas_w)} x {int(canvas_h)} mm",
                    QFont("Segoe UI", 9, QFont.Bold)
                )
                dim_top.setDefaultTextColor(QColor("#111C24"))
                dim_top.setPos(canvas_w / 2.0 - 180, -42)
                dim_top.setZValue(4)

        # 3. Top-Left Origin Marker (0,0)
        origin_lbl = self.scene.addText("(0,0)", QFont("Segoe UI", 8, QFont.Bold))
        origin_lbl.setDefaultTextColor(QColor("#FF9A4E" if is_door_view else "#111C24"))
        origin_lbl.setPos(-28, -24)
        origin_lbl.setZValue(5)

        # 4. Millimeter Grid Lines
        grid_color = "#CBD5E1" if is_door_view else "#94A3B8"
        for x in range(0, int(canvas_w), 50):
            is_major = (x % 100 == 0)
            pen = QPen(QColor("#64748B" if is_major else grid_color), 0.8 if is_major else 0.4)
            line = self.scene.addLine(x, 0, x, canvas_h, pen)
            line.setZValue(1)

        for y in range(0, int(canvas_h), 50):
            is_major = (y % 100 == 0)
            pen = QPen(QColor("#64748B" if is_major else grid_color), 0.8 if is_major else 0.4)
            line = self.scene.addLine(0, y, canvas_w, y, pen)
            line.setZValue(1)

        # 5. X Ruler along Top Edge (mm)
        for x in range(0, int(canvas_w) + 1, 50):
            tick_h = 10 if x % 100 == 0 else 5
            self.scene.addLine(x, -tick_h, x, 0, QPen(QColor("#FB7185" if is_door_view else "#38BDF8"), 1)).setZValue(3)
            if x % 100 == 0 and x > 0:
                txt = self.scene.addText(f"{x}", QFont("Segoe UI", 7))
                txt.setDefaultTextColor(QColor("#94A3B8"))
                txt.setPos(x - 12, -26)
                txt.setZValue(3)

        # 6. Y Ruler along Left Edge (mm)
        for y in range(0, int(canvas_h) + 1, 50):
            tick_w = 10 if y % 100 == 0 else 5
            self.scene.addLine(-tick_w, y, 0, y, QPen(QColor("#FB7185" if is_door_view else "#38BDF8"), 1)).setZValue(3)
            if y % 100 == 0 and y > 0:
                txt = self.scene.addText(f"{y}", QFont("Segoe UI", 7))
                txt.setDefaultTextColor(QColor("#94A3B8"))
                txt.setPos(-42, y - 10)
                txt.setZValue(3)

        # 7. Render Placed Components on the ACTIVE SURFACE ONLY
        for inst in self.project.physical_instances:
            if not inst.is_placed or inst.is_external:
                continue

            inst_surf = getattr(inst, "surface", "Z").upper()
            target_surf = "Z+1" if is_door_view else "Z"
            if inst_surf == target_surf:
                item = Component2DItem(inst, self)
                self.scene.addItem(item)
                self._item_map[inst.id] = item

        self._revalidate_and_highlight()
        self._apply_selection_filter()

    def _fit_view(self):
        if self.scene and self.view and self.view.width() > 80 and self.view.height() > 80:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def _refresh_palette(self):
        if not self.project:
            return

        self.palette_list.clear()
        query = self.search_edit.text().strip().lower()
        cat_sel = self.cat_filter.currentText()

        # Group instances by BOM item or component name to show aggregated status
        grouped: Dict[str, List[PhysicalInstance]] = {}
        for inst in self.project.physical_instances:
            if inst.is_external:
                continue
            key = f"{inst.name}##{inst.part_number}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(inst)

        for key, instances in grouped.items():
            first = instances[0]
            # Surface filter: match self.active_surface
            inst_surf = getattr(first, "surface", "Z").upper()
            if inst_surf != self.active_surface:
                continue

            # Category filter
            if cat_sel != "All Categories" and first.category.lower() != cat_sel.lower():
                continue
            # Search filter
            text_match = f"{first.name} {first.manufacturer} {first.part_number or ''} {first.category}".lower()
            if query and query not in text_match:
                continue

            placed_count = sum(1 for i in instances if i.is_placed)
            total_count = len(instances)
            unplaced = [i for i in instances if not i.is_placed]

            status_icon = f"[{placed_count}/{total_count}]"
            surf_tag = "[Door Z+1]" if inst_surf == "Z+1" else "[Plate Z]"
            item_text = (
                f"{status_icon} {first.name}  {surf_tag}\n"
                f"Mfr: {first.manufacturer} | P/N: {first.part_number or 'Standard'}\n"
                f"Size: {int(first.width)}×{int(first.height)}×{int(first.depth)}mm"
            )

            list_item = QListWidgetItem(item_text)
            target_id = unplaced[0].id if unplaced else first.id
            list_item.setData(Qt.UserRole, target_id)

            if unplaced:
                list_item.setForeground(QColor("#111C24"))
            else:
                list_item.setForeground(QColor("#616365"))

            self.palette_list.addItem(list_item)

        self._update_status_bar()

    def _place_selected_from_palette(self):
        cur = self.palette_list.currentItem()
        if cur:
            self._on_palette_double_clicked(cur)

    def _on_palette_double_clicked(self, item: QListWidgetItem):
        inst_id = item.data(Qt.UserRole)
        inst = next((i for i in self.project.physical_instances if i.id == inst_id), None)
        if not inst:
            return

        if inst.is_placed:
            same_unplaced = [
                i for i in self.project.physical_instances 
                if i.name == inst.name and not i.is_placed and not i.is_external
            ]
            if same_unplaced:
                inst = same_unplaced[0]
            else:
                QMessageBox.information(self, "All Placed", f"All instances of '{inst.name}' are already placed.")
                return

        if self.undo_manager:
            self.undo_manager.push_state()

        inst.surface = self.active_surface
        enc = self.project.enclosure
        is_door = (self.active_surface == "Z+1")
        if is_door:
            inst.mounting_type = MountingType.DOOR
            bound_w = enc.width
            bound_h = enc.height
        else:
            bound_w = enc.mounting_plate_width
            bound_h = enc.mounting_plate_height

        cand_x = 40.0
        cand_y = 40.0
        placed_spot_found = False

        for test_y in range(40, int(bound_h - inst.height - 20), 40):
            for test_x in range(40, int(bound_w - inst.width - 20), 40):
                inst.x = float(test_x)
                inst.y = float(test_y)
                inst.is_placed = True
                valid, _ = CollisionDetector.validate_position(
                    inst, self.project.physical_instances, bound_w, bound_h
                )
                if valid:
                    cand_x = float(test_x)
                    cand_y = float(test_y)
                    placed_spot_found = True
                    break
            if placed_spot_found:
                break

        if not placed_spot_found:
            cand_x = max(10.0, bound_w / 2.0 - inst.width / 2.0)
            cand_y = max(10.0, bound_h / 2.0 - inst.height / 2.0)

        inst.x = cand_x
        inst.y = cand_y
        inst.is_placed = True

        comp_item = Component2DItem(inst, self)
        self.scene.addItem(comp_item)
        self._item_map[inst.id] = comp_item
        comp_item.setSelected(True)

        self._refresh_palette()
        self._update_status_bar()
        self._update_undo_redo_ui()

    def place_instance_at(self, instance_id: str, scene_x: float, scene_y: float):
        """Place an unplaced component instance at a specific drop coordinate."""
        inst = next((i for i in self.project.physical_instances if i.id == instance_id), None)
        if not inst:
            return

        if inst.is_placed:
            same_unplaced = [
                i for i in self.project.physical_instances 
                if i.name == inst.name and not i.is_placed and not i.is_external
            ]
            if same_unplaced:
                inst = same_unplaced[0]
            else:
                self.show_status_message(f"All instances of '{inst.name}' are already placed.", is_warning=True)
                return

        if self.undo_manager:
            self.undo_manager.push_state()

        inst.surface = self.active_surface
        enc = self.project.enclosure
        is_door = (self.active_surface == "Z+1")
        if is_door:
            inst.mounting_type = MountingType.DOOR
            bound_w = enc.width
            bound_h = enc.height
        else:
            bound_w = enc.mounting_plate_width
            bound_h = enc.mounting_plate_height

        target_x = max(0.0, min(scene_x, bound_w - inst.width))
        target_y = max(0.0, min(scene_y, bound_h - inst.height))

        if self.grid_snap_enabled:
            target_x = round(target_x / self.grid_step) * self.grid_step
            target_y = round(target_y / self.grid_step) * self.grid_step

        inst.x = target_x
        inst.y = target_y
        inst.is_placed = True

        valid, reason = CollisionDetector.validate_position(
            inst, self.project.physical_instances, bound_w, bound_h
        )

        comp_item = Component2DItem(inst, self)
        self.scene.addItem(comp_item)
        self._item_map[inst.id] = comp_item
        comp_item.setSelected(True)

        if not valid:
            comp_item._flash_red_and_notify(reason)

        self._refresh_palette()
        self._update_status_bar()
        self._update_undo_redo_ui()

    def _run_auto_layout(self):
        """Automatically arrange and place all components into an optimal industrial 2D layout."""
        if not self.project:
            return

        if self.undo_manager:
            self.undo_manager.push_state()

        has_manual_rails = any(not r.id.startswith("din_rail_") for r in self.project.din_rails)
        has_manual_ducts = any(not d.id.startswith("duct_") for d in self.project.wiring_ducts)
        use_rails = self.project.din_rails if has_manual_rails else None
        use_ducts = self.project.wiring_ducts if has_manual_ducts else None

        # If all components were cleared/unplaced, calculate optimal compact enclosure for current BOM
        all_unplaced = all(not i.is_placed for i in self.project.physical_instances if not i.is_external)
        target_enc = None if all_unplaced else self.project.enclosure

        enc, placed_instances, rails, ducts, warnings = AutoLayoutEngine.generate_layout(
            self.project.physical_instances,
            target_enclosure=target_enc,
            existing_rails=use_rails,
            existing_ducts=use_ducts
        )

        overflow_warnings = [w for w in warnings if "PANEL SIZE INSUFFICIENT" in w]
        if overflow_warnings:
            reply = QMessageBox.warning(
                self,
                "Panel Size Insufficient",
                f"{overflow_warnings[0]}\n\n"
                "Would you like to expand the panel to the recommended size to fit all components?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                enc, placed_instances, rails, ducts, warnings = AutoLayoutEngine.generate_layout(
                    self.project.physical_instances,
                    target_enclosure=None,
                    existing_rails=use_rails,
                    existing_ducts=use_ducts
                )
                self.project.enclosure = enc

        self.project.enclosure = enc
        self.project.physical_instances = placed_instances
        self.project.din_rails = rails
        self.project.wiring_ducts = ducts
        self.project.layout_mode = "AUTOMATIC"

        self._rebuild_scene()
        self._refresh_palette()
        self._update_status_bar()
        self._fit_view()
        self._update_undo_redo_ui()

        placed_count = sum(1 for i in placed_instances if i.is_placed and not i.is_external)
        self.show_status_message(f"Auto-placement complete: {placed_count} components arranged across Plate (Z) and Door (Z+1).")

    def _unplace_all(self):
        """Clear all components from the mounting plate and return them to the unplaced palette."""
        if not self.project:
            return

        if self.undo_manager:
            self.undo_manager.push_state()

        for inst in self.project.physical_instances:
            inst.is_placed = False

        self.project.din_rails.clear()
        self.project.wiring_ducts.clear()
        self.project.layout_mode = "MANUAL"

        self._rebuild_scene()
        self._refresh_palette()
        self._update_status_bar()
        self._update_undo_redo_ui()
        self.show_status_message("All components cleared. Ready for manual placement.")

    def on_item_updated(self, instance: PhysicalInstance):
        self._revalidate_and_highlight()
        self._apply_selection_filter()
        self._update_status_bar()

    def _revalidate_and_highlight(self):
        """Re-validate boundaries and collisions for all items and update visuals."""
        if not self.project:
            return

        plate_w = self.project.enclosure.mounting_plate_width
        plate_h = self.project.enclosure.mounting_plate_height

        violations = CollisionDetector.check_all_collisions(self.project.physical_instances)
        colliding_ids = set()
        for c1, c2, msg in violations:
            if "PHYSICAL COLLISION" in msg:
                colliding_ids.add(c1)
                colliding_ids.add(c2)

        # Check boundary overflow
        for inst in self.project.physical_instances:
            if not inst.is_placed or inst.is_external:
                continue
            item = self._item_map.get(inst.id)
            if not item:
                continue

            eff_w = inst.height if int(inst.rotation) in (90, 270) else inst.width
            eff_h = inst.width if int(inst.rotation) in (90, 270) else inst.height

            is_door = (getattr(inst, "surface", "Z").upper() == "Z+1")
            limit_w = self.project.enclosure.width if is_door else plate_w
            limit_h = self.project.enclosure.height if is_door else plate_h

            out_of_bounds = (inst.x < 0 or inst.x + eff_w > limit_w or
                             inst.y < 0 or inst.y + eff_h > limit_h)

            item._update_appearance(is_colliding=(inst.id in colliding_ids or out_of_bounds))

    def _open_resize_dialog(self):
        """Allow user to dynamically change panel dimensions from 2D workspace."""
        if not self.project or not self.project.enclosure:
            return

        pre_snap = self.undo_manager.capture_snapshot() if self.undo_manager else None
        dlg = PanelResizeDialog(self.project.enclosure, self)
        if dlg.exec():
            if self.undo_manager and pre_snap:
                self.undo_manager.push_state(pre_snap)
                self._update_undo_redo_ui()

            new_w, new_h, new_d = dlg.get_dimensions()
            self.project.enclosure.width = new_w
            self.project.enclosure.height = new_h
            self.project.enclosure.depth = new_d

            # Rebuild canvas boundaries
            self._rebuild_scene()
            self._revalidate_and_highlight()
            self._apply_selection_filter()
            self._update_status_bar()
            self._fit_view()

            # Check if any placed component now exceeds boundaries
            plate_w = self.project.enclosure.mounting_plate_width
            plate_h = self.project.enclosure.mounting_plate_height
            violating = []
            for inst in self.project.physical_instances:
                if inst.is_placed and not inst.is_external:
                    eff_w = inst.height if int(inst.rotation) in (90, 270) else inst.width
                    eff_h = inst.width if int(inst.rotation) in (90, 270) else inst.height
                    limit_w = self.project.enclosure.width if getattr(inst, "surface", "Z") == "Z+1" else plate_w
                    limit_h = self.project.enclosure.height if getattr(inst, "surface", "Z") == "Z+1" else plate_h
                    if inst.x + eff_w > limit_w or inst.y + eff_h > limit_h:
                        violating.append(inst.name)

            if violating:
                QMessageBox.warning(
                    self,
                    "Boundary Warning",
                    f"The enclosure was resized to {int(new_w)}×{int(new_h)}×{int(new_d)} mm.\n"
                    f"{len(violating)} components currently exceed boundaries:\n"
                    f"• {', '.join(violating[:4])}\n\n"
                    f"Violating components are highlighted in red. Please reposition them."
                )

    def show_status_message(self, message: str, is_warning: bool = False):
        self.lbl_collision_status.setText(message)
        if is_warning:
            self.lbl_collision_status.setStyleSheet("color: #F43F5E; font-weight: 700; font-size: 12px; margin-left: 15px;")
        else:
            self.lbl_collision_status.setStyleSheet("color: #2DD4BF; font-weight: 700; font-size: 12px; margin-left: 15px;")

    def _update_status_bar(self):
        if not self.project or not self.project.enclosure:
            return

        enc = self.project.enclosure
        surf_label = "Mounting Plate (Z View)" if self.active_surface == "Z" else "Outer Door (Z+1 View)"
        self.lbl_panel_dims.setText(f"Enclosure: {int(enc.width)} × {int(enc.height)} × {int(enc.depth)} mm")
        self.lbl_plate_dims.setText(f"Active View: {surf_label}")

        placed_count = sum(1 for i in self.project.physical_instances if i.is_placed and not i.is_external)
        total_count = sum(1 for i in self.project.physical_instances if not i.is_external)
        pct = int(placed_count / total_count * 100) if total_count > 0 else 0
        self.lbl_placed_count.setText(f"Placed: {placed_count} / {total_count} ({pct}%)")

    def _on_generate_3d(self):
        placed = [i for i in self.project.physical_instances if i.is_placed and not i.is_external]
        if not placed:
            QMessageBox.warning(
                self,
                "No Placed Components",
                "Please place at least one component from the left sidebar onto the mounting plate before generating the 3D view."
            )
            return

        self.generate_3d_requested.emit()


    # =========================================================================
    # MEASUREMENT TOOL IMPLEMENTATION (Edge-to-Edge & Center-to-Center)
    # =========================================================================
    def toggle_measure_tool(self, checked: bool):
        """Toggle measurement mode on or off."""
        self.measure_mode_active = checked
        if checked:
            self.scene.clearSelection()
            self.view.setCursor(Qt.CrossCursor)
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.view.setMouseTracking(True)
            self.measure_start_point = None
            self.measure_start_label = ""
            self.show_status_message("Measure Tool Active: Click first point (snaps to component edge or center). Press Esc or M to exit.")
        else:
            self.view.setCursor(Qt.ArrowCursor)
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self._clear_measure_preview()
            self.show_status_message("Measure Tool deactivated.")

    def clear_measurements(self):
        """Remove all committed measurement lines and callout badges from canvas."""
        for item in self.measure_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self.measure_items.clear()
        self._clear_measure_preview()
        self.measure_start_point = None
        self.measure_start_label = ""
        self.show_status_message("Measurements cleared.")

    def _clear_measure_preview(self):
        """Remove temporary hover preview items."""
        for item in self.measure_preview_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self.measure_preview_items.clear()

    def find_nearest_snap_point(self, scene_pos: QPointF, snap_threshold: float = 28.0) -> Tuple[QPointF, str]:
        """
        Finds the nearest snap candidate (Component Edge, Center, DIN rail edge/center, or plate border)
        within the snap_threshold radius in scene coordinates.
        """
        candidates: List[Tuple[QPointF, str]] = []

        # 1. Placed BOM Components on active surface
        for item in self._item_map.values():
            if not item.isVisible():
                continue
            inst = item.instance
            w = inst.effective_width
            h = inst.effective_height
            x = item.pos().x()
            y = item.pos().y()
            name = inst.part_number or inst.name

            candidates.append((QPointF(x + w / 2.0, y + h / 2.0), f"{name} [Center]"))
            candidates.append((QPointF(x + w / 2.0, y), f"{name} [Top Edge]"))
            candidates.append((QPointF(x + w / 2.0, y + h), f"{name} [Bottom Edge]"))
            candidates.append((QPointF(x, y + h / 2.0), f"{name} [Left Edge]"))
            candidates.append((QPointF(x + w, y + h / 2.0), f"{name} [Right Edge]"))
            candidates.append((QPointF(x, y), f"{name} [Top-Left]"))
            candidates.append((QPointF(x + w, y), f"{name} [Top-Right]"))
            candidates.append((QPointF(x, y + h), f"{name} [Bottom-Left]"))
            candidates.append((QPointF(x + w, y + h), f"{name} [Bottom-Right]"))

        # 2. DIN Rails (on Mounting Plate)
        if self.active_surface == "Z":
            for rail_item in self._rail_map.values():
                if not rail_item.isVisible():
                    continue
                rail = rail_item.rail
                rw = rail.effective_width
                rh = rail.effective_height
                rx = rail_item.pos().x()
                ry = rail_item.pos().y()

                candidates.append((QPointF(rx + rw / 2.0, ry + rh / 2.0), f"{rail.name} [Center]"))
                candidates.append((QPointF(rx, ry + rh / 2.0), f"{rail.name} [Left Edge]"))
                candidates.append((QPointF(rx + rw, ry + rh / 2.0), f"{rail.name} [Right Edge]"))
                candidates.append((QPointF(rx + rw / 2.0, ry), f"{rail.name} [Top Edge]"))
                candidates.append((QPointF(rx + rw / 2.0, ry + rh), f"{rail.name} [Bottom Edge]"))

            for duct_item in self._duct_map.values():
                if not duct_item.isVisible():
                    continue
                duct = duct_item.duct
                dw = duct.effective_width
                dh = duct.effective_height
                dx = duct_item.pos().x()
                dy = duct_item.pos().y()

                candidates.append((QPointF(dx + dw / 2.0, dy + dh / 2.0), f"{duct.name} [Center]"))
                candidates.append((QPointF(dx, dy + dh / 2.0), f"{duct.name} [Left Edge]"))
                candidates.append((QPointF(dx + dw, dy + dh / 2.0), f"{duct.name} [Right Edge]"))
                candidates.append((QPointF(dx + dw / 2.0, dy), f"{duct.name} [Top Edge]"))
                candidates.append((QPointF(dx + dw / 2.0, dy + dh), f"{duct.name} [Bottom Edge]"))

        # 3. Canvas Frame / Outer Boundary
        if self.project and self.project.enclosure:
            enc = self.project.enclosure
            pw = enc.width if self.active_surface == "Z+1" else enc.mounting_plate_width
            ph = enc.height if self.active_surface == "Z+1" else enc.mounting_plate_height
            lbl = "Door" if self.active_surface == "Z+1" else "Plate"

            candidates.append((QPointF(0, 0), f"{lbl} Origin (0,0)"))
            candidates.append((QPointF(pw / 2.0, ph / 2.0), f"{lbl} Center"))
            candidates.append((QPointF(pw / 2.0, 0), f"{lbl} Top Center"))
            candidates.append((QPointF(pw / 2.0, ph), f"{lbl} Bottom Center"))
            candidates.append((QPointF(0, ph / 2.0), f"{lbl} Left Center"))
            candidates.append((QPointF(pw, ph / 2.0), f"{lbl} Right Center"))
            candidates.append((QPointF(pw, 0), f"{lbl} Top-Right"))
            candidates.append((QPointF(0, ph), f"{lbl} Bottom-Left"))
            candidates.append((QPointF(pw, ph), f"{lbl} Bottom-Right"))

            if self.active_surface == "Z+1" and getattr(enc, "door_type", "SINGLE") == "DOUBLE_VERTICAL":
                candidates.append((QPointF(pw / 2.0, 0), "Door Split Seam Top"))
                candidates.append((QPointF(pw / 2.0, ph / 2.0), "Door Split Seam Center"))
                candidates.append((QPointF(pw / 2.0, ph), "Door Split Seam Bottom"))

        # Determine closest candidate point
        best_pt = scene_pos
        best_label = f"({int(scene_pos.x())}, {int(scene_pos.y())})"
        best_dist = float("inf")

        for cand_pt, cand_label in candidates:
            dx = scene_pos.x() - cand_pt.x()
            dy = scene_pos.y() - cand_pt.y()
            d = (dx * dx + dy * dy) ** 0.5
            if d < best_dist:
                best_dist = d
                best_pt = cand_pt
                best_label = cand_label

        if best_dist <= snap_threshold:
            return best_pt, best_label

        return scene_pos, f"Point ({int(scene_pos.x())}, {int(scene_pos.y())})"

    def update_measure_hover(self, scene_pos: QPointF):
        """Update live snap indicator and dynamic rubberband dimension line during mouse move."""
        self._clear_measure_preview()

        pt, label = self.find_nearest_snap_point(scene_pos)

        # Draw high-visibility snap crosshair indicator
        ring = self.scene.addEllipse(pt.x() - 6, pt.y() - 6, 12, 12, QPen(QColor("#FF9A4E"), 2.0), QBrush(Qt.NoBrush))
        ring.setZValue(130)
        h_line = self.scene.addLine(pt.x() - 10, pt.y(), pt.x() + 10, pt.y(), QPen(QColor("#FF9A4E"), 1.5))
        h_line.setZValue(130)
        v_line = self.scene.addLine(pt.x(), pt.y() - 10, pt.x(), pt.y() + 10, QPen(QColor("#FF9A4E"), 1.5))
        v_line.setZValue(130)

        txt = self.scene.addText(f"{label}", QFont("Segoe UI", 8, QFont.Bold))
        txt.setDefaultTextColor(QColor("#E88536"))
        txt.setPos(pt.x() + 10, pt.y() - 16)
        txt.setZValue(131)

        self.measure_preview_items.extend([ring, h_line, v_line, txt])

        # If 1st point is already clicked, draw dynamic dashed line to current point
        if self.measure_start_point is not None:
            p1 = self.measure_start_point
            p2 = pt
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            dist = (dx * dx + dy * dy) ** 0.5

            d_line = self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(QColor("#FF9A4E"), 2.0, Qt.DashLine))
            d_line.setZValue(125)

            mid_x = (p1.x() + p2.x()) / 2.0
            mid_y = (p1.y() + p2.y()) / 2.0

            badge_bg = self.scene.addRect(mid_x - 55, mid_y - 13, 110, 26, QPen(QColor("#FF9A4E"), 1.5), QBrush(QColor("#FFFFFF")))
            badge_bg.setZValue(126)
            badge_txt = self.scene.addText(f"{dist:.1f} mm", QFont("Segoe UI", 9, QFont.Bold))
            badge_txt.setDefaultTextColor(QColor("#111C24"))
            badge_txt.setPos(mid_x - 45, mid_y - 14)
            badge_txt.setZValue(127)

            self.measure_preview_items.extend([d_line, badge_bg, badge_txt])
            self.show_status_message(f"Measuring: {dist:.1f} mm (ΔX: {abs(dx):.1f} mm, ΔY: {abs(dy):.1f} mm) to {label}")

    def handle_measure_click(self, scene_pos: QPointF):
        """Handle 1st click (start point) and 2nd click (stop point) for measurement."""
        pt, label = self.find_nearest_snap_point(scene_pos)

        if self.measure_start_point is None:
            # First Click: Set Start Point
            self.measure_start_point = pt
            self.measure_start_label = label

            start_dot = self.scene.addEllipse(pt.x() - 6, pt.y() - 6, 12, 12, QPen(QColor("#FF9A4E"), 2.0), QBrush(QColor("#FF9A4E")))
            start_dot.setZValue(115)
            start_txt = self.scene.addText(f"Start: {label}", QFont("Segoe UI", 8, QFont.Bold))
            start_txt.setDefaultTextColor(QColor("#E88536"))
            start_txt.setPos(pt.x() + 10, pt.y() - 16)
            start_txt.setZValue(116)
            self.measure_items.extend([start_dot, start_txt])

            self.show_status_message(f"Measure: Start set at {label} ({pt.x():.1f}, {pt.y():.1f}) mm. Click second point (edge or center).")
        else:
            # Second Click: Set Stop Point and Commit Dimension Line
            p1 = self.measure_start_point
            p2 = pt
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            dist = (dx * dx + dy * dy) ** 0.5

            # Dimension Line
            dim_line = self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(QColor("#FF9A4E"), 2.5))
            dim_line.setZValue(118)

            # End marker dot
            end_dot = self.scene.addEllipse(p2.x() - 6, p2.y() - 6, 12, 12, QPen(QColor("#FF9A4E"), 2.0), QBrush(QColor("#FF9A4E")))
            end_dot.setZValue(119)

            # End tick marks
            import math
            angle = math.atan2(dy, dx)
            perp = angle + math.pi / 2.0
            tick_len = 9.0
            tx1 = math.cos(perp) * tick_len
            ty1 = math.sin(perp) * tick_len

            tick_start = self.scene.addLine(p1.x() - tx1, p1.y() - ty1, p1.x() + tx1, p1.y() + ty1, QPen(QColor("#FF9A4E"), 2.0))
            tick_start.setZValue(119)
            tick_end = self.scene.addLine(p2.x() - tx1, p2.y() - ty1, p2.x() + tx1, p2.y() + ty1, QPen(QColor("#FF9A4E"), 2.0))
            tick_end.setZValue(119)

            # Badge showing Distance, Delta X and Delta Y
            mid_x = (p1.x() + p2.x()) / 2.0
            mid_y = (p1.y() + p2.y()) / 2.0

            badge_bg = self.scene.addRect(mid_x - 75, mid_y - 20, 150, 40, QPen(QColor("#FF9A4E"), 1.8), QBrush(QColor("#FFFFFF")))
            badge_bg.setZValue(120)

            badge_txt = self.scene.addText(
                f"Dist: {dist:.1f} mm\nΔX: {abs(dx):.1f} mm | ΔY: {abs(dy):.1f} mm",
                QFont("Segoe UI", 8, QFont.Bold)
            )
            badge_txt.setDefaultTextColor(QColor("#111C24"))
            badge_txt.setPos(mid_x - 70, mid_y - 20)
            badge_txt.setZValue(121)

            self.measure_items.extend([dim_line, end_dot, tick_start, tick_end, badge_bg, badge_txt])

            self.show_status_message(
                f"Measured: {dist:.1f} mm (ΔX: {abs(dx):.1f} mm, ΔY: {abs(dy):.1f} mm) from {self.measure_start_label} to {label}. Click to start next measurement."
            )

            # Reset start point so next click can begin another measurement
            self.measure_start_point = None
            self.measure_start_label = ""
            self._clear_measure_preview()
