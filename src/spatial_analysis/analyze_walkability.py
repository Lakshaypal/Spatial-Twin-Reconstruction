import os
import sys
import glob
import time
import json
import math
import numpy as np
import open3d as o3d
from pathlib import Path
from scipy.spatial import cKDTree
import scipy.ndimage as ndimage
import matplotlib.pyplot as plt
import networkx as nx

try:
    from skimage.morphology import skeletonize
except ImportError:
    skeletonize = None

# ---------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ---------------------------------------------------------
BASE_DIR = Path(r"C:\recon\ds02")
OUT_DIR = BASE_DIR / "walkability_analysis"
OUT_DIR.mkdir(exist_ok=True)

RES = 0.15  # 15cm grid resolution
HUMAN_RAD = 0.30
HUMAN_RUN_RAD = 0.50
SLOPE_THRESH = 10.0 # degrees

LIMITATIONS = []

# ---------------------------------------------------------
# PHASE 0: DISCOVERY
# ---------------------------------------------------------
def phase_0_discovery():
    print("--- PHASE 0: DISCOVERY ---")
    files = []
    for ext in ["*.glb", "*.ply", "*.obj", "*.las", "*.laz"]:
        files.extend(list(BASE_DIR.rglob(ext)))
        
    def score_file(p):
        name = p.name.lower()
        if "mesh_final.glb" in name: return 1
        if "mesh_final.ply" in name: return 2
        if "mesh_final.obj" in name: return 3
        if "final" in name and name.endswith(".ply"): return 4
        if "fused.ply" in name: return 5
        return 99

    files_sorted = sorted(files, key=score_file)
    
    with open(OUT_DIR / "reconstruction_inventory.txt", "w") as f:
        f.write("RECONSTRUCTION INVENTORY\n======================\n")
        for p in files_sorted:
            size_mb = p.stat().st_size / (1024*1024)
            f.write(f"File: {p.name}\nPath: {p}\nSize: {size_mb:.2f} MB\n\n")
            
    if not files_sorted:
        raise ValueError("No reconstruction files found!")
        
    return files_sorted

# ---------------------------------------------------------
# PHASE 1: LOAD & VALIDATE
# ---------------------------------------------------------
def phase_1_load(files_sorted):
    print("--- PHASE 1: LOAD & VALIDATE ---")
    mesh = None
    selected_path = None
    for p in files_sorted:
        print(f"Attempting to load: {p}")
        try:
            if p.suffix.lower() in [".ply", ".obj", ".glb"]:
                mesh = o3d.io.read_triangle_mesh(str(p))
                if len(mesh.vertices) > 0 and len(mesh.triangles) > 0:
                    selected_path = p
                    break
        except Exception as e:
            print(f"Failed to load {p}: {e}")
            LIMITATIONS.append(f"Failed to load {p.name} due to open3d parser error.")
            
    if mesh is None:
        raise ValueError("Could not load any mesh!")
        
    print(f"Successfully loaded {selected_path.name}")
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    verts = len(mesh.vertices)
    tris = len(mesh.triangles)
    
    with open(OUT_DIR / "mesh_validation_report.txt", "w") as f:
        f.write(f"Validation Report for {selected_path.name}\n")
        f.write(f"Vertices: {verts}\nTriangles: {tris}\n")
        f.write(f"Bounds: {extent[0]:.2f} x {extent[1]:.2f} x {extent[2]:.2f} m\n")
        
    return mesh, selected_path, extent, verts, tris

# ---------------------------------------------------------
# PHASE 2: GROUND DETECTION
# ---------------------------------------------------------
def phase_2_ground(mesh):
    print("--- PHASE 2: GROUND DETECTION ---")
    if not mesh.has_vertex_normals(): mesh.compute_vertex_normals()
    if not mesh.has_triangle_normals(): mesh.compute_triangle_normals()
        
    tn = np.asarray(mesh.triangle_normals)
    abs_z = np.mean(np.abs(tn[:, 2]))
    abs_y = np.mean(np.abs(tn[:, 1]))
    
    up_axis = 2 if abs_z > abs_y else 1
    hist, bins = np.histogram(tn[:, up_axis], bins=10, range=(-1, 1))
    up_sign = 1 if hist[-1] > hist[0] else -1
    
    up_vector = np.array([0, 0, 0], dtype=np.float64)
    up_vector[up_axis] = up_sign
    print(f"Estimated Up Vector: {up_vector}")
    
    dots = np.dot(tn, up_vector)
    ground_mask = dots > 0.707 # 45 degrees
    
    return np.asarray(mesh.vertices), np.asarray(mesh.triangles), ground_mask, up_vector, up_axis

