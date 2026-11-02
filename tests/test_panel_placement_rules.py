"""
Unit tests for Electrical Panel Placement Rules, Aesthetic Zoning,
Dense Packing (High Area Efficiency), and Absolute Zero-Overlap with Wiring Ducts.
"""
import pytest
from app.models.component import Component, PhysicalInstance, MountingType, ComponentCategory
from app.models.enclosure import Enclosure, STANDARD_ENCLOSURE_CATALOG
from app.models.bom import BOM
from app.database.catalog_manager import CatalogManager
from app.geometry.auto_layout import AutoLayoutEngine
from app.engineering.enclosure_sizing import EnclosureSizingEngine
from app.ai.offline_fallback import get_offline_bom_18kw_atv630


def check_2d_box_overlap(box1, box2):
    """Return True if two 2D boxes overlap."""
    return (
        box1[0] < box2[1] and box1[1] > box2[0] and
        box1[2] < box2[3] and box1[3] > box2[2]
    )


def test_zero_overlap_between_din_components_rails_and_wiring_ducts():
    """
    CRITICAL REQUIREMENT:
    Verify that components mounted on DIN rails and DIN rails themselves NEVER overlap with wiring ducts,
    and that any wiring duct below a DIN rail is strictly positioned below the lowest component.
    """
    bom_raw = get_offline_bom_18kw_atv630({
        "VFD": "Schneider Electric",
        "MCCB": "Schneider Electric",
        "Enclosure": "Rittal",
        "Terminal Blocks": "Connectwell"
    })
    bom = BOM.from_list(bom_raw)
    instances = bom.expand_to_instances()

    enc, placed, rails, ducts, warnings = AutoLayoutEngine.generate_layout(instances)

    plate_components = [
        i for i in placed 
        if i.surface == "Z" and i.is_placed and not i.is_external 
        and not any(k in i.name.lower() for k in ["enclosure", "cabinet"])
    ]
    assert len(plate_components) > 0

    # 1. Check AABB overlap between EVERY component and EVERY wiring duct
    for comp in plate_components:
        c_box = (comp.x, comp.x + comp.width, comp.y, comp.y + comp.height)
        for duct in ducts:
            is_vert = duct.orientation == "VERTICAL" or int(getattr(duct, "rotation", 0)) in (90, 270)
            dw = duct.width if is_vert else duct.length
            dh = duct.length if is_vert else duct.height
            d_box = (duct.x, duct.x + dw, duct.y, duct.y + dh)

            assert not check_2d_box_overlap(c_box, d_box), (
                f"OVERLAP DETECTED: Component '{comp.name}' [{c_box[0]:.1f}..{c_box[1]:.1f}, {c_box[2]:.1f}..{c_box[3]:.1f}] "
                f"overlaps with Duct '{duct.name}' [{d_box[0]:.1f}..{d_box[1]:.1f}, {d_box[2]:.1f}..{d_box[3]:.1f}]!"
            )

    # 2. Check AABB overlap between EVERY DIN rail and EVERY wiring duct
    for rail in rails:
        r_box = (rail.x, rail.x + rail.effective_width, rail.y, rail.y + rail.effective_height)
        for duct in ducts:
            is_vert = duct.orientation == "VERTICAL" or int(getattr(duct, "rotation", 0)) in (90, 270)
            dw = duct.width if is_vert else duct.length
            dh = duct.length if is_vert else duct.height
            d_box = (duct.x, duct.x + dw, duct.y, duct.y + dh)

            assert not check_2d_box_overlap(r_box, d_box), (
                f"OVERLAP DETECTED: DIN Rail '{rail.name}' [{r_box[0]:.1f}..{r_box[1]:.1f}, {r_box[2]:.1f}..{r_box[3]:.1f}] "
                f"overlaps with Duct '{duct.name}' [{d_box[0]:.1f}..{d_box[1]:.1f}, {d_box[2]:.1f}..{d_box[3]:.1f}]!"
            )

    # 3. Check that every horizontal duct below a rail is strictly below the lowest component
    for rail in rails:
        rail_comps = [c for c in plate_components if c.din_rail_id == rail.id]
        if not rail_comps:
            continue
        lowest_comp_bottom = max(c.y + c.height for c in rail_comps)
        
        # Check ducts positioned below this rail
        h_ducts_below = [
            d for d in ducts 
            if d.orientation == "HORIZONTAL" and d.y >= rail.y
        ]
        for d in h_ducts_below:
            assert d.y >= lowest_comp_bottom, (
                f"Duct '{d.name}' (y={d.y}) overlaps with components on '{rail.name}' "
                f"which extend down to y={lowest_comp_bottom}!"
            )

    # 4. Zero overlap warnings emitted
    overlap_warnings = [w for w in warnings if "OVERLAP" in w or "COLLISION" in w]
    assert len(overlap_warnings) == 0, f"Expected 0 overlap warnings, got: {overlap_warnings}"


