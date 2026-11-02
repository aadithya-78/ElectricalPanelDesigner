"""
Main Application Window for AI Electrical Panel Designer.
Implements the streamlined 5-step engineering workflow:
1. Requirement Input -> 2. AI-Generated Editable BOM -> 3. Panel Sizing Recommendation ->
4. Interactive 2D Panel Design -> 5. 3D Preview & Inspection.
"""
import os
import sys
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QStackedWidget, QMenuBar, QMenu, QStatusBar, 
    QFileDialog, QMessageBox, QFrame, QDialog
)
import os
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtCore import Qt

from app.models.project import ProjectData
from app.database.component_database import ComponentDatabase
from app.database.project_database import ProjectDatabase
from app.gui.styles import DARK_THEME_QSS
from app.gui.component_selection_page import ComponentSelectionPage
from app.gui.bom_editor import BOMEditorPage
from app.gui.panel_size_page import PanelSizePage
from app.gui.panel_2d_editor import Panel2DEditor
from app.gui.viewer_3d_page import Viewer3DPage
from app.gui.dialogs import ThermalDialog
from app.gui.undo_manager import UndoRedoManager
from app.export.excel_export import ExcelBOMExporter
from app.export.report_export import ReportExporter
from app.export.json_export import JSONExporter
from app.export.dxf_export import DXFExporter
from app.geometry.step_exporter import STEPExporter


