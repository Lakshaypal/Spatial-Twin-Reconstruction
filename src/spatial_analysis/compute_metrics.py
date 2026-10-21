import open3d as o3d
import numpy as np
import time
import json
import sys
import os

def compute_metrics(original_path, new_path):
    print(f"Loading {original_path}...")
    orig_mesh = o3d.io.read_triangle_mesh(original_path)
    print(f"Loading {new_path}...")
    new_mesh = o3d.io.read_triangle_mesh(new_path)
    
    metrics = {
        'original': {
            'vertices': len(orig_mesh.vertices),
            'faces': len(orig_mesh.triangles),
            'is_watertight': orig_mesh.is_watertight(),
            'bbox_volume': orig_mesh.get_axis_aligned_bounding_box().volume()
        },
        'new': {
            'vertices': len(new_mesh.vertices),
            'faces': len(new_mesh.triangles),
            'is_watertight': new_mesh.is_watertight(),
            'bbox_volume': new_mesh.get_axis_aligned_bounding_box().volume()
        }
    }
    
    print("Computing metrics...")
    
    # Connected components
    try:
        orig_cluster_idx, orig_cluster_counts, _ = orig_mesh.cluster_connected_triangles()
        metrics['original']['connected_components'] = len(orig_cluster_counts)
    except:
        metrics['original']['connected_components'] = "Error"
        
    try:
        new_cluster_idx, new_cluster_counts, _ = new_mesh.cluster_connected_triangles()
        metrics['new']['connected_components'] = len(new_cluster_counts)
    except:
        metrics['new']['connected_components'] = "Error"
        
    # Surface area
    try:
        metrics['original']['surface_area'] = orig_mesh.get_surface_area()
        metrics['new']['surface_area'] = new_mesh.get_surface_area()
    except:
        pass

    print("Computing distance metrics...")
    
    try:
        print("Sampling points on Original Mesh...")
        orig_pcd = orig_mesh.sample_points_uniformly(number_of_points=100000)
        print("Sampling points on New Mesh...")
        new_pcd = new_mesh.sample_points_uniformly(number_of_points=100000)
        
        print("Computing distance from Original -> New...")
        dists_to_new = orig_pcd.compute_point_cloud_distance(new_pcd)
        dists_to_new = np.asarray(dists_to_new)
        
        print("Computing distance from New -> Original...")
        dists_to_orig = new_pcd.compute_point_cloud_distance(orig_pcd)
        dists_to_orig = np.asarray(dists_to_orig)
        
        metrics['comparison'] = {
            'hausdorff_distance': float(max(dists_to_new.max(), dists_to_orig.max())),
            'rms_deviation': float(np.sqrt(np.mean(dists_to_new**2))),
            'mean_deviation': float(np.mean(dists_to_new))
        }
    except Exception as e:
        print("Error computing distances:", e)
        metrics['comparison'] = {'error': str(e)}
        
    # Ensure directory exists
    os.makedirs('C:/recon/reconstruction_v2', exist_ok=True)
    
    with open('C:/recon/reconstruction_v2/metrics_report.json', 'w') as f:
        json.dump(metrics, f, indent=4)
        
    print("\nMetrics Report:")
    print(json.dumps(metrics, indent=4))
    print("\nFinished writing metrics.")

if __name__ == "__main__":
    orig = r"C:\recon\chunks\lab\mesh_lab.ply"
    new = r"C:\recon\reconstruction_v2\mesh_best.ply"
    
    if not os.path.exists(orig):
        orig = r"c:\Users\krris\OneDrive\Documents\FIFA 23\Desktop\version_17july\mesh_outdoor.ply"
        
    compute_metrics(orig, new)
