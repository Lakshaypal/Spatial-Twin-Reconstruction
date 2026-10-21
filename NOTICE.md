# Attribution and component notices

This is Lakshay Pal's summer internship project archive from the 5G DoT Lab. It assembles reconstruction, geometry processing, spatial analysis and simulation work around existing research implementations. It is not the official implementation of COLMAP, MeshSplatting, LingBot-Map or 3D Gaussian Splatting.

## Existing notices retained

- The supplied root `LICENSE` names **Krrish Barsiwal** as copyright holder. That notice is retained without replacing or assigning its authorship.
- `src/mesh_splatting` contains upstream-derived source with **Inria/GRAPHDECO** and **University of Liège/TELIM** copyright headers. Those headers remain intact.
- Missing top-level `LICENSE.md` and `LICENSE_GS.md` texts for that snapshot were restored from the official MeshSplatting repository at commit `2a810a6c353215685307da3d4cc6ebd73b1c387b`. This identifies the source of the restored notices, not the exact historical revision of every supplied file.
- The differentiable triangle rasterizer retains its own `LICENSE.md` and `LICENSE_GS.md` files. The bundled `stbi_image_write.h` retains its original notices.
- Local rasterizer sources and camera-reader code are adaptations; the included upstream README is retained as upstream documentation and may describe files absent from this archive.

The root MIT notice does not relicense third-party components. Original upstream terms and file-level notices continue to apply. No lab endorsement, publication authorship or invention of the upstream algorithms is implied.

## Research implementations

- [MeshSplatting: Differentiable Rendering with Opaque Meshes](https://github.com/meshsplatting/mesh-splatting)
- [LingBot-Map: Geometric Context Transformer for Streaming 3D Reconstruction](https://github.com/Robbyant/lingbot-map)
- [COLMAP](https://github.com/colmap/colmap)
- [3D Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting)
- [Pcx for Unity](https://github.com/keijiro/Pcx)

The supplied paper PDF is replaced by reference links for this publication. Local compiled extensions, Python caches and machine-specific binaries are not distributed.
