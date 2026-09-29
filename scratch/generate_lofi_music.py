import math
import os
import struct
import wave
import numpy as np

SAMPLE_RATE = 44100
BPM = 85
DURATION_SEC = 28
BEAT_DUR = 60.0 / BPM
TOTAL_SAMPLES = int(SAMPLE_RATE * DURATION_SEC)

# Note frequencies (Hz)
NOTES = {
    'C2': 65.41, 'D2': 73.42, 'E2': 82.41, 'F2': 87.31, 'G2': 98.00, 'A2': 110.00,
    'C3': 130.81, 'D3': 146.83, 'E3': 164.81, 'F3': 174.61, 'G3': 196.00, 'A3': 220.00, 'B3': 246.94,
    'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23, 'G4': 392.00, 'A4': 440.00, 'B4': 493.88,
}

# Upbeat Jazz / Lo-Fi Chords
CHORDS = [
    # Fmaj7
    [NOTES['F3'], NOTES['A3'], NOTES['C4'], NOTES['E4']],
    # Em7
    [NOTES['E3'], NOTES['G3'], NOTES['B3'], NOTES['D4']],
    # Dm7
    [NOTES['D3'], NOTES['F3'], NOTES['A3'], NOTES['C4']],
    # Cmaj7
    [NOTES['C3'], NOTES['E3'], NOTES['G3'], NOTES['B4']],
]

BASS_NOTES = [NOTES['F2'], NOTES['E2'], NOTES['D2'], NOTES['C2']]

def synth_key(freq, duration, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Warm rhodes / electric piano sound: fundamental + soft 2nd & 3rd harmonics
    sig = 0.6 * np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t) + 0.1 * np.sin(2 * np.pi * freq * 3 * t)
    # Soft ADSR envelope
    attack = int(0.02 * sample_rate)
    decay = int(0.3 * sample_rate)
    release = int(0.15 * sample_rate)
    env = np.ones_like(sig)
    if len(env) > attack:
        env[:attack] = np.linspace(0, 1, attack)
    if len(env) > attack + decay:
        env[attack:attack+decay] = np.linspace(1, 0.6, decay)
        env[attack+decay:-release] = 0.6
        env[-release:] = np.linspace(0.6, 0, release)
    return sig * env

def synth_bass(freq, duration, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    sig = 0.8 * np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 2 * t)
    env = np.exp(-3 * t / duration)
    return sig * env

def make_kick(sample_rate=SAMPLE_RATE):
    dur = 0.18
    t = np.linspace(0, dur, int(sample_rate * dur), False)
    freq = np.linspace(130, 40, len(t))
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    sig = np.sin(phase) * np.exp(-12 * t)
    return sig

def make_snare(sample_rate=SAMPLE_RATE):
    dur = 0.15
    t = np.linspace(0, dur, int(sample_rate * dur), False)
    noise = np.random.uniform(-1, 1, len(t)) * np.exp(-18 * t)
    body = np.sin(2 * np.pi * 180 * t) * np.exp(-25 * t)
    return 0.7 * noise + 0.3 * body

def make_hihat(sample_rate=SAMPLE_RATE):
    dur = 0.05
    t = np.linspace(0, dur, int(sample_rate * dur), False)
    noise = np.random.uniform(-1, 1, len(t)) * np.exp(-40 * t)
    return 0.4 * noise

def generate_lofi_track():
    track = np.zeros(TOTAL_SAMPLES, dtype=np.float32)
    kick = make_kick()
    snare = make_snare()
    hihat = make_hihat()

    measures = int(math.ceil(DURATION_SEC / (BEAT_DUR * 4)))

    for m in range(measures):
        measure_start_time = m * 4 * BEAT_DUR
        chord = CHORDS[m % len(CHORDS)]
        bass = BASS_NOTES[m % len(BASS_NOTES)]

        # 4 beats per measure
        for b in range(4):
            beat_time = measure_start_time + b * BEAT_DUR
            idx = int(beat_time * SAMPLE_RATE)
            if idx >= TOTAL_SAMPLES:
                break

            # Piano Chord on beat 0 and beat 2
            if b in [0, 2]:
                chord_dur = BEAT_DUR * 1.8
                for freq in chord:
                    note_sig = synth_key(freq, chord_dur)
                    end_idx = min(TOTAL_SAMPLES, idx + len(note_sig))
                    track[idx:end_idx] += 0.18 * note_sig[:end_idx-idx]

            # Bass on beat 0 and beat 2.5
            bass_times = [beat_time] if b in [0, 2] else []
            if b == 2:
                bass_times.append(beat_time + BEAT_DUR * 0.5)

            for bt in bass_times:
                b_idx = int(bt * SAMPLE_RATE)
                bass_sig = synth_bass(bass, BEAT_DUR * 1.2)
                end_idx = min(TOTAL_SAMPLES, b_idx + len(bass_sig))
                track[b_idx:end_idx] += 0.3 * bass_sig[:end_idx-b_idx]

            # Kick on beat 0 and beat 2.5
            if b in [0] or (b == 2):
                end_idx = min(TOTAL_SAMPLES, idx + len(kick))
                track[idx:end_idx] += 0.35 * kick[:end_idx-idx]

            # Snare on beat 1 and beat 3
            if b in [1, 3]:
                end_idx = min(TOTAL_SAMPLES, idx + len(snare))
                track[idx:end_idx] += 0.25 * snare[:end_idx-idx]

            # Hi-hats on 8th notes (swing)
            sub_times = [0.0, 0.5]
            for st in sub_times:
                hh_idx = int((beat_time + st * BEAT_DUR) * SAMPLE_RATE)
                end_idx = min(TOTAL_SAMPLES, hh_idx + len(hihat))
                if hh_idx < TOTAL_SAMPLES:
                    track[hh_idx:end_idx] += 0.15 * hihat[:end_idx-hh_idx]

    # Vinyl noise texture (subtle lo-fi crackle)
    vinyl = np.random.uniform(-0.015, 0.015, TOTAL_SAMPLES)
    # Add occasional pop
    pops = np.random.choice([0, 1], size=TOTAL_SAMPLES, p=[0.9997, 0.0003]) * np.random.uniform(-0.1, 0.1, TOTAL_SAMPLES)
    track += vinyl + pops

    # Master Limiter / Normalization
    max_val = np.max(np.abs(track))
    if max_val > 0:
        track = track / max_val * 0.85

    # Convert to 16-bit PCM WAV
    pcm_data = (track * 32767).astype(np.int16)
    wav_path = '/tmp/lofi_background.wav'

    with wave.open(wav_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data.tobytes())

    print(f"Upbeat lo-fi track generated successfully: {wav_path} ({os.path.getsize(wav_path)} bytes)")
    return wav_path

if __name__ == '__main__':
    generate_lofi_track()
