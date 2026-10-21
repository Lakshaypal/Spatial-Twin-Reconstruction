from huggingface_hub import hf_hub_download
import os

print("Downloading lingbot-map model weights...")
path = hf_hub_download(repo_id="robbyant/lingbot-map", filename="lingbot-map.pt", local_dir=".")
print(f"Downloaded to {path}")
