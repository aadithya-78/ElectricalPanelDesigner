"""
End-to-End automated layout test for:
"Create an 18 kW motor drive panel using Schneider ATV630"
"""
from app.ai.offline_fallback import get_offline_bom_18kw_atv630
from app.models.bom import BOM
from app.geometry.auto_layout import AutoLayoutEngine
from app.models.component import MountingType


def test_18kw_atv630_automatic_layout():
    # 1. Load engineering BOM
    bom_raw = get_offline_bom_18kw_atv630({
        "VFD": "Schneider Electric",
        "MCCB": "Schneider Electric",
        "Enclosure": "Rittal",
        "Terminal Blocks": "Connectwell"
    })
    bom = BOM.from_list(bom_raw)
    assert len(bom.items) >= 20

    # 2. Expand into physical units (e.g. 16 control terminals -> 16 separate physical instances)
    instances = bom.expand_to_instances()
    terminal_instances = [i for i in instances if "Control Terminal" in i.name]
    assert len(terminal_instances) == 16, "16 control terminals should expand into 16 individual physical instances"

    # 3. Run Automatic Layout
    enclosure, placed_instances, din_rails, wiring_ducts, warnings = AutoLayoutEngine.generate_layout(instances)

    # 4. Assertions
    # Final enclosure size must be realistic and come from catalog
    assert enclosure.width >= 800.0
    assert enclosure.height >= 1200.0
    assert enclosure.depth >= 300.0

    # Physical objects check
    assert len(din_rails) >= 2, "Must create physical DIN rails"
    assert len(wiring_ducts) >= 2, "Must create slotted wiring ducts"

    # All active instances placed
    active_instances = [i for i in placed_instances if not i.is_external]
    assert all(i.is_placed for i in active_instances)

    # Check VFD placement
    vfd = next(i for i in active_instances if "ATV630" in i.part_number or "VFD" in i.name)
    assert vfd.is_placed
    assert vfd.x > 0
    assert vfd.y > 0

    # Check DIN rail component snapping
    din_instances = [i for i in active_instances if i.mounting_type == MountingType.DIN]
    assert all(i.din_rail_id is not None for i in din_instances)
    assert all(i.z >= 7.5 for i in din_instances)

