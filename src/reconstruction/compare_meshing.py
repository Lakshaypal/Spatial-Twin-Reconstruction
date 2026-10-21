import open3d as o3d
import numpy as np
import time
import os
import psutil
from scipy.spatial import cKDTree
from pathlib import Path
import json

def get_mem_mb():
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

def transfer_colors_kdtree(orig_verts, orig_colors, target_verts):
    print(f"  Building KD-tree from {len(orig_verts):,} source vertices...")
    tree = cKDTree(orig_verts)
    print(f"  Querying {len(target_verts):,} target vertices...")
    dists, indices = tree.query(target_verts, k=1, workers=-1)
    return orig_colors[indices]

def analyze_mesh(mesh, pcd, start_mem, name):
    print(f"\nAnalyzing {name} Mesh...")
    end_mem = get_mem_mb()
    mem_used = end_mem - start_mem
    
    verts = len(mesh.vertices)
    faces = len(mesh.triangles)
    
    # Components
    triangle_clusters, cluster_n_triangles, cluster_area = mesh.cluster_connected_triangles()
    num_components = len(cluster_n_triangles)
    
    isolated_pct = 0.0
    if num_components > 0:
        max_size = np.max(cluster_n_triangles)
        isolated_faces = np.sum(cluster_n_triangles[cluster_n_triangles < max_size * 0.01])
        isolated_pct = (isolated_faces / faces) * 100 if faces > 0 else 0.0

    # Coverage (approximate points represented by mesh)
    # Sample points from mesh to see how well it covers the original dense cloud
    try:
        sampled = mesh.sample_points_uniformly(number_of_points=len(pcd.points) // 10)
        dists = pcd.compute_point_cloud_distance(sampled)
        dists = np.asarray(dists)
        represented_pct = np.mean(dists < 0.05) * 100  # Within 5cm
    except:
        represented_pct = 0.0

    print(f"  Vertices: {verts:,}")
    print(f"  Triangles: {faces:,}")
    print(f"  Connected components: {num_components}")
    print(f"  Isolated fragments: {isolated_pct:.2f}%")
    print(f"  Dense points represented (approx): {represented_pct:.2f}%")
    print(f"  Memory usage: {mem_used:.1f} MB")
    
    return {
        "verts": verts,
        "faces": faces,
        "components": num_components,
        "isolated_pct": isolated_pct,
        "represented_pct": represented_pct,
        "memory_mb": mem_used
    }

def clean_topology(mesh):
    print("  Removing isolated components < 1% max size...")
    triangle_clusters, cluster_n_triangles, cluster_area = mesh.cluster_connected_triangles()
    triangle_clusters = np.asarray(triangle_clusters)
    cluster_n_triangles = np.asarray(cluster_n_triangles)

    if len(cluster_n_triangles) > 0:
        max_cluster_size = cluster_n_triangles.max()
        valid_clusters = np.where(cluster_n_triangles > max_cluster_size * 0.01)[0]
        triangles_to_remove = ~np.isin(triangle_clusters, valid_clusters)
        mesh.remove_triangles_by_mask(triangles_to_remove)
        mesh.remove_unreferenced_vertices()
    return mesh

def render_previews(mesh, out_dir):
    print("\nGenerating 12 high-resolution preview renders...")
    vis = o3d.visualization.Visualizer()
    vis.create_window(visible=False, width=1920, height=1080)
    vis.add_geometry(mesh)
    opt = vis.get_render_option()
    opt.background_color = np.asarray([0.1, 0.1, 0.15])
    opt.mesh_color_option = o3d.visualization.MeshColorOption.Color
    
    ctr = vis.get_view_control()
    ctr.set_zoom(0.8)
    
    # 12 angles around the Y axis, plus some pitch
    for i in range(12):
        vis.poll_events()
        vis.update_renderer()
        angle = (i / 12.0) * 360.0
        # simple rotation
        ctr.rotate(30.0, 0.0) # 30 pixels horizontally
        if i % 3 == 0:
            ctr.rotate(0.0, 15.0) # slightly up/down
        
        vis.poll_events()
        vis.update_renderer()
        
        img_path = str(out_dir / f"preview_{i:02d}.png")
        vis.capture_screen_image(img_path)
    
    vis.destroy_window()
    print("  Previews saved.")

def main():
    print("=" * 60)
    print("POST-PROCESSING PIPELINE: VALIDATION, MESHING, EXPORT")
    print("=" * 60)

    DENSE_DIR = Path(r"C:\recon\ds02\dense")
    FUSED_PLY = DENSE_DIR / "fused.ply"
    FINAL_DIR = DENSE_DIR / "final"
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading {FUSED_PLY}...")
    t0 = time.time()
    
    if not FUSED_PLY.exists():
        print(f"ERROR: {FUSED_PLY} does not exist.")
        return
        
    pcd = o3d.io.read_point_cloud(str(FUSED_PLY))
    raw_points_count = len(pcd.points)
    
    print("\n--- 1. Point Cloud Validation ---")
    if raw_points_count < 10000:
        print(f"FATAL: Point cloud has only {raw_points_count} points. Validation failed.")
        return
        
    bbox = pcd.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    has_colors = pcd.has_colors()
    has_normals = pcd.has_normals()
    
    print(f"Total point count: {raw_points_count:,}")
    print(f"Bounding box: {extent[0]:.2f} x {extent[1]:.2f} x {extent[2]:.2f}m")
    print(f"Colors present: {has_colors}")
    print(f"Normals present: {has_normals}")
    
    orig_verts = np.asarray(pcd.points)
    orig_colors = np.asarray(pcd.colors) if has_colors else None

    print("\nApplying slight voxel downsample (0.02m)...")
    pcd_down = pcd.voxel_down_sample(voxel_size=0.02)
    
    print("Applying Statistical Outlier Removal...")
    cl, ind = pcd_down.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd_clean = pcd_down.select_by_index(ind)
    cleaned_points_count = len(pcd_clean.points)
    outlier_percentage = (1 - (cleaned_points_count / len(pcd_down.points))) * 100
    print(f"Removed {outlier_percentage:.1f}% outliers. Cleaned points: {cleaned_points_count:,}")

    # Cluster validation
    labels = np.array(pcd_clean.cluster_dbscan(eps=0.2, min_points=10, print_progress=False))
    if len(labels) > 0:
        max_label = labels.max()
        print(f"Disconnected point clusters found: {max_label + 1}")
    else:
        print("Point clusters: 0")

    if not has_normals:
        print("Estimating normals...")
        pcd_clean.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        pcd_clean.orient_normals_consistent_tangent_plane(100)

    distances = pcd_clean.compute_nearest_neighbor_distance()
    avg_dist = np.mean(distances)
    print(f"Average point density (nearest neighbor spacing): {avg_dist:.4f}m")

    # ==========================
    # 2. Meshing Competition
    # ==========================
    print("\n--- 2. Meshing Algorithm Comparison ---")
    
    # BPA
    print("\n[A] Ball Pivoting Algorithm")
    start_mem = get_mem_mb()
    radii = [avg_dist, avg_dist * 2, avg_dist * 4, avg_dist * 8]
    t1 = time.time()
    mesh_bpa = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(pcd_clean, o3d.utility.DoubleVector(radii))
    bpa_time = time.time() - t1
    bpa_stats = analyze_mesh(mesh_bpa, pcd_clean, start_mem, "BPA")
    bpa_stats['time'] = bpa_time

    # Alpha Shapes
    print("\n[B] Alpha Shapes")
    start_mem = get_mem_mb()
    alpha = avg_dist * 4
    t2 = time.time()
    mesh_alpha = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd_clean, alpha)
    alpha_time = time.time() - t2
    alpha_stats = analyze_mesh(mesh_alpha, pcd_clean, start_mem, "Alpha")
    alpha_stats['time'] = alpha_time

    # Select Best Mesh Objectively
    # We want max represented points, min isolated fragmentation, and a reasonable triangle count without extreme bloat.
    # Score = represented_pct - isolated_pct 
    bpa_score = bpa_stats['represented_pct'] - (bpa_stats['isolated_pct'] * 2)
    alpha_score = alpha_stats['represented_pct'] - (alpha_stats['isolated_pct'] * 2)
    
    # Heavy penalty if algorithm completely failed to create surfaces
    if bpa_stats['faces'] < 1000: bpa_score = -999
    if alpha_stats['faces'] < 1000: alpha_score = -999

    print(f"\nObjective Scores (Representation - Fragmentation Penalty):")
    print(f"BPA Score: {bpa_score:.1f}")
    print(f"Alpha Score: {alpha_score:.1f}")

    if bpa_score >= alpha_score and bpa_score > -900:
        best_mesh = mesh_bpa
        best_name = "BPA"
        best_stats = bpa_stats
    elif alpha_score > bpa_score and alpha_score > -900:
        best_mesh = mesh_alpha
        best_name = "Alpha Shapes"
        best_stats = alpha_stats
    else:
        print("FATAL ERROR: Both meshing algorithms completely failed.")
        return

    print(f"\n=> WINNER: {best_name}")

    # ==========================
    # 3. Post-Processing & Export
    # ==========================
    print(f"\n--- 3. Finalization & Export ---")
    best_mesh = clean_topology(best_mesh)
    
    if orig_colors is not None:
        best_mesh.vertex_colors = o3d.utility.Vector3dVector(transfer_colors_kdtree(orig_verts, orig_colors, np.asarray(best_mesh.vertices)))
    else:
        best_mesh.paint_uniform_color([0.7, 0.7, 0.7])

    out_ply = FINAL_DIR / "mesh_final.ply"
    out_obj = FINAL_DIR / "mesh_final.obj"
    out_glb = FINAL_DIR / "mesh_final.glb"
    
    print(f"Saving {out_ply}...")
    o3d.io.write_triangle_mesh(str(out_ply), best_mesh)
    print(f"Saving {out_obj}...")
    o3d.io.write_triangle_mesh(str(out_obj), best_mesh)
    print(f"Saving {out_glb}...")
    o3d.io.write_triangle_mesh(str(out_glb), best_mesh)

    # Previews
    render_previews(best_mesh, FINAL_DIR)

    # Launch viewer via script
    print("\nLaunching viewer...")
    os.system(f"start cmd /c c:\\Users\\krris\\anaconda3\\python.exe c:\\Users\\krris\\OneDrive\\Documents\\FIFA 23\\Desktop\\version_17july\\viewer.py final")
    
    # Final Report
    report = f"""
============================================================
FINAL RECONSTRUCTION ENGINEERING REPORT
============================================================

1. Point Cloud Validation
-------------------------
Dense Points: {raw_points_count:,}
Outliers Removed: {outlier_percentage:.1f}%
Avg Point Density: {avg_dist:.4f}m
Disconnected Clusters: {labels.max() + 1 if len(labels) > 0 else 0}
Colors Retained: {has_colors}

2. Meshing Competition
-------------------------
Algorithm Chosen: {best_name}
Final Vertices: {best_stats['verts']:,}
Final Triangles: {best_stats['faces']:,}
Surface Coverage: {best_stats['represented_pct']:.1f}%
Isolated Fragmentation: {best_stats['isolated_pct']:.2f}%
Memory Peak (Meshing): {best_stats['memory_mb']:.1f} MB

3. Outputs Generated
-------------------------
{out_ply} ({os.path.getsize(out_ply)/(1024*1024):.1f} MB)
{out_obj} ({os.path.getsize(out_obj)/(1024*1024):.1f} MB)
{out_glb} ({os.path.getsize(out_glb)/(1024*1024):.1f} MB)
Plus 12 rendering previews in {FINAL_DIR}
"""
    with open(FINAL_DIR / "final_report.txt", "w") as f:
        f.write(report)
        
    print(report)

if __name__ == "__main__":
    main()
