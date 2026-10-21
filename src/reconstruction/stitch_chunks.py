import copy
import numpy as np
import open3d as o3d
import time

def preprocess_point_cloud(pcd, voxel_size):
    print(":: Downsampling point cloud with a voxel of %.3f." % voxel_size)
    pcd_down = pcd.voxel_down_sample(voxel_size)
    
    # Normally normals are already there, but let's ensure
    print(":: Estimating normals with search radius %.3f." % (voxel_size * 2))
    pcd_down.estimate_normals(
        o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 2, max_nn=30))
    
    print(":: Computing FPFH feature with search radius %.3f." % (voxel_size * 5))
    pcd_fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        pcd_down,
        o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 5, max_nn=100))
    return pcd_down, pcd_fpfh

def execute_global_registration(source_down, target_down, source_fpfh,
                                target_fpfh, voxel_size):
    distance_threshold = voxel_size * 1.5
    print(":: RANSAC global registration on downsampled point clouds.")
    print("   Distance threshold %.3f." % distance_threshold)
    result = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        source_down, target_down, source_fpfh, target_fpfh, True,
        distance_threshold,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        3, [
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(distance_threshold)
        ], o3d.pipelines.registration.RANSACConvergenceCriteria(100000, 0.999))
    return result

def refine_registration(source, target, source_fpfh, target_fpfh, voxel_size, initial_trans):
    distance_threshold = voxel_size * 0.4
    print(":: Point-to-plane ICP registration is applied on original point")
    print("   clouds to refine the alignment. Distance threshold %.3f." % distance_threshold)
    
    source.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 2, max_nn=30))
    target.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 2, max_nn=30))
    
    result = o3d.pipelines.registration.registration_icp(
        source, target, distance_threshold, initial_trans,
        o3d.pipelines.registration.TransformationEstimationPointToPlane())
    return result

if __name__ == "__main__":
    import os
    BASE_DIR = r"c:\Users\krris\OneDrive\Documents\FIFA 23\Desktop\version_17july"
    
    # Load point clouds for registration
    pc1_path = os.path.join(BASE_DIR, "2_processing", "exports", "mesh", "pointcloud_clean.ply")
    pc2_path = os.path.join(BASE_DIR, "pano1_processing_1fps", "export", "mesh", "pointcloud_clean.ply")
    
    print("Loading point clouds...")
    target_pc = o3d.io.read_point_cloud(pc1_path) # Chunk 1 is target (fixed)
    source_pc = o3d.io.read_point_cloud(pc2_path) # Chunk 2 is source (moving)
    
    # Calculate a suitable voxel size based on the bounding box
    bbox = target_pc.get_axis_aligned_bounding_box()
    voxel_size = bbox.get_extent().max() / 100.0  # adjust division as needed
    print(f"Computed voxel size: {voxel_size:.4f}")
    
    # Feature extraction
    t0 = time.time()
    source_down, source_fpfh = preprocess_point_cloud(source_pc, voxel_size)
    target_down, target_fpfh = preprocess_point_cloud(target_pc, voxel_size)
    
    # Global Registration
    result_ransac = execute_global_registration(source_down, target_down,
                                                source_fpfh, target_fpfh,
                                                voxel_size)
    print(f"Global Registration took {time.time() - t0:.2f}s")
    print(result_ransac)
    
    # ICP Refinement
    t1 = time.time()
    result_icp = refine_registration(source_down, target_down, source_fpfh, target_fpfh,
                                     voxel_size, result_ransac.transformation)
    print(f"ICP Refinement took {time.time() - t1:.2f}s")
    print(result_icp)
    print("Transformation is:")
    print(result_icp.transformation)
    
    # Load dense meshes
    print("\nLoading dense meshes to merge...")
    mesh1_path = os.path.join(BASE_DIR, "2_processing", "exports", "mesh", "room_mesh.ply")
    mesh2_path = os.path.join(BASE_DIR, "pano1_processing_1fps", "export", "mesh", "room_mesh.ply")
    
    mesh1 = o3d.io.read_triangle_mesh(mesh1_path)
    mesh2 = o3d.io.read_triangle_mesh(mesh2_path)
    
    # Transform chunk 2 mesh
    mesh2.transform(result_icp.transformation)
    
    # Merge meshes
    master_mesh = mesh1 + mesh2
    
    # Save master mesh
    out_path = os.path.join(BASE_DIR, "2_processing", "master_mesh.ply")
    o3d.io.write_triangle_mesh(out_path, master_mesh, write_vertex_colors=True)
    print(f"✅ Successfully stitched chunks together! Saved to {out_path}")
