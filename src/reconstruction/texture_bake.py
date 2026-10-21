r"""
Multi-View Texture Baking Pipeline
===================================
Projects original camera images onto the cleaned Poisson mesh using
COLMAP camera poses, UV unwrapping via xatlas, and weighted blending.

Input:  C:\recon\reconstruction_v2\mesh_final_vtxcolor.ply  (colored Poisson mesh)
        C:\recon\chunks\lab\sparse\0\cameras.bin            (COLMAP cameras)
        C:\recon\chunks\lab\sparse\0\images.bin             (COLMAP image poses)
        C:\recon\chunks\lab\images\                         (source RGB frames)

Output: C:\recon\reconstruction_v2\mesh_final.obj
        C:\recon\reconstruction_v2\mesh_final.mtl
        C:\recon\reconstruction_v2\texture_4096.png
"""

import open3d as o3d
import numpy as np
import struct
import os
import cv2
from PIL import Image
import xatlas
import time

OUT_DIR = r"C:\recon\reconstruction_v2"
MESH_PATH = os.path.join(OUT_DIR, "mesh_final_vtxcolor.ply")
COLMAP_DIR = r"C:\recon\chunks\lab\sparse\0"
IMAGES_DIR = r"C:\recon\chunks\lab\images"
TEX_SIZE = 4096
MAX_CAMERAS = 60  # Use a subset for speed; increase for quality

# ─────────────────────── COLMAP BINARY PARSERS ───────────────────────

def read_cameras_bin(path):
    """Parse COLMAP cameras.bin → dict of camera_id: {model, width, height, params}"""
    cameras = {}
    with open(path, 'rb') as f:
        num = struct.unpack('<Q', f.read(8))[0]
        for _ in range(num):
            cam_id = struct.unpack('<i', f.read(4))[0]
            model_id = struct.unpack('<i', f.read(4))[0]
            width = struct.unpack('<Q', f.read(8))[0]
            height = struct.unpack('<Q', f.read(8))[0]
            num_params = {0:3,1:4,2:4,3:5,4:8,5:8,6:12,7:5,8:4,9:5,10:12}[model_id]
            params = struct.unpack(f'<{num_params}d', f.read(8*num_params))
            cameras[cam_id] = {
                'model_id': model_id, 'width': width, 'height': height, 'params': params
            }
    return cameras

def read_images_bin(path):
    """Parse COLMAP images.bin → list of {image_id, qw,qx,qy,qz, tx,ty,tz, camera_id, name}"""
    images = []
    with open(path, 'rb') as f:
        num = struct.unpack('<Q', f.read(8))[0]
        for _ in range(num):
            image_id = struct.unpack('<i', f.read(4))[0]
            qw, qx, qy, qz = struct.unpack('<4d', f.read(32))
            tx, ty, tz = struct.unpack('<3d', f.read(24))
            camera_id = struct.unpack('<i', f.read(4))[0]
            # Read name (null-terminated)
            name_chars = []
            while True:
                c = f.read(1)
                if c == b'\x00':
                    break
                name_chars.append(c.decode('ascii'))
            name = ''.join(name_chars)
            # Read 2D points (skip them)
            num_points2D = struct.unpack('<Q', f.read(8))[0]
            f.read(num_points2D * 24)  # each point2D: x,y (2 doubles) + point3D_id (1 long)
            images.append({
                'image_id': image_id,
                'qvec': np.array([qw, qx, qy, qz]),
                'tvec': np.array([tx, ty, tz]),
                'camera_id': camera_id,
                'name': name
            })
    return images

def qvec2rotmat(qvec):
    """Convert quaternion to rotation matrix (COLMAP convention)."""
    w, x, y, z = qvec
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
        [2*x*y + 2*w*z, 1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
        [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x*x - 2*y*y]
    ])

def get_intrinsic_matrix(cam):
    """Build 3x3 intrinsic matrix from COLMAP camera params (OPENCV model)."""
    params = cam['params']
    if cam['model_id'] == 4:  # OPENCV
        fx, fy, cx, cy = params[0], params[1], params[2], params[3]
    elif cam['model_id'] == 1:  # PINHOLE
        fx, fy, cx, cy = params[0], params[1], params[2], params[3]
    elif cam['model_id'] == 0:  # SIMPLE_PINHOLE
        fx = fy = params[0]
        cx, cy = params[1], params[2]
    else:
        fx = fy = params[0]
        cx, cy = cam['width']/2, cam['height']/2
    return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])

