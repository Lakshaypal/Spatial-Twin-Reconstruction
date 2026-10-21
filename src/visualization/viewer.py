"""
Reconstruction Viewer - Open3D / Trimesh Python Backend
========================================================
Professional 3D mesh viewer with automatic cleanup.

Cleanup (visual only, original file untouched):
  - Isolates largest connected component
  - Removes fragments < 500 triangles
  - Removes statistical outlier vertices
  - Centers camera on clean mesh

Usage:
    python viewer.py                     # Auto-load interiorB (smallest)
    python viewer.py corridor            # Load corridor chunk
    python viewer.py outdoor lab         # Load multiple (first opens)
    python viewer.py list                # List all meshes
    python viewer.py <path.ply>          # Load any PLY directly

READ-ONLY: Does NOT modify any files in C:\\recon.
"""

import sys
import os

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from pathlib import Path

RECON = Path(r"C:\recon")

MESHES = {
    "corridor":   RECON / "chunks" / "corridor" / "mesh_corridor.ply",
    "outdoor":    RECON / "chunks" / "outdoor"  / "mesh_outdoor.ply",
    "lab":        RECON / "chunks" / "lab"       / "mesh_lab.ply",
    "interiorB":  RECON / "chunks" / "interiorB" / "mesh_interiorB.ply",
    "combined":   RECON / "combined" / "runA_combined.ply",
    "crop1":      RECON / "cropped_meshes" / "corridor" / "frame_00705.ply",
    "crop2":      RECON / "cropped_meshes" / "corridor" / "frame_00745.ply",
    "crop3":      RECON / "cropped_meshes" / "corridor" / "frame_00844.ply",
    "insp_corridor": RECON / "inspection" / "corridor" / "_render_copy.ply",
    "insp_lab":   RECON / "inspection" / "lab" / "_render_copy.ply",
}


def list_meshes():
    print("\n+================================================================+")
    print("|  RECONSTRUCTION MESH INVENTORY                                 |")
    print("+================================================================+")
    for name, path in MESHES.items():
        exists = path.exists()
        sz = f"{path.stat().st_size/1e6:>8.1f} MB" if exists else "   MISSING"
        mk = "[x]" if exists else "[ ]"
        print(f"|  {mk}  {name:<18s}  {sz}  |")
    print("+================================================================+\n")


def cleanup_open3d(mesh):
    """Visual cleanup: isolate largest component, remove outliers."""
    import open3d as o3d
    import numpy as np

    print("  [Cleanup] Analyzing connected components...")
    tri_clusters, cluster_n_tri, _ = mesh.cluster_connected_triangles()
    tri_clusters = np.asarray(tri_clusters)
    cluster_n_tri = np.asarray(cluster_n_tri)

    total_tris = len(mesh.triangles)
    n_clusters = len(cluster_n_tri)
    largest_idx = cluster_n_tri.argmax()
    largest_count = cluster_n_tri[largest_idx]
    pct = largest_count / total_tris * 100

    print(f"  [Cleanup] {n_clusters:,} components found")
    print(f"  [Cleanup] Largest: {largest_count:,} / {total_tris:,} faces ({pct:.1f}%)")

    # Keep only components >= 500 triangles (or the largest)
    keep_mask = np.zeros(total_tris, dtype=bool)
    for i, count in enumerate(cluster_n_tri):
        if count >= 500 or i == largest_idx:
            keep_mask[tri_clusters == i] = True

    removed = total_tris - keep_mask.sum()
    print(f"  [Cleanup] Removing {removed:,} fragment faces")

    mesh_clean = mesh.select_by_index(
        np.where(keep_mask)[0], cleanup=False
    ) if hasattr(mesh, 'select_by_index') else mesh

    # Fallback: manual triangle removal
    if removed > 0:
        triangles = np.asarray(mesh.triangles)
        mesh.triangles = o3d.utility.Vector3iVector(triangles[keep_mask])
        mesh.remove_unreferenced_vertices()

    # Statistical outlier removal on vertices
    print("  [Cleanup] Removing statistical outliers...")
    pcd_temp = o3d.geometry.PointCloud(mesh.vertices)
    _, inlier_idx = pcd_temp.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    before_v = len(mesh.vertices)

    # Keep only triangles whose vertices are all inliers
    inlier_set = set(inlier_idx)
    triangles = np.asarray(mesh.triangles)
    tri_mask = np.array([
        triangles[i, 0] in inlier_set and
        triangles[i, 1] in inlier_set and
        triangles[i, 2] in inlier_set
        for i in range(len(triangles))
    ])
    mesh.triangles = o3d.utility.Vector3iVector(triangles[tri_mask])
    mesh.remove_unreferenced_vertices()
    after_v = len(mesh.vertices)
    print(f"  [Cleanup] Outliers: {before_v - after_v:,} vertices removed")

    mesh.compute_vertex_normals()
    return mesh


