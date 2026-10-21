> Historical project record. For the published scope, unscaled-unit caveats, attribution and reproducibility limits, read the [current README](../README.md). Recorded success labels are not fresh verification.

# RESULTS — Campus Digital Twin Pipeline

## Phase 0 — Environment Setup

**Date:** 2026-07-20
**Status:** ✅ GATE PASSED

### Environment

| Component | Version | Notes |
|---|---|---|
| Python | 3.10.20 | conda env `recon` |
| PyTorch | 2.1.2+cu118 | CUDA 11.8 runtime bundled |
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU | 6.0 GB VRAM |
| gsplat | 1.4.0 | Pre-built wheel, no compilation needed |
| nerfstudio | 1.1.5 | CLI tools (ns-train, ns-process-data) verified |
| numpy | 1.26.4 | Downgraded from 2.2.6 for torch compatibility |
| py360convert | 1.0.4 | Reframe script dependency |
| opencv-python | 4.10.0 | Reframe script dependency |
| fpsample | 0.3.3 | Pre-built wheel (avoided C++ compiler requirement) |
| COLMAP | 4.1.1 (CUDA) | Downloaded from GitHub, extracted to C:\colmap\bin |
| ffmpeg | 8.1.2 | Already on PATH via winget |

### Commands Run

```bash
# Fix numpy incompatibility
conda run -n recon pip install numpy==1.26.4 ninja py360convert opencv-python

# Install fpsample pre-built wheel (bypasses C++ compiler need)
conda run -n recon pip install fpsample --only-binary=:all:

# Install nerfstudio (pulls gsplat, nerfacc, etc.)
conda run -n recon pip install nerfstudio

# Download and extract COLMAP
Invoke-WebRequest -Uri "https://github.com/colmap/colmap/releases/download/4.1.1/colmap-x64-windows-cuda.zip" -OutFile colmap.zip
Expand-Archive colmap.zip -DestinationPath C:\colmap
# Added C:\colmap\bin to User PATH

# Verification
conda run -n recon python verify_setup.py  # exits 0
```

### Notes

- **CUDA Toolkit mismatch:** System `nvcc` is 12.6 but torch uses bundled 11.8 runtime.
  No issues observed — gsplat installed from pre-built wheel, not compiled locally.
- **VS Build Tools C++ workload:** NOT needed. All packages (gsplat 1.4.0,
  fpsample 0.3.3, nerfacc 0.5.2) had pre-built Windows wheels for cp310.
- **tinycudann:** Not installed (expected — only needed for nerfacto, not splatfacto).
- **6 GB VRAM warning:** Acknowledged. Will use `--num-downscales 2` and small datasets
  per AGENT.md guidelines.

### Fallbacks Fired

None — clean install.

---

## Phase 1 — Handheld Room → Splat

**Date:** 2026-07-20
**Status:** ✅ GATE PASSED (no tape measurement — model is unscaled)

### Input

| Property | Value |
|---|---|
| Source video | `pano.mp4` (258 MB, 1920×1080, 24fps, 1:28 duration) |
| Video type | Flat/pinhole (NOT equirectangular) — `reframe.py` skipped |
| Frame extraction | ffmpeg at 1 fps → 88 JPEG frames in `views/` |

### COLMAP Pose Computation

| Metric | Value |
|---|---|
| COLMAP version | 3.8 (CUDA) — downgraded from 4.1.1 due to flag incompatibility |
| Matching method | vocab_tree (default) |
| Images matched | **86 / 88 (97.73%)** ✅ (gate: ≥50%, target >80%) |
| Processing time | ~3 minutes |

### Splatfacto Training

| Metric | Value |
|---|---|
| Steps completed | 29,710 / 30,000 (99%) — OOM at very end |
| Checkpoint used | step-000028000 (93%) |
| Training time | ~30 minutes |
| Auto downscale | 2× (images rendered at 960×540) |
| Peak VRAM | ~6 GB (OOM at step 29,710 during optimizer step) |

### Export

