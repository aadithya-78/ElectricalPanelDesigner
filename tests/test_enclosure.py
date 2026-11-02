"""
Unit tests for enclosure geometry and standard size catalog selection.
"""
from app.models.enclosure import Enclosure, STANDARD_ENCLOSURE_CATALOG
from app.engineering.enclosure_sizing import EnclosureSizingEngine


def test_enclosure_usable_dimensions():
    enc = Enclosure(
        width=800.0,
        height=1200.0,
        depth=400.0,
        wall_thickness=2.0,
        door_clearance=50.0,
        plate_standoff=25.0,
        gland_plate_height=80.0,
        top_cable_margin=60.0,
        side_margin=30.0
    )
    # Mounting plate width = 800 - 2*30 = 740 mm
    assert enc.mounting_plate_width == 740.0
    # Mounting plate height = 1200 - 80 - 60 = 1060 mm
    assert enc.mounting_plate_height == 1060.0
    # Usable internal depth = 400 - 2 - 25 - 50 = 323 mm
    assert enc.internal_depth == 323.0


def test_standard_catalog_selection():
    # If required mounting plate is 700x1000x240, catalog item ENC-801230 (800x1200x300, plate 740x1140, depth 240) should fit
    chosen = EnclosureSizingEngine.select_smallest_standard_enclosure(
        required_w=700.0,
        required_h=1000.0,
        required_d=240.0
    )
    assert chosen.width >= 800.0
    assert chosen.height >= 1000.0
    assert chosen.depth >= 300.0

