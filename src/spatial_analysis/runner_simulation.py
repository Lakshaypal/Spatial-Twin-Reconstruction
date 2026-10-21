import os
import sys
import json
import time
import math
import numpy as np
import open3d as o3d
from pathlib import Path
from scipy.spatial import cKDTree
import scipy.ndimage as ndimage
import networkx as nx
from scipy.interpolate import splprep, splev

try:
    from skimage.morphology import skeletonize
except ImportError:
    skeletonize = None

# ==================================================
# CONFIGURATION
# ==================================================
BASE_DIR = Path(r"C:\recon\ds02")
OUT_DIR = BASE_DIR / "running_space_analysis" / "runner_simulation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Clearance Radii (Model Units) - from previous
RAD_COMFORTABLE = 0.30
MAX_SLOPE = 10.0
DEFAULT_RES = 0.15 
MAX_RAM_GB = 8.0 

# Runner Configuration
RUNNER_HEIGHT = 1.75
RUNNER_RADIUS = 0.20
RUNNER_SPEED = 1.5 # model units/sec

EXPECTED_ROUTE_LENGTH = 57.43

# ==================================================
# 1. ROUTE RECONSTRUCTION (Exact Copy of Logic)
# ==================================================
def reconstruct_route():
    print("Loading mesh for route reconstruction...")
    mesh = o3d.io.read_triangle_mesh(str(BASE_DIR / "dense" / "final" / "mesh_final.ply"))
    mesh.compute_vertex_normals()
    mesh.compute_triangle_normals()
    
    # Ground detection
    tn = np.asarray(mesh.triangle_normals)
    up_vector = np.array([0.0, -1.0, 0.0]) # Forced based on previous run for exact match
    up_axis = 1
    
    dots = np.dot(tn, up_vector)
    ground_mask = dots > 0.707
    
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    
    # Rotation for rasterization
    R = np.array([[1,0,0], [0,0,-1], [0,1,0]])
    verts_rot = vertices @ R.T
    verts_rot[:, 2] = -verts_rot[:, 2]
    
    min_b, max_b = np.min(verts_rot, axis=0), np.max(verts_rot, axis=0)
    res = DEFAULT_RES
    width, height = int(np.ceil((max_b[0] - min_b[0])/res)), int(np.ceil((max_b[1] - min_b[1])/res))
    
    while (width * height * 8) / (1024**3) > (MAX_RAM_GB / 4.0):
        res *= 1.5
        width, height = int(np.ceil((max_b[0] - min_b[0])/res)), int(np.ceil((max_b[1] - min_b[1])/res))
        
    ground_verts_idx = np.unique(triangles[ground_mask])
    obs_verts_idx = np.unique(triangles[~ground_mask])
    
    gx = np.clip(((verts_rot[ground_verts_idx, 0] - min_b[0]) / res).astype(np.int32), 0, width-1)
    gy = np.clip(((verts_rot[ground_verts_idx, 1] - min_b[1]) / res).astype(np.int32), 0, height-1)
    gz = verts_rot[ground_verts_idx, 2]
    
    ox = np.clip(((verts_rot[obs_verts_idx, 0] - min_b[0]) / res).astype(np.int32), 0, width-1)
    oy = np.clip(((verts_rot[obs_verts_idx, 1] - min_b[1]) / res).astype(np.int32), 0, height-1)
    
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
    
    dzdx = ndimage.sobel(elev_map, axis=1) / (8.0 * res)
    dzdy = ndimage.sobel(elev_map, axis=0) / (8.0 * res)
    slope_map = np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))
    
    valid_mask = elev_map > -9990.0
    slope_map[~valid_mask] = 999.0
    
    dist_map_pixels = ndimage.distance_transform_edt(~obs_map)
    clearance_map = dist_map_pixels * res
    
    runnable = valid_mask & (slope_map <= MAX_SLOPE) & (clearance_map >= RAD_COMFORTABLE)
    labeled, num = ndimage.label(runnable)
    areas = ndimage.sum(runnable, labeled, range(1, num + 1))
    largest_idx = np.argmax(areas) + 1 if len(areas) > 0 else 0
    largest_mask = (labeled == largest_idx)
    
    if skeletonize is None: raise ImportError("skimage required for skeletonization")
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
            
    endpoints = [n for n, d in G.degree() if d == 1]
    if len(endpoints) < 2: endpoints = list(G.nodes())
    
    longest_path, longest_dist, max_d = [], 0.0, 0
    best_pair = None
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
        
    diff = abs(longest_dist - EXPECTED_ROUTE_LENGTH)
    pct = (diff / EXPECTED_ROUTE_LENGTH) * 100.0
    
    print(f"Previous route length: {EXPECTED_ROUTE_LENGTH}")
    print(f"Recomputed route length: {longest_dist:.2f}")
    print(f"Difference: {diff:.2f} ({pct:.2f}%)")
    
    if pct > 2.0:
        print("ERROR: Significant discrepancy in route reconstruction.")
        sys.exit(1)
        
    # Convert path to 3D original coordinates
    route_3d = []
    inv_R = np.linalg.inv(R.T)
    for px, py in longest_path:
        rx = min_b[0] + px * res
        ry = min_b[1] + py * res
        rz = elev_map[py, px]
        
        # Undo rotation (verts_rot[:, 2] = -verts_rot[:, 2] was done before)
        rz = -rz
        orig_pt = np.array([rx, ry, rz]) @ inv_R
        route_3d.append(orig_pt.tolist())
        
    # Spline smoothing
    if len(route_3d) > 3:
        pts = np.array(route_3d)
        tck, u = splprep([pts[:,0], pts[:,1], pts[:,2]], s=5.0)
        u_new = np.linspace(0, 1, len(route_3d) * 3) # 3x points
        new_points = splev(u_new, tck)
        route_3d = np.column_stack(new_points).tolist()
        
    # Save JSONs
    with open(OUT_DIR / "route_used.json", "w") as f:
        json.dump({
            "route_length_model_units": float(longest_dist),
            "coordinates": route_3d
        }, f, indent=4)
        
    with open(OUT_DIR / "route_reconstruction_metadata.json", "w") as f:
        json.dump({
            "mesh": "mesh_final.ply",
            "ground_normal": [0, -1, 0],
            "grid_resolution": res,
            "clearance_radius": RAD_COMFORTABLE,
            "calculated_length": longest_dist,
            "expected_length": EXPECTED_ROUTE_LENGTH,
            "difference_pct": pct
        }, f, indent=4)
        
    return mesh, np.array(route_3d), longest_dist