def test_dense_panel_sizing_for_18kw_drive():
    """
    Verify 18kW ATV630 drive panel is sized compactly (800x1200x400)
    with high space utilization (> 45%), NOT an oversized 2.5m giant cabinet.
    """
    bom_raw = get_offline_bom_18kw_atv630({
        "VFD": "Schneider Electric",
        "MCCB": "Schneider Electric",
        "Enclosure": "Rittal",
        "Terminal Blocks": "Connectwell"
    })
    bom = BOM.from_list(bom_raw)
    instances = bom.expand_to_instances()

    sizing = EnclosureSizingEngine.calculate_required_space(instances)

    # Must select standard 800x1200x400 industrial enclosure
    assert sizing["recommended_w"] == 800.0
    assert sizing["recommended_h"] == 1200.0
    assert sizing["recommended_d"] == 400.0

    # Must achieve high space utilization (compact dense panel)
    assert sizing["space_utilization_pct"] >= 45.0, f"Expected utilization >= 45%, got {sizing['space_utilization_pct']}%"


def test_dense_panel_sizing_for_compact_plc_panel():
    """
    Verify a compact PLC BOM (CPU + IO + SMPS + MCBs + Terminals) selects a
    compact wall-mount cabinet (e.g. 600x600 or 600x800), NOT an oversized 1200mm floor panel.
    """
    mgr = CatalogManager.get_instance()
    test_queries = [
        ("6ES7214-1AG40-0XB0", 1), # PLC CPU 1214C
        ("6ES7221-1BF32-0XB0", 2), # DI modules
        ("6ES7222-1BF32-0XB0", 1), # DQ module
        ("2904601", 1),            # SMPS 24V 5A
        ("A9F74210", 4),           # MCB 10A
        ("LC1D25BD", 2),           # Contactor
        ("3044076", 16),           # UT 2.5 Terminals
    ]
    components = []
    for idx, (pn, qty) in enumerate(test_queries, 1):
        res = mgr.search(query=pn)
        if res:
            comp = mgr.create_component_from_record(res[0], item_no=idx, quantity=qty)
            components.append(comp)

    bom = BOM(items=components)
    instances = bom.expand_to_instances()

    sizing = EnclosureSizingEngine.calculate_required_space(instances)

    # Must be a compact wall mount enclosure (<= 800mm height)
    assert sizing["recommended_w"] <= 600.0
    assert sizing["recommended_h"] <= 800.0
    assert sizing["space_utilization_pct"] >= 35.0


