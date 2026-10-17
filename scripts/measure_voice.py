"""Smoke measurement using synthetic WAV clips under .runtime; not a user accuracy benchmark."""
import asyncio
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from faster_whisper.audio import decode_audio
import os
os.environ['YOUAI_LLM_PROVIDER']='ollama'
os.environ['YOUAI_SPEECH_PROVIDER']='local'
from app.main import wake, stream_answer

async def main():
    results = []
    for name, expected in [("wake", True), ("command", True), ("negative", False), ("unrelated", False), ("news", False)]:
        path = Path(".runtime") / f"wake-{name}.wav"
        audio = np.concatenate([decode_audio(str(path), sampling_rate=16000), np.zeros(16000, dtype=np.float32)])
        pcm = (audio * 32767).astype(np.int16).tobytes()
        recognizer = wake.recognizer()
        detected = None
        start = time.perf_counter()
        for offset in range(0, len(pcm), 2560):
            if recognizer.feed(pcm[offset:offset + 2560]):
                detected = round((offset + 2560) / 32000, 2)
                break
        result = {"clip":name, "expected":expected, "detected_at_audio_seconds":detected,
                  "compute_seconds":round(time.perf_counter()-start, 3), "passed":(detected is not None)==expected}
        results.append(result)
        print(result)
    start=time.perf_counter()
    first=None
    answer=""
    async for token in stream_answer("Explain why the sky is blue in two short sentences.", []):
        if first is None:
            first=time.perf_counter()-start
        answer+=token
    latency={"first_token_seconds":round(first or 0,3),"complete_seconds":round(time.perf_counter()-start,3)}
    print(latency)
    Path(".runtime/voice-measurements.json").write_text(json.dumps({"synthetic_wake_checks":results,"stream_latency":latency},indent=2))
    if not all(r["passed"] for r in results):
        raise SystemExit("Wake smoke checks failed")

asyncio.run(main())