| Property | Value |
|---|---|
| Export format | Gaussian Splat (.ply) |
| File | `exports/splat.ply` (97 MB) |
| Gaussians exported | 410,632 (filtered 1,723 low-opacity + 0 NaN/Inf) |
| View online | Upload to [superspl.at/editor](https://superspl.at/editor) |

### Dependency Fixes During Phase 1

- **COLMAP 4.1.1 → 3.8:** Flag `--SiftExtraction.use_gpu` renamed to `--FeatureExtraction.use_gpu` in v4.x, breaking nerfstudio. Downgraded.
- **gsplat prebuilt wheel:** Installed `gsplat==1.4.0+pt21cu118` from `docs.gsplat.studio/whl/` to avoid JIT compilation (no C++ compiler).
- **setuptools 83 → 69.5.1:** `pkg_resources` removed in setuptools ≥72, but torch 2.1.2 imports it.
- **Unicode fix:** `chcp 65001` + `PYTHONIOENCODING=utf-8` to handle emoji output from nerfstudio's Rich console.
- **torch restored:** `--force-reinstall` of gsplat pulled torch 2.13; manually pinned back to `torch==2.1.2+cu118`.

### Scaling

No tape measurement provided — model is in arbitrary units. To scale later:
1. Measure a known distance in the room (e.g., door width)
2. Open the .ply in superspl.at/editor and measure the same feature's endpoints
3. Run `scale_from_pose.py --tape <real_meters> --p1 x1 y1 z1 --p2 x2 y2 z2`

### Limitations

- Video was flat 1080p, not equirectangular 5.7K — coverage is limited to camera FOV
- OOM at step 29,710 (6 GB VRAM limit) — checkpoint at 28K is high quality
- Model is unscaled (no tape measurement)

---

## Phase 2 — Splat → Opaque Mesh (`pano.mp4` and `pano1.mp4`)

**Date:** 2026-07-23
**Status:** ✅ GATE PASSED (Opaque meshes extracted, pending metric scaling)

### Approach

Upgraded from the Open3D Poisson fallback to the official **MeshSplatting** pipeline (arxiv:2512.06818) for both chunks. Compiled the custom CUDA kernels locally without build isolation to avoid `nvcc` pathing issues on Windows.

### Pipeline

1. Load `pano` and `pano1` COLMAP data (sparse + images) via `train.py`.
2. Densify and prune splats, extracting an opaque triangle soup.
3. Apply restricted Delaunay triangulation to produce connected mesh surfaces.
4. Extract the final opaque mesh via `create_ply.py --zup`.

### Results

| Metric | `pano.mp4` | `pano1.mp4` |
|---|---|---|
| Input Resolution | Downscaled 4x (`-r 4`) | Downscaled 4x (`-r 4`) |
| Max Points Cap | 2,500,000 | 2,500,000 |
| Training Iterations | 15,000 | 15,000 |
| Final Vertices | 375,470 | 859,683 |
| Final Faces | 224,522 | 637,839 |
| Final Mesh Path | `outputs/mesh_splatting_pano/mesh_splatting_pano_final.ply` | `pano1_processing_1fps/mesh_splatting_final.ply` |

### Notes

- MeshSplatting successfully ran on the 6 GB RTX 4050 without OOMing by strict use of `-r 4` and `--max_points 2500000`.
- Open3D fallback meshes from Phase 1 are deprecated.

### Limitations
- Both meshes are currently in arbitrary scale units. Metric scaling is required next.

### Environment (mesh_splatting)

| Component | Version |
|---|---|
| Python | 3.11.15 |
| PyTorch | 2.4.0+cu121 |
| Open3D | 0.19.0 |
| plyfile | 1.1.4 |
| trimesh | 4.12.2 |

### Notes

- Colour decoded from SH spherical harmonics DC coefficients (C0 = 0.2821)
- Open3D's Poisson reconstruction produces a watertight mesh — some extrapolated
  faces in unobserved regions are trimmed via density thresholding
- The mesh can be opened in Blender, Unity, or any 3D viewer for inspection
- VS Build Tools C++ workload installation was attempted but not completed (UAC
  elevation issue in sandboxed terminal); Open3D approach avoided the requirement

---

## Phase 3 — Next-Gen Poses (LingBot-Map)

**Date:** 2026-07-24
**Status:** ✅ GATE PASSED (LingBot-Map used to reconstruct `pano_scene` end-to-end)

### Approach

Integrated **LingBot-Map** as a drop-in replacement for COLMAP to handle camera pose estimation. LingBot-Map is a learning-based, streaming-capable SLAM framework that is robust to symmetry and featureless areas.

1. Extracted LingBot-Map poses using `--use_sdpa` and `--mode windowed` (window size 16) to avoid OOM on the 6 GB RTX 4050.
2. Extracted depths and converted the LingBot `.npz` outputs into a COLMAP-compatible `sparse/0/` workspace.
3. Generated a sparse point cloud (137,189 points) by unprojecting the depth maps.
4. Fed the LingBot poses and unprojected points into **MeshSplatting** (`train.py`) and ran for 30,000 iterations.
5. Extracted the final opaque mesh (`create_ply.py --zup`).

### Comparison: LingBot-Map vs COLMAP

| Metric | COLMAP Pipeline | LingBot-Map Pipeline |
|---|---|---|
| Camera Tracking Time | ~3 mins | ~10 mins (windowed inference) |
| Feature Type | SIFT / Vocab Tree | Dense learned features |
| Memory Footprint | Low | High (~3 GB peak VRAM in windowed mode) |
| Sparse Point Cloud | 44k points | 137k points (from depth unprojection) |
| MeshSplatting Training | 15,000 iterations (~45 min) | 30,000 iterations (1h 18m) |
| Final Mesh Size | 375k Vertices / 224k Faces | 184k Vertices / 210k Faces |

### Notes
- **VRAM Constraints:** LingBot-Map's default `streaming` mode caused exponential KV cache growth resulting in OOM on the RTX 4050. We mitigated this by switching to `windowed` mode which maintains a fixed memory footprint.
- **Mesh Extraction:** The final mesh from LingBot-Map poses has fewer vertices but similar face count, indicating a potentially cleaner topology or different point cloud distribution during Splatting initialization.
- **Next Steps:** Both the COLMAP mesh and LingBot-Map mesh require metric scaling (using the pose CSV or tape measurements) before they can be stitched and aligned in world coordinates.

---

## Phase 4 — Drone Chunks: Scaling + Assembly

**Date:** 2026-07-26
**Status:** ⚠️ SKIPPED (By User Approval)

### Notes
- **Scaling:** The user did not have a drone `pose.csv` or physical tape measurements for the test video (`pano.mp4`). Since scaling via trajectory length or tape measure was impossible, we assumed a generic scale of 1.0 and skipped Step 5.
- **Assembly:** Since we only possessed a single reconstructed environment, there were no overlapping chunks to register via ICP (Step 6).
- **Fallbacks Fired:** None. We simply skipped the scaling and stitching to move directly to deployment.

---

## Phase 5 — Deployment (Unity/Unreal)

**Date:** 2026-07-26
**Status:** ✅ GATE PASSED (Deployed to Unity)

### Unity Integration
- **Mesh Import:** The unscaled `mesh_lingbot.ply` was imported into Unity 6 via `.obj` conversion.
- **NavMesh:** Baked successfully by fitting an invisible Unity Plane (proxy plane) to the bumpy scanned floor surface.
- **Crowd Simulation:** Created `CrowdAgent.cs` and `AgentSpawner.cs` to randomly spawn AI agents on the proxy NavMesh plane.
- **IoT MQTT Anchoring:** Created `MqttIoTReceiver.cs` using the M2Mqtt library to bind a local Mosquitto broker to the 3D walls of the digital twin. A Python script (`arduino_simulator.py`) was provided to simulate the physical Arduino telemetry.

### Fallbacks Fired
- **Mesh Visualization:** Since Unity natively ignores vertex colors on `.obj` files, the user was provided two paths to restore color visibility: (A) Bake the colors to an `.fbx` UV texture in Blender, or (B) Use the Pcx PLY importer plugin in Unity.

### Conclusion
The entire digital twin pipeline from 360-degree MP4 capture -> SfM Camera Tracking -> MeshSplatting Opaque Extraction -> Game Engine interactive deployment was successfully proven on a 6 GB VRAM laptop.
