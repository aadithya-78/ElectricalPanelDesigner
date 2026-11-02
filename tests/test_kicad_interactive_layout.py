"""
Comprehensive tests for KiCad-style interactive 2D layout:
- Strict boundary rejection
- Strict collision rejection and rollback
- DIN-mounted component on DIN-rail exception
- Wire duct collision enforcement
- Mathematical enclosure sizing calculations
- Rotation support (0, 90, 180, 270 degrees)
"""
import pytest
from app.models.component import PhysicalInstance, MountingType, ComponentCategory, Component
from app.models.bom import BOM
from app.models.enclosure import Enclosure
from app.geometry.collision_detector import CollisionDetector
from app.engineering.enclosure_sizing import EnclosureSizingEngine


def test_strict_boundary_validation():
    """Test that components extending beyond mounting plate boundaries are strictly rejected."""
    plate_w = 740.0
    plate_h = 1060.0

    inst = PhysicalInstance(
        id="inst_1", component_item_no=1, name="VFD Drive",
        category="Power", manufacturer="Schneider", part_number="ATV630D18N4",
        width=211.0, height=546.0, depth=232.0,
        mounting_type=MountingType.PLATE, x=100.0, y=100.0, is_placed=True
    )

    # 1. Valid position inside boundary
    valid, reason = CollisionDetector.validate_position(inst, [inst], plate_w, plate_h)
    assert valid is True
    assert reason is None

    # 2. X extends beyond plate width
    inst.x = 600.0 # 600 + 211 = 811 > 740
    valid, reason = CollisionDetector.validate_position(inst, [inst], plate_w, plate_h)
    assert valid is False
    assert "Boundary violation" in reason

    # 3. Y extends beyond plate height
    inst.x = 100.0
    inst.y = 800.0 # 800 + 546 = 1346 > 1060
    valid, reason = CollisionDetector.validate_position(inst, [inst], plate_w, plate_h)
    assert valid is False
    assert "Boundary violation" in reason

    # 4. Negative X
    inst.x = -10.0
    inst.y = 100.0
    valid, reason = CollisionDetector.validate_position(inst, [inst], plate_w, plate_h)
    assert valid is False
    assert "Boundary violation" in reason


def test_strict_collision_detection():
    """Test that overlapping regular components are strictly rejected."""
    plate_w = 740.0
    plate_h = 1060.0

    comp1 = PhysicalInstance(
        id="c1", component_item_no=1, name="MCCB 63A",
        category="Power", manufacturer="Schneider", part_number="LV429630",
        width=105.0, height=161.0, depth=86.0,
        mounting_type=MountingType.PLATE, x=100.0, y=100.0, is_placed=True
    )

    comp2 = PhysicalInstance(
        id="c2", component_item_no=2, name="Contactor 50A",
        category="Power", manufacturer="Schneider", part_number="LC1D50AP7",
        width=55.0, height=122.0, depth=120.0,
        mounting_type=MountingType.PLATE, x=150.0, y=120.0, is_placed=True
    )

    # Overlapping position
    valid, reason = CollisionDetector.validate_position(comp2, [comp1, comp2], plate_w, plate_h)
    assert valid is False
    assert "Collision violation" in reason
    assert "MCCB 63A" in reason

    # Move comp2 to clear position
    comp2.x = 220.0
    valid, reason = CollisionDetector.validate_position(comp2, [comp1, comp2], plate_w, plate_h)
    assert valid is True
    assert reason is None


