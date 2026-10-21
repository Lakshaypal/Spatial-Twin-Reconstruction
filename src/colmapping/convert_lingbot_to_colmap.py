import os
import numpy as np
import cv2

def rotmat2qvec(R):
    Rxx, Ryx, Rzx, Rxy, Ryy, Rzy, Rxz, Ryz, Rzz = R.flat
    K = np.array([
        [Rxx - Ryy - Rzz, 0, 0, 0],
        [Ryx + Rxy, Ryy - Rxx - Rzz, 0, 0],
        [Rzx + Rxz, Rzy + Ryz, Rzz - Rxx - Ryy, 0],
        [Ryz - Rzy, Rzx - Rxz, Rxy - Ryx, Rxx + Ryy + Rzz]]) / 3.0
    eigvals, eigvecs = np.linalg.eigh(K)
    qstep = eigvecs[[3, 0, 1, 2], np.argmax(eigvals)]
    if qstep[0] < 0:
        qstep *= -1
    return qstep

npz_dir = r"lingbot_output\scenes"
out_dir = r"lingbot_colmap"
os.makedirs(os.path.join(out_dir, "sparse", "0"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)

cameras_path = os.path.join(out_dir, "sparse", "0", "cameras.txt")
images_path = os.path.join(out_dir, "sparse", "0", "images.txt")
points_path = os.path.join(out_dir, "sparse", "0", "points3D.txt")

camera_id = 1
fx, fy, cx, cy = 0, 0, 0, 0

images_lines = []
points_lines = []
point_id = 1

npz_files = sorted([f for f in os.listdir(npz_dir) if f.endswith('.npz') and f.startswith('frame_')])

for i, f in enumerate(npz_files):
    npz_path = os.path.join(npz_dir, f)
    data = np.load(npz_path)
    
    if i == 0:
        intrinsic = data['intrinsic']
        fx = intrinsic[0, 0]
        cx = intrinsic[0, 2]
        fy = intrinsic[1, 1]
        cy = intrinsic[1, 2]
        
    c2w = data['extrinsic'] # 3x4
    c2w_4x4 = np.eye(4)
    c2w_4x4[:3, :] = c2w
    
    w2c = np.linalg.inv(c2w_4x4)
    rot = w2c[:3, :3]
    t = w2c[:3, 3]
    q_w, q_x, q_y, q_z = rotmat2qvec(rot)
    
    # Image
    img_data = data['images']
    if img_data.dtype == np.float32 or img_data.dtype == np.float64:
        img_data = (img_data * 255).astype(np.uint8)
    
    img_data = np.transpose(img_data, (1, 2, 0)) # CHW -> HWC
    img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
    
    img_name = f"frame_{i:06d}.jpg"
    cv2.imwrite(os.path.join(out_dir, "images", img_name), img_bgr)
    
    image_id = i + 1
    # Note: no 2D point observations recorded since we don't do bundle adjustment
    line = f"{image_id} {q_w} {q_x} {q_y} {q_z} {t[0]} {t[1]} {t[2]} {camera_id} {img_name}\n\n"
    images_lines.append(line)
    
    # Unproject Depth to generate a point cloud
    depth = data['depth'].squeeze() # (H, W)
    H, W = depth.shape
    
    # Subsample depth heavily (e.g. sample 1 in every 10x10 grid)
    step = 10
    v, u = np.mgrid[0:H:step, 0:W:step]
    u = u.flatten()
    v = v.flatten()
    
    d = depth[v, u]
    valid = d > 0.1 # Filter out too close or zero depth
    u, v, d = u[valid], v[valid], d[valid]
    
    # Camera coords
    Zc = d
    Xc = (u - cx) * Zc / fx
    Yc = (v - cy) * Zc / fy
    
    pts_c = np.stack([Xc, Yc, Zc, np.ones_like(Zc)], axis=0) # 4 x N
    pts_w = (c2w_4x4 @ pts_c)[:3, :] # 3 x N
    
    colors = img_bgr[v, u] # BGR
    # to RGB
    colors = colors[:, ::-1]
    
    for j in range(pts_w.shape[1]):
        px, py, pz = pts_w[:, j]
        r, g, b = colors[j]
        # Format: POINT3D_ID X Y Z R G B ERROR TRACK[]
        points_lines.append(f"{point_id} {px:.4f} {py:.4f} {pz:.4f} {r} {g} {b} 0.0\n")
        point_id += 1

with open(cameras_path, "w") as f:
    f.write(f"{camera_id} PINHOLE 518 294 {fx} {fy} {cx} {cy}\n")

with open(images_path, "w") as f:
    f.writelines(images_lines)

with open(points_path, "w") as f:
    f.write("# 3D point list with one line of data per point:\n")
    f.writelines(points_lines)

print(f"Successfully converted {len(npz_files)} frames and {point_id-1} points to COLMAP format in {out_dir}")
