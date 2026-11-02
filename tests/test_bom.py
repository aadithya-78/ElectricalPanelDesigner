"""
Unit tests for BOM parsing, arithmetic, and physical instance expansion.
"""
import pytest
from app.models.component import Component, MountingType, ComponentCategory, ValidationStatus
from app.models.bom import BOM


def test_bom_creation_and_totals():
    bom = BOM()
    c1 = Component(
        item_no=1,
        category=ComponentCategory.POWER,
        name="VFD 18.5 kW",
        manufacturer="Schneider Electric",
        quantity=1,
        width_mm=211.0,
        height_mm=546.0,
        depth_mm=232.0,
        unit_price=1850.0,
        heat_loss_watts=455.0
    )
    c2 = Component(
        item_no=2,
        category=ComponentCategory.CONTROL,
        name="Terminal Block 2.5 sq mm",
        manufacturer="Connectwell",
        quantity=10,
        width_mm=6.0,
        height_mm=45.0,
        depth_mm=43.0,
        unit_price=1.5,
        heat_loss_watts=0.2
    )
    bom.add_item(c1)
    bom.add_item(c2)

    assert len(bom.items) == 2
    assert bom.total_cost() == 1850.0 + (10 * 1.5)
    assert bom.total_heat_loss() == pytest.approx(455.0 + (10 * 0.2), 0.1)


def test_bom_quantity_expansion():
    """Verify that Terminal Block Qty 12 expands to 12 individual physical instances."""
    bom = BOM()
    tb = Component(
        item_no=1,
        category=ComponentCategory.CONTROL,
        name="Terminal Block",
        manufacturer="Connectwell",
        quantity=12,
        width_mm=6.0,
        height_mm=45.0,
        depth_mm=43.0,
        mounting_type=MountingType.DIN
    )
    bom.add_item(tb)

    instances = bom.expand_to_instances()
    assert len(instances) == 12
    # Verify individual IDs and names
    assert instances[0].id == "inst_1_1"
    assert instances[0].name == "Terminal Block #1"
    assert instances[11].id == "inst_1_12"
    assert instances[11].name == "Terminal Block #12"
    assert all(inst.width == 6.0 for inst in instances)


def test_bom_serialization():
    bom = BOM()
    c = Component(
        item_no=1,
        category=ComponentCategory.POWER,
        name="MCCB 63A",
        manufacturer="Schneider Electric",
        part_number="LV429630",
        part_number_verified=True,
        quantity=1,
        width_mm=105.0,
        height_mm=161.0,
        depth_mm=86.0
    )
    bom.add_item(c)
    data = bom.to_list()
    assert len(data) == 1
    assert data[0]["name"] == "MCCB 63A"
    assert data[0]["part_number_verified"] is True

    reloaded = BOM.from_list(data)
    assert len(reloaded.items) == 1
    assert reloaded.items[0].part_number == "LV429630"

