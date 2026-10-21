# AGENT.md — Campus Digital Twin: build everything from scratch, then upgrade

You are a coding agent working in this repo on a **Windows laptop with an RTX
4050 (6 GB VRAM)**. Your job: set up, run, and progressively upgrade a 3D
reconstruction pipeline that turns Insta360 X3 video (handheld first, drone
later) into metric-scale 3D models.

Work **phase by phase, in order**. Each phase has a GATE — do not advance until
the gate passes. When something fails, use the phase's FALLBACK, not improvisation.

---

## Facts you must respect (do not "optimize" these away)

- **GPU: 6 GB VRAM.** All papers' defaults assume 24–40 GB. Always downscale
  images (~512–1600 px), cap counts, process one chunk at a time, watch
  `nvidia-smi`.
- **CUDA Toolkit 11.8 + PyTorch 2.1.2+cu118** for the `recon` env. Do NOT
  upgrade CUDA/torch to newer "because newer". LingBot-Map gets its **own
  separate env** (it wants newer torch) — never merge the two envs.
- **Never install `tinycudann`.** splatfacto uses gsplat. tinycudann is only for
  nerfacto and is a known Windows time-sink. If docs/errors suggest it: ignore.
- **Equirectangular video must be reframed to pinhole cube-faces before any
  SfM/reconstruction** (`reframe.py`, nadir face dropped — it contains the
  operator/rig). Never feed equirect frames to COLMAP directly.
- **Scale:** reconstructions are shape-correct, size-arbitrary. Metric scale
  comes from `scale_from_pose.py` — tape mode for handheld, `pose.csv`
  (drone VIO, metres) for drone chunks.
- **Chunking:** one capture folder = one chunk. Reconstruct per-chunk, then
  register chunks via their 20–30% overlaps (ICP). `capture_info.json →
  chunk.overlaps_with` says which chunks connect.
- **Human-in-the-loop steps you cannot do:** capturing video, stitching .insv →
  equirect MP4 in Insta360 Studio (GUI), clicking UAC prompts, tape measuring.
  When you reach one, STOP and print exactly what the human must do.

## Repo files you already have

| File | Purpose |
|---|---|
| `CAPTURE.py` + `README.md` (onsite) | field data-collection tool (input side) |
| `SETUP_GUIDE.md`, `SETUP_recon.bat`, `verify_setup.py` | env setup + verification |
| `HANDHELD_FIRST_TEST.md` | human-readable version of Phase 1 |
| `reframe.py` | 360 equirect MP4 → pinhole views (drops nadir) |
| `load_chunk.py` | load/validate one capture folder |
| `scale_from_pose.py` | metric scale from pose.csv or tape |
| `PROCESSING_WORKFLOW.md` | full pipeline reference (Phases 1–5 condensed) |

---

## PHASE 0 — Environment from scratch

1. Check manual prerequisites exist; if any missing, STOP and instruct the human
   (they are GUI installs): Miniconda, **VS Build Tools 2022 w/ C++**, **CUDA
   11.8** (`nvcc --version`), ffmpeg on PATH, COLMAP on PATH.
2. Build the env: run `SETUP_recon.bat` from an Anaconda-initialized shell, or
   the equivalent manual pip lines in `SETUP_GUIDE.md`.
3. **GATE:** `conda activate recon && python verify_setup.py` exits 0 and shows
   `CUDA available` + `GPU compute test passed`. If `torch.cuda.is_available()
   == False`: uninstall torch/torchvision, reinstall with
   `--index-url https://download.pytorch.org/whl/cu118`. Nothing proceeds until
   this gate passes.

## PHASE 1 — Handheld room → splat (prove the chain with boring tools)

Use COLMAP + Nerfstudio splatfacto ONLY. No research repos yet.

1. Human captures 60–90 s of one cluttered, well-lit room (see
   `HANDHELD_FIRST_TEST.md` Step 0) and stitches to `pano.mp4` (equirect) in
   Insta360 Studio. Human also tape-measures ONE distance.
2. `python reframe.py pano.mp4 --out views/ --fps 1 --face 1000`
   Check: images look like normal photos; operator/monopod NOT visible.
3. `ns-process-data images --data views/ --output-dir processed/`
   **GATE: ≥50% images registered** (target >80%). If <50%: the CAPTURE is bad —
   report to human to re-shoot (slower, more texture/light). Do not tune
   software to compensate.
4. `ns-train splatfacto --data processed/`
   On CUDA OOM: re-run step 3 with `--num-downscales 2`; consult
   `ns-train splatfacto --help` for current memory flags (flags drift between
   versions — never copy flags from old blogs).
5. `ns-export gaussian-splat --load-config outputs/.../config.yml --output-dir exports/`
   Human views the .ply at superspl.at/editor.
6. Scale: human measures the tape-measured feature's endpoints in the model;
   run `scale_from_pose.py --tape <D> --p1 ... --p2 ...`; apply factor; verify a
   second known distance reads within ~5%.