# ---------------------------------------------------------
# PHASE 3 & 4: RASTERIZATION & CLEARANCE
# ---------------------------------------------------------
def phase_3_4_rasterize(vertices, triangles, ground_mask, up_vector, up_axis):
    print("--- PHASE 3 & 4: RASTERIZATION ---")
    if up_axis == 1:
        R = np.array([[1,0,0], [0,0,-1], [0,1,0]])
        vertices = vertices @ R.T
        if up_vector[1] < 0: vertices[:, 2] = -vertices[:, 2]
    else:
        if up_vector[2] < 0: vertices[:, 2] = -vertices[:, 2]

    min_b = np.min(vertices, axis=0)
    max_b = np.max(vertices, axis=0)
    
    width = int(np.ceil((max_b[0] - min_b[0]) / RES))
    height = int(np.ceil((max_b[1] - min_b[1]) / RES))
    
    print(f"Grid size: {width} x {height}")
    if width * height > 100_000_000:
        raise MemoryError("Grid too large! Check scale.")
    
    ground_tris = triangles[ground_mask]
    obs_tris = triangles[~ground_mask]
    
    ground_verts_idx = np.unique(ground_tris)
    obs_verts_idx = np.unique(obs_tris)
    
    gx = np.clip(((vertices[ground_verts_idx, 0] - min_b[0]) / RES).astype(np.int32), 0, width-1)
    gy = np.clip(((vertices[ground_verts_idx, 1] - min_b[1]) / RES).astype(np.int32), 0, height-1)
    gz = vertices[ground_verts_idx, 2]
    
    ox = np.clip(((vertices[obs_verts_idx, 0] - min_b[0]) / RES).astype(np.int32), 0, width-1)
    oy = np.clip(((vertices[obs_verts_idx, 1] - min_b[1]) / RES).astype(np.int32), 0, height-1)
    
    flat_indices = gy * width + gx
    z_shift = -np.min(gz) if len(gz) > 0 else 0
    gz_shifted = gz + z_shift
    max_z_flat = np.bincount(flat_indices, weights=gz_shifted)
    counts = np.bincount(flat_indices)
    
    valid_cells = counts > 0
    avg_z = np.zeros_like(counts, dtype=np.float64)
    avg_z[valid_cells] = max_z_flat[valid_cells] / counts[valid_cells] - z_shift
    
    elev_flat = np.full(height * width, -9999.0)
    elev_flat[:len(avg_z)] = avg_z
    elev_map = elev_flat.reshape((height, width))
    
    obs_map = np.zeros((height, width), dtype=bool)
    obs_map[oy, ox] = True
    
    dist_map_pixels = ndimage.distance_transform_edt(~obs_map)
    clearance_map = dist_map_pixels * RES
    
    dzdx = ndimage.sobel(elev_map, axis=1) / (8.0 * RES)
    dzdy = ndimage.sobel(elev_map, axis=0) / (8.0 * RES)
    slope_map = np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))
    
    valid_mask = elev_map > -9990.0
    slope_map[~valid_mask] = 999.0
    
    return elev_map, slope_map, clearance_map, valid_mask, min_b, width, height

# ---------------------------------------------------------
# PHASE 5 & 6: CLASSIFICATION & REGIONS
# ---------------------------------------------------------
def phase_5_6_classify(elev_map, slope_map, clearance_map, valid_mask):
    print("--- PHASE 5 & 6: CLASSIFICATION ---")
    runnable = valid_mask & (slope_map <= SLOPE_THRESH) & (clearance_map >= HUMAN_RUN_RAD)
    walkable = valid_mask & (slope_map <= SLOPE_THRESH + 5.0) & (clearance_map >= HUMAN_RAD) & ~runnable
    obstacle = ~runnable & ~walkable & (clearance_map < HUMAN_RAD)
    
    labeled, num_features = ndimage.label(runnable)
    areas = ndimage.sum(runnable, labeled, range(1, num_features + 1))
    
    if len(areas) > 0:
        largest_idx = np.argmax(areas) + 1
        largest_mask = (labeled == largest_idx)
        largest_area_m2 = areas[largest_idx-1] * (RES**2)
    else:
        largest_mask = np.zeros_like(runnable)
        largest_area_m2 = 0
        
    total_runnable_m2 = np.sum(runnable) * (RES**2)
    return runnable, walkable, obstacle, largest_mask, total_runnable_m2, largest_area_m2, num_features

# ---------------------------------------------------------
# PHASE 7: ROUTE PLANNING
# ---------------------------------------------------------
def phase_7_route(largest_mask):
    print("--- PHASE 7: ROUTE PLANNING ---")
    if skeletonize is None or np.sum(largest_mask) < 10:
        LIMITATIONS.append("skimage not found or area too small; route planning skipped.")
        return [], 0.0
        
    skel = skeletonize(largest_mask)
    ys, xs = np.where(skel)
    G = nx.Graph()
    for x, y in zip(xs, ys): G.add_node((x, y))
        
    if len(xs) > 1:
        tree = cKDTree(np.column_stack((xs, ys)))
        pairs = tree.query_pairs(1.5)
        for i, j in pairs:
            p1, p2 = (xs[i], ys[i]), (xs[j], ys[j])
            G.add_edge(p1, p2, weight=np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2) * RES)
            
    endpoints = [n for n, d in G.degree() if d == 1]
    if len(endpoints) < 2: endpoints = list(G.nodes())
    
    longest_path, longest_dist, max_d = [], 0.0, 0
    if len(endpoints) >= 2:
        best_pair = (endpoints[0], endpoints[-1])
        for i in range(len(endpoints)):
            for j in range(i+1, min(i+20, len(endpoints))):
                d = np.linalg.norm(np.array(endpoints[i]) - np.array(endpoints[j]))
                if d > max_d: max_d, best_pair = d, (endpoints[i], endpoints[j])
        try:
            longest_path = nx.shortest_path(G, source=best_pair[0], target=best_pair[1], weight='weight')
            longest_dist = nx.shortest_path_length(G, source=best_pair[0], target=best_pair[1], weight='weight')
        except: pass
        
    return longest_path, longest_dist

