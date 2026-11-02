"""
3D STEP CAD Exporter for Industrial Electrical Enclosures and Placed Components.
Supports both native pure-Python ISO 10303-21 AP214 standard generation (zero dependencies)
and CadQuery assembly generation when CadQuery is installed.
Files can be opened in SolidWorks, Autodesk Inventor, Fusion 360, PTC Creo, Siemens NX, and FreeCAD.
"""
import os
import time
from typing import List, Dict, Any, Optional
from app.models.component import PhysicalInstance
from app.models.enclosure import Enclosure, DINRail, WiringDuct


class STEPExporter:
    @staticmethod
    def is_cad_backend_available() -> bool:
        """Check if external cadquery library is present."""
        try:
            import cadquery
            return True
        except ImportError:
            return False

    @classmethod
    def export_step(
        cls,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Flexible entry point supporting multiple call signatures:
        export_step(enclosure, instances, din_rails, wiring_ducts, file_path)
        export_step(file_path, enclosure, instances, din_rails, wiring_ducts)
        """
        file_path = None
        enclosure = None
        instances = []
        din_rails = []
        wiring_ducts = []

        # Parse args flexibly
        if len(args) == 5:
            if isinstance(args[0], str):
                file_path, enclosure, instances, din_rails, wiring_ducts = args
            else:
                enclosure, instances, din_rails, wiring_ducts, file_path = args
        elif len(args) == 2:
            # (project, file_path)
            project, file_path = args
            enclosure = project.enclosure
            instances = project.physical_instances
            din_rails = project.din_rails
            wiring_ducts = project.wiring_ducts
        else:
            file_path = kwargs.get("file_path")
            enclosure = kwargs.get("enclosure")
            instances = kwargs.get("instances", [])
            din_rails = kwargs.get("din_rails", [])
            wiring_ducts = kwargs.get("wiring_ducts", [])

        return cls.export_assembly(
            file_path=file_path,
            enclosure=enclosure,
            instances=instances,
            din_rails=din_rails,
            wiring_ducts=wiring_ducts
        )

    @classmethod
    def export_assembly(
        cls,
        file_path: str,
        enclosure: Enclosure,
        instances: List[PhysicalInstance],
        din_rails: List[DINRail],
        wiring_ducts: List[WiringDuct]
    ) -> Dict[str, Any]:
        """Export placed layout as 3D STEP assembly."""
        if not file_path:
            return {"success": False, "error": "No file path provided for STEP export."}

        # If cadquery is available, use it for parametric solids
        if cls.is_cad_backend_available():
            try:
                import cadquery as cq

                assembly = cq.Assembly(name="Electrical_Panel")

                # Mounting Plate
                plate = cq.Workplane("XY").box(
                    enclosure.mounting_plate_width,
                    enclosure.mounting_plate_height,
                    2.5
                )
                assembly.add(plate, name="Mounting_Plate", color=cq.Color(0.8, 0.8, 0.8, 0.5))

                # Components
                for inst in instances:
                    if not inst.is_placed or inst.is_external:
                        continue
                    c_box = cq.Workplane("XY").box(inst.width, inst.height, inst.depth)
                    loc = cq.Location(
                        cq.Vector(
                            inst.x + inst.width / 2.0 - enclosure.mounting_plate_width / 2.0,
                            inst.y + inst.height / 2.0 - enclosure.mounting_plate_height / 2.0,
                            inst.z + inst.depth / 2.0
                        )
                    )
                    clean_name = inst.id.replace(" ", "_").replace("#", "_")
                    assembly.add(c_box, loc=loc, name=clean_name)

                assembly.save(file_path)
                return {
                    "success": True,
                    "message": f"Successfully exported 3D STEP model to {file_path}"
                }
            except Exception as e:
                print(f"CadQuery export failed ({e}), falling back to native ISO 10303-21 exporter.")

        # Native pure-Python ISO 10303-21 AP214 STEP exporter (zero dependency)
        try:
            step_content = cls._generate_iso_step_string(
                enclosure, instances, din_rails, wiring_ducts
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(step_content)
            return {
                "success": True,
                "message": f"Successfully exported native ISO 10303-21 3D STEP model to {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate STEP model: {str(e)}"
            }

    @classmethod
    def _generate_iso_step_string(
        cls,
        enclosure: Enclosure,
        instances: List[PhysicalInstance],
        din_rails: List[DINRail],
        wiring_ducts: List[WiringDuct]
    ) -> str:
        """Construct a complete, standard ISO 10303-21 AP214 STEP file with 3D solid cuboids."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        lines = [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('STEP AP214 3D Industrial Electrical Panel Assembly'),'2;1');",
            f"FILE_NAME('panel_assembly.step','{timestamp}',('Antigravity'),('Industrial Panel Placement Engine'),'','','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
            "ENDSEC;",
            "DATA;",
            "#1=APPLICATION_CONTEXT('automotive design');",
            "#2=APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#1);",
            "#3=PRODUCT_CONTEXT('',#1,'mechanical');",
            "#4=PRODUCT('Electrical_Panel_Assembly','Electrical_Panel_Assembly','',(#3));",
            "#5=PRODUCT_DEFINITION_FORMATION('','',#4);",
            "#6=PRODUCT_DEFINITION('design','',#5,#3);",
            "#7=PRODUCT_DEFINITION_SHAPE('','',#6);"
        ]

        curr = 10
        entity_lines = []
        brep_ids = []

        # Global Coordinate System
        dir_z = curr
        entity_lines.append(f"#{curr}=DIRECTION('',(0.,0.,1.));")
        curr += 1
        dir_x = curr
        entity_lines.append(f"#{curr}=DIRECTION('',(1.,0.,0.));")
        curr += 1
        dir_y = curr
        entity_lines.append(f"#{curr}=DIRECTION('',(0.,1.,0.));")
        curr += 1
        origin = curr
        entity_lines.append(f"#{curr}=CARTESIAN_POINT('',(0.,0.,0.));")
        curr += 1
        axis_base = curr
        entity_lines.append(f"#{curr}=AXIS2_PLACEMENT_3D('',#{origin},#{dir_z},#{dir_x});")
        curr += 1

        # Unit vectors for faces
        face_normals = [
            (0.0, 0.0, -1.0, 1.0, 0.0, 0.0), # Bottom
            (0.0, 0.0, 1.0, 1.0, 0.0, 0.0),  # Top
            (0.0, -1.0, 0.0, 1.0, 0.0, 0.0), # Front
            (0.0, 1.0, 0.0, -1.0, 0.0, 0.0), # Back
            (-1.0, 0.0, 0.0, 0.0, 1.0, 0.0), # Left
            (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)   # Right
        ]
        norm_ids = []
        for nx, ny, nz, rx, ry, rz in face_normals:
            n_dir = curr
            entity_lines.append(f"#{curr}=DIRECTION('',({nx:.1f},{ny:.1f},{nz:.1f}));")
            curr += 1
            r_dir = curr
            entity_lines.append(f"#{curr}=DIRECTION('',({rx:.1f},{ry:.1f},{rz:.1f}));")
            curr += 1
            norm_ids.append((n_dir, r_dir))

        # Collect all 3D solid cuboids: (name, x, y, z, dx, dy, dz)
        boxes = []

        # 1. Mounting Plate (Z = 0)
        plate_w = enclosure.mounting_plate_width
        plate_h = enclosure.mounting_plate_height
        boxes.append(("Mounting_Plate", 0.0, 0.0, 0.0, plate_w, plate_h, 2.5))

        # 2. DIN Rails (Z = 2.5 mm, depth = 7.5 or 15 mm)
        for r_idx, rail in enumerate(din_rails, 1):
            r_name = f"DIN_Rail_{r_idx}"
            rw = getattr(rail, "effective_width", getattr(rail, "length", 600.0))
            rh = getattr(rail, "effective_height", getattr(rail, "height", 35.0))
            rd = getattr(rail, "depth", 7.5)
            # Map screen Y (top-down) to 3D Cartesian Y (bottom-up)
            ry = plate_h - rail.y - rh
            boxes.append((r_name, rail.x, ry, 2.5, rw, rh, rd))

        # 3. Wiring Ducts (Z = 2.5 mm, depth = 40 mm)
        for d_idx, duct in enumerate(wiring_ducts, 1):
            d_name = f"Wire_Duct_{d_idx}"
            dw = getattr(duct, "effective_width", getattr(duct, "length", 600.0))
            dh = getattr(duct, "effective_height", getattr(duct, "width", 40.0))
            dd = getattr(duct, "height", 40.0) if getattr(duct, "height", 40.0) > 0 else 40.0
            # Map screen Y (top-down) to 3D Cartesian Y (bottom-up)
            dy = plate_h - duct.y - dh
            boxes.append((d_name, duct.x, dy, 2.5, dw, dh, dd))

        # 4. Placed Physical Components
        for inst in instances:
            if not inst.is_placed or inst.is_external:
                continue
            clean_name = (inst.part_number or inst.name or "Component").replace(" ", "_").replace("-", "_").replace(".", "_")
            surf = getattr(inst, "surface", "Z").upper()
            if surf == "Z":
                cy = plate_h - inst.y - inst.height
                z_pos = 10.0
            else:
                cy = enclosure.height - inst.y - inst.height
                z_pos = enclosure.depth - inst.depth
            boxes.append((clean_name, inst.x, cy, z_pos, inst.width, inst.height, inst.depth))

        # Build B-Rep solids for each box
        for name, bx, by, bz, bdx, bdy, bdz in boxes:
            pts = [
                (bx, by, bz),
                (bx + bdx, by, bz),
                (bx + bdx, by + bdy, bz),
                (bx, by + bdy, bz),
                (bx, by, bz + bdz),
                (bx + bdx, by, bz + bdz),
                (bx + bdx, by + bdy, bz + bdz),
                (bx, by + bdy, bz + bdz)
            ]
            pt_ids = []
            for px, py, pz in pts:
                entity_lines.append(f"#{curr}=CARTESIAN_POINT('',({px:.2f},{py:.2f},{pz:.2f}));")
                pt_ids.append(curr)
                curr += 1

            faces = [
                (0, 3, 2, 1), # Bottom
                (4, 5, 6, 7), # Top
                (0, 1, 5, 4), # Front
                (2, 3, 7, 6), # Back
                (0, 4, 7, 3), # Left
                (1, 2, 6, 5)  # Right
            ]
            face_ids = []
            for f_idx, f in enumerate(faces):
                p_loop = curr
                p_refs = ",".join(f"#{pt_ids[idx]}" for idx in f)
                entity_lines.append(f"#{p_loop}=POLY_LOOP('',({p_refs}));")
                curr += 1

                f_bound = curr
                entity_lines.append(f"#{f_bound}=FACE_OUTER_BOUND('',#{p_loop},.T.);")
                curr += 1

                n_dir, r_dir = norm_ids[f_idx]
                pln_axis = curr
                entity_lines.append(f"#{curr}=AXIS2_PLACEMENT_3D('',#{pt_ids[f[0]]},#{n_dir},#{r_dir});")
                curr += 1

                pln = curr
                entity_lines.append(f"#{curr}=PLANE('',#{pln_axis});")
                curr += 1

                f_surf = curr
                entity_lines.append(f"#{f_surf}=ADVANCED_FACE('',(#{f_bound}),#{pln},.T.);")
                curr += 1
                face_ids.append(f_surf)

            shell_id = curr
            f_refs = ",".join(f"#{fid}" for fid in face_ids)
            entity_lines.append(f"#{shell_id}=CLOSED_SHELL('',({f_refs}));")
            curr += 1

            brep_id = curr
            entity_lines.append(f"#{brep_id}=MANIFOLD_SOLID_BREP('{name}',#{shell_id});")
            curr += 1
            brep_ids.append(brep_id)

        # Connect all solids to Shape Representation
        shape_rep_id = curr
        brep_refs = ",".join(f"#{bid}" for bid in brep_ids) + f",#{axis_base}"
        entity_lines.append(f"#{shape_rep_id}=SHAPE_REPRESENTATION('Electrical_Panel_Assembly',({brep_refs}),#{curr+1});")
        curr += 1

        # Representation Context with standard Engineering Millimeters
        ctx_id = curr
        entity_lines.append(
            f"#{curr}=(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{curr+1})) "
            f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{curr+2},#{curr+3},#{curr+4})) REPRESENTATION_CONTEXT('3D','TOPOLOGY'));"
        )
        curr += 1
        entity_lines.append(f"#{curr}=UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#{curr+1},'closure','');")
        curr += 1
        entity_lines.append(f"#{curr}=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.));")
        curr += 1
        entity_lines.append(f"#{curr}=(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.));")
        curr += 1
        entity_lines.append(f"#{curr}=(NAMED_UNIT(*) SOLID_ANGLE_UNIT() SI_UNIT($,.STERADIAN.));")
        curr += 1

        # Product Shape Definition
        entity_lines.append(f"#{curr}=SHAPE_DEFINITION_REPRESENTATION(#7,#{shape_rep_id});")
        curr += 1

        lines.extend(entity_lines)
        lines.append("ENDSEC;")
        lines.append("END-ISO-10303-21;")

        return "\n".join(lines)
