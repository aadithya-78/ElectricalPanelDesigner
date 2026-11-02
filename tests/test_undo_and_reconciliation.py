"""
Unit and integration tests for Undo/Redo (capped at 5 steps) and
non-destructive BOM-to-2D instance reconciliation.
"""
import sys
import pytest
from PySide6.QtWidgets import QApplication
from app.models.project import ProjectData
from app.models.bom import BOM
from app.models.component import Component, ComponentCategory, MountingType, PhysicalInstance
from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.gui.undo_manager import UndoRedoManager, MAX_UNDO_STEPS
from app.gui.panel_2d_editor import Panel2DEditor, Component2DItem


def get_qapp():
    return QApplication.instance() or QApplication(sys.argv)


def create_sample_project():
    proj = ProjectData("Test Panel")
    proj.enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0)

    # 3 Components
    c1 = Component(
        item_no=1,
        category=ComponentCategory.POWER,
        name="ATV630 Drive",
        manufacturer="Schneider Electric",
        part_number="ATV630D18N4",
        quantity=1,
        width_mm=211.0,
        height_mm=546.0,
        depth_mm=232.0,
        mounting_type=MountingType.PLATE
    )
    c2 = Component(
        item_no=2,
        category=ComponentCategory.POWER,
        name="Main MCCB 50A",
        manufacturer="Schneider Electric",
        part_number="LV429630",
        quantity=1,
        width_mm=105.0,
        height_mm=161.0,
        depth_mm=86.0,
        mounting_type=MountingType.PLATE
    )
    c3 = Component(
        item_no=3,
        category=ComponentCategory.CONTROL,
        name="Terminal Block",
        manufacturer="Phoenix Contact",
        part_number="UT-4",
        quantity=5,
        width_mm=6.2,
        height_mm=47.7,
        depth_mm=47.5,
        mounting_type=MountingType.DIN
    )
    proj.bom = BOM([c1, c2, c3])

    # Initial reconciliation
    proj.reconcile_instances_with_bom()
    return proj


def test_initial_reconciliation():
    proj = create_sample_project()
    # 1 drive + 1 mccb + 5 terminals = 7 instances
    assert len(proj.physical_instances) == 7
    for inst in proj.physical_instances:
        assert not inst.is_placed
        assert inst.x == 0.0
        assert inst.y == 0.0


def test_bom_deletion_erases_only_deleted_component():
    proj = create_sample_project()

    # Place components on mounting plate
    inst_drive = next(i for i in proj.physical_instances if "ATV630" in i.name)
    inst_drive.is_placed = True
    inst_drive.x = 100.0
    inst_drive.y = 150.0

    inst_mccb = next(i for i in proj.physical_instances if "MCCB" in i.name)
    inst_mccb.is_placed = True
    inst_mccb.x = 350.0
    inst_mccb.y = 150.0

    inst_tb = next(i for i in proj.physical_instances if "Terminal" in i.name)
    inst_tb.is_placed = True
    inst_tb.x = 200.0
    inst_tb.y = 700.0

    # Add a DIN rail and wiring duct to workspace
    rail = DINRail(id="rail_1", name="DIN Rail", x=100.0, y=700.0, length=500.0)
    proj.din_rails.append(rail)
    duct = WiringDuct(id="duct_1", name="Wiring Duct", x=50.0, y=100.0, length=800.0)
    proj.wiring_ducts.append(duct)

    # NOW DELETE ONLY MCCB FROM BOM
    deleted = proj.bom.remove_item(2) # Item 2 is MCCB
    assert deleted is True
    assert len(proj.bom.items) == 2

    # Run reconciliation
    proj.reconcile_instances_with_bom()

    # Verify: MCCB is ERASED, Drive and TB remain exactly at their positions!
    mccb_instances = [i for i in proj.physical_instances if "MCCB" in i.name]
    assert len(mccb_instances) == 0, "Deleted component instances must be erased!"

    remaining_drive = next(i for i in proj.physical_instances if "ATV630" in i.name)
    assert remaining_drive.is_placed is True
    assert remaining_drive.x == 100.0
    assert remaining_drive.y == 150.0

    remaining_tb = next(i for i in proj.physical_instances if "Terminal" in i.name and i.is_placed)
    assert remaining_tb.x == 200.0
    assert remaining_tb.y == 700.0

    # DIN rails and wiring ducts MUST be untouched
    assert len(proj.din_rails) == 1
    assert proj.din_rails[0].x == 100.0
    assert len(proj.wiring_ducts) == 1
    assert proj.wiring_ducts[0].y == 100.0


