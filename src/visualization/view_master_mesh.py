import open3d as o3d
import os

BASE_DIR = r"c:\Users\krris\OneDrive\Documents\FIFA 23\Desktop\version_17july"
out_path = os.path.join(BASE_DIR, "2_processing", "master_mesh.ply")

print(f"Loading stitched mesh from {out_path}...")
master_mesh = o3d.io.read_triangle_mesh(out_path)

if len(master_mesh.vertices) == 0:
    print("Mesh is empty! Did stitching fail?")
else:
    print(f"Mesh loaded: {len(master_mesh.vertices)} vertices, {len(master_mesh.triangles)} faces.")
    print("Opening 3D viewer. Use your mouse to rotate and zoom.")
    o3d.visualization.draw_geometries([master_mesh])
