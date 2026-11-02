"""
SQLite Component Library Database.
Stores verified component dimensions, ratings, heat loss, and mounting types.
Pre-populated with industrial standard parts.
"""
import os
import sqlite3
import sys
import shutil
from typing import List, Dict, Any, Optional


def get_db_path(db_filename: str = "component_library.db") -> str:
    """
    Resolve an absolute, writable path for SQLite database files.
    Ensures parent directory is created and handles:
    - Normal Python source execution
    - PyInstaller --onefile mode
    - PyInstaller --onedir mode
    """
    # 1. If running frozen, try alongside executable (data folder or exe dir)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        cand_dirs = [
            os.path.join(exe_dir, "data"),
            exe_dir
        ]
        for cdir in cand_dirs:
            try:
                os.makedirs(cdir, exist_ok=True)
                test_file = os.path.join(cdir, f".test_{os.getpid()}")
                with open(test_file, "w") as tf:
                    tf.write("1")
                os.remove(test_file)
                target_path = os.path.join(cdir, db_filename)
                _seed_file_if_needed(target_path, db_filename)
                return target_path
            except Exception:
                continue

    # 2. In development, check app/database/
    dev_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(dev_dir, exist_ok=True)
        test_file = os.path.join(dev_dir, f".test_{os.getpid()}")
        with open(test_file, "w") as tf:
            tf.write("1")
        os.remove(test_file)
        target_path = os.path.join(dev_dir, db_filename)
        _seed_file_if_needed(target_path, db_filename)
        return target_path
    except Exception:
        pass

    # 3. Fallback to user AppData (guaranteed writable on Windows)
    app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    fallback_dir = os.path.join(app_data, "ElectricalPanelDesigner", "data")
    os.makedirs(fallback_dir, exist_ok=True)
    target_path = os.path.join(fallback_dir, db_filename)
    _seed_file_if_needed(target_path, db_filename)
    return target_path


def _seed_file_if_needed(target_path: str, db_filename: str):
    """If target DB file does not exist, check bundled sources and copy over."""
    if os.path.isfile(target_path):
        return
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "app", "database", db_filename))
        candidates.append(os.path.join(sys._MEIPASS, "data", db_filename))
        candidates.append(os.path.join(sys._MEIPASS, db_filename))
    candidates.append(os.path.join(os.path.dirname(__file__), db_filename))
    for c in candidates:
        if os.path.isfile(c) and c != target_path:
            try:
                shutil.copy2(c, target_path)
                return
            except Exception:
                pass


DEFAULT_DB_PATH = get_db_path("component_library.db")