# ==================================================
# 2. RUNNER SIMULATION
# ==================================================
def build_humanoid():
    # Simple low poly runner
    mat = o3d.visualization.rendering.MaterialRecord() if hasattr(o3d.visualization, 'rendering') else None
    
    head = o3d.geometry.TriangleMesh.create_sphere(radius=0.12)
    head.compute_vertex_normals()
    head.paint_uniform_color([0.9, 0.7, 0.6])
    
    torso = o3d.geometry.TriangleMesh.create_cylinder(radius=0.15, height=0.6)
    torso.compute_vertex_normals()
    torso.paint_uniform_color([0.2, 0.4, 0.8])
    
    l_arm = o3d.geometry.TriangleMesh.create_cylinder(radius=0.06, height=0.6)
    l_arm.compute_vertex_normals()
    l_arm.paint_uniform_color([0.8, 0.3, 0.3])
    
    r_arm = o3d.geometry.TriangleMesh.create_cylinder(radius=0.06, height=0.6)
    r_arm.compute_vertex_normals()
    r_arm.paint_uniform_color([0.8, 0.3, 0.3])
    
    l_leg = o3d.geometry.TriangleMesh.create_cylinder(radius=0.08, height=0.8)
    l_leg.compute_vertex_normals()
    l_leg.paint_uniform_color([0.2, 0.2, 0.2])
    
    r_leg = o3d.geometry.TriangleMesh.create_cylinder(radius=0.08, height=0.8)
    r_leg.compute_vertex_normals()
    r_leg.paint_uniform_color([0.2, 0.2, 0.2])
    
    clearance = o3d.geometry.TriangleMesh.create_cylinder(radius=RAD_COMFORTABLE, height=RUNNER_HEIGHT)
    clearance.compute_vertex_normals()
    # Open3D legacy visualizer transparency hack: paint it white, but we'll render it wireframe
    clearance.paint_uniform_color([0.0, 1.0, 1.0]) 

    return {
        "head": head, "torso": torso, 
        "l_arm": l_arm, "r_arm": r_arm, 
        "l_leg": l_leg, "r_leg": r_leg,
        "clearance": clearance
    }