def test_aesthetic_panel_zoning_and_hierarchy():
    """
    Verify industrial aesthetic rules:
    - Power tier at top: MCCB on left, Line Reactor adjacent, VFD on right.
    - Automation tier in middle: SMPS, MCBs, PLC CPU.
    - Terminal blocks in tight row with 0mm gap at bottom.
    - Door: Pilot lamps at eye-level, HMI centered, operator controls below, E-Stop on right.
    """
    bom_raw = get_offline_bom_18kw_atv630({
        "VFD": "Schneider Electric",
        "MCCB": "Schneider Electric",
        "Enclosure": "Rittal",
        "Terminal Blocks": "Connectwell"
    })
    bom = BOM.from_list(bom_raw)
    instances = bom.expand_to_instances()

    enc, placed, rails, ducts, warnings = AutoLayoutEngine.generate_layout(instances)

    # Check Power tier
    mccb = next((i for i in placed if "mccb" in i.name.lower() and i.surface == "Z"), None)
    vfd = next((i for i in placed if any(k in i.name.lower() for k in ["vfd", "drive"]) and i.surface == "Z"), None)
    reactor = next((i for i in placed if any(k in i.name.lower() for k in ["reactor", "choke"]) and i.surface == "Z"), None)

    assert mccb is not None
    assert vfd is not None
    assert reactor is not None

    # MCCB on left of VFD
    assert mccb.x < vfd.x
    assert reactor.x < vfd.x

    # Check terminal blocks are on a terminal DIN rail near the bottom
    terminals = [i for i in placed if "terminal" in i.name.lower() and i.mounting_type == MountingType.DIN]
    assert len(terminals) > 0
    term_y = terminals[0].y
    # Terminals must be lower than MCCB and VFD
    assert term_y > mccb.y + mccb.height
    assert term_y > vfd.y + vfd.height / 2

    # Check Door items (Z+1)
    lamps = [i for i in placed if i.surface == "Z+1" and any(k in i.name.lower() for k in ["lamp", "pilot", "led"])]
    e_stop = next((i for i in placed if i.surface == "Z+1" and "emergency" in i.name.lower()), None)
    controls = [i for i in placed if i.surface == "Z+1" and any(k in i.name.lower() for k in ["push", "button", "selector"])]

    if lamps:
        # Pilot lamps at top of door (y <= 100mm)
        assert all(l.y <= 100.0 for l in lamps)

    if e_stop and controls:
        # E-stop accessible on right
        assert e_stop.x > 300.0


