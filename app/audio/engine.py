"""
Real-time Audio Processing Engine.
Manages low-latency audio streams with smooth click-free bypass transitions,
peak meters, robust error handling, and support for cross-host API device pairs
(e.g., MME/DirectSound Input with WASAPI/DirectSound Output).
"""

import time
import threading
from typing import Callable, Optional
import numpy as np
import sounddevice as sd

from eight_d import EightDProcessor, EightDSettings
from app.audio.buffer import AudioRingQueue


class AudioEngine:
    """
    Real-time audio processing engine.
    Supports either unified full-duplex stream (when input & output share the same host API)
    or decoupled dual-streams (InputStream + OutputStream connected via a low-latency ring buffer),
    completely eliminating PortAudio's 'Illegal combination of I/O devices' error!
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        block_size: int = 512,
        input_device: Optional[int] = None,
        output_device: Optional[int] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_peak_level: Optional[Callable[[float, float], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.input_device = input_device
        self.output_device = output_device
        self.on_status_change = on_status_change
        self.on_peak_level = on_peak_level

        self.processor = EightDProcessor(sample_rate=sample_rate)
        self.settings = EightDSettings(
            enabled=False,
            speed=0.2,
            intensity=0.85,
            reverb_mix=0.15
        )

        # Smooth bypass crossfade state:
        self.current_blend = 0.0
        self.target_blend = 0.0
        self.blend_step = 0.05  # crossfade over ~20 blocks (~200ms)

        self._unified_stream: Optional[sd.Stream] = None
        self._input_stream: Optional[sd.InputStream] = None
        self._output_stream: Optional[sd.OutputStream] = None
        self._ring_queue = AudioRingQueue(maxsize=12)

        self._is_running = False
        self._lock = threading.Lock()

        # Telemetry / metrics
        self.total_frames_processed = 0
        self.buffer_underruns = 0
        self.cpu_load_approx = 0.0

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_enabled(self, enabled: bool):
        """Toggle 8D effect with smooth crossfade ramp."""
        with self._lock:
            self.settings.enabled = enabled
            self.target_blend = 1.0 if enabled else 0.0

    def set_speed(self, speed: float):
        with self._lock:
            self.settings.speed = max(0.01, min(5.0, float(speed)))

    def set_intensity(self, intensity: float):
        with self._lock:
            self.settings.intensity = max(0.0, min(1.0, float(intensity)))

    def set_reverb_mix(self, mix: float):
        with self._lock:
            self.settings.reverb_mix = max(0.0, min(0.5, float(mix)))

    def _process_frame(self, stereo_in: np.ndarray, frames: int) -> np.ndarray:
        """Internal DSP and bypass crossfading logic."""
        # Calculate peak for UI metering
        if self.on_peak_level:
            peak_l = float(np.max(np.abs(stereo_in[:, 0])))
            peak_r = float(np.max(np.abs(stereo_in[:, 1])))
            self.on_peak_level(peak_l, peak_r)

        # Thread-safe read of DSP parameters
        with self._lock:
            current_settings = EightDSettings(
                enabled=True,
                speed=self.settings.speed,
                intensity=self.settings.intensity,
                reverb_mix=self.settings.reverb_mix
            )
            target_blend = self.target_blend

        # Advance smooth crossfade ramp
        if self.current_blend < target_blend:
            self.current_blend = min(target_blend, self.current_blend + self.blend_step)
        elif self.current_blend > target_blend:
            self.current_blend = max(target_blend, self.current_blend - self.blend_step)

        blend = self.current_blend

        if blend <= 0.001:
            out_audio = stereo_in
        else:
            wet_out = self.processor.process_block(stereo_in, current_settings)
            if blend >= 0.999:
                out_audio = wet_out
            else:
                out_audio = (1.0 - blend) * stereo_in + blend * wet_out

        self.total_frames_processed += frames
        return out_audio

    def _unified_callback(self, indata, outdata, frames, time_info, status):
        """Unified full-duplex callback for matching host APIs."""
        if status:
            self.buffer_underruns += 1

        start_time = time.perf_counter()

        in_channels = indata.shape[1] if indata.ndim > 1 else 1
        stereo_in = np.column_stack((indata[:, 0], indata[:, 0])) if in_channels == 1 else indata[:, :2]

        outdata[:] = self._process_frame(stereo_in, frames)

        elapsed = time.perf_counter() - start_time
        buffer_period = frames / self.sample_rate
        if buffer_period > 0:
            self.cpu_load_approx = min(100.0, (elapsed / buffer_period) * 100.0)

    def _input_callback(self, indata, frames, time_info, status):
        """Independent input callback for decoupled dual-stream operation."""
        if not self._is_running:
            return
        if status:
            self.buffer_underruns += 1

        in_channels = indata.shape[1] if indata.ndim > 1 else 1
        stereo_in = np.column_stack((indata[:, 0], indata[:, 0])) if in_channels == 1 else indata[:, :2].copy()

        self._ring_queue.write(stereo_in)

    def _output_callback(self, outdata, frames, time_info, status):
        """Independent output callback for decoupled dual-stream operation."""
        if not self._is_running:
            outdata.fill(0)
            return
        if status:
            self.buffer_underruns += 1

        start_time = time.perf_counter()
        stereo_in = self._ring_queue.read((frames, 2), dtype=np.float32)

        outdata[:] = self._process_frame(stereo_in, frames)

        elapsed = time.perf_counter() - start_time
        buffer_period = frames / self.sample_rate
        if buffer_period > 0:
            self.cpu_load_approx = min(100.0, (elapsed / buffer_period) * 100.0)

    def start(self):
        """Start real-time audio streaming."""
        if self._is_running:
            return

        self.processor.reset()
        self.current_blend = 1.0 if self.settings.enabled else 0.0
        self.target_blend = self.current_blend
        self._ring_queue.clear()

        # Check if input and output share the same PortAudio Host API
        devices = sd.query_devices()
        in_api = devices[self.input_device]['hostapi'] if self.input_device is not None else None
        out_api = devices[self.output_device]['hostapi'] if self.output_device is not None else None

        can_use_unified = (in_api is not None and in_api == out_api)

        if can_use_unified:
            try:
                self._unified_stream = sd.Stream(
                    device=(self.input_device, self.output_device),
                    samplerate=self.sample_rate,
                    blocksize=self.block_size,
                    channels=(2, 2),
                    dtype=np.float32,
                    latency='low',
                    callback=self._unified_callback
                )
                self._unified_stream.start()
                self._is_running = True
                if self.on_status_change:
                    self.on_status_change("Running (Unified Stream)")
                return
            except Exception:
                # If unified fails for any driver reason, seamlessly fallback to dual-stream
                if self._unified_stream:
                    try:
                        self._unified_stream.close()
                    except Exception:
                        pass
                    self._unified_stream = None

        # Cross-API or fallback mode: Dual Stream (InputStream + OutputStream)
        try:
            self._input_stream = sd.InputStream(
                device=self.input_device,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=2,
                dtype=np.float32,
                latency='low',
                callback=self._input_callback
            )
            self._output_stream = sd.OutputStream(
                device=self.output_device,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=2,
                dtype=np.float32,
                latency='low',
                callback=self._output_callback
            )

            self._is_running = True
            self._input_stream.start()
            self._output_stream.start()

            if self.on_status_change:
                self.on_status_change("Running (Dual Stream)")
        except Exception as e:
            self.stop()
            if self.on_status_change:
                self.on_status_change(f"Error: {e}")
            raise e

    def stop(self):
        """Stop all streams cleanly."""
        self._is_running = False

        if self._unified_stream:
            try:
                self._unified_stream.stop()
                self._unified_stream.close()
            except Exception:
                pass
            self._unified_stream = None

        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None

        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

        self._ring_queue.clear()
        if self.on_status_change:
            self.on_status_change("Stopped")
