import open3d as o3d
import numpy as np
import os
from pathlib import Path

RECON_DIR = Path(r"C:\recon")
V2_DIR = RECON_DIR / "reconstruction_v2"
RENDER_DIR = V2_DIR / "before_after"
RENDER_DIR.mkdir(parents=True, exist_ok=True)

MESH_FILE = V2_DIR / "mesh_best.ply"
if not MESH_FILE.exists():
    print("Mesh not found!")
    exit(1)

print(f"Loading {MESH_FILE.name} for rendering...")
mesh = o3d.io.read_triangle_mesh(str(MESH_FILE))
mesh.compute_vertex_normals()

# Setup rendering
width = 3840
height = 2160
render = o3d.visualization.rendering.OffscreenRenderer(width, height)
render.scene.set_background([0.1, 0.1, 0.15, 1.0])

mat = o3d.visualization.rendering.MaterialRecord()
mat.shader = "defaultLit"

if mesh.has_vertex_colors():
    mat.base_color = [1.0, 1.0, 1.0, 1.0]
else:
    mat.base_color = [0.8, 0.8, 0.8, 1.0]

render.scene.add_geometry("mesh", mesh, mat)
render.scene.camera.set_projection(o3d.visualization.rendering.Camera.Perspective, 60.0, width/height, 0.1, 1000.0)

# Calculate views based on bounding box
bbox = mesh.get_axis_aligned_bounding_box()
center = bbox.get_center()
extent = bbox.get_extent()
max_extent = max(extent)
distance = max_extent * 1.5

views = [
    ("front", [center[0], center[1], center[2] + distance]),
    ("back", [center[0], center[1], center[2] - distance]),
    ("left", [center[0] - distance, center[1], center[2]]),
    ("right", [center[0] + distance, center[1], center[2]]),
    ("top", [center[0], center[1] + distance, center[2]]),
    ("bottom", [center[0], center[1] - distance, center[2]]),
    ("isometric", [center[0] + distance*0.7, center[1] + distance*0.7, center[2] + distance*0.7]),
    ("birdseye", [center[0], center[1] + distance*0.8, center[2] + distance*0.5])
]

# Configure lighting
render.scene.scene.set_sun_light([0.7, -0.7, -0.7], [1.0, 1.0, 1.0], 100000)
render.scene.scene.enable_sun_light(True)

for i, (name, eye) in enumerate(views):
    print(f"Rendering {name}...")
    render.setup_camera(60.0, center, eye, [0, 1, 0])
    img = render.render_to_image()
    o3d.io.write_image(str(RENDER_DIR / f"{i+1:02d}_{name}.png"), img)

# Wireframe
mat.shader = "unlitLine"
render.scene.modify_geometry_material("mesh", mat)
print("Rendering wireframe...")
img = render.render_to_image()
o3d.io.write_image(str(RENDER_DIR / "09_wireframe.png"), img)

# Normals
mat.shader = "normals"
render.scene.modify_geometry_material("mesh", mat)
print("Rendering normals...")
img = render.render_to_image()
o3d.io.write_image(str(RENDER_DIR / "10_normals.png"), img)

print("Rendering complete!")
