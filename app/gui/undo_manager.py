"""
Undo/Redo Manager for AI Electrical Panel Designer.
Maintains history capped at 5 steps (MAX_STEPS = 5) for panel placement,
workspace objects, and BOM operations.
"""
from typing import Dict, Any, List, Optional, Callable
from app.models.project import ProjectData
from app.models.bom import BOM
from app.models.component import PhysicalInstance
from app.models.enclosure import Enclosure, DINRail, WiringDuct

MAX_UNDO_STEPS = 5


class UndoRedoManager:
    """
    Manages undo/redo state stacks capped at 5 steps.
    Captures complete snapshots of BOM, physical instances, DIN rails,
    wiring ducts, and enclosure settings.
    """
    def __init__(self, get_project_fn: Callable[[], ProjectData], on_state_restored_fn: Callable[[], None], max_steps: int = MAX_UNDO_STEPS):
        self.get_project = get_project_fn
        self.on_state_restored = on_state_restored_fn
        self.max_steps = max_steps
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []
        self._is_undoing_redoing = False

    def capture_snapshot(self) -> Dict[str, Any]:
        """Capture a clean deep snapshot dictionary of current project state."""
        proj = self.get_project()
        if not proj:
            return {}
        return {
            "project_name": proj.project_name,
            "bom": [c.to_dict() for c in proj.bom.items],
            "physical_instances": [i.to_dict() for i in proj.physical_instances],
            "din_rails": [r.to_dict() for r in proj.din_rails],
            "wiring_ducts": [d.to_dict() for d in proj.wiring_ducts],
            "enclosure": proj.enclosure.to_dict() if proj.enclosure else {},
            "layout_mode": proj.layout_mode,
        }

    def push_state(self, pre_snapshot: Optional[Dict[str, Any]] = None):
        """
        Record a state onto the undo stack.
        If pre_snapshot is provided, that state is recorded (useful for operations
        where snapshot was taken right before a drag/mutation).
        """
        if self._is_undoing_redoing:
            return

        snapshot = pre_snapshot if pre_snapshot is not None else self.capture_snapshot()
        if not snapshot:
            return

        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.max_steps:
            self.undo_stack.pop(0)

        # A new action always clears the redo stack
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo(self) -> bool:
        """Roll back to the previous state (up to max_steps steps)."""
        if not self.can_undo() or self._is_undoing_redoing:
            return False

        self._is_undoing_redoing = True
        try:
            current_state = self.capture_snapshot()
            self.redo_stack.append(current_state)
            if len(self.redo_stack) > self.max_steps:
                self.redo_stack.pop(0)

            prev_state = self.undo_stack.pop()
            self._apply_snapshot(prev_state)
            self.on_state_restored()
            return True
        finally:
            self._is_undoing_redoing = False

    def redo(self) -> bool:
        """Re-apply a previously undone state (up to max_steps steps)."""
        if not self.can_redo() or self._is_undoing_redoing:
            return False

        self._is_undoing_redoing = True
        try:
            current_state = self.capture_snapshot()
            self.undo_stack.append(current_state)
            if len(self.undo_stack) > self.max_steps:
                self.undo_stack.pop(0)

            next_state = self.redo_stack.pop()
            self._apply_snapshot(next_state)
            self.on_state_restored()
            return True
        finally:
            self._is_undoing_redoing = False

    def _apply_snapshot(self, snap: Dict[str, Any]):
        proj = self.get_project()
        if not proj or not snap:
            return

        if "project_name" in snap:
            proj.project_name = snap["project_name"]
        proj.bom = BOM.from_list(snap.get("bom", []))
        proj.physical_instances = [PhysicalInstance.from_dict(d) for d in snap.get("physical_instances", [])]
        proj.din_rails = [DINRail.from_dict(d) for d in snap.get("din_rails", [])]
        proj.wiring_ducts = [WiringDuct.from_dict(d) for d in snap.get("wiring_ducts", [])]
        if snap.get("enclosure"):
            proj.enclosure = Enclosure.from_dict(snap["enclosure"])
        proj.layout_mode = snap.get("layout_mode", "AUTOMATIC")

    def clear(self):
        """Clear all undo and redo history."""
        self.undo_stack.clear()
        self.redo_stack.clear()
