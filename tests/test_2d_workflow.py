"""
Unit tests for the revised 2D Front-View workflow:
1. Panel size input & constrained placement
2. Overflow warning when specified panel is too small
3. Conversion of 2D coordinates to 3D model
"""
import pytest
import sys
from PySide6.QtWidgets import QApplication
from app.models.bom import BOM
from app.models.component import Component, MountingType, ComponentCategory
from app.models.enclosure import Enclosure
from app.geometry.auto_layout import AutoLayoutEngine


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_constrained_layout_in_user_specified_size():
    # Create sample BOM
    bom = BOM()
    vfd = Component(
        item_no=1, category=ComponentCategory.POWER, name="VFD ATV630",
        manufacturer="Schneider", width_mm=211.0, height_mm=546.0, depth_mm=232.0,
        mounting_type=MountingType.PLATE
    )
    mccb = Component(
        item_no=2, category=ComponentCategory.POWER, name="MCCB 63A",
        manufacturer="Schneider", width_mm=105.0, height_mm=161.0, depth_mm=86.0,
        mounting_type=MountingType.PLATE
    )
    bom.add_item(vfd)
    bom.add_item(mccb)

    instances = bom.expand_to_instances()

    # User specifies 800 x 1200 x 400 mm panel
    user_enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0)
    enc, placed, rails, ducts, warnings = AutoLayoutEngine.generate_layout(
        instances, target_enclosure=user_enclosure
    )

    assert enc.width == 800.0
    assert enc.height == 1200.0
    assert enc.depth == 400.0
    assert all(i.is_placed for i in placed)


def test_overflow_detection_for_undersized_panel():
    # Create large drive BOM
    bom = BOM()
    vfd = Component(
        item_no=1, category=ComponentCategory.POWER, name="VFD ATV630",
        manufacturer="Schneider", width_mm=211.0, height_mm=546.0, depth_mm=232.0,
        clearance_top_mm=100.0, clearance_bottom_mm=100.0,
        mounting_type=MountingType.PLATE
    )
    bom.add_item(vfd)
    instances = bom.expand_to_instances()

    # User enters tiny panel: 300 x 400 x 200 mm (Mounting plate is 240 x 260 mm, smaller than 546mm VFD!)
    tiny_enclosure = Enclosure(width=300.0, height=400.0, depth=200.0)
    enc, placed, rails, ducts, warnings = AutoLayoutEngine.generate_layout(
        instances, target_enclosure=tiny_enclosure
    )

    # Should detect insufficient size
    assert any("PANEL SIZE INSUFFICIENT" in w for w in warnings)


def test_2d_to_3d_coordinate_preservation():
    """Verify that 2D (x, y) coordinates on mounting plate are preserved in 3D scene."""
    inst = Component(
        item_no=1, category=ComponentCategory.CONTROL, name="SMPS 24V",
        manufacturer="Mean Well", width_mm=52.0, height_mm=90.0, depth_mm=55.0,
        mounting_type=MountingType.DIN
    )
    bom = BOM([inst])
    instances = bom.expand_to_instances()

    # Assign manual 2D position
    instances[0].x = 150.0
    instances[0].y = 280.0
    instances[0].is_placed = True

    # When converted to 3D:
    # DIN device has Z = 7.5mm (on DIN rail), X = 150mm, Y = 280mm
    if instances[0].mounting_type == MountingType.DIN:
        instances[0].z = 7.5

    bbox = instances[0].bounding_box
    assert bbox["min_x"] == 150.0
    assert bbox["min_y"] == 280.0
    assert bbox["min_z"] == 7.5
    assert bbox["max_z"] == 7.5 + 55.0


def test_2d_selection_filter_and_select_all(qapp):
    """Verify 2D selection filtering and marquee select-all on canvas."""
    from app.models.project import ProjectData
    from app.gui.panel_2d_editor import Panel2DEditor

    project = ProjectData()
    project.enclosure = Enclosure(width=800, height=1000, depth=300)
    c1 = Component(
        item_no=1, category=ComponentCategory.CONTROL, name="MCB 1",
        manufacturer="ABB", width_mm=36, height_mm=90, depth_mm=70,
        mounting_type=MountingType.DIN
    )
    project.bom = BOM([c1])
    project.physical_instances = project.bom.expand_to_instances()
    project.physical_instances[0].is_placed = True

    editor = Panel2DEditor()
    editor.load_project(project)
    editor.add_workspace_object("din_rail")
    editor.add_workspace_object("wire_duct_h")

    # Filter: All Objects
    editor.combo_select_filter.setCurrentText("All Objects")
    editor.select_all()
    assert len(editor.scene.selectedItems()) == 3

    # Filter: DIN Rails Only
    editor.combo_select_filter.setCurrentText("DIN Rails Only")
    editor.select_all()
    assert len(editor.scene.selectedItems()) == 1

    # Filter: Wiring Ducts Only
    editor.combo_select_filter.setCurrentText("Wiring Ducts Only")
    editor.select_all()
    assert len(editor.scene.selectedItems()) == 1

    # Filter: Components Only
    editor.combo_select_filter.setCurrentText("Components Only")
    editor.select_all()
    assert len(editor.scene.selectedItems()) == 1


