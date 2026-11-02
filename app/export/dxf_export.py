"""
2D CAD DXF (Drawing Exchange Format) Exporter for Electrical Control Panels.
Generates industry-standard AutoCAD Release 12 / 2000 ASCII DXF files readable by
AutoCAD, SolidWorks, DraftSight, LibreCAD, QCad, Fusion 360, and CNC punch/laser tools.
Zero external library dependencies (pure Python).
"""
import math
from typing import List, Optional
from app.models.project import ProjectData
from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.models.component import PhysicalInstance


class DXFExporter:
    """Exports 2D electrical panel layouts (Mounting Plate and Door) to standard AutoCAD DXF."""

    # Standard AutoCAD Color Indices (ACI)
    COLOR_RED = 1
    COLOR_YELLOW = 2
    COLOR_GREEN = 3
    COLOR_CYAN = 4
    COLOR_BLUE = 5
    COLOR_MAGENTA = 6
    COLOR_WHITE = 7
    COLOR_GREY = 8
    COLOR_DARK_GREY = 9
    COLOR_ORANGE = 30

    @classmethod
    def export_project(
        cls,
        project: ProjectData,
        file_path: str,
        include_door: bool = True
    ) -> bool:
        """Export complete project layout to DXF file."""
        try:
            dxf_text = cls.generate_dxf_string(
                project.enclosure,
                project.physical_instances,
                project.din_rails,
                project.wiring_ducts,
                project_name=project.project_name,
                include_door=include_door
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(dxf_text)
            return True
        except Exception as e:
            print(f"Error exporting DXF: {e}")
            return False

    @classmethod
    def generate_dxf_string(
        cls,
        enclosure: Enclosure,
        instances: List[PhysicalInstance],
        din_rails: List[DINRail],
        wiring_ducts: List[WiringDuct],
        project_name: str = "Control Panel",
        include_door: bool = True
    ) -> str:
        """Construct a complete, standard ASCII DXF string."""
        lines = []

        # 1. HEADER SECTION
        lines.extend([
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER",
            "1", "AC1009",      # AutoCAD Release 11/12 standard (universal compatibility)
            "9", "$INSUNITS",
            "70", "4",          # 4 = Millimeters
            "0", "ENDSEC"
        ])

        # 2. TABLES SECTION (Layers & Line Types)
        layers = [
            ("0", cls.COLOR_WHITE, "CONTINUOUS"),
            ("PANEL_BORDER", cls.COLOR_WHITE, "CONTINUOUS"),
            ("MOUNTING_PLATE", cls.COLOR_GREY, "CONTINUOUS"),
            ("DIN_RAILS", cls.COLOR_CYAN, "CONTINUOUS"),
            ("WIRE_DUCTS", cls.COLOR_DARK_GREY, "CONTINUOUS"),
            ("COMPONENTS_PLATE", cls.COLOR_ORANGE, "CONTINUOUS"),
            ("COMPONENTS_DOOR", cls.COLOR_YELLOW, "CONTINUOUS"),
            ("TEXT_LABELS", cls.COLOR_GREEN, "CONTINUOUS"),
            ("DIMENSIONS", cls.COLOR_RED, "CONTINUOUS"),
            ("TITLE_BLOCK", cls.COLOR_CYAN, "CONTINUOUS")
        ]

        lines.extend([
            "0", "SECTION",
            "2", "TABLES",
            "0", "TABLE",
            "2", "LTYPE",
            "70", "1",
            "0", "LTYPE",
            "2", "CONTINUOUS",
            "70", "0",
            "3", "Solid line",
            "72", "65",
            "73", "0",
            "40", "0.0",
            "0", "ENDTAB",
            "0", "TABLE",
            "2", "LAYER",
            "70", str(len(layers))
        ])

        for l_name, l_color, l_type in layers:
            lines.extend([
                "0", "LAYER",
                "2", l_name,
                "70", "0",
                "62", str(l_color),
                "6", l_type
            ])

        lines.extend([
            "0", "ENDTAB",
            "0", "ENDSEC"
        ])

        # 3. BLOCKS SECTION
        lines.extend([
            "0", "SECTION",
            "2", "BLOCKS",
            "0", "ENDSEC"
        ])

        # 4. ENTITIES SECTION
        lines.extend([
            "0", "SECTION",
            "2", "ENTITIES"
        ])

        # A. VIEW 1: MOUNTING PLATE VIEW (Base at X=0, Y=0)
        plate_w = enclosure.mounting_plate_width
        plate_h = enclosure.mounting_plate_height
        enc_w = enclosure.width
        enc_h = enclosure.height

        # Offset mounting plate inside enclosure frame
        mp_offset_x = (enc_w - plate_w) / 2.0
        mp_offset_y = (enc_h - plate_h) / 2.0

        # Outer Enclosure Outline
        cls._add_rect(lines, "PANEL_BORDER", 0, 0, enc_w, enc_h)
        cls._add_text(lines, "TITLE_BLOCK", enc_w / 2.0, enc_h + 35, 18.0, f"MOUNTING PLATE VIEW - {enc_w:.0f}x{enc_h:.0f} mm")

        # Mounting Plate Outline
        cls._add_rect(lines, "MOUNTING_PLATE", mp_offset_x, mp_offset_y, plate_w, plate_h)
        cls._add_text(lines, "MOUNTING_PLATE", mp_offset_x + 10, mp_offset_y + plate_h - 15, 8.0, f"Plate: {plate_w:.0f} x {plate_h:.0f} mm")

        # DIN Rails
        for rail in din_rails:
            rw = getattr(rail, "effective_width", getattr(rail, "length", 600.0))
            rh = getattr(rail, "effective_height", getattr(rail, "height", 35.0))
            rx = mp_offset_x + rail.x
            # Convert screen Y (top-down) to CAD Y (bottom-up)
            ry = mp_offset_y + (plate_h - rail.y - rh)
            cls._add_rect(lines, "DIN_RAILS", rx, ry, rw, rh)
            # Centerline indicator
            mid_y = ry + rh / 2.0
            cls._add_line(lines, "DIN_RAILS", rx, mid_y, rx + rw, mid_y)
            cls._add_text(lines, "TEXT_LABELS", rx + 5, mid_y + 2.0, 5.0, f"DIN Rail ({rw:.0f}mm)")

        # Wiring Ducts
        for duct in wiring_ducts:
            dw = getattr(duct, "effective_width", getattr(duct, "length", 600.0))
            dh = getattr(duct, "effective_height", getattr(duct, "width", 40.0))
            dx = mp_offset_x + duct.x
            # Convert screen Y (top-down) to CAD Y (bottom-up)
            dy = mp_offset_y + (plate_h - duct.y - dh)
            cls._add_rect(lines, "WIRE_DUCTS", dx, dy, dw, dh)
            cls._add_text(lines, "TEXT_LABELS", dx + 4, dy + dh / 2.0 - 2.0, 5.0, f"Duct {dw:.0f}x{dh:.0f}")

        # Plate Components (surface == "Z")
        for inst in instances:
            if not inst.is_placed:
                continue
            surf = getattr(inst, "surface", "Z").upper()
            if surf == "Z":
                cw = inst.width
                ch = inst.height
                cx = mp_offset_x + inst.x
                # Convert screen Y (top-down) to CAD Y (bottom-up)
                cy = mp_offset_y + (plate_h - inst.y - ch)
                cls._add_rect(lines, "COMPONENTS_PLATE", cx, cy, cw, ch)
                # Label
                label = inst.part_number or inst.name
                cls._add_text(lines, "TEXT_LABELS", cx + cw / 2.0, cy + ch / 2.0 + 2.0, min(6.0, max(3.5, ch * 0.15)), label, align_center=True)
                cls._add_text(lines, "TEXT_LABELS", cx + cw / 2.0, cy + ch / 2.0 - 6.0, min(5.0, max(3.0, ch * 0.12)), f"{cw:.0f}x{ch:.0f}", align_center=True)

        # B. VIEW 2: DOOR VIEW (Side-by-side at X = enc_w + 200)
        if include_door:
            door_x = enc_w + 200.0
            door_y = 0.0
            is_double = getattr(enclosure, "door_type", "SINGLE") == "DOUBLE_VERTICAL"

            # Outer Door Outline
            cls._add_rect(lines, "PANEL_BORDER", door_x, door_y, enc_w, enc_h)
            door_title = f"OUTER DOUBLE DOOR (VERTICAL SPLIT) - 2x {enc_w / 2.0:.0f}x{enc_h:.0f} mm" if is_double else f"OUTER DOOR VIEW (Z+1) - {enc_w:.0f}x{enc_h:.0f} mm"
            cls._add_text(lines, "TITLE_BLOCK", door_x + enc_w / 2.0, door_y + enc_h + 35, 18.0, door_title)

            if is_double:
                # Vertical split seam down the center
                mid_door_x = door_x + enc_w / 2.0
                cls._add_line(lines, "PANEL_BORDER", mid_door_x, door_y, mid_door_x, door_y + enc_h)
                cls._add_text(lines, "PANEL_BORDER", door_x + enc_w / 4.0, door_y + 15, 8.0, "LEFT DOOR LEAF", align_center=True)
                cls._add_text(lines, "PANEL_BORDER", door_x + 3.0 * enc_w / 4.0, door_y + 15, 8.0, "RIGHT DOOR LEAF", align_center=True)

            # Door Components (surface == "Z+1")
            for inst in instances:
                if not inst.is_placed:
                    continue
                surf = getattr(inst, "surface", "Z").upper()
                if surf == "Z+1":
                    cw = inst.width
                    ch = inst.height
                    cx = door_x + inst.x
                    # Convert screen Y (top-down) to CAD Y (bottom-up)
                    cy = door_y + (enc_h - inst.y - ch)
                    cls._add_rect(lines, "COMPONENTS_DOOR", cx, cy, cw, ch)
                    # Crosshairs for pilot lamps / pushbuttons / cutouts
                    cls._add_line(lines, "COMPONENTS_DOOR", cx + cw / 2.0, cy, cx + cw / 2.0, cy + ch)
                    cls._add_line(lines, "COMPONENTS_DOOR", cx, cy + ch / 2.0, cx + cw, cy + ch / 2.0)
                    # Label
                    label = inst.part_number or inst.name
                    cls._add_text(lines, "TEXT_LABELS", cx + cw / 2.0, cy + ch / 2.0 + 2.0, min(7.0, max(4.0, ch * 0.15)), label, align_center=True)
                    cls._add_text(lines, "TEXT_LABELS", cx + cw / 2.0, cy + ch / 2.0 - 6.0, min(5.5, max(3.0, ch * 0.12)), f"Cutout {cw:.0f}x{ch:.0f}", align_center=True)

        # C. TITLE BLOCK BANNER (Bottom)
        total_w = (enc_w * 2 + 200.0) if include_door else enc_w
        tb_y = -80.0
        cls._add_rect(lines, "TITLE_BLOCK", 0, tb_y, total_w, 60.0)
        cls._add_text(lines, "TITLE_BLOCK", 20, tb_y + 40, 10.0, f"PROJECT: {project_name.upper()}")
        door_label = "Double Door (Vertical Split)" if is_double else "Single Door"
        cls._add_text(lines, "TITLE_BLOCK", 20, tb_y + 24, 7.5, f"ENCLOSURE: {enc_w:.0f} x {enc_h:.0f} x {enclosure.depth:.0f} mm | IP{enclosure.ip_rating} | {door_label}")
        cls._add_text(lines, "TITLE_BLOCK", 20, tb_y + 10, 7.5, f"COMPONENTS: {len([i for i in instances if i.is_placed])} Placed Units | CAD GENERATED 2D MANUFACTURING DRAWING")

        lines.extend([
            "0", "ENDSEC",
            "0", "EOF"
        ])

        return "\n".join(lines)

    @classmethod
    def _add_line(
        cls,
        lines: List[str],
        layer: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float
    ):
        """Append an AutoCAD standard 2D LINE entity."""
        lines.extend([
            "0", "LINE",
            "8", layer,
            "10", f"{x1:.3f}",
            "20", f"{y1:.3f}",
            "30", "0.0",
            "11", f"{x2:.3f}",
            "21", f"{y2:.3f}",
            "31", "0.0"
        ])

    @classmethod
    def _add_rect(
        cls,
        lines: List[str],
        layer: str,
        x: float,
        y: float,
        w: float,
        h: float
    ):
        """Append 4 lines forming a closed rectangle."""
        x2 = x + w
        y2 = y + h
        cls._add_line(lines, layer, x, y, x2, y)
        cls._add_line(lines, layer, x2, y, x2, y2)
        cls._add_line(lines, layer, x2, y2, x, y2)
        cls._add_line(lines, layer, x, y2, x, y)

    @classmethod
    def _add_text(
        cls,
        lines: List[str],
        layer: str,
        x: float,
        y: float,
        height: float,
        text: str,
        align_center: bool = False
    ):
        """Append an AutoCAD standard TEXT entity."""
        clean_text = str(text).replace("\n", " ").replace("\r", "").strip()
        if not clean_text:
            return

        lines.extend([
            "0", "TEXT",
            "8", layer,
            "10", f"{x:.3f}",
            "20", f"{y:.3f}",
            "30", "0.0",
            "40", f"{height:.2f}",
            "1", clean_text
        ])
        if align_center:
            lines.extend([
                "72", "1",      # Horizontal alignment: Center
                "11", f"{x:.3f}",
                "21", f"{y:.3f}",
                "31", "0.0"
            ])
