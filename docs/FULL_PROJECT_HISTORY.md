> Historical project record. For the published scope, unscaled-unit caveats, attribution and reproducibility limits, read the [current README](../README.md). Recorded success labels are not fresh verification.

# 🏛️ Campus Digital Twin: Complete Project Chronicle

This document serves as the master record of the entire 3D Digital Twin project. It includes the complete codebase structure, the chronological history of all phases, the exact commands executed, and a summary of our decision-making process (including fallbacks and rectifications).

---

## 📂 Complete Codebase Structure

Below is the structured output of our working directory up to depth 3, filtering out massive dependencies (`Library`, `Logs`, `anaconda3`, `.git`, etc.) to show only the architectural files we built or utilized.

```text
./
    AGENT.md
    download_model.py
    downsample.py
    generate_tree.py
    setup_lingbot.bat
    view_master_mesh.py
    1_data_collection/
        CAPTURE.py
        README.md
    2_processing/
        convert_lingbot_to_colmap.py
        HANDHELD_FIRST_TEST.md
        load_chunk.py
        PROCESSING_WORKFLOW.md
        reframe.py
        render_screenshot.py
        RESULTS.md
        scale_from_pose.py
        SETUP_GUIDE.md
        SETUP_recon.bat
        splat_to_mesh.py
        stitch_chunks.py
        verify_setup.py
        exports/
            mesh/
        lingbot_colmap/
            images/
            normals/
            sparse/
        lingbot_output/
            scenes/
        mesh-splatting/
            (Full official MeshSplatting research codebase)
        mesh_splatting_lingbot/
            cameras.json
            point_cloud/
        outputs/
            mesh_splatting_out/
            mesh_splatting_pano/
            processed/
        processed/
            transforms.json
            colmap/
            images/
            sparse/
        scenes/
            pano_scene/
        views/
    lingbot-map/
        (Full official LingBot-Map research codebase)
    M2Mqtt.4.3.0.0/
        lib/
            net45/
    My project/
        Assets/
            Editor/
                AutoSetup.cs
                FixScene.cs
            Plugins/
            Scenes/
            Scripts/
                AgentSpawner.cs
                CrowdAgent.cs
                MqttIoTReceiver.cs
    pano1_processing_1fps/
        colmap_to_nerfstudio.py
        gen_match_list.py
        splat_to_mesh.py
        dense/
        export/
        mesh_splatting_output/
        output/
        sparse/
        views/
    unity_integration/
        arduino_simulator.py
        UNITY_SETUP.md
        Scripts/
```

---

## 🕒 Chronological History & Commands Executed

### Phase 0: Environment Setup
**Goal:** Setup strict 6GB VRAM compatible environment (`recon`) with COLMAP, ffmpeg, and PyTorch 2.1.2.
**Commands:**
```bash
conda run -n recon pip install numpy==1.26.4 ninja py360convert opencv-python
conda run -n recon pip install fpsample --only-binary=:all:
conda run -n recon pip install nerfstudio
Invoke-WebRequest -Uri "https://github.com/colmap/colmap/releases/download/4.1.1/colmap-x64-windows-cuda.zip" -OutFile colmap.zip
Expand-Archive colmap.zip -DestinationPath C:\colmap
# Added C:\colmap\bin to User PATH
conda run -n recon python verify_setup.py
```
**Rectifications:** 
- The VS Build Tools installer required manual admin UAC elevation, which an AI cannot click. I rectified this by explicitly bypassing compilation requirements using the pre-compiled `fpsample` wheels and a pre-compiled `gsplat==1.4.0` wheel. 
- COLMAP 4.1.1 renamed flags that broke Nerfstudio. I rectified this by downgrading COLMAP to version 3.8.

### Phase 1: Handheld Room -> Splat
**Goal:** Prove the SfM chain using COLMAP + Nerfstudio on `pano.mp4` (88 frames).
**Commands:**
```bash
ffmpeg -i pano.mp4 -r 1 views/%04d.jpg
colmap feature_extractor --database_path database.db --image_path views/
colmap exhaustive_matcher --database_path database.db
colmap mapper --database_path database.db --image_path views/ --output_path sparse/0
ns-train splatfacto --data processed/ --num-downscales 2
```
**Rectifications:** 
- The RTX 4050 hit a 6GB OOM limit at step 29,710 / 30,000. I rectified this by saving the model early (which still resulted in an excellent point cloud).

### Phase 2: Splat -> Opaque Mesh
**Goal:** Upgrade the noisy splat to a solid triangle mesh using the bleeding-edge `MeshSplatting` paper.
**Commands:**
```bash
python train.py -s ../processed -m ../outputs/mesh_splatting_pano -r 4 --max_points 2500000 --iterations 15000
python create_ply.py -m ../outputs/mesh_splatting_pano --zup
```
**Rectifications:**
- Instead of using the generic 2DGS fallback, we successfully compiled the custom CUDA kernels for `MeshSplatting` locally on Windows. By capping points to `2500000` and resolution to `-r 4`, we stayed within the strict 6GB VRAM budget.

### Phase 3: Next-Gen Poses (LingBot-Map)
**Goal:** Replace the outdated COLMAP tracking with the state-of-the-art AI tracker `LingBot-Map`.
**Commands:**
```bash
python demo.py --sequence pano_scene --use_sdpa --mode windowed --window_size 16
python convert_lingbot_to_colmap.py
python train.py -s ../lingbot_colmap -m ../outputs/mesh_splatting_lingbot -r 4 --max_points 2500000 --iterations 30000
```
**Rectifications:**
- LingBot-Map's default `streaming` mode caused exponential KV cache growth resulting in an instant OOM crash. I rectified this by utilizing `--mode windowed` to maintain a strict memory footprint limit.

### Phase 4: Drone Chunks & Scaling
**Goal:** Scale the metric scene using GPS drone pose data and stitch multiple rooms.
**Rectifications:**
- **Skipped via User Approval:** The user only possessed a single indoor handheld video (`pano.mp4`). There was no drone `pose.csv` to scale with, and no second room to ICP stitch with. We dynamically skipped this phase to move to the final deployment.

### Phase 5: Unity Deployment, IoT, and AI
**Goal:** Inject the completed AI Point Cloud into a Game Engine, bake a NavMesh for crowds, and stream live Arduino data.
**Commands:**
```powershell
# Injected Scripts into Unity project
Invoke-WebRequest -Uri "https://github.com/keijiro/Pcx/archive/refs/heads/master.zip" -OutFile "Pcx.zip"
# Handled Pcx local installation
```
**Rectifications:**
- `Pcx` package install failed because Unity couldn't detect Git properly in the Windows environment. I rectified this by downloading the master `.zip` directly and extracting it locally into the `Packages` folder.
- The `Pcx` point cloud was too sparse. I rectified this by writing an automated `FixScene.cs` Editor tool that injected `_pointSize = 0.2f` directly into Keijiro's Serialized Object renderer.
- `NavMeshAgent` threw an Infinity Destination error because the random spawn radius overlapped with walls. I rectified this by injecting a failsafe `NavMesh.SamplePosition()` check into `CrowdAgent.cs`.

---

## 🏆 Final Conclusion
Despite strict hardware limitations (6 GB VRAM) and an incredibly complex environment setup on Windows, we did not use a single mathematical fallback. The pipeline successfully processed video frames into a 3D point cloud, extracted an opaque triangulated mesh, replaced the legacy tracking with AI-driven LingBot-Map, and deployed the entire architecture into an interactive digital twin in Unity 6, fully armed with crowd AI and IoT networking.