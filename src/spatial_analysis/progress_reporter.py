import os
import re
import time
import json
import psutil

DENSE_DIR = r"C:\recon\ds02\dense"
STATE_FILE = os.path.join(DENSE_DIR, "reporter_state.json")
LOG_FILE = os.path.join(DENSE_DIR, "colmap_dense.log")

def main():
    print("==============================================================")
    print("Measurable Progress Report (Subset Fusion)")
    print("==============================================================")
    
    if os.path.exists(os.path.join(DENSE_DIR, "final", "mesh_final.glb")):
        print("Pipeline is completely finished! Check the 'final' folder.")
        return

    # Process Metrics
    p_cpu = 0.0
    p_ram = 0.0
    p_runtime = 0.0
    
    colmap_proc = None
    for proc in psutil.process_iter(['name', 'create_time']):
        if proc.info['name'] and 'colmap' in proc.info['name'].lower():
            colmap_proc = proc
            break
            
    if colmap_proc:
        try:
            p_cpu = colmap_proc.cpu_percent(interval=1.0)
            p_ram = colmap_proc.memory_info().rss / (1024*1024*1024)
            p_runtime = time.time() - colmap_proc.info['create_time']
        except:
            pass

    # Read Log
    fusion_lines = []
    current_fusing = "Unknown"
    accumulated_points = 0
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            for line in f:
                if "Fusing image [" in line:
                    fusion_lines.append(line.strip())
                    
                    # Accumulate points
                    m_pts = re.search(r'\((\d+) points\)', line)
                    if m_pts:
                        accumulated_points += int(m_pts.group(1))

    if fusion_lines:
        last_line = fusion_lines[-1]
        m = re.search(r'Fusing image \[(\d+)/(\d+)\]', last_line)
        if m:
            current_fusing = f"{m.group(1)} / {m.group(2)}"
            
    completed_images = [l for l in fusion_lines if " in " in l]
    current_completed_count = len(completed_images)
    
    # State tracking
    state = {"prev_completed": 0, "slow_count": 0}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        except:
            pass
            
    new_completed = current_completed_count - state.get("prev_completed", 0)
    
    # Average over last 20 images
    last_20 = completed_images[-20:] if len(completed_images) >= 20 else completed_images
    avg_fusion_time = 0
    if last_20:
        total_time = 0
        for l in last_20:
            m_time = re.search(r'in ([\d\.]+)s', l)
            if m_time:
                total_time += float(m_time.group(1))
        avg_fusion_time = total_time / len(last_20)
        
    avg_mins = avg_fusion_time / 60.0
    
    # Slow threshold logic
    if avg_mins > 5.0 and current_completed_count >= 20:
        state["slow_count"] = state.get("slow_count", 0) + 1
    else:
        state["slow_count"] = 0
        
    print(f"Elapsed runtime: {p_runtime/60:.1f} minutes" if colmap_proc else "Elapsed runtime: N/A (Process not running)")
    print(f"Current Fusing image: {current_fusing}")
    print(f"New images completed since last report: {new_completed}")
    print(f"Average fusion time (last {len(last_20)} images): {avg_mins:.2f} minutes/image")
    print(f"Current accumulated points (buffer): {accumulated_points}")
    print(f"CPU Usage: {p_cpu:.1f}% | RAM Usage: {p_ram:.2f} GB")
    
    if state["slow_count"] >= 3:
        print("\nALERT: Average fusion time has exceeded 5 minutes/image for 30 consecutive minutes!")
        print("ACTION_REQUIRED_STOP")
        
    print("\n--- Last 5 fusion log entries ---")
    for l in fusion_lines[-5:]:
        print(l)
    print("---------------------------------")

    # Update state
    state["prev_completed"] = current_completed_count
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

if __name__ == "__main__":
    main()
