"""
Component and Physical Instance data models for AI Electrical Panel Designer.
Coordinate convention:
  X = Width (horizontal)
  Y = Height (vertical)
  Z = Depth (thickness / into the panel)
All dimensions in millimeters (mm).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class MountingType(str, Enum):
    PLATE = "Plate"
    DIN = "DIN Rail"
    DOOR = "Door"
    BOTTOM = "Bottom"
    EXTERNAL = "External"


class ValidationStatus(str, Enum):
    VERIFIED = "Verified"
    UNVERIFIED = "Unverified"
    REQUIRES_REVIEW = "Requires Review"


class ComponentCategory(str, Enum):
    POWER = "Power"
    CONTROL = "Control"
    ACCESSORIES = "Accessories"
    WIRING = "Wiring"


# Standard Category Colors for 3D cuboids
CATEGORY_COLORS: Dict[str, str] = {
    "VFD": "#1E88E5",          # Blue
    "Drive": "#1E88E5",        # Blue
    "MCCB": "#E53935",         # Red
    "MCB": "#FB8C00",          # Orange/Amber
    "Contactor": "#8E24AA",    # Purple
    "Relay": "#00ACC1",        # Cyan
    "SMPS": "#FFB300",         # Amber/Orange
    "Terminal Block": "#43A047", # Green
    "Reactor": "#5E35B1",      # Deep Purple
    "Filter": "#3949AB",       # Indigo
    "DIN Rail": "#9E9E9E",     # Silver/Grey
    "Wire Duct": "#757575",    # Dark Grey
    "Cooling Fan": "#00897B",  # Teal
    "Power": "#E53935",        # Red
    "Control": "#039BE5",      # Light Blue
    "Accessories": "#7CB342",  # Light Green
    "Wiring": "#F4511E",       # Deep Orange
    "Default": "#78909C"       # Blue Grey
}


def get_component_color(name: str, category: str = "Default") -> str:
    """Return appropriate hex color for 3D cuboid based on component name or category."""
    name_upper = name.upper()
    if any(k in name_upper for k in ["VFD", "DRIVE", "ATV", "INVERTER"]):
        return CATEGORY_COLORS["Drive"]
    if "MCCB" in name_upper:
        return CATEGORY_COLORS["MCCB"]
    if "MCB" in name_upper or "FUSE" in name_upper:
        return CATEGORY_COLORS["MCB"]
    if "CONTACTOR" in name_upper:
        return CATEGORY_COLORS["Contactor"]
    if "RELAY" in name_upper:
        return CATEGORY_COLORS["Relay"]
    if "SMPS" in name_upper or "POWER SUPPLY" in name_upper:
        return CATEGORY_COLORS["SMPS"]
    if "TERMINAL" in name_upper or "TB" in name_upper:
        return CATEGORY_COLORS["Terminal Block"]
    if "REACTOR" in name_upper or "CHOKE" in name_upper:
        return CATEGORY_COLORS["Reactor"]
    if "FAN" in name_upper:
        return CATEGORY_COLORS["Cooling Fan"]
    if "DIN" in name_upper:
        return CATEGORY_COLORS["DIN Rail"]
    if "DUCT" in name_upper or "TRUNKING" in name_upper:
        return CATEGORY_COLORS["Wire Duct"]
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["Default"])


@dataclass
class Component:
    """BOM Component specification."""
    item_no: int
    category: ComponentCategory
    name: str
    manufacturer: str
    part_number: Optional[str] = None
    part_number_verified: bool = False
    description: str = ""
    quantity: int = 1
    width_mm: float = 50.0      # X
    height_mm: float = 75.0     # Y
    depth_mm: float = 60.0      # Z
    mounting_type: MountingType = MountingType.PLATE
    clearance_top_mm: float = 10.0
    clearance_bottom_mm: float = 10.0
    clearance_sides_mm: float = 5.0
    heat_loss_watts: float = 0.0
    unit_price: float = 0.0
    total_price: float = 0.0
    validation: ValidationStatus = ValidationStatus.UNVERIFIED
    is_optional: bool = False
    is_external: bool = False
    notes: str = ""
    surface: str = "Z"           # "Z" (Mounting Plate) or "Z+1" (Door)
    voltage: str = ""
    rated_current_a: float = 0.0
    power_kw: float = 0.0
    frequency_hz: float = 50.0

    def __post_init__(self):
        if not self.total_price and self.unit_price:
            self.calculate_total_price()

    def calculate_total_price(self) -> float:
        self.total_price = round(self.quantity * self.unit_price, 2)
        return self.total_price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_no": self.item_no,
            "category": self.category.value if isinstance(self.category, ComponentCategory) else str(self.category),
            "name": self.name,
            "manufacturer": self.manufacturer,
            "part_number": self.part_number,
            "part_number_verified": self.part_number_verified,
            "description": self.description,
            "quantity": self.quantity,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "depth_mm": self.depth_mm,
            "mounting_type": self.mounting_type.value if isinstance(self.mounting_type, MountingType) else str(self.mounting_type),
            "clearance_top_mm": self.clearance_top_mm,
            "clearance_bottom_mm": self.clearance_bottom_mm,
            "clearance_sides_mm": self.clearance_sides_mm,
            "heat_loss_watts": self.heat_loss_watts,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "validation": self.validation.value if isinstance(self.validation, ValidationStatus) else str(self.validation),
            "is_optional": self.is_optional,
            "is_external": self.is_external,
            "notes": self.notes,
            "surface": self.surface,
            "voltage": self.voltage,
            "rated_current_a": self.rated_current_a,
            "power_kw": self.power_kw,
            "frequency_hz": self.frequency_hz
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Component":
        cat = data.get("category", "Power")
        category_enum = ComponentCategory.POWER
        for c in ComponentCategory:
            if c.value.lower() == str(cat).lower() or c.name.lower() == str(cat).lower():
                category_enum = c
                break

        mnt = data.get("mounting_type", "Plate")
        mounting_enum = MountingType.PLATE
        for m in MountingType:
            if m.value.lower() == str(mnt).lower() or m.name.lower() == str(mnt).lower():
                mounting_enum = m
                break

        val = data.get("validation", "Unverified")
        val_enum = ValidationStatus.UNVERIFIED
        for v in ValidationStatus:
            if v.value.lower() == str(val).lower() or v.name.lower() == str(val).lower():
                val_enum = v
                break

        surface = str(data.get("surface", "Z")).upper()
        if not surface:
            surface = "Z+1" if mounting_enum == MountingType.DOOR else "Z"

        return cls(
            item_no=int(data.get("item_no", 1)),
            category=category_enum,
            name=str(data.get("name", "Component")),
            manufacturer=str(data.get("manufacturer", "Generic")),
            part_number=data.get("part_number"),
            part_number_verified=bool(data.get("part_number_verified", False)),
            description=str(data.get("description", "")),
            quantity=int(data.get("quantity", 1)),
            width_mm=float(data.get("width_mm", 50.0)),
            height_mm=float(data.get("height_mm", 75.0)),
            depth_mm=float(data.get("depth_mm", 60.0)),
            mounting_type=mounting_enum,
            clearance_top_mm=float(data.get("clearance_top_mm", 10.0)),
            clearance_bottom_mm=float(data.get("clearance_bottom_mm", 10.0)),
            clearance_sides_mm=float(data.get("clearance_sides_mm", 5.0)),
            heat_loss_watts=float(data.get("heat_loss_watts", 0.0)),
            unit_price=float(data.get("unit_price", 0.0)),
            total_price=float(data.get("total_price", 0.0)),
            validation=val_enum,
            is_optional=bool(data.get("is_optional", False)),
            is_external=bool(data.get("is_external", False)),
            notes=str(data.get("notes", "")),
            surface=surface,
            voltage=str(data.get("voltage", "")),
            rated_current_a=float(data.get("rated_current_a", 0.0)),
            power_kw=float(data.get("power_kw", 0.0)),
            frequency_hz=float(data.get("frequency_hz", 50.0))
        )


@dataclass
class PhysicalInstance:
    """Individual 3D physical unit placed inside the enclosure."""
    id: str                         # Unique ID e.g. "inst_1_tb_3"
    component_item_no: int          # Reference back to BOM Item No
    name: str
    category: str
    manufacturer: str
    part_number: Optional[str]
    width: float                    # X (mm)
    height: float                   # Y (mm)
    depth: float                    # Z (mm)
    mounting_type: MountingType
    x: float = 0.0                  # X position in enclosure coordinates (left-to-right)
    y: float = 0.0                  # Y position in enclosure coordinates (bottom-to-top)
    z: float = 0.0                  # Z position (depth from mounting surface)
    rotation: float = 0.0           # Rotation around Z axis (0 or 90 deg)
    clearance_top: float = 10.0
    clearance_bottom: float = 10.0
    clearance_sides: float = 5.0
    is_locked: bool = False
    is_placed: bool = False
    is_external: bool = False
    din_rail_id: Optional[str] = None
    color: str = "#78909C"
    surface: str = "Z"             # "Z" (Mounting Plate) or "Z+1" (Door)
    voltage: str = ""
    rated_current_a: float = 0.0
    power_kw: float = 0.0
    frequency_hz: float = 50.0

    @property
    def effective_width(self) -> float:
        """Visual width considering rotation."""
        return self.height if int(getattr(self, "rotation", 0)) in (90, 270) else self.width

    @property
    def effective_height(self) -> float:
        """Visual height considering rotation."""
        return self.width if int(getattr(self, "rotation", 0)) in (90, 270) else self.height

    @property
    def bounding_box(self) -> Dict[str, float]:
        """Returns physical cuboid bounds: min_x, max_x, min_y, max_y, min_z, max_z."""
        eff_w = self.effective_width
        eff_h = self.effective_height
        return {
            "min_x": self.x,
            "max_x": self.x + eff_w,
            "min_y": self.y,
            "max_y": self.y + eff_h,
            "min_z": self.z,
            "max_z": self.z + self.depth
        }

    @property
    def clearance_box(self) -> Dict[str, float]:
        """Returns bounds including required safety & thermal clearances."""
        eff_w = self.height if int(self.rotation) in (90, 270) else self.width
        eff_h = self.width if int(self.rotation) in (90, 270) else self.height
        return {
            "min_x": self.x - self.clearance_sides,
            "max_x": self.x + eff_w + self.clearance_sides,
            "min_y": self.y - self.clearance_bottom,
            "max_y": self.y + eff_h + self.clearance_top,
            "min_z": self.z,
            "max_z": self.z + self.depth
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "component_item_no": self.component_item_no,
            "name": self.name,
            "category": self.category,
            "manufacturer": self.manufacturer,
            "part_number": self.part_number,
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "mounting_type": self.mounting_type.value if isinstance(self.mounting_type, MountingType) else str(self.mounting_type),
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "rotation": self.rotation,
            "clearance_top": self.clearance_top,
            "clearance_bottom": self.clearance_bottom,
            "clearance_sides": self.clearance_sides,
            "is_locked": self.is_locked,
            "is_placed": self.is_placed,
            "is_external": self.is_external,
            "din_rail_id": self.din_rail_id,
            "color": self.color,
            "surface": self.surface,
            "voltage": self.voltage,
            "rated_current_a": self.rated_current_a,
            "power_kw": self.power_kw,
            "frequency_hz": self.frequency_hz
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhysicalInstance":
        mnt = data.get("mounting_type", "Plate")
        mounting_enum = MountingType.PLATE
        for m in MountingType:
            if m.value.lower() == str(mnt).lower():
                mounting_enum = m
                break

        surface = str(data.get("surface", "Z")).upper()
        if not surface:
            surface = "Z+1" if mounting_enum == MountingType.DOOR else "Z"

        return cls(
            id=data["id"],
            component_item_no=int(data.get("component_item_no", 1)),
            name=data.get("name", "Instance"),
            category=data.get("category", "Power"),
            manufacturer=data.get("manufacturer", "Generic"),
            part_number=data.get("part_number"),
            width=float(data.get("width", 50.0)),
            height=float(data.get("height", 75.0)),
            depth=float(data.get("depth", 60.0)),
            mounting_type=mounting_enum,
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            z=float(data.get("z", 0.0)),
            rotation=float(data.get("rotation", 0.0)),
            clearance_top=float(data.get("clearance_top", 10.0)),
            clearance_bottom=float(data.get("clearance_bottom", 10.0)),
            clearance_sides=float(data.get("clearance_sides", 5.0)),
            is_locked=bool(data.get("is_locked", False)),
            is_placed=bool(data.get("is_placed", False)),
            is_external=bool(data.get("is_external", False)),
            din_rail_id=data.get("din_rail_id"),
            color=data.get("color", "#78909C"),
            surface=surface,
            voltage=str(data.get("voltage", "")),
            rated_current_a=float(data.get("rated_current_a", 0.0)),
            power_kw=float(data.get("power_kw", 0.0)),
            frequency_hz=float(data.get("frequency_hz", 50.0))
        )

