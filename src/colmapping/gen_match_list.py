"""
Generate a custom match list for COLMAP that only pairs images that
actually share visual overlap:
  1. Same face direction, consecutive timesteps (temporal neighbors)
  2. Adjacent face directions at the same timestep (spatial neighbors)
     Adjacent pairs: F-R, R-B, B-L, L-F (horizontal ring) + F-U, R-U, B-U, L-U (up)
"""
import os
import re
from collections import defaultdict

views_dir = "views"
files = sorted(os.listdir(views_dir))

# Parse filenames: eq_XXXX_D.png -> (frame_idx, face)
parsed = []
for f in files:
    m = re.match(r'eq_(\d+)_([FRBLU])\.png', f)
    if m:
        parsed.append((int(m.group(1)), m.group(2), f))

# Group by frame index
by_frame = defaultdict(dict)
for idx, face, fname in parsed:
    by_frame[idx][face] = fname

# Define adjacency for cube faces (which faces share an edge)
adjacent = {
    'F': ['R', 'L', 'U'],
    'R': ['F', 'B', 'U'],
    'B': ['R', 'L', 'U'],
    'L': ['F', 'B', 'U'],
    'U': ['F', 'R', 'B', 'L'],
}

frame_indices = sorted(by_frame.keys())
pairs = set()

for i, idx in enumerate(frame_indices):
    faces_here = by_frame[idx]
    
    # 1. Spatial neighbors: adjacent faces at same timestep
    for face, fname in faces_here.items():
        for adj_face in adjacent.get(face, []):
            if adj_face in faces_here:
                pair = tuple(sorted([fname, faces_here[adj_face]]))
                pairs.add(pair)
    
    # 2. Temporal neighbors: same face across nearby timesteps
    for j in range(1, 6):  # look 5 timesteps ahead
        if i + j < len(frame_indices):
            next_idx = frame_indices[i + j]
            faces_next = by_frame[next_idx]
            for face, fname in faces_here.items():
                if face in faces_next:
                    pair = tuple(sorted([fname, faces_next[face]]))
                    pairs.add(pair)
                # Also cross-face temporal: F->R next frame etc.
                for adj_face in adjacent.get(face, []):
                    if adj_face in faces_next:
                        pair = tuple(sorted([fname, faces_next[adj_face]]))
                        pairs.add(pair)

# Write match list
with open("match_list.txt", "w") as f:
    for a, b in sorted(pairs):
        f.write(f"{a} {b}\n")

print(f"Generated {len(pairs)} pairs from {len(parsed)} images across {len(frame_indices)} frames")