# ─────────────────────── UV UNWRAP ───────────────────────

def unwrap_mesh(mesh):
    """UV unwrap using xatlas."""
    print("\n=== UV Unwrapping with xatlas ===")
    verts = np.asarray(mesh.vertices).astype(np.float32)
    tris = np.asarray(mesh.triangles).astype(np.uint32)

    t0 = time.time()
    atlas = xatlas.Atlas()
    atlas.add_mesh(verts, tris)
    atlas.generate()
    vmapping, new_indices, new_uvs = atlas[0]
    print(f"  UV unwrap done in {time.time()-t0:.1f}s")
    print(f"  New vertices: {len(vmapping)}, UV coords: {len(new_uvs)}")

    return vmapping, new_indices, new_uvs

# ─────────────────────── TEXTURE BAKING ───────────────────────

def bake_texture(mesh, cameras, images, vmapping, new_indices, new_uvs, tex_size):
    """Project camera images onto UV atlas to create texture map."""
    print(f"\n=== Texture Baking ({tex_size}x{tex_size}) ===")

    verts = np.asarray(mesh.vertices)
    # Map original vertex positions to new UV vertices
    mapped_verts = verts[vmapping]

    texture = np.zeros((tex_size, tex_size, 3), dtype=np.float64)
    weight_map = np.zeros((tex_size, tex_size), dtype=np.float64)

    # Select a subset of cameras for speed
    cam_subset = images[:MAX_CAMERAS]
    print(f"  Using {len(cam_subset)} of {len(images)} cameras")

    for idx, img_data in enumerate(cam_subset):
        cam = cameras[img_data['camera_id']]
        K = get_intrinsic_matrix(cam)
        R = qvec2rotmat(img_data['qvec'])
        t = img_data['tvec']

        # Load image
        img_path = os.path.join(IMAGES_DIR, img_data['name'])
        if not os.path.exists(img_path):
            continue

        img = cv2.imread(img_path)
        if img is None:
            continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0
        h_img, w_img = img.shape[:2]

        # Camera center in world coords
        cam_center = -R.T @ t

        # Project all vertices
        pts_cam = (R @ mapped_verts.T).T + t  # Nx3
        depth = pts_cam[:, 2]

        # Only keep points in front of camera
        valid = depth > 0.1

        # Project to 2D
        pts_2d = (K @ pts_cam.T).T
        pts_2d[:, 0] /= pts_2d[:, 2]
        pts_2d[:, 1] /= pts_2d[:, 2]
        u = pts_2d[:, 0]
        v = pts_2d[:, 1]

        # Check within image bounds
        valid &= (u >= 0) & (u < w_img - 1) & (v >= 0) & (v < h_img - 1)

        if valid.sum() == 0:
            continue

        # Viewing angle weighting
        if mesh.has_vertex_normals():
            normals = np.asarray(mesh.vertex_normals)[vmapping]
            view_dirs = cam_center - mapped_verts
            view_dirs /= (np.linalg.norm(view_dirs, axis=1, keepdims=True) + 1e-10)
            cos_angles = np.sum(normals * view_dirs, axis=1)
            angle_valid = cos_angles > 0.25  # reject grazing angles > ~75 deg
            valid &= angle_valid
            angle_weight = np.clip(cos_angles, 0, 1)
        else:
            angle_weight = np.ones(len(mapped_verts))

        # Distance weighting (prefer closer cameras)
        dists = np.linalg.norm(mapped_verts - cam_center, axis=1)
        dist_weight = 1.0 / (dists + 1e-6)

        combined_weight = angle_weight * dist_weight
        combined_weight[~valid] = 0

        # For each valid vertex, sample color from image and paint into UV space
        for vi in np.where(valid)[0]:
            iu = int(u[vi])
            iv = int(v[vi])
            color = img[iv, iu]
            w = combined_weight[vi]

            # UV of this vertex
            uv = new_uvs[vi]
            tx = int(uv[0] * (tex_size - 1))
            ty = int((1.0 - uv[1]) * (tex_size - 1))  # Flip Y
            tx = np.clip(tx, 0, tex_size - 1)
            ty = np.clip(ty, 0, tex_size - 1)

            texture[ty, tx] += color * w
            weight_map[ty, tx] += w

        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx+1}/{len(cam_subset)} cameras "
                  f"({valid.sum()} visible vertices)")

    # Normalize
    mask = weight_map > 0
    texture[mask] /= weight_map[mask, np.newaxis]

    # Fill holes with vertex colors
    if mesh.has_vertex_colors():
        print("  Filling unprojected texels with vertex colors...")
        vtx_colors = np.asarray(mesh.vertex_colors)[vmapping]
        for vi in range(len(new_uvs)):
            uv = new_uvs[vi]
            tx = int(uv[0] * (tex_size - 1))
            ty = int((1.0 - uv[1]) * (tex_size - 1))
            tx = np.clip(tx, 0, tex_size - 1)
            ty = np.clip(ty, 0, tex_size - 1)
            if weight_map[ty, tx] == 0:
                texture[ty, tx] = vtx_colors[vi]

    # Slight Gaussian blur to smooth seams
    texture_uint8 = np.clip(texture * 255, 0, 255).astype(np.uint8)
    texture_uint8 = cv2.GaussianBlur(texture_uint8, (3, 3), 0.5)

    return texture_uint8, new_indices, new_uvs, mapped_verts

