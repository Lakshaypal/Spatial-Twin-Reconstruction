import os
import sys
import glob
import time
import json
import psutil
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

# ==================================================
# PHASE 5 — DEFINE A RUNNER (Configurable Constants)
# ==================================================
BASE_DIR = Path(r"C:\recon\ds02")
OUT_DIR = BASE_DIR / "running_space_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Clearance Radiuses
RAD_NARROW = 0.30
RAD_COMFORTABLE = 0.375
RAD_CONSERVATIVE = 0.50

# Slope
MAX_SLOPE = 10.0
PREF_SLOPE = 5.0

# Memory & Grid
MAX_RAM_GB = 8.0 # Soft limit for grid allocation
DEFAULT_RES = 0.15 # 15cm if units are meters

# Report Data
REPORT_DATA = {}
LIMITATIONS = []

# ==================================================
# UTILS
# ==================================================
def print_header(title):
    print(f"\n{'-'*50}\n{title}\n{'-'*50}")

# ==================================================
# PHASE 1 & 2 & 3 — DISCOVER, LOAD, SCALE
# ==================================================
def phase_1_2_3():
    print_header("PHASE 1-3: DISCOVERY, LOAD & SCALE")
    
    # 1. Discover
    files = []
    for ext in ["*.glb", "*.ply", "*.obj"]:
        files.extend(list(BASE_DIR.rglob(ext)))
        
    def score_file(p):
        name = p.name.lower()
        if "mesh_final.glb" in name: return 1
        if "mesh_final.ply" in name: return 2
        if "mesh_final.obj" in name: return 3
        if "fused" in name: return 99
        return 50

    files_sorted = sorted(files, key=score_file)
    if not files_sorted:
        raise ValueError("No mesh files found in C:\\recon\\ds02")
    
    # 2. Load
    mesh = None
    selected_path = None
    for p in files_sorted:
        print(f"Attempting: {p.name}")
        try:
            mesh = o3d.io.read_triangle_mesh(str(p))
            if len(mesh.vertices) > 0 and len(mesh.triangles) > 0:
                selected_path = p
                break
        except Exception as e:
            print(f"Failed loading {p.name}: {e}")
            LIMITATIONS.append(f"Failed to load {p.name}")
            
    if mesh is None:
        raise ValueError("Could not load any valid mesh.")
        
    print(f"Loaded: {selected_path.name}")
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    
    # 3. Scale Validation
    scale_status = "UNKNOWN"
    unit_name = "model units"
    
    # Search for scale info
    # Usually in colmap this implies cameras.txt might have priors, but for safety:
    LIMITATIONS.append("Scale verified as UNKNOWN. All metrics are in Model Units.")
    REPORT_DATA['Scale'] = scale_status
    REPORT_DATA['Unit'] = unit_name
    
    REPORT_DATA['Mesh'] = selected_path.name
    REPORT_DATA['Vertices'] = len(mesh.vertices)
    REPORT_DATA['Triangles'] = len(mesh.triangles)
    REPORT_DATA['BoundingBox'] = [float(x) for x in extent]
    
    return mesh, unit_name

# ==================================================
# PHASE 4 — GROUND DETECTION
# ==================================================
def phase_4_ground(mesh):
    print_header("PHASE 4: GROUND DETECTION")
    if not mesh.has_vertex_normals(): mesh.compute_vertex_normals()
    if not mesh.has_triangle_normals(): mesh.compute_triangle_normals()
        
    tn = np.asarray(mesh.triangle_normals)
    abs_z = np.mean(np.abs(tn[:, 2]))
    abs_y = np.mean(np.abs(tn[:, 1]))
    
    up_axis = 2 if abs_z > abs_y else 1
    hist, bins = np.histogram(tn[:, up_axis], bins=20, range=(-1, 1))
    up_sign = 1 if hist[-1] > hist[0] else -1
    
    up_vector = np.array([0.0, 0.0, 0.0])
    up_vector[up_axis] = up_sign
    print(f"Dominant Up Vector: {up_vector}")
    REPORT_DATA['UpVector'] = up_vector.tolist()
    
    dots = np.dot(tn, up_vector)
    ground_mask = dots > 0.707 # 45 degrees relative to up
    
    return np.asarray(mesh.vertices), np.asarray(mesh.triangles), ground_mask, up_vector, up_axis