def test_bom_quantity_increase_and_decrease():
    proj = create_sample_project()
    tb_comp = proj.bom.get_item(3) # TB qty was 5

    # Place TB #1
    tb_1 = next(i for i in proj.physical_instances if "Terminal" in i.name)
    tb_1.is_placed = True
    tb_1.x = 250.0
    tb_1.y = 600.0

    # Increase quantity from 5 to 7
    tb_comp.quantity = 7
    proj.reconcile_instances_with_bom()

    tb_instances = [i for i in proj.physical_instances if "Terminal" in i.name]
    assert len(tb_instances) == 7
    # Preserves placed tb_1
    placed = [i for i in tb_instances if i.is_placed]
    assert len(placed) == 1
    assert placed[0].x == 250.0

    # Decrease quantity from 7 to 3
    tb_comp.quantity = 3
    proj.reconcile_instances_with_bom()
    tb_instances = [i for i in proj.physical_instances if "Terminal" in i.name]
    assert len(tb_instances) == 3
    # Placed tb_1 is still preserved
    assert any(i.is_placed and i.x == 250.0 for i in tb_instances)


def test_undo_redo_manager_max_5_steps():
    proj = ProjectData("State 0")
    restored_count = [0]

    def on_restored():
        restored_count[0] += 1

    mgr = UndoRedoManager(lambda: proj, on_restored, max_steps=5)
    assert not mgr.can_undo()
    assert not mgr.can_redo()

    # Perform 7 sequential actions (saving state before each action)
    for i in range(1, 8):
        mgr.push_state()
        proj.project_name = f"State {i}"

    # Current state is "State 7". Stack cap is 5 steps!
    assert len(mgr.undo_stack) == 5
    assert mgr.can_undo()
    assert not mgr.can_redo()

    # Undo 5 times
    undo_names = []
    for _ in range(5):
        assert mgr.can_undo()
        success = mgr.undo()
        assert success
        undo_names.append(proj.project_name)

    # 6th undo must fail (capped at 5 steps)
    assert not mgr.can_undo()
    assert not mgr.undo()
    assert len(undo_names) == 5
    # Sequence of undone states (State 6 down to State 2)
    assert undo_names == ["State 6", "State 5", "State 4", "State 3", "State 2"]

    # Redo 5 times
    redo_names = []
    for _ in range(5):
        assert mgr.can_redo()
        success = mgr.redo()
        assert success
        redo_names.append(proj.project_name)

    assert not mgr.can_redo()
    assert not mgr.redo()
    assert redo_names == ["State 3", "State 4", "State 5", "State 6", "State 7"]


def test_undo_redo_cleared_on_new_action():
    proj = ProjectData("State 0")
    mgr = UndoRedoManager(lambda: proj, lambda: None, max_steps=5)

    mgr.push_state()
    proj.project_name = "State 1"
    mgr.push_state()
    proj.project_name = "State 2"

    # Undo back to State 1
    mgr.undo()
    assert proj.project_name == "State 1"
    assert mgr.can_redo()

    # Perform new action: State 3
    mgr.push_state()
    proj.project_name = "State 3"

    # Redo stack must be cleared
    assert not mgr.can_redo()


def test_panel_2d_editor_sync_and_undo():
    _ = get_qapp()
    editor = Panel2DEditor()
    proj = create_sample_project()
    editor.project = proj

    restored_called = [False]

    def on_restored():
        restored_called[0] = True
        editor._rebuild_scene()
        editor._refresh_palette()

    mgr = UndoRedoManager(lambda: editor.project, on_restored, max_steps=5)
    editor.undo_manager = mgr

    editor.load_project(proj)
    assert len(editor._item_map) == 0 # None placed yet

    # Place drive instance manually
    drive_inst = next(i for i in proj.physical_instances if "ATV630" in i.name)
    editor.place_instance_at(drive_inst.id, 100.0, 100.0)

    assert drive_inst.id in editor._item_map
    assert drive_inst.is_placed is True
    assert mgr.can_undo()
    assert editor.btn_undo.isEnabled()

    # Place MCCB
    mccb_inst = next(i for i in proj.physical_instances if "MCCB" in i.name)
    editor.place_instance_at(mccb_inst.id, 400.0, 100.0)
    assert mccb_inst.id in editor._item_map

    # Delete MCCB from BOM
    proj.bom.remove_item(2)
    proj.reconcile_instances_with_bom()
    editor.sync_instances_from_project()

    # Verify: Drive is STILL placed in 2D scene, MCCB is erased!
    assert drive_inst.id in editor._item_map
    assert mccb_inst.id not in editor._item_map
    assert drive_inst.is_placed is True
    assert drive_inst.x == 100.0
    assert drive_inst.y == 100.0

    # Test Ctrl+Z Undo
    success = mgr.undo()
    assert success is True
    assert restored_called[0] is True