def view_open3d(mesh_path, mesh_name):
    try:
        import open3d as o3d
        print(f"  [Open3D {o3d.__version__}] Loading...")
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))

        if not mesh.has_vertex_normals():
            mesh.compute_vertex_normals()

        # Cleanup (visual copy only — original file untouched)
        mesh = cleanup_open3d(mesh)

        v = len(mesh.vertices)
        f = len(mesh.triangles)
        hc = mesh.has_vertex_colors()
        bb = mesh.get_axis_aligned_bounding_box()

        print(f"\n  Mesh: {mesh_name}")
        print(f"  File: {mesh_path}")
        print(f"  Vertices: {v:,}")
        print(f"  Faces: {f:,}")
        print(f"  Vertex colors: {hc}")
        print(f"  BBox min: [{bb.min_bound[0]:.2f}, {bb.min_bound[1]:.2f}, {bb.min_bound[2]:.2f}]")
        print(f"  BBox max: [{bb.max_bound[0]:.2f}, {bb.max_bound[1]:.2f}, {bb.max_bound[2]:.2f}]")

        # Visualizer
        vis = o3d.visualization.VisualizerWithKeyCallback()
        vis.create_window(window_name=f"RECON VIEWER - {mesh_name}", width=1600, height=1000)
        vis.add_geometry(mesh)

        opt = vis.get_render_option()
        opt.background_color = [0.04, 0.06, 0.12]
        opt.point_size = 2.0
        opt.show_coordinate_frame = True
        opt.mesh_show_wireframe = False
        opt.mesh_show_back_face = True
        opt.light_on = True

        # Fit camera to cleaned mesh
        ctr = vis.get_view_control()
        ctr.set_zoom(0.45)

        # Keyboard shortcuts
        vis.register_key_callback(ord('W'), lambda v: setattr(v.get_render_option(), 'mesh_show_wireframe',
            not v.get_render_option().mesh_show_wireframe) or False)

        def toggle_normals(v):
            o = v.get_render_option()
            if o.mesh_color_option == o3d.visualization.MeshColorOption.Normal:
                o.mesh_color_option = (o3d.visualization.MeshColorOption.Color if hc
                                       else o3d.visualization.MeshColorOption.Default)
            else:
                o.mesh_color_option = o3d.visualization.MeshColorOption.Normal
            return False
        vis.register_key_callback(ord('N'), toggle_normals)

        for key, front, up in [
            (ord('1'), [0, 0, -1], [0, -1, 0]),
            (ord('2'), [0, -1, 0], [0, 0, -1]),
            (ord('3'), [1, 0, 0],  [0, -1, 0]),
            (ord('4'), [-1, 0, 0], [0, -1, 0]),
        ]:
            f_val, u_val = front, up
            vis.register_key_callback(key, lambda v, f=f_val, u=u_val: (
                v.get_view_control().set_front(f),
                v.get_view_control().set_up(u),
                v.get_view_control().set_zoom(0.45),
                False)[-1])

        print("\n  Controls:")
        print("    Mouse drag = Orbit   |   Scroll = Zoom   |   Shift+drag = Pan")
        print("    W = Wireframe   N = Normals   1-4 = View presets")
        print("    Q / Esc = Quit\n")

        vis.run()
        vis.destroy_window()
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  Open3D error: {e}")
        return False


def view_trimesh(mesh_path, mesh_name):
    try:
        import trimesh
        print(f"  [Trimesh {trimesh.__version__}] Loading...")
        mesh = trimesh.load(str(mesh_path))
        if hasattr(mesh, 'vertices'):
            print(f"  Vertices: {len(mesh.vertices):,}")
        if hasattr(mesh, 'faces'):
            print(f"  Faces: {len(mesh.faces):,}")
        mesh.show()
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  Trimesh error: {e}")
        return False


def main():
    print()
    print("  +=====================================================+")
    print("  |   RECONSTRUCTION VIEWER - Python Backend            |")
    print("  |   READ-ONLY - no files modified                     |")
    print("  +=====================================================+")
    print()

    arg = sys.argv[1] if len(sys.argv) > 1 else "interiorB"

    if arg == "list":
        list_meshes()
        return

    if arg in MESHES:
        mesh_path, mesh_name = MESHES[arg], arg
    elif os.path.isfile(arg):
        mesh_path, mesh_name = Path(arg), Path(arg).stem
    else:
        print(f"  Unknown: '{arg}'")
        list_meshes()
        return

    if not mesh_path.exists():
        print(f"  ERROR: Not found: {mesh_path}")
        return

    sz = mesh_path.stat().st_size / 1e6
    print(f"  Selected: {mesh_name}  ({sz:.1f} MB)")
    print(f"  Path:     {mesh_path}")
    print()

    if view_open3d(mesh_path, mesh_name):
        return
    print("  Open3D not available, trying Trimesh...")
    if view_trimesh(mesh_path, mesh_name):
        return
    print()
    print("  +=====================================================+")
    print("  |  No 3D library installed!                           |")
    print("  |  Use: pip install open3d                            |")
    print("  |  Or run launch_viewer.bat for the browser viewer    |")
    print("  +=====================================================+")
    print()


if __name__ == "__main__":
    main()
