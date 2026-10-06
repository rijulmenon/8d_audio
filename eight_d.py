import numpy as np


def apply_8d(audio, sample_rate, speed=0.2, intensity=1.0):
    """
    Apply a simple 8D-style rotating stereo effect.

    audio:
        Stereo audio as a NumPy array:
        [samples, 2]

    sample_rate:
        Audio sample rate, e.g. 44100

    speed:
        Number of left/right cycles per second.

    intensity:
        How strongly the panning effect is applied.
    """

    num_samples = len(audio)

    # Create time values for every audio sample
    time = np.arange(num_samples) / sample_rate

    # Create a smooth left-right movement
    movement = np.sin(2 * np.pi * speed * time)

    # Convert movement into left/right gains
    left_gain = np.cos((movement + 1) * np.pi / 4)
    right_gain = np.sin((movement + 1) * np.pi / 4)

    # Keep some of the original signal
    left_gain = (1 - intensity) + intensity * left_gain
    right_gain = (1 - intensity) + intensity * right_gain

    # Apply gains
    output = audio.copy()

    output[:, 0] *= left_gain
    output[:, 1] *= right_gain

    return output