@echo off
echo Starting MeshSplatting Phase 2 Demo...
call C:\Users\krris\anaconda3\Scripts\activate.bat mesh_splatting
cd "C:\Users\krris\OneDrive\Documents\FIFA 23\Desktop\version_17july\2_processing\mesh-splatting"

echo Training MeshSplatting (This will take ~45 minutes on RTX 4050)...
python train.py -s ../processed -m ../outputs/mesh_splatting_demo -r 4 --max_points 2500000 --iterations 15000

echo Extracting Opaque Mesh...
python create_ply.py -s ../processed -m ../outputs/mesh_splatting_demo --zup

echo DONE! Output mesh is at ../outputs/mesh_splatting_demo/mesh_splatting_demo_final.ply