def update_humanoid(humanoid, pos, tangent, up, phase):
    # Base transforms
    rot_matrix = np.eye(3)
    
    # We want tangent to be the facing direction (Z local)
    # Up is the up direction (Y local)
    # Right is cross product
    forward = tangent / np.linalg.norm(tangent)
    up_norm = up / np.linalg.norm(up)
    right = np.cross(up_norm, forward)
    right = right / np.linalg.norm(right)
    forward = np.cross(right, up_norm)
    
    rot_matrix[:, 0] = right
    rot_matrix[:, 1] = up_norm
    rot_matrix[:, 2] = forward
    
    def transform_part(part, local_pos, rx, ry, rz):
        part_copy = o3d.geometry.TriangleMesh(part)
        
        # Local rotation
        R_loc = part_copy.get_rotation_matrix_from_xyz((rx, ry, rz))
        part_copy.rotate(R_loc, center=(0,0,0))
        
        # Translate to local offset
        part_copy.translate(local_pos)
        
        # Global rot & trans
        part_copy.rotate(rot_matrix, center=(0,0,0))
        part_copy.translate(pos)
        return part_copy

    # Swing angles based on phase (sin wave)
    arm_swing = math.sin(phase) * 0.8
    leg_swing = math.sin(phase) * 0.8
    
    # Local positions assuming bottom of feet is at y=0 local
    # Torso center is around y=1.1
    h_torso = transform_part(humanoid["torso"], [0, 1.1, 0], 0, 0, 0)
    h_head = transform_part(humanoid["head"], [0, 1.5, 0], 0, 0, 0)
    
    # Arms (pivot at top, so offset geometry)
    h_l_arm = transform_part(humanoid["l_arm"], [-0.25, 1.1, 0], arm_swing, 0, 0)
    h_r_arm = transform_part(humanoid["r_arm"], [0.25, 1.1, 0], -arm_swing, 0, 0)
    
    # Legs (pivot at hips)
    h_l_leg = transform_part(humanoid["l_leg"], [-0.1, 0.4, 0], -leg_swing, 0, 0)
    h_r_leg = transform_part(humanoid["r_leg"], [0.1, 0.4, 0], leg_swing, 0, 0)
    
    h_clear = transform_part(humanoid["clearance"], [0, RUNNER_HEIGHT/2.0, 0], 0, 0, 0)
    
    # Combine all into one mesh for easy updating in visualizer
    full_mesh = h_torso + h_head + h_l_arm + h_r_arm + h_l_leg + h_r_leg
    return full_mesh, h_clear

