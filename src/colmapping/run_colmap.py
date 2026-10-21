import os
import subprocess
import sqlite3

def run_colmap(project_dir, image_dir):
    database_path = os.path.join(project_dir, "database.db")
    sparse_dir = os.path.join(project_dir, "sparse", "0")
    
    os.makedirs(os.path.join(project_dir, "sparse"), exist_ok=True)
    os.makedirs(sparse_dir, exist_ok=True)
    
    # Wait, the user wants f=604 for 100-degree FOV on 1440 width.
    # focal_length = width / (2 * tan(FOV / 2))
    # FOV = 100 -> tan(50 deg) = 1.19175 -> 1440 / (2 * 1.19175) = 604.15
    focal_length = 604.15
    camera_model = "OPENCV" # fx, fy, cx, cy, k1, k2, p1, p2
    
    print("==============================================================================")
    print("1. Feature Extraction")
    print("==============================================================================")
    cmd_extract = [
        "colmap", "feature_extractor",
        "--database_path", database_path,
        "--image_path", image_dir,
        "--ImageReader.single_camera", "1",
        "--ImageReader.camera_model", camera_model,
        "--ImageReader.camera_params", f"{focal_length},{focal_length},720,720,0,0,0,0",
        "--SiftExtraction.use_gpu", "1"
    ]
    subprocess.check_call(cmd_extract)
    
    print("\n==============================================================================")
    print("2. Sequential Matching")
    print("==============================================================================")
    cmd_match = [
        "colmap", "sequential_matcher",
        "--database_path", database_path,
        "--SequentialMatching.overlap", "10",
        "--SequentialMatching.loop_detection", "1",
        "--SequentialMatching.loop_detection_period", "20",
        "--SequentialMatching.loop_detection_num_images", "30",
        "--SiftMatching.use_gpu", "1"
    ]
    subprocess.check_call(cmd_match)
    
    print("\n==============================================================================")
    print("3. Mapping")
    print("==============================================================================")
    cmd_map = [
        "colmap", "mapper",
        "--database_path", database_path,
        "--image_path", image_dir,
        "--output_path", os.path.join(project_dir, "sparse")
    ]
    subprocess.check_call(cmd_map)

    print("\nDONE!")
    print(f"Check results in {os.path.join(project_dir, 'sparse')}")

if __name__ == "__main__":
    run_colmap(r"C:\recon\ds02", r"C:\recon\ds02\views")
