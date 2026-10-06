"""
Automated DSP Test Suite for 8D Audio Engine.
Covers all 12 core requirements + streaming buffer continuity:
1. Input/output sample count consistency
2. Stereo input remains stereo
3. Mono input handled correctly
4. No NaN values produced
5. No Inf values produced
6. Output stays within expected [-1.0, 1.0] range
7. OFF/Bypass mode produces effectively unchanged audio
8. ON mode modifies stereo balance
9. Changing speed does not crash
10. Changing intensity does not crash
11. Short audio buffers work (e.g. 64, 128, 256 samples)
12. Long audio buffers work (e.g. 8192, 16384 samples)
13. Stream continuity: chunk-by-chunk processing matches continuous phase evolution
"""

import pytest
import numpy as np
from eight_d import EightDProcessor, EightDSettings, apply_8d


@pytest.fixture
def sample_rate():
    return 44100


@pytest.fixture
def stereo_sine_audio(sample_rate):
    """1 second stereo 440Hz test sine wave."""
    t = np.linspace(0, 1.0, sample_rate, endpoint=False)
    sig = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    return np.column_stack((sig, sig))


def test_sample_count_consistency(stereo_sine_audio, sample_rate):
    """1. Input/output sample count remains consistent."""
    proc = EightDProcessor(sample_rate=sample_rate)
    settings = EightDSettings(enabled=True, speed=0.3, intensity=0.8)
    out = proc.process_block(stereo_sine_audio, settings)
    assert len(out) == len(stereo_sine_audio)
    assert out.shape == stereo_sine_audio.shape


def test_stereo_remains_stereo(stereo_sine_audio, sample_rate):
    """2. Stereo audio remains stereo."""
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(stereo_sine_audio, EightDSettings(enabled=True))
    assert out.ndim == 2
    assert out.shape[1] == 2


def test_mono_input_handled_correctly(sample_rate):
    """3. Mono input (1D array or 2D Nx1) is converted to stereo (Nx2)."""
    t = np.linspace(0, 0.5, int(sample_rate * 0.5), endpoint=False)
    mono_1d = (0.5 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    mono_2d = mono_1d[:, np.newaxis]

    proc = EightDProcessor(sample_rate=sample_rate)
    out_1d = proc.process_block(mono_1d, EightDSettings())
    assert out_1d.shape == (len(mono_1d), 2)

    proc.reset()
    out_2d = proc.process_block(mono_2d, EightDSettings())
    assert out_2d.shape == (len(mono_2d), 2)


def test_no_nan_values(stereo_sine_audio, sample_rate):
    """4. No NaN values are produced."""
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(stereo_sine_audio, EightDSettings(enabled=True, intensity=1.0))
    assert not np.isnan(out).any()


def test_no_inf_values(stereo_sine_audio, sample_rate):
    """5. No infinite values are produced."""
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(stereo_sine_audio, EightDSettings(enabled=True, intensity=1.0))
    assert not np.isinf(out).any()


def test_output_stays_within_range(sample_rate):
    """6. Output stays within expected range [-1.0, 1.0], even with hot input."""
    # Hot input (amplitude 2.5) to test limiter protection
    hot_audio = (np.ones((1000, 2), dtype=np.float32)) * 2.5
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(hot_audio, EightDSettings(enabled=True))
    assert np.all(out <= 1.0)
    assert np.all(out >= -1.0)


def test_off_mode_produces_unchanged_audio(stereo_sine_audio, sample_rate):
    """7. OFF mode produces effectively unchanged audio."""
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(stereo_sine_audio, EightDSettings(enabled=False))
    np.testing.assert_allclose(out, stereo_sine_audio, atol=1e-6)


def test_on_mode_modifies_stereo_balance(stereo_sine_audio, sample_rate):
    """8. ON mode modifies the stereo balance."""
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(stereo_sine_audio, EightDSettings(enabled=True, speed=0.5, intensity=0.9))
    # Channels in input are identical, but in output they should differ over time
    assert not np.allclose(out[:, 0], out[:, 1], atol=1e-3)


def test_changing_speed_does_not_crash(stereo_sine_audio, sample_rate):
    """9. Changing speed does not crash."""
    proc = EightDProcessor(sample_rate=sample_rate)
    for speed in [0.01, 0.1, 0.5, 2.0, 10.0]:
        out = proc.process_block(stereo_sine_audio[:1000], EightDSettings(speed=speed))
        assert out.shape == (1000, 2)
        assert not np.isnan(out).any()


def test_changing_intensity_does_not_crash(stereo_sine_audio, sample_rate):
    """10. Changing intensity does not crash."""
    proc = EightDProcessor(sample_rate=sample_rate)
    for intensity in [0.0, 0.25, 0.5, 0.75, 1.0]:
        out = proc.process_block(stereo_sine_audio[:1000], EightDSettings(intensity=intensity))
        assert out.shape == (1000, 2)
        assert not np.isnan(out).any()


@pytest.mark.parametrize("buffer_size", [32, 64, 128, 256, 512])
def test_short_audio_buffers(buffer_size, sample_rate):
    """11. Short audio buffers work without error or distortion."""
    short_input = np.random.uniform(-0.5, 0.5, (buffer_size, 2)).astype(np.float32)
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(short_input, EightDSettings(enabled=True))
    assert out.shape == (buffer_size, 2)
    assert not np.isnan(out).any()


@pytest.mark.parametrize("buffer_size", [4096, 8192, 16384])
def test_long_audio_buffers(buffer_size, sample_rate):
    """12. Long audio buffers work properly."""
    long_input = np.random.uniform(-0.5, 0.5, (buffer_size, 2)).astype(np.float32)
    proc = EightDProcessor(sample_rate=sample_rate)
    out = proc.process_block(long_input, EightDSettings(enabled=True))
    assert out.shape == (buffer_size, 2)
    assert not np.isnan(out).any()


def test_stream_phase_continuity(sample_rate):
    """13. Chunked processing maintains continuous phase across block boundaries."""
    total_samples = 4096
    chunk_size = 512
    t = np.linspace(0, total_samples / sample_rate, total_samples, endpoint=False)
    full_audio = np.column_stack((np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t))).astype(np.float32)

    # Process all at once
    proc_single = EightDProcessor(sample_rate=sample_rate)
    settings = EightDSettings(enabled=True, speed=0.5, intensity=0.9, reverb_mix=0.0)
    single_out = proc_single.process_block(full_audio, settings)

    # Process in chunks
    proc_chunked = EightDProcessor(sample_rate=sample_rate)
    chunked_out_list = []
    for i in range(0, total_samples, chunk_size):
        chunk = full_audio[i:i + chunk_size]
        chunk_res = proc_chunked.process_block(chunk, settings)
        chunked_out_list.append(chunk_res)

    chunked_out = np.vstack(chunked_out_list)

    # They should match within float precision since phase tracks smoothly
    np.testing.assert_allclose(chunked_out, single_out, atol=1e-5)
