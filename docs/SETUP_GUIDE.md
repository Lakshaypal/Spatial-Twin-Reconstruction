> Historical project record. For the published scope, unscaled-unit caveats, attribution and reproducibility limits, read the [current README](../README.md). Recorded success labels are not fresh verification.

# SETUP GUIDE — the `recon` environment

This builds the environment for the handheld first test (COLMAP + Nerfstudio
splatfacto). **Be warned: this is the fiddliest step in the whole project.**
Nerfstudio compiles CUDA code, so it needs a C++ compiler and a CUDA toolkit.
Budget an evening. Once it's done you never touch it again.

**Order matters.** Do the manual prerequisites first, then run the script.

---

## PART 1 — Manual prerequisites (can't be scripted)

Install these five things **in this order**, then reboot.

### 1. Miniconda
https://docs.conda.io/en/latest/miniconda.html
Accept defaults. Afterwards you'll have an **"Anaconda Prompt"** in the Start
menu — use that for everything below.

### 2. Visual Studio Build Tools 2022  ← the one people skip
https://visualstudio.microsoft.com/downloads/ → scroll to *Tools for Visual
Studio* → **Build Tools for Visual Studio 2022**.
In the installer, tick **"Desktop development with C++"**. Install (~6 GB).

> Without this, gsplat cannot compile and nerfstudio install fails with
> cryptic C++ errors. This is the #1 cause of setup failure on Windows.

### 3. CUDA Toolkit 11.8
https://developer.nvidia.com/cuda-11-8-0-download-archive
Choose Windows → x86_64 → your version → exe (local). Install.

> Why 11.8 and not the newest? It's the best-supported combination with
> PyTorch + gsplat. Newer is not better here.
> Check it worked: open a new prompt and run `nvcc --version`.

### 4. FFmpeg
https://www.gyan.dev/ffmpeg/builds/ → download the "release essentials" zip.
Extract to e.g. `C:\ffmpeg`, then add `C:\ffmpeg\bin` to your **PATH**.
Check: `ffmpeg -version`

### 5. COLMAP
https://colmap.github.io/ → Download → Windows binary (CUDA version).
Extract to e.g. `C:\colmap`, add that folder to your **PATH**.
Check: `colmap -h`

> **How to add to PATH:** Start → "Edit the system environment variables" →
> Environment Variables → under *System variables* select **Path** → Edit →
> New → paste the folder → OK. **Open a NEW terminal** for it to take effect.

**Now reboot.**

---

## PART 2 — Run the setup script

Open **Anaconda Prompt** (not regular CMD), `cd` to this folder, and run:

```
SETUP_recon.bat
```

It creates the `recon` env and installs PyTorch (CUDA 11.8), Nerfstudio + gsplat,
and the reframe deps. The Nerfstudio step compiles CUDA kernels — **it can take
20–40 minutes and looks frozen. Let it run.**

### Or do it manually (same thing)

```
conda create -n recon python=3.10 -y
conda activate recon

pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 --index-url https://download.pytorch.org/whl/cu118
pip install ninja
pip install nerfstudio
pip install py360convert opencv-python numpy
```

---

## PART 3 — Verify (do not skip)

```
conda activate recon
python verify_setup.py
```

It checks Python, PyTorch, **actual GPU compute**, gsplat, nerfstudio CLI,
py360convert/opencv, and ffmpeg/colmap on PATH. It prints `READY` or a list of
exactly what's broken.

**The single most important line** is under `[2] PyTorch + GPU`:
```
  [ OK ] CUDA available — NVIDIA GeForce RTX 4050 Laptop GPU
  [ OK ] GPU compute test passed
  [ OK ] VRAM: 6.0 GB
```
If it says `torch.cuda.is_available() == False`, nothing else matters — fix that
first (see below).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `torch.cuda.is_available() == False` | CPU-only torch got installed | `pip uninstall torch torchvision -y` then re-run the torch line **with** the `--index-url ...cu118` part |
| nerfstudio install fails with C++ / `cl.exe` errors | VS Build Tools missing | Install Build Tools 2022 + "Desktop development with C++", reboot, retry |
| gsplat fails to build | no CUDA toolkit / mismatch | Install CUDA 11.8, check `nvcc --version`, retry |
| `ns-train` not found | install incomplete | `conda activate recon` first; if still missing, `pip install nerfstudio` again and read the error |
| `colmap` / `ffmpeg` not found | not on PATH | add folder to PATH, **open a new terminal** |
| `tinycudann` warnings | it's optional | **Ignore it.** splatfacto uses gsplat, not tinycudann. Only nerfacto needs it. |
| Install is glacially slow | it's compiling | Normal. 20–40 min. Don't kill it. |
| conda command not found | wrong terminal | Use **Anaconda Prompt**, not CMD/PowerShell |

---

## Every time you work (the daily commands)

```
conda activate recon
```
That's it — then run the pipeline:
```
python reframe.py pano.mp4 --out views/ --fps 1 --face 1000
ns-process-data images --data views/ --output-dir processed/
ns-train splatfacto --data processed/
```

---

## Files here

- `SETUP_recon.bat` — builds the env (run after Part 1)
- `verify_setup.py` — checks it worked (run after Part 2)
- `SETUP_GUIDE.md` — this file
