# FIRST TEST — Handheld Room → 3D Model

**Goal:** prove the whole processing chain works, on the easiest possible data,
before the drone is involved. No drone. No pose.csv. No 5G. Just you, the
Insta360 X3, and one room.

**Time:** ~2 hours end-to-end. **Success = a 3D model of a room you can spin
around on screen.**

Once this works, everything after (drone footage, pose.csv scaling, meshes,
chunk stitching) is the *same pipeline with better inputs*.

> **Why the easy tools first:** this test uses COLMAP + Nerfstudio splatfacto —
> mature, well-documented, install-and-go. We are NOT using LingBot-Map or
> MeshSplatting yet. Prove the chain with tools that definitely work, then
> upgrade one component at a time. If you start with research code you'll never
> know whether a failure is your pipeline or their code.

---

## What to install (once)

```
# 1. Insta360 Studio      -> insta360.com/download   (Windows/Mac — stitching)
# 2. FFmpeg               -> add to PATH
# 3. Miniconda            -> then:
conda create -n recon python=3.10 -y
conda activate recon

# 4. PyTorch with CUDA (match your CUDA version — check `nvidia-smi`)
#    see pytorch.org for the exact command for your setup

# 5. Nerfstudio (includes gsplat + runs COLMAP for you)
pip install nerfstudio

# 6. COLMAP (Nerfstudio calls it)
#    Windows: download from colmap.github.io, add to PATH
#    Linux:   sudo apt install colmap

# 7. reframe.py deps
pip install py360convert opencv-python
```

Verify before you start:
```
ffmpeg -version
colmap -h
ns-train --help
nvidia-smi          # confirm your GPU + VRAM is visible
```

---

## STEP 0 — Capture the video (15 min)

**Pick the right room. This decides success more than any setting.**

| Good room ✅ | Bad room ❌ |
|---|---|
| Furniture, posters, shelves, clutter | Bare white walls |
| Bright, even lighting | Dim / lights that change |
| Matte surfaces | Mirrors, glass, glossy floors |
| Varied texture | Repeating tiles, plain carpet |

A cluttered lab or office = easy mode. An empty white seminar hall = will fail.
*(Trick if you must use a plain room: tape a few newspaper/posters on the walls
as temporary texture. This is a legitimate, standard technique.)*

**How to shoot:**
1. X3 on a monopod/selfie stick, held **above head height**, arm extended.
2. **Lock exposure and white balance** before you start. Do not let it auto-adjust.
3. Record **5.7K / 30fps**.
4. **Walk SLOWLY** — about 0.5 m/s, half normal walking pace. Smooth, no jerks.
   *Motion blur is the #1 killer. Slow beats everything.*
5. Walk a **loop around the room perimeter and return to where you started**
   (this "loop closure" massively helps the reconstruction).
6. Stay ~1–2 m from walls. Don't hug them.
7. **Keep it to 60–90 seconds for this first test.** Short = fast = you find
   problems today, not tomorrow. Longer videos come after this works.

**Also do now (for Step 7):** with a tape measure, measure ONE known distance in
the room — a door width, a table edge, a wall — and write it down. e.g.
`door width = 0.90 m`. You'll need it to set scale.

---

## STEP 1 — Stitch (Insta360 Studio, ~10 min)

1. Import the `.insv` file.
2. Export → **Equirectangular** (NOT reframed/flat), max resolution (5760×2880).
3. FlowState stabilization ON is fine.
4. Save as `pano.mp4`.

