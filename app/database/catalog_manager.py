"""
Catalog Manager for loading, searching, and filtering industrial electrical components from Excel files.
Manages components across Siemens, Schneider Electric, Phoenix Contact, and other brands.
"""
import os
import glob
from typing import List, Dict, Any, Optional
import pandas as pd
from app.models.component import Component, ComponentCategory, MountingType, ValidationStatus


class CatalogManager:
    """Loads and caches components from Excel catalog files in the catalogs/ directory."""
    _instance: Optional["CatalogManager"] = None

    def __init__(self, catalogs_dir: Optional[str] = None):
        if catalogs_dir is None:
            import sys
            candidates = []
            if hasattr(sys, "_MEIPASS"):
                candidates.append(os.path.join(sys._MEIPASS, "catalogs"))
            candidates.append(os.path.abspath(os.path.join(os.path.dirname(sys.executable), "catalogs")))
            candidates.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "catalogs")))
            candidates.append(os.path.abspath(os.path.join(os.getcwd(), "catalogs")))

            for cand in candidates:
                if os.path.exists(cand) and glob.glob(os.path.join(cand, "*.xlsx")):
                    self.catalogs_dir = cand
                    break
            else:
                self.catalogs_dir = candidates[0] if candidates else os.path.abspath("catalogs")
        else:
            self.catalogs_dir = catalogs_dir

        self.df: pd.DataFrame = pd.DataFrame()
        self.load_catalogs()

    @classmethod
    def get_instance(cls) -> "CatalogManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_catalogs(self) -> None:
        """Scan and load all .xlsx files in catalogs_dir into a unified DataFrame."""
        if not os.path.exists(self.catalogs_dir):
            os.makedirs(self.catalogs_dir, exist_ok=True)

        excel_files = glob.glob(os.path.join(self.catalogs_dir, "*.xlsx"))
        dfs = []
        for file in excel_files:
            try:
                sub_df = pd.read_excel(file)
                dfs.append(sub_df)
            except Exception as e:
                print(f"Error reading {file}: {e}")

        if dfs:
            self.df = pd.concat(dfs, ignore_index=True)
            # Ensure text columns are clean strings
            for col in ["Category", "Manufacturer", "Part_Number", "Name", "Description", "Mounting_Type", "Default_Surface", "Voltage_V"]:
                if col in self.df.columns:
                    self.df[col] = self.df[col].fillna("").astype(str)
        else:
            self.df = pd.DataFrame()

    def get_categories(self) -> List[str]:
        if self.df.empty or "Category" not in self.df.columns:
            return []
        cats = sorted(list(self.df["Category"].dropna().unique()))
        return [c for c in cats if c]

    def get_manufacturers(self) -> List[str]:
        if self.df.empty or "Manufacturer" not in self.df.columns:
            return []
        mfrs = sorted(list(self.df["Manufacturer"].dropna().unique()))
        return [m for m in mfrs if m]

    def search(
        self,
        query: str = "",
        category: str = "All",
        manufacturer: str = "All",
        surface: str = "All"
    ) -> List[Dict[str, Any]]:
        """
        Search catalog with multiple filters:
        - query: searches in Part_Number, Name, Description, Voltage_V
        - category: filter by specific category
        - manufacturer: filter by manufacturer
        - surface: 'Z' (Mounting Plate), 'Z+1' (Door), or 'All'
        """
        if self.df.empty:
            return []

        filtered = self.df.copy()

        if category and category != "All" and "Category" in filtered.columns:
            filtered = filtered[filtered["Category"].str.lower() == category.lower()]

        if manufacturer and manufacturer != "All" and "Manufacturer" in filtered.columns:
            filtered = filtered[filtered["Manufacturer"].str.lower() == manufacturer.lower()]

        if surface and surface != "All" and "Default_Surface" in filtered.columns:
            filtered = filtered[filtered["Default_Surface"].str.upper() == surface.upper()]

        if query and query.strip():
            terms = query.strip().lower().split()
            for term in terms:
                mask = (
                    filtered["Part_Number"].str.lower().str.contains(term, na=False) |
                    filtered["Name"].str.lower().str.contains(term, na=False) |
                    filtered["Description"].str.lower().str.contains(term, na=False) |
                    filtered["Manufacturer"].str.lower().str.contains(term, na=False) |
                    filtered["Voltage_V"].str.lower().str.contains(term, na=False)
                )
                filtered = filtered[mask]

        return filtered.to_dict(orient="records")

    def create_component_from_record(self, record: Dict[str, Any], item_no: int, quantity: int = 1) -> Component:
        """Convert a catalog record dictionary into a Component dataclass instance."""
        cat_str = str(record.get("Category", "Power"))
        # Map category
        cat_enum = ComponentCategory.POWER
        if any(c in cat_str.lower() for c in ["plc", "hmi", "push", "switch", "relay", "smps"]):
            cat_enum = ComponentCategory.CONTROL
        elif "terminal" in cat_str.lower() or "distribution" in cat_str.lower():
            cat_enum = ComponentCategory.WIRING

        # Map mounting type
        mount_str = str(record.get("Mounting_Type", "Plate")).lower()
        if "din" in mount_str:
            mount_enum = MountingType.DIN
        elif "door" in mount_str:
            mount_enum = MountingType.DOOR
        else:
            mount_enum = MountingType.PLATE

        surface = str(record.get("Default_Surface", "Z")).upper()
        if not surface:
            surface = "Z+1" if mount_enum == MountingType.DOOR else "Z"

        comp = Component(
            item_no=item_no,
            category=cat_enum,
            name=str(record.get("Name", "Component")),
            manufacturer=str(record.get("Manufacturer", "Generic")),
            part_number=str(record.get("Part_Number", "")),
            part_number_verified=True,
            description=str(record.get("Description", "")),
            quantity=max(1, quantity),
            width_mm=float(record.get("Width_mm", 50.0)),
            height_mm=float(record.get("Height_mm", 75.0)),
            depth_mm=float(record.get("Depth_mm", 60.0)),
            mounting_type=mount_enum,
            clearance_top_mm=10.0,
            clearance_bottom_mm=10.0,
            clearance_sides_mm=5.0,
            heat_loss_watts=float(record.get("Heat_Loss_W", 0.0)),
            unit_price=float(record.get("Unit_Price_USD", 0.0)),
            validation=ValidationStatus.VERIFIED,
            surface=surface,
            voltage=str(record.get("Voltage_V", "")),
            rated_current_a=float(record.get("Rated_Current_A", 0.0)),
            power_kw=float(record.get("Power_kW", 0.0)),
            frequency_hz=float(record.get("Frequency_Hz", 50.0))
        )
        comp.calculate_total_price()
        return comp