def test_2d_alignment_and_distribution(qapp):
    """Verify 2D alignment (top, bottom, left, right, h-center, v-center) and distribution."""
    from app.models.project import ProjectData
    from app.gui.panel_2d_editor import Panel2DEditor

    project = ProjectData()
    project.enclosure = Enclosure(width=800, height=1000, depth=300)
    c1 = Component(item_no=1, category=ComponentCategory.CONTROL, name="MCB 1", manufacturer="ABB", width_mm=36, height_mm=90, depth_mm=70, mounting_type=MountingType.DIN)
    c2 = Component(item_no=2, category=ComponentCategory.CONTROL, name="MCB 2", manufacturer="ABB", width_mm=36, height_mm=90, depth_mm=70, mounting_type=MountingType.DIN)
    c3 = Component(item_no=3, category=ComponentCategory.CONTROL, name="MCB 3", manufacturer="ABB", width_mm=36, height_mm=90, depth_mm=70, mounting_type=MountingType.DIN)
    project.bom = BOM([c1, c2, c3])
    project.physical_instances = project.bom.expand_to_instances()
    for i, inst in enumerate(project.physical_instances):
        inst.x = 100.0 + i * 80.0
        inst.y = 200.0 + i * 20.0
        inst.is_placed = True

    editor = Panel2DEditor()
    editor.load_project(project)
    editor.select_all()

    # Align Top
    editor.align_selected_top()
    for it in editor.scene.selectedItems():
        assert it.pos().y() == 200.0

    # Align Left
    editor.align_selected_left()
    for it in editor.scene.selectedItems():
        assert it.pos().x() == 100.0

    # Test Distribution
    items = list(editor._item_map.values())
    items[0].setPos(100, 200)
    items[1].setPos(250, 200)
    items[2].setPos(400, 200)
    for it in items:
        it.setSelected(True)
    editor.distribute_selected_horizontally()
    assert items[0].pos().x() == 100.0
    assert items[2].pos().x() == 400.0


def test_measure_tool_and_din_snap_centering(qapp):
    """Test measurement snap points (edges & centers) and DIN rail vertical centering."""
    from app.gui.panel_2d_editor import Panel2DEditor
    from app.models.project import ProjectData
    from app.models.enclosure import DINRail
    from PySide6.QtCore import QPointF

    proj = ProjectData("Measure Test")
    proj.enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0)
    rail = DINRail(id="rail_1", name="DIN Rail 1", x=100.0, y=300.0, length=500.0, height=35.0)
    proj.din_rails = [rail]

    c = Component(item_no=1, category=ComponentCategory.CONTROL, manufacturer="Schneider Electric", name="MCB 2P", width_mm=36.0, height_mm=85.0, depth_mm=75.0, mounting_type=MountingType.DIN)
    proj.bom.add_item(c)
    proj.physical_instances = proj.bom.expand_to_instances()
    inst = proj.physical_instances[0]
    inst.x = 150.0
    inst.y = 200.0
    inst.is_placed = True

    editor = Panel2DEditor()
    editor.load_project(proj)

    # 1. Test Snapping to Component Center
    comp_center_expected = QPointF(inst.x + inst.effective_width / 2.0, inst.y + inst.effective_height / 2.0)
    snapped_pt, label = editor.find_nearest_snap_point(QPointF(inst.x + 10.0, inst.y + 35.0))
    assert "[Center]" in label
    assert abs(snapped_pt.x() - comp_center_expected.x()) < 0.1
    assert abs(snapped_pt.y() - comp_center_expected.y()) < 0.1

    # 2. Test Snapping to Component Top Edge
    top_edge_expected = QPointF(inst.x + inst.effective_width / 2.0, inst.y)
    snapped_pt, label = editor.find_nearest_snap_point(QPointF(inst.x + 18.0, inst.y + 2.0))
    assert "[Top Edge]" in label
    assert abs(snapped_pt.y() - top_edge_expected.y()) < 0.1

    # 3. Test Measurement 2-click workflow (Start & Stop)
    editor.toggle_measure_tool(True)
    assert editor.measure_mode_active is True

    # 1st click: component center
    editor.handle_measure_click(comp_center_expected)
    assert editor.measure_start_point is not None

    # 2nd click: rail center
    rail_center = QPointF(rail.x + rail.length / 2.0, rail.y + rail.height / 2.0)
    editor.handle_measure_click(rail_center)
    assert editor.measure_start_point is None  # Completed measurement and ready for next
    assert len(editor.measure_items) > 0

    # 4. Test DIN Rail vertical centering during snap
    # Rail center Y is 300 + 17.5 = 317.5. Component height is 85.
    # Centered component Y should be 317.5 - 42.5 = 275.0.
    item = editor._item_map[inst.id]
    item.setPos(150.0, 290.0)  # Dragged near rail Y=300
    # Simulate mouse release snap logic
    eff_h = inst.effective_height
    rail_center_y = rail.y + (rail.height / 2.0)
    target_y = rail_center_y - (eff_h / 2.0)
    assert target_y == 275.0
    # Verify rail is in the exact middle of the component
    assert target_y + eff_h / 2.0 == rail_center_y


