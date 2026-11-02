"""
Unit tests for CAD & deliverable export formats:
HTML, STEP, DXF, and Excel.
"""
import os
import tempfile
import pytest

from app.models.project import ProjectData
from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.models.component import Component, ComponentCategory, MountingType, PhysicalInstance
from app.models.bom import BOM
from app.export.dxf_export import DXFExporter
from app.export.report_export import ReportExporter
from app.geometry.step_exporter import STEPExporter


@pytest.fixture
def sample_project():
    proj = ProjectData("Test Panel Project")
    proj.enclosure = Enclosure(width=800.0, height=1200.0, depth=400.0, ip_rating="IP54")
    
    c1 = Component(
        item_no=1,
        category=ComponentCategory.POWER,
        name="VFD 18kW",
        manufacturer="Schneider Electric",
        part_number="ATV630D18N4",
        quantity=1,
        width_mm=211.0,
        height_mm=546.0,
        depth_mm=232.0,
        unit_price=1850.0,
        mounting_type=MountingType.PLATE,
        surface="Z"
    )
    c2 = Component(
        item_no=2,
        category=ComponentCategory.CONTROL,
        name="HMI Touch Screen",
        manufacturer="Siemens",
        part_number="6AV2123-2GB03-0AX0",
        quantity=1,
        width_mm=214.0,
        height_mm=158.0,
        depth_mm=45.0,
        unit_price=420.0,
        mounting_type=MountingType.DOOR,
        surface="Z+1"
    )
    proj.bom = BOM([c1, c2])
    instances = proj.bom.expand_to_instances()
    instances[0].is_placed = True
    instances[0].x = 50.0
    instances[0].y = 400.0
    instances[0].z = 10.0

    instances[1].is_placed = True
    instances[1].x = 293.0
    instances[1].y = 800.0
    instances[1].z = 355.0

    proj.physical_instances = instances
    
    proj.din_rails = [
        DINRail(id="rail_1", name="DIN Rail 1", x=40.0, y=300.0, length=720.0, height=35.0, depth=7.5)
    ]
    proj.wiring_ducts = [
        WiringDuct(id="duct_1", name="Wire Duct 1", x=40.0, y=250.0, width=720.0, height=40.0, orientation="Horizontal")
    ]
    return proj


