# 8D Audio — Real-Time System-Wide Audio Processor

A high-performance Windows desktop application that captures system audio (from YouTube, Spotify, games, Discord, browser, media players), applies real-time 8D spatial movement, equal-power circular rotation, distance perception, and acoustic crossfeed, and streams it to your physical headphones.

---

## Features

- **System-Wide Audio Processing:** Processes audio from any Windows application without requiring manual file conversions.
- **Master 8D ON/OFF Switch:** Instant toggling with click-free equal-power crossfade ramping.
- **Smooth Spatial Movement:** Continuous sine/cosine phase tracking with zero clicks or boundary pop artifacts across audio chunks.
- **Equal-Power Panning & Distance Simulation:** Orbiting spatial movement model with subtle distance depth modulation.
- **Headphone Spatial Ambiance / Crossfeed:** Comb-filtered crossfeed for an out-of-head listening experience.
- **Safety Limiter:** Soft-knee compression and peak limiting prevents digital clipping even on hot signals.
- **Modern Dark Desktop GUI:** Built with PySide6 (Qt) featuring live stereo VU meters, DSP CPU monitoring, buffer latency readout, and device pickers.

---

## Architecture & System-Wide Routing

Windows audio applications (Spotify, YouTube, Games, Discord) send their audio to the default playback device. To process system audio in real time without writing risky unsigned kernel drivers, the standard pro-audio approach uses a Virtual Audio Cable or Windows Stereo Mix:

```
[ Windows Apps (Spotify, YouTube, Games) ]
                    │
                    ▼ (Default Windows Playback)
     [ Virtual Cable / Stereo Mix ]
                    │
                    ▼ (Input Device)
         [ 8D Audio Engine (DSP) ]
                    │
                    ▼ (Output Device)
    [ Physical Headphones / Speakers ]
```

### Virtual Audio Setup (One-Time Setup)

1. **Option A (Built-in Windows Stereo Mix):**
   - Press `Win + R`, type `mmsys.cpl` and hit Enter.
   - Go to the **Recording** tab.
   - Right-click an empty space and ensure **Show Disabled Devices** is checked.
   - If **Stereo Mix** is visible, right-click and choose **Enable**.
   - In 8D Audio, select `Stereo Mix` as your **Audio Input**.

2. **Option B (Recommended Pro Setup — VB-Audio Virtual Cable):**
   - Download the free, official signed driver: [VB-Audio Virtual Cable](https://vb-audio.com/Cable/).
   - Extract and run `VBCABLE_Setup_x64.exe` as Administrator, then click **Install Driver**.
   - In Windows Sound Settings (`mmsys.cpl`), set **CABLE Input** as your default Windows playback device.
   - In the **8D Audio** application:
     - Set **Audio Input** to `CABLE Output (VB-Audio Virtual Cable)`.
     - Set **Audio Output** to your physical **Headphones** (e.g. Sony WH-1000XM4, Realtek Audio, USB DAC).
     - Click **START AUDIO ENGINE**, then toggle **8D EFFECT: ON**!

---

## Installation & Running

### Requirements
- Windows 10 / 11 (64-bit)
- Python 3.10+ (Python 3.12 recommended)

### Run from Source
1. Clone or navigate to the repository directory:
   ```cmd
   cd c:\Users\rijul\Downloads\8d_audio
   ```
2. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
3. Run the application:
   ```cmd
   python app/main.py
   ```
   Or double-click:
   ```cmd
   run.bat
   ```

---

## Running Automated Tests

Run the comprehensive pytest test suite covering all 12 DSP properties, phase continuity, and audio callback streaming:
```cmd
python -m pytest tests/ -v
```

---

## Privacy
All DSP computation executes 100% locally on your computer. No audio is ever recorded, stored to disk during streaming, or transmitted over the internet.