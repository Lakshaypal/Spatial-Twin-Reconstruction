import open3d as o3d
import numpy as np
import sys
import os

mesh_path = sys.argv[1]
out_path = sys.argv[2]

mesh = o3d.io.read_triangle_mesh(mesh_path)
mesh.compute_vertex_normals()

vis = o3d.visualization.Visualizer()
vis.create_window(visible=False, width=1920, height=1080)
vis.add_geometry(mesh)

opt = vis.get_render_option()
opt.mesh_show_back_face = True
opt.mesh_show_wireframe = False
opt.background_color = np.asarray([0.1, 0.1, 0.1])

# Adjust camera
ctr = vis.get_view_control()
ctr.set_zoom(0.8)

vis.poll_events()
vis.update_renderer()

vis.capture_screen_image(out_path)
vis.destroy_window()
print(f"Saved screenshot to {out_path}")