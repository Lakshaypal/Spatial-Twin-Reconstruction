#!/usr/bin/env python3
"""
============================================================================
 STEP 4 — scale_from_pose.py : give the reconstruction TRUE METRIC SCALE
============================================================================
The reconstruction (from COLMAP/LingBot-Map/MeshSplatting) is correct in
SHAPE but arbitrary in SIZE. The drone's pose.csv is in real metres. This
script computes the single scale factor that maps the reconstruction into
metres, by comparing the camera path length in both.

Two modes:
  (A) --tape D   : simplest. You already measured one real distance D (m)
                   between two points; give the same two points' reconstruction
                   coords and it computes scale = D / recon_distance.
  (B) default    : compares total path length of the reconstruction's camera
                   trajectory vs the drone pose trajectory length.

Outputs the scale factor. Apply it uniformly to the mesh in Blender/CloudCompare
(or feed it into the export step).

Usage (path-length mode):
    python scale_from_pose.py --pose DTU_.../pose.csv --recon_traj recon_cams.csv
Usage (tape mode):
    python scale_from_pose.py --tape 6.00 --p1 x1,y1,z1 --p2 x2,y2,z2
============================================================================
"""
import argparse, csv, math, sys

def path_length(points):
    d = 0.0
    for a, b in zip(points, points[1:]):
        d += math.dist(a, b)
    return d

def load_xyz(path, cols=("x","y","z")):
    pts = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                pts.append((float(r[cols[0]]), float(r[cols[1]]), float(r[cols[2]])))
            except (ValueError, KeyError):
                continue
    return pts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose", help="drone pose.csv (metres)")
    ap.add_argument("--recon_traj", help="reconstruction camera path CSV with x,y,z")
    ap.add_argument("--tape", type=float, help="a real measured distance in metres")
    ap.add_argument("--p1", help="recon coord of point 1: x,y,z")
    ap.add_argument("--p2", help="recon coord of point 2: x,y,z")
    args = ap.parse_args()

    if args.tape is not None:
        if not (args.p1 and args.p2):
            sys.exit("tape mode needs --p1 and --p2 (recon coords of the two points)")
        p1 = tuple(float(v) for v in args.p1.split(","))
        p2 = tuple(float(v) for v in args.p2.split(","))
        recon_d = math.dist(p1, p2)
        if recon_d == 0:
            sys.exit("the two recon points are identical")
        scale = args.tape / recon_d
        print(f"[tape mode] real={args.tape} m  recon={recon_d:.4f} units")
        print(f"SCALE FACTOR = {scale:.6f}   (multiply the reconstruction by this)")
        return

    if not (args.pose and args.recon_traj):
        sys.exit("path-length mode needs --pose and --recon_traj")
    drone = load_xyz(args.pose)
    recon = load_xyz(args.recon_traj)
    if len(drone) < 2 or len(recon) < 2:
        sys.exit("need >=2 points in each trajectory")
    dl = path_length(drone)
    rl = path_length(recon)
    if rl == 0:
        sys.exit("reconstruction path length is zero")
    scale = dl / rl
    print(f"[path-length mode]")
    print(f"  drone path (metric) : {dl:.3f} m")
    print(f"  recon path (units)  : {rl:.3f}")
    print(f"SCALE FACTOR = {scale:.6f}   (multiply the reconstruction by this)")
    print("\nSanity check: verify against a tape measurement afterward. If a")
    print("known 6 m distance doesn't read ~6 m after scaling, use --tape mode.")

if __name__ == "__main__":
    main()
