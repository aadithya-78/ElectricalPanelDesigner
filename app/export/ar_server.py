"""
Augmented Reality (AR) Web Server & 3D GLB/glTF Exporter for Electrical Enclosures.
Enables instant 1:1 physical scale AR viewing on mobile devices (Android & iOS).
- Exports CAD layout (mm) to glTF/GLB with 0.001 scale conversion (meters for real-world AR).
- Serves interactive WebAR page powered by Google @model-viewer and Google Scene Viewer / Quick Look.
- Generates dynamic LAN IP link and QR code for one-click mobile camera scanning.
"""
import io
import json
import os
import socket
import struct
import base64
import tempfile
import threading
from typing import List, Optional, Tuple, Dict, Any
import http.server
import socketserver

import pyvista as pv

from app.models.enclosure import Enclosure, DINRail, WiringDuct
from app.models.component import PhysicalInstance


def get_local_ip() -> str:
    """Detect the local LAN/Wi-Fi IPv4 address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connecting to public or broadcast IP selects the active outgoing network interface
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def find_free_port(start_port: int = 8080, max_attempts: int = 25) -> int:
    """Find the next available TCP port starting from start_port."""
    for p in range(start_port, start_port + max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', p))
            sock.close()
            return p
        except OSError:
            continue
    return start_port


def gltf_to_glb(gltf_dict: Dict[str, Any]) -> bytes:
    """
    Package a glTF 2.0 dictionary containing embedded base64 data URIs
    into a standardized binary GLB (glTF 2.0 Binary container).
    """
    combined_bin = bytearray()
    buffers = gltf_dict.get('buffers', [])
    buffer_offsets = []

    for buf in buffers:
        uri = buf.get('uri', '')
        if uri.startswith('data:application/octet-stream;base64,'):
            b64_data = uri.split(',', 1)[1]
            raw_bytes = base64.b64decode(b64_data)
        elif uri.startswith('data:;base64,'):
            b64_data = uri.split(',', 1)[1]
            raw_bytes = base64.b64decode(b64_data)
        else:
            raw_bytes = b''

        # Align each buffer to 4-byte boundary
        while len(combined_bin) % 4 != 0:
            combined_bin.append(0)

        offset = len(combined_bin)
        buffer_offsets.append(offset)
        combined_bin.extend(raw_bytes)

    # Remap bufferViews to the unified binary chunk
    for bv in gltf_dict.get('bufferViews', []):
        old_buf_idx = bv.get('buffer', 0)
        old_offset = bv.get('byteOffset', 0)
        bv['buffer'] = 0
        base_offset = buffer_offsets[old_buf_idx] if old_buf_idx < len(buffer_offsets) else 0
        bv['byteOffset'] = base_offset + old_offset

    # Single unified binary buffer for the GLB BIN chunk
    gltf_dict['buffers'] = [{'byteLength': len(combined_bin)}]

    # JSON Chunk (UTF-8, 4-byte space padded)
    json_bytes = json.dumps(gltf_dict, separators=(',', ':')).encode('utf-8')
    while len(json_bytes) % 4 != 0:
        json_bytes += b' '

    # Align binary chunk to 4 bytes
    while len(combined_bin) % 4 != 0:
        combined_bin.append(0)

    total_len = 12 + (8 + len(json_bytes)) + (8 + len(combined_bin))

    # Header: Magic b'glTF' (0x46546C67), Version 2, Total Length
    header = struct.pack('<4sII', b'glTF', 2, total_len)
    json_chunk = struct.pack('<I4s', len(json_bytes), b'JSON') + json_bytes
    bin_chunk = struct.pack('<I4s', len(combined_bin), b'BIN\x00') + bytes(combined_bin)

    return header + json_chunk + bin_chunk


def generate_panel_glb(
    enclosure: Enclosure,
    instances: List[PhysicalInstance],
    din_rails: List[DINRail],
    wiring_ducts: List[WiringDuct],
    show_door: bool = True
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Renders 3D meshes for enclosure, mounting plate, door, DIN rails,
    wiring ducts, and placed electrical components.
    Exports to glTF, converts units from mm to meters (1:1 AR real scale),
    centers coordinates on the floor plane, and returns binary GLB bytes.
    """
    pl = pv.Plotter(off_screen=True)

    plate_w = enclosure.mounting_plate_width
    plate_h = enclosure.mounting_plate_height
    enc_w = enclosure.width
    enc_h = enclosure.height
    enc_d = enclosure.depth

    x_min = -enclosure.side_margin
    x_max = x_min + enc_w
    y_min = -enclosure.gland_plate_height
    y_max = y_min + enc_h
    z_min = -enclosure.plate_standoff
    z_max = z_min + enc_d

    wall_t = 2.0  # 2mm industrial sheet steel

    # 1. Back Mounting Plate (Galvanized zinc steel)
    plate_mesh = pv.Box(bounds=(0, plate_w, 0, plate_h, -3.0, 0.0))
    pl.add_mesh(plate_mesh, color="#94A3B8")

    # 2. Enclosure Outer Cabinet Walls (Sheet metal body)
    # Left wall
    pl.add_mesh(pv.Box(bounds=(x_min, x_min + wall_t, y_min, y_max, z_min, z_max)), color="#475569")
    # Right wall
    pl.add_mesh(pv.Box(bounds=(x_max - wall_t, x_max, y_min, y_max, z_min, z_max)), color="#475569")
    # Top roof
    pl.add_mesh(pv.Box(bounds=(x_min, x_max, y_max - wall_t, y_max, z_min, z_max)), color="#475569")
    # Bottom floor / gland plate
    pl.add_mesh(pv.Box(bounds=(x_min, x_max, y_min, y_min + wall_t, z_min, z_max)), color="#475569")
    # Back wall behind mounting plate
    pl.add_mesh(pv.Box(bounds=(x_min, x_max, y_min, y_max, z_min, z_min + wall_t)), color="#334155")

    # 3. Outer Door Sheet (Z+1 Surface)
    if show_door:
        is_double = (getattr(enclosure, "door_type", "SINGLE") == "DOUBLE_VERTICAL")
        if is_double:
            mid_x = (x_min + x_max) / 2.0
            left_leaf = pv.Box(bounds=(x_min, mid_x - 1.0, y_min, y_max, z_max - 2.0, z_max))
            right_leaf = pv.Box(bounds=(mid_x + 1.0, x_max, y_min, y_max, z_max - 2.0, z_max))
            pl.add_mesh(left_leaf, color="#94A3B8", opacity=0.35)
            pl.add_mesh(right_leaf, color="#94A3B8", opacity=0.35)
        else:
            door_sheet = pv.Box(bounds=(x_min, x_max, y_min, y_max, z_max - 2.0, z_max))
            pl.add_mesh(door_sheet, color="#94A3B8", opacity=0.30)

    # 4. DIN Rails (DIN EN 60715 35mm profile on mounting plate)
    for rail in din_rails:
        y_3d = plate_h - rail.y - rail.height
        rail_mesh = pv.Box(bounds=(
            rail.x, rail.x + rail.length,
            y_3d, y_3d + rail.height,
            rail.z, rail.z + rail.depth
        ))
        pl.add_mesh(rail_mesh, color="#E2E8F0")

    # 5. Slotted Wiring Ducts (Trunking on mounting plate)
    for duct in wiring_ducts:
        is_vert = duct.orientation.upper() == "VERTICAL" or int(getattr(duct, "rotation", 0)) in (90, 270)
        duct_w = duct.width if is_vert else duct.length
        duct_h = duct.length if is_vert else (duct.height if 0 < duct.height <= 80 else 40.0)
        duct_d = duct.height if is_vert else (duct.width if 0 < duct.width <= 80 else 40.0)

        y_3d = plate_h - duct.y - duct_h
        duct_mesh = pv.Box(bounds=(
            duct.x, duct.x + duct_w,
            y_3d, y_3d + duct_h,
            duct.z, duct.z + duct_d
        ))
        duct_col = duct.color if duct.color else "#94A3B8"
        pl.add_mesh(duct_mesh, color=duct_col, opacity=0.85)

    # 6. Electrical Components (3D Cuboids on Mounting Plate Z and Door Z+1)
    placed_count = 0
    for inst in instances:
        if not inst.is_placed or inst.is_external:
            continue
        if any(k in inst.name.lower() for k in ["enclosure", "cabinet"]):
            continue
        if getattr(inst, "category", "").lower() in ["enclosure", "enclosures", "cabinet", "cabinets"]:
            continue
        if getattr(inst, "is_enclosure", False):
            continue

        eff_w = inst.height if int(inst.rotation) in (90, 270) else inst.width
        eff_h = inst.width if int(inst.rotation) in (90, 270) else inst.height
        is_door_item = (getattr(inst, "surface", "Z").upper() == "Z+1")

        if is_door_item:
            x_3d = x_min + inst.x
            y_3d = y_min + (enc_h - inst.y - eff_h)
            z_comp_min = z_max - min(inst.depth * 0.7, 45.0)
            z_comp_max = z_max + max(6.0, inst.depth * 0.3)
            comp_mesh = pv.Box(bounds=(
                x_3d, x_3d + eff_w,
                y_3d, y_3d + eff_h,
                z_comp_min, z_comp_max
            ))
        else:
            y_3d = plate_h - inst.y - eff_h
            comp_mesh = pv.Box(bounds=(
                inst.x, inst.x + eff_w,
                y_3d, y_3d + eff_h,
                inst.z, inst.z + inst.depth
            ))

        color = inst.color if inst.color else "#FF9A4E"
        pl.add_mesh(comp_mesh, color=color, opacity=0.98)
        placed_count += 1

    # Export glTF to temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".gltf")
    os.close(temp_fd)

    try:
        pl.export_gltf(temp_path)
        with open(temp_path, "r", encoding="utf-8") as f:
            gltf_dict = json.load(f)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # Ensure transparent materials have alphaMode = BLEND and doubleSided = True
    for mat in gltf_dict.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        color_factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
        if len(color_factor) >= 4 and color_factor[3] < 0.99:
            mat["alphaMode"] = "BLEND"
            mat["doubleSided"] = True

    # Real-World AR 1:1 Scale & Floor-Level Alignment
    # Scale: 0.001 (1 mm = 0.001 m)
    # Origin: Centered horizontally (X), grounded on floor (Y starting at 0), centered depth (Z)
    x_center = (x_min + x_max) / 2.0
    y_floor = y_min
    z_center = (z_min + z_max) / 2.0

    all_scenes = gltf_dict.get("scenes", [])
    all_root_children = []
    for s in all_scenes:
        all_root_children.extend(s.get("nodes", []))

    root_idx = len(gltf_dict.get("nodes", []))
    gltf_dict.setdefault("nodes", []).append({
        "name": "AR_Root_Centered_Scaled",
        "translation": [-x_center * 0.001, -y_floor * 0.001, -z_center * 0.001],
        "scale": [0.001, 0.001, 0.001],
        "children": all_root_children
    })

    for s in all_scenes:
        s["nodes"] = [root_idx]

    glb_bytes = gltf_to_glb(gltf_dict)

    metadata = {
        "width_mm": enc_w,
        "height_mm": enc_h,
        "depth_mm": enc_d,
        "ip_rating": enclosure.ip_rating,
        "door_type": getattr(enclosure, "door_type", "SINGLE"),
        "component_count": placed_count,
        "glb_size_bytes": len(glb_bytes)
    }

    return glb_bytes, metadata