def test_dxf_export(sample_project):
    """Verify 2D CAD DXF export generates standard AC1009 entities, layers, and coordinates."""
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tf:
        dxf_path = tf.name

    try:
        success = DXFExporter.export_project(sample_project, dxf_path)
        assert success is True
        assert os.path.exists(dxf_path)
        assert os.path.getsize(dxf_path) > 500

        with open(dxf_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check DXF standard structure
        assert "SECTION" in content
        assert "HEADER" in content
        assert "$ACADVER" in content
        assert "AC1009" in content
        assert "TABLES" in content
        assert "ENTITIES" in content
        assert "EOF" in content

        # Check standard CAD layers
        assert "PANEL_BORDER" in content
        assert "MOUNTING_PLATE" in content
        assert "DIN_RAILS" in content
        assert "WIRE_DUCTS" in content
        assert "COMPONENTS_PLATE" in content
        assert "COMPONENTS_DOOR" in content

        # Check component text tags
        assert "ATV630D18N4" in content
        assert "6AV2123-2GB03-0AX0" in content
    finally:
        if os.path.exists(dxf_path):
            os.remove(dxf_path)


def test_step_export(sample_project):
    """Verify 3D CAD STEP export generates valid ISO 10303-21 solids and geometry."""
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tf:
        step_path = tf.name

    try:
        res = STEPExporter.export_step(
            sample_project.enclosure,
            sample_project.physical_instances,
            sample_project.din_rails,
            sample_project.wiring_ducts,
            step_path
        )
        assert res.get("success", False) is True
        assert os.path.exists(step_path)
        assert os.path.getsize(step_path) > 1000

        with open(step_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify ISO 10303-21 standard syntax
        assert "ISO-10303-21;" in content
        assert "HEADER;" in content
        assert "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));" in content
        assert "DATA;" in content
        assert "CARTESIAN_POINT" in content
        assert "POLY_LOOP" in content
        assert "ADVANCED_FACE" in content
        assert "CLOSED_SHELL" in content
        assert "MANIFOLD_SOLID_BREP" in content
        assert "SHAPE_REPRESENTATION" in content
        assert "END-ISO-10303-21;" in content

        # Verify solids are named
        assert "Mounting_Plate" in content
        assert "DIN_Rail" in content
        assert "Wire_Duct" in content
    finally:
        if os.path.exists(step_path):
            os.remove(step_path)


def test_html_report_export(sample_project):
    """Verify HTML engineering layout report includes dual currency, BOM, and specs."""
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
        html_path = tf.name

    try:
        success = ReportExporter.export_report(sample_project, html_path)
        assert success is True
        assert os.path.exists(html_path)
        assert os.path.getsize(html_path) > 1000

        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "<!DOCTYPE html>" in content
        assert "ELECTRICAL PANEL DESIGNER — ENGINEERING REPORT" in content
        assert "ATV630D18N4" in content
        assert "Unit Price ($ / ₹)" in content
        assert "Total Price ($ / ₹)" in content
        assert "$1,850.00" in content
    finally:
        if os.path.exists(html_path):
            os.remove(html_path)


def test_epd_project_save_and_load(sample_project):
    """Verify that .epd project files are saved and imported cleanly as JSON."""
    from app.export.json_export import JSONExporter
    import json

    with tempfile.NamedTemporaryFile(suffix=".epd", delete=False) as tf:
        epd_path = tf.name

    try:
        success = JSONExporter.export_project(sample_project, epd_path)
        assert success is True
        assert os.path.exists(epd_path)

        # Verify underlying content is valid JSON
        with open(epd_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["project_name"] == "Test Panel Project"
        assert len(data["bom"]) == 2

        # Re-import from .epd
        loaded = JSONExporter.import_project(epd_path)
        assert loaded.project_name == "Test Panel Project"
        assert len(loaded.bom.items) == 2
        assert loaded.enclosure.width == 800.0
    finally:
        if os.path.exists(epd_path):
            os.remove(epd_path)


def test_double_door_enclosure_and_dxf(sample_project):
    """Test double door configuration, serialization, and DXF split seam output."""
    sample_project.enclosure.door_type = "DOUBLE_VERTICAL"
    
    # Test serialization
    enc_dict = sample_project.enclosure.to_dict()
    assert enc_dict["door_type"] == "DOUBLE_VERTICAL"
    restored = Enclosure.from_dict(enc_dict)
    assert restored.door_type == "DOUBLE_VERTICAL"

    # Test DXF export contains double door markers
    dxf_content = DXFExporter.generate_dxf_string(
        sample_project.enclosure,
        sample_project.physical_instances,
        sample_project.din_rails,
        sample_project.wiring_ducts,
        project_name=sample_project.project_name
    )
    assert "OUTER DOUBLE DOOR (VERTICAL SPLIT)" in dxf_content
    assert "LEFT DOOR LEAF" in dxf_content
    assert "RIGHT DOOR LEAF" in dxf_content


def test_ar_glb_generation_and_scale(sample_project):
    """Test 1:1 real-world scale GLB export for mobile Augmented Reality."""
    from app.export.ar_server import generate_panel_glb

    glb_bytes, metadata = generate_panel_glb(
        sample_project.enclosure,
        sample_project.physical_instances,
        sample_project.din_rails,
        sample_project.wiring_ducts
    )

    # GLB starts with magic bytes b'glTF'
    assert glb_bytes[:4] == b"glTF"
    assert len(glb_bytes) > 2000
    assert metadata["width_mm"] == 800.0
    assert metadata["height_mm"] == 1200.0
    assert metadata["depth_mm"] == 400.0
    assert metadata["component_count"] >= 1


def test_ar_server_lifecycle_and_endpoints(sample_project):
    """Test background AR HTTP server lifecycle and endpoints: /, /model.glb, /qr, /status."""
    import urllib.request
    from app.export.ar_server import get_ar_server

    srv = get_ar_server()
    url = srv.start()
    assert url.startswith("http://")
    assert srv.is_running is True

    try:
        srv.update_model(
            sample_project.enclosure,
            sample_project.physical_instances,
            sample_project.din_rails,
            sample_project.wiring_ducts
        )

        # 1. HTML WebAR root
        html_resp = urllib.request.urlopen(f"{url}/").read().decode("utf-8")
        assert "<model-viewer" in html_resp
        assert "ar-scale=\"fixed\"" in html_resp
        assert "Electrical Panel AR" in html_resp

        # 2. Binary GLB model
        glb_resp = urllib.request.urlopen(f"{url}/model.glb").read()
        assert glb_resp[:4] == b"glTF"
        assert len(glb_resp) == len(srv.glb_data)

        # 3. QR code PNG
        qr_resp = urllib.request.urlopen(f"{url}/qr").read()
        assert qr_resp[:4] == b"\x89PNG"

        # 4. Status metadata
        status_resp = urllib.request.urlopen(f"{url}/status").read().decode("utf-8")
        assert "width_mm" in status_resp
        assert "800" in status_resp
    finally:
        srv.stop()
        assert srv.is_running is False



