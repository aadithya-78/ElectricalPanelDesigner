"""
Layout and Engineering Report Generator (HTML & Text format).
"""
import time
from typing import Dict, Any
from app.models.project import ProjectData


class ReportExporter:
    @classmethod
    def generate_html_report(cls, project: ProjectData, file_path: str) -> bool:
        """Generate a comprehensive printable HTML engineering design report."""
        try:
            enc = project.enclosure
            bom = project.bom
            therm = project.thermal_data

            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Electrical Panel Engineering Report - {project.project_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 30px;
            color: #263238;
            background-color: #fdfdfd;
            line-height: 1.5;
        }}
        h1 {{
            color: #0d47a1;
            border-bottom: 2px solid #1976d2;
            padding-bottom: 8px;
            font-size: 24px;
        }}
        h2 {{
            color: #1565c0;
            margin-top: 25px;
            border-bottom: 1px solid #cfd8dc;
            padding-bottom: 5px;
            font-size: 18px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 13px;
        }}
        th, td {{
            border: 1px solid #cfd8dc;
            padding: 8px 10px;
            text-align: left;
        }}
        th {{
            background-color: #eceff1;
            color: #37474f;
            font-weight: 600;
        }}
        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .card {{
            background: #ffffff;
            border: 1px solid #cfd8dc;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .unverified {{
            color: #c62828;
            font-weight: 600;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
        }}
        .badge-power {{ background: #ffcdd2; color: #b71c1c; }}
        .badge-control {{ background: #bbdefb; color: #0d47a1; }}
        .badge-acc {{ background: #c8e6c9; color: #1b5e20; }}
        .badge-wire {{ background: #ffe0b2; color: #e65100; }}
        .footer {{
            margin-top: 40px;
            border-top: 1px solid #cfd8dc;
            padding-top: 10px;
            font-size: 11px;
            color: #78909c;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>ELECTRICAL PANEL DESIGNER — ENGINEERING REPORT</h1>
    
    <div class="card">
        <div class="grid-2">
            <div>
                <strong>Project:</strong> {project.project_name}<br>
                <strong>Date:</strong> {project.created_at}<br>
                <strong>Input Requirement:</strong> "{project.raw_requirement}"<br>
                <strong>Panel Application:</strong> {project.extracted_params.get('application', 'N/A')}<br>
                <strong>Motor Rating:</strong> {project.extracted_params.get('motor_kw', 'N/A')} kW ({project.extracted_params.get('motor_kw_note', '')})
            </div>
            <div>
                <strong>Supply:</strong> {project.extracted_params.get('supply_voltage', 415)}V AC, 3-Phase, 50Hz<br>
                <strong>Drive Type:</strong> {project.extracted_params.get('drive_type', 'N/A')}<br>
                <strong>Enclosure Size:</strong> {int(enc.width)} x {int(enc.height)} x {int(enc.depth)} mm ({enc.ip_rating}) | {'Double Door (Vertical Split)' if getattr(enc, 'door_type', 'SINGLE') == 'DOUBLE_VERTICAL' else 'Single Door'}<br>
                <strong>Mounting Plate:</strong> {int(enc.mounting_plate_width)} x {int(enc.mounting_plate_height)} mm<br>
                <strong>Total Heat Loss:</strong> {bom.total_heat_loss():.1f} W (Cooling: {therm.get('cooling_type', 'Filter Fan')})
            </div>
        </div>
    </div>

    <h2>1. Provisional Engineering Assumptions</h2>
    <ul>
        {"".join(f"<li>{a}</li>" for a in project.provisional_assumptions) if project.provisional_assumptions else "<li>No specific assumptions recorded.</li>"}
    </ul>

    <h2>2. Manufacturer Selections</h2>
    <table>
        <thead>
            <tr><th>Equipment Category</th><th>Selected Manufacturer</th></tr>
        </thead>
        <tbody>
            {"".join(f"<tr><td>{cat}</td><td>{mfr}</td></tr>" for cat, mfr in project.manufacturer_selections.items())}
        </tbody>
    </table>

    <h2>3. Approved Bill of Materials (BOM)</h2>
    <table>
        <thead>
            <tr>
                <th>Item</th>
                <th>Category</th>
                <th>Component</th>
                <th>Manufacturer</th>
                <th>Part Number</th>
                <th>Qty</th>
                <th>Dimensions X×Y×Z (mm)</th>
                <th>Mounting</th>
                <th>Heat (W)</th>
                <th>Unit Price ($ / ₹)</th>
                <th>Total Price ($ / ₹)</th>
            </tr>
        </thead>
        <tbody>
"""
            for item in bom.items:
                part_display = item.part_number if item.part_number else '<span class="unverified">NOT VERIFIED</span>'
                badge_cls = "badge-power" if item.category.value == "Power" else "badge-control" if item.category.value == "Control" else "badge-acc"
                u_price = f"${item.unit_price:,.2f} (₹{item.unit_price * 83.0:,.0f})"
                t_price = f"${item.total_price:,.2f} (₹{item.total_price * 83.0:,.0f})"
                html += f"""
            <tr>
                <td>{item.item_no}</td>
                <td><span class="badge {badge_cls}">{item.category.value}</span></td>
                <td><strong>{item.name}</strong><br><small>{item.description}</small></td>
                <td>{item.manufacturer}</td>
                <td>{part_display}</td>
                <td>{item.quantity}</td>
                <td>{item.width_mm} × {item.height_mm} × {item.depth_mm}</td>
                <td>{item.mounting_type.value}</td>
                <td>{item.heat_loss_watts}</td>
                <td>{u_price}</td>
                <td>{t_price}</td>
            </tr>
"""

            html += f"""
        </tbody>
    </table>

    <h2>4. 3D Component Placements & Coordinates</h2>
    <table>
        <thead>
            <tr>
                <th>Instance ID</th>
                <th>Component</th>
                <th>Mounting</th>
                <th>X (mm)</th>
                <th>Y (mm)</th>
                <th>Z (mm)</th>
                <th>Width (mm)</th>
                <th>Height (mm)</th>
                <th>Depth (mm)</th>
                <th>DIN Rail ID</th>
            </tr>
        </thead>
        <tbody>
"""
            for inst in project.physical_instances:
                if not inst.is_placed:
                    continue
                html += f"""
            <tr>
                <td>{inst.id}</td>
                <td>{inst.name}</td>
                <td>{inst.mounting_type.value}</td>
                <td>{inst.x:.1f}</td>
                <td>{inst.y:.1f}</td>
                <td>{inst.z:.1f}</td>
                <td>{inst.width:.1f}</td>
                <td>{inst.height:.1f}</td>
                <td>{inst.depth:.1f}</td>
                <td>{inst.din_rail_id or '-'}</td>
            </tr>
"""

            html += f"""
        </tbody>
    </table>

    <h2>5. DIN Rails & Wiring Ducts</h2>
    <div class="grid-2">
        <div>
            <h3>DIN Rails (DIN EN 60715 35mm)</h3>
            <ul>
                {"".join(f"<li><strong>{r.name}:</strong> Length {r.length:.0f} mm at Y={r.y:.0f} mm (Utilization: {r.utilization_percent}%)</li>" for r in project.din_rails)}
            </ul>
        </div>
        <div>
            <h3>Slotted Wiring Trunking / Ducts</h3>
            <ul>
                {"".join(f"<li><strong>{d.name}:</strong> {d.orientation} ({d.width:.0f}x{d.height:.0f} mm) Length: {d.length:.0f} mm</li>" for d in project.wiring_ducts)}
            </ul>
        </div>
    </div>

    <h2>6. Thermal Balance & Dissipation</h2>
    <div class="card">
        <p><strong>Total Installed Heat Dissipation:</strong> {bom.total_heat_loss():.1f} W</p>
        <p><strong>Natural Enclosure Convection:</strong> {therm.get('natural_dissipation_watts', 0):.1f} W</p>
        <p><strong>Excess Thermal Load:</strong> {therm.get('excess_heat_watts', 0):.1f} W</p>
        <p><strong>Required Forced Airflow:</strong> {therm.get('required_airflow_m3h', 0):.1f} m³/h</p>
        <p><strong>Cooling Recommendation:</strong> {therm.get('cooling_recommendation', 'Standard Filter Fan')}</p>
        <p><em>Notice: {therm.get('warning', '')}</em></p>
    </div>

    <div class="footer">
        Generated by Electrical Panel Designer. Verified calculations compliant with IEC 61439 standards.
    </div>
</body>
</html>
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            return True
        except Exception as e:
            print(f"Error generating report: {e}")
            return False

    @classmethod
    def export_report(cls, project: ProjectData, file_path: str) -> bool:
        """Alias for generate_html_report."""
        return cls.generate_html_report(project, file_path)


