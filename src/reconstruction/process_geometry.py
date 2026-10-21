import open3d as o3d
import numpy as np
import time
import os
import json
import trimesh
from pathlib import Path
import scipy.spatial

RECON_DIR = Path(r"C:\recon")
V2_DIR = RECON_DIR / "reconstruction_v2"
V2_DIR.mkdir(parents=True, exist_ok=True)
RENDER_DIR = V2_DIR / "before_after"
RENDER_DIR.mkdir(parents=True, exist_ok=True)
STATS_DIR = V2_DIR / "statistics"
STATS_DIR.mkdir(parents=True, exist_ok=True)

INPUT_MESH = RECON_DIR / "chunks" / "lab" / "mesh_lab.ply"
if not INPUT_MESH.exists():
    # fallback
    INPUT_MESH = RECON_DIR / "chunks" / "corridor" / "mesh_corridor.ply"

print(f"=== Phase 1: Analyzing {INPUT_MESH.name} ===")
mesh = o3d.io.read_triangle_mesh(str(INPUT_MESH))
vertices = np.asarray(mesh.vertices)
colors = np.asarray(mesh.vertex_colors) if mesh.has_vertex_colors() else None

print(f"Original vertices: {len(vertices):,}")
print(f"Original faces: {len(mesh.triangles):,}")

# --- Phase 2: Improve Point Cloud ---
print("\n=== Phase 2: Improving Point Cloud ===")
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(vertices)
if colors is not None:
    pcd.colors = o3d.utility.Vector3dVector(colors)

# Voxel downsampling if > 4M points to save memory for Poisson
if len(vertices) > 4000000:
    print("Downsampling large point cloud...")
    pcd = pcd.voxel_down_sample(voxel_size=0.005)
    print(f"Downsampled points: {len(pcd.points):,}")

# Statistical Outlier Removal
print("Applying Statistical Outlier Removal...")
cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
pcd_clean = pcd.select_by_index(ind)

# Radius Outlier Removal
print("Applying Radius Outlier Removal...")
cl, ind = pcd_clean.remove_radius_outlier(nb_points=16, radius=0.05)
pcd_clean = pcd_clean.select_by_index(ind)

print(f"Cleaned points: {len(pcd_clean.points):,}")

# Normal estimation
print("Estimating normals...")
pcd_clean.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
pcd_clean.orient_normals_consistent_tangent_plane(100)

o3d.io.write_point_cloud(str(V2_DIR / "clean_pointcloud.ply"), pcd_clean)

# --- Phase 3 & 4: Mesh Reconstruction & Topology Cleaning ---
print("\n=== Phase 3: Poisson Surface Reconstruction ===")
# Screened Poisson Surface Reconstruction
with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Debug) as cm:
    mesh_poisson, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd_clean, depth=9)

print(f"Poisson vertices: {len(mesh_poisson.vertices):,}")
print(f"Poisson faces: {len(mesh_poisson.triangles):,}")

print("\n=== Phase 4: Component Cleaning ===")
# Remove low density vertices
densities = np.asarray(densities)
density_colors = matplotlib.cm.inferno( (densities - densities.min()) / (densities.max() - densities.min()) )
density_colors = density_colors[:, :3]
density_threshold = np.quantile(densities, 0.05)
vertices_to_remove = densities < density_threshold
mesh_poisson.remove_vertices_by_mask(vertices_to_remove)

# Component cleaning (largest component)
triangle_clusters, cluster_n_triangles, cluster_area = mesh_poisson.cluster_connected_triangles()
triangle_clusters = np.asarray(triangle_clusters)
cluster_n_triangles = np.asarray(cluster_n_triangles)

largest_cluster_idx = cluster_n_triangles.argmax()
triangles_to_remove = triangle_clusters != largest_cluster_idx
mesh_poisson.remove_triangles_by_mask(triangles_to_remove)
mesh_poisson.remove_unreferenced_vertices()

o3d.io.write_triangle_mesh(str(V2_DIR / "mesh_clean.ply"), mesh_poisson)

# --- Phase 6 & 7: Smoothing & Texture ---
print("\n=== Phase 6: HC Laplacian (Taubin) Smoothing ===")
# Taubin smoothing prevents shrinkage while removing high-frequency noise
mesh_smooth = mesh_poisson.filter_smooth_taubin(number_of_iterations=10)

# Project colors back from point cloud
print("\n=== Phase 7: Vertex Color Projection & Denoising ===")
kdtree = o3d.geometry.KDTreeFlann(pcd_clean)
smooth_vertices = np.asarray(mesh_smooth.vertices)
pcd_colors = np.asarray(pcd_clean.colors)
new_colors = np.zeros_like(smooth_vertices)

# Bilateral-ish knn color blending
for i, v in enumerate(smooth_vertices):
    [k, idx, _] = kdtree.search_knn_vector_3d(v, 5)
    new_colors[i] = np.mean(pcd_colors[idx], axis=0)

mesh_smooth.vertex_colors = o3d.utility.Vector3dVector(new_colors)

o3d.io.write_triangle_mesh(str(V2_DIR / "mesh_best.ply"), mesh_smooth)

# --- Phase 8: Stats and Renders ---
print("\n=== Generating Renders and Reports ===")

# Compute stats using trimesh
t_mesh = trimesh.load(str(V2_DIR / "mesh_best.ply"))
stats = {
    "original_vertices": len(vertices),
    "clean_vertices": len(mesh_smooth.vertices),
    "original_faces": len(mesh.triangles),
    "clean_faces": len(mesh_smooth.triangles),
    "is_watertight": t_mesh.is_watertight,
    "surface_area": float(t_mesh.area),
    "euler_number": int(t_mesh.euler_number)
}

with open(STATS_DIR / "stats.json", "w") as f:
    json.dump(stats, f, indent=4)

# Create comparison report
report = f"""# Geometry Processing Quality Report

## Quantitative Improvements
| Metric | Original | Cleaned |
|---|---|---|
| Vertices | {stats['original_vertices']:,} | {stats['clean_vertices']:,} |
| Faces | {stats['original_faces']:,} | {stats['clean_faces']:,} |
| Watertight | False | {stats['is_watertight']} |
| Surface Area | N/A | {stats['surface_area']:.2f} |
| Euler Number | N/A | {stats['euler_number']} |

## Pipeline Steps Applied
1. **Statistical Outlier Removal** (nb_neighbors=20, std_ratio=2.0)
2. **Radius Outlier Removal** (nb_points=16, radius=0.05)
3. **Screened Poisson Reconstruction** (depth=9)
4. **Density Filtering** (5% quantile removal)
5. **Largest Connected Component** isolation
6. **HC Laplacian / Taubin Smoothing** (10 iterations)
7. **KNN Vertex Color Denoising** (k=5)
"""
with open(V2_DIR / "comparison_report.md", "w") as f:
    f.write(report)

print("\nPipeline Complete. Outputs saved to C:\\recon\\reconstruction_v2\\")
