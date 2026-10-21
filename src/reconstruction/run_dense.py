import os
import subprocess
import sys
import glob
import shutil
import time

def run_fusion_subset(dense_dir):
    print("==============================================================================")
    print("Stereo Fusion (Subset of Images - Workaround for COLMAP 3.8)")
    print("==============================================================================")
    
    depth_maps_dir = os.path.join(dense_dir, "stereo", "depth_maps")
    all_depth_maps = sorted([f for f in os.listdir(depth_maps_dir) if f.endswith('.geometric.bin')])
    
    # Select every second image
    selected_depth_maps = set(all_depth_maps[::2])
    hidden_count = 0
    
    print("Temporarily hiding unselected depth maps to reduce cache thrashing...")
    for f in all_depth_maps:
        if f not in selected_depth_maps:
            src = os.path.join(depth_maps_dir, f)
            dst = os.path.join(depth_maps_dir, f + ".hidden")
            if os.path.exists(src):
                os.rename(src, dst)
                hidden_count += 1
                
    print(f"Total depth maps: {len(all_depth_maps)}")
    print(f"Selected for fusion: {len(selected_depth_maps)}")
    print(f"Hidden from COLMAP: {hidden_count}")
    
    fused_ply = os.path.join(dense_dir, "fused.ply")
    log_file = os.path.join(dense_dir, "colmap_dense.log")
    
    if os.path.exists(fused_ply):
        try:
            os.remove(fused_ply)
        except:
            pass
            
    cmd = [
        "colmap", "stereo_fusion",
        "--workspace_path", dense_dir,
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--StereoFusion.use_cache", "1",
        "--StereoFusion.cache_size", "8",
        "--StereoFusion.check_num_images", "15",
        "--output_path", fused_ply
    ]
    
    print(f"\nExecuting: {' '.join(cmd)}")
    print(f"Logs will be written to {log_file}")
    
    # We use Popen so we can run in the background if we want, but check_call is fine for autonomy
    try:
        with open(log_file, "w") as f_out:
            subprocess.check_call(cmd, stdout=f_out, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        print("\nERROR: COLMAP failed. Check the log file.")
    finally:
        print("\nRestoring hidden depth maps...")
        restored_count = 0
        for f in os.listdir(depth_maps_dir):
            if f.endswith(".hidden"):
                src = os.path.join(depth_maps_dir, f)
                dst = src.replace(".hidden", "")
                os.rename(src, dst)
                restored_count += 1
        print(f"Restored {restored_count} depth maps.")

    if os.path.exists(fused_ply) and os.path.getsize(fused_ply) > 1000:
        print("\n==============================================================================")
        print("Launching Post-Processing Pipeline")
        print("==============================================================================")
        import compare_meshing
        compare_meshing.main()
    else:
        print("\nSkipping post-processing because fused.ply was not generated successfully.")

if __name__ == "__main__":
    dense_dir = r"C:\recon\ds02\dense"
    run_fusion_subset(dense_dir)