def generate_qr_png_bytes(url: str) -> bytes:
    """Generate PNG bytes of QR code pointing to URL."""
    import qrcode
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111C24", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_webar_html(metadata: Dict[str, Any], url: str) -> str:
    """Construct high-performance, mobile-responsive WebAR HTML interface."""
    w = int(metadata.get("width_mm", 800))
    h = int(metadata.get("height_mm", 1200))
    d = int(metadata.get("depth_mm", 400))
    ip = metadata.get("ip_rating", "IP54")
    count = metadata.get("component_count", 0)

    # Convert to meters string for real AR display
    w_m = f"{w / 1000.0:.2f} m"
    h_m = f"{h / 1000.0:.2f} m"
    d_m = f"{d / 1000.0:.2f} m"

    glb_url = f"{url}/model.glb"
    scene_viewer_intent = (
        f"intent://arvr.google.com/scene-viewer/1.0?"
        f"file={glb_url}&mode=ar_preferred&title=Electrical+Panel+{w}x{h}x{d}mm&resizable=false"
        f"#Intent;scheme=https;package=com.google.ar.core;action=android.intent.action.VIEW;"
        f"S.browser_fallback_url={url};end;"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AR Panel Inspection - ElectricalPanelDesigner</title>
    <!-- Google @model-viewer for WebXR, Android Scene Viewer & iOS Quick Look -->
    <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        body {{
            background: #111C24;
            color: #FFFFFF;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        header {{
            background: #1A2730;
            padding: 12px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1.5px solid #2A3945;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            z-index: 10;
        }}
        .brand {{
            font-size: 15px;
            font-weight: 800;
            letter-spacing: 0.4px;
            color: #FFFFFF;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .badge {{
            background: #FF9A4E;
            color: #111C24;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .viewer-container {{
            flex: 1;
            position: relative;
            background: radial-gradient(circle at 50% 40%, #1e2c38 0%, #0d151c 100%);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        model-viewer {{
            width: 100%;
            height: 100%;
            outline: none;
        }}
        #ar-button {{
            background: #FF9A4E;
            color: #111C24;
            border: none;
            border-radius: 28px;
            padding: 14px 28px;
            font-size: 15px;
            font-weight: 800;
            position: absolute;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            box-shadow: 0 4px 20px rgba(255, 154, 78, 0.45);
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            z-index: 20;
            white-space: nowrap;
            transition: transform 0.15s, background-color 0.15s;
        }}
        #ar-button:active {{
            background: #F08738;
            transform: translateX(-50%) scale(0.97);
        }}
        .ar-icon {{
            width: 22px;
            height: 22px;
            fill: none;
            stroke: #111C24;
            stroke-width: 2.3;
        }}
        .info-panel {{
            background: #1A2730;
            border-top: 1.5px solid #2A3945;
            padding: 12px 18px;
            font-size: 12px;
            color: #8A8C8D;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 10;
        }}
        .info-pill {{
            color: #E2E8F0;
            font-weight: 700;
            font-size: 13px;
        }}
        .sub-bar {{
            background: #141E26;
            padding: 8px 18px;
            font-size: 11px;
            color: #64748B;
            text-align: center;
            display: flex;
            justify-content: center;
            gap: 16px;
        }}
        .sub-bar a {{
            color: #38BDF8;
            text-decoration: none;
            font-weight: 600;
        }}
        .scale-alert {{
            position: absolute;
            top: 14px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(17, 28, 36, 0.85);
            backdrop-filter: blur(6px);
            border: 1px solid #38BDF8;
            color: #E2E8F0;
            font-size: 11px;
            padding: 6px 14px;
            border-radius: 20px;
            pointer-events: none;
            z-index: 15;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FF9A4E" stroke-width="2.5"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            Electrical Panel AR
        </div>
        <div class="badge">1:1 Actual Scale</div>
    </header>

    <div class="viewer-container">
        <div class="scale-alert">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#38BDF8" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            Actual 1:1 Scale ({w_m} × {h_m} × {d_m})
        </div>

        <model-viewer
            id="panel-viewer"
            src="/model.glb"
            alt="Electrical Panel 3D Model"
            ar
            ar-modes="scene-viewer webxr quick-look"
            ar-scale="fixed"
            camera-controls
            touch-action="pan-y"
            auto-rotate
            auto-rotate-delay="1500"
            rotation-per-second="18deg"
            shadow-intensity="1.2"
            shadow-softness="0.7"
            exposure="1.0">

            <button slot="ar-button" id="ar-button">
                <svg class="ar-icon" viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
                View in AR (Actual Size)
            </button>
        </model-viewer>
    </div>

    <div class="info-panel">
        <div>Size: <span class="info-pill">{w} × {h} × {d} mm</span> ({ip})</div>
        <div>Components: <span class="info-pill">{count} Placed</span></div>
    </div>

    <div class="sub-bar">
        <span>Point camera at floor or wall to anchor</span>
        <a href="{scene_viewer_intent}">Direct Android AR</a>
        <a href="/model.glb" download>Download .GLB</a>
    </div>
</body>
</html>"""


class ARRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handles HTTP requests for WebAR HTML, GLB model, QR image, and status."""

    def log_message(self, format, *args):
        # Quiet logger to avoid terminal clutter
        pass

    def do_GET(self):
        server: "ARServer" = self.server.ar_server  # type: ignore

        if self.path == "/" or self.path.startswith("/index"):
            html = get_webar_html(server.panel_metadata, server.base_url)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/model.glb"):
            glb_data = server.glb_data
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(len(glb_data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(glb_data)

        elif self.path.startswith("/qr"):
            qr_bytes = generate_qr_png_bytes(server.base_url)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(qr_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(qr_bytes)

        elif self.path.startswith("/status"):
            st = json.dumps(server.panel_metadata).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(st)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(st)

        else:
            self.send_response(404)
            self.end_headers()


class ARServer:
    """Singleton background HTTP server for serving WebAR models to mobile devices."""

    def __init__(self, default_port: int = 8080):
        self.default_port = default_port
        self.actual_port = default_port
        self.local_ip = get_local_ip()
        self.base_url = f"http://{self.local_ip}:{self.actual_port}"

        self.httpd: Optional[socketserver.ThreadingTCPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running: bool = False

        self.glb_data: bytes = b""
        self.panel_metadata: Dict[str, Any] = {}

    def update_model(
        self,
        enclosure: Enclosure,
        instances: List[PhysicalInstance],
        din_rails: List[DINRail],
        wiring_ducts: List[WiringDuct],
        show_door: bool = True
    ) -> str:
        """Regenerates the 1:1 scaled GLB 3D model from current project data."""
        self.glb_data, self.panel_metadata = generate_panel_glb(
            enclosure, instances, din_rails, wiring_ducts, show_door=show_door
        )
        return self.base_url

    def start(self) -> str:
        """Starts the background AR HTTP server if not already running."""
        if self.is_running and self.httpd:
            return self.base_url

        self.local_ip = get_local_ip()
        self.actual_port = find_free_port(self.default_port)
        self.base_url = f"http://{self.local_ip}:{self.actual_port}"

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.httpd = socketserver.ThreadingTCPServer(("", self.actual_port), ARRequestHandler)
        self.httpd.ar_server = self  # type: ignore

        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.is_running = True

        return self.base_url

    def stop(self):
        """Stops the background HTTP server."""
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
        self.is_running = False


# Module-level singleton
_ar_server_instance: Optional[ARServer] = None


def get_ar_server() -> ARServer:
    global _ar_server_instance
    if _ar_server_instance is None:
        _ar_server_instance = ARServer()
    return _ar_server_instance
