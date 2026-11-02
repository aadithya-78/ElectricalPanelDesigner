"""
Unit tests for the new 5-step engineering workflow modifications:
1. Excel Catalog loading & component selection (Siemens, Schneider, Phoenix Contact).
2. BOM 3D Component Preview and Surface toggling (Z vs Z+1).
3. CollisionDetector dual-surface isolation (Plate vs Door never collide).
4. AutoLayout zero-overlap placement with door components on Z+1 and plate components on Z.
5. 3D enclosure dual-surface positioning.
"""
import pytest
from app.models.component import Component, PhysicalInstance, MountingType, ComponentCategory
from app.models.enclosure import Enclosure
from app.database.catalog_manager import CatalogManager
from app.geometry.collision_detector import CollisionDetector
from app.geometry.auto_layout import AutoLayoutEngine


def test_catalog_manager_loaded_and_searchable():
    """Verify all 8 Excel catalogs load properly with realistic Siemens, Schneider, Phoenix Contact parts."""
    mgr = CatalogManager.get_instance()
    all_items = mgr.search()
    assert len(all_items) >= 100, f"Expected at least 100 components, got {len(all_items)}"

    # Check manufacturers
    mfrs = {item.get("Manufacturer") for item in all_items}
    assert "Siemens" in mfrs
    assert "Schneider Electric" in mfrs
    assert "Phoenix Contact" in mfrs

    # Search for ATV630 drive
    atv_results = mgr.search(query="ATV630")
    assert len(atv_results) > 0
    atv_comp = mgr.create_component_from_record(atv_results[0], item_no=1)
    assert atv_comp.width_mm > 100
    assert atv_comp.height_mm > 200
    assert atv_comp.surface == "Z"

    # Search for HMI (should default to Z+1 Door)
    hmi_results = mgr.search(query="KTP700")
    assert len(hmi_results) > 0
    hmi_comp = mgr.create_component_from_record(hmi_results[0], item_no=2)
    assert hmi_comp.surface == "Z+1"
    assert hmi_comp.mounting_type == MountingType.DOOR


def test_collision_detector_dual_surface_isolation():
    """Verify components at identical (X, Y) do NOT collide if on different surfaces (Z vs Z+1)."""
    # Item 1 on Mounting Plate (Z)
    inst_plate = PhysicalInstance(
        id="inst_plate_1",
        component_item_no=1,
        name="Schneider ATV630 Drive",
        category="Power",
        manufacturer="Schneider Electric",
        part_number="ATV630D18N4",
        x=100.0,
        y=100.0,
        z=0.0,
        width=226.0,
        height=613.0,
        depth=274.0,
        surface="Z",
        mounting_type=MountingType.PLATE,
        is_placed=True
    )

    # Item 2 on Outer Door (Z+1) with overlapping (X, Y)
    inst_door = PhysicalInstance(
        id="inst_door_1",
        component_item_no=2,
        name="Siemens KTP700 HMI",
        category="Control",
        manufacturer="Siemens",
        part_number="6AV2123-2GB03-0AX0",
        x=120.0,
        y=150.0,
        z=400.0,
        width=214.0,
        height=158.0,
        depth=43.0,
        surface="Z+1",
        mounting_type=MountingType.DOOR,
        is_placed=True
    )

    # Should NOT collide because surfaces are different (Plate vs Door)
    collides = CollisionDetector.check_instance_collision(inst_plate, inst_door)
    assert not collides, "Components on different surfaces (Z vs Z+1) must not collide!"

    # If moved to same surface, they MUST collide
    inst_door.surface = "Z"
    collides_same_surface = CollisionDetector.check_instance_collision(inst_plate, inst_door)
    assert collides_same_surface, "Components overlapping on the same surface must register a collision!"