class MainWindow(QMainWindow):
    @staticmethod
    def _resolve_icon_path(icon_name: str = "epd_logo.png") -> Optional[str]:
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "app", "resources", "icons", icon_name))
            candidates.append(os.path.join(sys._MEIPASS, "resources", "icons", icon_name))
            candidates.append(os.path.join(sys._MEIPASS, icon_name))
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "app", "resources", "icons", icon_name))
        candidates.append(os.path.join(exe_dir, "resources", "icons", icon_name))
        candidates.append(os.path.join(exe_dir, icon_name))
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(gui_dir, "..", "resources", "icons", icon_name))
        candidates.append(os.path.join(os.getcwd(), "app", "resources", "icons", icon_name))
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electrical Panel Designer — Professional 2D & 3D Engineering")
        self.setMinimumSize(1340, 860)
        self.setStyleSheet(DARK_THEME_QSS)

        # Set Window Icon
        icon_path = self._resolve_icon_path("epd_logo.png")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        # Core Engines (Offline & Deterministic)
        self.comp_db = ComponentDatabase()
        self.proj_db = ProjectDatabase()
        self.project = ProjectData("18 kW ATV630 Motor Drive Panel")
        self.undo_manager = UndoRedoManager(lambda: self.project, self._on_undo_redo_restored, max_steps=5)

        self._init_ui()
        self.page_bom.undo_manager = self.undo_manager
        self.page_2d.undo_manager = self.undo_manager
        self._setup_menus()
        self._connect_signals()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Clean Professional Top Navigation Header
        nav_bar = QFrame()
        nav_bar.setObjectName("topNavBar")
        nav_bar.setStyleSheet("""
            QFrame#topNavBar {
                background-color: #FFFFFF;
                border-bottom: 2px solid #8A8C8D;
                min-height: 52px;
            }
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(24, 8, 24, 8)
        nav_layout.setSpacing(12)

        # Brand title with official EPD logo
        brand_box = QHBoxLayout()
        brand_box.setSpacing(10)

        icon_path = self._resolve_icon_path("epd_logo.png")
        if icon_path:
            logo_img = QLabel()
            logo_img.setPixmap(QPixmap(icon_path).scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            brand_box.addWidget(logo_img)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        logo_lbl = QLabel("Electrical Panel Designer")
        logo_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #111C24; letter-spacing: 0.5px;")
        title_box.addWidget(logo_lbl)

        sub_title = QLabel("2D Layout & 3D Physical Verification")
        sub_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF9A4E;")
        title_box.addWidget(sub_title)
        brand_box.addLayout(title_box)
        nav_layout.addLayout(brand_box)

        nav_layout.addSpacing(24)

        # 5-Step Core Navigation
        self.nav_buttons = []
        self.STEPS = [
            ("1. Component Selection", 0),
            ("2. BOM & 3D Preview", 1),
            ("3. Panel Sizing", 2),
            ("4. 2D Layout (Z & Z+1)", 3),
            ("5. 3D Preview", 4)
        ]

        for text, idx in self.STEPS:
            btn = QPushButton(text)
            btn.setCheckable(False)
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_step(i))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_layout.addStretch()

        # Action Buttons (Export & Settings)
        btn_export = QPushButton("Export Deliverables")
        btn_export.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #111C24;
                border: 1.5px solid #8A8C8D;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
                min-height: 26px;
            }
            QPushButton:hover {
                background: #FF9A4E;
                color: #111C24;
                border-color: #616365;
            }
        """)
        btn_export.clicked.connect(self._open_export_dialog)
        nav_layout.addWidget(btn_export)

        main_layout.addWidget(nav_bar)

        # 2. Multi-step Stacked Widget
        self.stack = QStackedWidget()

        # Step 1: Component Selection from Pre-loaded Excel Catalogs
        self.page_select = ComponentSelectionPage()
        self.stack.addWidget(self.page_select)

        # Step 2: AI-Generated Editable BOM with 3D Preview
        self.page_bom = BOMEditorPage(self.comp_db)
        self.stack.addWidget(self.page_bom)

        # Step 3: Panel Size Recommendation & Selection
        self.page_size = PanelSizePage()
        self.stack.addWidget(self.page_size)

        # Step 4: 2D Front-View Layout Editor (Z & Z+1 dual-surface)
        self.page_2d = Panel2DEditor()
        self.stack.addWidget(self.page_2d)

        # Step 5: 3D Visualization & Verification
        self.page_3d = Viewer3DPage()
        self.stack.addWidget(self.page_3d)

        main_layout.addWidget(self.stack)

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background-color: #FFFFFF; color: #616365; border-top: 1px solid #8A8C8D; padding: 4px 12px; font-weight: 500;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Step 1: Select components from pre-loaded Siemens, Schneider, and Phoenix Contact catalogs.")

        self._switch_step(0)

    def _setup_menus(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("background-color: #FFFFFF; color: #111C24; border-bottom: 1px solid #8A8C8D;")

        # File Menu
        menu_file = menubar.addMenu("&File")

        act_new = QAction("&New Project", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._new_project)
        menu_file.addAction(act_new)

        act_open = QAction("&Open Project (.epd)...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_project)
        menu_file.addAction(act_open)

        act_save = QAction("&Save Project (.epd)", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._save_project)
        menu_file.addAction(act_save)

        menu_file.addSeparator()

        act_excel = QAction("Export &BOM to Excel...", self)
        act_excel.triggered.connect(self._export_excel)
        menu_file.addAction(act_excel)

        act_report = QAction("Generate &HTML Layout Report...", self)
        act_report.triggered.connect(self._export_report)
        menu_file.addAction(act_report)

        act_dxf = QAction("Export 2D CAD &DXF Drawing...", self)
        act_dxf.triggered.connect(self._export_dxf)
        menu_file.addAction(act_dxf)

        act_step = QAction("Export 3D &STEP Model...", self)
        act_step.triggered.connect(self._export_step)
        menu_file.addAction(act_step)

        menu_file.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Edit Menu (Undo / Redo up to 5 steps)
        menu_edit = menubar.addMenu("&Edit")
        self.act_undo = QAction("&Undo", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(self._on_undo)
        self.act_undo.setEnabled(False)
        menu_edit.addAction(self.act_undo)

        self.act_redo = QAction("&Redo", self)
        self.act_redo.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
        self.act_redo.triggered.connect(self._on_redo)
        self.act_redo.setEnabled(False)
        menu_edit.addAction(self.act_redo)

        # Miscellaneous Menu (DIN Rails & Wiring Ducts)
        menu_misc = menubar.addMenu("&Miscellaneous")
        act_add_din = QAction("Add &DIN Rail (35mm)", self)
        act_add_din.setShortcut("Ctrl+D")
        act_add_din.triggered.connect(self._add_din_rail_action)
        menu_misc.addAction(act_add_din)

        act_add_duct_h = QAction("Add &Horizontal Wiring Duct", self)
        act_add_duct_h.triggered.connect(self._add_duct_h_action)
        menu_misc.addAction(act_add_duct_h)

        act_add_duct_v = QAction("Add &Vertical Wiring Duct", self)
        act_add_duct_v.triggered.connect(self._add_duct_v_action)
        menu_misc.addAction(act_add_duct_v)

        # Tools Menu
        menu_tools = menubar.addMenu("&Tools")
        act_thermal = QAction("&Thermal & Cooling Analysis...", self)
        act_thermal.triggered.connect(self._open_thermal)
        menu_tools.addAction(act_thermal)

    def _connect_signals(self):
        self.page_select.bom_ready.connect(self._on_catalog_bom_ready)
        self.page_bom.bom_approved.connect(self._on_bom_approved)
        self.page_bom.bom_modified.connect(self._on_bom_modified)
        self.page_size.panel_size_confirmed.connect(self._on_panel_size_confirmed)
        self.page_2d.generate_3d_requested.connect(self._on_generate_3d_requested)
        self.page_3d.back_to_2d_requested.connect(lambda: self._switch_step(3))
        self.page_3d.export_requested.connect(self._open_export_dialog)

    def _on_undo(self):
        if self.undo_manager.undo():
            self.status_bar.showMessage("Undone (Ctrl+Z) - restored previous state.")
            self._update_undo_redo_actions()

    def _on_redo(self):
        if self.undo_manager.redo():
            self.status_bar.showMessage("Redone (Ctrl+Y) - re-applied state.")
            self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        can_u = self.undo_manager.can_undo()
        can_r = self.undo_manager.can_redo()
        self.act_undo.setEnabled(can_u)
        self.act_redo.setEnabled(can_r)
        if hasattr(self, 'page_2d') and hasattr(self.page_2d, '_update_undo_redo_ui'):
            self.page_2d._update_undo_redo_ui()

    def _on_undo_redo_restored(self):
        # 0. Update Component Selection page
        if hasattr(self, 'page_select') and self.project.bom:
            self.page_select.set_selected_components(self.project.bom.items)

        # 1. Update BOM editor table
        if hasattr(self, 'page_bom') and self.project.bom:
            self.page_bom.bom = self.project.bom
            self.page_bom._refresh_table()

        # 2. Update panel size page
        if hasattr(self, 'page_size') and self.project.enclosure:
            self.page_size.set_project(self.project)

        # 3. Update 2D layout editor
        if hasattr(self, 'page_2d') and self.page_2d.project:
            self.page_2d._rebuild_scene()
            self.page_2d._refresh_palette()
            self.page_2d._update_status_bar()
            self.page_2d._revalidate_and_highlight()

        # 4. Update 3D page if active
        if hasattr(self, 'page_3d') and self.stack.currentWidget() == self.page_3d:
            self.page_3d.load_project(self.project)

        self._update_undo_redo_actions()

    def _on_bom_modified(self, bom):
        if self.undo_manager and getattr(self.undo_manager, "_is_undoing_redoing", False):
            return
        self.project.bom = bom
        self.project.reconcile_instances_with_bom()
        if hasattr(self, 'page_2d') and self.page_2d.project is self.project:
            self.page_2d.sync_instances_from_project()
        if hasattr(self, 'page_size') and self.project.enclosure:
            self.page_size.set_project(self.project)
        self._update_undo_redo_actions()

    def _switch_step(self, step_idx: int):
        # Synchronize and refresh target step from project data
        if step_idx == 0:
            if hasattr(self, 'page_select') and self.project and self.project.bom:
                self.page_select.set_selected_components(self.project.bom.items)
        elif step_idx == 1:
            if hasattr(self, 'page_bom') and self.project and self.project.bom:
                self.page_bom.bom = self.project.bom
                self.page_bom._refresh_table()
        elif step_idx == 2:
            if hasattr(self, 'page_size') and self.project:
                self.page_size.set_project(self.project)
        elif step_idx == 3:
            if hasattr(self, 'page_2d') and self.project:
                self.page_2d.load_project(self.project)
        elif step_idx == 4:
            if hasattr(self, 'page_3d') and self.project:
                self.page_3d.load_project(self.project)

        self.stack.setCurrentIndex(step_idx)
        for idx, btn in enumerate(self.nav_buttons):
            if idx == step_idx:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FF9A4E;
                        color: #111C24;
                        border: 1.5px solid #E88536;
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-weight: 700;
                        font-size: 11px;
                        min-height: 26px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #616365;
                        border: 1.5px solid #8A8C8D;
                        border-radius: 6px;
                        padding: 4px 10px;
                        font-weight: 600;
                        font-size: 11px;
                        min-height: 26px;
                    }
                    QPushButton:hover {
                        background-color: #F5F6F7;
                        color: #111C24;
                        border-color: #FF9A4E;
                    }
                """)

    def _on_catalog_bom_ready(self, bom_items: list, summary_data: dict = None):
        self.project.raw_requirement = f"Catalog project ({len(bom_items)} selected components)"
        self.page_bom.set_bom_items(bom_items)
        self.project.bom = self.page_bom.bom
        self.project.reconcile_instances_with_bom()
        self._switch_step(1)
        self.status_bar.showMessage("Step 2: Review BOM components, edit ratings/dimensions, and inspect 3D models.")

    def _on_bom_ready(self, bom_items: list, req_data: dict):
        self.page_bom.set_bom_items(bom_items)
        self.project.bom = self.page_bom.bom
        self.project.reconcile_instances_with_bom()
        self._switch_step(1)
        self.status_bar.showMessage("Step 2: Review and edit BOM components, ratings, and physical dimensions.")

    def _on_bom_approved(self, bom):
        self.project.bom = bom
        self.project.reconcile_instances_with_bom()
        self.page_size.set_project(self.project)
        self._switch_step(2)
        self.status_bar.showMessage("Step 3: Review panel size recommendation and specify enclosure external envelope.")
        self._update_undo_redo_actions()

    def _on_panel_size_confirmed(self, enclosure):
        self.project.enclosure = enclosure
        self.page_2d.load_project(self.project)
        self._switch_step(3)
        self.status_bar.showMessage("Step 4: 2D Front-View Mounting Plate Layout Editor. Drag components from palette to place.")
        self._update_undo_redo_actions()

    def _on_generate_3d_requested(self):
        self.page_3d.load_project(self.project)
        self._switch_step(4)
        self.status_bar.showMessage("Step 5: 3D Visualization and physical clearance verification.")

    def _open_export_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Export Project Deliverables")
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(14)
        lay.setContentsMargins(24, 24, 24, 24)

        t_lbl = QLabel("Export Engineering Deliverables")
        t_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #FFFFFF;")
        lay.addWidget(t_lbl)

        sub = QLabel("Select format to export for manufacturing, CAD, or quotation:")
        sub.setStyleSheet("color: #94A3B8; font-size: 13px;")
        lay.addWidget(sub)

        # Excel
        btn_x = QPushButton("Export Bill of Materials to Excel (.xlsx)")
        btn_x.setMinimumHeight(40)
        btn_x.clicked.connect(lambda: (dlg.accept(), self._export_excel()))
        lay.addWidget(btn_x)

        # HTML Report
        btn_r = QPushButton("Generate Complete Engineering HTML Report")
        btn_r.setProperty("class", "secondary")
        btn_r.setMinimumHeight(40)
        btn_r.clicked.connect(lambda: (dlg.accept(), self._export_report()))
        lay.addWidget(btn_r)

        # 2D CAD DXF
        btn_d = QPushButton("Export 2D CAD DXF Drawing (.dxf)")
        btn_d.setProperty("class", "secondary")
        btn_d.setMinimumHeight(40)
        btn_d.clicked.connect(lambda: (dlg.accept(), self._export_dxf()))
        lay.addWidget(btn_d)

        # Project File (.epd)
        btn_j = QPushButton("Save Project File (.epd)")
        btn_j.setProperty("class", "secondary")
        btn_j.setMinimumHeight(40)
        btn_j.clicked.connect(lambda: (dlg.accept(), self._save_project()))
        lay.addWidget(btn_j)

        # STEP
        btn_s = QPushButton("Export 3D CAD STEP File (.step)")
        btn_s.setProperty("class", "secondary")
        btn_s.setMinimumHeight(40)
        btn_s.clicked.connect(lambda: (dlg.accept(), self._export_step()))
        lay.addWidget(btn_s)

        btn_close = QPushButton("Close")
        btn_close.setProperty("class", "secondary")
        btn_close.setMinimumHeight(34)
        btn_close.clicked.connect(dlg.reject)
        lay.addWidget(btn_close)

        dlg.exec()

    def _new_project(self):
        self.project = ProjectData("New Motor Drive Panel")
        self.undo_manager.clear()
        self._update_undo_redo_actions()
        if hasattr(self, 'page_select'):
            self.page_select.clear_selection()
        self._switch_step(0)
        self.status_bar.showMessage("New project started. Select components from pre-loaded catalogs.")

    def _open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Electrical Panel Project",
            "",
            "Electrical Panel Project (*.epd);;JSON Files (*.json);;All Files (*.*)"
        )
        if file_path:
            try:
                proj = JSONExporter.import_project(file_path)
                self.project = proj
                self.project.reconcile_instances_with_bom()
                self.undo_manager.clear()

                # 1. Update Component Selection page (Step 1)
                if hasattr(self, 'page_select') and proj.bom:
                    self.page_select.set_selected_components(proj.bom.items)

                # 2. Update BOM editor table (Step 2)
                self.page_bom.bom = proj.bom
                self.page_bom._refresh_table()

                # 3. Update panel size page (Step 3)
                self.page_size.set_project(proj)

                # 4. Update 2D layout editor (Step 4)
                self.page_2d.load_project(proj)

                # 5. Update 3D viewer (Step 5)
                if hasattr(self, 'page_3d'):
                    self.page_3d.load_project(proj)

                # Navigate to Step 4 (2D layout) with all steps initialized
                self._switch_step(3)
                self._update_undo_redo_actions()
                QMessageBox.information(self, "Project Loaded", f"Loaded project: {proj.name}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load project: {str(e)}")

    def _save_project(self):
        default_name = f"{self.project.name}.epd" if not self.project.name.endswith(".epd") else self.project.name
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Electrical Panel Project",
            default_name,
            "Electrical Panel Project (*.epd);;JSON Files (*.json)"
        )
        if file_path:
            try:
                JSONExporter.export_project(self.project, file_path)
                QMessageBox.information(self, "Project Saved", f"Saved successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save project: {str(e)}")

    def _export_excel(self):
        if not self.project.bom or not self.project.bom.items:
            QMessageBox.warning(self, "No BOM", "BOM is empty. Generate a BOM first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export BOM to Excel", f"{self.project.name}_BOM.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                ExcelBOMExporter.export_bom(self.project.bom, file_path)
                QMessageBox.information(self, "Export Complete", f"Exported BOM to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export Excel file: {str(e)}")

    def _export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export HTML Report", f"{self.project.name}_Report.html", "HTML Files (*.html)")
        if file_path:
            try:
                ReportExporter.export_html_report(self.project, file_path)
                QMessageBox.information(self, "Report Generated", f"Generated complete engineering report:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Report Error", f"Failed to generate report: {str(e)}")

    def _export_dxf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export 2D CAD DXF", f"{self.project.name}.dxf", "AutoCAD DXF Files (*.dxf)")
        if file_path:
            try:
                success = DXFExporter.export_project(self.project, file_path)
                if success:
                    QMessageBox.information(
                        self,
                        "DXF Export Complete",
                        f"Successfully exported 2D CAD DXF layout to:\n{file_path}\n\nCompatible with AutoCAD, SolidWorks, DraftSight, LibreCAD, and CNC machinery."
                    )
                else:
                    QMessageBox.critical(self, "DXF Export Error", "Failed to write DXF drawing.")
            except Exception as e:
                QMessageBox.critical(self, "DXF Export Error", f"Failed to export DXF: {str(e)}")

    def _export_step(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export 3D STEP", f"{self.project.name}.step", "STEP Files (*.step *.stp)")
        if file_path:
            try:
                res = STEPExporter.export_step(
                    self.project.enclosure,
                    self.project.physical_instances,
                    self.project.din_rails,
                    self.project.wiring_ducts,
                    file_path
                )
                if res.get("success", False):
                    QMessageBox.information(
                        self,
                        "STEP Export Complete",
                        f"Successfully exported 3D STEP assembly model to:\n{file_path}\n\nCompatible with SolidWorks, Autodesk Inventor, Fusion 360, and PTC Creo."
                    )
                else:
                    QMessageBox.critical(self, "STEP Export Error", res.get("error", "Unknown error exporting STEP."))
            except Exception as e:
                QMessageBox.critical(self, "STEP Export Error", f"Failed to export STEP model: {str(e)}")

    def _add_din_rail_action(self):
        self._switch_step(3)
        self.page_2d.add_workspace_object("din_rail")

    def _add_duct_h_action(self):
        self._switch_step(3)
        self.page_2d.add_workspace_object("wire_duct_h")

    def _add_duct_v_action(self):
        self._switch_step(3)
        self.page_2d.add_workspace_object("wire_duct_v")

    def _open_thermal(self):
        dlg = ThermalDialog(self.project, self)
        dlg.exec()