**Checkpoint:** open `pano.mp4` — it should look like a warped world-map view
(that's equirectangular, correct). If it looks like a normal flat video, you
exported the wrong mode — redo.

---

## STEP 2 — Reframe 360 → pinhole views (~5 min)

```
conda activate recon
python reframe.py pano.mp4 --out views/ --fps 1 --face 1000
```

This extracts 1 frame/sec and turns each into 5 pinhole images (front/right/back/
left/up), **dropping the downward face** (that's where you and the monopod are).

For a 90-second clip: ~90 frames × 5 = **~450 images**. That's the sweet spot for
a fast first test.

**Checkpoint:** open `views/` — you should see normal-looking photos of the room
from different directions. **You should NOT see yourself or the monopod** in any
of them. If you do, the nadir drop isn't enough — tell me and we'll add a mask.

---

## STEP 3 — Camera poses (COLMAP, ~20–60 min)

Nerfstudio runs COLMAP for you — one command:

```
ns-process-data images --data views/ --output-dir processed/
```

Go make tea. This finds features in every image and works out where each photo
was taken from. It's the slowest step.

**Checkpoint — the most important one in the whole test:**
Read the output. It tells you how many images were **registered** (successfully
placed).

- **>80% registered** → excellent, continue.
- **50–80%** → usable, continue but expect gaps.
- **<50%** → ❌ STOP. The capture was the problem, not the software. Go back to
  Step 0: slower walk, better-lit room, more texture. Re-shoot. **Do not try to
  fix this downstream — you can't.**

---

## STEP 4 — Train the 3D model (~20–40 min)

```
ns-train splatfacto --data processed/
```

This builds the 3D Gaussian splat model. A live viewer link appears in the
terminal (usually `http://localhost:7007`) — **open it and watch the room build
itself in real time.** That's your first proof it works, and it makes a great
screen-recording for the report.

**Your GPU has 6 GB. If it crashes with CUDA out-of-memory:**
- Re-run Step 3 with downscaling: `ns-process-data images --data views/ --output-dir processed/ --num-downscales 2`
- Or check `ns-train splatfacto --help` for the current memory flags (they change
  between versions — don't trust flags copied from old blog posts).
- Watch usage in another terminal: `nvidia-smi -l 1`

Let it run to completion (default ~30k steps), or stop it early once the viewer
looks good — even 7k steps gives a recognisable room.

---

## STEP 5 — Export and view

```
ns-export gaussian-splat --load-config outputs/processed/splatfacto/<RUN>/config.yml --output-dir exports/
```
(replace `<RUN>` with the timestamped folder that was created)

Then open **https://superspl.at/editor** in your browser and **drag the exported
`.ply` in**. Nothing to install. Spin it around. Delete floating junk with the
selection tools.

**🎉 If you can spin your room around on screen — the pipeline works.** That is
the milestone. Everything else is refinement.

---

## STEP 6 — Check quality honestly

Look at the model and note:
- Are walls flat, or wobbly?
- Are there holes where you didn't walk?
- Is anything smeared/ghosted? (= motion blur or bad poses there)

Write these down — they're your "capture lessons" for the drone flights.

---

## STEP 7 — Set the scale (make it real metres)

Right now the model has arbitrary size. Use your tape measurement:

1. In **CloudCompare** (or SuperSplat's measure tool), load the exported `.ply`
   and measure the same thing you tape-measured (e.g. the door width). Note the
   two endpoint coordinates.
2. Compute the factor:
```
python scale_from_pose.py --tape 0.90 --p1 x1,y1,z1 --p2 x2,y2,z2
```
3. It prints `SCALE FACTOR`. Apply it to the model (CloudCompare: Edit → Multiply;
   Blender: scale by that number).
4. **Verify:** measure a *different* known distance. It should now read correct
   within a few cm.

*(When you switch to drone footage, `pose.csv` replaces this manual step — the
drone's own metric trajectory sets the scale automatically. This tape method
stays as your cross-check.)*

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| COLMAP registers <50% | blur / blank walls / too fast | re-shoot slower, more textured room |
| Model is smeared | motion blur | walk slower, more light |
| Big holes | didn't cover that area | walk the perimeter fully, loop back |
| CUDA out of memory | 6 GB limit | `--num-downscales 2`, fewer images (`--fps 1`) |
| You appear in the model | nadir not fully removed | tell me — we add a side-face mask |
| `ns-train` flag errors | version differences | `ns-train splatfacto --help` — use current flags |
| Warped/duplicated walls | loop closure failed | ensure you return to the start point |

---

## What comes next (in order)

1. ✅ **This test** — handheld, one room, splats. *You are here.*
2. **Bigger handheld** — 3–5 min, multiple rooms, `--fps 2`. Same commands.
3. **Add the mesh** — swap splatfacto → MeshSplatting (or 2DGS/SuGaR fallback)
   to get a solid game-engine mesh instead of splats.
4. **Add LingBot-Map** — swap COLMAP → LingBot-Map for poses (your innovation
   claim). Keep COLMAP as fallback.
5. **Add the drone** — same pipeline, but now `pose.csv` gives scale
   automatically and you process one chunk per folder.
6. **Stitch chunks** — ICP the overlaps, assemble in USD.

**Do not skip ahead.** Each step changes exactly one thing, so when something
breaks you know what broke.