# ==================================================
# PHASE 6 — RASTERIZATION
# ==================================================
def phase_6_rasterize(vertices, triangles, ground_mask, up_vector, up_axis):
    print_header("PHASE 6: RUNNABLE SURFACE (RASTERIZATION)")
    
    # Rotate so Z is Up
    if up_axis == 1:
        R = np.array([[1,0,0], [0,0,-1], [0,1,0]])
        vertices = vertices @ R.T
        if up_vector[1] < 0: vertices[:, 2] = -vertices[:, 2]
    else:
        if up_vector[2] < 0: vertices[:, 2] = -vertices[:, 2]

    min_b = np.min(vertices, axis=0)
    max_b = np.max(vertices, axis=0)
    
    # Dynamic RAM sizing
    res = DEFAULT_RES
    width = int(np.ceil((max_b[0] - min_b[0]) / res))
    height = int(np.ceil((max_b[1] - min_b[1]) / res))
    
    while (width * height * 8) / (1024**3) > (MAX_RAM_GB / 4.0):
        print("Grid too large for safe RAM overhead. Decreasing resolution...")
        res *= 1.5
        width = int(np.ceil((max_b[0] - min_b[0]) / res))
        height = int(np.ceil((max_b[1] - min_b[1]) / res))
        
    print(f"Final Grid: {width} x {height} (Res: {res:.3f})")
    REPORT_DATA['GridRes'] = res
    
    ground_tris = triangles[ground_mask]
    obs_tris = triangles[~ground_mask]
    
    ground_verts_idx = np.unique(ground_tris)
    obs_verts_idx = np.unique(obs_tris)
    
    gx = np.clip(((vertices[ground_verts_idx, 0] - min_b[0]) / res).astype(np.int32), 0, width-1)
    gy = np.clip(((vertices[ground_verts_idx, 1] - min_b[1]) / res).astype(np.int32), 0, height-1)
    gz = vertices[ground_verts_idx, 2]
    
    ox = np.clip(((vertices[obs_verts_idx, 0] - min_b[0]) / res).astype(np.int32), 0, width-1)
    oy = np.clip(((vertices[obs_verts_idx, 1] - min_b[1]) / res).astype(np.int32), 0, height-1)
    
    # Elevation projection
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
    
    # Slope
    dzdx = ndimage.sobel(elev_map, axis=1) / (8.0 * res)
    dzdy = ndimage.sobel(elev_map, axis=0) / (8.0 * res)
    slope_map = np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))
    
    valid_mask = elev_map > -9990.0
    slope_map[~valid_mask] = 999.0
    
    return elev_map, slope_map, obs_map, valid_mask, res

