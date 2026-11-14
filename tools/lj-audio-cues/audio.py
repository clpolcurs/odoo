"""The sound side: decode an audio file, find where speech starts after a silence, and what the recogniser hears.

ffmpeg decodes the file (any format Odoo holds) to 16 kHz mono; faster-whisper recognises it with the time of every
word. The recognition of a file is kept in data/asr/<sha1>.<model>.json, so a second run costs nothing.
"""

import json
import re
import subprocess
from functools import cache
from pathlib import Path

DATA = Path(__file__).parent / "data"
SILENCE_NOISE, SILENCE_SECONDS = "-35dB", 0.25


def samples(path):
    """The audio as float32 samples at 16 kHz, mono."""
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def onsets(path):
    """Seconds at which a silence of at least SILENCE_SECONDS ends: where speech starts again."""
    log = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af",
         f"silencedetect=noise={SILENCE_NOISE}:d={SILENCE_SECONDS}", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    return [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]


@cache
def _model(name):
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=4, download_root=str(DATA / "models"))


def recognise(path, sha1, model="small"):
    """{"duration": seconds, "words": [{"start", "end", "word", "p"}]} of the audio file, from the cache if there."""
    cached = DATA / "asr" / f"{sha1}.{model}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    segments, info = _model(model).transcribe(
        samples(path), language="ja", word_timestamps=True, vad_filter=False, beam_size=5,
        condition_on_previous_text=False,
    )
    words = [
        {"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word, "p": round(w.probability, 3)}
        for segment in segments for w in (segment.words or [])
    ]
    result = {"duration": info.duration, "words": words}
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(result, ensure_ascii=False))
    return result
