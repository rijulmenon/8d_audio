"""
Audio Device Manager.
Handles device enumeration, querying, validation, and friendly naming across Windows APIs.
"""

from dataclasses import dataclass
from typing import List, Optional
import sounddevice as sd


@dataclass
class AudioDeviceInfo:
    id: int
    name: str
    hostapi_name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_input: bool
    is_output: bool

    @property
    def display_name(self) -> str:
        return f"{self.name} [{self.hostapi_name}] (#{self.id})"


class AudioDeviceManager:
    """Manages audio device discovery and format validation."""

    @staticmethod
    def get_devices() -> List[AudioDeviceInfo]:
        """Query and return all audio devices on the system."""
        hostapis = sd.query_hostapis()
        raw_devices = sd.query_devices()
        device_list: List[AudioDeviceInfo] = []

        for idx, dev in enumerate(raw_devices):
            api_name = hostapis[dev['hostapi']]['name'] if dev['hostapi'] < len(hostapis) else "Unknown"
            info = AudioDeviceInfo(
                id=idx,
                name=dev['name'],
                hostapi_name=api_name,
                max_input_channels=dev['max_input_channels'],
                max_output_channels=dev['max_output_channels'],
                default_samplerate=dev['default_samplerate'],
                is_input=dev['max_input_channels'] > 0,
                is_output=dev['max_output_channels'] > 0
            )
            device_list.append(info)
        return device_list

    @classmethod
    def get_input_devices(cls) -> List[AudioDeviceInfo]:
        """Return all input capable audio devices."""
        return [d for d in cls.get_devices() if d.is_input]

    @classmethod
    def get_output_devices(cls) -> List[AudioDeviceInfo]:
        """Return all output capable audio devices."""
        return [d for d in cls.get_devices() if d.is_output]

    @classmethod
    def get_default_input_device(cls) -> Optional[AudioDeviceInfo]:
        devices = cls.get_devices()
        default_in, _ = sd.default.device
        if default_in is not None and 0 <= default_in < len(devices):
            return devices[default_in]
        inputs = cls.get_input_devices()
        return inputs[0] if inputs else None

    @classmethod
    def get_default_output_device(cls) -> Optional[AudioDeviceInfo]:
        devices = cls.get_devices()
        _, default_out = sd.default.device
        if default_out is not None and 0 <= default_out < len(devices):
            return devices[default_out]
        outputs = cls.get_output_devices()
        return outputs[0] if outputs else None

    @classmethod
    def find_virtual_cable_input(cls) -> Optional[AudioDeviceInfo]:
        """Look for common virtual audio cables/inputs like 'CABLE Output', 'VB-Audio', 'Stereo Mix'."""
        inputs = cls.get_input_devices()
        for dev in inputs:
            lower = dev.name.lower()
            if "cable output" in lower or "vb-audio" in lower or "virtual" in lower:
                return dev
        for dev in inputs:
            if "stereo mix" in dev.name.lower():
                return dev
        return None
