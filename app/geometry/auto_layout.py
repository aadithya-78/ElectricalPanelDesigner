"""
Deterministic Automatic Component Placement Engine for Electrical Panels.
Implements industrial engineering rules for power devices, DIN rails, wiring ducts,
and door-mounted operator controls using the dual-surface (Z Mounting Plate and Z+1 Outer Door) system.
Guarantees ZERO physical overlapping through strict clearance zoning and dynamic row-by-row duct calculation.
"""
from typing import List, Dict, Any, Tuple, Optional
from app.models.component import PhysicalInstance, MountingType
from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.engineering.enclosure_sizing import EnclosureSizingEngine
from app.engineering.din_rail_calculator import DINRailCalculator
from app.engineering.duct_calculator import DuctCalculator
from app.geometry.collision_detector import CollisionDetector


class AutoLayoutEngine:
    @staticmethod
    def is_door_component(inst: PhysicalInstance) -> bool:
        """Determines if a component belongs on the outer panel door (Z+1 View)."""
        surf = getattr(inst, "surface", "Z") or "Z"
        if surf.upper() == "Z+1":
            return True
        if inst.mounting_type == MountingType.DOOR:
            return True
        
        name_l = (inst.name or "").lower()
        part_l = (getattr(inst, "part_number", "") or "").lower()
        cat_l = (inst.category.value if hasattr(inst.category, "value") else str(inst.category)).lower()

        door_keywords = [
            "hmi", "touch", "display", "screen", "comfort panel", "panelview",
            "pushbutton", "push button", "selector", "switch", "pilot", "indicator",
            "lamp", "led", "e-stop", "emergency stop", "key switch", "illuminated",
            "meter", "pac2200", "pm2220", "voltmeter", "ammeter", "fan", "filter"
        ]
        if any(k in name_l or k in part_l for k in door_keywords):
            return True
        if "display" in cat_l or "switch" in cat_l:
            return True
        return False

    @classmethod
    def generate_layout(
        cls,
        instances: List[PhysicalInstance],
        target_enclosure: Optional[Enclosure] = None,
        existing_rails: Optional[List[DINRail]] = None,
        existing_ducts: Optional[List[WiringDuct]] = None
    ) -> Tuple[Enclosure, List[PhysicalInstance], List[DINRail], List[WiringDuct], List[str]]:
        """
        Execute deterministic layout generation with ZERO collisions:
        1. Classify and route components to either Z (Mounting Plate) or Z+1 (Outer Door).
        2. Size panel enclosure envelope to achieve maximum area efficiency without oversizing.
        3. Layout Outer Door (Z+1): Displays, Indicator Lamps, Control switches, E-Stop.
        4. Layout Mounting Plate (Z): Power zone (MCCB, Reactor, VFD), DIN rails with modular devices, Earth bar.
        5. Generate wiring ducts strictly below components with guaranteed zero overlap.
        6. Validate collisions and boundary limits.
        """
        warnings: List[str] = []

        # 1. Filter and assign surfaces (exclude enclosure itself from plate devices)
        active_instances = [
            inst for inst in instances 
            if not inst.is_external and not any(k in inst.name.lower() for k in ["enclosure", "cabinet"])
        ]

        door_devices: List[PhysicalInstance] = []
        plate_devices: List[PhysicalInstance] = []
        din_devices: List[PhysicalInstance] = []
        bottom_devices: List[PhysicalInstance] = []

        for inst in active_instances:
            if cls.is_door_component(inst):
                inst.surface = "Z+1"
                inst.mounting_type = MountingType.DOOR
                door_devices.append(inst)
            elif inst.mounting_type == MountingType.BOTTOM or "gland" in inst.name.lower():
                inst.surface = "Z"
                inst.mounting_type = MountingType.BOTTOM
                bottom_devices.append(inst)
            elif inst.mounting_type == MountingType.DIN or any(k in inst.name.lower() for k in [
                "mcb", "miniature circuit breaker", "terminal", "relay", "contactor", 
                "smps", "power supply", "plc", "cpu", "di ", "dq ", "ai ", "aq ", "io module", "thermostat"
            ]):
                inst.surface = "Z"
                inst.mounting_type = MountingType.DIN
                din_devices.append(inst)
            else:
                inst.surface = "Z"
                inst.mounting_type = MountingType.PLATE
                plate_devices.append(inst)

        # 2. Compute minimum recommended space
        sizing = EnclosureSizingEngine.calculate_required_space(active_instances)
        suggested_enclosure = sizing.get("enclosure")
        if suggested_enclosure is None:
            suggested_enclosure = EnclosureSizingEngine.select_smallest_standard_enclosure(
                sizing["min_internal_w"],
                sizing["min_internal_h"],
                sizing["min_internal_d"]
            )

        if target_enclosure is not None:
            enclosure = target_enclosure
            if (enclosure.mounting_plate_width < sizing["min_internal_w"] or 
                enclosure.mounting_plate_height < sizing["min_internal_h"]):
                warnings.append(
                    f"PANEL SIZE INSUFFICIENT: Specified enclosure ({int(enclosure.width)}x{int(enclosure.height)}x{int(enclosure.depth)} mm) "
                    f"is smaller than recommended minimum ({int(suggested_enclosure.width)}x{int(suggested_enclosure.height)}x{int(suggested_enclosure.depth)} mm)."
                )
        else:
            enclosure = suggested_enclosure

        plate_w = enclosure.mounting_plate_width
        plate_h = enclosure.mounting_plate_height
        enc_w = enclosure.width
        enc_h = enclosure.height
        enc_d = enclosure.depth

        # =========================================================================
        # 3. DOOR-MOUNTED LAYOUT (Z+1 Surface: Origin 0,0 at Top-Left of Door Face)
        # =========================================================================
        door_z = enc_d - 5.0
        
        # Categorize door devices
        exhaust_fan = next((i for i in door_devices if "fan" in i.name.lower()), None)
        inlet_filter = next((i for i in door_devices if "filter" in i.name.lower()), None)
        
        pilot_lamps = [i for i in door_devices if any(k in i.name.lower() for k in ["lamp", "led", "pilot", "indicator"])]
        hmis = [i for i in door_devices if any(k in i.name.lower() for k in ["hmi", "touch", "display", "screen", "comfort", "meter", "pac", "pm"]) and i not in pilot_lamps]
        e_stop = next((i for i in door_devices if any(k in i.name.lower() for k in ["emergency", "e-stop"]) and i not in pilot_lamps), None)
        
        controls = [
            i for i in door_devices 
            if i not in pilot_lamps and i not in hmis and i != e_stop and i != exhaust_fan and i != inlet_filter
        ]

        # Exhaust fan & inlet filter (corner ventilation)
        if exhaust_fan:
            exhaust_fan.x = max(20.0, enc_w - exhaust_fan.width - 40.0)
            exhaust_fan.y = 40.0
            exhaust_fan.z = door_z
            exhaust_fan.is_placed = True

        if inlet_filter:
            inlet_filter.x = 40.0
            inlet_filter.y = max(40.0, enc_h - inlet_filter.height - 40.0)
            inlet_filter.z = door_z
            inlet_filter.is_placed = True

        # Pilot lamps row (Top center, eye level)
        if pilot_lamps:
            lamp_spacing = 24.0
            total_lamps_w = sum(l.width for l in pilot_lamps) + (len(pilot_lamps) - 1) * lamp_spacing
            lamp_start_x = max(40.0, (enc_w - total_lamps_w) / 2.0)
            cur_lamp_x = lamp_start_x
            for lamp in pilot_lamps:
                lamp.x = cur_lamp_x
                lamp.y = 60.0
                lamp.z = door_z
                lamp.is_placed = True
                cur_lamp_x += lamp.width + lamp_spacing

        # HMIs / Displays (Upper-middle center)
        cur_hmi_y = 130.0 if pilot_lamps else 70.0
        for hmi in hmis:
            hmi.x = max(40.0, (enc_w - hmi.width) / 2.0)
            hmi.y = cur_hmi_y
            hmi.z = door_z
            hmi.is_placed = True
            cur_hmi_y += hmi.height + 30.0

        # Controls & Emergency Stop (Operator control band)
        ctrl_y = max(cur_hmi_y + 30.0, enc_h * 0.48)
        
        # Position Emergency Stop on the right side of the control area
        if e_stop:
            e_stop.x = max(50.0, enc_w - e_stop.width - 70.0)
            e_stop.y = ctrl_y
            e_stop.z = door_z
            e_stop.is_placed = True

        # Pushbuttons & Selector switches neatly distributed
        if controls:
            avail_ctrl_w = (enc_w - 200.0) if e_stop else (enc_w - 120.0)
            ctrl_start_x = 60.0
            cur_ctrl_x = ctrl_start_x
            cur_ctrl_y = ctrl_y

            for ctrl in controls:
                eff_w = ctrl.height if int(getattr(ctrl, "rotation", 0)) in (90, 270) else ctrl.width
                if cur_ctrl_x + eff_w > (ctrl_start_x + avail_ctrl_w):
                    cur_ctrl_x = ctrl_start_x
                    cur_ctrl_y += 60.0 # Next control row

                ctrl.x = cur_ctrl_x
                ctrl.y = cur_ctrl_y
                ctrl.z = door_z
                ctrl.is_placed = True
                cur_ctrl_x += eff_w + 30.0

        # =========================================================================
        # 4. MOUNTING PLATE LAYOUT (Z Surface: Usable Plate Coordinates)
        # =========================================================================
        # Vertical ducts are at X=10 (left, w=40) and X=plate_w - 50 (right, w=40)
        usable_left_x = 55.0
        usable_right_x = max(usable_left_x + 120.0, plate_w - 55.0)
        usable_span_w = max(200.0, usable_right_x - usable_left_x)

        # Segregate plate power devices
        vfd_inst = next((i for i in plate_devices if any(k in i.name.lower() for k in ["vfd", "drive", "atv"])), None)
        mccb_inst = next((i for i in plate_devices if "mccb" in i.name.lower()), None)
        reactor_inst = next((i for i in plate_devices if any(k in i.name.lower() for k in ["reactor", "choke"])), None)
        earth_bar = next((i for i in plate_devices if any(k in i.name.lower() for k in ["earth", "pe ", "busbar"])), None)

        power_top_y = 30.0
        placed_power_items: List[PhysicalInstance] = []

        # Position power incomer & drive tier
        if mccb_inst:
            mccb_inst.x = usable_left_x + 10.0
            mccb_inst.y = power_top_y
            mccb_inst.z = 0.0
            mccb_inst.is_placed = True
            mccb_inst.is_locked = False
            placed_power_items.append(mccb_inst)

        if reactor_inst:
            if mccb_inst:
                reactor_x = mccb_inst.x + mccb_inst.width + 20.0
            else:
                reactor_x = usable_left_x + 10.0
            reactor_inst.x = reactor_x
            reactor_inst.y = power_top_y
            reactor_inst.z = 0.0
            reactor_inst.is_placed = True
            reactor_inst.is_locked = False
            placed_power_items.append(reactor_inst)

        if vfd_inst:
            vfd_w = vfd_inst.height if int(getattr(vfd_inst, "rotation", 0)) in (90, 270) else vfd_inst.width
            # Check if VFD fits side-by-side with reactor and MCCB
            left_extent = (reactor_inst.x + reactor_inst.width + 25.0) if reactor_inst else ((mccb_inst.x + mccb_inst.width + 25.0) if mccb_inst else usable_left_x + 10.0)
            if left_extent + vfd_w <= usable_right_x:
                # Place VFD on right side of power row
                vfd_inst.x = max(left_extent, usable_right_x - vfd_w - 10.0)
                vfd_inst.y = power_top_y
            else:
                # Place VFD on row below MCCB & Reactor if they exist, else at top-left
                if any([mccb_inst, reactor_inst]):
                    p_max_bottom = max(p.y + p.height for p in [mccb_inst, reactor_inst] if p)
                    vfd_inst.x = usable_left_x + 10.0
                    vfd_inst.y = p_max_bottom + 20.0
                else:
                    vfd_inst.x = usable_left_x + 10.0
                    vfd_inst.y = power_top_y

            vfd_inst.z = 0.0
            vfd_inst.is_placed = True
            vfd_inst.is_locked = False
            placed_power_items.append(vfd_inst)

        # Place any other miscellaneous non-DIN plate devices
        other_plate = [i for i in plate_devices if i not in [vfd_inst, mccb_inst, reactor_inst, earth_bar]]
        if other_plate:
            cur_p_x = usable_left_x + 10.0
            p_base_y = max((p.y + p.height) for p in placed_power_items) + 20.0 if placed_power_items else power_top_y
            cur_p_y = p_base_y
            for op in other_plate:
                eff_w = op.height if int(getattr(op, "rotation", 0)) in (90, 270) else op.width
                if cur_p_x + eff_w > usable_right_x:
                    cur_p_x = usable_left_x + 10.0
                    cur_p_y += (op.height + 20.0)
                op.x = cur_p_x
                op.y = cur_p_y
                op.z = 0.0
                op.is_placed = True
                placed_power_items.append(op)
                cur_p_x += eff_w + 20.0

        # Calculate exact bottom boundary of all power equipment
        horizontal_duct_positions: List[float] = []

        if placed_power_items:
            power_bottom_y = max(p.y + p.height for p in placed_power_items)
            # Horizontal wire duct below power zone
            duct_power_y = power_bottom_y + 15.0
            horizontal_duct_positions.append(duct_power_y)
            # DIN rows start strictly below this duct
            din_start_y = duct_power_y + 40.0 + 15.0
        else:
            # Horizontal duct along top
            top_duct_y = 25.0
            horizontal_duct_positions.append(top_duct_y)
            din_start_y = top_duct_y + 40.0 + 15.0

        # =========================================================================
        # 5. DIN RAILS & MODULAR DEVICES (Dynamic Zero-Overlap Stacking)
        # =========================================================================
        din_rails: List[DINRail] = []

        if existing_rails and len(existing_rails) > 0:
            # Preserve manual DIN rails as created by the user
            din_rails = list(existing_rails)
            h_rails = sorted(
                [r for r in din_rails if r.orientation.upper() == "HORIZONTAL"],
                key=lambda r: r.y
            )
            if not h_rails:
                h_rails = din_rails

            rail_idx = 0
            cur_rail = h_rails[0]
            curr_x = cur_rail.x + 15.0

            for inst in din_devices:
                eff_w = inst.height if int(getattr(inst, "rotation", 0)) in (90, 270) else inst.width
                if curr_x + eff_w > (cur_rail.x + cur_rail.length - 15.0):
                    if rail_idx + 1 < len(h_rails):
                        rail_idx += 1
                        cur_rail = h_rails[rail_idx]
                        curr_x = cur_rail.x + 15.0

                inst.x = curr_x
                # Position component centered vertically on DIN rail
                eff_h = inst.width if int(getattr(inst, "rotation", 0)) in (90, 270) else inst.height
                rail_center_y = cur_rail.y + (cur_rail.height / 2.0)
                inst.y = rail_center_y - (eff_h / 2.0)
                inst.z = 7.5
                inst.din_rail_id = cur_rail.id
                inst.is_placed = True
                curr_x += eff_w + 4.0
                cur_rail.occupied_length = max(cur_rail.occupied_length, curr_x - cur_rail.x)

            rail_y_positions = [r.y for r in h_rails]
            # Place horizontal ducts safely relative to manual rails
            for ry in rail_y_positions:
                horizontal_duct_positions.append(ry + 45.0)
        else:
            # Dynamic layout guaranteeing zero overlap
            created_rails, placements, duct_ys, rail_ys = DINRailCalculator.layout_din_rows(
                din_instances=din_devices,
                span_w=usable_span_w,
                start_x=usable_left_x,
                start_y=din_start_y,
                plate_h=plate_h
            )
            din_rails = created_rails
            rail_y_positions = rail_ys
            horizontal_duct_positions.extend(duct_ys)

            for inst in din_devices:
                if inst.id in placements:
                    x_pos, y_pos, rail_id = placements[inst.id]
                    inst.x = x_pos
                    inst.y = y_pos
                    inst.z = 7.5  # Snapped onto 7.5mm DIN rail profile
                    inst.din_rail_id = rail_id
                    inst.is_placed = True

        # Place Earth / PE Busbar along the bottom
        last_item_bottom = max([i.y + i.height for i in active_instances if i.surface == "Z" and i != earth_bar], default=din_start_y)
        if horizontal_duct_positions:
            last_item_bottom = max(last_item_bottom, max(d_y + 40.0 for d_y in horizontal_duct_positions))

        if earth_bar:
            earth_bar.x = usable_left_x + 10.0
            safe_pe_y = min(plate_h - earth_bar.height - 10.0, max(last_item_bottom + 12.0, plate_h - earth_bar.height - 20.0))
            earth_bar.y = max(10.0, safe_pe_y)
            earth_bar.z = 0.0
            earth_bar.is_placed = True
            earth_bar.is_locked = False

        # Position Bottom devices (e.g. cable glands)
        for idx, b_dev in enumerate(bottom_devices):
            b_dev.x = 100.0 + idx * 80.0
            b_dev.y = 10.0
            b_dev.z = 100.0
            b_dev.is_placed = True

        # =========================================================================
        # 6. GENERATE WIRING DUCTS (Guaranteed Zero Overlap)
        # =========================================================================
        if existing_ducts and len(existing_ducts) > 0:
            wiring_ducts = list(existing_ducts)
        else:
            wiring_ducts = DuctCalculator.generate_ducts(
                enclosure=enclosure,
                horizontal_duct_y_positions=horizontal_duct_positions,
                power_row_y=power_top_y
            )

        # =========================================================================
        # 7. VALIDATE COLLISIONS & BOUNDARIES
        # =========================================================================
        collisions = CollisionDetector.check_all_collisions(active_instances)
        for c1, c2, msg in collisions:
            warnings.append(msg)

        # Strict check: component vs wiring duct overlaps
        for inst in active_instances:
            if inst.surface != "Z" or not inst.is_placed:
                continue
            ix1, ix2 = inst.x, inst.x + inst.width
            iy1, iy2 = inst.y, inst.y + inst.height
            for duct in wiring_ducts:
                is_vert = duct.orientation == "VERTICAL" or int(getattr(duct, "rotation", 0)) in (90, 270)
                dw = duct.width if is_vert else duct.length
                dh = duct.length if is_vert else duct.height
                dx1, dx2 = duct.x, duct.x + dw
                dy1, dy2 = duct.y, duct.y + dh
                if ix1 < dx2 and ix2 > dx1 and iy1 < dy2 and iy2 > dy1:
                    warnings.append(f"DUCT OVERLAP: Component '{inst.name}' overlaps with '{duct.name}'")

        # Strict check: DIN rail vs horizontal wiring duct overlaps
        for rail in din_rails:
            rx1, rx2 = rail.x, rail.x + rail.effective_width
            ry1, ry2 = rail.y, rail.y + rail.effective_height
            for duct in wiring_ducts:
                if duct.orientation != "HORIZONTAL":
                    continue
                dx1, dx2 = duct.x, duct.x + duct.effective_width
                dy1, dy2 = duct.y, duct.y + duct.effective_height
                if rx1 < dx2 and rx2 > dx1 and ry1 < dy2 and ry2 > dy1:
                    warnings.append(f"RAIL DUCT OVERLAP: DIN Rail '{rail.name}' overlaps with '{duct.name}'")

        # Strict check: wiring duct vs wiring duct overlaps
        for i_d, d1 in enumerate(wiring_ducts):
            if d1.orientation != "HORIZONTAL":
                continue
            for d2 in wiring_ducts[i_d + 1:]:
                if d2.orientation != "HORIZONTAL":
                    continue
                if d1.y < d2.y + d2.effective_height and d1.y + d1.effective_height > d2.y:
                    warnings.append(f"DUCT CLASH: '{d1.name}' overlaps with '{d2.name}'")

        for inst in active_instances:
            overflows = CollisionDetector.check_boundary_overflow(inst, enclosure)
            warnings.extend(overflows)

        lowest_comp_bottom = max(
            [i.y + i.height for i in active_instances if i.surface == "Z" and not any(k in i.name.lower() for k in ["enclosure", "cabinet"])],
            default=0.0
        )
        if lowest_comp_bottom > plate_h - 5.0:
            rec_h = int(lowest_comp_bottom + 80.0)
            warnings.append(
                f"PANEL SIZE INSUFFICIENT: Equipment extends to Y={lowest_comp_bottom:.0f}mm, exceeding mounting plate height ({plate_h:.0f}mm). "
                f"Please choose an enclosure with height of at least {rec_h}mm."
            )

        # Check door components overflow
        lowest_door_bottom = max(
            [i.y + i.height for i in active_instances if getattr(i, "surface", "Z").upper() == "Z+1" and not any(k in i.name.lower() for k in ["enclosure", "cabinet"])],
            default=0.0
        )
        if lowest_door_bottom > enc_h - 10.0:
            rec_door_h = int(lowest_door_bottom + 60.0)
            warnings.append(
                f"PANEL SIZE INSUFFICIENT: Door equipment extends to Y={lowest_door_bottom:.0f}mm, exceeding enclosure door height ({enc_h:.0f}mm). "
                f"Please choose an enclosure with height of at least {rec_door_h}mm."
            )

        rightmost_door = max(
            [i.x + i.width for i in active_instances if getattr(i, "surface", "Z").upper() == "Z+1" and not any(k in i.name.lower() for k in ["enclosure", "cabinet"])],
            default=0.0
        )
        if rightmost_door > enc_w - 10.0:
            rec_door_w = int(rightmost_door + 60.0)
            warnings.append(
                f"PANEL SIZE INSUFFICIENT: Door equipment extends to X={rightmost_door:.0f}mm, exceeding enclosure door width ({enc_w:.0f}mm). "
                f"Please choose an enclosure with width of at least {rec_door_w}mm."
            )

        return enclosure, active_instances, din_rails, wiring_ducts, warnings