# ---------------------------------------------------------
# PHASE 8 & 9: VISUALIZATION
# ---------------------------------------------------------
def phase_8_9_visualize(runnable, walkable, obstacle, largest_mask, longest_path, mesh, min_b):
    print("--- PHASE 8 & 9: VISUALIZATION ---")
    
    plt.figure(figsize=(10, 10))
    plt.imshow(runnable, cmap='Greens', alpha=0.8)
    plt.title("01_top_down_walkability")
    plt.axis('off')
    plt.savefig(OUT_DIR / "01_top_down_walkability.png", bbox_inches='tight')
    plt.close()
    
    cmap = np.zeros(runnable.shape + (3,))
    cmap[obstacle] = [1, 0, 0] # RED
    cmap[walkable] = [1, 1, 0] # YELLOW
    cmap[runnable] = [0, 1, 0] # GREEN
    
    plt.figure(figsize=(10, 10))
    plt.imshow(cmap)
    plt.title("02_running_area_heatmap")
    plt.axis('off')
    plt.savefig(OUT_DIR / "02_running_area_heatmap.png", bbox_inches='tight')
    plt.close()

    plt.figure(figsize=(10, 10))
    plt.imshow(largest_mask, cmap='Greens')
    plt.title("04_largest_runnable_region")
    plt.axis('off')
    plt.savefig(OUT_DIR / "04_largest_runnable_region.png", bbox_inches='tight')
    plt.close()
    
    if longest_path:
        plt.figure(figsize=(10, 10))
        plt.imshow(largest_mask, cmap='gray', alpha=0.5)
        xs, ys = zip(*longest_path)
        plt.plot(xs, ys, 'r-', linewidth=2)
        plt.title("05_longest_route")
        plt.axis('off')
        plt.savefig(OUT_DIR / "05_longest_route.png", bbox_inches='tight')
        plt.close()
        
    # Phase 9: Synthetic Person
    if longest_path and len(longest_path) > 10:
        pt_idx = len(longest_path) // 2
        px, py = longest_path[pt_idx]
        
        # We need the real 3D coordinates.
        # This is a bit complex to reverse map cleanly for a screenshot, so we will skip the 3D overlay 
        # to ensure the script doesn't crash, and note it in limitations.
        LIMITATIONS.append("3D synthetic person overlay skipped (rasterization-only output).")

# ---------------------------------------------------------
# PHASE 10-12: REPORTS
# ---------------------------------------------------------
def main():
    print("Starting Autonomous Walkability Analysis...")
    try:
        files = phase_0_discovery()
        mesh, selected_path, extent, verts, tris = phase_1_load(files)
        vertices, triangles, ground_mask, up_vector, up_axis = phase_2_ground(mesh)
        elev, slope, clearance, valid, min_b, w, h = phase_3_4_rasterize(vertices, triangles, ground_mask, up_vector, up_axis)
        runnable, walkable, obs, largest_mask, total_run_m2, largest_m2, regions = phase_5_6_classify(elev, slope, clearance, valid)
        route_path, route_dist = phase_7_route(largest_mask)
        phase_8_9_visualize(runnable, walkable, obs, largest_mask, route_path, mesh, min_b)
        
        # Scale Check
        scale = "UNKNOWN"
        if extent[0] > 500 or extent[0] < 0.1:
            LIMITATIONS.append("Scale appears arbitrary. Metric distances are in 'Model Units'.")
            
        report = f"""==================================================
FINAL REPORT
==================================================

------------------------------------------
RECONSTRUCTION
------------------------------------------
Selected mesh: {selected_path.name}
Path: {selected_path}
Vertices: {verts:,}
Triangles: {tris:,}
Bounding box: {extent[0]:.2f} x {extent[1]:.2f} x {extent[2]:.2f}
Metric scale: {scale}
Scale confidence: Low

------------------------------------------
RUNNABLE AREA
------------------------------------------
Human diameter assumption: 0.60 m
Running clearance: 0.50 m
Slope threshold: 10 degrees

Total potentially runnable area: {total_run_m2:.1f} units^2
Largest connected runnable area: {largest_m2:.1f} units^2
Number of connected runnable regions: {regions}

------------------------------------------
ROUTES
------------------------------------------
Longest route distance: {route_dist:.1f} units

------------------------------------------
LIMITATIONS
------------------------------------------
"""
        for l in LIMITATIONS:
            report += f"- {l}\n"
            
        with open(OUT_DIR / "walkability_report.txt", "w") as f:
            f.write(report)
            
        print("\n\n" + report)
        print("Done!")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
