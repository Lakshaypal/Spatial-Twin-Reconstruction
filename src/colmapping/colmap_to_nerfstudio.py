"""
Convert COLMAP sparse model (binary) to nerfstudio transforms.json.
Reads from dense/sparse/ (the undistorted model) and writes transforms.json
pointing at dense/images/.
"""
import json, struct, sys, os, numpy as np
from pathlib import Path

ROOT = Path(__file__).parent
SPARSE = ROOT / "dense" / "sparse"
IMAGES_DIR = ROOT / "dense" / "images"

# ── read cameras.bin ──────────────────────────────────────────────────
def read_cameras_bin(path):
    cameras = {}
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            cam_id = struct.unpack("<i", f.read(4))[0]
            model  = struct.unpack("<i", f.read(4))[0]
            w      = struct.unpack("<Q", f.read(8))[0]
            h      = struct.unpack("<Q", f.read(8))[0]
            # PINHOLE has 4 params: fx, fy, cx, cy
            num_params = {0:3, 1:4, 2:4, 3:5, 4:4, 5:5, 6:4, 7:5, 8:12, 9:8, 10:5}
            np_ = num_params.get(model, 4)
            params = struct.unpack(f"<{np_}d", f.read(8*np_))
            cameras[cam_id] = {"model": model, "w": w, "h": h, "params": params}
    return cameras

# ── read images.bin ───────────────────────────────────────────────────
def read_images_bin(path):
    images = {}
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            img_id = struct.unpack("<i", f.read(4))[0]
            qw, qx, qy, qz = struct.unpack("<4d", f.read(32))
            tx, ty, tz      = struct.unpack("<3d", f.read(24))
            cam_id          = struct.unpack("<i", f.read(4))[0]
            # name is null-terminated
            name = b""
            while True:
                c = f.read(1)
                if c == b"\x00":
                    break
                name += c
            name = name.decode("utf-8")
            # skip 2D points
            num_pts = struct.unpack("<Q", f.read(8))[0]
            f.read(num_pts * 24)  # x, y, pt3d_id  (8+8+8)
            images[img_id] = {
                "name": name,
                "cam_id": cam_id,
                "qvec": [qw, qx, qy, qz],
                "tvec": [tx, ty, tz],
            }
    return images

# ── quaternion to rotation matrix ─────────────────────────────────────
def qvec2rotmat(qvec):
    w, x, y, z = qvec
    return np.array([
        [1 - 2*y*y - 2*z*z,   2*x*y - 2*w*z,       2*x*z + 2*w*y],
        [2*x*y + 2*w*z,       1 - 2*x*x - 2*z*z,   2*y*z - 2*w*x],
        [2*x*z - 2*w*y,       2*y*z + 2*w*x,       1 - 2*x*x - 2*y*y],
    ])

# ── main ──────────────────────────────────────────────────────────────
cameras = read_cameras_bin(SPARSE / "cameras.bin")
images  = read_images_bin(SPARSE / "images.bin")

print(f"Cameras: {len(cameras)}, Images: {len(images)}")

# assume single camera
cam = list(cameras.values())[0]
fx, fy, cx, cy = cam["params"][:4]
w, h = cam["w"], cam["h"]

frames = []
for img_id in sorted(images):
    img = images[img_id]
    R = qvec2rotmat(img["qvec"])
    t = np.array(img["tvec"])
    # world-to-camera  →  camera-to-world
    R_inv = R.T
    t_inv = -R.T @ t
    # build 4×4
    c2w = np.eye(4)
    c2w[:3, :3] = R_inv
    c2w[:3,  3] = t_inv
    # nerfstudio uses OpenGL convention (flip y and z)
    c2w[:, 1] *= -1
    c2w[:, 2] *= -1
    frames.append({
        "file_path": f"images/{img['name']}",
        "transform_matrix": c2w.tolist(),
    })

out = {
    "camera_model": "OPENCV",
    "fl_x": fx,
    "fl_y": fy,
    "cx": cx,
    "cy": cy,
    "w": int(w),
    "h": int(h),
    "k1": 0.0,
    "k2": 0.0,
    "p1": 0.0,
    "p2": 0.0,
    "frames": frames,
}

out_path = ROOT / "dense" / "transforms.json"
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)

print(f"Wrote {len(frames)} frames to {out_path}")
