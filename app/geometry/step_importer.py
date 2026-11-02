"""
STEP / STP CAD file importer and bounding box extractor.
Checks for CadQuery / pythonOCC and provides clean feedback.
"""
import os
from typing import Dict, Any, Optional


class STEPImporter:
    @staticmethod
    def is_cad_backend_available() -> bool:
        """Check if CadQuery or pythonOCC is installed."""
        try:
            import cadquery
            return True
        except ImportError:
            pass

        try:
            import OCC
            return True
        except ImportError:
            pass

        return False

    @classmethod
    def import_step_dimensions(cls, file_path: str) -> Dict[str, Any]:
        """
        Extract X, Y, Z bounding box dimensions from a STEP/STP file.
        Returns dict with width_mm, height_mm, depth_mm, or error message.
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        if not cls.is_cad_backend_available():
            return {
                "success": False,
                "error": (
                    "CAD Kernel (CadQuery or pythonOCC) is not installed in current Python environment.\n"
                    "To enable automatic STEP bounding box calculation, install cadquery:\n"
                    "    pip install cadquery\n"
                    "You can still enter component X, Y, Z dimensions manually or load them from the database."
                )
            }

        try:
            import cadquery as cq
            shape = cq.importers.importStep(file_path)
            bb = shape.val().BoundingBox()
            
            x_len = round(bb.xlen, 1)
            y_len = round(bb.ylen, 1)
            z_len = round(bb.zlen, 1)

            return {
                "success": True,
                "width_mm": x_len,
                "height_mm": y_len,
                "depth_mm": z_len,
                "message": f"Successfully calculated bounding box: {x_len} x {y_len} x {z_len} mm"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parsing STEP file: {str(e)}"
            }

