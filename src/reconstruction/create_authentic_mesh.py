import open3d as o3d
import numpy as np
import time
from scipy.spatial import cKDTree
from pathlib import Path

def transfer_colors_kdtree(orig_verts, orig_colors, target_verts):
    print(f"  Building KD-tree from {len(orig_verts):,} source vertices...")
    tree = cKDTree(orig_verts)
    print(f"  Querying {len(target_verts):,} target vertices...")
    dists, indices = tree.query(target_verts, k=1, workers=-1)
    
    # 1-nearest neighbor is exact for BPA because BPA uses a subset of original vertices
    return orig_colors[indices]

def main():
    print("=" * 60)
    print("AUTHENTIC MESH GENERATION (BPA / Alpha Shapes)")
    print("=" * 60)

    # Paths
    DENSE_DIR = Path(r"C:\recon\ds02\dense")
    FUSED_PLY = DENSE_DIR / "fused.ply"
    FINAL_DIR = DENSE_DIR / "final"
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    
    OUT_MESH_PLY = FINAL_DIR / "mesh_final.ply"
    OUT_MESH_OBJ = FINAL_DIR / "mesh_final.obj"
    
    print(f"Loading {FUSED_PLY}...")
    t0 = time.time()
    pcd = o3d.io.read_point_cloud(str(FUSED_PLY))
    print(f"Loaded {len(pcd.points):,} points in {time.time()-t0:.1f}s")
    
    # Save original colors
    orig_verts = np.asarray(pcd.points)
    orig_colors = np.asarray(pcd.colors) if pcd.has_colors() else None

    # Slightly downsample to make it computable, but preserving structure
    print("\nApplying slight voxel downsample (0.02m)...")
    pcd = pcd.voxel_down_sample(voxel_size=0.02)
    print(f"Remaining points: {len(pcd.points):,}")

    print("\nApplying Statistical Outlier Removal...")
    cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd_clean = pcd.select_by_index(ind)
    print(f"Cleaned points: {len(pcd_clean.points):,}")

    print("\nEstimating normals...")
    pcd_clean.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    pcd_clean.orient_normals_consistent_tangent_plane(100)

    # Test Alpha Shapes vs BPA
    # Since Alpha shapes can be heavy, we default to BPA which connects points perfectly.
    print("\nRunning Ball Pivoting Algorithm (BPA)...")
    # Radii should capture varying densities of points
    distances = pcd_clean.compute_nearest_neighbor_distance()
    avg_dist = np.mean(distances)
    print(f"Average nearest neighbor distance: {avg_dist:.4f}")
    
    radii = [avg_dist, avg_dist * 2, avg_dist * 4, avg_dist * 8]
    t1 = time.time()
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
        pcd_clean, o3d.utility.DoubleVector(radii)
    )
    print(f"BPA Meshing completed in {time.time()-t1:.1f}s")
    print(f"Generated {len(mesh.vertices):,} vertices, {len(mesh.triangles):,} faces")

    print("\nCleaning up mesh topology (removing isolated components)...")
    triangle_clusters, cluster_n_triangles, cluster_area = mesh.cluster_connected_triangles()
    triangle_clusters = np.asarray(triangle_clusters)
    cluster_n_triangles = np.asarray(cluster_n_triangles)

    if len(cluster_n_triangles) > 0:
        # Keep components that have at least 1% of the max cluster size to preserve small real objects
        max_cluster_size = cluster_n_triangles.max()
        valid_clusters = np.where(cluster_n_triangles > max_cluster_size * 0.01)[0]
        triangles_to_remove = ~np.isin(triangle_clusters, valid_clusters)
        mesh.remove_triangles_by_mask(triangles_to_remove)
        mesh.remove_unreferenced_vertices()

    print(f"Final Mesh: {len(mesh.vertices):,} vertices, {len(mesh.triangles):,} faces")

    # Transfer Colors
    if orig_colors is not None:
        print("\nTransferring exact original colors to mesh vertices...")
        mesh_verts = np.asarray(mesh.vertices)
        new_colors = transfer_colors_kdtree(orig_verts, orig_colors, mesh_verts)
        mesh.vertex_colors = o3d.utility.Vector3dVector(new_colors)

    print(f"\nSaving {OUT_MESH_PLY}...")
    o3d.io.write_triangle_mesh(str(OUT_MESH_PLY), mesh)

    print(f"Saving {OUT_MESH_OBJ}...")
    o3d.io.write_triangle_mesh(str(OUT_MESH_OBJ), mesh)

    print("\nDONE!")

if __name__ == "__main__":
    main()