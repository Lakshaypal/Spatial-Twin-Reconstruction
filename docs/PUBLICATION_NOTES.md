# Publication checks — 22 October 2026

The original Downloads folder was preserved. Publication uses a separate working copy.

- README rewritten around implemented components, saved artifacts, external dependencies and historical run records.
- Existing copyright holders and upstream notices retained; missing MeshSplatting licence texts restored from an identified upstream revision.
- Python caches, machine-specific `.so` files and the supplied third-party paper PDF omitted. Original paper links are in `references/README.md`.
- Configuration example changed from a personal absolute path to relative workspace paths.
- Historical reports remain as experiment notes. Their success labels and hardware claims are not fresh verification. Raw datasets, output meshes, checkpoints, complete Unity project and some upstream training dependencies are absent.
- Route search is a heuristic skeleton-graph procedure; procedural runner and NavMesh agents are not RL-trained policies. The saved geometry is unscaled; legacy metre labels do not establish metric calibration.

Validation performed for publication: source/archive structure tests, Python syntax checks, a known-distance scale-factor example and a credential scan. GPU reconstruction, CUDA compilation, mesh-quality metrics, Unity execution and real sensor operation were not reproduced on this Mac.