# ==================================================
# ANIMATION LOOP
# ==================================================
def run_simulation(mesh, route_pts, total_length):
    humanoid_base = build_humanoid()
    
    # Route LineSet for visualization
    route_ls = o3d.geometry.LineSet()
    route_ls.points = o3d.utility.Vector3dVector(route_pts)
    route_ls.lines = o3d.utility.Vector2iVector([[i, i+1] for i in range(len(route_pts)-1)])
    route_ls.paint_uniform_color([1, 0.8, 0]) # Yellow route
    
    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name="Synthetic Runner Simulation", width=1280, height=720)
    
    vis.add_geometry(mesh)
    vis.add_geometry(route_ls)
    
    # Init runner geometry
    start_pos = route_pts[0]
    tangent = route_pts[1] - route_pts[0]
    runner_mesh, clear_mesh = update_humanoid(humanoid_base, start_pos, tangent, np.array([0, -1, 0]), 0)
    
    vis.add_geometry(runner_mesh)
    
    # Save frames if requested or just run
    dist_traveled = 0.0
    current_idx = 0
    phase = 0.0
    
    last_time = time.time()
    
    frame_dir = OUT_DIR / "runner_frames"
    frame_dir.mkdir(exist_ok=True)
    frame_idx = 0
    
    # Setup Camera
    ctr = vis.get_view_control()
    
    print("Starting simulation... saving frames...")
    
    # We will simulate at 30 fps
    fps = 30.0
    dt = 1.0 / fps
    speed = RUNNER_SPEED
    
    while current_idx < len(route_pts) - 1:
        p1 = route_pts[current_idx]
        p2 = route_pts[current_idx + 1]
        seg_len = np.linalg.norm(p2 - p1)
        
        if seg_len == 0:
            current_idx += 1
            continue
            
        step = speed * dt
        if step >= seg_len:
            current_idx += 1
            dist_traveled += seg_len
            continue
            
        # Interpolate
        ratio = step / seg_len
        pos = p1 + (p2 - p1) * ratio
        route_pts[current_idx] = pos # advance p1 for next tick
        tangent = p2 - p1
        
        dist_traveled += step
        phase += step * 4.0 # swing speed
        
        new_runner, _ = update_humanoid(humanoid_base, pos, tangent, np.array([0, -1, 0]), phase)
        
        runner_mesh.vertices = new_runner.vertices
        runner_mesh.vertex_colors = new_runner.vertex_colors
        runner_mesh.vertex_normals = new_runner.vertex_normals
        
        vis.update_geometry(runner_mesh)
        
        # Follow camera logic
        # Place camera behind and above runner
        # Tangent is forward, UP is [0, -1, 0] (negative Y is up)
        # So camera pos = pos - tangent*offset + UP*offset
        forward = tangent / np.linalg.norm(tangent)
        cam_pos = pos - forward * 3.0 + np.array([0, -1, 0]) * 1.5
        
        cam = ctr.convert_to_pinhole_camera_parameters()
        cam.extrinsic = np.array([
            [right[0], up_vec[0], -forward[0], cam_pos[0]],
            [right[1], up_vec[1], -forward[1], cam_pos[1]],
            [right[2], up_vec[2], -forward[2], cam_pos[2]],
            [0, 0, 0, 1]
        ])
        
        # Open3D's lookat is weird, we just rely on standard view matrix construction
        # Wait, the best way in Open3D without breaking the view matrix is setting front, lookat, up
        ctr.set_lookat(pos.tolist())
        ctr.set_front((-forward + np.array([0, 1, 0])*0.5).tolist())
        ctr.set_up([0, -1, 0])
        
        vis.poll_events()
        vis.update_renderer()
        
        # Export frame
        vis.capture_screen_image(str(frame_dir / f"frame_{frame_idx:04d}.png"))
        frame_idx += 1
        
        if frame_idx > 300: # Limit frames for backend safety
            break

    vis.destroy_window()
    
    with open(OUT_DIR / "simulation_report.txt", "w") as f:
        f.write(f"""SYNTHETIC RUNNER SIMULATION
===========================

Mesh:
mesh_final.ply

Route:
Longest detected runnable route

Route length:
{total_length:.2f} model units

Scale:
UNKNOWN

Runner height:
{RUNNER_HEIGHT} model units

Runner radius:
{RUNNER_RADIUS} model units

Comfortable clearance:
{RAD_COMFORTABLE} model units

Speed:
{RUNNER_SPEED} model units/second

Simulation result:
COMPLETED
""")

if __name__ == "__main__":
    mesh, route_pts, length = reconstruct_route()
    run_simulation(mesh, route_pts, length)
    print("Done!")
