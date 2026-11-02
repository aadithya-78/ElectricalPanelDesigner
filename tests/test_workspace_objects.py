"""
Unit tests for Task 1 & Task 2:
- Workspace objects (DIN rails & wiring ducts) in 2D workspace
- Movable, selectable, and editable properties
- Separation of workspace objects from BOM
- Auto-placement preserving existing manual objects without duplication
"""
import pytest
from app.models.component import Component, PhysicalInstance, MountingType
from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.models.bom import BOM
from app.models.project import ProjectData
from app.geometry.auto_layout import AutoLayoutEngine
from app.export.json_export import JSONExporter


def test_din_rail_and_duct_models():
    """Verify DINRail and WiringDuct data model attributes and serialization."""
    rail = DINRail(
        id="rail_test",
        name="Main DIN Rail",
        x=50.0,
        y=300.0,
        z=0.0,
        length=600.0,
        height=35.0,
        depth=7.5,
        orientation="HORIZONTAL",
        rotation=0.0,
        is_locked=False
    )
    assert rail.effective_width == 600.0
    assert rail.effective_height == 35.0

    # Rotate 90 degrees
    rail.rotation = 90.0
    assert rail.effective_width == 35.0
    assert rail.effective_height == 600.0

    # Serialization roundtrip
    d = rail.to_dict()
    assert d["rotation"] == 90.0
    assert d["is_locked"] is False

    restored = DINRail.from_dict(d)
    assert restored.id == "rail_test"
    assert restored.rotation == 90.0

    # Wiring duct
    duct = WiringDuct(
        id="duct_test",
        name="Vertical Duct",
        x=20.0,
        y=50.0,
        z=0.0,
        width=40.0,
        height=60.0,
        length=800.0,
        orientation="VERTICAL",
        rotation=90.0,
        is_locked=True
    )
    assert duct.effective_width == 40.0
    assert duct.effective_height == 800.0

    dd = duct.to_dict()
    assert dd["rotation"] == 90.0
    assert dd["is_locked"] is True

    restored_duct = WiringDuct.from_dict(dd)
    assert restored_duct.id == "duct_test"
    assert restored_duct.is_locked is True


def test_bom_strict_exclusion_of_workspace_objects():
    """Verify DIN rails, wiring ducts, and mounting plates are NEVER part of BOM items."""
    proj = ProjectData("18 kW ATV630 Test")
    
    # Add BOM components
    proj.bom.add_item(Component(item_no=1, name="Schneider ATV630 18kW", category="Power", manufacturer="Schneider", part_number="ATV630U18N4", quantity=1))
    proj.bom.add_item(Component(item_no=2, name="MCCB 80A 3P", category="Power", manufacturer="Schneider", part_number="LV429630", quantity=1))

    # Add workspace objects
    proj.din_rails.append(DINRail(id="r1", name="DIN Rail Row 1", x=50.0, y=400.0, length=600.0))
    proj.wiring_ducts.append(WiringDuct(id="d1", name="Horizontal Duct", x=50.0, y=340.0, length=600.0))
    proj.enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0)

    # 1. BOM items should strictly contain only the 2 electrical items
    assert len(proj.bom.items) == 2
    for item in proj.bom.items:
        assert "din rail" not in item.name.lower()
        assert "duct" not in item.name.lower()
        assert "plate" not in item.name.lower()

    # 2. Workspace objects live in their own lists
    assert len(proj.din_rails) == 1
    assert len(proj.wiring_ducts) == 1
    assert proj.enclosure.mounting_plate_width == 740.0


def test_auto_layout_preserves_manually_added_rails_and_ducts():
    """Verify auto-placement respects manually added rails and ducts without creating duplicates."""
    proj = ProjectData("Manual Preservation Test")
    enc = Enclosure(width=800.0, height=1200.0, depth=400.0)

    # Manually add 2 DIN rails and 1 wiring duct
    manual_rail_1 = DINRail(id="manual_r1", name="Manual Rail 1", x=60.0, y=500.0, length=620.0)
    manual_rail_2 = DINRail(id="manual_r2", name="Manual Rail 2", x=60.0, y=700.0, length=620.0)
    manual_duct = WiringDuct(id="manual_d1", name="Manual Duct", x=60.0, y=450.0, length=620.0)

    proj.din_rails = [manual_rail_1, manual_rail_2]
    proj.wiring_ducts = [manual_duct]

    # Add DIN mounted instances
    instances = [
        PhysicalInstance(id="c1", component_item_no=1, name="SMPS 24V", category="Control", manufacturer="Schneider", part_number="ABL8REM24050", width=54.0, height=120.0, depth=120.0, mounting_type=MountingType.DIN),
        PhysicalInstance(id="c2", component_item_no=2, name="MCB 2P 6A", category="Control", manufacturer="Schneider", part_number="A9F74206", width=36.0, height=85.0, depth=78.5, mounting_type=MountingType.DIN),
        PhysicalInstance(id="c3", component_item_no=3, name="Contactor 50A", category="Power", manufacturer="Schneider", part_number="LC1D50A", width=55.0, height=122.0, depth=120.0, mounting_type=MountingType.DIN)
    ]

    new_enc, placed_instances, rails, ducts, warnings = AutoLayoutEngine.generate_layout(
        instances,
        target_enclosure=enc,
        existing_rails=proj.din_rails,
        existing_ducts=proj.wiring_ducts
    )

    # Must preserve the exact manual rails and ducts
    rail_ids = [r.id for r in rails]
    assert "manual_r1" in rail_ids
    assert "manual_r2" in rail_ids
    assert len(rails) == 2, "Should reuse manual rails rather than creating duplicates"

    duct_ids = [d.id for d in ducts]
    assert "manual_d1" in duct_ids
    assert len(ducts) == 1, "Should reuse manual duct rather than creating duplicates"

    # All DIN devices must be placed on the manual rails
    assert all(i.is_placed for i in placed_instances)
    assert all(i.din_rail_id in ("manual_r1", "manual_r2") for i in placed_instances)


