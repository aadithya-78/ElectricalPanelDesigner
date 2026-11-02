"""
Collision and Clearance Zone Detection Engine for electrical panels.
Provides 2D mounting plate collision checking with DIN-rail mounting exceptions,
strict boundary validation, and rollback support.
"""
from typing import List, Dict, Tuple, Optional
from app.models.component import PhysicalInstance, MountingType
from app.models.enclosure import Enclosure


class CollisionDetector:
    @staticmethod
    def is_din_rail(inst: PhysicalInstance) -> bool:
        """Check if an instance is a DIN rail."""
        name_u = inst.name.upper()
        return "DIN RAIL" in name_u or name_u.startswith("DIN ")

    @staticmethod
    def is_wire_duct(inst: PhysicalInstance) -> bool:
        """Check if an instance is a wire duct / trunking."""
        name_u = inst.name.upper()
        return "DUCT" in name_u or "TRUNKING" in name_u

    @staticmethod
    def check_aabb_intersection(box1: Dict[str, float], box2: Dict[str, float]) -> bool:
        """Return True if two 3D Axis-Aligned Bounding Boxes overlap with positive volume."""
        return (
            box1["min_x"] < box2["max_x"] and box1["max_x"] > box2["min_x"] and
            box1["min_y"] < box2["max_y"] and box1["max_y"] > box2["min_y"] and
            box1["min_z"] < box2["max_z"] and box1["max_z"] > box2["min_z"]
        )

    @staticmethod
    def check_2d_intersection(box1: Dict[str, float], box2: Dict[str, float]) -> bool:
        """Return True if two 2D bounding boxes overlap on the mounting plate surface."""
        eps = 0.5
        return (
            (box1["min_x"] + eps) < box2["max_x"] and (box1["max_x"] - eps) > box2["min_x"] and
            (box1["min_y"] + eps) < box2["max_y"] and (box1["max_y"] - eps) > box2["min_y"]
        )

    @classmethod
    def check_instance_collision(
        cls,
        inst1: PhysicalInstance,
        inst2: PhysicalInstance,
        check_clearance: bool = False
    ) -> bool:
        """
        Check if two physical instances collide on their 2D surface.
        Components on different surfaces (Mounting plate Z vs Outer Door Z+1) NEVER collide.
        Exception: DIN-mounted components are allowed to sit on / overlap DIN rails.
        """
        if inst1.id == inst2.id:
            return False

        # Physical surface check: Z (plate) vs Z+1 (door) are separate planes
        surf1 = getattr(inst1, "surface", "Z") or "Z"
        surf2 = getattr(inst2, "surface", "Z") or "Z"
        if surf1.upper() != surf2.upper():
            return False

        b1 = inst1.clearance_box if check_clearance else inst1.bounding_box
        b2 = inst2.clearance_box if check_clearance else inst2.bounding_box

        if not cls.check_2d_intersection(b1, b2):
            return False

        # If checking clearance zones:
        if check_clearance:
            # Components on the same DIN rail sit adjacent along the rail;
            # terminal blocks and modular devices are designed to mount side-by-side without side clearance penalty
            if inst1.din_rail_id and inst2.din_rail_id and inst1.din_rail_id == inst2.din_rail_id:
                return False

        # If checking strict physical body collision (not clearance zones):
        if not check_clearance:
            is_din1 = cls.is_din_rail(inst1)
            is_din2 = cls.is_din_rail(inst2)

            # Exception: DIN mounted component on DIN rail is physically valid
            if is_din1 and inst2.mounting_type == MountingType.DIN:
                return False
            if is_din2 and inst1.mounting_type == MountingType.DIN:
                return False

        return True

    @classmethod
    def check_all_collisions(
        cls,
        instances: List[PhysicalInstance]
    ) -> List[Tuple[str, str, str]]:
        """
        Check all pairs of placed instances for physical collisions and clearance violations.
        Returns list of (inst1_id, inst2_id, severity_message).
        """
        violations: List[Tuple[str, str, str]] = []
        placed = [i for i in instances if i.is_placed and not i.is_external]

        for i in range(len(placed)):
            for j in range(i + 1, len(placed)):
                inst1 = placed[i]
                inst2 = placed[j]

                # Check direct physical body overlap
                if cls.check_instance_collision(inst1, inst2, check_clearance=False):
                    violations.append((
                        inst1.id,
                        inst2.id,
                        f"PHYSICAL COLLISION: '{inst1.name}' overlaps with '{inst2.name}'"
                    ))
                # Check clearance overlap
                elif cls.check_instance_collision(inst1, inst2, check_clearance=True):
                    violations.append((
                        inst1.id,
                        inst2.id,
                        f"CLEARANCE VIOLATION: '{inst1.name}' encroaches into clearance zone of '{inst2.name}'"
                    ))

        return violations

    @classmethod
    def validate_position(
        cls,
        candidate_inst: PhysicalInstance,
        all_instances: List[PhysicalInstance],
        plate_w: float,
        plate_h: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Strict validation for placement or move:
        1. Boundary check: must be fully inside (0, 0, plate_w, plate_h).
        2. Collision check: must not collide with any other placed instance on the SAME surface.
        Returns (is_valid, error_reason).
        """
        bbox = candidate_inst.bounding_box
        surf_label = "Outer Door (Z+1)" if getattr(candidate_inst, "surface", "Z") == "Z+1" else "Mounting Plate (Z)"

        # 1. Boundary Check
        if bbox["min_x"] < 0 or bbox["max_x"] > plate_w:
            return False, f"Boundary violation: Component extends horizontally outside {surf_label} ({bbox['min_x']:.0f} to {bbox['max_x']:.0f} mm, max {plate_w:.0f} mm)."

        if bbox["min_y"] < 0 or bbox["max_y"] > plate_h:
            return False, f"Boundary violation: Component extends vertically outside {surf_label} ({bbox['min_y']:.0f} to {bbox['max_y']:.0f} mm, max {plate_h:.0f} mm)."

        # 2. Collision Check against items on the same physical surface
        cand_surf = getattr(candidate_inst, "surface", "Z") or "Z"
        for other in all_instances:
            if not other.is_placed or other.is_external or other.id == candidate_inst.id:
                continue
            if any(k in other.name.lower() for k in ["enclosure", "cabinet"]):
                continue

            other_surf = getattr(other, "surface", "Z") or "Z"
            if cand_surf.upper() != other_surf.upper():
                continue

            if cls.check_instance_collision(candidate_inst, other, check_clearance=False):
                return False, f"Collision violation: Component overlaps with '{other.name}' on {surf_label}."

        return True, None

    @staticmethod
    def check_boundary_overflow(
        inst: PhysicalInstance,
        enclosure: Enclosure
    ) -> List[str]:
        """Check if an instance extends outside its usable surface or enclosure envelope."""
        if not inst.is_placed or inst.is_external:
            return []

        bbox = inst.bounding_box
        errors = []
        surf = getattr(inst, "surface", "Z") or "Z"

        if surf == "Z+1" or inst.mounting_type == MountingType.DOOR:
            # Door mounted
            door_w = enclosure.width
            door_h = enclosure.height
            if bbox["min_x"] < 0 or bbox["max_x"] > door_w:
                errors.append(f"Door component '{inst.name}' extends beyond door width ({bbox['max_x']:.1f} > {door_w:.1f} mm)")
            if bbox["min_y"] < 0 or bbox["max_y"] > door_h:
                errors.append(f"Door component '{inst.name}' extends beyond door height ({bbox['max_y']:.1f} > {door_h:.1f} mm)")
        elif inst.mounting_type in [MountingType.PLATE, MountingType.DIN]:
            plate_w = enclosure.mounting_plate_width
            plate_h = enclosure.mounting_plate_height
            usable_d = enclosure.internal_depth

            if bbox["min_x"] < 0 or bbox["max_x"] > plate_w:
                errors.append(f"'{inst.name}' extends beyond mounting plate width ({bbox['max_x']:.1f} > {plate_w:.1f} mm)")
            if bbox["min_y"] < 0 or bbox["max_y"] > plate_h:
                errors.append(f"'{inst.name}' extends beyond mounting plate height ({bbox['max_y']:.1f} > {plate_h:.1f} mm)")
            if bbox["max_z"] > usable_d:
                errors.append(f"'{inst.name}' depth ({bbox['max_z']:.1f} mm) exceeds usable enclosure depth ({usable_d:.1f} mm)")

        return errors