class ComponentDatabase:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path if db_path is not None else get_db_path("component_library.db")
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    manufacturer TEXT NOT NULL,
                    part_number TEXT,
                    description TEXT,
                    width_mm REAL NOT NULL,
                    height_mm REAL NOT NULL,
                    depth_mm REAL NOT NULL,
                    mounting_type TEXT NOT NULL,
                    clearance_top_mm REAL DEFAULT 10.0,
                    clearance_bottom_mm REAL DEFAULT 10.0,
                    clearance_sides_mm REAL DEFAULT 5.0,
                    heat_loss_watts REAL DEFAULT 0.0,
                    unit_price REAL DEFAULT 0.0,
                    verified INTEGER DEFAULT 0
                )
            """)
            conn.commit()

        # Seed initial library if empty
        if self.count() == 0:
            self._seed_default_library()

    def count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM components")
            return cursor.fetchone()[0]

    def add_component(self, comp: Dict[str, Any]) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO components (
                    name, category, manufacturer, part_number, description,
                    width_mm, height_mm, depth_mm, mounting_type,
                    clearance_top_mm, clearance_bottom_mm, clearance_sides_mm,
                    heat_loss_watts, unit_price, verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                comp.get("name", "Unknown"),
                comp.get("category", "Power"),
                comp.get("manufacturer", "Generic"),
                comp.get("part_number"),
                comp.get("description", ""),
                float(comp.get("width_mm", 50.0)),
                float(comp.get("height_mm", 75.0)),
                float(comp.get("depth_mm", 60.0)),
                comp.get("mounting_type", "Plate"),
                float(comp.get("clearance_top_mm", 10.0)),
                float(comp.get("clearance_bottom_mm", 10.0)),
                float(comp.get("clearance_sides_mm", 5.0)),
                float(comp.get("heat_loss_watts", 0.0)),
                float(comp.get("unit_price", 0.0)),
                1 if comp.get("verified", False) else 0
            ))
            conn.commit()
            return cursor.lastrowid

    def find_by_part_or_name(self, query: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            q = f"%{query}%"
            cursor.execute("""
                SELECT * FROM components 
                WHERE name LIKE ? OR part_number LIKE ? OR description LIKE ?
                LIMIT 50
            """, (q, q, q))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_exact_match(self, manufacturer: str, part_number: str) -> Optional[Dict[str, Any]]:
        if not part_number:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM components 
                WHERE LOWER(manufacturer) = LOWER(?) AND LOWER(part_number) = LOWER(?)
                LIMIT 1
            """, (manufacturer, part_number))
            row = cursor.fetchone()
            return dict(row) if row else None

    def _seed_default_library(self):
        """Pre-populate realistic industrial components."""
        seeds = [
            # Schneider ATV630 Drives
            {
                "name": "Altivar Process ATV630 18.5 kW",
                "category": "Power",
                "manufacturer": "Schneider Electric",
                "part_number": "ATV630D18N4",
                "description": "3-Phase 380-480V 18.5 kW / 25 HP VFD IP21",
                "width_mm": 211.0, "height_mm": 546.0, "depth_mm": 232.0,
                "mounting_type": "Plate", "clearance_top_mm": 100.0, "clearance_bottom_mm": 100.0, "clearance_sides_mm": 50.0,
                "heat_loss_watts": 455.0, "unit_price": 1850.0, "verified": 1
            },
            {
                "name": "Altivar Process ATV630 15 kW",
                "category": "Power",
                "manufacturer": "Schneider Electric",
                "part_number": "ATV630D15N4",
                "description": "3-Phase 380-480V 15 kW / 20 HP VFD IP21",
                "width_mm": 211.0, "height_mm": 546.0, "depth_mm": 232.0,
                "mounting_type": "Plate", "clearance_top_mm": 100.0, "clearance_bottom_mm": 100.0, "clearance_sides_mm": 50.0,
                "heat_loss_watts": 380.0, "unit_price": 1600.0, "verified": 1
            },
            {
                "name": "Altivar Process ATV630 30 kW",
                "category": "Power",
                "manufacturer": "Schneider Electric",
                "part_number": "ATV630D30N4",
                "description": "3-Phase 380-480V 30 kW / 40 HP VFD IP21",
                "width_mm": 226.0, "height_mm": 673.0, "depth_mm": 274.0,
                "mounting_type": "Plate", "clearance_top_mm": 100.0, "clearance_bottom_mm": 100.0, "clearance_sides_mm": 50.0,
                "heat_loss_watts": 680.0, "unit_price": 2750.0, "verified": 1
            },
            # MCCBs
            {
                "name": "Compact NSX100F 63A 3P MCCB",
                "category": "Power",
                "manufacturer": "Schneider Electric",
                "part_number": "LV429630",
                "description": "3P 63A 36kA thermal-magnetic trip unit",
                "width_mm": 105.0, "height_mm": 161.0, "depth_mm": 86.0,
                "mounting_type": "Plate", "clearance_top_mm": 30.0, "clearance_bottom_mm": 30.0, "clearance_sides_mm": 15.0,
                "heat_loss_watts": 18.0, "unit_price": 280.0, "verified": 1
            },
            {
                "name": "Compact NSX100F 100A 3P MCCB",
                "category": "Power",
                "manufacturer": "Schneider Electric",
                "part_number": "LV429631",
                "description": "3P 100A 36kA thermal-magnetic trip unit",
                "width_mm": 105.0, "height_mm": 161.0, "depth_mm": 86.0,
                "mounting_type": "Plate", "clearance_top_mm": 30.0, "clearance_bottom_mm": 30.0, "clearance_sides_mm": 15.0,
                "heat_loss_watts": 24.0, "unit_price": 310.0, "verified": 1
            },
            # AC Line Reactor
            {
                "name": "Input AC Line Choke 3% 45A",
                "category": "Power",
                "manufacturer": "Schneider Electric",
                "part_number": "VW3A4554",
                "description": "Line choke 45A for ATV630 15/18.5 kW",
                "width_mm": 180.0, "height_mm": 210.0, "depth_mm": 140.0,
                "mounting_type": "Plate", "clearance_top_mm": 40.0, "clearance_bottom_mm": 40.0, "clearance_sides_mm": 20.0,
                "heat_loss_watts": 95.0, "unit_price": 240.0, "verified": 1
            },
            # SMPS
            {
                "name": "Mean Well HDR-60-24 24V 2.5A SMPS",
                "category": "Control",
                "manufacturer": "Mean Well",
                "part_number": "HDR-60-24",
                "description": "Ultra slim 60W 24V DC DIN rail power supply",
                "width_mm": 52.0, "height_mm": 90.0, "depth_mm": 55.0,
                "mounting_type": "DIN Rail", "clearance_top_mm": 20.0, "clearance_bottom_mm": 20.0, "clearance_sides_mm": 10.0,
                "heat_loss_watts": 9.0, "unit_price": 38.0, "verified": 1
            },
            # MCBs
            {
                "name": "Acti9 iC60N 2P 6A C-Curve MCB",
                "category": "Control",
                "manufacturer": "Schneider Electric",
                "part_number": "A9F74206",
                "description": "2P 6A 10kA miniature circuit breaker",
                "width_mm": 36.0, "height_mm": 85.0, "depth_mm": 78.0,
                "mounting_type": "DIN Rail", "clearance_top_mm": 20.0, "clearance_bottom_mm": 20.0, "clearance_sides_mm": 5.0,
                "heat_loss_watts": 2.2, "unit_price": 22.0, "verified": 1
            },
            # Terminals
            {
                "name": "Connectwell Feed-Through Terminal 35 sq mm",
                "category": "Power",
                "manufacturer": "Connectwell",
                "part_number": "CTS35U",
                "description": "High current DIN terminal block 35 sq mm 125A 1000V",
                "width_mm": 16.0, "height_mm": 58.0, "depth_mm": 54.0,
                "mounting_type": "DIN Rail", "clearance_top_mm": 15.0, "clearance_bottom_mm": 15.0, "clearance_sides_mm": 0.0,
                "heat_loss_watts": 2.5, "unit_price": 8.0, "verified": 1
            },
            {
                "name": "Connectwell Terminal Block 2.5 sq mm",
                "category": "Control",
                "manufacturer": "Connectwell",
                "part_number": "CTS2.5UN",
                "description": "Control DIN terminal block 2.5 sq mm 24A 800V",
                "width_mm": 6.0, "height_mm": 45.0, "depth_mm": 43.0,
                "mounting_type": "DIN Rail", "clearance_top_mm": 15.0, "clearance_bottom_mm": 15.0, "clearance_sides_mm": 0.0,
                "heat_loss_watts": 0.2, "unit_price": 1.2, "verified": 1
            },
            # Rittal Filter Fan
            {
                "name": "Rittal TopTherm Filter Fan 230V AC",
                "category": "Accessories",
                "manufacturer": "Rittal",
                "part_number": "SK 3239.100",
                "description": "Filter fan unit 230 m3/h air throughput",
                "width_mm": 204.0, "height_mm": 204.0, "depth_mm": 90.0,
                "mounting_type": "Door", "clearance_top_mm": 15.0, "clearance_bottom_mm": 15.0, "clearance_sides_mm": 15.0,
                "heat_loss_watts": 19.0, "unit_price": 95.0, "verified": 1
            }
        ]

        for s in seeds:
            self.add_component(s)

