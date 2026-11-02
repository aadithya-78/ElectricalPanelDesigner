"""
Excel BOM Exporter using openpyxl.
Produces professionally formatted engineering Bill of Materials with project summary.
"""
from typing import Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.models.project import ProjectData


class ExcelBOMExporter:
    @classmethod
    def export_to_excel(cls, project: ProjectData, file_path: str) -> bool:
        """Export complete project BOM and engineering specs to Excel."""
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Engineering BOM"

            # Styles
            header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
            header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            
            sub_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
            sub_font = Font(name="Segoe UI", size=10, bold=True, color="1F497D")

            title_font = Font(name="Segoe UI", size=16, bold=True, color="1F497D")
            bold_font = Font(name="Segoe UI", size=10, bold=True)
            normal_font = Font(name="Segoe UI", size=10)
            warning_font = Font(name="Segoe UI", size=9, italic=True, color="C00000")

            thin_border = Border(
                left=Side(style='thin', color='D9D9D9'),
                right=Side(style='thin', color='D9D9D9'),
                top=Side(style='thin', color='D9D9D9'),
                bottom=Side(style='thin', color='D9D9D9')
            )

            # 1. Project Header Banner
            ws.merge_cells("A1:N1")
            ws["A1"] = "ELECTRICAL PANEL DESIGNER — ENGINEERING BILL OF MATERIALS"
            ws["A1"].font = title_font
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 30

            ws["A3"] = "Project Name:"
            ws["A3"].font = bold_font
            ws["B3"] = project.project_name
            ws["B3"].font = normal_font

            ws["D3"] = "Requirement:"
            ws["D3"].font = bold_font
            ws["E3"] = project.raw_requirement
            ws["E3"].font = normal_font

            ws["A4"] = "Enclosure Size:"
            ws["A4"].font = bold_font
            enc = project.enclosure
            ws["B4"] = f"{int(enc.width)} x {int(enc.height)} x {int(enc.depth)} mm ({enc.ip_rating})"
            ws["B4"].font = normal_font

            ws["D4"] = "Total Heat Loss:"
            ws["D4"].font = bold_font
            ws["E4"] = f"{project.bom.total_heat_loss():.1f} Watts"
            ws["E4"].font = normal_font

            ws["G4"] = "Estimated BOM Cost:"
            ws["G4"].font = bold_font
            tot_usd = project.bom.total_cost()
            tot_inr = tot_usd * 83.0
            ws["H4"] = f"${tot_usd:,.2f} / ₹{tot_inr:,.0f}"
            ws["H4"].font = bold_font

            # 2. Table Column Headers
            headers = [
                "Item No.", "Category", "Component Name", "Manufacturer", 
                "Part Number", "Description", "Qty", "Width X (mm)", 
                "Height Y (mm)", "Depth Z (mm)", "Mounting", "Clearance (mm)", 
                "Heat Loss (W)", "Unit Price ($ / ₹)", "Total Price ($ / ₹)", "Validation"
            ]

            start_row = 6
            for col_idx, h in enumerate(headers, 1):
                cell = ws.cell(row=start_row, column=col_idx, value=h)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border
            ws.row_dimensions[start_row].height = 25

            # 3. Data Rows
            current_row = start_row + 1
            for item in project.bom.items:
                clearance_str = f"T:{int(item.clearance_top_mm)} B:{int(item.clearance_bottom_mm)} S:{int(item.clearance_sides_mm)}"
                part_no_display = item.part_number if item.part_number else "PART NUMBER NOT VERIFIED"
                val_status = "Verified" if item.part_number_verified else "Unverified"
                unit_price_display = f"${item.unit_price:,.2f} (₹{item.unit_price * 83.0:,.0f})"
                total_price_display = f"${item.total_price:,.2f} (₹{item.total_price * 83.0:,.0f})"

                row_vals = [
                    item.item_no,
                    item.category.value if hasattr(item.category, "value") else str(item.category),
                    item.name,
                    item.manufacturer,
                    part_no_display,
                    item.description,
                    item.quantity,
                    item.width_mm,
                    item.height_mm,
                    item.depth_mm,
                    item.mounting_type.value if hasattr(item.mounting_type, "value") else str(item.mounting_type),
                    clearance_str,
                    item.heat_loss_watts,
                    unit_price_display,
                    total_price_display,
                    val_status
                ]

                for col_idx, val in enumerate(row_vals, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=val)
                    cell.font = normal_font
                    cell.border = thin_border
                    
                    if col_idx in [1, 7]:
                        cell.alignment = Alignment(horizontal="center")
                    elif col_idx in [8, 9, 10, 13, 14, 15]:
                        cell.alignment = Alignment(horizontal="right")
                    else:
                        cell.alignment = Alignment(horizontal="left")

                    if col_idx == 5 and "NOT VERIFIED" in str(val):
                        cell.font = warning_font

                current_row += 1

            # Total row
            ws.cell(row=current_row, column=3, value="TOTAL ESTIMATED COST:").font = bold_font
            tot_cell = ws.cell(row=current_row, column=15, value=f"${tot_usd:,.2f} (₹{tot_inr:,.0f})")
            tot_cell.font = bold_font
            tot_cell.fill = sub_fill

            # Auto-adjust column widths
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(12, min(max_len + 3, 40))

            wb.save(file_path)
            return True
        except Exception as e:
            print(f"Error saving Excel: {e}")
            return False

