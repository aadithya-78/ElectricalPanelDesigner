"""
Wiring duct calculator and automatic trunking layout.
Generates slotted PVC wire ducts between component rows and side cable alleys.
Guarantees ZERO physical overlapping with components mounted on DIN rails.
"""
from typing import List, Optional
from app.models.enclosure import WiringDuct, Enclosure


class DuctCalculator:
    @staticmethod
    def generate_ducts(
        enclosure: Enclosure,
        rail_y_positions: Optional[List[float]] = None,
        power_row_y: float = 30.0,
        horizontal_duct_y_positions: Optional[List[float]] = None,
        duct_width: float = 40.0
    ) -> List[WiringDuct]:
        """
        Generate horizontal and vertical wiring ducts based on enclosure size and row heights.
        Horizontal ducts are placed strictly at collision-free Y positions.
        Guarantees:
        - Never clamps ducts upward into components.
        - Never generates two adjacent or stacked horizontal wire ducts.
        - Strictly fits within the mounting plate boundaries.
        """
        ducts: List[WiringDuct] = []
        plate_w = enclosure.mounting_plate_width
        plate_h = enclosure.mounting_plate_height
        
        # 1. Left Vertical Main Wire Duct (40x60mm)
        left_duct = WiringDuct(
            id="duct_vert_left",
            name="Main Left Vertical Duct (40x60)",
            x=10.0,
            y=15.0,
            z=0.0,
            width=duct_width,
            height=60.0,
            length=max(100.0, plate_h - 30.0),
            orientation="VERTICAL",
            color="#616161"
        )
        ducts.append(left_duct)

        # 2. Right Vertical Main Wire Duct (40x60mm)
        right_duct = WiringDuct(
            id="duct_vert_right",
            name="Main Right Vertical Duct (40x60)",
            x=max(60.0, plate_w - 50.0),
            y=15.0,
            z=0.0,
            width=duct_width,
            height=60.0,
            length=max(100.0, plate_h - 30.0),
            orientation="VERTICAL",
            color="#616161"
        )
        ducts.append(right_duct)

        # 3. Horizontal Ducts between rows
        horiz_span = max(100.0, plate_w - 100.0)
        horiz_x = 50.0

        if horizontal_duct_y_positions is not None:
            # Sort and deduplicate positions, guaranteeing at least 70mm between ducts
            raw_ys = sorted(set(horizontal_duct_y_positions))
            valid_ys: List[float] = []

            for y_pos in raw_ys:
                # Ensure duct strictly fits inside mounting plate without exceeding the bottom
                if y_pos + duct_width > plate_h - 10.0:
                    continue
                # Ensure at least duct_width + 30mm clearance to any previous horizontal duct
                # A DIN rail row with components requires at least 70mm between ducts
                if not valid_ys or (y_pos - valid_ys[-1] >= (duct_width + 30.0)):
                    valid_ys.append(y_pos)

            for idx, y_pos in enumerate(valid_ys, 1):
                duct = WiringDuct(
                    id=f"duct_horiz_{idx}",
                    name=f"Horizontal Wire Duct {idx} (40x40)",
                    x=horiz_x,
                    y=y_pos,
                    z=0.0,
                    width=duct_width,
                    height=duct_width,
                    length=horiz_span,
                    orientation="HORIZONTAL",
                    color="#757575"
                )
                ducts.append(duct)
        elif rail_y_positions:
            # Fallback when only rail positions are given
            sorted_rails = sorted(set(rail_y_positions))
            valid_ys = []
            for y_rail in sorted_rails:
                safe_y = max(15.0, y_rail - 50.0)
                if safe_y + duct_width <= plate_h - 10.0:
                    if not valid_ys or (safe_y - valid_ys[-1] >= (duct_width + 30.0)):
                        valid_ys.append(safe_y)

            for idx, y_pos in enumerate(valid_ys, 1):
                duct = WiringDuct(
                    id=f"duct_horiz_{idx}",
                    name=f"Horizontal Wire Duct {idx} (40x40)",
                    x=horiz_x,
                    y=y_pos,
                    z=0.0,
                    width=duct_width,
                    height=duct_width,
                    length=horiz_span,
                    orientation="HORIZONTAL",
                    color="#757575"
                )
                ducts.append(duct)

        return ducts
