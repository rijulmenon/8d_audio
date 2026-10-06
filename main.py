import numpy as np
import soundfile as sf

from eight_d import apply_8d


INPUT_FILE = "test.wav"
OUTPUT_FILE = "output_8d.wav"


audio, sample_rate = sf.read(INPUT_FILE)

print("Sample rate:", sample_rate)
print("Audio shape:", audio.shape)


if audio.ndim == 1:
    audio = audio[:, np.newaxis]


processed = apply_8d(
    audio,
    sample_rate,
    speed=0.2,
    intensity=1.0
)


sf.write(OUTPUT_FILE, processed, sample_rate)

print("8D audio created!")
print("Output:", OUTPUT_FILE)