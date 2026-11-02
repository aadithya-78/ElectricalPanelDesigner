"""
Unit tests for 3D AABB and Clearance Zone Collision Detection.
"""
from app.models.component import PhysicalInstance, MountingType
from app.geometry.collision_detector import CollisionDetector
from app.models.enclosure import Enclosure


def test_aabb_no_collision():
    box1 = {"min_x": 0.0, "max_x": 100.0, "min_y": 0.0, "max_y": 100.0, "min_z": 0.0, "max_z": 50.0}
    box2 = {"min_x": 120.0, "max_x": 220.0, "min_y": 0.0, "max_y": 100.0, "min_z": 0.0, "max_z": 50.0}
    assert CollisionDetector.check_aabb_intersection(box1, box2) is False


def test_aabb_direct_collision():
    box1 = {"min_x": 0.0, "max_x": 100.0, "min_y": 0.0, "max_y": 100.0, "min_z": 0.0, "max_z": 50.0}
    box2 = {"min_x": 50.0, "max_x": 150.0, "min_y": 50.0, "max_y": 150.0, "min_z": 0.0, "max_z": 50.0}
    assert CollisionDetector.check_aabb_intersection(box1, box2) is True


def test_instance_clearance_violation():
    """Verify that physical bodies that don't touch can still violate thermal/clearance zones."""
    inst1 = PhysicalInstance(
        id="vfd",
        component_item_no=1,
        name="VFD",
        category="Power",
        manufacturer="Schneider",
        part_number="ATV630",
        width=200.0,
        height=400.0,
        depth=200.0,
        mounting_type=MountingType.PLATE,
        x=100.0,
        y=100.0,
        z=0.0,
        clearance_top=100.0, # 100mm required above
        clearance_bottom=100.0,
        clearance_sides=50.0,
        is_placed=True
    )
    # Put another device 50mm above VFD (violates 100mm top clearance)
    inst2 = PhysicalInstance(
        id="mcb",
        component_item_no=2,
        name="MCB",
        category="Control",
        manufacturer="Schneider",
        part_number="Acti9",
        width=50.0,
        height=80.0,
        depth=70.0,
        mounting_type=MountingType.PLATE,
        x=100.0,
        y=550.0, # inst1 max_y is 500, clearance extends to 600
        z=0.0,
        clearance_top=10.0,
        clearance_bottom=10.0,
        clearance_sides=5.0,
        is_placed=True
    )

    # Physical bodies do not intersect (500 < 550)
    assert CollisionDetector.check_instance_collision(inst1, inst2, check_clearance=False) is False
    # But clearance zone is violated
    assert CollisionDetector.check_instance_collision(inst1, inst2, check_clearance=True) is True


def test_boundary_overflow():
    enc = Enclosure(width=800.0, height=1200.0, depth=400.0)
    inst = PhysicalInstance(
        id="huge",
        component_item_no=1,
        name="Huge Device",
        category="Power",
        manufacturer="Generic",
        part_number=None,
        width=500.0,
        height=400.0,
        depth=200.0,
        mounting_type=MountingType.PLATE,
        x=600.0, # 600 + 500 = 1100 > 740mm plate width!
        y=100.0,
        z=0.0,
        is_placed=True
    )
    errors = CollisionDetector.check_boundary_overflow(inst, enc)
    assert len(errors) > 0
    assert "extends beyond mounting plate width" in errors[0]

