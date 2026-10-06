"""
8D Audio DSP Engine
Provides smooth continuous spatial movement, equal-power panning,
subtle distance modulation, and safety limiting without digital clipping.
Supports stateful processing across sequential audio buffers.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class EightDSettings:
    """Settings controlling 8D Audio processing."""
    enabled: bool = True
    speed: float = 0.2        # Rotation cycles per second (Hz)
    intensity: float = 0.85   # Effect depth [0.0 = bypass/dry, 1.0 = maximum movement]
    reverb_mix: float = 0.15  # Subtle acoustic space mix [0.0 to 0.4]


class EightDProcessor:
    """
    Stateful 8D Audio Processor suitable for both offline batch processing
    and streaming real-time audio chunk processing.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        # Continuous phase angle [0, 2*pi) for seamless block-to-block continuity
        self.phase = 0.0

        # Simple comb delay line for subtle headphone crossfeed / spatial ambiance
        # ~25ms delay buffer
        self._delay_len = max(1, int(0.025 * sample_rate))
        self._delay_buf_l = np.zeros(self._delay_len, dtype=np.float32)
        self._delay_buf_r = np.zeros(self._delay_len, dtype=np.float32)
        self._delay_pos = 0

    def reset(self):
        """Reset phase and internal delay lines."""
        self.phase = 0.0
        self._delay_buf_l.fill(0.0)
        self._delay_buf_r.fill(0.0)
        self._delay_pos = 0

    def process_block(self, audio_block: np.ndarray, settings: EightDSettings) -> np.ndarray:
        """
        Process an audio block with 8D spatial movement.

        Parameters:
        -----------
        audio_block: np.ndarray
            Shape: (N, 2) stereo or (N,) / (N, 1) mono float audio array.
        settings: EightDSettings
            Parameters for speed, intensity, enabled, and ambiance.

        Returns:
        --------
        np.ndarray:
            Processed float32 stereo array of shape (N, 2).
        """
        # Ensure audio is float32
        if audio_block.dtype != np.float32:
            audio = audio_block.astype(np.float32)
        else:
            audio = audio_block.copy()

        # Handle mono -> stereo expansion
        if audio.ndim == 1:
            audio = np.column_stack((audio, audio))
        elif audio.ndim == 2 and audio.shape[1] == 1:
            audio = np.column_stack((audio[:, 0], audio[:, 0]))

        num_samples = len(audio)
        if num_samples == 0:
            return np.zeros((0, 2), dtype=np.float32)

        # Bypass mode: return input safely normalized/clipped to [-1.0, 1.0]
        if not settings.enabled or settings.intensity <= 0.0:
            return np.clip(audio, -1.0, 1.0)

        # Compute sample phase increments
        # phase(t) = 2 * pi * speed * t
        d_phase = 2.0 * np.pi * settings.speed / self.sample_rate
        phases = self.phase + np.arange(num_samples, dtype=np.float32) * d_phase
        # Update stateful phase wrapped to [0, 2*pi)
        self.phase = float((self.phase + num_samples * d_phase) % (2.0 * np.pi))

        # Position pan: -1.0 (full left) to +1.0 (full right)
        pan = np.sin(phases) * settings.intensity

        # Equal-power panning law:
        # angle ranges from 0 (Left) to pi/2 (Right) when pan is in [-1, 1]
        # angle = (pan + 1) * pi / 4
        pan_angle = (pan + 1.0) * (np.pi / 4.0)
        gain_left = np.cos(pan_angle)
        gain_right = np.sin(pan_angle)

        # Distance/front-back perception modulation (subtle volume dipping when moving behind)
        # Using cos(phases) to create circular orbit depth
        depth = (np.cos(phases) * 0.15 * settings.intensity) + (1.0 - 0.15 * settings.intensity)
        gain_left *= depth
        gain_right *= depth

        # Apply panning gains
        left_channel = audio[:, 0] * gain_left
        right_channel = audio[:, 1] * gain_right

        # Subtle acoustic ambiance / crossfeed for natural headphone externalization
        if settings.reverb_mix > 0.0:
            # Vectorized comb delay processing
            d_len = self._delay_len
            d_l = self._delay_buf_l
            d_r = self._delay_buf_r
            pos = self._delay_pos

            delayed_l = np.empty(num_samples, dtype=np.float32)
            delayed_r = np.empty(num_samples, dtype=np.float32)

            for i in range(num_samples):
                delayed_l[i] = d_l[pos]
                delayed_r[i] = d_r[pos]
                # Feed delayed opposite channel with slight decay (0.4)
                d_l[pos] = audio[i, 0] + 0.35 * d_l[pos]
                d_r[pos] = audio[i, 1] + 0.35 * d_r[pos]
                pos = (pos + 1) % d_len

            self._delay_pos = pos

            # Crossfeed mix into opposite channels for spacious out-of-head perception
            mix = settings.reverb_mix * settings.intensity
            left_channel = (1.0 - mix) * left_channel + mix * delayed_r
            right_channel = (1.0 - mix) * right_channel + mix * delayed_l

        # Combine into stereo
        output = np.column_stack((left_channel, right_channel))

        # Soft-knee peak limiting to prevent digital clipping while preserving dynamics
        peak = np.max(np.abs(output))
        if peak > 0.95:
            # Soft compression curve tanh
            output = 0.95 * np.tanh(output / 0.95)

        return np.clip(output, -1.0, 1.0).astype(np.float32)


def apply_8d(
    audio: np.ndarray,
    sample_rate: int,
    speed: float = 0.2,
    intensity: float = 0.85,
    reverb_mix: float = 0.15,
    enabled: bool = True
) -> np.ndarray:
    """
    Convenience function to apply 8D audio to a complete audio array in one shot.
    """
    processor = EightDProcessor(sample_rate=sample_rate)
    settings = EightDSettings(
        enabled=enabled,
        speed=speed,
        intensity=intensity,
        reverb_mix=reverb_mix
    )
    return processor.process_block(audio, settings)