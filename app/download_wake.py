"""Explicit setup-time model download. Never invoked by a microphone request."""
import os
import urllib.request
import zipfile
from pathlib import Path
from app.wake import MODEL_NAME

def main():
    root = Path(os.getenv("YOUAI_DATA_DIR", str(Path(os.environ["LOCALAPPDATA"]) / "YouAI"))) / "models"
    target = root / MODEL_NAME
    if (target / "am" / "final.mdl").is_file():
        print("Wake model already installed.")
        return
    root.mkdir(parents=True, exist_ok=True)
    archive = root / (MODEL_NAME + ".zip")
    urllib.request.urlretrieve(f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip", archive)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            resolved = (root / entry.filename).resolve()
            if not resolved.is_relative_to(target.resolve()):
                raise ValueError("Unexpected archive path")
        bundle.extractall(root)
    archive.unlink()
    print("Wake model ready.")

if __name__ == "__main__":
    main()