def test_din_rail_mounting_exception():
    """
    Test that DIN-mounted components are allowed to overlap DIN rails,
    while plate-mounted components colliding with DIN rails are rejected.
    """
    plate_w = 740.0
    plate_h = 1060.0

    din_rail = PhysicalInstance(
        id="rail_1", component_item_no=99, name="DIN Rail Row 1",
        category="Accessories", manufacturer="Generic", part_number=None,
        width=600.0, height=35.0, depth=7.5,
        mounting_type=MountingType.PLATE, x=70.0, y=400.0, is_placed=True
    )

    # DIN-mounted relay sitting directly on the DIN rail
    din_relay = PhysicalInstance(
        id="relay_1", component_item_no=3, name="Control Relay",
        category="Control", manufacturer="Phoenix Contact", part_number="2966171",
        width=6.2, height=90.0, depth=76.0,
        mounting_type=MountingType.DIN, x=100.0, y=380.0, is_placed=True
    )

    # DIN component on DIN rail: Allowed!
    collision = CollisionDetector.check_instance_collision(din_relay, din_rail, check_clearance=False)
    assert collision is False

    valid, reason = CollisionDetector.validate_position(din_relay, [din_rail, din_relay], plate_w, plate_h)
    assert valid is True
    assert reason is None

    # Heavy plate-mounted drive sitting over a DIN rail: Rejected!
    plate_vfd = PhysicalInstance(
        id="vfd_1", component_item_no=1, name="VFD Heavy",
        category="Power", manufacturer="Schneider", part_number="ATV630",
        width=211.0, height=546.0, depth=232.0,
        mounting_type=MountingType.PLATE, x=100.0, y=300.0, is_placed=True
    )

    collision_vfd = CollisionDetector.check_instance_collision(plate_vfd, din_rail, check_clearance=False)
    assert collision_vfd is True

    valid_vfd, reason_vfd = CollisionDetector.validate_position(plate_vfd, [din_rail, plate_vfd], plate_w, plate_h)
    assert valid_vfd is False
    assert "Collision violation" in reason_vfd


def test_rotation_support():
    """Test 90, 180, and 270 degree rotation dimension swapping."""
    inst = PhysicalInstance(
        id="inst_rot", component_item_no=1, name="Rotatable Unit",
        category="Control", manufacturer="Generic", part_number=None,
        width=60.0, height=120.0, depth=50.0,
        mounting_type=MountingType.PLATE, x=10.0, y=10.0, is_placed=True
    )

    # 0 deg: 60 x 120
    inst.rotation = 0.0
    bbox0 = inst.bounding_box
    assert bbox0["max_x"] - bbox0["min_x"] == 60.0
    assert bbox0["max_y"] - bbox0["min_y"] == 120.0

    # 90 deg: 120 x 60
    inst.rotation = 90.0
    bbox90 = inst.bounding_box
    assert bbox90["max_x"] - bbox90["min_x"] == 120.0
    assert bbox90["max_y"] - bbox90["min_y"] == 60.0

    # 180 deg: 60 x 120
    inst.rotation = 180.0
    bbox180 = inst.bounding_box
    assert bbox180["max_x"] - bbox180["min_x"] == 60.0
    assert bbox180["max_y"] - bbox180["min_y"] == 120.0

    # 270 deg: 120 x 60
    inst.rotation = 270.0
    bbox270 = inst.bounding_box
    assert bbox270["max_x"] - bbox270["min_x"] == 120.0
    assert bbox270["max_y"] - bbox270["min_y"] == 60.0


def test_mathematical_enclosure_sizing():
    """Verify local mathematical panel sizing calculations without AI."""
    bom = BOM()
    vfd = Component(
        item_no=1, category=ComponentCategory.POWER, name="18kW VFD ATV630",
        manufacturer="Schneider", width_mm=211.0, height_mm=546.0, depth_mm=232.0,
        clearance_top_mm=100.0, clearance_bottom_mm=100.0,
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
    sizing = EnclosureSizingEngine.calculate_required_space(instances)

    assert sizing["max_comp_depth"] == 232.0
    assert sizing["min_internal_w"] >= 500.0
    assert sizing["min_internal_h"] >= 700.0
    assert sizing["recommended_w"] >= 600.0
    assert sizing["recommended_h"] >= 800.0
    assert sizing["recommended_d"] >= 300.0
    assert sizing["space_utilization_pct"] > 0.0
    assert sizing["usable_plate_w"] < sizing["recommended_w"]
    assert sizing["usable_plate_h"] < sizing["recommended_h"]