import sys
from PySide6.QtWidgets import QApplication

def get_app():
    return QApplication.instance() or QApplication(sys.argv)


def test_workspace_editor_add_and_delete_objects():
    """Verify Panel2DEditor can add and delete DIN rails and wiring ducts interactively."""
    _app = get_app()
    from app.gui.panel_2d_editor import Panel2DEditor, DINRail2DItem, WireDuct2DItem

    editor = Panel2DEditor()
    proj = ProjectData("Interactive Workspace Objects Test")
    proj.enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0)
    editor.load_project(proj)

    # 1. Add DIN Rail
    editor.add_workspace_object("din_rail", 80.0, 400.0)
    assert len(proj.din_rails) == 1
    assert len(editor._rail_map) == 1
    rail = proj.din_rails[0]
    assert rail.x == 80.0
    assert rail.y == 400.0
    rail_item = editor._rail_map[rail.id]
    assert isinstance(rail_item, DINRail2DItem)

    # 2. Add Horizontal Duct
    editor.add_workspace_object("wire_duct_h", 60.0, 340.0)
    assert len(proj.wiring_ducts) == 1
    assert len(editor._duct_map) == 1
    duct = proj.wiring_ducts[0]
    assert duct.x == 60.0
    assert duct.y == 340.0
    duct_item = editor._duct_map[duct.id]
    assert isinstance(duct_item, WireDuct2DItem)

    # 3. Add Vertical Duct
    editor.add_workspace_object("wire_duct_v", 30.0, 60.0)
    assert len(proj.wiring_ducts) == 2
    assert len(editor._duct_map) == 2

    # 4. Delete selected item
    editor.scene.clearSelection()
    rail_item.setSelected(True)
    editor.delete_selected_items()
    assert len(proj.din_rails) == 0
    assert len(editor._rail_map) == 0

    # 5. Delete duct directly
    editor.delete_wiring_duct(duct)
    assert len(proj.wiring_ducts) == 1


def test_kicad_properties_dialog_edit_rail_and_duct():
    """Verify KiCadPropertiesDialog allows editing dimensions, position, and rotation of rails & ducts."""
    _app = get_app()
    from app.gui.panel_2d_editor import Panel2DEditor, KiCadPropertiesDialog

    editor = Panel2DEditor()
    proj = ProjectData("Properties Dialog Test")
    proj.enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0)
    editor.load_project(proj)

    # Test DIN rail editing
    rail = DINRail(id="r1", name="Test Rail", x=100.0, y=300.0, length=500.0, height=35.0, depth=7.5)
    proj.din_rails.append(rail)

    dlg = KiCadPropertiesDialog(rail, editor)
    dlg.name_edit.setText("Updated Main Rail")
    dlg.spin_x.setValue(120.0)
    dlg.spin_y.setValue(350.0)
    dlg.spin_w.setValue(550.0) # Length
    dlg.combo_rot.setCurrentText("90°")
    dlg._validate_and_apply()

    assert rail.name == "Updated Main Rail"
    assert rail.x == 120.0
    assert rail.y == 350.0
    assert rail.length == 550.0
    assert rail.rotation == 90.0
    assert rail.orientation == "VERTICAL"


def test_load_demo_project_and_verify_interactions():
    """Verify Demo/18kW_Motor_Drive.json loads in Panel2DEditor and all objects are interactive."""
    import os
    _app = get_app()
    from app.gui.panel_2d_editor import Panel2DEditor

    demo_path = os.path.join("Demo", "18kW_Motor_Drive.json")
    assert os.path.exists(demo_path), "Demo/18kW_Motor_Drive.json must exist"

    project = JSONExporter.import_project(demo_path)
    assert project.name == "18kW_Motor_Drive"
    assert len(project.bom.items) == 25
    assert len(project.din_rails) == 3
    assert len(project.wiring_ducts) == 5

    # Check that no DIN rail, wiring duct, or plate is in BOM
    for item in project.bom.items:
        n = item.name.lower()
        assert "din rail" not in n
        assert "duct" not in n
        assert "mounting plate" not in n

    editor = Panel2DEditor()
    editor.load_project(project)

    # Verify editor scene contains items for rails and ducts
    assert len(editor._rail_map) == 3
    assert len(editor._duct_map) == 5

    # Test that each rail item is selectable and movable
    for rail_id, item in editor._rail_map.items():
        assert item.flags() & item.GraphicsItemFlag.ItemIsMovable
        assert item.flags() & item.GraphicsItemFlag.ItemIsSelectable

    # Test that each duct item is selectable and movable
    for duct_id, item in editor._duct_map.items():
        assert item.flags() & item.GraphicsItemFlag.ItemIsMovable
        assert item.flags() & item.GraphicsItemFlag.ItemIsSelectable


