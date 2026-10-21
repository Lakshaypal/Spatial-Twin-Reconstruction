> Historical project record. For the published scope, unscaled-unit caveats, attribution and reproducibility limits, read the [current README](../README.md). Recorded success labels are not fresh verification.

# PROCESSING WORKFLOW — After the Flight

You are the **processing** half of the project. You receive capture folders from
the input side (one per area/chunk) and turn them into scaled 3D meshes, then
assemble those into one master digital twin.

This document is the full pipeline: what to install, the exact order of steps,
the commands, the glue scripts included here, and the fallback for every stage.

---

## What you receive per chunk

One folder per captured area:

    DTU_eastStand_2026-07-09_run1/
    ├── pose.csv            metric camera trajectory (metres) ★ scale source
    ├── height.csv          downward rangefinder (metres, quality>0 valid)
    ├── gps.csv             GPS (zeros indoors — ignore those)
    ├── clock.csv           drone clock refs (video sync)
    ├── sync.csv            clap markers (>=2: start & end)
    ├── capture_info.json   metadata: overlaps_with, tape measurements
    └── VID_xxxxx.insv      the X3 360 video ★ geometry source

You'll get several of these. `capture_info.json → chunk.overlaps_with` tells you
which chunks share geometry and must be stitched together (Step 6).

---

## The scripts included here (glue you run directly)

| Script | Step | What it does |
|---|---|---|
| `load_chunk.py`      | 1 | Load + validate one capture folder. |
| `reframe.py`         | 2 | 360 video → pinhole cube-face images (drops rig). |
| `scale_from_pose.py` | 4 | Compute metric scale from pose.csv or tape. |

The heavy reconstruction (Steps 3, 5) uses research tools you install separately
— commands given below.

---

## One-time setup

```
# glue-script deps
pip install py360convert opencv-python numpy

# system tools
#   ffmpeg          (frame extraction)  -> add to PATH
#   COLMAP          (pose fallback)     -> apt install colmap  / colmap.github.io
#   Insta360 Studio (stitching)         -> Windows/Mac only
#   CloudCompare    (scale, ICP, mesh)  -> free
#   Blender         (export, USD)       -> free

# reconstruction models — SEPARATE conda envs (they conflict):
#   LingBot-Map   : follow its repo README (PyTorch 2.9 + CUDA 12.8)
#   MeshSplatting : follow its repo README (PyTorch + Taichi)
# VERIFY each runs on a small sample on your RTX 4050 (6 GB) before relying on it.
```

> RTX 4050 = **6 GB VRAM**. This is why you process **one chunk at a time** and
> downscale. The research papers' numbers are on 40 GB A100s — expect longer
> times and use the memory settings noted in Step 5.

---

## THE PIPELINE (per chunk, then assemble)

Do Steps 1–5 for EACH chunk folder. Then Step 6 assembles all chunks. Then Step 7.

### Step 1 — Load & validate the chunk
```
python load_chunk.py DTU_eastStand_2026-07-09_run1/
```
Prints "READY" or lists FAILs (empty pose, missing video). Fix FAILs with the
input side before continuing. Note any VIO-reset WARN — if `reset_counter`
changed mid-flight, treat the trajectory as two segments.

### Step 2 — Stitch, then reframe the 360 video
First **stitch** the `.insv` in **Insta360 Studio** → export **equirectangular
MP4**, max resolution. Then:
```
python reframe.py pano.mp4 --out views/ --fps 2 --face 1200
```
This extracts frames and converts each to 5 pinhole cube-faces, **dropping the
downward face** (removes the drone/stick/operator). Output: `views/*.png`.

*Tune:* faster motion → `--fps 3` or `5`. If you get >3000 images, raise `--face`
downscale or sample fewer.

### Step 3 — Camera poses (choose primary or fallback)

**Primary — LingBot-Map** (your innovation claim, streaming SfM replacement):
run its inference on `views/` per its README, producing camera poses + a sparse
point cloud. Keep it windowed/keyframed to fit 6 GB — benchmark first.

**Fallback — COLMAP** (if LingBot-Map drifts on foliage/symmetry):
```
colmap feature_extractor --database_path db.db --image_path views \
  --ImageReader.camera_model PINHOLE --SiftExtraction.use_gpu 1
colmap sequential_matcher --database_path db.db
colmap mapper --database_path db.db --image_path views --output_path sparse
```
Slower but reliable. Same output role: poses + sparse cloud.

**Sanity check:** load the poses/cloud in a viewer. The camera path should trace
the real walk/flight; walls should be planar. If it folds or smears → use the
other method for this chunk.

### Step 4 — Reconstruct the mesh (MeshSplatting or fallback)

