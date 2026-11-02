# Electrical Panel Designer (EPD)

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20(Qt%20for%20Python)-green.svg)](https://pypi.org/project/PySide6/)
[![3D Engine](https://img.shields.io/badge/3D%20Engine-PyVista%20%7C%20VTK-orange.svg)](https://pyvista.org/)
[![CAD Standards](https://img.shields.io/badge/Standard-IEC%2061439%20%7C%20IEC%2060529-yellow.svg)]()
[![Tests](https://img.shields.io/badge/Tests-53%20Passed-brightgreen.svg)]()

**Electrical Panel Designer (EPD)** is a professional, deterministic engineering CAD and Bill of Materials (BOM) software application for industrial control panels, switchgear assemblies, and automation cabinets.

Designed for electrical switchboard manufacturers, panel builders, and automation engineers, EPD streamlines the complete engineering lifecycle from technical requirements to 2D layout drafting, 3D digital-twin inspection, and manufacturing CAD deliverables.

---

## Key Features

### 1. Technical Requirements & Engineering Extraction
* **Offline Deterministic Engineering Rules**: Accurately maps motor ratings (e.g., 18 kW maps to the IEC standard 18.5 kW / 25 HP class, ~38A FLA at 415V 3-Phase).
* Auto-selects upstream circuit breakers (MCCB), contactors, line reactors, control power supplies (SMPS), protection MCBs, and terminal distributions.
* Configures operational parameters: Supply Voltage (415V / 230V / 110V), Ingress Protection (**IP54**, **IP55**, **IP65**), and Drive Types (VFD, DOL, Star-Delta, Soft Starter).

### 2. Multi-Vendor Manufacturer Selection & BOM Generation
* **Catalog Vendor Strategies**: Schneider Electric, ABB, Siemens, Connectwell, Mean Well, Rittal, or Mixed Best-of-Breed.
* **Dual Currency Pricing**: Real-time pricing display and calculation in both **USD ($)** and **INR (₹)** across all tables and Excel exports.
* **Component Footprint Database**: Verified physical dimensions ($W \times H \times D$), ventilation clearances, heat loss (Watts), and mounting configurations.
* **Custom Catalog Expansion**: Users can drop custom `.xlsx` spreadsheets directly into the `catalogs/` folder to add their own proprietary components.

### 3. Enclosure Sizing & Door Configurations
* **Mathematical Sizing Engine**: Computes required physical enclosure dimensions based on total component footprint, mandatory IEC ventilation clearances, wire duct routing, and cable gland reserves.
* **Standard Industrial Presets**: Rittal AX/VX and Schneider Spacial standard catalog dimensions.
* **Door Configuration**:
  * **Single Door**: Standard hinged door.
  * **Double Door (Vertical Split)**: Two independent door leaves with a central meeting stile and split seam, ideal for wide floor/wall enclosures ($\ge 1000\text{ mm}$).

### 4. Interactive 2D Front-View Layout Editor
* **Multi-Surface Workspace**:
  * **Mounting Plate (Z View)**: Internal galvanized zinc plate for power devices, DIN rails, and slotted trunking.
  * **Outer Door (Z+1 View)**: Pilot lights, pushbuttons, emergency stops, selectors, and HMIs with cutout dimensions.
* **DIN Rail Vertical Center Snapping**: Any component dragged near a DIN rail automatically centers itself vertically on the rail ($Y_{\text{center}} = Y_{\text{rail\_center}}$), ensuring the DIN rail runs directly through the middle of modular devices.
* **Edge & Center Measurement Tool (`M`)**:
  * Precision 2-click distance measurement tool with keyboard shortcut **`M`**.
  * **Automatic Snapping**: Snaps to component **Centers**, **Top/Bottom/Left/Right Edge Centers**, **Corners**, DIN rails, wire ducts, and enclosure perimeter boundaries.
  * Displays live dynamic dimension lines with callouts for direct distance ($L$), horizontal offset ($\Delta X$), and vertical offset ($\Delta Y$).
* **Professional Alignment & Distribution**: Align Left, Right, Top, Bottom, Horizontal Center, Vertical Center, Distribute H-Space, Distribute V-Space.
* **Dynamic Collision Detection**: Zero-overlap enforcement with visual collision highlights and boundary overflow prevention.

### 5. 3D Digital Twin Visualization
* High-performance interactive 3D rendering powered by **PyVista** and **VTK**.
* Realistic sheet-metal textures: galvanized zinc mounting plate, semi-transparent enclosure frame, slotted wiring ducts, physical DIN EN 60715 rail profiles, and color-coded 3D electrical components.
* Door toggle to inspect internal vs. outer door hardware arrangements.

### 6. Comprehensive Manufacturing Deliverables
* **2D CAD Drawing (`.dxf`)**: AutoCAD-compatible manufacturing layout with layer segregation (`PANEL_BORDER`, `MOUNTING_PLATE`, `DIN_RAILS`, `WIRE_DUCTS`, `COMPONENTS`, `TEXT_LABELS`), component crosshairs, cutouts, double door split lines, and standard engineering title block.
* **3D Neutral CAD Model (`.step`)**: Standard ISO 10303-21 AP214 exchange format for SolidWorks, Autodesk Inventor, PTC Creo, and FreeCAD.
* **Executive Engineering Report (`.html`)**: Self-contained report with thermal loss balance, air conditioning sizing, bill of materials, and manufacturer breakdown.
* **Industrial Quotation & BOM (`.xlsx`)**: Formatted Microsoft Excel workbook with dual currency pricing (USD/INR) and summary metrics.
* **Project File Persistence (`.epd`)**: Standard Electrical Panel Designer project format (processed as JSON).

---

## Application Architecture

```
ElectricalPanelDesigner/
├── main.py                     # Application entry point
├── build_command.txt           # Build commands and instructions
├── requirements.txt            # Python dependencies
├── catalogs/                   # Excel component database catalogs (.xlsx)
├── Deliverables/               # Ready-to-use standalone package
│   ├── ElectricalPanelDesigner.exe
│   ├── catalogs/
│   ├── data/
│   └── README.txt
├── app/
│   ├── ai/                     # Requirements interpretation & offline engines
│   ├── database/               # Catalog manager & SQLite component databases
│   ├── engineering/            # Sizing, DIN rail stacking, thermal calculations
│   ├── export/                 # DXF, STEP, HTML report, and Excel exporters
│   ├── geometry/               # Collision detection, auto-layout, STEP generation
│   ├── gui/                    # PySide6 Qt GUI widgets, 2D editor, 3D viewer
│   ├── models/                 # Component, BOM, Enclosure, and Project data models
│   └── resources/              # Icons and logo graphics
└── tests/                      # Automated test suite (53 tests)
```

---

## Installation & Setup

### Prerequisites
* Python 3.10, 3.11, 3.12, or 3.13
* Windows 10/11 (or Linux/macOS with X11/OpenGL)

### Setup Steps
1. **Clone the repository:**
   ```bash
   git clone https://github.com/aadithya-78/ElectricalPanelDesigner.git
   cd ElectricalPanelDesigner
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the application:**
   ```bash
   python main.py
   ```

---

## Building the Standalone Executable

To compile a standalone, single-file Windows executable (`.exe`) with all libraries, Qt frameworks, VTK renderers, and database engines bundled (no `_internal` folder required):

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "ElectricalPanelDesigner" --icon "app/resources/icons/epd_logo.ico" --add-data "catalogs;catalogs" --add-data "app/resources;app/resources" --add-data "app/database/component_library.db;app/database" main.py
```

The resulting standalone executable will be generated at:
```text
dist/ElectricalPanelDesigner.exe
```

---

## Adding Custom Component Catalogs

Users can add custom parts to the component library at any time. Simply add an `.xlsx` workbook into the `catalogs/` folder following these standard columns:

| Column Header | Type | Description |
| :--- | :--- | :--- |
| `Category` | Text | `Power`, `Control`, `Wiring`, `Accessories` |
| `Manufacturer` | Text | Vendor or brand name |
| `Part_Number` | Text | Unique ordering code |
| `Name` | Text | Component display name |
| `Description` | Text | Technical specification |
| `Width_mm` | Number | Physical width ($X$) |
| `Height_mm` | Number | Physical height ($Y$) |
| `Depth_mm` | Number | Physical depth ($Z$) |
| `Mounting_Type` | Text | `DIN Rail`, `Plate`, or `Door` |
| `Default_Surface` | Text | `Z` (Mounting Plate) or `Z+1` (Door) |
| `Clearance_Top_mm` | Number | Top ventilation clearance |
| `Clearance_Bottom_mm`| Number | Bottom ventilation clearance |
| `Clearance_Sides_mm` | Number | Side-by-side clearance |
| `Heat_Loss_W` | Number | Thermal heat dissipation (Watts) |
| `Price_USD` | Number | Unit price in USD ($) |
| `Price_INR` | Number | Unit price in INR (₹) |

---

## Running Automated Tests

EPD includes a comprehensive test suite covering the 2D workspace, collision validation, enclosure sizing, auto-layout, CAD exports, and dual currency calculations:

```bash
pytest
```

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