def test_auto_layout_zero_overlap_and_door_routing():
    """Verify AutoLayoutEngine positions door items on Z+1 and power/modular on Z with 0 collisions."""
    mgr = CatalogManager.get_instance()
    
    # Assemble test project items: Drive + MCCB + Line Reactor + HMI + 3 Pilot Lamps + 2 Pushbuttons + E-Stop + SMPS + MCB
    test_queries = [
        ("ATV630D18N4", 1), # VFD
        ("LV429630", 1),    # MCCB 50A
        ("VW3A4555", 1),    # Line Choke / Reactor (18.5 kW)
        ("6AV2123-2GB03-0AX0", 1), # Siemens KTP700 HMI
        ("XB4BVB3", 3),     # Green Pilot Lamps
        ("XB4BA31", 2),     # Pushbuttons
        ("XB4BS542", 1),    # E-Stop
        ("2904601", 1),     # Phoenix Contact QUINT SMPS
        ("A9F74216", 4)     # MCB 16A
    ]

    components = []
    for idx, (pn, qty) in enumerate(test_queries, 1):
        res = mgr.search(query=pn)
        assert len(res) > 0, f"Part number {pn} not found in catalog"
        comp = mgr.create_component_from_record(res[0], item_no=idx, quantity=qty)
        components.append(comp)

    from app.models.bom import BOM
    bom = BOM(items=components)
    instances = bom.expand_to_instances()

    enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0)

    enc, placed, rails, ducts, warnings = AutoLayoutEngine.generate_layout(
        instances,
        target_enclosure=enclosure
    )

    assert len(placed) == len(instances)
    assert all(i.is_placed for i in placed)

    # Verify door items are on Z+1
    door_instances = [i for i in placed if i.surface == "Z+1"]
    plate_instances = [i for i in placed if i.surface == "Z"]

    assert len(door_instances) >= 7 # HMI + 3 Lamps + 2 Buttons + E-Stop
    assert len(plate_instances) >= 7 # VFD + MCCB + Reactor + SMPS + 4 MCBs

    for di in door_instances:
        assert any(k in (di.name + " " + di.part_number + " " + di.category).lower() for k in ["hmi", "ktp", "lamp", "pilot", "light", "indicator", "button", "push", "stop", "touch", "switch", "control"])
        # Check within door boundaries
        assert di.x >= 0
        assert di.x + di.width <= enclosure.width
        assert di.y >= 0
        assert di.y + di.height <= enclosure.height

    for pi in plate_instances:
        # Check within mounting plate boundaries
        assert pi.x >= 0
        assert pi.x + pi.width <= enclosure.mounting_plate_width
        assert pi.y >= 0
        assert pi.y + pi.height <= enclosure.mounting_plate_height

    # Verify ZERO physical collisions on either surface
    collisions = CollisionDetector.check_all_collisions(placed)
    phys_collisions = [c for c in collisions if "PHYSICAL COLLISION" in c[2]]
    assert len(phys_collisions) == 0, f"Expected 0 physical collisions, got {len(phys_collisions)}: {phys_collisions}"


def test_surface_toggle_and_boundary_checks():
    """Verify switching component between Z and Z+1 adjusts boundaries correctly."""
    inst = PhysicalInstance(
        id="test_switch_inst",
        component_item_no=1,
        name="Control Selector Switch",
        category="Control",
        manufacturer="Schneider Electric",
        part_number="XB4BD21",
        x=50.0,
        y=50.0,
        z=0.0,
        width=30.0,
        height=45.0,
        depth=40.0,
        surface="Z",
        mounting_type=MountingType.PLATE,
        is_placed=True
    )

    # Valid on mounting plate
    valid, _ = CollisionDetector.validate_position(inst, [inst], plate_w=740.0, plate_h=1060.0)
    assert valid

    # Switch to Door (Z+1)
    inst.surface = "Z+1"
    inst.mounting_type = MountingType.DOOR
    valid_door, _ = CollisionDetector.validate_position(inst, [inst], plate_w=800.0, plate_h=1200.0)
    assert valid_door


