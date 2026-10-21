r"""
Color Transfer Pipeline
=======================
Transfers vertex colors from the original high-density mesh (3.3M vertices)
onto the cleaned Poisson mesh (14K vertices) using KD-tree nearest-neighbor
interpolation with inverse-distance weighting and bilateral smoothing.

Input:  C:\recon\chunks\lab\mesh_lab.ply          (original, colored)
        C:\recon\reconstruction_v2\mesh_best.ply   (Poisson, gray)
Output: C:\recon\reconstruction_v2\mesh_final_vtxcolor.ply
"""

import open3d as o3d
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import uniform_filter1d
import time
import os

OUT_DIR = r"C:\recon\reconstruction_v2"
ORIG_PATH = r"C:\recon\chunks\lab\mesh_lab.ply"
POISSON_PATH = os.path.join(OUT_DIR, "mesh_best.ply")
OUTPUT_PATH = os.path.join(OUT_DIR, "mesh_final_vtxcolor.ply")

K_NEIGHBORS = 32          # Number of nearest neighbors for color lookup
BILATERAL_SIGMA_S = 0.05  # Spatial sigma for bilateral filter (in mesh units)
BILATERAL_SIGMA_C = 0.1   # Color sigma for bilateral filter
BILATERAL_ITERS = 2       # Number of bilateral smoothing passes

def load_meshes():
    print("Loading original colored mesh...")
    t0 = time.time()
    orig = o3d.io.read_triangle_mesh(ORIG_PATH)
    print(f"  Loaded in {time.time()-t0:.1f}s: {len(orig.vertices):,} vertices, "
          f"has_colors={orig.has_vertex_colors()}")

    print("Loading Poisson mesh...")
    poisson = o3d.io.read_triangle_mesh(POISSON_PATH)
    print(f"  Loaded: {len(poisson.vertices):,} vertices")

    return orig, poisson

def transfer_colors_kdtree(orig, poisson):
    """Transfer colors using inverse-distance-weighted KNN from original mesh."""
    print(f"\n=== KD-Tree Color Transfer (K={K_NEIGHBORS}) ===")

    orig_verts = np.asarray(orig.vertices)
    orig_colors = np.asarray(orig.vertex_colors)  # Nx3, range [0,1]
    target_verts = np.asarray(poisson.vertices)

    print(f"  Building KD-tree from {len(orig_verts):,} source vertices...")
    t0 = time.time()
    tree = cKDTree(orig_verts)
    print(f"  KD-tree built in {time.time()-t0:.1f}s")

    print(f"  Querying {len(target_verts):,} target vertices with K={K_NEIGHBORS}...")
    t0 = time.time()
    dists, indices = tree.query(target_verts, k=K_NEIGHBORS, workers=-1)
    print(f"  Query completed in {time.time()-t0:.1f}s")

    # Inverse distance weighting
    # Avoid division by zero for exact matches
    dists = np.maximum(dists, 1e-10)
    weights = 1.0 / dists  # Shape: (N_target, K)
    weights_sum = weights.sum(axis=1, keepdims=True)
    weights_norm = weights / weights_sum  # Normalized weights

    # Gather source colors for all neighbors
    neighbor_colors = orig_colors[indices]  # Shape: (N_target, K, 3)

    # Weighted average
    new_colors = (weights_norm[:, :, np.newaxis] * neighbor_colors).sum(axis=1)

    print(f"  Color range: [{new_colors.min():.3f}, {new_colors.max():.3f}]")
    print(f"  Mean color: {new_colors.mean(axis=0)}")

    return new_colors

def bilateral_smooth_colors(mesh, colors, sigma_s, sigma_c, iterations):
    """Edge-preserving bilateral smoothing of vertex colors on mesh topology."""
    print(f"\n=== Bilateral Color Smoothing ({iterations} iterations) ===")

    verts = np.asarray(mesh.vertices)
    tris = np.asarray(mesh.triangles)

    # Build adjacency from triangles
    print("  Building vertex adjacency graph...")
    from collections import defaultdict
    adj = defaultdict(set)
    for tri in tris:
        adj[tri[0]].update([tri[1], tri[2]])
        adj[tri[1]].update([tri[0], tri[2]])
        adj[tri[2]].update([tri[0], tri[1]])

    smoothed = colors.copy()

    for it in range(iterations):
        new_colors = smoothed.copy()
        changed = 0

        for v_idx in range(len(verts)):
            neighbors = list(adj.get(v_idx, []))
            if not neighbors:
                continue

            v_pos = verts[v_idx]
            v_col = smoothed[v_idx]

            # Compute weights for each neighbor
            total_weight = 1.0  # Self-weight
            weighted_sum = v_col.copy()

            for n_idx in neighbors:
                n_pos = verts[n_idx]
                n_col = smoothed[n_idx]

                # Spatial weight
                spatial_dist = np.linalg.norm(v_pos - n_pos)
                w_s = np.exp(-(spatial_dist ** 2) / (2 * sigma_s ** 2))

                # Color similarity weight (edge-preserving)
                color_dist = np.linalg.norm(v_col - n_col)
                w_c = np.exp(-(color_dist ** 2) / (2 * sigma_c ** 2))

                w = w_s * w_c
                total_weight += w
                weighted_sum += w * n_col

            new_colors[v_idx] = weighted_sum / total_weight
            if not np.allclose(new_colors[v_idx], smoothed[v_idx], atol=1e-4):
                changed += 1

        smoothed = new_colors
        print(f"  Iteration {it+1}: {changed:,} vertices changed")

    return np.clip(smoothed, 0.0, 1.0)

def main():
    print("=" * 60)
    print("COLOR TRANSFER PIPELINE")
    print("=" * 60)

    orig, poisson = load_meshes()

    # Step 1: KD-tree color transfer
    new_colors = transfer_colors_kdtree(orig, poisson)

    # Step 2: Bilateral smoothing
    smoothed_colors = bilateral_smooth_colors(
        poisson, new_colors, BILATERAL_SIGMA_S, BILATERAL_SIGMA_C, BILATERAL_ITERS
    )

    # Step 3: Apply and save
    poisson.vertex_colors = o3d.utility.Vector3dVector(smoothed_colors)
    poisson.compute_vertex_normals()

    print(f"\nSaving to {OUTPUT_PATH}...")
    o3d.io.write_triangle_mesh(OUTPUT_PATH, poisson, write_vertex_colors=True)
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"  Saved: {file_size:,} bytes")

    # Verify
    check = o3d.io.read_triangle_mesh(OUTPUT_PATH)
    print(f"\nVerification:")
    print(f"  Vertices: {len(check.vertices):,}")
    print(f"  Faces: {len(check.triangles):,}")
    print(f"  Has vertex colors: {check.has_vertex_colors()}")
    if check.has_vertex_colors():
        vc = np.asarray(check.vertex_colors)
        print(f"  Color range: [{vc.min():.3f}, {vc.max():.3f}]")
        print(f"  Mean color: {vc.mean(axis=0)}")

    print("\n✓ Phase 1 complete: mesh_final_vtxcolor.ply")

if __name__ == "__main__":
    main()
