"""
Unit tests for component dimension handling and rotation conventions.
"""
from app.models.component import Component, PhysicalInstance, MountingType


def test_coordinate_conventions():
    """Verify X=Width, Y=Height, Z=Depth convention."""
    c = Component(
        item_no=1,
        category="Power",
        name="VFD",
        manufacturer="Schneider",
        width_mm=211.0,
        height_mm=546.0,
        depth_mm=232.0
    )
    assert c.width_mm == 211.0   # X
    assert c.height_mm == 546.0  # Y
    assert c.depth_mm == 232.0   # Z


def test_rotation_geometry():
    """Verify 90-degree rotation swaps effective width (X) and height (Y)."""
    inst = PhysicalInstance(
        id="comp1",
        component_item_no=1,
        name="Contactor",
        category="Power",
        manufacturer="Schneider",
        part_number="LC1D",
        width=45.0,
        height=85.0,
        depth=90.0,
        mounting_type=MountingType.PLATE,
        x=100.0,
        y=100.0,
        z=0.0,
        rotation=0.0
    )
    b0 = inst.bounding_box
    assert b0["max_x"] - b0["min_x"] == 45.0
    assert b0["max_y"] - b0["min_y"] == 85.0

    # Rotate 90 deg
    inst.rotation = 90.0
    b90 = inst.bounding_box
    assert b90["max_x"] - b90["min_x"] == 85.0
    assert b90["max_y"] - b90["min_y"] == 45.0

