> Historical project record. For the published scope, unscaled-unit caveats, attribution and reproducibility limits, read the [current README](../README.md). Recorded success labels are not fresh verification.

# Evidence-Based Mesh Comparison Report

This report provides a strict, objective evaluation of the original raw photogrammetry mesh (`mesh_lab.ply`) versus the Screened Poisson Surface Reconstruction (`mesh_best.ply`). 

## 1. Quantitative Geometric Metrics

| Metric | Original (`mesh_lab.ply`) | Poisson v2 (`mesh_best.ply`) |
|--------|---------------------------|------------------------------|
| **Vertices** | 3,334,720 | 14,072 |
| **Faces** | 5,506,256 | 27,967 |
| **Connected Components** | **61,451** (Extremely fragmented) | **1** (Unified manifold) |
| **Surface Area** | 727.4 m² | 893.8 m² |
| **Bounding Box Vol** | 5966 m³ | 5585 m³ |

### Deviation Analysis (Original → New)
- **Mean Surface Deviation:** `0.16 meters`
- **Root Mean Square (RMS) Deviation:** `0.23 meters`
- **Hausdorff Distance (Max Deviation):** `5.77 meters`

## 2. Qualitative Visual Assessment

> [!WARNING]
> While the Poisson reconstruction successfully repaired the broken topology, it fundamentally altered the structural accuracy of the data.

- **Preservation of Building Edges:** *Degraded.* Sharp architectural corners (90-degree walls, roof edges) have been mathematically smoothed, losing their crispness.
- **Stair Geometry:** *Degraded.* Steps have been blended into a ramp-like structure due to the HC Laplacian smoothing and Poisson interpolation.
- **Vegetation:** *Severely Degraded.* Trees and foliage, which were previously represented as noisy point clusters, have been transformed into solid, rounded green "blobs."
- **Floating Artifacts:** *Improved.* The 61,450 disconnected floating noise fragments were successfully eliminated.
- **Hole Filling:** *Improved but Artificial.* The significant increase in surface area (from 727m² to 893m²) and the 5.77m Hausdorff distance confirms that Poisson hallucinated large artificial surfaces across empty space (likely the ground plane and missing walls) where no camera observations existed.
- **Performance:** *Massively Improved.* Rendering 27k faces takes sub-milliseconds, whereas 5.5M faces caused significant WebGL overhead.

## 3. Final Verdict

The original hypothesis is correct: **The new mesh is not strictly "better"; it serves a different purpose.**

**What improved?**
Visual cleanliness, viewer performance, and topological continuity. The mesh is now a single piece rather than a cloud of 61,000 fragments.

**What became worse?**
High-frequency geometric fidelity. Sharp edges were smoothed, and missing data was synthetically filled with assumed surfaces.

### Recommendation
Both datasets must be preserved for different workflows:
1. **Analysis & Engineering:** Use the **Original** raw mesh for accurate distance measurements, volumetric calculations, and structural inspection.
2. **Presentations & Web Visualization:** Use the **Poisson-cleaned (v2)** mesh for fluid, continuous interactive visualization where aesthetic completeness is preferred over millimeter accuracy.

You can inspect both meshes simultaneously via the new split-screen mode:
Launch `compare.html` to toggle wireframes and red/green overlay modes to visually confirm the 0.16m mean deviation in real-time.