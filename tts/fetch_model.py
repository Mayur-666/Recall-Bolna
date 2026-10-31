"""Build-time download of Kokoro-82M into the image, pinned to one Hugging Face revision.

Run from the Dockerfile; the service then works with no network and no files from the host.
"""

import os
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO = "hexgrad/Kokoro-82M"
REVISION = os.environ["KOKORO_REVISION"]
VOICES = os.environ["KOKORO_VOICES"].split()
DEST = Path(os.environ.get("KOKORO_DIR", "/models/kokoro"))

files = ["config.json", "kokoro-v1_0.pth", *[f"voices/{v}.pt" for v in VOICES]]
for name in files:
    path = hf_hub_download(REPO, name, revision=REVISION, local_dir=DEST)
    print(f"{name}: {Path(path).stat().st_size / 1e6:.1f} MB")
print(f"Kokoro-82M @ {REVISION[:8]} -> {DEST} ({len(VOICES)} voices)")
