"""
Engineering validator for electrical panels, components, and layout constraints.
"""
from typing import List, Dict, Any
from app.models.bom import BOM
from app.models.component import Component, ValidationStatus, MountingType


class ComponentValidator:
    @staticmethod
    def validate_bom(
        bom: BOM,
        motor_kw: float = 18.5,
        supply_voltage: int = 415,
        ip_rating: str = "IP54"
    ) -> List[Dict[str, Any]]:
        """
        Validate electrical integrity and physical constraints of BOM.
        Returns list of warnings or recommendations.
        """
        issues: List[Dict[str, Any]] = []

        vfd_found = False
        mccb_found = False
        vfd_power_match = False
        unverified_count = 0

        for item in bom.items:
            name_lower = item.name.lower()
            
            # Check verification status
            if not item.part_number_verified or item.validation == ValidationStatus.UNVERIFIED:
                unverified_count += 1

            # Check VFD
            if "drive" in name_lower or "vfd" in name_lower or "atv" in name_lower:
                vfd_found = True
                if item.clearance_top_mm < 100.0 or item.clearance_bottom_mm < 100.0:
                    issues.append({
                        "severity": "WARNING",
                        "component": item.name,
                        "message": f"VFD {item.name} top/bottom clearance is {item.clearance_top_mm}/{item.clearance_bottom_mm} mm. Recommended minimum is 100 mm for airflow."
                    })

            # Check MCCB
            if "mccb" in name_lower or "breaker" in name_lower:
                mccb_found = True

        if not vfd_found:
            issues.append({
                "severity": "CRITICAL",
                "component": "Drive",
                "message": "No Variable Frequency Drive found in the BOM for a motor drive panel!"
            })

        if not mccb_found:
            issues.append({
                "severity": "CRITICAL",
                "component": "Main Breaker",
                "message": "No Main incoming MCCB / isolator found. Circuit protection is mandatory."
            })

        if unverified_count > 0:
            issues.append({
                "severity": "INFO",
                "component": "Part Numbers",
                "message": f"{unverified_count} components have unverified manufacturer part numbers. Validate against vendor catalog before ordering."
            })

        return issues

