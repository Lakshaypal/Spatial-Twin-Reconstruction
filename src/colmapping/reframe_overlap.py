import argparse, os, subprocess, sys, glob
import numpy as np
import cv2
import py360convert

def extract_frames(mp4, frames_dir, fps):
    os.makedirs(frames_dir, exist_ok=True)
    n = len(glob.glob(os.path.join(frames_dir, "*.png")))
    if n > 0:
        print(f"  found {n} frames, skipping ffmpeg extraction...")
        return n
        
    cmd = ["ffmpeg", "-nostdin", "-y", "-i", mp4, "-vf", f"fps={fps}",
           os.path.join(frames_dir, "eq_%04d.png")]
    print(f"  running ffmpeg frame extraction at {fps} fps...")
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n = len(glob.glob(os.path.join(frames_dir, "*.png")))
    print(f"  extracted {n} equirectangular frames")
    return n

def generate_overlapping_views(frames_dir, views_dir, width, fov_deg):
    os.makedirs(views_dir, exist_ok=True)
    frames = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
    
    # 6 horizontal views + 1 top view
    yaws = [0, 60, 120, 180, 240, 300]
    names = ["F0", "F60", "F120", "F180", "F240", "F300"]
    
    for i, f in enumerate(frames):
        eq = cv2.imread(f)
        if eq is None:
            continue
            
        base = os.path.splitext(os.path.basename(f))[0]
        
        # Horizontal views
        for yaw, name in zip(yaws, names):
            view = py360convert.e2p(eq, fov_deg=fov_deg, u_deg=yaw, v_deg=0, out_hw=(width, width))
            cv2.imwrite(os.path.join(views_dir, f"{base}_{name}.png"), view)
            
        # Top view (yaw=0, pitch=90)
        top_view = py360convert.e2p(eq, fov_deg=fov_deg, u_deg=0, v_deg=90, out_hw=(width, width))
        cv2.imwrite(os.path.join(views_dir, f"{base}_Top.png"), top_view)
        
        if (i + 1) % 10 == 0:
            print(f"  reframed {i+1}/{len(frames)} frames")
            
    out_n = len(glob.glob(os.path.join(views_dir, "*.png")))
    print(f"  wrote {out_n} overlapping pinhole views")
    return out_n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4", help="equirectangular MP4")
    ap.add_argument("--out", default="views", help="output folder for pinhole views")
    ap.add_argument("--frames", default="frames", help="temp folder for equirect frames")
    ap.add_argument("--fps", type=float, default=2.0, help="frames/sec to sample")
    ap.add_argument("--face", type=int, default=1440, help="cube-face pixel size")
    ap.add_argument("--fov", type=float, default=100.0, help="FOV in degrees")
    args = ap.parse_args()

    print(f"[reframe_overlap] Processing {args.mp4}")
    extract_frames(args.mp4, args.frames, args.fps)
    generate_overlapping_views(args.frames, args.out, args.face, args.fov)
    print(f"[reframe_overlap] done -> {args.out}/")

if __name__ == "__main__":
    main()