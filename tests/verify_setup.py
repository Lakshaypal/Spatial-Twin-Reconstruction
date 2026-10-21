#!/usr/bin/env python3
"""
============================================================================
 verify_setup.py — check the 'recon' environment is actually usable
============================================================================
Run AFTER setup, inside the env:

    conda activate recon
    python verify_setup.py

Tells you exactly what works and what's missing, in the order that matters.
============================================================================
"""
import importlib, shutil, subprocess, sys

OK, WARN, FAIL = "[ OK ]", "[WARN]", "[FAIL]"
problems = []

def say(tag, msg):
    print(f"  {tag} {msg}")

def check_import(mod, label=None, blocking=True):
    label = label or mod
    try:
        m = importlib.import_module(mod)
        v = getattr(m, "__version__", "")
        say(OK, f"{label} {v}")
        return m
    except Exception as e:
        say(FAIL if blocking else WARN, f"{label} — {type(e).__name__}: {e}")
        if blocking:
            problems.append(label)
        return None

def check_exe(name, hint):
    p = shutil.which(name)
    if p:
        say(OK, f"{name} found: {p}")
        return True
    say(FAIL, f"{name} NOT on PATH — {hint}")
    problems.append(name)
    return False

print("=" * 62)
print(" VERIFYING 'recon' ENVIRONMENT")
print("=" * 62)

# --- python ---
print("\n[1] Python")
v = sys.version_info
if v.major == 3 and v.minor == 10:
    say(OK, f"Python {v.major}.{v.minor}.{v.micro}")
else:
    say(WARN, f"Python {v.major}.{v.minor} (3.10 recommended for nerfstudio)")

# --- torch + CUDA: the big one ---
print("\n[2] PyTorch + GPU")
torch = check_import("torch", "torch")
if torch:
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        say(OK, f"CUDA available — {name}")
        say(OK, f"CUDA version (torch): {torch.version.cuda}")
        say(OK, f"VRAM: {vram:.1f} GB")
        if vram < 7:
            say(WARN, "6 GB class GPU — use --num-downscales 2 and small datasets")
        # actually try a GPU op
        try:
            x = torch.rand(1000, 1000, device="cuda")
            _ = (x @ x).sum().item()
            say(OK, "GPU compute test passed")
        except Exception as e:
            say(FAIL, f"GPU compute test FAILED: {e}")
            problems.append("gpu-compute")
    else:
        say(FAIL, "torch.cuda.is_available() == False — CPU-only install!")
        say(WARN, "  Reinstall torch with the CUDA index-url (see SETUP_GUIDE.md)")
        problems.append("cuda")

# --- nerfstudio + gsplat ---
print("\n[3] Nerfstudio / gsplat")
check_import("nerfstudio", "nerfstudio")
check_import("gsplat", "gsplat")   # the splat renderer — must compile OK
# tinycudann is NOT needed for splatfacto; warn only
try:
    importlib.import_module("tinycudann")
    say(OK, "tinycudann (optional)")
except Exception:
    say(WARN, "tinycudann missing — fine for splatfacto, only nerfacto needs it")

# --- our reframe deps ---
print("\n[4] Reframe script deps")
check_import("py360convert", "py360convert")
check_import("cv2", "opencv-python")
check_import("numpy", "numpy")

# --- external binaries ---
print("\n[5] External tools on PATH")
check_exe("ffmpeg", "install from gyan.dev and add its bin/ to PATH")
check_exe("colmap", "install from colmap.github.io and add to PATH")

# --- nerfstudio CLI ---
print("\n[6] Nerfstudio CLI")
for cli in ("ns-train", "ns-process-data"):
    if shutil.which(cli):
        say(OK, f"{cli} found")
    else:
        say(FAIL, f"{cli} NOT found — nerfstudio install incomplete")
        problems.append(cli)

# --- verdict ---
print("\n" + "=" * 62)
if not problems:
    print(" RESULT: environment READY. Proceed to the handheld first test.")
else:
    print(f" RESULT: {len(problems)} problem(s): {', '.join(problems)}")
    print(" See SETUP_GUIDE.md -> Troubleshooting for each.")
print("=" * 62)
sys.exit(1 if problems else 0)
