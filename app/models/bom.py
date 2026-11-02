"""
BOM (Bill of Materials) data structure and operations.
"""
from typing import List, Dict, Any, Optional
from app.models.component import Component, PhysicalInstance, MountingType, ComponentCategory, get_component_color


class BOM:
    def __init__(self, items: Optional[List[Component]] = None):
        self.items: List[Component] = items if items is not None else []

    def add_item(self, item: Component) -> None:
        self.items.append(item)

    def remove_item(self, item_no: int) -> bool:
        initial_len = len(self.items)
        self.items = [item for item in self.items if item.item_no != item_no]
        # Re-number remaining items
        for idx, item in enumerate(self.items, 1):
            item.item_no = idx
        return len(self.items) < initial_len

    def get_item(self, item_no: int) -> Optional[Component]:
        for item in self.items:
            if item.item_no == item_no:
                return item
        return None

    def duplicate_item(self, item_no: int) -> Optional[Component]:
        original = self.get_item(item_no)
        if not original:
            return None
        new_data = original.to_dict()
        new_data["item_no"] = len(self.items) + 1
        new_data["name"] = f"{original.name} (Copy)"
        new_comp = Component.from_dict(new_data)
        self.items.append(new_comp)
        return new_comp

    def expand_to_instances(self) -> List[PhysicalInstance]:
        """
        Expands BOM quantities into individual physical instances.
        For example: Terminal Block Qty 12 -> 12 individual PhysicalInstances.
        Wiring or purely accessory items (like ferrules or cable ties) that have no
        distinct physical bounding box can be excluded from 3D layout or marked external.
        """
        instances: List[PhysicalInstance] = []
        for comp in self.items:
            if comp.is_external or comp.mounting_type == MountingType.EXTERNAL:
                continue
            
            # Non-physical consumables (wires, ferrules, markers) with zero/tiny dims can be skipped
            is_consumable = (
                comp.category == ComponentCategory.WIRING or 
                any(w in comp.name.lower() for w in ["wire", "cable", "ferrule", "lug", "tie", "marker"])
            ) and (comp.width_mm <= 0 or comp.height_mm <= 0 or comp.depth_mm <= 0)

            if is_consumable:
                continue

            qty = max(1, comp.quantity)
            color = get_component_color(comp.name, comp.category.value if hasattr(comp.category, 'value') else str(comp.category))

            for i in range(1, qty + 1):
                inst_id = f"inst_{comp.item_no}_{i}"
                inst_name = f"{comp.name} #{i}" if qty > 1 else comp.name

                inst = PhysicalInstance(
                    id=inst_id,
                    component_item_no=comp.item_no,
                    name=inst_name,
                    category=comp.category.value if hasattr(comp.category, 'value') else str(comp.category),
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
                    surface=getattr(comp, "surface", "Z"),
                    voltage=getattr(comp, "voltage", ""),
                    rated_current_a=getattr(comp, "rated_current_a", 0.0),
                    power_kw=getattr(comp, "power_kw", 0.0),
                    frequency_hz=getattr(comp, "frequency_hz", 50.0)
                )
                instances.append(inst)

        return instances

    def total_cost(self) -> float:
        return round(sum(item.calculate_total_price() for item in self.items), 2)

    def total_heat_loss(self) -> float:
        return round(sum(item.heat_loss_watts * item.quantity for item in self.items), 1)

    def to_list(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_list(cls, data: List[Dict[str, Any]]) -> "BOM":
        items = [Component.from_dict(d) for d in data]
        return cls(items)

