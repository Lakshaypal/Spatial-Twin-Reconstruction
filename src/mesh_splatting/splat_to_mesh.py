"""
Phase 2: Convert Gaussian Splat PLY → Opaque Mesh
Uses Open3D Poisson surface reconstruction on the Gaussian centers.
No C++ compiler required.
"""
import numpy as np
import open3d as o3d
from plyfile import PlyData
import os, sys, time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--splat', type=str, required=True, help="Path to splat.ply")
parser.add_argument('--out', type=str, required=True, help="Output directory")
args = parser.parse_args()

SPLAT_PATH = args.splat
OUT_DIR    = args.out
os.makedirs(OUT_DIR, exist_ok=True)

print("=" * 60)
print("Phase 2 — Gaussian Splat → Opaque Mesh")
print("=" * 60)

# ── 1. Load Gaussian splat PLY ─────────────────────────────────
print("\n[1/6] Loading Gaussian splat PLY …")
t0 = time.time()
ply = PlyData.read(SPLAT_PATH)
vtx = ply['vertex']
N = len(vtx)
print(f"       Loaded {N:,} Gaussians in {time.time()-t0:.1f}s")

# ── 2. Extract positions & colors ──────────────────────────────
print("[2/6] Extracting positions & colours …")
xyz = np.column_stack([vtx['x'], vtx['y'], vtx['z']]).astype(np.float64)

if 'f_dc_0' in vtx.data.dtype.names:
    C0 = 0.28209479177387814  # 1/(2*sqrt(pi))
    r = 0.5 + C0 * np.array(vtx['f_dc_0'], dtype=np.float64)
    g = 0.5 + C0 * np.array(vtx['f_dc_1'], dtype=np.float64)
    b = 0.5 + C0 * np.array(vtx['f_dc_2'], dtype=np.float64)
    rgb = np.clip(np.column_stack([r, g, b]), 0, 1)
    print("       Decoded colours from SH DC coefficients")
elif 'red' in vtx.data.dtype.names:
    rgb = np.column_stack([vtx['red'], vtx['green'], vtx['blue']]).astype(np.float64)
    if rgb.max() > 1.0:
        rgb /= 255.0
    print("       Read colours from red/green/blue channels")
else:
    rgb = np.ones((N, 3)) * 0.7
    print("       WARNING: No colour data found – using grey")

# ── 3. Build Open3D point cloud ────────────────────────────────
print("[3/6] Building Open3D point cloud …")
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(xyz)
pcd.colors = o3d.utility.Vector3dVector(rgb)

# ── 3a. Statistical outlier removal ────────────────────────────
print("       Removing statistical outliers …")
pcd_clean, inlier_idx = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
print(f"       Kept {len(inlier_idx):,} / {N:,} points ({100*len(inlier_idx)/N:.1f}%)")

# ── 3b. Downsample if too many points (VRAM / RAM guard) ──────
MAX_PTS = 500_000
if len(pcd_clean.points) > MAX_PTS:
    voxel_size = pcd_clean.get_axis_aligned_bounding_box().get_extent().max() / 300
    pcd_clean = pcd_clean.voxel_down_sample(voxel_size)
    print(f"       Downsampled to {len(pcd_clean.points):,} points (voxel={voxel_size:.4f})")

# ── 4. Estimate normals ────────────────────────────────────────
print("[4/6] Estimating normals …")
pcd_clean.estimate_normals(
    search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
)
pcd_clean.orient_normals_consistent_tangent_plane(k=15)
print(f"       Normals estimated for {len(pcd_clean.points):,} points")

pcd_path = os.path.join(OUT_DIR, "pointcloud_clean.ply")
o3d.io.write_point_cloud(pcd_path, pcd_clean)
print(f"       Saved cleaned point cloud → {pcd_path}")

# ── 5. Poisson surface reconstruction ──────────────────────────
print("[5/6] Running Poisson surface reconstruction (depth=9) …")
t1 = time.time()
mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
    pcd_clean, depth=9, width=0, scale=1.1, linear_fit=False
)
print(f"       Poisson done in {time.time()-t1:.1f}s")
print(f"       Raw mesh: {len(mesh.vertices):,} vertices, {len(mesh.triangles):,} faces")

densities_np = np.asarray(densities)
density_thresh = np.quantile(densities_np, 0.02)
vertices_to_remove = densities_np < density_thresh
mesh.remove_vertices_by_mask(vertices_to_remove)
print(f"       After density trimming: {len(mesh.vertices):,} vertices, {len(mesh.triangles):,} faces")

mesh.compute_vertex_normals()

# ── 6. Save outputs ────────────────────────────────────────────
print("[6/6] Saving mesh …")

ply_out = os.path.join(OUT_DIR, "room_mesh.ply")
obj_out = os.path.join(OUT_DIR, "room_mesh.obj")

o3d.io.write_triangle_mesh(ply_out, mesh, write_vertex_colors=True)
o3d.io.write_triangle_mesh(obj_out, mesh, write_vertex_colors=True)

print(f"\n✅ Mesh saved:")
print(f"   PLY → {ply_out}")
print(f"   OBJ → {obj_out}")
print(f"   Vertices: {len(mesh.vertices):,}")
print(f"   Faces:    {len(mesh.triangles):,}")
print(f"\nPhase 2 complete!")