**Primary — MeshSplatting:** feed the posed images + sparse cloud in per its
README. It optimizes an opaque, connected, coloured triangle mesh (game-engine
ready). 6 GB settings (state as intent, not invented flags):
- downscale training images to ~512 px,
- cap vertex count via densification-iteration / pruning thresholds (~2–2.5M),
- mixed precision *where the framework supports it*,
- one chunk at a time; watch `nvidia-smi`.

**Fallback — 2DGS or SuGaR** (if MeshSplatting OOMs or won't run): mature,
lighter mesh-from-splatting alternatives in the same slot. Convert to opaque in
Blender if needed.

Output: `chunk_raw.ply` / `.obj` — correct shape, arbitrary size.

### Step 5 — Give it metric scale
The mesh is shape-correct but size-arbitrary. Fix that from the drone pose.

**Preferred — path length vs pose:** export the reconstruction's per-frame
camera positions to a CSV with `x,y,z` columns (`recon_cams.csv`), then:
```
python scale_from_pose.py --pose DTU_eastStand_.../pose.csv --recon_traj recon_cams.csv
```
It prints a SCALE FACTOR = (metric path length) / (recon path length).

**Fallback / cross-check — tape:** pick two points you tape-measured on-site,
read their reconstruction coords, and:
```
python scale_from_pose.py --tape 6.00 --p1 x1,y1,z1 --p2 x2,y2,z2
```

Apply the scale factor uniformly to the mesh (Blender: scale by the factor;
CloudCompare: Edit → Multiply). **Verify:** a known 6 m distance must read ~6 m
after scaling. Now `chunk_metric.glb/.ply` is in true metres.

### Step 6 — Assemble chunks (only after all chunks are scaled)
For each pair of chunks that `overlaps_with` each other:
1. Load both in **CloudCompare**, crop each to the shared 20–30% overlap region.
2. *Tools → Registration → Fine Registration (ICP)* → get the transform + **RMS**
   (record the RMS — it's a result for your report).
3. Apply that transform to place chunk B relative to chunk A.

Then build the master scene in **Blender/OpenUSD**: bring each scaled chunk in as
a **USD reference/payload** (non-destructive links, not copies) and apply the ICP
transforms. Output: `DTU_master.usd`.

*Fallback:* if ICP won't converge (overlap too small/repetitive), seed it with
3+ manually-picked matching points, then ICP. If it still fails, that seam lacked
overlap — flag it back to the input side to re-capture.

### Step 7 — Deploy (Unity/Unreal) — the applications
- Import `DTU_master.usd`.
- **Navmesh:** fit flat **proxy planes** to floors and bake the navmesh on those,
  NOT the raw noisy mesh. Use the full mesh only for visuals + wall colliders.
- **Crowd sim:** spawn agents on the navmesh (MeshSplatting's opaque mesh works
  with Unity's stock mesh collider directly).
- **IoT anchoring:** Mosquitto MQTT broker; Arduino (DHT11/IR) publishes; an
  engine subscriber pins live 3D tags to wall coordinates.

---

## Quick per-chunk checklist

```
[ ] load_chunk.py says READY
[ ] stitched .insv -> equirectangular .mp4 (Insta360 Studio)
[ ] reframe.py -> views/ (nadir dropped)
[ ] poses: LingBot-Map (or COLMAP fallback) — path sanity-checked
[ ] mesh: MeshSplatting (or 2DGS/SuGaR) — stayed under 6 GB
[ ] scale_from_pose.py -> applied -> 6 m reads ~6 m
[ ] chunk_metric saved
```
After all chunks:
```
[ ] ICP-registered overlapping pairs (RMS recorded)
[ ] USD references assembled into master
[ ] navmesh on proxy planes, crowd sim, IoT tags
```

---

## Fallback quick-reference

| Stage | Symptom | Fallback |
|---|---|---|
| Poses (3) | path folds / cloud smears | LingBot-Map → **COLMAP** |
| Mesh (4)  | CUDA OOM / won't run       | MeshSplatting → **2DGS / SuGaR** |
| Scale (5) | path-length looks off     | use **--tape** mode |
| Assembly (6) | ICP won't converge     | manual point seed → ICP; else re-capture seam |
| Navmesh (7) | fragments / agents stutter | bake on **proxy planes** |

---

## What to record for the report (from processing)

- Per-chunk: pose method used, mesh training time, peak VRAM, vertex count.
- Scale error: a held-out known distance measured vs real (target <2–5%).
- Assembly: ICP RMS per stitched pair.
- Honest limitations: glass rendered opaque, mesh not watertight, gaps where
  coverage was thin.
