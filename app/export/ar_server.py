"""
Augmented Reality (AR) Web Server & 3D GLB/glTF Exporter for Electrical Enclosures.
Enables instant 1:1 physical scale AR viewing on mobile devices (Android & iOS).
- Exports CAD layout (mm) to glTF/GLB with 0.001 scale conversion (meters for real-world AR).
- Serves interactive WebAR page powered by Google @model-viewer with on-screen visual guidance (Amazon-style).
- Includes built-in Live Camera AR overlay mode and in-browser WebXR (no crashing external Scene Viewer app).
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

        while len(combined_bin) % 4 != 0:
            combined_bin.append(0)

        offset = len(combined_bin)
        buffer_offsets.append(offset)
        combined_bin.extend(raw_bytes)

    for bv in gltf_dict.get('bufferViews', []):
        old_buf_idx = bv.get('buffer', 0)
        old_offset = bv.get('byteOffset', 0)
        bv['buffer'] = 0
        base_offset = buffer_offsets[old_buf_idx] if old_buf_idx < len(buffer_offsets) else 0
        bv['byteOffset'] = base_offset + old_offset

    gltf_dict['buffers'] = [{'byteLength': len(combined_bin)}]

    json_bytes = json.dumps(gltf_dict, separators=(',', ':')).encode('utf-8')
    while len(json_bytes) % 4 != 0:
        json_bytes += b' '

    while len(combined_bin) % 4 != 0:
        combined_bin.append(0)

    total_len = 12 + (8 + len(json_bytes)) + (8 + len(combined_bin))

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
    pl.add_mesh(pv.Box(bounds=(x_min, x_min + wall_t, y_min, y_max, z_min, z_max)), color="#475569")
    pl.add_mesh(pv.Box(bounds=(x_max - wall_t, x_max, y_min, y_max, z_min, z_max)), color="#475569")
    pl.add_mesh(pv.Box(bounds=(x_min, x_max, y_max - wall_t, y_max, z_min, z_max)), color="#475569")
    pl.add_mesh(pv.Box(bounds=(x_min, x_max, y_min, y_min + wall_t, z_min, z_max)), color="#475569")
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

    for mat in gltf_dict.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        color_factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
        if len(color_factor) >= 4 and color_factor[3] < 0.99:
            mat["alphaMode"] = "BLEND"
            mat["doubleSided"] = True

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
    """Construct high-performance, mobile-responsive WebAR HTML interface with Amazon-style on-screen guiding."""
    w = int(metadata.get("width_mm", 800))
    h = int(metadata.get("height_mm", 1200))
    d = int(metadata.get("depth_mm", 400))
    ip = metadata.get("ip_rating", "IP54")
    count = metadata.get("component_count", 0)

    w_m = f"{w / 1000.0:.2f} m"
    h_m = f"{h / 1000.0:.2f} m"
    d_m = f"{d / 1000.0:.2f} m"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AR Panel Inspection - ElectricalPanelDesigner</title>
    <!-- Google @model-viewer: Strict WebXR and Quick Look (Scene Viewer removed to prevent app crashes) -->
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
            position: relative;
        }}
        header {{
            background: #1A2730;
            padding: 10px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1.5px solid #2A3945;
            z-index: 20;
        }}
        .brand {{
            font-size: 15px;
            font-weight: 800;
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
        }}
        .viewer-container {{
            flex: 1;
            position: relative;
            background: #111C24;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}
        #camera-video {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: none;
            z-index: 1;
        }}
        model-viewer {{
            width: 100%;
            height: 100%;
            outline: none;
            position: relative;
            z-index: 2;
            --poster-color: transparent;
        }}

        /* On-Screen Amazon-Style AR HUD Overlay */
        .ar-overlay-hud {{
            position: absolute;
            inset: 0;
            pointer-events: none;
            z-index: 30;
            display: none;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            padding: 20px 16px;
        }}
        .hud-card {{
            background: rgba(17, 28, 36, 0.90);
            backdrop-filter: blur(10px);
            border: 1.5px solid #38BDF8;
            border-radius: 16px;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            max-width: 90%;
            animation: fadeInDown 0.3s ease;
        }}
        @keyframes fadeInDown {{
            from {{ opacity: 0; transform: translateY(-15px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .phone-scanner {{
            width: 32px;
            height: 32px;
            animation: wavePhone 2s infinite ease-in-out;
        }}
        @keyframes wavePhone {{
            0%, 100% {{ transform: rotate(-15deg) translateX(-6px); }}
            50% {{ transform: rotate(15deg) translateX(6px); }}
        }}
        .hud-title {{
            font-size: 14px;
            font-weight: 800;
            color: #38BDF8;
        }}
        .hud-sub {{
            font-size: 11px;
            color: #CBD5E1;
            margin-top: 2px;
        }}

        /* Reticle Guide in Center of Camera */
        .reticle-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            animation: pulseReticle 2s infinite ease-in-out;
        }}
        @keyframes pulseReticle {{
            0%, 100% {{ transform: scale(0.95); opacity: 0.8; }}
            50% {{ transform: scale(1.08); opacity: 1; }}
        }}
        .reticle-ring {{
            width: 80px;
            height: 80px;
            border: 3px dashed #FF9A4E;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 154, 78, 0.15);
        }}
        .reticle-text {{
            background: rgba(17, 28, 36, 0.85);
            color: #FF9A4E;
            font-size: 12px;
            font-weight: 800;
            padding: 4px 12px;
            border-radius: 20px;
            border: 1px solid #FF9A4E;
        }}

        /* Placed Notification */
        .placed-hud {{
            background: rgba(22, 101, 52, 0.92);
            border: 1.5px solid #4ADE80;
            border-radius: 14px;
            padding: 10px 18px;
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 700;
            display: none;
            align-items: center;
            gap: 8px;
        }}

        /* Action Buttons Area */
        .action-dock {{
            position: absolute;
            bottom: 20px;
            left: 0;
            right: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            z-index: 25;
            padding: 0 16px;
        }}
        .btn-primary-ar {{
            background: #FF9A4E;
            color: #111C24;
            border: none;
            border-radius: 30px;
            padding: 14px 26px;
            font-size: 15px;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(255, 154, 78, 0.5);
            transition: transform 0.1s;
        }}
        .btn-primary-ar:active {{
            transform: scale(0.96);
        }}
        .btn-camera-live {{
            background: #0284C7;
            color: #FFFFFF;
            border: none;
            border-radius: 20px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(2, 132, 199, 0.4);
        }}

        /* Instructions Drawer */
        .guide-steps {{
            background: rgba(26, 39, 48, 0.95);
            border: 1px solid #2A3945;
            border-radius: 12px;
            padding: 10px 14px;
            display: flex;
            gap: 12px;
            font-size: 11px;
            color: #CBD5E1;
            max-width: 440px;
            width: 100%;
            justify-content: space-around;
        }}
        .step-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .step-num {{
            background: #FF9A4E;
            color: #111C24;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 10px;
        }}
        .info-panel {{
            background: #1A2730;
            border-top: 1.5px solid #2A3945;
            padding: 10px 16px;
            font-size: 12px;
            color: #8A8C8D;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 20;
        }}
        .info-pill {{
            color: #E2E8F0;
            font-weight: 700;
        }}
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FF9A4E" stroke-width="2.5"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            Electrical Panel AR
        </div>
        <div class="badge">1:1 Scale</div>
    </header>

    <div class="viewer-container">
        <!-- Live Camera Stream Background (For Live Camera Mode) -->
        <video id="camera-video" autoplay playsinline muted></video>

        <!-- 3D Model Viewer with Strict WebXR (Scene Viewer omitted to prevent crashes) -->
        <model-viewer
            id="panel-viewer"
            src="/model.glb"
            alt="Electrical Panel 3D Model"
            ar
            ar-modes="webxr quick-look"
            ar-scale="fixed"
            camera-controls
            touch-action="pan-y"
            auto-rotate
            auto-rotate-delay="1500"
            rotation-per-second="18deg"
            shadow-intensity="1.2"
            shadow-softness="0.7"
            exposure="1.0">

            <!-- Slot AR Button used by WebXR -->
            <button slot="ar-button" id="webxr-ar-btn" style="display: none;"></button>
        </model-viewer>

        <!-- On-Screen Amazon-Style AR Guidance HUD -->
        <div id="ar-hud" class="ar-overlay-hud">
            <!-- Step 1: Scanning Prompt -->
            <div id="hud-scanning" class="hud-card">
                <svg class="phone-scanner" viewBox="0 0 24 24" fill="none" stroke="#38BDF8" stroke-width="2.2"><rect x="5" y="2" width="14" height="20" rx="3"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>
                <div>
                    <div class="hud-title">Scanning Floor / Surface</div>
                    <div class="hud-sub">Move phone slowly in a circle pointing at floor</div>
                </div>
            </div>

            <!-- Center Target Reticle -->
            <div id="hud-reticle" class="reticle-container">
                <div class="reticle-ring">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#FF9A4E" stroke-width="2.2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
                </div>
                <div class="reticle-text">Tap anywhere to place 1:1 Panel</div>
            </div>

            <!-- Placed Confirmation -->
            <div id="hud-placed" class="placed-hud">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>Panel Anchored! Walk around to inspect</span>
            </div>
        </div>

        <!-- Floating Action Dock -->
        <div id="action-dock" class="action-dock">
            <button id="btn-camera-toggle" class="btn-primary-ar" onclick="toggleCameraOverlay()">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#111C24" stroke-width="2.3"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>
                <span id="cam-btn-text">📷 Open Live Room Camera (Instant AR)</span>
            </button>

            <!-- Optional WebXR button -->
            <button id="main-ar-trigger" class="btn-camera-live" onclick="launchAR()">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
                <span>Floor Surface Tracking (WebXR)</span>
            </button>
        </div>

        <!-- Floating Camera HUD Notification -->
        <div id="camera-hud" style="display: none; position: absolute; top: 16px; left: 16px; right: 16px; background: rgba(17, 28, 36, 0.92); border: 1.5px solid #38BDF8; border-radius: 12px; padding: 10px 14px; z-index: 35; align-items: center; justify-content: space-between; font-size: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.6);">
            <div>
                <b style="color: #38BDF8;">📷 Room Camera Active!</b>
                <div style="color: #CBD5E1; font-size: 11px;">Drag panel with 1 finger • Use 2 fingers to rotate & zoom</div>
            </div>
            <button onclick="resetModelView()" style="background: #0284C7; color: white; border: none; padding: 5px 10px; border-radius: 6px; font-weight: 700; font-size: 11px;">Reset View</button>
        </div>
    </div>

    <div class="info-panel">
        <div>Size: <span class="info-pill">{w} × {h} × {d} mm</span> ({ip})</div>
        <div>Scale: <span class="info-pill">{w_m} × {h_m} × {d_m}</span></div>
    </div>

    <script>
        const viewer = document.getElementById('panel-viewer');
        const hud = document.getElementById('ar-hud');
        const hudScanning = document.getElementById('hud-scanning');
        const hudReticle = document.getElementById('hud-reticle');
        const hudPlaced = document.getElementById('hud-placed');
        const cameraHud = document.getElementById('camera-hud');
        const actionDock = document.getElementById('action-dock');
        const video = document.getElementById('camera-video');
        let cameraActive = false;
        let camStream = null;

        viewer.addEventListener('ar-status', (event) => {{
            const status = event.detail.status;
            if (status === 'session-started') {{
                hud.style.display = 'flex';
                hudScanning.style.display = 'flex';
                hudReticle.style.display = 'flex';
                hudPlaced.style.display = 'none';
                actionDock.style.display = 'none';
            }} else if (status === 'object-placed') {{
                hudScanning.style.display = 'none';
                hudReticle.style.display = 'none';
                hudPlaced.style.display = 'flex';
                setTimeout(() => {{ hudPlaced.style.display = 'none'; }}, 4000);
            }} else if (status === 'not-presenting' || status === 'failed') {{
                hud.style.display = 'none';
                actionDock.style.display = 'flex';
            }}
        }});

        function launchAR() {{
            if (viewer.canActivateAR) {{
                viewer.activateAR();
            }} else {{
                toggleCameraOverlay();
            }}
        }}

        function resetModelView() {{
            viewer.cameraOrbit = '0deg 75deg 105%';
            viewer.resetTurntableRotation();
        }}

        async function toggleCameraOverlay() {{
            if (!cameraActive) {{
                try {{
                    camStream = await navigator.mediaDevices.getUserMedia({{
                        video: {{ facingMode: {{ ideal: 'environment' }} }}
                    }});
                    video.srcObject = camStream;
                    video.style.display = 'block';
                    await video.play();
                    document.querySelector('.viewer-container').style.background = 'transparent';
                    viewer.style.background = 'transparent';
                    cameraActive = true;
                    document.getElementById('cam-btn-text').innerText = '✕ Close Room Camera View';
                    cameraHud.style.display = 'flex';
                }} catch (err) {{
                    alert('Camera access error: ' + err.message + '\\nPlease ensure camera permission is granted in browser.');
                }}
            }} else {{
                if (camStream) {{
                    camStream.getTracks().forEach(t => t.stop());
                }}
                video.style.display = 'none';
                document.querySelector('.viewer-container').style.background = '#111C24';
                viewer.style.background = '';
                cameraActive = false;
                document.getElementById('cam-btn-text').innerText = '📷 Open Live Room Camera (Instant AR)';
                cameraHud.style.display = 'none';
            }}
        }}
    </script>
</body>
</html>"""


class ARRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handles HTTP requests for WebAR HTML, GLB model, QR image, and status."""

    def log_message(self, format, *args):
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
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
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


_ar_server_instance: Optional[ARServer] = None


def get_ar_server() -> ARServer:
    global _ar_server_instance
    if _ar_server_instance is None:
        _ar_server_instance = ARServer()
    return _ar_server_instance