# ==================================================
# PHASE 7 & 8 — CLEARANCE & REGIONS
# ==================================================
def phase_7_8_clearance_regions(slope_map, obs_map, valid_mask, res):
    print_header("PHASE 7 & 8: CLEARANCE & REGIONS")
    
    dist_map_pixels = ndimage.distance_transform_edt(~obs_map)
    clearance_map = dist_map_pixels * res
    
    # 3 Scenarios
    narrow_run = valid_mask & (slope_map <= MAX_SLOPE) & (clearance_map >= RAD_NARROW)
    comf_run   = valid_mask & (slope_map <= MAX_SLOPE) & (clearance_map >= RAD_COMFORTABLE)
    cons_run   = valid_mask & (slope_map <= MAX_SLOPE) & (clearance_map >= RAD_CONSERVATIVE)
    
    print(f"Narrow Area: {np.sum(narrow_run) * (res**2):.1f}")
    print(f"Comfortable Area: {np.sum(comf_run) * (res**2):.1f}")
    print(f"Conservative Area: {np.sum(cons_run) * (res**2):.1f}")
    
    # Use Comfortable for primary analysis
    runnable = comf_run
    walkable = valid_mask & (slope_map <= MAX_SLOPE + 5.0) & (clearance_map >= RAD_NARROW) & ~runnable
    obstacle = ~runnable & ~walkable & (clearance_map < RAD_NARROW)
    
    # Connected Components
    labeled, num_features = ndimage.label(runnable)
    areas = ndimage.sum(runnable, labeled, range(1, num_features + 1))
    
    if len(areas) > 0:
        largest_idx = np.argmax(areas) + 1
        largest_mask = (labeled == largest_idx)
        largest_area = areas[largest_idx-1] * (res**2)
    else:
        largest_mask = np.zeros_like(runnable)
        largest_area = 0.0
        
    REPORT_DATA['TotalRunnableArea'] = float(np.sum(runnable) * (res**2))
    REPORT_DATA['LargestRunnableArea'] = float(largest_area)
    REPORT_DATA['NumRegions'] = int(num_features)
    
    return runnable, walkable, obstacle, largest_mask, clearance_map, res

# ==================================================
# PHASE 9 & 10 — GRAPH (ROUTE & LOOP)
# ==================================================
def phase_9_10_routes(largest_mask, res, clearance_map, slope_map):
    print_header("PHASE 9 & 10: ROUTES & LOOPS")
    if skeletonize is None or np.sum(largest_mask) < 10:
        LIMITATIONS.append("Graph analysis skipped (too small or missing skimage)")
        REPORT_DATA['LongestRoute'] = 0.0
        REPORT_DATA['LongestLoop'] = 0.0
        return [], []
        
    skel = skeletonize(largest_mask)
    ys, xs = np.where(skel)
    G = nx.Graph()
    for x, y in zip(xs, ys): G.add_node((x, y))
        
    if len(xs) > 1:
        tree = cKDTree(np.column_stack((xs, ys)))
        pairs = tree.query_pairs(1.5)
        for i, j in pairs:
            p1, p2 = (xs[i], ys[i]), (xs[j], ys[j])
            G.add_edge(p1, p2, weight=np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2) * res)
            
    if len(G.nodes) == 0:
        return [], []
        
    # Phase 9: Longest Route
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
        
    # Phase 10: Loop Test
    cycles = nx.cycle_basis(G)
    longest_loop = []
    max_loop_dist = 0.0
    
    for cycle in cycles:
        if len(cycle) < 4: continue
        # Calculate length of cycle
        dist = 0.0
        for i in range(len(cycle)):
            n1, n2 = cycle[i], cycle[(i+1) % len(cycle)]
            dist += G[n1][n2]['weight']
        if dist > max_loop_dist:
            max_loop_dist = dist
            longest_loop = cycle
            
    # Add final closing edge for visualization
    if len(longest_loop) > 0:
        longest_loop.append(longest_loop[0])
        
    print(f"Longest Route: {longest_dist:.1f}")
    print(f"Longest Loop: {max_loop_dist:.1f}")
    
    if max_loop_dist == 0:
        print("No continuous runnable loop detected.")
        LIMITATIONS.append("No continuous runnable loop detected.")
        
    REPORT_DATA['LongestRoute'] = float(longest_dist)
    REPORT_DATA['LongestLoop'] = float(max_loop_dist)
    
    return longest_path, longest_loop