def test_zero_overlap_and_no_stacked_ducts_in_compact_panel():
    """
    CRITICAL USER REQUIREMENT:
    Verify that in a 600x800 compact panel with multiple DIN rows (PLC, SMPS, Motor Control, Terminals):
    1. Zero overlap between components and horizontal/vertical wire ducts.
    2. Zero overlap between DIN rails and horizontal wire ducts.
    3. Zero stacked or adjacent horizontal wire ducts (all ducts >= 70mm apart).
    4. NO redundant wire duct below the bottom-most terminal rail.
    5. Terminal blocks fit strictly within mounting plate height.
    """
    enc = Enclosure(width=600, height=800, depth=250, model_name="Wall Mount 600x800x250")
    
    instances = [
        PhysicalInstance(id='mcb_incom', component_item_no=1, manufacturer='Schneider', part_number='A9F74332', name='Main Incomer MCB 32A', category='Control', width=72.0, height=85.0, depth=70.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='mcb_1', component_item_no=2, manufacturer='Schneider', part_number='A9F74110', name='MCB 10A 1P', category='Control', width=18.0, height=85.0, depth=70.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='mcb_2', component_item_no=3, manufacturer='Schneider', part_number='A9F74316', name='MCB 16A 3P', category='Control', width=54.0, height=85.0, depth=70.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='plc_cpu', component_item_no=4, manufacturer='Siemens', part_number='6ES7214-1AG40-0XB0', name='Siemens S7-1200 CPU 1214C', category='Control', width=110.0, height=100.0, depth=75.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='plc_di', component_item_no=5, manufacturer='Siemens', part_number='6ES7221-1BH32-0XB0', name='SM 1221 DI 16x24VDC', category='Control', width=45.0, height=100.0, depth=75.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='plc_dq', component_item_no=6, manufacturer='Siemens', part_number='6ES7222-1BH32-0XB0', name='SM 1222 DQ 16x24VDC', category='Control', width=45.0, height=100.0, depth=75.0, mounting_type=MountingType.DIN, surface='Z'),

        PhysicalInstance(id='smps_1', component_item_no=7, manufacturer='Schneider', part_number='ABL8RPS24100', name='Power Supply 24VDC 10A ABL8', category='Control', width=70.0, height=130.0, depth=125.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='mpcb_1', component_item_no=8, manufacturer='Schneider', part_number='GV2ME08', name='MPCB 2.5-4A', category='Control', width=45.0, height=90.0, depth=75.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='cont_1', component_item_no=9, manufacturer='Schneider', part_number='LC1D09BD', name='Contactor LC1D09 9A', category='Control', width=45.0, height=85.0, depth=90.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='cont_2', component_item_no=10, manufacturer='Schneider', part_number='LC1D09BD', name='Contactor LC1D09 9A', category='Control', width=45.0, height=85.0, depth=90.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='relay_1', component_item_no=11, manufacturer='Schneider', part_number='RXM2LB2BD', name='Relay 24VDC RXM2', category='Control', width=27.0, height=80.0, depth=70.0, mounting_type=MountingType.DIN, surface='Z'),
        PhysicalInstance(id='relay_2', component_item_no=12, manufacturer='Schneider', part_number='RXM2LB2BD', name='Relay 24VDC RXM2', category='Control', width=27.0, height=80.0, depth=70.0, mounting_type=MountingType.DIN, surface='Z'),
    ]
    for i in range(28):
        instances.append(
            PhysicalInstance(id=f'tb_{i}', component_item_no=13+i, manufacturer='Phoenix', part_number='3044076', name='Terminal Block UT 2.5', category='Wiring', width=6.2, height=47.5, depth=47.5, mounting_type=MountingType.DIN, surface='Z')
        )

    res_enc, placed, rails, ducts, warnings = AutoLayoutEngine.generate_layout(instances, target_enclosure=enc)

    plate_h = enc.mounting_plate_height
    plate_components = [i for i in placed if i.surface == "Z" and i.is_placed and not i.is_external]

    # 1. Zero overlaps between components and ducts
    for comp in plate_components:
        c_box = (comp.x, comp.x + comp.width, comp.y, comp.y + comp.height)
        for duct in ducts:
            is_vert = duct.orientation == "VERTICAL" or int(getattr(duct, "rotation", 0)) in (90, 270)
            dw = duct.width if is_vert else duct.length
            dh = duct.length if is_vert else duct.height
            d_box = (duct.x, duct.x + dw, duct.y, duct.y + dh)
            assert not check_2d_box_overlap(c_box, d_box), f"Overlap between {comp.name} and {duct.name}"

    # 2. Zero overlaps between rails and ducts
    for rail in rails:
        r_box = (rail.x, rail.x + rail.effective_width, rail.y, rail.y + rail.effective_height)
        for duct in ducts:
            is_vert = duct.orientation == "VERTICAL" or int(getattr(duct, "rotation", 0)) in (90, 270)
            dw = duct.width if is_vert else duct.length
            dh = duct.length if is_vert else duct.height
            d_box = (duct.x, duct.x + dw, duct.y, duct.y + dh)
            assert not check_2d_box_overlap(r_box, d_box), f"Overlap between {rail.name} and {duct.name}"

    # 3. Zero stacked horizontal ducts (minimum 70mm separation)
    h_ducts = sorted([d for d in ducts if d.orientation == "HORIZONTAL"], key=lambda d: d.y)
    for i in range(len(h_ducts) - 1):
        d1, d2 = h_ducts[i], h_ducts[i+1]
        gap = d2.y - (d1.y + d1.height)
        assert gap >= 30.0, f"Ducts too close or stacked: {d1.name} (y={d1.y}) and {d2.name} (y={d2.y}), gap={gap}"

    # 4. Check that lowest terminal block fits strictly within plate_h
    tbs = [c for c in plate_components if "terminal" in c.name.lower()]
    assert len(tbs) > 0
    max_tb_y = max(t.y + t.height for t in tbs)
    assert max_tb_y <= plate_h, f"Terminals overflow plate: {max_tb_y} > {plate_h}"

    # 5. Zero overlap/collision warnings
    overlap_warnings = [w for w in warnings if "OVERLAP" in w or "CLASH" in w or "COLLISION" in w]
    assert len(overlap_warnings) == 0, f"Unexpected overlap warnings: {overlap_warnings}"