# ─────────────────────── EXPORT OBJ ───────────────────────

def export_obj(verts, faces, uvs, tex_filename, out_dir):
    """Write mesh_final.obj + mesh_final.mtl."""
    obj_path = os.path.join(out_dir, "mesh_final.obj")
    mtl_path = os.path.join(out_dir, "mesh_final.mtl")

    print(f"\n=== Exporting OBJ ===")

    # MTL
    with open(mtl_path, 'w') as f:
        f.write("# Mesh Final Material\n")
        f.write("newmtl textured\n")
        f.write("Ka 1.0 1.0 1.0\n")
        f.write("Kd 1.0 1.0 1.0\n")
        f.write("Ks 0.0 0.0 0.0\n")
        f.write("d 1.0\n")
        f.write(f"map_Kd {tex_filename}\n")

    # OBJ
    with open(obj_path, 'w') as f:
        f.write(f"# Mesh Final - Textured Reconstruction\n")
        f.write(f"mtllib mesh_final.mtl\n")
        f.write(f"usemtl textured\n\n")
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for uv in uvs:
            f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")
        for face in faces:
            f1, f2, f3 = face[0]+1, face[1]+1, face[2]+1
            f.write(f"f {f1}/{f1} {f2}/{f2} {f3}/{f3}\n")

    print(f"  Saved: {obj_path}")
    print(f"  Saved: {mtl_path}")

# ─────────────────────── MAIN ───────────────────────

def main():
    print("=" * 60)
    print("MULTI-VIEW TEXTURE BAKING PIPELINE")
    print("=" * 60)

    # Load mesh
    print("Loading mesh...")
    mesh = o3d.io.read_triangle_mesh(MESH_PATH)
    mesh.compute_vertex_normals()
    print(f"  {len(mesh.vertices):,} vertices, {len(mesh.triangles):,} faces")

    # Load COLMAP data
    print("\nParsing COLMAP cameras...")
    cameras = read_cameras_bin(os.path.join(COLMAP_DIR, "cameras.bin"))
    print(f"  {len(cameras)} camera(s)")

    print("Parsing COLMAP images...")
    images = read_images_bin(os.path.join(COLMAP_DIR, "images.bin"))
    print(f"  {len(images)} registered images")

    # UV unwrap
    vmapping, new_indices, new_uvs = unwrap_mesh(mesh)

    # Texture baking
    texture, faces, uvs, verts = bake_texture(
        mesh, cameras, images, vmapping, new_indices, new_uvs, TEX_SIZE
    )

    # Save texture
    tex_path = os.path.join(OUT_DIR, "texture_4096.png")
    Image.fromarray(texture).save(tex_path)
    print(f"\n  Saved texture: {tex_path} ({os.path.getsize(tex_path):,} bytes)")

    # Export OBJ
    export_obj(verts, faces, uvs, "texture_4096.png", OUT_DIR)

    # Also save as PLY with vertex colors for quick viewing
    print("\nDone! Texture baking complete.")

if __name__ == "__main__":
    main()
