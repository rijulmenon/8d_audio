"""
8D Audio Modern PySide6 Desktop GUI Application.
Features:
- Master ON/OFF Switch with smooth transition
- Real-time Audio Start/Stop Processing
- Movement Speed & Intensity Sliders
- Preset Selection (Slow, Normal, Fast, Intense, Custom)
- Input and Output Audio Device Pickers
- Live VU Peak Meter and Status indicator
- Latency and CPU load display
- Help dialog explaining Windows Virtual Audio Routing
"""

import sys
from typing import Optional
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QComboBox, QGroupBox, QProgressBar,
    QMessageBox, QFrame, QSizePolicy
)

from app.audio.engine import AudioEngine
from app.audio.device_manager import AudioDeviceManager, AudioDeviceInfo


class AudioBridge(QObject):
    """Thread-safe signal bridge between real-time audio thread and Qt UI."""
    peak_received = Signal(float, float)
    status_changed = Signal(str)


class Modern8DWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("8D Audio — Real-Time Spatial Processor")
        self.setFixedSize(540, 720)

        self.bridge = AudioBridge()
        self.bridge.peak_received.connect(self._on_peak_received)
        self.bridge.status_changed.connect(self._on_status_changed)

        self.device_manager = AudioDeviceManager()
        self.input_devices = self.device_manager.get_input_devices()
        self.output_devices = self.device_manager.get_output_devices()

        # Audio engine instance
        self.engine: Optional[AudioEngine] = None

        self._init_ui()
        self._apply_styling()

        # Telemetry refresh timer
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._update_telemetry)
        self.telemetry_timer.start(250)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # Header Title
        title_box = QVBoxLayout()
        title_label = QLabel("8D AUDIO")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignCenter)
        subtitle_label = QLabel("Real-Time System-Wide Spatial Sound Engine")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setAlignment(Qt.AlignCenter)
        title_box.addWidget(title_label)
        title_box.addWidget(subtitle_label)
        main_layout.addLayout(title_box)

        # Master 8D ON/OFF Hero Button
        self.btn_8d_toggle = QPushButton("8D EFFECT: OFF")
        self.btn_8d_toggle.setObjectName("btn8dToggle")
        self.btn_8d_toggle.setCheckable(True)
        self.btn_8d_toggle.setFixedHeight(56)
        self.btn_8d_toggle.clicked.connect(self._toggle_8d_effect)
        main_layout.addWidget(self.btn_8d_toggle)

        # Controls Group
        controls_group = QGroupBox("Spatial Controls")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(12)

        # Movement Speed Slider
        speed_header = QHBoxLayout()
        speed_label = QLabel("Movement Speed:")
        self.speed_val_label = QLabel("0.20 Hz (5.0s / cycle)")
        speed_header.addWidget(speed_label)
        speed_header.addStretch()
        speed_header.addWidget(self.speed_val_label)
        controls_layout.addLayout(speed_header)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(5, 150)  # 0.05 Hz to 1.50 Hz
        self.speed_slider.setValue(20)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        controls_layout.addWidget(self.speed_slider)

        # Intensity Slider
        intensity_header = QHBoxLayout()
        intensity_label = QLabel("Effect Intensity:")
        self.intensity_val_label = QLabel("85%")
        intensity_header.addWidget(intensity_label)
        intensity_header.addStretch()
        intensity_header.addWidget(self.intensity_val_label)
        controls_layout.addLayout(intensity_header)

        self.intensity_slider = QSlider(Qt.Horizontal)
        self.intensity_slider.setRange(0, 100)
        self.intensity_slider.setValue(85)
        self.intensity_slider.valueChanged.connect(self._on_intensity_changed)
        controls_layout.addWidget(self.intensity_slider)

        # Preset Selector
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Preset:")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Slow (Relaxing)", "Normal (Standard)", "Fast (Energetic)", "Custom"])
        self.preset_combo.setCurrentIndex(1)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_combo)
        controls_layout.addLayout(preset_layout)

        main_layout.addWidget(controls_group)

        # Audio Routing Group
        routing_group = QGroupBox("Audio Device Routing")
        routing_layout = QVBoxLayout(routing_group)
        routing_layout.setSpacing(10)

        # Input Device
        in_layout = QVBoxLayout()
        in_header = QHBoxLayout()
        in_label = QLabel("Audio Input (Source / Virtual Device):")
        help_btn = QPushButton("ℹ How it works")
        help_btn.setObjectName("helpBtn")
        help_btn.clicked.connect(self._show_routing_guide)
        in_header.addWidget(in_label)
        in_header.addStretch()
        in_header.addWidget(help_btn)
        in_layout.addLayout(in_header)

        self.input_combo = QComboBox()
        default_in = self.device_manager.get_default_input_device()
        suggested_virtual = self.device_manager.find_virtual_cable_input()
        default_in_idx = 0
        for i, dev in enumerate(self.input_devices):
            self.input_combo.addItem(dev.display_name, dev.id)
            if suggested_virtual and dev.id == suggested_virtual.id:
                default_in_idx = i
            elif not suggested_virtual and default_in and dev.id == default_in.id:
                default_in_idx = i
        self.input_combo.setCurrentIndex(default_in_idx)
        in_layout.addWidget(self.input_combo)
        routing_layout.addLayout(in_layout)

        # Output Device
        out_layout = QVBoxLayout()
        out_label = QLabel("Audio Output (Headphones / Speakers):")
        out_layout.addWidget(out_label)
        self.output_combo = QComboBox()
        default_out = self.device_manager.get_default_output_device()
        default_out_idx = 0
        for i, dev in enumerate(self.output_devices):
            self.output_combo.addItem(dev.display_name, dev.id)
            if default_out and dev.id == default_out.id:
                default_out_idx = i
        self.output_combo.setCurrentIndex(default_out_idx)
        out_layout.addWidget(self.output_combo)
        routing_layout.addLayout(out_layout)

        main_layout.addWidget(routing_group)

        # Status & Level Meter
        status_box = QHBoxLayout()
        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("color: #718096; font-size: 16px;")
        self.status_text = QLabel("Stream: Inactive")
        self.status_text.setObjectName("statusLabel")
        status_box.addWidget(self.status_icon)
        status_box.addWidget(self.status_text)
        status_box.addStretch()

        self.telemetry_label = QLabel("CPU: 0% | Latency: ~10ms")
        self.telemetry_label.setStyleSheet("color: #a0aec0; font-size: 12px;")
        status_box.addWidget(self.telemetry_label)
        main_layout.addLayout(status_box)

        # Audio Peak Meters (Left & Right)
        meter_layout = QVBoxLayout()
        meter_layout.setSpacing(4)
        
        meter_l_row = QHBoxLayout()
        meter_l_row.addWidget(QLabel("L:"))
        self.meter_l = QProgressBar()
        self.meter_l.setRange(0, 100)
        self.meter_l.setValue(0)
        self.meter_l.setTextVisible(False)
        self.meter_l.setFixedHeight(8)
        meter_l_row.addWidget(self.meter_l)
        meter_layout.addLayout(meter_l_row)

        meter_r_row = QHBoxLayout()
        meter_r_row.addWidget(QLabel("R:"))
        self.meter_r = QProgressBar()
        self.meter_r.setRange(0, 100)
        self.meter_r.setValue(0)
        self.meter_r.setTextVisible(False)
        self.meter_r.setFixedHeight(8)
        meter_r_row.addWidget(self.meter_r)
        meter_layout.addLayout(meter_r_row)

        main_layout.addLayout(meter_layout)

        # Start / Stop Engine Stream Button
        self.btn_stream_start = QPushButton("START AUDIO ENGINE")
        self.btn_stream_start.setObjectName("btnStreamStart")
        self.btn_stream_start.setFixedHeight(48)
        self.btn_stream_start.clicked.connect(self._toggle_audio_stream)
        main_layout.addWidget(self.btn_stream_start)

    def _apply_styling(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #12151c;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            #titleLabel {
                font-size: 26px;
                font-weight: bold;
                letter-spacing: 3px;
                color: #63b3ed;
            }
            #subtitleLabel {
                font-size: 12px;
                color: #718096;
            }
            QGroupBox {
                border: 1px solid #2d3748;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #a0aec0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QComboBox {
                background-color: #1a202c;
                color: #edf2f7;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1a202c;
                color: #edf2f7;
                selection-background-color: #3182ce;
            }
            #btn8dToggle {
                background-color: #2d3748;
                color: #a0aec0;
                border: 2px solid #4a5568;
                border-radius: 10px;
                font-size: 18px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            #btn8dToggle:checked {
                background-color: #3182ce;
                color: #ffffff;
                border: 2px solid #63b3ed;
            }
            #btnStreamStart {
                background-color: #38a169;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
            }
            #btnStreamStart:hover {
                background-color: #2f855a;
            }
            #helpBtn {
                background: transparent;
                border: none;
                color: #63b3ed;
                font-size: 11px;
                text-decoration: underline;
            }
            QProgressBar {
                border: 1px solid #2d3748;
                border-radius: 4px;
                background-color: #1a202c;
            }
            QProgressBar::chunk {
                background-color: #3182ce;
                border-radius: 3px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2d3748;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #3182ce;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #63b3ed;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
        """)

    def _toggle_8d_effect(self):
        is_on = self.btn_8d_toggle.isChecked()
        if is_on:
            self.btn_8d_toggle.setText("8D EFFECT: ON")
            if self.engine:
                self.engine.set_enabled(True)
        else:
            self.btn_8d_toggle.setText("8D EFFECT: OFF")
            if self.engine:
                self.engine.set_enabled(False)

    def _on_speed_changed(self, value):
        speed_hz = value / 100.0
        cycle_sec = 1.0 / speed_hz if speed_hz > 0 else 0
        self.speed_val_label.setText(f"{speed_hz:.2f} Hz ({cycle_sec:.1f}s / cycle)")
        if self.engine:
            self.engine.set_speed(speed_hz)

    def _on_intensity_changed(self, value):
        self.intensity_val_label.setText(f"{value}%")
        if self.engine:
            self.engine.set_intensity(value / 100.0)

    def _on_preset_changed(self, index):
        if index == 0:  # Slow
            self.speed_slider.setValue(10)      # 0.10 Hz (10s/cycle)
            self.intensity_slider.setValue(75)
        elif index == 1:  # Normal
            self.speed_slider.setValue(20)      # 0.20 Hz (5s/cycle)
            self.intensity_slider.setValue(85)
        elif index == 2:  # Fast
            self.speed_slider.setValue(40)      # 0.40 Hz (2.5s/cycle)
            self.intensity_slider.setValue(95)

    def _toggle_audio_stream(self):
        if self.engine and self.engine.is_running:
            # Stop stream
            self.engine.stop()
            self.btn_stream_start.setText("START AUDIO ENGINE")
            self.btn_stream_start.setStyleSheet("background-color: #38a169; color: white;")
            self.status_icon.setStyleSheet("color: #718096; font-size: 16px;")
            self.status_text.setText("Stream: Inactive")
            self.input_combo.setEnabled(True)
            self.output_combo.setEnabled(True)
        else:
            # Start stream
            in_dev_id = self.input_combo.currentData()
            out_dev_id = self.output_combo.currentData()

            try:
                self.engine = AudioEngine(
                    sample_rate=48000,
                    block_size=512,
                    input_device=in_dev_id,
                    output_device=out_dev_id,
                    on_status_change=self.bridge.status_changed.emit,
                    on_peak_level=self.bridge.peak_received.emit
                )
                self.engine.set_enabled(self.btn_8d_toggle.isChecked())
                self.engine.set_speed(self.speed_slider.value() / 100.0)
                self.engine.set_intensity(self.intensity_slider.value() / 100.0)
                self.engine.start()

                self.btn_stream_start.setText("STOP AUDIO ENGINE")
                self.btn_stream_start.setStyleSheet("background-color: #e53e3e; color: white;")
                self.status_icon.setStyleSheet("color: #48bb78; font-size: 16px;")
                self.status_text.setText("Stream: Running (Active)")
                self.input_combo.setEnabled(False)
                self.output_combo.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Audio Device Error", f"Failed to start audio stream:\n\n{str(e)}\n\nTry selecting a different input or output device.")

    def _on_peak_received(self, peak_l: float, peak_r: float):
        self.meter_l.setValue(int(min(1.0, peak_l) * 100))
        self.meter_r.setValue(int(min(1.0, peak_r) * 100))

    def _on_status_changed(self, status: str):
        self.status_text.setText(f"Stream: {status}")

    def _update_telemetry(self):
        if self.engine and self.engine.is_running:
            cpu = self.engine.cpu_load_approx
            lat_ms = (self.engine.block_size / self.engine.sample_rate) * 1000.0
            self.telemetry_label.setText(f"DSP Load: {cpu:.1f}% | Block: {lat_ms:.1f}ms")
        else:
            self.meter_l.setValue(0)
            self.meter_r.setValue(0)
            self.telemetry_label.setText("DSP Load: 0.0% | Inactive")

    def _show_routing_guide(self):
        guide = (
            "<h3>How System-Wide 8D Audio Works</h3>"
            "<p>To process all Windows audio (YouTube, Spotify, Games, Discord):</p>"
            "<ol>"
            "<li>Install a free virtual audio device like <b>VB-Audio Virtual Cable</b> (or enable <b>Stereo Mix</b> in Windows Sound settings).</li>"
            "<li>Set Windows Default Playback Device to <b>CABLE Input</b>. All applications will now play into the cable.</li>"
            "<li>In 8D Audio, set <b>Audio Input</b> to <b>CABLE Output</b> (or Stereo Mix).</li>"
            "<li>Set <b>Audio Output</b> to your real physical <b>Headphones</b>.</li>"
            "<li>Click <b>START AUDIO ENGINE</b>, then toggle <b>8D EFFECT ON</b>!</li>"
            "</ol>"
        )
        QMessageBox.information(self, "System-Wide Audio Routing Guide", guide)

    def closeEvent(self, event):
        if self.engine and self.engine.is_running:
            self.engine.stop()
        event.accept()


def run_gui():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    window = Modern8DWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
