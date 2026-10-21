import open3d as o3d
import numpy as np
import os
import time
from pathlib import Path

def setup_camera(vis, center, eye, up):
    ctr = vis.get_view_control()
    ctr.set_lookat(center)
    ctr.set_front(eye)
    ctr.set_up(up)
    ctr.set_zoom(0.8)
    vis.poll_events()
    vis.update_renderer()

def main():
    print("=" * 60)
    print("AUTHENTIC RENDER GENERATOR")
    print("=" * 60)

    FINAL_MESH = Path(r"C:\recon\ds02\dense\final\mesh_final.ply")
    RENDER_DIR = Path(r"C:\recon\ds02\final_visualization")
    RENDER_DIR.mkdir(parents=True, exist_ok=True)

    if not FINAL_MESH.exists():
        print(f"ERROR: Mesh not found at {FINAL_MESH}")
        return

    print("Loading mesh...")
    mesh = o3d.io.read_triangle_mesh(str(FINAL_MESH))
    if not mesh.has_vertex_normals():
        mesh.compute_vertex_normals()
    
    # Calculate bounding box for camera positioning
    bbox = mesh.get_axis_aligned_bounding_box()
    center = bbox.get_center()
    extent = bbox.get_extent()
    max_extent = max(extent)

    # Move mesh to origin for easier camera rotation
    mesh.translate(-center)

    print("Setting up Offscreen Renderer...")
    width, height = 1920, 1080
    vis = o3d.visualization.Visualizer()
    vis.create_window(width=width, height=height, visible=False)
    vis.add_geometry(mesh)
    
    opt = vis.get_render_option()
    opt.background_color = np.asarray([0.1, 0.1, 0.15])
    opt.mesh_show_back_face = True
    
    # Standard Views (Eye vectors, Up vectors)
    views = {
        "Front": ([0, 0, 1], [0, 1, 0]),
        "Back": ([0, 0, -1], [0, 1, 0]),
        "Left": ([-1, 0, 0], [0, 1, 0]),
        "Right": ([1, 0, 0], [0, 1, 0]),
        "Top": ([0, 1, 0], [0, 0, 1]),
        "Isometric": ([1, 1, 1], [0, 1, 0])
    }
    
    for name, (eye, up) in views.items():
        print(f"Rendering {name} view...")
        # Normalize eye vector
        eye_dir = np.array(eye, dtype=float)
        eye_dir /= np.linalg.norm(eye_dir)
        
        setup_camera(vis, [0, 0, 0], eye_dir, up)
        
        # Give it a moment to render
        time.sleep(0.1)
        
        out_path = RENDER_DIR / f"render_{name.lower()}.png"
        vis.capture_screen_image(str(out_path), do_render=True)
        print(f"  Saved {out_path}")

    vis.destroy_window()
    print("\nDONE! Renders saved to", RENDER_DIR)

if __name__ == "__main__":
    main()