import io
import os
import threading
from pathlib import Path

class Speech:
    def __init__(self, root: Path):
        self.root = root
        self.model = None
        self.lock = threading.Lock()
        self.load_lock = threading.Lock()
        self.name = os.getenv("YOUAI_WHISPER_MODEL", "base")
        self.error = None

    def load(self):
        with self.load_lock:
            if self.model is None:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(self.name, device="cpu", compute_type="int8",
                                          cpu_threads=4, download_root=str(self.root),
                                          local_files_only=os.getenv("YOUAI_ALLOW_DOWNLOAD") != "1")
        return self.model

    def transcribe(self, audio, language=None):
        # One inference at a time keeps wake mode from exhausting memory.
        with self.lock:
            model = self.load()
            segments, info = model.transcribe(io.BytesIO(audio), beam_size=1,
                vad_filter=True, condition_on_previous_text=False, language=language)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            return {"text": text, "language": info.language}
