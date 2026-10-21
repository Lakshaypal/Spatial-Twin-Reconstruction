#!/usr/bin/env python3
"""
============================================================================
 STEP 2 — reframe.py : 360 video -> pinhole frames ready for reconstruction
============================================================================
Takes the stitched equirectangular MP4 and turns it into pinhole cube-face
images that COLMAP / MeshSplatting understand, DROPPING the downward (nadir)
face where the drone/stick/operator sits.

PREREQUISITE: stitch the X3 .insv into an equirectangular .mp4 first, using
Insta360 Studio (export -> equirectangular, max resolution). This script
takes that .mp4.

    python reframe.py pano.mp4 --out views/ --fps 2 --face 1200

Output: views/eq_XXXX_{F,R,B,L,U}.png   (nadir 'D' intentionally omitted)
============================================================================
"""
import argparse, os, subprocess, sys, glob

def extract_frames(mp4, frames_dir, fps):
    os.makedirs(frames_dir, exist_ok=True)
    cmd = ["ffmpeg", "-nostdin", "-i", mp4, "-vf", f"fps={fps}",
           os.path.join(frames_dir, "eq_%04d.png")]
    print("  running ffmpeg frame extraction...")
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n = len(glob.glob(os.path.join(frames_dir, "*.png")))
    print(f"  extracted {n} equirectangular frames")
    return n

def reframe_all(frames_dir, views_dir, face_w, keep_nadir=False):
    import py360convert, cv2
    os.makedirs(views_dir, exist_ok=True)
    faces_keep = ["F", "R", "B", "L", "U"] + (["D"] if keep_nadir else [])
    frames = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
    for i, f in enumerate(frames):
        eq = cv2.imread(f)
        if eq is None:
            continue
        cube = py360convert.e2c(eq, face_w=face_w, cube_format="dict")
        base = os.path.splitext(os.path.basename(f))[0]
        for name in faces_keep:
            cv2.imwrite(os.path.join(views_dir, f"{base}_{name}.png"), cube[name])
        if (i + 1) % 50 == 0:
            print(f"  reframed {i+1}/{len(frames)} frames")
    out_n = len(glob.glob(os.path.join(views_dir, "*.png")))
    print(f"  wrote {out_n} pinhole views (nadir {'kept' if keep_nadir else 'DROPPED'})")
    return out_n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4", help="equirectangular MP4 (stitched in Insta360 Studio)")
    ap.add_argument("--out", default="views", help="output folder for pinhole views")
    ap.add_argument("--frames", default="frames", help="temp folder for equirect frames")
    ap.add_argument("--fps", type=float, default=2.0, help="frames/sec to sample")
    ap.add_argument("--face", type=int, default=1200, help="cube-face pixel size")
    ap.add_argument("--keep-nadir", action="store_true",
                    help="keep the downward face (default: drop it, removes rig)")
    args = ap.parse_args()

    try:
        import py360convert, cv2  # noqa
    except ImportError:
        sys.exit("Missing deps. Install: pip install py360convert opencv-python")

    print(f"[reframe] {args.mp4}")
    extract_frames(args.mp4, args.frames, args.fps)
    reframe_all(args.frames, args.out, args.face, args.keep_nadir)
    print(f"[reframe] done -> {args.out}/")
    print("Next: run pose estimation (Step 3) on this views/ folder.")

if __name__ == "__main__":
    main()
