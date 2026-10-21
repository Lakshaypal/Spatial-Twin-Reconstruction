import os
import subprocess
import open3d as o3d
import time

def verify_chunk(ply_path):
    if not os.path.exists(ply_path):
        return False, "File does not exist"
    try:
        pcd = o3d.io.read_point_cloud(ply_path)
        if len(pcd.points) < 100:
            return False, f"Too few points: {len(pcd.points)}"
        if not pcd.has_colors():
            return False, "No RGB colors present"
        bbox = pcd.get_axis_aligned_bounding_box()
        if bbox.volume() <= 0:
            return False, "Invalid bounding box"
        return True, f"Valid ({len(pcd.points):,} points)"
    except Exception as e:
        return False, f"Corruption: {str(e)}"

def run_chunked_fusion(dense_dir):
    print("==============================================================================")
    print("Stereo Fusion (Chunked to prevent Cache Thrashing)")
    print("==============================================================================")
    
    # Overlapping chunks based on scene extents
    chunks = [
        {"name": "chunk_1", "min": "-130 -45 -45", "max": "-27 15 35"},
        {"name": "chunk_2", "min": "-37 -45 -45", "max": "65 15 35"},
        {"name": "chunk_3", "min": "-130 -45 24", "max": "-27 15 105"},
        {"name": "chunk_4", "min": "-37 -45 24", "max": "65 15 105"}
    ]
    
    chunk_files = []
    
    for i, chunk in enumerate(chunks):
        out_ply = os.path.join(dense_dir, f"{chunk['name']}.ply")
        log_file = os.path.join(dense_dir, f"colmap_{chunk['name']}.log")
        bbox_file = os.path.join(dense_dir, f"{chunk['name']}_bbox.txt")
        chunk_files.append(out_ply)
        
        with open(bbox_file, "w", encoding="ascii") as f_bbox:
            f_bbox.write(f"{chunk['min']} {chunk['max']}\n")
            
        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            print(f"\n---> Processing {chunk['name']} (Chunk {i+1}/{len(chunks)}) - Attempt {attempt+1}")
            
            if os.path.exists(out_ply):
                valid, msg = verify_chunk(out_ply)
                if valid:
                    print(f"Skipping: Chunk verified successfully. {msg}")
                    success = True
                    break
                else:
                    print(f"Existing chunk failed verification: {msg}. Retrying...")
                    os.remove(out_ply)
            
            print(f"Bounding Box: Min({chunk['min']}) Max({chunk['max']})")
            
            cmd = [
                "colmap", "stereo_fusion",
                "--workspace_path", dense_dir,
                "--workspace_format", "COLMAP",
                "--input_type", "geometric",
                "--StereoFusion.use_cache", "1",
                "--StereoFusion.cache_size", "8",
                "--bbox_path", bbox_file,
                "--output_path", out_ply
            ]
            
            try:
                with open(log_file, "w") as f_out:
                    subprocess.check_call(cmd, stdout=f_out, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                print("COLMAP returned an error. Check log.")
                continue
                
            valid, msg = verify_chunk(out_ply)
            if valid:
                print(f"Finished {chunk['name']} successfully. {msg}")
                success = True
                break
            else:
                print(f"Verification failed after generation: {msg}")
                
        if not success:
            print(f"\nFATAL ERROR: Failed to generate {chunk['name']} after {max_retries} attempts.")
            return

    print("\n==============================================================================")
    print("Merging Chunks")
    print("==============================================================================")
    
    merged_pcd = o3d.geometry.PointCloud()
    for cf in chunk_files:
        print(f"Loading {cf}...")
        pcd = o3d.io.read_point_cloud(cf)
        merged_pcd += pcd
            
    print("Applying downsample to remove duplicated points at chunk seams...")
    merged_pcd = merged_pcd.voxel_down_sample(voxel_size=0.005)
    
    final_out = os.path.join(dense_dir, "fused.ply")
    print(f"Saving final merged point cloud to {final_out}...")
    o3d.io.write_point_cloud(final_out, merged_pcd)
    
    print("\nDONE! Chunked stereo fusion is fully complete.")
    
    print("\n==============================================================================")
    print("Launching Post-Processing Pipeline")
    print("==============================================================================")
    # Import the actual comparison script and run it
    import compare_meshing
    compare_meshing.main()

if __name__ == "__main__":
    run_chunked_fusion(r"C:\recon\ds02\dense")
