import os
import subprocess
import sqlite3

def run_colmap(project_dir, image_dir):
    database_path = os.path.join(project_dir, "database.db")
    
    print("\n==============================================================================")
    print("2. Sequential Matching")
    print("==============================================================================")
    cmd_match = [
        "colmap", "sequential_matcher",
        "--database_path", database_path,
        "--SequentialMatching.overlap", "10",
        "--SequentialMatching.loop_detection", "0",
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
