"""
Project data model containing complete panel design state.
"""
import json
import time
from typing import Dict, Any, List, Optional
from app.models.bom import BOM
from app.models.component import Component, PhysicalInstance, MountingType, ComponentCategory, get_component_color
from app.models.enclosure import Enclosure, DINRail, WiringDuct


class ProjectData:
    def __init__(self, project_name: str = "New Panel Project"):
        self.project_name: str = project_name
        self.raw_requirement: str = ""
        self.extracted_params: Dict[str, Any] = {}
        self.provisional_assumptions: List[str] = []
        self.manufacturer_selections: Dict[str, str] = {}
        self.bom: BOM = BOM()
        self.physical_instances: List[PhysicalInstance] = []
        self.din_rails: List[DINRail] = []
        self.wiring_ducts: List[WiringDuct] = []
        self.enclosure: Enclosure = Enclosure()
        self.thermal_data: Dict[str, Any] = {}
        self.layout_mode: str = "AUTOMATIC"
        self.created_at: str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at: str = self.created_at

    @property
    def name(self) -> str:
        return self.project_name

    @name.setter
    def name(self, val: str):
        self.project_name = val

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "raw_requirement": self.raw_requirement,
            "extracted_params": self.extracted_params,
            "provisional_assumptions": self.provisional_assumptions,
            "manufacturer_selections": self.manufacturer_selections,
            "bom": self.bom.to_list(),
            "physical_instances": [inst.to_dict() for inst in self.physical_instances],
            "din_rails": [r.to_dict() for r in self.din_rails],
            "wiring_ducts": [d.to_dict() for d in self.wiring_ducts],
            "enclosure": self.enclosure.to_dict(),
            "thermal_data": self.thermal_data,
            "layout_mode": self.layout_mode,
            "created_at": self.created_at,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectData":
        proj = cls(data.get("project_name", "Untitled Project"))
        proj.raw_requirement = data.get("raw_requirement", "")
        proj.extracted_params = data.get("extracted_params", {})
        proj.provisional_assumptions = data.get("provisional_assumptions", [])
        proj.manufacturer_selections = data.get("manufacturer_selections", {})
        
        bom_data = data.get("bom", [])
        proj.bom = BOM.from_list(bom_data)

        inst_data = data.get("physical_instances", [])
        proj.physical_instances = [PhysicalInstance.from_dict(d) for d in inst_data]

        rails_data = data.get("din_rails", [])
        proj.din_rails = [DINRail.from_dict(d) for d in rails_data]

        ducts_data = data.get("wiring_ducts", [])
        proj.wiring_ducts = [WiringDuct.from_dict(d) for d in ducts_data]

        enc_data = data.get("enclosure", {})
        if enc_data:
            proj.enclosure = Enclosure.from_dict(enc_data)

        proj.thermal_data = data.get("thermal_data", {})
        proj.layout_mode = data.get("layout_mode", "AUTOMATIC")
        proj.created_at = data.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        proj.updated_at = data.get("updated_at", proj.created_at)
        return proj

    def save_to_file(self, file_path: str) -> None:
        self.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def reconcile_instances_with_bom(self) -> None:
        """
        Reconciles physical_instances with the current BOM items non-destructively:
        - When a component is deleted from BOM, ONLY its instances are erased from 2D.
        - Existing placed components preserve their exact (X, Y, Z) coordinates,
          rotation, is_placed status, is_locked flag, and DIN rail bindings.
        - Dimensions and component metadata are refreshed from the BOM.
        - If quantities increased or new components were added, new unplaced instances are created.
        - Existing DIN rails and wiring ducts are preserved without modification.
        """
        if not self.bom or not self.bom.items:
            self.physical_instances = []
            return

        remaining_pool = list(self.physical_instances)
        reconciled_instances: List[PhysicalInstance] = []

        for comp in self.bom.items:
            if comp.is_external or comp.mounting_type == MountingType.EXTERNAL:
                continue
            if any(k in comp.name.lower() for k in ["enclosure", "cabinet"]):
                continue

            # Non-physical consumables with zero or negative dimensions
            is_consumable = (
                comp.category == ComponentCategory.WIRING or
                any(w in comp.name.lower() for w in ["wire", "cable", "ferrule", "lug", "tie", "marker"])
            ) and (comp.width_mm <= 0 or comp.height_mm <= 0 or comp.depth_mm <= 0)
            if is_consumable:
                continue

            target_qty = max(1, comp.quantity)
            comp_cat_str = comp.category.value if hasattr(comp.category, 'value') else str(comp.category)
            color = get_component_color(comp.name, comp_cat_str)

            # Score each available instance in the pool for this component
            matched_with_scores = []
            for inst in remaining_pool:
                score = 0
                # Part number match
                if comp.part_number and inst.part_number and comp.part_number.strip().lower() == inst.part_number.strip().lower():
                    score += 100
                # Exact name match
                if comp.name.strip().lower() == inst.name.strip().lower():
                    score += 80
                elif inst.name.strip().lower().startswith(comp.name.strip().lower() + " #"):
                    score += 70
                # Item number match
                if inst.component_item_no == comp.item_no:
                    score += 25
                # Manufacturer match
                if comp.manufacturer and inst.manufacturer and comp.manufacturer.strip().lower() == inst.manufacturer.strip().lower():
                    score += 15
                # Category match
                if comp_cat_str.lower() == inst.category.lower():
                    score += 10

                if score >= 40:
                    matched_with_scores.append((score, inst))

            # Sort candidate instances: highest match score first, then already placed ones first
            matched_with_scores.sort(key=lambda x: (x[0], 1 if x[1].is_placed else 0), reverse=True)
            matched_instances = [inst for _, inst in matched_with_scores[:target_qty]]

            # Remove taken instances from remaining pool
            for inst in matched_instances:
                remaining_pool.remove(inst)
                # Update metadata from BOM while strictly preserving spatial coordinates & placement
                inst.component_item_no = comp.item_no
                inst.category = comp_cat_str
                inst.manufacturer = comp.manufacturer
                inst.part_number = comp.part_number
                inst.width = comp.width_mm
                inst.height = comp.height_mm
                inst.depth = comp.depth_mm
                inst.mounting_type = comp.mounting_type
                inst.clearance_top = comp.clearance_top_mm
                inst.clearance_bottom = comp.clearance_bottom_mm
                inst.clearance_sides = comp.clearance_sides_mm
                inst.is_external = comp.is_external
                inst.color = color
                inst.surface = getattr(comp, "surface", "Z")
                inst.voltage = getattr(comp, "voltage", "")
                inst.rated_current_a = getattr(comp, "rated_current_a", 0.0)
                inst.power_kw = getattr(comp, "power_kw", 0.0)
                inst.frequency_hz = getattr(comp, "frequency_hz", 50.0)
                if target_qty == 1:
                    inst.name = comp.name
                reconciled_instances.append(inst)

            # If more instances are needed (quantity increased or new component)
            if len(matched_instances) < target_qty:
                for idx in range(len(matched_instances) + 1, target_qty + 1):
                    new_id = f"inst_{comp.item_no}_{idx}_{int(time.time() * 1000) % 100000}"
                    new_name = f"{comp.name} #{idx}" if target_qty > 1 else comp.name
                    new_inst = PhysicalInstance(
                        id=new_id,
                        component_item_no=comp.item_no,
                        name=new_name,
                        category=comp_cat_str,
                        manufacturer=comp.manufacturer,
                        part_number=comp.part_number,
                        width=comp.width_mm,
                        height=comp.height_mm,
                        depth=comp.depth_mm,
                        mounting_type=comp.mounting_type,
                        clearance_top=comp.clearance_top_mm,
                        clearance_bottom=comp.clearance_bottom_mm,
                        clearance_sides=comp.clearance_sides_mm,
                        is_external=comp.is_external,
                        color=color,
                        is_placed=False,
                        x=0.0,
                        y=0.0,
                        surface=getattr(comp, "surface", "Z"),
                        voltage=getattr(comp, "voltage", ""),
                        rated_current_a=getattr(comp, "rated_current_a", 0.0),
                        power_kw=getattr(comp, "power_kw", 0.0),
                        frequency_hz=getattr(comp, "frequency_hz", 50.0)
                    )
                    reconciled_instances.append(new_inst)

        # remaining_pool contains instances whose components are no longer in BOM.
        # They are dropped from reconciled_instances, thus erased from the layout.
        self.physical_instances = reconciled_instances

    @classmethod
    def load_from_file(cls, file_path: str) -> "ProjectData":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

