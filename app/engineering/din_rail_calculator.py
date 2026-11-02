"""
DIN Rail calculator and layout generator.
Ensures DIN EN 60715 35mm rails are physical objects behind DIN-mounted components.
Provides dynamic zero-overlap row stacking with proportional pitching and aesthetic industrial grouping.
"""
from typing import List, Dict, Tuple, Optional
from app.models.enclosure import DINRail
from app.models.component import PhysicalInstance, MountingType


class DINRailCalculator:
    @staticmethod
    def calculate_required_rail_length(instances: List[PhysicalInstance], spare_percent: float = 20.0) -> float:
        """Calculate total linear width needed for DIN devices plus spare space."""
        total_w = sum(inst.width for inst in instances)
        return total_w * (1.0 + spare_percent / 100.0)

    @classmethod
    def group_din_components(cls, din_instances: List[PhysicalInstance]) -> List[Tuple[str, List[PhysicalInstance]]]:
        """
        Group DIN components into clean industrial engineering tiers:
        Tier 1: Control & PLC Automation (SMPS, MCBs, PLC CPU & I/O expansion)
        Tier 2: Power Switching & Motor Control (MPCBs, Contactors, Relays)
        Tier 3: Field Terminals (Mains/Motor Power Terminals, Signal Terminals)
        """
        terminals: List[PhysicalInstance] = []
        control_devices: List[PhysicalInstance] = []
        motor_control_devices: List[PhysicalInstance] = []

        for inst in din_instances:
            name_l = inst.name.lower()
            cat_l = (inst.category.value if hasattr(inst.category, "value") else str(inst.category)).lower()

            if any(k in name_l for k in ["terminal", "tb ", "ground terminal", "terminal block"]):
                terminals.append(inst)
            elif any(k in name_l for k in ["mpcb", "motor starter", "contactor", "relay", "lc1d", "rxm", "gv2"]):
                motor_control_devices.append(inst)
            else:
                control_devices.append(inst)

        # Sort control devices: SMPS (24VDC) -> MCBs -> PLC CPU -> PLC I/O
        def ctrl_sort_key(i: PhysicalInstance) -> int:
            nl = i.name.lower()
            if any(k in nl for k in ["smps", "power supply", "quint", "power pack", "abl"]):
                return 1
            if any(k in nl for k in ["mcb", "circuit breaker", "fuse", "supplementary"]):
                return 2
            if "cpu" in nl or "plc" in nl:
                return 3
            if any(k in nl for k in ["di ", "dq ", "ai ", "aq ", "io module", "input", "output"]):
                return 4
            return 5

        control_devices.sort(key=ctrl_sort_key)

        # Sort motor control devices: MPCBs -> Contactors -> Relays -> Thermostats
        def motor_sort_key(i: PhysicalInstance) -> int:
            nl = i.name.lower()
            if "mpcb" in nl or "gv2" in nl or "motor starter" in nl:
                return 1
            if "contactor" in nl or "lc1d" in nl:
                return 2
            if "relay" in nl or "rxm" in nl:
                return 3
            return 4

        motor_control_devices.sort(key=motor_sort_key)

        # Sort terminals: Power / Mains / Motor terminals first, then Control terminals
        def terminal_sort_key(i: PhysicalInstance) -> int:
            nl = i.name.lower()
            if any(k in nl for k in ["35 sq mm", "mains", "power", "motor", "line"]):
                return 1
            return 2

        terminals.sort(key=terminal_sort_key)

        groups = []
        if control_devices:
            groups.append(("Control & PLC Automation", control_devices))
        if motor_control_devices:
            groups.append(("Motor Control & Switching", motor_control_devices))
        if terminals:
            groups.append(("Field Terminals", terminals))

        # If both control and motor control are present and their total count is small, merge them into 1 group
        # so they can share a rail if space permits
        if control_devices and motor_control_devices:
            # Keep separate so they are cleanly grouped, but layout_din_rows will merge into 1 rail if they fit
            pass

        return groups

    @classmethod
    def layout_din_rows(
        cls,
        din_instances: List[PhysicalInstance],
        span_w: float,
        start_x: float,
        start_y: float,
        plate_h: float = 4000.0
    ) -> Tuple[List[DINRail], Dict[str, Tuple[float, float, str]], List[float], List[float]]:
        """
        Dynamically layout DIN components into rows guaranteeing ZERO OVERLAP.
        Uses proportional vertical pitching so rows and intermediate horizontal ducts
        are evenly distributed within usable mounting plate height.
        
        CRITICAL INDUSTRIAL RULE:
        - Exactly (N - 1) intermediate horizontal ducts between N DIN rows.
        - NO horizontal duct below the bottom-most terminal rail (field cables enter from bottom gland plate).
        - Guaranteed minimum gap between components and ducts under all conditions.

        Returns:
            rails: List of created DINRail objects
            placements: Dict mapping instance ID -> (x_pos, y_pos, rail_id)
            duct_y_positions: List of Y coordinates for horizontal ducts between rows
            rail_y_positions: List of Y coordinates of the DIN rails
        """
        rails: List[DINRail] = []
        placements: Dict[str, Tuple[float, float, str]] = {}
        duct_y_positions: List[float] = []
        rail_y_positions: List[float] = []

        if not din_instances:
            return rails, placements, duct_y_positions, rail_y_positions

        groups = cls.group_din_components(din_instances)
        rail_len = max(200.0, span_w)
        rail_comp_capacity = rail_len - 20.0

        # Step 1: Pack items into logical rows fitting rail_comp_capacity
        planned_rows: List[Tuple[str, List[PhysicalInstance]]] = []

        # Check if control and motor control can fit on a single rail
        ctrl_group = next((items for title, items in groups if "control & plc" in title.lower()), None)
        motor_group = next((items for title, items in groups if "motor control" in title.lower()), None)

        used_merged_control = False
        if ctrl_group and motor_group:
            combined_items = ctrl_group + motor_group
            comb_w = sum(i.width + 4.0 for i in combined_items)
            if comb_w <= rail_comp_capacity:
                planned_rows.append(("Modular Control & Switching", combined_items))
                used_merged_control = True

        for group_title, items in groups:
            if used_merged_control and any(k in group_title.lower() for k in ["control & plc", "motor control"]):
                continue

            current_row_items: List[PhysicalInstance] = []
            current_row_w = 0.0
            part = 1

            for inst in items:
                eff_w = inst.height if int(getattr(inst, "rotation", 0)) in (90, 270) else inst.width
                is_terminal = any(k in inst.name.lower() for k in ["terminal", "tb"])
                is_plc_io = any(k in inst.name.lower() for k in ["di ", "dq ", "ai ", "aq ", "io"])
                gap = 0.0 if (is_terminal or is_plc_io) else 4.0

                if current_row_items and (current_row_w + eff_w + gap > rail_comp_capacity):
                    suffix = f" (Part {part})" if (part > 1 or len(items) > len(current_row_items)) else ""
                    planned_rows.append((f"{group_title}{suffix}", current_row_items))
                    current_row_items = [inst]
                    current_row_w = eff_w
                    part += 1
                else:
                    current_row_items.append(inst)
                    current_row_w += eff_w + gap

            if current_row_items:
                suffix = f" (Part {part})" if part > 1 else ""
                planned_rows.append((f"{group_title}{suffix}", current_row_items))

        num_rows = len(planned_rows)
        if num_rows == 0:
            return rails, placements, duct_y_positions, rail_y_positions

        # Step 2: Proportional Vertical Pitching
        # Compute available height from start_y to bottom gland/earth margin (plate_h - 45mm)
        safe_bottom_y = plate_h - 45.0
        avail_h = max(60.0, safe_bottom_y - start_y)

        # Intermediate wire duct height
        duct_h = 40.0
        row_heights = [max(inst.height for inst in items) for _, items in planned_rows]
        total_comp_h = sum(row_heights)
        total_duct_h = (num_rows - 1) * duct_h

        # Compute slack space
        slack_h = avail_h - (total_comp_h + total_duct_h)

        if num_rows == 1:
            row_gap = max(15.0, min(slack_h / 2.0, 40.0))
            cur_y = start_y + (row_gap if slack_h > 0 else 5.0)
        else:
            num_gaps = 2 * (num_rows - 1)
            if slack_h >= 0:
                # Comfortable space: distribute slack evenly between rows and ducts
                row_gap = max(12.0, min(30.0, slack_h / num_gaps))
            else:
                # Tight space: use compact duct height (30mm) and minimum safety gap (8mm)
                if duct_h == 40.0 and slack_h < -20.0:
                    duct_h = 30.0
                row_gap = 8.0
            cur_y = start_y

        # Step 3: Commit rows and intermediate ducts
        for row_idx, (group_title, items) in enumerate(planned_rows, 1):
            rail_id = f"din_rail_{row_idx}"
            max_h = max(inst.height for inst in items)

            # Centerline of the DIN rail
            rail_center_y = cur_y + (max_h / 2.0)
            rail_top_y = rail_center_y - (35.0 / 2.0)

            rail = DINRail(
                id=rail_id,
                name=f"DIN Rail {row_idx} ({group_title})",
                x=start_x,
                y=rail_top_y,
                z=0.0,
                length=rail_len,
                height=35.0,
                depth=7.5,
                orientation="HORIZONTAL",
                occupied_length=0.0
            )

            # Center components on the rail with zero lateral overlap
            curr_x = start_x + 10.0
            for inst in items:
                eff_w = inst.height if int(getattr(inst, "rotation", 0)) in (90, 270) else inst.width
                is_terminal = any(k in inst.name.lower() for k in ["terminal", "tb"])
                is_plc_io = any(k in inst.name.lower() for k in ["di ", "dq ", "ai ", "aq ", "io"])
                gap_x = 0.0 if (is_terminal or is_plc_io) else 4.0

                comp_y = rail_center_y - (inst.height / 2.0)
                placements[inst.id] = (curr_x, comp_y, rail_id)
                curr_x += eff_w + gap_x

            rail.occupied_length = curr_x - start_x
            rails.append(rail)
            rail_y_positions.append(rail.y)

            row_bottom_y = cur_y + max_h

            # Generate intermediate horizontal duct between this row and the next row
            # CRITICAL: NEVER place a duct below the last row (field terminals)
            if row_idx < num_rows:
                duct_y = row_bottom_y + row_gap
                # Ensure duct fits inside the plate
                if duct_y + duct_h <= plate_h - 10.0:
                    duct_y_positions.append(duct_y)
                cur_y = duct_y + duct_h + row_gap
            else:
                cur_y = row_bottom_y + row_gap

        return rails, placements, duct_y_positions, rail_y_positions

    @classmethod
    def organize_din_rails(
        cls,
        din_instances: List[PhysicalInstance],
        available_plate_w: float,
        rail_start_x: float,
        y_positions: List[float]
    ) -> Tuple[List[DINRail], Dict[str, Tuple[float, float, str]]]:
        """
        Organize DIN instances into physical DIN rails (backward-compatible API).
        """
        rails, placements, _, _ = cls.layout_din_rows(
            din_instances=din_instances,
            span_w=available_plate_w,
            start_x=rail_start_x,
            start_y=y_positions[0] if y_positions else 120.0
        )
        return rails, placements
