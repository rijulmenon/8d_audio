# 8D Audio — Architecture Design Document

## 1. System Overview

8D Audio is designed to provide smooth, low-latency, real-time spatialization of system audio under Windows.

The system is organized into decoupled layers:

```
┌────────────────────────────────────────────────────────┐
│                   PySide6 GUI Thread                   │
│   (Main Window, Sliders, Device Selectors, VU Meters)  │
└──────────────────────────┬─────────────────────────────┘
                           │ Signals & Thread-Safe Params
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Audio Engine Layer                   │
│       (AudioEngine, Stream Manager, State Crossfade)   │
└──────────────────────────┬─────────────────────────────┘
                           │ Real-Time Audio Callback (PortAudio)
                           ▼
┌────────────────────────────────────────────────────────┐
│                     8D DSP Layer                       │
│    (EightDProcessor, Equal-Power Panning, Limiter)     │
└────────────────────────────────────────────────────────┘
```

## 2. DSP Engine (`eight_d.py`)

### Equal-Power Panning
Linear stereo panning causes a 3dB volume drop at center position. The `EightDProcessor` implements an equal-power sinusoidal panning law:

$$\theta(t) = (\text{pan}(t) + 1.0) \times \frac{\pi}{4}$$
$$G_L(t) = \cos(\theta(t)), \quad G_R(t) = \sin(\theta(t))$$

This guarantees $G_L^2 + G_R^2 = 1$, preserving perceived acoustic loudness as sound circles through the stereo field.

### Orbit Depth & Distance Perception
Real-world circular sound rotation involves front-to-back distance changes. We simulate this by modulating signal amplitude with a secondary phase dimension:

$$\text{depth}(t) = 1.0 - d_{\text{mod}} \cdot (1.0 - \cos(\theta))$$

### Acoustic Headphone Crossfeed
To prevent unnatural direct-into-eardrum sound separation, a fractional delay line crossfeeds opposite channels with decay to create an out-of-head listening room perception.

### Soft-Knee Limiting
To ensure that hot signals never clip digitally, output samples passing 0.95 peak undergo soft-saturation compression:

$$y = 0.95 \cdot \tanh\left(\frac{x}{0.95}\right)$$

Clamped strictly to $[-1.0, 1.0]$.

## 3. Streaming Engine (`engine.py`)

- **Full-Duplex Stream:** Uses `sounddevice.Stream` configured for low-latency block-based input and output.
- **Zero-Allocation Callback:** Avoids memory allocations, disk I/O, or GUI calls in the audio thread.
- **Click-Free Bypass Crossfade:** When toggling the 8D effect ON or OFF, the engine ramps a blend coefficient over multiple audio blocks ($\sim 200$ ms) to eliminate clicks and pops.
- **Metering & Telemetry:** Computes instantaneous peak levels and measures callback duration relative to buffer period to report approximate DSP load.

## 4. System-Wide Audio Integration

Under Windows, apps output to the default endpoint. We bridge this transparently using either:
1. **Virtual Audio Cable (VB-Audio Cable):** Windows output $\to$ Cable Input $\to$ Cable Output $\to$ 8D Audio Engine $\to$ Physical Headphones.
2. **Stereo Mix:** Windows Realtek capture loopback.
