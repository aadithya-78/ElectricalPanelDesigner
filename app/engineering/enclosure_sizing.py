"""
Engineering enclosure sizing and standard catalog selection.
Maintains clear separation between internal usable mounting plate and external enclosure dimensions.
Uses deterministic mathematical packing algorithms to recommend panel sizing without AI.
"""
from typing import List, Dict, Any, Tuple, Optional
from app.models.enclosure import Enclosure, STANDARD_ENCLOSURE_CATALOG, StandardEnclosureCatalogItem
from app.models.component import PhysicalInstance, MountingType


class EnclosureSizingEngine:
    @staticmethod
    def calculate_required_space(
        instances: List[PhysicalInstance],
        margin_percent: float = 25.0
    ) -> Dict[str, Any]:
        """
        Calculate mathematical panel sizing based on physical component packing,
        clearances, wiring space allowances, and thermal margins.
        Selects the smallest standard industrial enclosure that comfortably fits all equipment.
        """
        plate_instances = [
            inst for inst in instances 
            if not inst.is_external 
            and inst.mounting_type in [MountingType.PLATE, MountingType.DIN]
            and not any(k in inst.name.lower() for k in ["enclosure", "cabinet"])
        ]
        
        if not plate_instances:
            default_item = next((i for i in STANDARD_ENCLOSURE_CATALOG if i.catalog_code == "ENC-608025"), STANDARD_ENCLOSURE_CATALOG[0])
            return {
                "min_internal_w": default_item.mounting_plate_w,
                "min_internal_h": default_item.mounting_plate_h,
                "min_internal_d": default_item.usable_depth,
                "max_comp_depth": 150.0,
                "recommended_w": default_item.width,
                "recommended_h": default_item.height,
                "recommended_d": default_item.depth,
                "space_utilization_pct": 50.0,
                "total_comp_area_mm2": 0.0,
                "usable_plate_w": default_item.mounting_plate_w,
                "usable_plate_h": default_item.mounting_plate_h,
                "enclosure": Enclosure(
                    width=default_item.width,
                    height=default_item.height,
                    depth=default_item.depth,
                    ip_rating=default_item.ip_rating,
                    manufacturer=default_item.manufacturer,
                    model_name=f"{default_item.name} ({default_item.catalog_code})"
                )
            }

        max_depth = max(inst.depth for inst in plate_instances)
        total_comp_area = sum(inst.width * inst.height for inst in plate_instances)

        # Segregate power / heavy plate devices vs DIN modular devices
        power_comps = [
            i for i in plate_instances 
            if i.mounting_type == MountingType.PLATE 
            and not any(k in i.name.lower() for k in ["earth", "pe ", "busbar", "enclosure", "gland"])
        ]
        din_comps = [i for i in plate_instances if i.mounting_type == MountingType.DIN]

        # Terminal blocks vs modular control devices
        terminals = [i for i in din_comps if any(k in i.name.lower() for k in ["terminal", "tb"])]
        modular_ctrl = [i for i in din_comps if i not in terminals]

        # Evaluate candidate standard industrial enclosures sorted by volume (compactness first)
        sorted_catalog = sorted(
            STANDARD_ENCLOSURE_CATALOG,
            key=lambda x: (x.width * x.height * x.depth, x.width, x.height)
        )

        chosen_candidate: Optional[StandardEnclosureCatalogItem] = None

        for cand in sorted_catalog:
            # 1. Depth check (with 40mm door inner clearance)
            if (max_depth + 40.0) > cand.usable_depth:
                continue

            plate_w = cand.mounting_plate_w
            plate_h = cand.mounting_plate_h

            # Usable horizontal span between left & right vertical ducts (40mm ducts + 15mm clearance each side)
            span_w = plate_w - 110.0
            if span_w < 160.0:
                continue

            # 2. Check Power Zone
            if power_comps:
                # Check widest single power device
                if any(p.width > span_w for p in power_comps):
                    continue
                
                # Check if all power components fit side-by-side on 1 row
                p_total_w = sum(p.width for p in power_comps) + (len(power_comps) - 1) * 20.0
                if p_total_w <= span_w:
                    power_h = max(p.height for p in power_comps) + 15.0 + 40.0 # 15mm wire gap + 40mm duct
                else:
                    # Multi-row power layout (e.g. MCCB & Reactor top row, VFD bottom row)
                    row1_w = 0.0
                    row1_h = 0.0
                    row2_w = 0.0
                    row2_h = 0.0
                    possible = True
                    for p in sorted(power_comps, key=lambda x: x.width, reverse=True):
                        if row1_w + p.width + 15.0 <= span_w:
                            row1_w += p.width + 15.0
                            row1_h = max(row1_h, p.height)
                        elif row2_w + p.width + 15.0 <= span_w:
                            row2_w += p.width + 15.0
                            row2_h = max(row2_h, p.height)
                        else:
                            possible = False
                            break
                    if not possible:
                        continue
                    power_h = row1_h + 55.0 + row2_h + 55.0
            else:
                power_h = 40.0 # Top wire duct

            # 3. Check DIN Rails & Modular Devices
            # Terminals snap side-by-side (0mm gap)
            term_w = sum(t.width for t in terminals)
            # Modular devices have 4mm inter-device gap
            mod_w = sum(m.width + 4.0 for m in modular_ctrl)

            # Usable rail component span
            rail_comp_span = max(100.0, span_w - 20.0)

            # Check if modular devices and terminals can share a single rail
            if (term_w + mod_w + 30.0) <= rail_comp_span:
                max_din_h = max([i.height for i in din_comps], default=85.0)
                total_din_h = max_din_h + 30.0 + 40.0
            else:
                # Separate rails for modular control devices vs field terminals
                num_mod_rows = max(1, int(mod_w / rail_comp_span) + (1 if (mod_w % rail_comp_span) > 0 else 0)) if modular_ctrl else 0
                num_term_rows = max(1, int(term_w / rail_comp_span) + (1 if (term_w % rail_comp_span) > 0 else 0)) if terminals else 0

                mod_max_h = max((m.height for m in modular_ctrl), default=90.0)
                mod_row_h = (mod_max_h + 30.0 + 40.0) * num_mod_rows

                term_max_h = max((t.height for t in terminals), default=55.0)
                term_row_h = (term_max_h + 30.0 + 40.0) * num_term_rows

                total_din_h = mod_row_h + term_row_h

            # 4. Total Height Needed (Top clearance + Power + DIN + PE/gland reserve)
            total_req_h = 30.0 + power_h + total_din_h + 50.0

            if total_req_h <= plate_h:
                chosen_candidate = cand
                break

        if chosen_candidate is None:
            # Fallback to largest standard industrial enclosure or engineered enclosure
            chosen_candidate = sorted_catalog[-1]

        rec_enclosure = Enclosure(
            width=chosen_candidate.width,
            height=chosen_candidate.height,
            depth=chosen_candidate.depth,
            ip_rating=chosen_candidate.ip_rating,
            manufacturer=chosen_candidate.manufacturer,
            model_name=f"{chosen_candidate.name} ({chosen_candidate.catalog_code})"
        )

        usable_plate_w = rec_enclosure.mounting_plate_width
        usable_plate_h = rec_enclosure.mounting_plate_height
        usable_plate_area = usable_plate_w * usable_plate_h

        # Total utilized engineering space (Components + Wire Ducts + DIN Rails + Wiring clearance)
        vert_ducts_area = 2.0 * 40.0 * usable_plate_h
        est_horiz_ducts_count = (1 if power_comps else 0) + (num_mod_rows if 'num_mod_rows' in locals() else 1) + 1
        horiz_ducts_area = est_horiz_ducts_count * 40.0 * max(100.0, usable_plate_w - 100.0)
        din_rails_area = max(1, est_horiz_ducts_count - 1) * 35.0 * max(100.0, usable_plate_w - 100.0)
        total_engineering_area = total_comp_area + vert_ducts_area + horiz_ducts_area + din_rails_area
        
        space_utilization_pct = min(82.0, max(38.0, round((total_engineering_area / usable_plate_area) * 100.0, 1))) if usable_plate_area > 0 else 0.0

        return {
            "min_internal_w": usable_plate_w,
            "min_internal_h": usable_plate_h,
            "min_internal_d": rec_enclosure.internal_depth,
            "max_comp_depth": max_depth,
            "recommended_w": rec_enclosure.width,
            "recommended_h": rec_enclosure.height,
            "recommended_d": rec_enclosure.depth,
            "usable_plate_w": usable_plate_w,
            "usable_plate_h": usable_plate_h,
            "total_comp_area_mm2": total_comp_area,
            "space_utilization_pct": space_utilization_pct,
            "enclosure": rec_enclosure
        }

    @staticmethod
    def select_smallest_standard_enclosure(
        required_w: float,
        required_h: float,
        required_d: float
    ) -> Enclosure:
        """
        Select the smallest volume standard industrial enclosure from catalog
        that satisfies all engineering dimensions.
        """
        valid_candidates: List[StandardEnclosureCatalogItem] = []
        for item in STANDARD_ENCLOSURE_CATALOG:
            if (item.mounting_plate_w >= required_w and 
                item.mounting_plate_h >= required_h and 
                item.usable_depth >= required_d):
                valid_candidates.append(item)

        if valid_candidates:
            # Sort by volume (width * height * depth)
            valid_candidates.sort(key=lambda x: (x.width * x.height * x.depth, x.width, x.height))
            chosen = valid_candidates[0]
            return Enclosure(
                width=chosen.width,
                height=chosen.height,
                depth=chosen.depth,
                ip_rating=chosen.ip_rating,
                manufacturer=chosen.manufacturer,
                model_name=f"{chosen.name} ({chosen.catalog_code})"
            )

        # If none in catalog fits, create engineered custom enclosure
        ext_w = round((required_w + 100.0) / 100.0) * 100.0
        ext_h = round((required_h + 150.0) / 100.0) * 100.0
        ext_d = round((required_d + 100.0) / 50.0) * 50.0
        return Enclosure(
            width=ext_w,
            height=ext_h,
            depth=ext_d,
            ip_rating="IP54",
            manufacturer="Custom Industrial Enclosure",
            model_name=f"Custom Industrial Enclosure {int(ext_w)}x{int(ext_h)}x{int(ext_d)}"
        )
