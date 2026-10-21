import os
import shutil

src = "pano1_processing/views"
dst = "pano1_processing_1fps/views"
os.makedirs(dst, exist_ok=True)

for file in os.listdir(src):
    if file.endswith(".png"):
        parts = file.split('_')
        frame_idx = int(parts[1])
        if frame_idx % 2 == 0:
            shutil.copy(os.path.join(src, file), os.path.join(dst, file))
print("Done downsampling images.")