# ==================================================
# PHASE 11 & 12 — VISUALIZATION & REPORT
# ==================================================
def phase_11_12(runnable, walkable, obstacle, largest_mask, longest_path, longest_loop, clearance_map, slope_map, unit_name):
    print_header("PHASE 11 & 12: EXPORT")
    
    # 1. Top Down
    plt.figure(figsize=(10, 10))
    cmap = np.zeros(runnable.shape + (3,))
    cmap[obstacle] = [1, 0, 0]
    cmap[walkable] = [1, 1, 0]
    cmap[runnable] = [0, 1, 0]
    plt.imshow(cmap)
    plt.title(f"Running Area Heatmap (Green=Run, Yel=Walk, Red=Obs)\nUnits: {unit_name}")
    plt.axis('off')
    plt.savefig(OUT_DIR / "01_top_down_map.png", bbox_inches='tight')
    plt.close()
    
    # 2. Longest Route
    if longest_path:
        plt.figure(figsize=(10, 10))
        plt.imshow(largest_mask, cmap='gray', alpha=0.5)
        xs, ys = zip(*longest_path)
        plt.plot(xs, ys, 'c-', linewidth=3, label=f"Route: {REPORT_DATA['LongestRoute']:.1f}")
        plt.legend()
        plt.axis('off')
        plt.savefig(OUT_DIR / "02_longest_route.png", bbox_inches='tight')
        plt.close()
        
    # 3. Loop
    if longest_loop:
        plt.figure(figsize=(10, 10))
        plt.imshow(largest_mask, cmap='gray', alpha=0.5)
        xs, ys = zip(*longest_loop)
        plt.plot(xs, ys, 'm-', linewidth=3, label=f"Loop: {REPORT_DATA['LongestLoop']:.1f}")
        plt.legend()
        plt.axis('off')
        plt.savefig(OUT_DIR / "03_best_loop.png", bbox_inches='tight')
        plt.close()
        
    # 4. Clearance
    plt.figure(figsize=(10, 10))
    cl = plt.imshow(np.clip(clearance_map, 0, 2.0), cmap='viridis')
    plt.colorbar(cl, label=f"Clearance ({unit_name})")
    plt.axis('off')
    plt.savefig(OUT_DIR / "04_clearance_heatmap.png", bbox_inches='tight')
    plt.close()
    
    with open(OUT_DIR / "running_space_report.json", "w") as f:
        json.dump(REPORT_DATA, f, indent=4)
        
    report = f"""========================================
RUNNING SPACE ANALYSIS COMPLETE
========================================
Mesh: {REPORT_DATA.get('Mesh', 'Unknown')}
Scale: {REPORT_DATA.get('Scale')} ({unit_name})

Runnable area: {REPORT_DATA.get('TotalRunnableArea', 0):.1f} {unit_name}^2
Largest runnable region: {REPORT_DATA.get('LargestRunnableArea', 0):.1f} {unit_name}^2

Longest route: {REPORT_DATA.get('LongestRoute', 0):.1f} {unit_name}
Longest loop: {REPORT_DATA.get('LongestLoop', 0):.1f} {unit_name}

Scale confidence: Low
Output directory: {OUT_DIR}
========================================

LIMITATIONS & AUTHENTICITY:
"""
    for l in LIMITATIONS:
        report += f"- {l}\n"
        
    report += """
- NEVER invent scale. Measurements are in Model Units.
- NEVER fabricate missing ground or smooth holes.
- This is a GEOMETRIC ACCESSIBILITY analysis, NOT a physical safety certification.
"""
    with open(OUT_DIR / "running_space_report.txt", "w") as f:
        f.write(report)
        
    print(report)

# ==================================================
# MAIN
# ==================================================
def main():
    mesh, unit_name = phase_1_2_3()
    vertices, triangles, ground_mask, up_vector, up_axis = phase_4_ground(mesh)
    elev, slope, obs, valid, res = phase_6_rasterize(vertices, triangles, ground_mask, up_vector, up_axis)
    runnable, walkable, obstacle, largest_mask, clearance, res = phase_7_8_clearance_regions(slope, obs, valid, res)
    route, loop = phase_9_10_routes(largest_mask, res, clearance, slope)
    phase_11_12(runnable, walkable, obstacle, largest_mask, route, loop, clearance, slope, unit_name)

if __name__ == "__main__":
    main()
