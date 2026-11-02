"""
Enclosure, DIN Rail, and Wiring Duct data models.
Units: millimeters (mm).
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DINRail:
    """Standard DIN EN 60715 35mm Rail as an independent 2D workspace object."""
    id: str
    name: str = "DIN Rail 35mm"
    x: float = 50.0          # Left position (mm)
    y: float = 200.0         # Center-line / top position (mm)
    z: float = 0.0           # Mounting plate surface (mm)
    length: float = 600.0    # Rail span along major axis (mm)
    height: float = 35.0     # Standard height (mm)
    depth: float = 7.5       # Standard profile depth 7.5mm or 15mm (mm)
    orientation: str = "HORIZONTAL"  # "HORIZONTAL" or "VERTICAL"
    rotation: float = 0.0    # 0, 90, 180, 270 degrees
    is_locked: bool = False
    occupied_length: float = 0.0

    @property
    def utilization_percent(self) -> float:
        if self.length <= 0:
            return 0.0
        return round((self.occupied_length / self.length) * 100.0, 1)

    @property
    def effective_width(self) -> float:
        """Visual width on mounting plate considering orientation & rotation."""
        is_vert = self.orientation.upper() == "VERTICAL" or int(self.rotation) in (90, 270)
        return self.height if is_vert else self.length

    @property
    def effective_height(self) -> float:
        """Visual height on mounting plate considering orientation & rotation."""
        is_vert = self.orientation.upper() == "VERTICAL" or int(self.rotation) in (90, 270)
        return self.length if is_vert else self.height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "length": self.length,
            "height": self.height,
            "depth": self.depth,
            "orientation": self.orientation,
            "rotation": self.rotation,
            "is_locked": self.is_locked,
            "occupied_length": self.occupied_length
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DINRail":
        return cls(
            id=data["id"],
            name=data.get("name", "DIN Rail 35mm"),
            x=float(data.get("x", 50.0)),
            y=float(data.get("y", 200.0)),
            z=float(data.get("z", 0.0)),
            length=float(data.get("length", 600.0)),
            height=float(data.get("height", 35.0)),
            depth=float(data.get("depth", 7.5)),
            orientation=data.get("orientation", "HORIZONTAL"),
            rotation=float(data.get("rotation", 0.0)),
            is_locked=bool(data.get("is_locked", False)),
            occupied_length=float(data.get("occupied_length", 0.0))
        )


@dataclass
class WiringDuct:
    """Slotted Wiring Trunking / Duct as an independent 2D workspace object."""
    id: str
    name: str = "Wire Duct"
    x: float = 50.0
    y: float = 150.0
    z: float = 0.0
    width: float = 40.0      # Duct cross-section width (mm)
    height: float = 60.0     # Duct profile height / depth (mm)
    length: float = 600.0    # Length along span (mm)
    orientation: str = "HORIZONTAL"  # "HORIZONTAL" or "VERTICAL"
    rotation: float = 0.0    # 0, 90, 180, 270 degrees
    is_locked: bool = False
    color: str = "#616161"

    @property
    def effective_width(self) -> float:
        """Visual width on mounting plate considering orientation & rotation."""
        is_vert = self.orientation.upper() == "VERTICAL" or int(self.rotation) in (90, 270)
        return self.width if is_vert else self.length

    @property
    def effective_height(self) -> float:
        """Visual height on mounting plate considering orientation & rotation."""
        is_vert = self.orientation.upper() == "VERTICAL" or int(self.rotation) in (90, 270)
        return self.length if is_vert else self.height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "width": self.width,
            "height": self.height,
            "length": self.length,
            "orientation": self.orientation,
            "rotation": self.rotation,
            "is_locked": self.is_locked,
            "color": self.color
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WiringDuct":
        return cls(
            id=data["id"],
            name=data.get("name", "Wire Duct"),
            x=float(data.get("x", 50.0)),
            y=float(data.get("y", 150.0)),
            z=float(data.get("z", 0.0)),
            width=float(data.get("width", 40.0)),
            height=float(data.get("height", 60.0)),
            length=float(data.get("length", 600.0)),
            orientation=data.get("orientation", "HORIZONTAL"),
            rotation=float(data.get("rotation", 0.0)),
            is_locked=bool(data.get("is_locked", False)),
            color=data.get("color", "#616161")
        )


@dataclass
class StandardEnclosureCatalogItem:
    """Predefined standard industrial electrical enclosure size."""
    catalog_code: str
    name: str
    width: float             # External width (mm)
    height: float            # External height (mm)
    depth: float            # External depth (mm)
    mounting_plate_w: float  # Usable plate width (mm)
    mounting_plate_h: float  # Usable plate height (mm)
    usable_depth: float      # Max component depth allowed (mm)
    ip_rating: str = "IP54"
    manufacturer: str = "Rittal"


# Industrial standard enclosure catalogue sizes (e.g., Rittal AX / VX, Schneider Spacial S3D/SF)
STANDARD_ENCLOSURE_CATALOG: List[StandardEnclosureCatalogItem] = [
    # Compact Wall-Mount Cabinets
    StandardEnclosureCatalogItem("ENC-405021", "Wall Mount 400x500x210", 400, 500, 210, 340, 360, 133, "IP54"),
    StandardEnclosureCatalogItem("ENC-406021", "Wall Mount 400x600x210", 400, 600, 210, 340, 460, 133, "IP54"),
    StandardEnclosureCatalogItem("ENC-506021", "Wall Mount 500x600x210", 500, 600, 210, 440, 460, 133, "IP54"),
    StandardEnclosureCatalogItem("ENC-507025", "Wall Mount 500x700x250", 500, 700, 250, 440, 560, 173, "IP54"),
    StandardEnclosureCatalogItem("ENC-606021", "Wall Mount 600x600x210", 600, 600, 210, 540, 460, 133, "IP54"),
    StandardEnclosureCatalogItem("ENC-606025", "Wall Mount 600x600x250", 600, 600, 250, 540, 460, 173, "IP54"),
    StandardEnclosureCatalogItem("ENC-608025", "Wall Mount 600x800x250", 600, 800, 250, 540, 660, 173, "IP54"),
    StandardEnclosureCatalogItem("ENC-608030", "Wall Mount 600x800x300", 600, 800, 300, 540, 660, 223, "IP54"),
    StandardEnclosureCatalogItem("ENC-601025", "Wall Mount 600x1000x250", 600, 1000, 250, 540, 860, 173, "IP54"),
    StandardEnclosureCatalogItem("ENC-601030", "Wall Mount 600x1000x300", 600, 1000, 300, 540, 860, 223, "IP54"),

    # Medium Control & Automation Panels
    StandardEnclosureCatalogItem("ENC-808025", "Wall Mount 800x800x250", 800, 800, 250, 740, 660, 173, "IP54"),
    StandardEnclosureCatalogItem("ENC-808030", "Wall Mount 800x800x300", 800, 800, 300, 740, 660, 223, "IP54"),
    StandardEnclosureCatalogItem("ENC-801025", "Compact 800x1000x250", 800, 1000, 250, 740, 860, 173, "IP54"),
    StandardEnclosureCatalogItem("ENC-801030", "Compact 800x1000x300", 800, 1000, 300, 740, 860, 223, "IP54"),
    StandardEnclosureCatalogItem("ENC-801230", "Control Panel 800x1200x300", 800, 1200, 300, 740, 1060, 223, "IP54"),
    StandardEnclosureCatalogItem("ENC-801240", "Heavy Drive Panel 800x1200x400", 800, 1200, 400, 740, 1060, 323, "IP55"),

    # Floor / Large Control Panels
    StandardEnclosureCatalogItem("ENC-101030", "Control Panel 1000x1000x300", 1000, 1000, 300, 940, 860, 223, "IP55"),
    StandardEnclosureCatalogItem("ENC-101230", "Control Panel 1000x1200x300", 1000, 1200, 300, 940, 1060, 223, "IP55"),
    StandardEnclosureCatalogItem("ENC-101240", "Floor/Wall 1000x1200x400", 1000, 1200, 400, 940, 1060, 323, "IP55"),
    StandardEnclosureCatalogItem("ENC-101440", "Floor Standing 1000x1400x400", 1000, 1400, 400, 940, 1260, 323, "IP55"),
    StandardEnclosureCatalogItem("ENC-101640", "Floor Standing 1000x1600x400", 1000, 1600, 400, 940, 1460, 323, "IP55"),
    StandardEnclosureCatalogItem("ENC-121640", "Floor Standing 1200x1600x400", 1200, 1600, 400, 1140, 1460, 323, "IP55"),
    StandardEnclosureCatalogItem("ENC-121850", "Floor Standing 1200x1800x500", 1200, 1800, 500, 1140, 1660, 423, "IP55"),
    StandardEnclosureCatalogItem("ENC-122050", "Full Suite 1200x2000x500", 1200, 2000, 500, 1140, 1860, 423, "IP55"),
]


@dataclass
class Enclosure:
    """Enclosure specifications with internal vs external geometry."""
    width: float = 800.0             # External Width (mm)
    height: float = 1200.0           # External Height (mm)
    depth: float = 400.0             # External Depth (mm)
    wall_thickness: float = 2.0      # Metal sheet thickness (mm)
    door_clearance: float = 50.0     # Door inner space for lamps/switches (mm)
    plate_standoff: float = 25.0     # Stand-off between back wall and mounting plate (mm)
    gland_plate_height: float = 80.0 # Bottom cable gland reserved zone (mm)
    top_cable_margin: float = 60.0   # Top margin (mm)
    side_margin: float = 30.0        # Left/right margins to frame (mm)
    ip_rating: str = "IP54"
    door_type: str = "SINGLE"        # "SINGLE" or "DOUBLE_VERTICAL"
    manufacturer: str = "Schneider / Rittal"
    model_name: str = "Standard Industrial Enclosure"
    material: str = "Sheet Steel, Powder Coated RAL 7035"

    @property
    def internal_width(self) -> float:
        """Usable internal width inside side frames."""
        return max(100.0, self.width - 2 * (self.wall_thickness + self.side_margin))

    @property
    def internal_height(self) -> float:
        """Usable internal height inside enclosure."""
        return max(100.0, self.height - 2 * self.wall_thickness - self.gland_plate_height - self.top_cable_margin)

    @property
    def internal_depth(self) -> float:
        """Max usable depth from mounting plate to door."""
        return max(50.0, self.depth - self.wall_thickness - self.plate_standoff - self.door_clearance)

    @property
    def mounting_plate_width(self) -> float:
        return max(80.0, self.width - 2 * self.side_margin)

    @property
    def mounting_plate_height(self) -> float:
        return max(80.0, self.height - self.gland_plate_height - self.top_cable_margin)

    @property
    def volume_m3(self) -> float:
        return (self.width * self.height * self.depth) / 1e9

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "wall_thickness": self.wall_thickness,
            "door_clearance": self.door_clearance,
            "plate_standoff": self.plate_standoff,
            "gland_plate_height": self.gland_plate_height,
            "top_cable_margin": self.top_cable_margin,
            "side_margin": self.side_margin,
            "ip_rating": self.ip_rating,
            "door_type": self.door_type,
            "manufacturer": self.manufacturer,
            "model_name": self.model_name,
            "material": self.material,
            "internal_width": self.internal_width,
            "internal_height": self.internal_height,
            "internal_depth": self.internal_depth,
            "mounting_plate_width": self.mounting_plate_width,
            "mounting_plate_height": self.mounting_plate_height
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Enclosure":
        return cls(
            width=float(data.get("width", 800.0)),
            height=float(data.get("height", 1200.0)),
            depth=float(data.get("depth", 400.0)),
            wall_thickness=float(data.get("wall_thickness", 2.0)),
            door_clearance=float(data.get("door_clearance", 50.0)),
            plate_standoff=float(data.get("plate_standoff", 25.0)),
            gland_plate_height=float(data.get("gland_plate_height", 80.0)),
            top_cable_margin=float(data.get("top_cable_margin", 60.0)),
            side_margin=float(data.get("side_margin", 30.0)),
            ip_rating=str(data.get("ip_rating", "IP54")),
            door_type=str(data.get("door_type", "SINGLE")),
            manufacturer=str(data.get("manufacturer", "Schneider / Rittal")),
            model_name=str(data.get("model_name", "Standard Industrial Enclosure")),
            material=str(data.get("material", "Sheet Steel, Powder Coated RAL 7035"))
        )