def test_component_selection_page_dynamic_search_and_bom_priority():
    """Verify Master Catalog is hidden initially, shows recommendations only on typing, and BOM is primary."""
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from app.gui.component_selection_page import ComponentSelectionPage

    page = ComponentSelectionPage()
    page.show()

    # 1. Recommendations must be HIDDEN when search is empty
    assert page.rec_card.isHidden() is True
    assert len(page.selected_components) == 0

    # 2. Type "ATV630" -> Recommendations card appears
    page.search_edit.setText("ATV630")
    assert page.rec_card.isHidden() is False
    assert page.rec_table.rowCount() > 0

    # 3. Add first item -> BOM table populates
    page._add_first_recommended_item()
    assert len(page.selected_components) == 1
    assert page.bom_table.rowCount() == 1
    comp = page.selected_components[0]
    assert "ATV630" in comp.part_number

    # 4. Clear search -> Recommendations card hides again, BOM remains visible and primary
    page.search_edit.clear()
    assert page.rec_card.isHidden() is True
    assert page.bom_table.rowCount() == 1

    # 5. Clear selection -> Clears BOM cleanly
    page.clear_selection()
    assert len(page.selected_components) == 0
    assert page.bom_table.rowCount() == 0


def test_main_window_new_project_and_catalog_bom_ready():
    """Verify MainWindow initializes, clears selection on new project without AttributeError, and receives BOM signal."""
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from app.gui.main_window import MainWindow
    win = MainWindow()

    # Populate 1 item in selection page
    mgr = CatalogManager.get_instance()
    res = mgr.search(query="ATV630")
    comp = mgr.create_component_from_record(res[0], item_no=1)
    win.page_select.selected_components.append(comp)
    win.page_select._refresh_bom_table()
    assert len(win.page_select.selected_items) == 1

    # Call _new_project - must not raise AttributeError: 'ComponentSelectionPage' object has no attribute 'selected_items'
    win._new_project()
    assert len(win.page_select.selected_items) == 0

    # Emit bom_ready signal with 1 or 2 arguments - must not raise TypeError
    win.page_select.selected_components.append(comp)
    win.page_select._proceed_to_bom()
    assert win.stack.currentIndex() == 1


def test_open_project_loads_all_pages():
    """Verify loading project JSON populates all 5 pages: Selection, BOM, Sizing, 2D Layout, and 3D."""
    import sys, tempfile, os
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from app.gui.main_window import MainWindow
    from app.models.project import ProjectData
    from app.models.bom import BOM
    from app.export.json_export import JSONExporter

    proj = ProjectData("Drive Project All Pages")
    proj.enclosure = Enclosure(width=800, height=1200, depth=400)
    c1 = Component(item_no=1, category=ComponentCategory.POWER, name="VFD 18kW", manufacturer="Schneider", width_mm=211, height_mm=546, depth_mm=232, mounting_type=MountingType.PLATE, surface="Z")
    c2 = Component(item_no=2, category=ComponentCategory.CONTROL, name="HMI KTP700", manufacturer="Siemens", width_mm=214, height_mm=158, depth_mm=45, mounting_type=MountingType.DOOR, surface="Z+1")
    proj.bom = BOM([c1, c2])
    proj.physical_instances = proj.bom.expand_to_instances()
    proj.physical_instances[0].is_placed = True
    proj.physical_instances[1].is_placed = True

    with tempfile.NamedTemporaryFile(suffix=".epd", delete=False) as tf:
        tmp_path = tf.name

    JSONExporter.export_project(proj, tmp_path)

    win = MainWindow()
    loaded_proj = JSONExporter.import_project(tmp_path)
    win.project = loaded_proj
    win.project.reconcile_instances_with_bom()

    # Step 1: Selection page
    win.page_select.set_selected_components(loaded_proj.bom.items)
    assert len(win.page_select.selected_components) == 2
    assert win.page_select.bom_table.rowCount() == 2

    # Step 2: BOM editor
    win.page_bom.bom = loaded_proj.bom
    win.page_bom._refresh_table()
    assert win.page_bom.table.rowCount() == 2

    # Step 3: Panel size page
    win.page_size.set_project(loaded_proj)
    assert win.page_size.spin_w.value() > 0

    # Step 4: 2D layout page
    win.page_2d.load_project(loaded_proj)
    assert len(win.page_2d._item_map) > 0

    # Switch steps and verify pages stay synchronized
    win._switch_step(0)
    assert len(win.page_select.selected_components) == 2
    win._switch_step(1)
    assert win.page_bom.table.rowCount() == 2

    os.remove(tmp_path)


