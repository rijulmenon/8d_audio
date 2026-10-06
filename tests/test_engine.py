"""
Test script for verifying Real-Time Audio Engine functionality.
"""

import time
import pytest
import numpy as np
from app.audio.engine import AudioEngine
from app.audio.device_manager import AudioDeviceManager


def test_device_discovery():
    devices = AudioDeviceManager.get_devices()
    assert len(devices) > 0, "No audio devices detected!"
    inputs = AudioDeviceManager.get_input_devices()
    outputs = AudioDeviceManager.get_output_devices()
    assert len(inputs) > 0, "No audio inputs detected!"
    assert len(outputs) > 0, "No audio outputs detected!"


def test_engine_callback_logic():
    """Verify that the engine callback handles synthetic data, crossfades, and bypass correctly without hardware."""
    engine = AudioEngine(sample_rate=48000, block_size=256)
    
    indata = np.ones((256, 2), dtype=np.float32) * 0.5
    outdata = np.zeros((256, 2), dtype=np.float32)

    # 1. Bypass mode test
    engine.set_enabled(False)
    engine._unified_callback(indata, outdata, 256, None, None)
    np.testing.assert_allclose(outdata, indata, atol=1e-5)

    # 2. Toggle ON and verify smooth ramp
    engine.set_enabled(True)
    engine.set_speed(1.0)
    # Step through several callback iterations to allow crossfade blend to ramp to 1.0
    for _ in range(30):
        engine._unified_callback(indata, outdata, 256, None, None)

    # Outdata should now be fully modulated
    assert not np.allclose(outdata[:, 0], outdata[:, 1], atol=1e-3)
    assert np.all(outdata <= 1.0)
    assert np.all(outdata >= -1.0)

    # 3. Toggle OFF and verify smooth ramp back to bypass
    engine.set_enabled(False)
    for _ in range(30):
        engine._unified_callback(indata, outdata, 256, None, None)

    np.testing.assert_allclose(outdata, indata, atol=1e-4)


if __name__ == "__main__":
    print("Testing Device Manager...")
    test_device_discovery()
    print("Devices OK!")
    
    print("Testing Engine Callback Logic...")
    test_engine_callback_logic()
    print("Engine Callback Logic OK!")
