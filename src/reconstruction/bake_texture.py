"""
Bake vertex colors from mesh_splatting_pano_final.ply into a texture atlas.
Exports: mesh_splatting_pano_textured.obj + mesh_splatting_pano_textured.mtl + mesh_splatting_pano_textured.png
Unity imports this as a standard textured mesh with full color.
"""
import numpy as np
import open3d as o3d
from PIL import Image
import os

INPUT_PLY = r"c:\Users\krris\OneDrive\Documents\FIFA 23\Desktop\version_17july\2_processing\outputs\mesh_splatting_pano\mesh_splatting_pano_final.ply"
OUTPUT_DIR = r"c:\Users\krris\OneDrive\Documents\FIFA 23\Desktop\version_17july\My project\Assets"

print("Loading mesh...")
mesh = o3d.io.read_triangle_mesh(INPUT_PLY)
print(f"  Vertices: {len(mesh.vertices)}")
print(f"  Triangles: {len(mesh.triangles)}")
print(f"  Has vertex colors: {mesh.has_vertex_colors()}")

if not mesh.has_vertex_colors():
    print("ERROR: No vertex colors found!")
    exit(1)

vertices = np.asarray(mesh.vertices)
triangles = np.asarray(mesh.triangles)
colors = np.asarray(mesh.vertex_colors)  # shape (N, 3), values 0-1

# Strategy: create a simple per-triangle texture atlas
# Each triangle gets a tiny patch in the texture, colored by its average vertex color.
# This is the simplest approach that preserves color in OBJ format.

num_tris = len(triangles)
# Pack triangles into a square grid of small patches
patches_per_row = int(np.ceil(np.sqrt(num_tris)))
patch_size = 4  # pixels per patch
tex_size = patches_per_row * patch_size

print(f"  Creating {tex_size}x{tex_size} texture atlas for {num_tris} triangles...")

# Create texture image
tex = np.zeros((tex_size, tex_size, 3), dtype=np.uint8)

# Create UV coordinates (one per vertex per triangle = 3 * num_tris)
uvs = []
obj_lines = ["# MeshSplatting Phase 2 - Textured Export\n"]
obj_lines.append(f"mtllib mesh_splatting_pano_textured.mtl\n")
obj_lines.append(f"usemtl textured_material\n\n")

# Write vertices
for v in vertices:
    obj_lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

obj_lines.append("\n")

# Write UVs and fill texture
uv_idx = 1
for i, tri in enumerate(triangles):
    row = i // patches_per_row
    col = i % patches_per_row

    # Average color of the three vertices
    avg_color = colors[tri].mean(axis=0)
    r, g, b = int(avg_color[0]*255), int(avg_color[1]*255), int(avg_color[2]*255)

    # Fill the patch with the average color
    py = row * patch_size
    px = col * patch_size
    tex[py:py+patch_size, px:px+patch_size] = [r, g, b]

    # UV coordinates (center of patch + small triangle)
    u_center = (col * patch_size + patch_size/2) / tex_size
    v_center = 1.0 - (row * patch_size + patch_size/2) / tex_size
    offset = (patch_size * 0.3) / tex_size

    uv1 = (u_center - offset, v_center - offset)
    uv2 = (u_center + offset, v_center - offset)
    uv3 = (u_center, v_center + offset)

    obj_lines.append(f"vt {uv1[0]:.6f} {uv1[1]:.6f}\n")
    obj_lines.append(f"vt {uv2[0]:.6f} {uv2[1]:.6f}\n")
    obj_lines.append(f"vt {uv3[0]:.6f} {uv3[1]:.6f}\n")

obj_lines.append("\n")

# Write faces with UV references
for i, tri in enumerate(triangles):
    uv_base = i * 3 + 1
    obj_lines.append(f"f {tri[0]+1}/{uv_base} {tri[1]+1}/{uv_base+1} {tri[2]+1}/{uv_base+2}\n")

# Write OBJ
obj_path = os.path.join(OUTPUT_DIR, "mesh_splatting_pano_textured.obj")
with open(obj_path, "w") as f:
    f.writelines(obj_lines)
print(f"  Wrote {obj_path}")

# Write MTL
mtl_path = os.path.join(OUTPUT_DIR, "mesh_splatting_pano_textured.mtl")
with open(mtl_path, "w") as f:
    f.write("newmtl textured_material\n")
    f.write("Ka 1.0 1.0 1.0\n")
    f.write("Kd 1.0 1.0 1.0\n")
    f.write("Ks 0.0 0.0 0.0\n")
    f.write("d 1.0\n")
    f.write("illum 1\n")
    f.write("map_Kd mesh_splatting_pano_textured.png\n")
print(f"  Wrote {mtl_path}")

# Write texture
tex_path = os.path.join(OUTPUT_DIR, "mesh_splatting_pano_textured.png")
Image.fromarray(tex).save(tex_path)
print(f"  Wrote {tex_path} ({tex_size}x{tex_size})")

print("\nDone! Unity will auto-import the OBJ with the texture applied.")