def test_dual_currency_display_and_export():
    """Verify all prices are displayed dual-currency in USD ($) and INR (₹)."""
    import sys
    import os
    import tempfile
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from app.gui.component_selection_page import ComponentSelectionPage
    from app.gui.bom_editor import BOMEditorPage
    from app.database.component_database import ComponentDatabase
    from app.export.excel_export import ExcelBOMExporter
    from app.models.project import ProjectData
    from app.models.bom import BOM

    c = Component(
        item_no=1,
        category=ComponentCategory.CONTROL,
        name="Test PLC",
        manufacturer="Siemens",
        part_number="6ES7211-1BE40-0XB0",
        quantity=2,
        width_mm=90,
        height_mm=100,
        depth_mm=75,
        unit_price=100.0,
        mounting_type=MountingType.PLATE,
        surface="Z"
    )

    # 1. Step 1: ComponentSelectionPage
    sel_page = ComponentSelectionPage()
    sel_page.set_selected_components([c])

    # Header check
    assert "Unit Price ($ / ₹)" in sel_page.BOM_COLS
    assert "Total ($ / ₹)" in sel_page.BOM_COLS
    assert "Unit Price ($ / ₹)" in sel_page.REC_COLS

    # Table item checks
    unit_item = sel_page.bom_table.item(0, 9).text()
    tot_item = sel_page.bom_table.item(0, 10).text()
    assert "$100.00 / ₹8,300" in unit_item
    assert "$200.00 / ₹16,600" in tot_item
    assert "$200.00 / ₹16,600" in sel_page.lbl_summary.text()

    # 2. Step 2: BOMEditorPage
    db = ComponentDatabase()
    bom_page = BOMEditorPage(db)
    bom_page.bom = BOM([c])
    bom_page._refresh_table()

    assert "Unit Price ($ / ₹)" in bom_page.COLUMNS
    assert "Total Price ($ / ₹)" in bom_page.COLUMNS
    assert "$100.00 (₹8,300)" in bom_page.table.item(0, 13).text()
    assert "$200.00 (₹16,600)" in bom_page.table.item(0, 14).text()
    assert "$200.00 / ₹16,600" in bom_page.lbl_cost.text()

    # Inline editing test: user changes unit price to 150
    table_unit_item = bom_page.table.item(0, 13)
    table_unit_item.setText("150.0")
    assert c.unit_price == 150.0
    assert c.total_price == 300.0
    assert "$300.00 (₹24,900)" in bom_page.table.item(0, 14).text()
    assert "$300.00 / ₹24,900" in bom_page.lbl_cost.text()

    # 3. Excel Export
    proj = ProjectData("Dual Currency Export Test")
    proj.enclosure = Enclosure(width=800, height=1000, depth=300)
    proj.bom = BOM([c])

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        xlsx_path = tf.name

    success = ExcelBOMExporter.export_to_excel(proj, xlsx_path)
    assert success is True

    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    assert "Estimated BOM Cost:" in ws["G4"].value
    assert "$300.00 / ₹24,900" in str(ws["H4"].value)
    assert "Unit Price ($ / ₹)" in [ws.cell(row=6, column=col).value for col in range(1, 17)]
    assert "$150.00 (₹12,450)" in [str(ws.cell(row=7, column=col).value) for col in range(1, 17)]
    wb.close()
    os.remove(xlsx_path)


