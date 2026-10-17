"""Small local streaming recognizer used only for activation, not command STT."""
import json
import threading
from pathlib import Path

MODEL_NAME = "vosk-model-small-en-us-0.15"

class WakeEngine:
    def __init__(self, root: Path):
        self.path = root / MODEL_NAME
        self.model = None
        self.lock = threading.Lock()

    def recognizer(self, stability=2):
        from vosk import Model, KaldiRecognizer, SetLogLevel
        with self.lock:
            if self.model is None:
                if not self.path.is_dir():
                    raise RuntimeError("Run setup.ps1 to download the wake model.")
                SetLogLevel(-1)
                self.model = Model(str(self.path))
        # Include unknown speech rather than forcing every sound into our phrase.
        recognizer = KaldiRecognizer(self.model, 16000, json.dumps(["hey you", "[unk]"]))
        recognizer.SetWords(True)
        return WakeSession(recognizer, stability)

class WakeSession:
    def __init__(self, recognizer, stability=2):
        self.recognizer = recognizer
        self.matches = 0
        self.stability = stability

    def feed(self, data: bytes):
        final = self.recognizer.AcceptWaveform(data)
        result = json.loads(self.recognizer.Result() if final else self.recognizer.PartialResult())
        words = result.get("text" if final else "partial", "").split()
        found = any(words[i:i + 2] == ["hey", "you"] for i in range(len(words) - 1))
        if final and result.get("result"):
            found = found and all(w.get("conf",1)>=0.6 for w in result["result"] if w.get("word") in ("hey","you"))
        self.matches = self.matches + 1 if found else 0
        # Require stability across two frames, or a completed phrase.
        if found and (final or self.matches >= self.stability):
            self.recognizer.Reset()
            self.matches = 0
            return True
        return False