**PHASE GATE:** a spinnable, correctly-scaled room model exists. Record:
registration %, train time, peak VRAM.

## PHASE 2 — Upgrade the output: MeshSplatting (opaque connected mesh)

Goal: replace splats with a solid game-engine mesh, per the MeshSplatting paper
(Held et al., arXiv 2512.06818 — differentiable rendering with opaque triangles;
triangle soup → restricted Delaunay → opaque connected mesh).

1. Locate the official repo via the paper/project page
   (https://meshsplatting.github.io/). **First check code is actually released
   and runnable.** If not released/broken → FALLBACK now (step 4), report why.
2. Create a **separate env** per its README (PyTorch + Taichi). Do not touch
   `recon`.
3. Run it on Phase 1's `processed/` data (posed images + sparse cloud). 6 GB
   discipline: images ~512 px, cap vertices ~2–2.5M via densification/pruning
   settings the repo actually exposes (read its configs — do not invent flags),
   mixed precision only if the repo supports it. Monitor `nvidia-smi -l 1`.
4. **FALLBACK:** 2DGS or SuGaR (mature mesh-from-splatting repos) in the same
   slot; convert result to opaque in Blender if needed.
5. Scale the mesh exactly as Phase 1 step 6.
**PHASE GATE:** an opaque `.ply/.obj` mesh of the room, metric-scaled, opens in
Blender, walls solid. Note limitations honestly: not watertight; glass renders
opaque (expected — opaque triangles cannot represent transparency).

## PHASE 3 — Upgrade the poses: LingBot-Map (streaming SfM replacement)

Goal: replace COLMAP with LingBot-Map (feed-forward streaming reconstruction,
https://github.com/Robbyant/lingbot-map) — the project's innovation claim.

1. **Separate env** (it wants newer PyTorch/CUDA than `recon` — likely torch 2.9
   / CUDA 12.8 per its README; this is why envs never merge). Checkpoint is
   ~4.6 GB — verify it loads on 6 GB at all before promising anything.
2. Benchmark on Phase 1's `views/` with keyframe-interval / windowed settings
   from its README. Compare its camera path to COLMAP's from Phase 1 — same
   shape = good.
3. Feed its poses + points into the Phase 2 mesher in place of COLMAP output.
4. **FALLBACK:** COLMAP remains the pose source whenever LingBot-Map drifts
   (foliage, repeating structure) or OOMs. Per-chunk decision, not global.
**PHASE GATE:** one chunk reconstructed end-to-end with LingBot-Map poses, with
a written comparison (time, VRAM, path sanity) vs COLMAP.

## PHASE 4 — Drone chunks: pose.csv scaling + assembly

Now consume real capture folders from `CAPTURE.py` (drone/handheld on-site).

1. Per folder: `python load_chunk.py <folder>` must print READY. Heed WARNs
   (VIO `reset_counter` change → split trajectory at the reset).
2. Per chunk: stitch (human) → `reframe.py` → poses (Phase 3 primary / COLMAP
   fallback) → mesh (Phase 2 primary / fallback).
3. **Scale from the drone, not tape:** export the reconstruction's per-frame
   camera positions to `recon_cams.csv` (x,y,z), then
   `python scale_from_pose.py --pose <folder>/pose.csv --recon_traj recon_cams.csv`.
   Cross-check against `capture_info.json` tape_measurements — a known distance
   must read within ~5%, else fall back to `--tape` mode.
4. Assembly: for each pair listed in `chunk.overlaps_with`, ICP-register the
   overlap regions (CloudCompare — human-driven GUI; you prepare the cropped
   overlap exports and record the RMS it reports). Apply transforms; assemble
   chunks as USD references/payloads → `DTU_master.usd`.
**PHASE GATE:** ≥2 chunks registered into one metric master scene; ICP RMS and
per-chunk scale error recorded.

## PHASE 5 — Deployment (Unity/Unreal)

Import the master USD. Navmesh: bake on **flat proxy planes fitted to floors**,
never the raw noisy mesh; full mesh = visuals + wall colliders only. Crowd sim
agents on the navmesh. IoT: Mosquitto MQTT broker + engine subscriber pinning
live Arduino (DHT11/IR) readings to wall coordinates.

---

## Reporting duties (append to `RESULTS.md` as you go)

Per phase: what ran, exact commands, times, peak VRAM, registration %, scale
error vs tape, ICP RMS, which fallbacks fired and why. Honest limitations list.
These numbers ARE the internship report's results section.

## Standing rules

- One variable changes per phase. Never upgrade poses and mesher simultaneously.
- Prefer reading a repo's actual configs/flags over inventing plausible ones.
- On any OOM: reduce resolution first, counts second; never silently switch tools.
- If a gate fails twice with fallbacks exhausted: stop, summarize state, ask the
  human. Do not thrash.
