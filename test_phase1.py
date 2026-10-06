"""
Phase 1 Test and Audio Generation Utility.
Generates an expressive melodic test WAV file, applies the 8D DSP engine,
validates output properties, and writes output_8d.wav.
"""

import sys
import numpy as np
import soundfile as sf
from eight_d import EightDProcessor, EightDSettings, apply_8d


def generate_test_audio(
    filename: str = "test_signal.wav",
    duration: float = 8.0,
    sample_rate: int = 44100
) -> str:
    """
    Generate an engaging melodic arpeggio synth chord test signal
    so spatial panning and rotation can be clearly auditioned.
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Generate an arpeggiated melodic sequence: C4 (261.63), E4 (329.63), G4 (392.00), B4 (493.88)
    notes = [261.63, 329.63, 392.00, 493.88, 523.25]
    note_duration = 0.25  # quarter second per note
    
    signal = np.zeros_like(t, dtype=np.float32)
    for i, current_t in enumerate(t):
        note_idx = int(current_t / note_duration) % len(notes)
        freq = notes[note_idx]
        
        # Note envelope (decaying attack)
        t_in_note = (current_t % note_duration)
        env = np.exp(-t_in_note * 5.0)
        
        # Harmonic richness (fundamental + 2nd + 3rd harmonic)
        sample_val = (
            np.sin(2 * np.pi * freq * current_t) * 0.6 +
            np.sin(2 * np.pi * (freq * 2) * current_t) * 0.25 +
            np.sin(2 * np.pi * (freq * 3) * current_t) * 0.15
        )
        signal[i] = sample_val * env

    # Add a continuous soft pad chord in background for continuous spatial sensation
    pad = (
        np.sin(2 * np.pi * 130.81 * t) * 0.15 + # C3
        np.sin(2 * np.pi * 196.00 * t) * 0.15   # G3
    )
    signal = signal * 0.6 + pad * 0.4

    # Normalize test signal to [-0.7, 0.7] to give safe headroom
    max_val = np.max(np.abs(signal))
    if max_val > 0:
        signal = (signal / max_val) * 0.7

    # Create stereo signal (same signal in both channels initially)
    stereo = np.column_stack((signal, signal)).astype(np.float32)
    sf.write(filename, stereo, sample_rate)
    return filename


def run_phase_1_test():
    print("=" * 60)
    print(" 8D AUDIO — PHASE 1 TEST: OFFLINE DSP VERIFICATION ")
    print("=" * 60)

    sample_rate = 44100
    test_input_file = "test_signal.wav"
    output_file = "output_8d.wav"

    # Step 1: Generate reference test audio if not present or for automated run
    print(f"\n[1] Generating clean melodic test signal ({test_input_file})...")
    generate_test_audio(test_input_file, duration=8.0, sample_rate=sample_rate)
    print(f"    Created '{test_input_file}' (8.0s duration, stereo, 44.1 kHz).")

    # Step 2: Read and inspect WAV file
    print(f"\n[2] Reading and verifying input file '{test_input_file}'...")
    audio, sr = sf.read(test_input_file)
    print(f"    Sample Rate: {sr} Hz")
    print(f"    Shape: {audio.shape}")
    print(f"    Channels: {1 if audio.ndim == 1 else audio.shape[1]}")
    print(f"    Peak amplitude: {np.max(np.abs(audio)):.4f}")

    # Ensure format verification
    if audio.ndim == 1:
        print("    Converting mono input to dual-channel stereo...")
        audio = np.column_stack((audio, audio))

    # Step 3: Apply 8D effect using the DSP engine
    print(f"\n[3] Processing audio with 8D Audio DSP...")
    speed = 0.2          # 1 complete revolution every 5 seconds
    intensity = 0.9      # 90% spatial panning depth
    reverb_mix = 0.15     # subtle crossfeed/ambiance
    
    print(f"    Parameters: Speed = {speed} Hz (5s/cycle), Intensity = {intensity}, Reverb = {reverb_mix}")
    
    processor = EightDProcessor(sample_rate=sr)
    settings = EightDSettings(
        enabled=True,
        speed=speed,
        intensity=intensity,
        reverb_mix=reverb_mix
    )
    processed = processor.process_block(audio, settings)

    # Step 4: Verification checks
    print("\n[4] Validating processed signal properties:")
    assert processed.shape == audio.shape, f"Shape mismatch: {processed.shape} vs {audio.shape}"
    print("    [PASS] Output shape matches input shape exactly.")

    assert not np.isnan(processed).any(), "Found NaN values in output!"
    print("    [PASS] No NaN values present.")

    assert not np.isinf(processed).any(), "Found Infinite values in output!"
    print("    [PASS] No Inf values present.")

    peak_out = np.max(np.abs(processed))
    print(f"    Output peak amplitude: {peak_out:.4f}")
    assert peak_out <= 1.0, f"Digital clipping detected! Peak = {peak_out}"
    print("    [PASS] Signal bounded within [-1.0, 1.0] safe digital ceiling (No clipping).")

    # Measure channel difference to ensure spatial stereo modulation actually occurred
    diff = np.abs(processed[:, 0] - processed[:, 1])
    mean_diff = np.mean(diff)
    print(f"    Mean L/R channel divergence: {mean_diff:.4f}")
    assert mean_diff > 0.05, "Stereo channels are identical! Effect was not applied."
    print("    [PASS] Dynamic stereo spatial separation verified.")

    # Step 5: Save output file
    print(f"\n[5] Writing processed audio to '{output_file}'...")
    sf.write(output_file, processed, sr)
    print(f"    Successfully written '{output_file}'.")
    print("=" * 60)
    print(" PHASE 1 COMPLETED SUCCESSFULLY! ")
    print("=" * 60)


if __name__ == "__main__":
    run_phase_1_test()
