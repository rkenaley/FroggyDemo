"""
===============================================================================
FROGGY: 16-BIT METROIDVANIA TECH DEMO ENGINE (720p HD LUSH EDITION)
===============================================================================
A complete, self-contained 2D platformer engine inspired by Super Castlevania IV,
Super Metroid, and Donkey Kong Country.

DESIGNED FOR ONE-CREATOR LEGIBILITY (NEPHEW'S CODE WALKTHROUGH):
Every system in this file is organized into numbered chapters with step-by-step
comments explaining the math and game-programming patterns behind it:

  CHAPTER 1 : Global Constants & 720p Integer-Scaled Resolution (1280x720)
  CHAPTER 2 : Procedural Chiptune Synthesizer (Jamaican Dub Groove & Sinister Boss Theme)
  CHAPTER 3 : Asset Pipeline & 4-Bit Neighbor Auto-Tiling (How Mossy Edges Work)
  CHAPTER 4 : Lush Ambiance Engine (Interactive Physics Vines, Fireflies & Lighting)
  CHAPTER 5 : World Blueprints (Level 1 Canopy -> Temple -> Cavern -> Boss Sanctum)
  CHAPTER 6 : Particles & Boomerang/Scythe Projectiles
  CHAPTER 7 : Enemy AI & 3-Phase Emperor Mantis Boss State Machine
  CHAPTER 8 : TileMapRoom Parser, Auto-Decorator & Live Level Builder
  CHAPTER 9 : Metroidvania World Manager & Dramatic Boss Awakening Director
  CHAPTER 10: SNES 12-Button Controller Abstraction (Gamepad + Keyboard)
  CHAPTER 11: Froggy Player Physics (AABB, Coyote Time, Wall-Jump & Pendulum Swing)
  CHAPTER 12: Dual-Axis Hysteresis Camera & Metroidvania Minimap HUD
  CHAPTER 13: Title Screen, Pause Menu, Game Over & Main 60 FPS Game Loop

CONTROLS (Keyboard / SNES Controller):
- D-Pad (8-Way Aim & Move) : Arrow Keys or W/A/S/D | Gamepad D-Pad / Left Stick
- A or B Button (Jump)     : SPACE, Z, or K        | Gamepad A / B
- Y Button (8-Way Tongue)  : X or J                | Gamepad X / Y
- R Button (Spore Weapon)  : C, U, or Left Shift   | Gamepad R1
- Menu Navigation          : UP / DOWN to select   | SPACE / A / ENTER to confirm
- Pause / Return to Menu   : ESCAPE
- Toggle HUD Telemetry     : TAB
- Warp to Boss Sanctum     : B (in Adventure mode)
- Export Room ASCII        : P (in Builder mode)
===============================================================================
"""

import io
import math
import os
import random
import struct
import sys
import wave
import pygame

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import generate_assets
    HAS_ASSET_GENERATOR = True
except ImportError:
    HAS_ASSET_GENERATOR = False


# =============================================================================
# CHAPTER 1. GLOBAL ENGINE CONSTANTS & 720p RESOLUTION TUNING
# =============================================================================
# HOW RETRO PIXEL SCALING WORKS AT 720p:
# Instead of rendering tiny 16x16 sprites directly onto a huge 1280x720 window
# (which would make everything look microscopic), we draw the entire game onto
# a 640x360 internal "SNES Widescreen Canvas" (`INTERNAL_WIDTH` x `INTERNAL_HEIGHT`).
# At the end of every frame, we scale that canvas up by an exact integer factor
# of 2 (`WINDOW_SCALE = 2`) to fill the 1280x720 (720p HD) monitor window.
# Because 640 * 2 = 1280 and 360 * 2 = 720, every pixel becomes an exact 2x2
# square with zero shimmering or distortion!

TILE_SIZE = 16

INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 360
WINDOW_SCALE = 2
WINDOW_WIDTH = INTERNAL_WIDTH * WINDOW_SCALE   # 1280 px (720p HD Width)
WINDOW_HEIGHT = INTERNAL_HEIGHT * WINDOW_SCALE # 720 px  (720p HD Height)

TARGET_FPS = 60

# --- Platformer Physics Tuning (Measured in Pixels per Frame at 60 FPS) ---
GRAVITY = 0.38
MAX_FALL_SPEED = 8.5
WALL_SLIDE_SPEED = 1.6
MOVE_ACCEL = 0.55
AIR_ACCEL = 0.38
GROUND_FRICTION = 0.78
AIR_DRAG = 0.94
MAX_RUN_SPEED = 3.6
JUMP_VELOCITY = -7.6
DOUBLE_JUMP_VELOCITY = -6.8
VARIABLE_JUMP_CUTOFF = 0.45
WALL_JUMP_X_SPEED = 4.4
WALL_JUMP_Y_SPEED = -7.2
WALL_JUMP_LOCK_FRAMES = 10
COYOTE_TIME_FRAMES = 6
JUMP_BUFFER_FRAMES = 6

# --- Super Castlevania IV Tongue & Pendulum Grapple Constants ---
TONGUE_EXTEND_SPEED = 14.0
TONGUE_RETRACT_SPEED = 15.0
TONGUE_MAX_LENGTH = 145.0
TONGUE_HOLD_FRAMES = 7
SWING_GRAVITY = 0.011
SWING_DAMPING = 0.992
SWING_PUMP_FORCE = 0.0022
SWING_REEL_SPEED = 1.5
SWING_MIN_LENGTH = 28.0

# --- Health & Combat Constants ---
PLAYER_MAX_HP = 5
PLAYER_INVULN_FRAMES = 65
ENEMY_STUN_FRAMES = 210
BOSS_MAX_HP = 6
BOSS_WEAK_EXPOSED_FRAMES = 210

# --- Metroidvania Screen Transitions ---
TRANSITION_FADE_SPEED = 18
DOOR_COOLDOWN_FRAMES = 24

# --- Color Palette (16-Bit SNES Inspired RGB Tuples) ---
COLOR_BG_GRID = (26, 38, 56)
COLOR_TONGUE_PINK = (242, 107, 148)
COLOR_TONGUE_TIP = (255, 175, 205)
COLOR_SPORE_CYAN = (80, 245, 210)
COLOR_HUD_TEXT = (230, 245, 255)
COLOR_DOOR_GLOW = (90, 235, 255)
COLOR_HEART_RED = (235, 65, 85)
COLOR_HEART_EMPTY = (60, 45, 70)
COLOR_BOSS_CORE = (255, 70, 210)
COLOR_BOSS_GOLD = (255, 215, 70)


# =============================================================================
# CHAPTER 2. PROCEDURAL CHIPTUNE AUDIO SYNTHESIZER
# =============================================================================
# HOW PROCEDURAL AUDIO WORKS:
# Sound is just air pressure vibrating back and forth thousands of times per
# second (44,100 samples per second at CD quality).
# By evaluating mathematical waves (Sine, Triangle, Square/Pulse, Sawtooth, and
# White Noise) into NumPy arrays, we synthesize 15 retro sound effects and two
# contrasting full-length multi-track songs right in RAM:
#   1. "level" : Upbeat Jamaican Reggae / Dub Froggy Groove (G Major, 104 BPM)
#   2. "boss"  : Sinister Emperor Mantis Theme (D Harmonic Minor / Phrygian,
#                142 BPM) with pulsing sub-bass, dissonant cathedral organ
#                chords, tribal war drums, and screeching chromatic leads!

class RetroAudioEngine:
    SAMPLE_RATE = 44100

    def __init__(self):
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.SAMPLE_RATE, -16, 2, 512)
            self.enabled = True
            self.music_channel = pygame.mixer.Channel(0)
            self.music_channel.set_volume(0.48)
            print("[Audio Engine] Synthesizing Jamaican groove, Sinister Boss theme & SFX...")
            self.sfx = self._build_all_sfx()
            self.music_tracks = self._build_all_music()
            self.current_track_name = None
            print("[Audio Engine] Audio synthesis complete!")
        except Exception as err:
            print(f"[Audio Engine] Notice: Audio device unavailable ({err}). Running in silent mode.")

    @classmethod
    def _create_wav_sound(cls, samples):
        """Packs float samples [-1.0, 1.0] into a stereo/mono WAV buffer in RAM."""
        buf = io.BytesIO()
        wav_file = wave.open(buf, 'wb')
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(cls.SAMPLE_RATE)
        data = bytearray()
        for s in samples:
            val = int(max(-32767, min(32767, s * 32767)))
            data.extend(struct.pack('<h', val))
        wav_file.writeframes(data)
        wav_file.close()
        buf.seek(0)
        return pygame.mixer.Sound(buf)

    def _build_all_sfx(self):
        sr = self.SAMPLE_RATE
        sfx = {}

        # 1. Jump: Rising triangle slide (160 Hz -> 480 Hz)
        n = int(sr * 0.12)
        samples = []
        for i in range(n):
            t = i / sr
            f = 160.0 + (t / 0.12) * 320.0
            p = (f * t) % 1.0
            tri = 4.0 * abs(p - 0.5) - 1.0
            samples.append(tri * (1.0 - t / 0.12) * 0.45)
        sfx['jump'] = self._create_wav_sound(samples)

        # 2. Double Jump: High-pitched chirp with harmonic pulse
        n = int(sr * 0.14)
        samples = []
        for i in range(n):
            t = i / sr
            f = 340.0 + (t / 0.14) * 440.0
            pulse = 1.0 if ((f * t) % 1.0) < 0.28 else -1.0
            samples.append(pulse * (1.0 - t / 0.14) * 0.4)
        sfx['double_jump'] = self._create_wav_sound(samples)

        # 3. Wall Jump: Springy punch pop
        n = int(sr * 0.11)
        samples = []
        for i in range(n):
            t = i / sr
            f = 240.0 - (t / 0.11) * 110.0
            tri = 4.0 * abs(((f * t) % 1.0) - 0.5) - 1.0
            noise = (random.random() * 2.0 - 1.0) * max(0.0, 1.0 - t * 40.0)
            samples.append((tri * 0.35 + noise * 0.25) * (1.0 - t / 0.11))
        sfx['wall_jump'] = self._create_wav_sound(samples)

        # 4. Tongue Whip Shoot: High-speed snap and extending whip whoosh
        n = int(sr * 0.09)
        samples = []
        for i in range(n):
            t = i / sr
            noise = (random.random() * 2.0 - 1.0) * max(0.0, 1.0 - t * 25.0)
            f = 620.0 - (t / 0.09) * 460.0
            sq = 1.0 if ((f * t) % 1.0) < 0.5 else -1.0
            samples.append((noise * 0.4 + sq * 0.3) * (1.0 - t / 0.09))
        sfx['tongue'] = self._create_wav_sound(samples)

        # 5. Grapple Latch: Castlevania-style dual-tone metallic bell clink
        n = int(sr * 0.18)
        samples = []
        for i in range(n):
            t = i / sr
            s1 = math.sin(2.0 * math.pi * 880.0 * t) * 0.35
            s2 = math.sin(2.0 * math.pi * 1320.0 * t) * 0.25
            samples.append((s1 + s2) * math.exp(-t * 22.0))
        sfx['latch'] = self._create_wav_sound(samples)

        # 6. Spore Boomerang: Spinning frequency oscillation
        n = int(sr * 0.16)
        samples = []
        for i in range(n):
            t = i / sr
            f = 330.0 + math.sin(2.0 * math.pi * 32.0 * t) * 110.0
            sq = 1.0 if ((f * t) % 1.0) < 0.35 else -1.0
            samples.append(sq * (1.0 - t / 0.16) * 0.35)
        sfx['spore'] = self._create_wav_sound(samples)

        # 7. Enemy Stun: Goofy spring boing wobble
        n = int(sr * 0.20)
        samples = []
        for i in range(n):
            t = i / sr
            f = max(110.0, 520.0 - t * 1300.0) + math.sin(2.0 * math.pi * 26.0 * t) * 70.0
            samples.append(math.sin(2.0 * math.pi * f * t) * (1.0 - t / 0.20) * 0.45)
        sfx['stun'] = self._create_wav_sound(samples)

        # 8. Enemy Swallow / Eat: Gulp crunch + cheerful health restore chime
        n = int(sr * 0.24)
        samples = []
        for i in range(n):
            t = i / sr
            if t < 0.07:
                f = 220.0 + (t / 0.07) * 320.0
                v = (4.0 * abs(((f * t) % 1.0) - 0.5) - 1.0) * 0.35
            else:
                t2 = t - 0.07
                c1 = math.sin(2.0 * math.pi * 523.25 * t2) * 0.25
                c2 = math.sin(2.0 * math.pi * 659.25 * t2) * 0.25
                v = (c1 + c2) * math.exp(-t2 * 14.0)
            samples.append(v)
        sfx['eat'] = self._create_wav_sound(samples)

        # 9. Hurt: Noise impact thud + low square drop
        n = int(sr * 0.18)
        samples = []
        for i in range(n):
            t = i / sr
            noise = (random.random() * 2.0 - 1.0) * 0.45
            f = max(55.0, 160.0 - t * 420.0)
            sq = (1.0 if ((f * t) % 1.0) < 0.5 else -1.0) * 0.35
            samples.append((noise + sq) * (1.0 - t / 0.18))
        sfx['hurt'] = self._create_wav_sound(samples)

        # 10. Door Portal: Shimmering rising arpeggio
        n = int(sr * 0.28)
        samples = []
        pitches = [440.0, 554.37, 659.25, 880.0]
        for i in range(n):
            t = i / sr
            idx = min(3, int(t / 0.07))
            f = pitches[idx]
            samples.append(math.sin(2.0 * math.pi * f * t) * (1.0 - (t % 0.07) / 0.07) * 0.35)
        sfx['door'] = self._create_wav_sound(samples)

        # 11. Cursor Move: Crisp 8-bit blip
        n = int(sr * 0.04)
        samples = [(1.0 if (((650.0 * (i / sr)) % 1.0) < 0.5) else -1.0) * (1.0 - (i / n)) * 0.22 for i in range(n)]
        sfx['cursor'] = self._create_wav_sound(samples)

        # 12. Cursor Select: Two-tone affirmative fanfare
        n = int(sr * 0.15)
        samples = []
        for i in range(n):
            t = i / sr
            f = 523.25 if t < 0.07 else 783.99
            samples.append((1.0 if (((f * t) % 1.0) < 0.5) else -1.0) * 0.28 * max(0.0, 1.0 - (t % 0.07) * 12.0))
        sfx['select'] = self._create_wav_sound(samples)

        # 13. Game Over: Sad descending organ slide
        n = int(sr * 0.65)
        samples = []
        sad_pitches = [392.0, 349.2, 329.6, 261.6]
        for i in range(n):
            t = i / sr
            idx = min(3, int(t / 0.16))
            f = sad_pitches[idx]
            samples.append(math.sin(2.0 * math.pi * f * t) * 0.35 * (1.0 - (t % 0.16) / 0.16))
        sfx['game_over'] = self._create_wav_sound(samples)

        # 14. Boss Core Hit: Metallic clang
        n = int(sr * 0.22)
        samples = []
        for i in range(n):
            t = i / sr
            c1 = math.sin(2.0 * math.pi * 920.0 * t) * 0.3
            c2 = math.sin(2.0 * math.pi * 1480.0 * t) * 0.3
            noise = (random.random() * 2.0 - 1.0) * 0.25 * max(0.0, 1.0 - t * 30.0)
            samples.append((c1 + c2 + noise) * math.exp(-t * 16.0))
        sfx['boss_hit'] = self._create_wav_sound(samples)

        # 15. Boss Awakening Roar: Menacing insectoid screech + sub-bass tremor
        n = int(sr * 0.55)
        samples = []
        for i in range(n):
            t = i / sr
            env = (1.0 - t / 0.55)
            screech_f = 580.0 - t * 420.0 + math.sin(2.0 * math.pi * 48.0 * t) * 95.0
            saw = 2.0 * ((screech_f * t) % 1.0) - 1.0
            sub = math.sin(2.0 * math.pi * 58.0 * t) * 0.45
            noise = (random.random() * 2.0 - 1.0) * 0.22
            samples.append((saw * 0.32 + sub + noise) * env)
        sfx['boss_roar'] = self._create_wav_sound(samples)

        return sfx

    def _build_jamaican_track(self, bpm, pattern):
        """Synthesizes the upbeat Jamaican Dub / Reggae level theme."""
        sr = self.SAMPLE_RATE
        step_dur = 60.0 / (bpm * 4.0)

        if HAS_NUMPY:
            num_steps = len(pattern)
            step_samples = int(sr * step_dur)
            total_samples = num_steps * step_samples
            out = np.zeros(total_samples, dtype=np.float32)
            t_step = np.linspace(0, step_dur, step_samples, endpoint=False)

            for i, (b_freq, (sk1, sk2), l_freq, drum) in enumerate(pattern):
                start = i * step_samples
                end = start + step_samples
                s = np.zeros(step_samples, dtype=np.float32)

                # 1. Warm Dub Bass (Triangle + Sub-Bass Sine)
                if b_freq > 0:
                    phase = (b_freq * t_step) % 1.0
                    tri = 4.0 * np.abs(phase - 0.5) - 1.0
                    sub = np.sin(2.0 * np.pi * b_freq * t_step) * 0.25
                    env_b = np.maximum(0.0, 1.0 - t_step / step_dur)
                    s += (tri + sub) * 0.35 * env_b

                # 2. Reggae Skank Chords (Offbeat percussive chops)
                if sk1 > 0:
                    p1 = (sk1 * t_step) % 1.0
                    p2 = (sk2 * t_step) % 1.0
                    sq1 = np.where(p1 < 0.35, 1.0, -1.0)
                    sq2 = np.where(p2 < 0.35, 1.0, -1.0)
                    env_sk = np.maximum(0.0, 1.0 - t_step * 16.0)
                    s += (sq1 + sq2) * 0.12 * env_sk

                # 3. Whimsical Island Froggy Lead
                if l_freq > 0:
                    vib = np.sin(2.0 * np.pi * 5.5 * t_step) * (l_freq * 0.02)
                    mf = l_freq + vib
                    p_lead = (mf * t_step) % 1.0
                    pulse = np.where(p_lead < 0.25, 1.0, -1.0)
                    env_l = np.maximum(0.0, 1.0 - t_step * 2.2)
                    s += pulse * 0.18 * env_l

                # 4. One-Drop Drums
                if drum in ('k', 'd'):
                    freq_k = np.maximum(35.0, 130.0 - t_step * 650.0)
                    kick = np.sin(2.0 * np.pi * freq_k * t_step) * 0.40 * np.maximum(0.0, 1.0 - t_step * 14.0)
                    s += kick
                if drum in ('s', 'd', 'f'):
                    noise = (np.random.rand(step_samples) * 2.0 - 1.0) * 0.22 * np.maximum(0.0, 1.0 - t_step * 15.0)
                    rim = np.sin(2.0 * np.pi * 220.0 * t_step) * 0.18 * np.maximum(0.0, 1.0 - t_step * 20.0)
                    s += noise + rim
                if drum == 'h':
                    hat = (np.random.rand(step_samples) * 2.0 - 1.0) * 0.06 * np.maximum(0.0, 1.0 - t_step * 38.0)
                    s += hat

                out[start:end] = s

            out = np.clip(out, -0.95, 0.95)
            pcm16 = (out * 32767).astype(np.int16)
            stereo = np.repeat(pcm16[:, np.newaxis], 2, axis=1)
            return pygame.sndarray.make_sound(stereo)
        else:
            return self._create_wav_sound([0.0] * 1000)

    def _build_sinister_boss_track(self, bpm, pattern):
        """
        Synthesizes a dark, menacing 16-bit Boss Theme for the Emperor Mantis!
        Unlike the cheerful Jamaican groove, this uses:
          - Aggressive Sawtooth + Sub-Octave Bass ostinato
          - Dissonant Gothic Cathedral Organ chords (detuned harmonics)
          - Piercing Phrygian Dominant / Harmonic Minor lead with eerie vibrato
          - Driving double-kick & metallic industrial snare percussion
        """
        sr = self.SAMPLE_RATE
        step_dur = 60.0 / (bpm * 4.0)

        if HAS_NUMPY:
            num_steps = len(pattern)
            step_samples = int(sr * step_dur)
            total_samples = num_steps * step_samples
            out = np.zeros(total_samples, dtype=np.float32)
            t_step = np.linspace(0, step_dur, step_samples, endpoint=False)

            for i, (b_freq, (org1, org2), l_freq, drum) in enumerate(pattern):
                start = i * step_samples
                end = start + step_samples
                s = np.zeros(step_samples, dtype=np.float32)

                # 1. Menacing Sawtooth + Sub-Octave Bass
                if b_freq > 0:
                    saw = 2.0 * ((b_freq * t_step) % 1.0) - 1.0
                    sub = np.sin(2.0 * np.pi * (b_freq * 0.5) * t_step)
                    env_b = np.maximum(0.0, 1.0 - t_step / (step_dur * 0.95))
                    s += (saw * 0.24 + sub * 0.28) * env_b

                # 2. Dark Gothic Organ / Pad (Dissonant minor/diminished intervals)
                if org1 > 0:
                    o1 = np.sin(2.0 * np.pi * org1 * t_step) + 0.5 * np.sin(4.0 * np.pi * org1 * t_step)
                    o2 = np.sin(2.0 * np.pi * org2 * t_step) + 0.5 * np.sin(4.0 * np.pi * org2 * t_step)
                    env_o = np.maximum(0.0, 1.0 - t_step * 4.5)
                    s += (o1 + o2) * 0.09 * env_o

                # 3. Sinister Chromatic / Phrygian Lead Synth
                if l_freq > 0:
                    vib = np.sin(2.0 * np.pi * 7.5 * t_step) * (l_freq * 0.028)
                    mf = l_freq + vib
                    p1 = (mf * t_step) % 1.0
                    p2 = ((mf * 1.006) * t_step) % 1.0  # Detuned chorus saw/pulse
                    lead_wave = np.where(p1 < 0.22, 1.0, -1.0) + (2.0 * p2 - 1.0) * 0.5
                    env_l = np.maximum(0.0, 1.0 - t_step * 2.6)
                    s += lead_wave * 0.16 * env_l

                # 4. Heavy Industrial / Tribal War Drums
                if drum in ('k', 'd'):
                    freq_k = np.maximum(30.0, 155.0 - t_step * 820.0)
                    kick = np.sin(2.0 * np.pi * freq_k * t_step) * 0.45 * np.maximum(0.0, 1.0 - t_step * 15.0)
                    s += kick
                if drum in ('s', 'd', 'f'):
                    noise = (np.random.rand(step_samples) * 2.0 - 1.0) * 0.28 * np.maximum(0.0, 1.0 - t_step * 14.0)
                    body = np.sin(2.0 * np.pi * 185.0 * t_step) * 0.22 * np.maximum(0.0, 1.0 - t_step * 22.0)
                    s += noise + body
                if drum == 'h':
                    hat = (np.random.rand(step_samples) * 2.0 - 1.0) * 0.07 * np.maximum(0.0, 1.0 - t_step * 42.0)
                    s += hat

                out[start:end] = s

            out = np.clip(out, -0.95, 0.95)
            pcm16 = (out * 32767).astype(np.int16)
            stereo = np.repeat(pcm16[:, np.newaxis], 2, axis=1)
            return pygame.sndarray.make_sound(stereo)
        else:
            return self._create_wav_sound([0.0] * 1000)

    def _build_all_music(self):
        # ---------------------------------------------------------------------
        # TRACK 1: 64-Step Jamaican Froggy Groove (G Major / Dub Reggae, 104 BPM)
        # ---------------------------------------------------------------------
        pattern_jamaica = [
            # BAR 1: G Major
            (0,     (0,0),         392.0, '.'),
            (98.0,  (0,0),         0,     'h'),
            (0,     (246.9,392.0), 329.6, 'h'),
            (98.0,  (0,0),         0,     'h'),
            (0,     (0,0),         293.7, 'h'),
            (146.8, (0,0),         0,     'h'),
            (0,     (246.9,392.0), 392.0, 'h'),
            (0,     (0,0),         0,     'h'),
            (98.0,  (0,0),         440.0, 'd'),
            (0,     (0,0),         0,     'h'),
            (0,     (246.9,392.0), 392.0, 'h'),
            (123.5, (0,0),         0,     'h'),
            (146.8, (0,0),         329.6, 'h'),
            (0,     (0,0),         0,     'h'),
            (0,     (246.9,392.0), 293.7, 'h'),
            (164.8, (0,0),         0,     'f'),

            # BAR 2: C Major
            (0,     (0,0),         261.6, '.'),
            (130.8, (0,0),         0,     'h'),
            (0,     (261.6,329.6), 329.6, 'h'),
            (130.8, (0,0),         0,     'h'),
            (0,     (0,0),         392.0, 'h'),
            (164.8, (0,0),         0,     'h'),
            (0,     (261.6,329.6), 523.2, 'h'),
            (0,     (0,0),         0,     'h'),
            (130.8, (0,0),         392.0, 'd'),
            (0,     (0,0),         0,     'h'),
            (0,     (261.6,329.6), 329.6, 'h'),
            (146.8, (0,0),         0,     'h'),
            (164.8, (0,0),         261.6, 'h'),
            (0,     (0,0),         0,     'h'),
            (0,     (261.6,329.6), 293.7, 'h'),
            (146.8, (0,0),         0,     'f'),

            # BAR 3: E Minor / D Major
            (0,     (0,0),         329.6, '.'),
            (82.4,  (0,0),         0,     'h'),
            (0,     (196.0,329.6), 392.0, 'h'),
            (82.4,  (0,0),         0,     'h'),
            (0,     (0,0),         440.0, 'h'),
            (123.5, (0,0),         0,     'h'),
            (0,     (196.0,329.6), 493.8, 'h'),
            (0,     (0,0),         0,     'h'),
            (146.8, (0,0),         392.0, 'd'),
            (0,     (0,0),         0,     'h'),
            (0,     (220.0,369.9), 329.6, 'h'),
            (110.0, (0,0),         0,     'h'),
            (146.8, (0,0),         293.7, 'h'),
            (0,     (0,0),         0,     'h'),
            (0,     (220.0,369.9), 246.9, 'h'),
            (123.5, (0,0),         0,     'f'),

            # BAR 4: D7 Turnaround
            (0,     (0,0),         293.7, '.'),
            (146.8, (0,0),         0,     'h'),
            (0,     (220.0,293.7), 369.9, 'h'),
            (146.8, (0,0),         0,     'h'),
            (0,     (0,0),         440.0, 'h'),
            (110.0, (0,0),         0,     'h'),
            (0,     (220.0,293.7), 493.8, 'h'),
            (0,     (0,0),         0,     'h'),
            (146.8, (0,0),         587.3, 'd'),
            (0,     (0,0),         0,     'h'),
            (0,     (220.0,293.7), 493.8, 'h'),
            (164.8, (0,0),         0,     'h'),
            (146.8, (0,0),         440.0, 'h'),
            (130.8, (0,0),         0,     's'),
            (123.5, (220.0,293.7), 392.0, 's'),
            (110.0, (0,0),         369.9, 'f'),
        ]

        # ---------------------------------------------------------------------
        # TRACK 2: 64-Step SINISTER EMPEROR MANTIS THEME (D Harmonic Minor /
        # Phrygian Dominant: D, Eb, F#, G, A, Bb, C# - 140 BPM)
        # ---------------------------------------------------------------------
        # Note frequencies used:
        # Bass: D2=73.4, Eb2=77.8, F2=87.3, G2=98.0, G#2=103.8, A2=110.0, Bb2=116.5, C#3=138.6
        # Lead: D4=293.7, Eb4=311.1, F4=349.2, F#4=370.0, G4=392.0, G#4=415.3, A4=440.0, Bb4=466.2, C#5=554.4, D5=587.3
        pattern_sinister_boss = [
            # BAR 1: Ominous D Minor / Eb Phrygian Stalking Ostinato
            (73.4,  (146.8,220.0), 587.3, 'k'),
            (73.4,  (0,0),         0,     'h'),
            (77.8,  (0,0),         554.4, 'k'),
            (73.4,  (0,0),         587.3, 'h'),
            (73.4,  (146.8,220.0), 440.0, 's'),
            (73.4,  (0,0),         0,     'h'),
            (103.8, (0,0),         466.2, 'k'),
            (110.0, (0,0),         440.0, 'h'),
            (73.4,  (146.8,220.0), 349.2, 'k'),
            (73.4,  (0,0),         0,     'k'),
            (77.8,  (155.6,233.1), 311.1, 'h'),
            (77.8,  (0,0),         0,     'h'),
            (73.4,  (146.8,220.0), 293.7, 's'),
            (0,     (0,0),         311.1, 'h'),
            (103.8, (207.7,293.7), 415.3, 'k'),
            (110.0, (0,0),         440.0, 'f'),

            # BAR 2: Rising Diminished / Chromatic Terror
            (73.4,  (146.8,220.0), 587.3, 'k'),
            (73.4,  (0,0),         0,     'h'),
            (87.3,  (0,0),         622.3, 'k'), # Eb5
            (73.4,  (0,0),         587.3, 'h'),
            (103.8, (207.7,293.7), 554.4, 's'),
            (103.8, (0,0),         0,     'h'),
            (110.0, (0,0),         466.2, 'k'),
            (73.4,  (0,0),         440.0, 'h'),
            (116.5, (233.1,349.2), 466.2, 'k'),
            (116.5, (0,0),         554.4, 'k'),
            (110.0, (220.0,329.6), 587.3, 'h'),
            (103.8, (0,0),         554.4, 'h'),
            (98.0,  (196.0,293.7), 466.2, 's'),
            (87.3,  (0,0),         440.0, 'h'),
            (77.8,  (155.6,233.1), 349.2, 'k'),
            (73.4,  (0,0),         311.1, 'f'),

            # BAR 3: Gothic Cathedral Organ & Scythe Arpeggio
            (116.5, (233.1,349.2), 466.2, 'k'),
            (116.5, (0,0),         349.2, 'h'),
            (116.5, (0,0),         293.7, 'k'),
            (116.5, (0,0),         466.2, 'h'),
            (110.0, (220.0,330.0), 440.0, 's'),
            (110.0, (0,0),         370.0, 'h'),
            (110.0, (0,0),         293.7, 'k'),
            (110.0, (0,0),         440.0, 'h'),
            (103.8, (207.7,311.1), 415.3, 'k'),
            (103.8, (0,0),         349.2, 'k'),
            (103.8, (0,0),         293.7, 'h'),
            (103.8, (0,0),         415.3, 'h'),
            (110.0, (220.0,330.0), 440.0, 's'),
            (110.0, (0,0),         466.2, 'k'),
            (138.6, (277.2,415.3), 554.4, 's'),
            (110.0, (0,0),         587.3, 'f'),

            # BAR 4: Frantic Diminished Climax & Loop Turnaround
            (73.4,  (146.8,220.0), 698.5, 'k'), # F5
            (77.8,  (0,0),         622.3, 'h'), # Eb5
            (73.4,  (0,0),         587.3, 'k'), # D5
            (103.8, (0,0),         554.4, 'h'), # C#5
            (110.0, (220.0,330.0), 466.2, 's'), # Bb4
            (103.8, (0,0),         440.0, 'h'), # A4
            (98.0,  (0,0),         415.3, 'k'), # G#4
            (87.3,  (0,0),         392.0, 'h'), # G4
            (77.8,  (155.6,233.1), 349.2, 'k'), # F4
            (77.8,  (0,0),         311.1, 'k'), # Eb4
            (87.3,  (0,0),         349.2, 's'),
            (98.0,  (0,0),         415.3, 'h'),
            (103.8, (207.7,311.1), 466.2, 'k'),
            (110.0, (220.0,330.0), 554.4, 's'),
            (138.6, (277.2,415.3), 587.3, 's'),
            (73.4,  (146.8,220.0), 293.7, 'f'),
        ]

        jamaican_music = self._build_jamaican_track(104, pattern_jamaica)
        boss_music = self._build_sinister_boss_track(140, pattern_sinister_boss)

        return {
            'title': jamaican_music,
            'level': jamaican_music,
            'boss': boss_music,
        }

    def play_sfx(self, name):
        if not self.enabled:
            return
        snd = self.sfx.get(name)
        if snd:
            snd.play()

    def play_music(self, track_name):
        if not self.enabled or track_name == self.current_track_name:
            return
        track = self.music_tracks.get(track_name)
        if track:
            self.current_track_name = track_name
            self.music_channel.play(track, loops=-1)

    def stop_music(self):
        if self.enabled:
            self.music_channel.stop()
            self.current_track_name = None


# =============================================================================
# CHAPTER 3. HYBRID ASSET LOADER & 4-BIT AUTO-TILER
# =============================================================================
# HOW 4-BIT NEIGHBOR AUTO-TILING WORKS:
# When a level designer types '#' in the ASCII map, how does the game know
# whether to draw lush overhanging grass on top, a chiseled stone wall on the
# left, or deep temple bricks inside?
#
# For every '#' tile at (row, col), we check its 4 cardinal neighbors:
#   - North (row - 1, col) -> Adds 1 if also '#'
#   - East  (row, col + 1) -> Adds 2 if also '#'
#   - South (row + 1, col) -> Adds 4 if also '#'
#   - West  (row, col - 1) -> Adds 8 if also '#'
#
# That sum is a number from 0 to 15 (a 4-bit binary bitmask!).
#   - If North is 0 (air above), `terrain_<mask>.png` has lush overhanging moss!
#   - If North is 1 (solid above), `terrain_<mask>.png` is solid masonry!

class AssetManager:
    """
    Loads all generated PNG assets from `assets/` (auto-generating them first
    via `generate_assets.py` if missing) and provides instant fallbacks.
    """
    def __init__(self):
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        if HAS_ASSET_GENERATOR:
            generate_assets.build_all_assets(force=False)

        self.autotiles = {"jungle": {}, "sanctum": {}}
        self.special_tiles = {}
        self.props = {}
        self.lights = {}
        self.backgrounds = {}
        self.parallax_mid = {}

        self._load_all()

    def _load_png(self, subdir, filename, convert_alpha=True):
        path = os.path.join(self.base_dir, subdir, filename)
        if os.path.exists(path):
            img = pygame.image.load(path)
            return img.convert_alpha() if convert_alpha else img.convert()
        return None

    def _load_all(self):
        # 1. Load 16-variant 4-bit Auto-Tile Sets (Jungle & Sinister Sanctum)
        for theme, prefix in [("jungle", "terrain"), ("sanctum", "sanctum")]:
            for mask in range(16):
                surf = self._load_png("tiles", f"{prefix}_{mask}.png")
                if surf is None:
                    surf = pygame.Surface((16, 16))
                    surf.fill((56, 72, 102) if theme == "jungle" else (62, 28, 54))
                self.autotiles[theme][mask] = surf
            alt = self._load_png("tiles", f"{prefix}_15_alt.png")
            self.autotiles[theme]["15_alt"] = alt if alt else self.autotiles[theme][15]

        # 2. Load Special Interactive Tiles (Grapple Idol, Doors, Animated Water)
        self.special_tiles["grapple"] = [
            self._load_png("tiles", "grapple_0.png"),
            self._load_png("tiles", "grapple_1.png"),
        ]
        self.special_tiles["door"] = [
            self._load_png("tiles", f"door_{i}.png") for i in range(4)
        ]
        self.special_tiles["boss_door"] = [
            self._load_png("tiles", f"boss_door_{i}.png") for i in range(4)
        ]
        self.special_tiles["water"] = [
            self._load_png("tiles", f"water_{i}.png") for i in range(4)
        ]

        # 3. Load Lush Foliage & Storytelling Props
        self.props["fern"] = [self._load_png("props", f"fern_{i}.png") for i in range(3)]
        self.props["grass"] = [self._load_png("props", f"grass_{i}.png") for i in range(2)]
        self.props["shroom_cyan"] = self._load_png("props", "shroom_cyan.png")
        self.props["shroom_magenta"] = self._load_png("props", "shroom_magenta.png")
        self.props["shroom_gold"] = self._load_png("props", "shroom_gold.png")
        self.props["frog_statue"] = self._load_png("props", "frog_statue.png")
        self.props["mantis_totem"] = self._load_png("props", "mantis_totem.png")

        # 4. Load Additive Radial Light Maps (`BLEND_RGB_ADD`)
        for lname in ("cyan", "emerald", "gold", "magenta", "crimson", "player"):
            lsurf = self._load_png("fx", f"light_{lname}.png", convert_alpha=False)
            if lsurf is None:
                lsurf = pygame.Surface((64, 64))
            self.lights[lname] = lsurf

        # 5. Load 640x360 16-Bit Pixel-Art Backgrounds & Parallax Layers
        for bg_key in ("canopy", "temple", "cavern", "sanctum"):
            ai_bg = self._load_png("backgrounds", f"bg_{bg_key}.png", convert_alpha=False)
            proc_bg = self._load_png("backgrounds", f"proc_{bg_key}_sky.png", convert_alpha=False)
            self.backgrounds[bg_key] = ai_bg if ai_bg is not None else proc_bg
            self.parallax_mid[bg_key] = self._load_png("backgrounds", f"parallax_{bg_key}_mid.png", convert_alpha=True)

    def build_froggy_animations(self):
        """Loads upgraded multi-shaded Froggy sprites (with flip for left-facing)."""
        raw_frames = {
            "idle": [
                self._load_png("sprites", "froggy_idle_0.png"),
                self._load_png("sprites", "froggy_idle_1.png"),
            ],
            "run": [
                self._load_png("sprites", "froggy_run_0.png"),
                self._load_png("sprites", "froggy_run_1.png"),
                self._load_png("sprites", "froggy_run_2.png"),
                self._load_png("sprites", "froggy_run_3.png"),
            ],
            "jump": [self._load_png("sprites", "froggy_jump_0.png")],
            "wall_slide": [self._load_png("sprites", "froggy_wall_0.png")],
            "tongue": [self._load_png("sprites", "froggy_tongue_0.png")],
        }
        animations = {"right": {}, "left": {}}
        for state_name, surface_list in raw_frames.items():
            animations["right"][state_name] = surface_list
            animations["left"][state_name] = [
                pygame.transform.flip(surf, True, False) for surf in surface_list
            ]
        return animations

    def build_enemy_animations(self):
        """Loads Spiked Moss Beetle, Neon Buzzfly, and 36x36 Emperor Mantis sprites."""
        b0 = self._load_png("sprites", "beetle_0.png")
        b1 = self._load_png("sprites", "beetle_1.png")
        b_stun = pygame.transform.flip(b0, False, True)

        f0 = self._load_png("sprites", "fly_0.png")
        f1 = self._load_png("sprites", "fly_1.png")

        m_arm_r = self._load_png("sprites", "mantis_armored.png")
        m_arm_l = pygame.transform.flip(m_arm_r, True, False)
        m_exp_r = self._load_png("sprites", "mantis_exposed.png")
        m_exp_l = pygame.transform.flip(m_exp_r, True, False)

        return {
            "beetle": {
                "right": [b0, b1],
                "left": [pygame.transform.flip(b0, True, False), pygame.transform.flip(b1, True, False)],
                "stunned": [b_stun, pygame.transform.flip(b_stun, True, False)],
            },
            "fly": {
                "right": [f0, f1],
                "left": [pygame.transform.flip(f0, True, False), pygame.transform.flip(f1, True, False)],
            },
            "mantis": {
                "armored_right": m_arm_r,
                "armored_left": m_arm_l,
                "exposed_right": m_exp_r,
                "exposed_left": m_exp_l,
            },
        }


# =============================================================================
# CHAPTER 4. LUSH AMBIANCE ENGINE (INTERACTIVE VINES & FIREFLIES)
# =============================================================================
# To make the jungle feel alive:
# 1. `HangingVine`: Hangs from ceiling blocks. When Froggy runs or jumps through
#    a vine, his horizontal speed pushes the vine segments so they sway back and
#    forth like a real pendulum chain!
# 2. `FireflySpore`: Drifts through the air on gentle sine-wave currents and
#    emits an additive light halo (`BLEND_RGB_ADD`) onto the background.

class HangingVine:
    def __init__(self, x, y, num_segments=6, sinister=False):
        self.anchor_x = float(x)
        self.anchor_y = float(y)
        self.num_segments = num_segments
        self.seg_len = 8.0
        self.angle = random.uniform(-0.08, 0.08)
        self.angular_vel = 0.0
        self.phase_offset = random.uniform(0.0, math.tau)
        self.sinister = sinister

    def update(self, player, pulse_timer):
        # Gentle ambient breeze + spring restoring force toward vertical (0 radians)
        wind = math.sin(pulse_timer * 0.04 + self.phase_offset) * 0.0012
        spring = -0.018 * self.angle
        self.angular_vel = (self.angular_vel + spring + wind) * 0.96
        self.angle += self.angular_vel

        # Check if Froggy brushes against the vine
        if player is not None:
            vine_h = self.num_segments * self.seg_len
            if (abs(player.center_x - self.anchor_x) < 12 and
                    self.anchor_y <= player.center_y <= self.anchor_y + vine_h):
                self.angular_vel += np.clip(player.vx * 0.012, -0.06, 0.06) if HAS_NUMPY else (player.vx * 0.01)

    def draw(self, surface, camera_x, camera_y):
        sx = self.anchor_x - camera_x
        sy = self.anchor_y - camera_y
        if sx < -32 or sx > INTERNAL_WIDTH + 32 or sy > INTERNAL_HEIGHT + 32:
            return

        col_main = (145, 32, 65) if self.sinister else (46, 152, 64)
        col_leaf = (225, 65, 105) if self.sinister else (112, 225, 92)

        curr_x, curr_y = sx, sy
        for i in range(1, self.num_segments + 1):
            # Lower segments bend slightly more for a whip-like curve
            seg_angle = self.angle * (1.0 + i * 0.18)
            next_x = curr_x + math.sin(seg_angle) * self.seg_len
            next_y = curr_y + math.cos(seg_angle) * self.seg_len
            pygame.draw.line(surface, col_main, (int(curr_x), int(curr_y)), (int(next_x), int(next_y)), 2)
            if i % 2 == 1:
                leaf_dx = 3 if (i % 4 == 1) else -3
                pygame.draw.circle(surface, col_leaf, (int(next_x + leaf_dx), int(next_y)), 2)
            curr_x, curr_y = next_x, next_y


class FireflySpore:
    def __init__(self, world_w, world_h, sinister=False):
        self.x = random.uniform(24, max(64, world_w - 24))
        self.y = random.uniform(24, max(64, world_h - 24))
        self.base_x = self.x
        self.base_y = self.y
        self.phase = random.uniform(0.0, math.tau)
        self.speed = random.uniform(0.02, 0.045)
        self.sinister = sinister
        if sinister:
            self.color = random.choice([(255, 75, 120), (210, 95, 255), (255, 190, 70)])
            self.light_key = "crimson" if self.color[0] > 230 else "magenta"
        else:
            self.color = random.choice([(130, 255, 235), (165, 255, 120), (255, 235, 110)])
            self.light_key = "cyan" if self.color[2] > 200 else "emerald"

    def update(self, pulse_timer):
        t = pulse_timer * self.speed + self.phase
        self.x = self.base_x + math.sin(t) * 18.0
        self.y = self.base_y + math.cos(t * 0.8) * 12.0

    def draw(self, surface, camera_x, camera_y, assets, pulse_timer):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        if -32 <= sx <= INTERNAL_WIDTH + 32 and -32 <= sy <= INTERNAL_HEIGHT + 32:
            # Soft additive glow halo
            light_tex = assets.lights.get(self.light_key)
            if light_tex and (int(self.phase * 10) + pulse_timer) % 2 == 0:
                lw, lh = light_tex.get_size()
                surface.blit(light_tex, (sx - lw // 2, sy - lh // 2), special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(surface, self.color, (sx, sy), 2)
            pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 1)


# =============================================================================
# CHAPTER 5. VISUAL ASCII WORLD BLUEPRINTS (LEVEL 1 TO BOSS SANCTUM)
# =============================================================================
# LEGEND FOR ASCII LEVEL BLUEPRINTS:
#   '#' = Solid Terrain (Automatically 4-bit auto-tiled with moss, roots & stone!)
#   '~' = Bioluminescent Swamp Water Hazard (Animated 4-frame glowing water)
#   'G' = Golden Frog Grapple Idol (Latch & swing with Y button!)
#   'S' = Froggy's Default Spawn Point
#   'E' = Spiked Moss Beetle (Stun with R or Tongue, then Swallow with Y!)
#   'F' = Neon Buzzfly (Sine-wave flying bug - instant Swallow with Y!)
#   'M' = Emperor Mantis 3-Phase Boss (Dormant until Froggy approaches!)
#   'T' = Ancient Mantis Warning Totem (Ominous environmental storytelling prop)
#   'A', 'B', 'C' = Glowing Rune Portals connecting the Metroidvania world

WORLD_BLUEPRINTS = {
    # -------------------------------------------------------------------------
    # LEVEL 1: LUSH CANOPY TRAIL -> TEMPLE CHIMNEY -> EMPEROR MANTIS SANCTUM
    # A complete, seamless 3-act showcase level (116 cols x 23 rows = 1856x368 px):
    #   - Act I   (Cols 0..38) : Sunlit Lush Canopy (Hops, Double Jump, First Beetle)
    #   - Act II  (Cols 39..76): Temple Wall-Jump Chimney & Grapple Water Chasm
    #   - Act III (Cols 77..115): Ominous Totems & The Emperor Mantis Boss Arena!
    # When Froggy crosses into Act III, the Emperor Mantis awakens and the music
    # dynamically shifts from the Jamaican groove to the Sinister Boss Theme!
    # -------------------------------------------------------------------------
    "level_1": {
        "title": "LEVEL 1: LUSH CANOPY TO MANTIS SANCTUM",
        "theme": "canopy",
        "bg_color": (16, 28, 42),
        "map_coords": (0, 0),
        "boss_trigger_x": 1220,  # Crossing X=1220 awakens the Emperor Mantis & sinister music!
        "doors": {
            "A": {
                "target_room": "entrance_hall",
                "target_door": "A_IN",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "####################################################################################################################", # 0
            "#..................................................................................................................#", # 1
            "#..................................................................................................................#", # 2
            "#..................................................................................................................#", # 3
            "#.............................................................G....................................................#", # 4
            "#....................................................................................G..........G..........G.......#", # 5
            "#...............................................#...#.######.......................................................#", # 6
            "#...............................................#...#..............................................................#", # 7
            "#...............................................#...#..............................................................#", # 8
            "#.........................F.....................#...#....................................................M.........#", # 9
            "#.......................#####...................#...#...................#######....................................#", # 10
            "#...............................................#...#.........................T......#####.................#####...#", # 11
            "#.............................##############....#...#..............................................................#", # 12
            "#....................................E..........#...#.......................................G..........G...........#", # 13
            "#...............................................#...#..............................................................#", # 14
            "#................####...........................#...#..........F...................................................#", # 15
            "#...................................................#....................................#####.........#####.......#", # 16
            "#....S..............................................#..............................................................A", # 17
            "#..######...##......................................#..............................................................A", # 18
            "#.......................E...........................#.........................T....................................A", # 19
            "#....................#######........................#...................#############..............................#", # 20
            "#####################################################~~~~~~~~~~~~~~~~~~~############################################", # 21
            "####################################################################################################################", # 22
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 2: SUNKEN FROG TEMPLE HALL
    # -------------------------------------------------------------------------
    "entrance_hall": {
        "title": "2. SUNKEN FROG TEMPLE HALL",
        "theme": "temple",
        "bg_color": (18, 24, 44),
        "map_coords": (1, 0),
        "doors": {
            "A_IN": {
                "target_room": "level_1",
                "target_door": "A",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
            "A": {
                "target_room": "chimney_tower",
                "target_door": "A",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#..........................................................#",
            "#................G........................G................#",
            "#..........................................................#",
            "#............................F.............................#",
            "#...................................................########",
            "#............................E.............................#",
            "#.........................########.........................#",
            "#.........F......................................F.........#",
            "#.............######....................######.............#",
            "#..........................................................#",
            "#..........................................................#",
            "#.............................................E............#",
            "#..........................................######..........#",
            "#....................E.....................................#",
            "#.................######...................................#",
            "A_IN.......................................................A",
            "A_IN.......................................................A",
            "A_IN###.......................................E............A",
            "#..........................................#######.........#",
            "########################~~~~~~~~~~~~########################",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 3: VINE CHIMNEY TOWER
    # -------------------------------------------------------------------------
    "chimney_tower": {
        "title": "3. VINE CHIMNEY ASCENT",
        "theme": "cavern",
        "bg_color": (22, 20, 44),
        "map_coords": (1, 1),
        "doors": {
            "A": {
                "target_room": "entrance_hall",
                "target_door": "A",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
            "B": {
                "target_room": "grapple_cavern",
                "target_door": "B",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################",
            "#..........................................#",
            "#.....................G....................#",
            "#..........................................B",
            "#..................................E.......B",
            "#............................###############",
            "#..................###.....#...............#",
            "#........F.........###.....#...............#",
            "#..................###.....#...............#",
            "#........G.........###.....#...............#",
            "#..................###.....#...............#",
            "#..................###.....#...............#",
            "#..................###...........F.........#",
            "#..................###...............E.....#",
            "#..................###............######...#",
            "#........F.........###.....................#",
            "#..................###.....................#",
            "#..................###.............G.......#",
            "#..........E.......###.....................#",
            "#.......######.....###.....................#",
            "#..................###............E........#",
            "A..............................######......#",
            "A............E.............................#",
            "A.........######...........................#",
            "############################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 4: BIOLUMINESCENT GRAPPLE CAVERN
    # -------------------------------------------------------------------------
    "grapple_cavern": {
        "title": "4. BIOLUMINESCENT GRAPPLE CAVERN",
        "theme": "cavern",
        "bg_color": (14, 30, 42),
        "map_coords": (2, 1),
        "doors": {
            "B": {
                "target_room": "chimney_tower",
                "target_door": "B",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
            "C": {
                "target_room": "boss_sanctum",
                "target_door": "C",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#..........................................................#",
            "B...........G.............G.............G.............G....#",
            "B..........................................................#",
            "#########..................................................#",
            "#.................F.............F.............F............#",
            "#...................G.............G.............G..........#",
            "#..........................................................#",
            "#........................................................T.#",
            "#..........E..........................................######",
            "#.......#####.............F.............F..................#",
            "#..........................................................#",
            "#...................###.........###.........###............#",
            "#...................###.........###.........###............C",
            "#...................###.........###.........###..........E.C",
            "#...................###.........###.........###.......######",
            "#...................###.........###.........###............#",
            "#...................###.........###.........###............#",
            "#...................###.........###.........###............#",
            "#...................###.........###.........###............#",
            "###################~~~~~~~~~###~~~~~~~~~###~~~~~~~~~~~~~~~~#",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 5: EMPEROR MANTIS SANCTUM (DEDICATED BOSS LAIR)
    # -------------------------------------------------------------------------
    "boss_sanctum": {
        "title": "5. EMPEROR MANTIS SANCTUM",
        "theme": "sanctum",
        "bg_color": (34, 12, 28),
        "map_coords": (3, 1),
        "boss_trigger_x": 60,  # Immediate boss awakening upon entering the Sanctum!
        "doors": {
            "C": {
                "target_room": "grapple_cavern",
                "target_door": "C",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################",
            "#..........................................#",
            "#..........................................#",
            "#.........G..........G..........G..........#",
            "#..........................................#",
            "#..........................................#",
            "#..............................M...........#",
            "#..........................................#",
            "#....######......................######....#",
            "#..........................................#",
            "#..............G............G..............#",
            "#..........................................#",
            "#..........................................#",
            "#.........######............######.........#",
            "#..........................................#",
            "#..........................................#",
            "#..........................................#",
            "C......T............................T......#",
            "C...#######......................#######...#",
            "C..........................................#",
            "#..........................................#",
            "############################################",
            "############################################",
        ],
    },

    # -------------------------------------------------------------------------
    # SANDBOX ROOM: CLEAN CANVAS FOR "CREATE LEVEL" MODE
    # -------------------------------------------------------------------------
    "sandbox_room": {
        "title": "BUILDER'S SANDBOX",
        "theme": "canopy",
        "bg_color": (18, 24, 38),
        "map_coords": (0, 2),
        "doors": {
            "A": {
                "target_room": "level_1",
                "target_door": "A",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "##################################################",
            "#................................................#",
            "#................................................#",
            "#..................G..........G..................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#....S...........................................A",
            "#..######..............######....................A",
            "#................................................A",
            "#................................................#",
            "##################################################",
            "##################################################",
        ],
    },
}


# =============================================================================
# CHAPTER 6. PARTICLES & BOOMERANG / SCYTHE PROJECTILES
# =============================================================================

class Particle:
    def __init__(self, x, y, vx, vy, color, lifetime):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.color = color
        self.lifetime = lifetime
        self.age = 0

    def update(self):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.14

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        size = 3 if (self.lifetime - self.age) > 8 else 2
        pygame.draw.rect(surface, self.color, (sx, sy, size, size))


class SporeBoomerang:
    """
    Froggy's Special Weapon (R Button):
    Launches a glowing cyan bioluminescent spore along the 8-way D-Pad aim
    vector, then accelerates backward so it curves back like a boomerang!
    """
    def __init__(self, x, y, dir_x, dir_y):
        self.x = float(x)
        self.y = float(y)
        self.vx = dir_x * 6.6
        self.vy = dir_y * 6.6
        self.return_ax = -dir_x * 0.14
        self.return_ay = -dir_y * 0.14
        self.age = 0
        self.max_age = 115
        self.radius = 5
        self.alive = True

    def update(self, room, audio=None):
        self.age += 1
        self.vx += self.return_ax
        self.vy += self.return_ay
        self.x += self.vx
        self.y += self.vy

        hit_box = pygame.Rect(int(self.x - 6), int(self.y - 6), 12, 12)

        for enemy in room.enemies:
            if enemy.alive and enemy.state == "PATROL" and enemy.rect.colliderect(hit_box):
                enemy.stun(knockback_dir_x=(1.0 if self.vx >= 0 else -1.0))
                room.spawn_particle_burst(enemy.center_x, enemy.center_y, COLOR_SPORE_CYAN, count=10)
                if audio:
                    audio.play_sfx("stun")

        boss = room.get_active_boss()
        if boss and boss.alive and boss.awakened and boss.rect.colliderect(hit_box):
            if boss.hit_by_spore_boomerang(room):
                self.alive = False
                if audio:
                    audio.play_sfx("stun")

        if self.age >= self.max_age:
            self.alive = False

    def draw(self, surface, camera_x, camera_y, assets=None):
        screen_x = int(self.x - camera_x)
        screen_y = int(self.y - camera_y)
        if assets and "cyan" in assets.lights:
            lt = assets.lights["cyan"]
            surface.blit(lt, (screen_x - lt.get_width() // 2, screen_y - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        angle = self.age * 0.35
        for i in range(4):
            blade_angle = angle + i * (math.pi * 0.5)
            bx = screen_x + int(math.cos(blade_angle) * 6)
            by = screen_y + int(math.sin(blade_angle) * 6)
            pygame.draw.line(surface, COLOR_SPORE_CYAN, (screen_x, screen_y), (bx, by), 2)
        pygame.draw.circle(surface, (255, 255, 255), (screen_x, screen_y), 2)


class BossScytheWave:
    """Crescent energy wave fired by the Emperor Mantis."""
    def __init__(self, x, y, vx, vy, enraged=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.enraged = enraged
        self.radius = 8
        self.age = 0
        self.max_age = 165
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x - 5), int(self.y - 5), 10, 10)

    def update(self, room):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        if self.age >= self.max_age or room.is_point_inside_solid(self.x, self.y):
            self.alive = False

    def draw(self, surface, camera_x, camera_y, assets=None):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        if assets:
            lt = assets.lights["crimson" if self.enraged else "emerald"]
            surface.blit(lt, (sx - lt.get_width() // 2, sy - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        outer_col = (255, 80, 115) if self.enraged else (130, 255, 125)
        pygame.draw.circle(surface, outer_col, (sx, sy), self.radius, 2)
        pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 3)


# =============================================================================
# CHAPTER 7. ENEMY ENTITIES & 3-PHASE EMPEROR MANTIS BOSS AI
# =============================================================================

class BaseEnemy:
    def __init__(self, spawn_x, spawn_y, width, height):
        self.x = float(spawn_x)
        self.y = float(spawn_y)
        self.width = width
        self.height = height
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        self.vx = 0.0
        self.vy = 0.0
        self.dir_x = 1
        self.state = "PATROL"
        self.stun_timer = 0
        self.anim_timer = random.randint(0, 30)
        self.alive = True
        self.is_boss = False
        self.can_yank_immediately = False

    @property
    def center_x(self):
        return self.x + self.width * 0.5

    @property
    def center_y(self):
        return self.y + self.height * 0.5

    def set_center(self, cx, cy):
        self.x = cx - self.width * 0.5
        self.y = cy - self.height * 0.5
        self.rect.topleft = (int(self.x), int(self.y))

    def stun(self, knockback_dir_x=0.0):
        self.state = "STUNNED"
        self.stun_timer = ENEMY_STUN_FRAMES
        self.vx = knockback_dir_x * 1.8
        self.vy = -3.8


class BossEnergyPearl(BaseEnemy):
    """Glowing life-force pearl yanked from the Emperor Mantis's exposed core!"""
    def __init__(self, x, y):
        super().__init__(x, y, width=12, height=12)
        self.state = "YANKED"
        self.can_yank_immediately = True

    def update(self, room):
        self.anim_timer += 1

    def draw(self, surface, camera_x, camera_y, assets=None):
        sx = int(self.center_x - camera_x)
        sy = int(self.center_y - camera_y)
        if assets and "magenta" in assets.lights:
            lt = assets.lights["magenta"]
            surface.blit(lt, (sx - lt.get_width() // 2, sy - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.circle(surface, COLOR_BOSS_CORE, (sx, sy), 6)
        pygame.draw.circle(surface, COLOR_BOSS_GOLD, (sx, sy), 4)
        pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 2)


class MossBeetle(BaseEnemy):
    """Armored ground patroller with cliff-feeler AI so it never walks off ledges."""
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y + 2, width=14, height=14)
        self.anims = enemy_anims["beetle"]
        self.patrol_speed = 0.85
        self.can_yank_immediately = False

    def update(self, room):
        self.anim_timer += 1
        if self.state == "YANKED":
            return

        if self.state == "STUNNED":
            self.stun_timer -= 1
            self.vx *= 0.88
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=False)
            if self.stun_timer <= 0:
                self.state = "PATROL"
            return

        self.vx = self.dir_x * self.patrol_speed
        self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
        self._move_and_collide(room, turn_at_ledges=True)

    def _move_and_collide(self, room, turn_at_ledges):
        self.x += self.vx
        self.rect.x = int(round(self.x))
        hit_wall = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vx > 0:
                    self.rect.right = tile.left
                elif self.vx < 0:
                    self.rect.left = tile.right
                self.x = float(self.rect.x)
                hit_wall = True

        if hit_wall and self.state == "PATROL":
            self.dir_x *= -1

        self.y += self.vy
        self.rect.y = int(round(self.y))
        on_ground = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vy > 0:
                    self.rect.bottom = tile.top
                    on_ground = True
                elif self.vy < 0:
                    self.rect.top = tile.bottom
                self.y = float(self.rect.y)
                self.vy = 0.0

        if turn_at_ledges and on_ground:
            feeler_x = self.rect.right + 2 if self.dir_x > 0 else self.rect.left - 2
            feeler_y = self.rect.bottom + 2
            if not room.is_point_inside_solid(feeler_x, feeler_y):
                self.dir_x *= -1

    def draw(self, surface, camera_x, camera_y, assets=None):
        sx = int(self.rect.x - 1 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)
        if self.state in ("STUNNED", "YANKED"):
            frames = self.anims["stunned"]
            speed = 4 if (self.state == "STUNNED" and self.stun_timer < 60) else 10
            sprite = frames[(self.anim_timer // speed) % len(frames)]
            surface.blit(sprite, (sx, sy))

            if self.state == "STUNNED":
                star_angle = self.anim_timer * 0.18
                for i in range(2):
                    ang = star_angle + i * math.pi
                    star_x = int(self.center_x - camera_x + math.cos(ang) * 7)
                    star_y = int(self.rect.top - 5 - camera_y + math.sin(ang) * 2)
                    pygame.draw.circle(surface, (255, 240, 90), (star_x, star_y), 2)
        else:
            facing_key = "right" if self.dir_x > 0 else "left"
            frames = self.anims[facing_key]
            sprite = frames[(self.anim_timer // 8) % len(frames)]
            surface.blit(sprite, (sx, sy))


class BuzzFly(BaseEnemy):
    """Bioluminescent flying insect that oscillates along a sine wave."""
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y, width=14, height=14)
        self.anims = enemy_anims["fly"]
        self.base_y = float(spawn_y)
        self.patrol_origin_x = float(spawn_x)
        self.patrol_radius = 56.0
        self.fly_speed = 1.15
        self.can_yank_immediately = True

    def update(self, room):
        self.anim_timer += 1
        if self.state == "YANKED":
            return

        if self.state == "STUNNED":
            self.stun_timer -= 1
            self.y += 0.5
            self.rect.y = int(round(self.y))
            if self.stun_timer <= 0:
                self.state = "PATROL"
            return

        self.x += self.dir_x * self.fly_speed
        self.rect.x = int(round(self.x))
        if (abs(self.x - self.patrol_origin_x) > self.patrol_radius or
                room.rect_collides_with_solid(self.rect)):
            self.dir_x *= -1
            self.x += self.dir_x * self.fly_speed * 2

        self.y = self.base_y + math.sin(self.anim_timer * 0.09) * 12.0
        self.rect.topleft = (int(round(self.x)), int(round(self.y)))

    def draw(self, surface, camera_x, camera_y, assets=None):
        sx = int(self.rect.x - 1 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)
        if assets and "cyan" in assets.lights:
            lt = assets.lights["cyan"]
            surface.blit(lt, (sx + 8 - lt.get_width() // 2, sy + 8 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        facing_key = "right" if self.dir_x > 0 else "left"
        frames = self.anims[facing_key]
        sprite = frames[(self.anim_timer // 4) % len(frames)]
        surface.blit(sprite, (sx, sy))


class EmperorMantis(BaseEnemy):
    """
    3-Phase Boss Entity: THE EMPEROR MANTIS!
    - Starts in a dormant state high in the sanctum shadows until Froggy crosses
      the Sanctum threshold (`awakened == True`), triggering a dramatic descent,
      roar SFX, screen tremor, and sinister boss music!
    - Combat Puzzle:
      1. Dodge his figure-8 hover scythe waves and high-speed diagonal dives.
      2. Strike him with the Spore Boomerang (R) to crack open his golden
         thoracic armor (`WEAK_EXPOSED`).
      3. Whip your Tongue (Y) into his glowing magenta core to yank out an
         Energy Pearl (-1 Boss HP, +1 Froggy Heart!).
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y - 80, width=32, height=34)
        self.anims = enemy_anims["mantis"]
        self.is_boss = True
        self.max_hp = BOSS_MAX_HP
        self.hp = BOSS_MAX_HP
        self.home_x = float(spawn_x)
        self.home_y = float(spawn_y)
        self.flight_timer = 0.0
        self.attack_cooldown = 90

        self.awakened = False
        self.intro_timer = 0
        self.state = "DORMANT"
        self.state_timer = 0
        self.dive_vx = 0.0
        self.dive_vy = 0.0
        self.flash_timer = 0

    def awaken(self):
        """Triggers the dramatic boss entrance from the ceiling shadows."""
        if not self.awakened:
            self.awakened = True
            self.state = "INTRO_DESCENT"
            self.intro_timer = 75

    @property
    def phase(self):
        if self.hp >= 5:
            return 1
        elif self.hp >= 3:
            return 2
        return 3

    def hit_by_spore_boomerang(self, room):
        if self.state in ("HOVER", "DIVE_TELEGRAPH", "DIVE_ATTACK"):
            self.state = "WEAK_EXPOSED"
            self.stun_timer = BOSS_WEAK_EXPOSED_FRAMES
            self.vx = 0.0
            self.vy = 1.2
            self.flash_timer = 12
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_SPORE_CYAN, count=20)
            return True
        return False

    def yank_exposed_weak_point(self, room):
        self.hp -= 1
        self.flash_timer = 20
        pearl = BossEnergyPearl(self.center_x, self.center_y)
        room.enemies.append(pearl)
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=26)

        if self.hp <= 0:
            self.alive = False
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=50)
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=40)
        else:
            self.state = "RECOVERING"
            self.state_timer = 45
            fly_count = sum(1 for e in room.enemies if isinstance(e, BuzzFly) and e.alive)
            if self.phase >= 2 and fly_count < 1:
                room.enemies.append(BuzzFly(self.home_x - 90, self.home_y - 20, room.enemy_anims))

        return pearl

    def update(self, room):
        self.anim_timer += 1
        if self.flash_timer > 0:
            self.flash_timer -= 1

        if not self.awakened or self.state == "DORMANT":
            return

        player = room.active_player_ref
        if player is not None:
            self.dir_x = 1 if player.center_x >= self.center_x else -1

        if self.state == "INTRO_DESCENT":
            self.intro_timer -= 1
            self.x += (self.home_x - self.x) * 0.09
            self.y += (self.home_y - self.y) * 0.09
            self.rect.topleft = (int(round(self.x)), int(round(self.y)))
            if self.intro_timer % 6 == 0:
                room.spawn_particle_burst(self.center_x, self.center_y, (255, 70, 120), count=6)
            if self.intro_timer <= 0:
                self.state = "HOVER"
            return

        if self.state == "WEAK_EXPOSED":
            self.stun_timer -= 1
            self.vy = min(self.vy + GRAVITY * 0.65, 4.5)
            self.y += self.vy
            self.rect.y = int(round(self.y))
            for tile in room.solid_tiles:
                if self.rect.colliderect(tile):
                    if self.vy > 0:
                        self.rect.bottom = tile.top
                    self.y = float(self.rect.y)
                    self.vy = 0.0

            if self.stun_timer <= 0:
                self.state = "RECOVERING"
                self.state_timer = 35
            return

        if self.state == "RECOVERING":
            self.state_timer -= 1
            self.x += (self.home_x - self.x) * 0.08
            self.y += (self.home_y - self.y) * 0.08
            self.rect.topleft = (int(round(self.x)), int(round(self.y)))
            if self.state_timer <= 0:
                self.state = "HOVER"
                self.attack_cooldown = 55
            return

        if self.state == "DIVE_TELEGRAPH":
            self.state_timer -= 1
            self.rect.x = int(round(self.x)) + random.randint(-2, 2)
            if self.state_timer <= 0 and player is not None:
                dx = player.center_x - self.center_x
                dy = player.center_y - self.center_y
                dist = max(1.0, math.hypot(dx, dy))
                dive_speed = 6.2 if self.phase == 2 else 7.5
                self.dive_vx = (dx / dist) * dive_speed
                self.dive_vy = (dy / dist) * dive_speed
                self.state = "DIVE_ATTACK"
                self.state_timer = 42
            return

        if self.state == "DIVE_ATTACK":
            self.state_timer -= 1
            self.x += self.dive_vx
            self.y += self.dive_vy
            self.rect.topleft = (int(round(self.x)), int(round(self.y)))
            if room.rect_collides_with_solid(self.rect) or self.state_timer <= 0:
                room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=12)
                self.state = "RECOVERING"
                self.state_timer = 40
            return

        # Figure-8 Hover Pattern
        speed_mult = 1.0 + (self.phase - 1) * 0.38
        self.flight_timer += 0.032 * speed_mult
        target_x = self.home_x + math.sin(self.flight_timer) * 135.0
        target_y = self.home_y + math.sin(self.flight_timer * 2.0) * 38.0
        self.x += (target_x - self.x) * 0.1
        self.y += (target_y - self.y) * 0.1
        self.rect.topleft = (int(round(self.x)), int(round(self.y)))

        self.attack_cooldown -= 1
        if self.attack_cooldown <= 0 and player is not None:
            self._fire_scythe_attack(room, player)
            if self.phase >= 2 and random.random() < 0.55:
                self.state = "DIVE_TELEGRAPH"
                self.state_timer = 32
            self.attack_cooldown = max(42, 95 - (self.phase - 1) * 22)

    def _fire_scythe_attack(self, room, player):
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        base_angle = math.atan2(dy, dx)
        wave_speed = 3.6 if self.phase < 3 else 4.5
        angles = [base_angle] if self.phase < 3 else [base_angle - 0.28, base_angle, base_angle + 0.28]
        for ang in angles:
            vx = math.cos(ang) * wave_speed
            vy = math.sin(ang) * wave_speed
            room.boss_projectiles.append(
                BossScytheWave(self.center_x, self.center_y, vx, vy, enraged=(self.phase == 3))
            )

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.awakened:
            return

        sx = int(self.rect.x - 2 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)
        cx_screen = int(self.center_x - camera_x)
        cy_screen = int(self.center_y - camera_y)

        # Dynamic additive boss aura glow
        if assets:
            l_key = "magenta" if self.state == "WEAK_EXPOSED" else ("crimson" if self.phase >= 2 else "gold")
            lt = assets.lights.get(l_key)
            if lt:
                surface.blit(lt, (cx_screen - lt.get_width() // 2, cy_screen - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        if self.state == "WEAK_EXPOSED":
            key = "exposed_right" if self.dir_x > 0 else "exposed_left"
        else:
            key = "armored_right" if self.dir_x > 0 else "armored_left"
        sprite = self.anims[key]

        if self.phase == 3 or self.state in ("DIVE_TELEGRAPH", "INTRO_DESCENT"):
            aura_col = (255, 60, 90) if (self.anim_timer // 3) % 2 == 0 else COLOR_BOSS_GOLD
            pygame.draw.circle(surface, aura_col, (cx_screen, cy_screen), 22, 1)

        surface.blit(sprite, (sx, sy))

        if self.state == "WEAK_EXPOSED":
            pulse_r = 6 + int(math.sin(self.anim_timer * 0.35) * 2)
            pygame.draw.circle(surface, COLOR_BOSS_CORE, (cx_screen, cy_screen - 2), pulse_r, 1)
            for i in range(3):
                ang = self.anim_timer * 0.16 + i * (math.tau / 3.0)
                star_x = cx_screen + int(math.cos(ang) * 14)
                star_y = int(self.rect.top - 5 - camera_y + math.sin(ang) * 3)
                pygame.draw.circle(surface, COLOR_BOSS_GOLD, (star_x, star_y), 2)


# =============================================================================
# CHAPTER 8. ASCII TILEMAP ROOM PARSER, AUTO-TILER & LUSH DECORATOR
# =============================================================================

class DoorPortal:
    def __init__(self, door_id, rect, target_room, target_door, spawn_offset_x, spawn_offset_y):
        self.door_id = door_id
        self.rect = rect
        self.target_room = target_room
        self.target_door = target_door
        self.spawn_offset_x = spawn_offset_x
        self.spawn_offset_y = spawn_offset_y


class TileMapRoom:
    def __init__(self, room_id, blueprint, assets, enemy_anims):
        self.room_id = room_id
        self.title = blueprint["title"]
        self.theme = blueprint.get("theme", "canopy")
        self.bg_color = blueprint["bg_color"]
        self.map_coords = blueprint["map_coords"]
        self.boss_trigger_x = blueprint.get("boss_trigger_x", None)
        self.door_configs = blueprint.get("doors", {})
        self.assets = assets
        self.enemy_anims = enemy_anims

        raw_lines = blueprint["ascii_grid"]
        self.rows = len(raw_lines)
        self.cols = max(len(line) for line in raw_lines)
        self.grid = [list(line.ljust(self.cols, '.')) for line in raw_lines]

        self.world_width = self.cols * TILE_SIZE
        self.world_height = self.rows * TILE_SIZE

        self.solid_tiles = []
        self.autotiled_bricks = []   # List of (world_x, world_y, tile_surface)
        self.water_hazards = []      # List of pygame.Rect for glowing swamp pits
        self.grapple_nodes = []
        self.door_tiles = []         # List of (world_x, world_y, is_boss_door)
        self.doors = {}
        self.enemy_spawns = []
        self.enemies = []
        self.boss_projectiles = []
        self.particles = []

        # Lush Ambiance Collections (Auto-populated from terrain geometry!)
        self.props_list = []         # List of (kind, world_x, world_y)
        self.hanging_vines = []      # List of HangingVine physics chains
        self.fireflies = []          # List of FireflySpore glowing particles

        self.default_spawn = (64, 64)
        self.active_player_ref = None
        self.boss_defeated_banner_timer = 0
        self.boss_awakening_banner_timer = 0
        self.screen_shake_timer = 0
        self.sinister_ambience_active = (self.theme == "sanctum")

        self.rebuild_geometry(respawn_enemies=True)

    def _is_solid_cell(self, r, c):
        """Returns True if (r, c) is a solid '#' tile (or outside map bounds)."""
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return True
        return self.grid[r][c] == '#'

    def rebuild_geometry(self, respawn_enemies=True):
        self.solid_tiles.clear()
        self.autotiled_bricks.clear()
        self.water_hazards.clear()
        self.grapple_nodes.clear()
        self.door_tiles.clear()
        self.doors.clear()
        self.enemy_spawns.clear()
        self.props_list.clear()
        self.hanging_vines.clear()

        door_bounds = {}
        rng = random.Random(hash(self.room_id) & 0xFFFFFFFF)

        for row in range(self.rows):
            col = 0
            while col < self.cols:
                char = self.grid[row][col]
                world_x = col * TILE_SIZE
                world_y = row * TILE_SIZE

                if char == '#':
                    start_col = col
                    while col < self.cols and self.grid[row][col] == '#':
                        wx = col * TILE_SIZE
                        # Compute 4-Bit Neighbor Bitmask (N=1, E=2, S=4, W=8)
                        mask = 0
                        if self._is_solid_cell(row - 1, col): mask |= 1
                        if self._is_solid_cell(row, col + 1): mask |= 2
                        if self._is_solid_cell(row + 1, col): mask |= 4
                        if self._is_solid_cell(row, col - 1): mask |= 8

                        # Use Sanctum tiles on the boss side of Level 1 or in Boss Sanctum
                        is_sanctum_zone = (self.theme == "sanctum") or (
                            self.boss_trigger_x is not None and wx >= self.boss_trigger_x - 64
                        )
                        t_set = self.assets.autotiles["sanctum" if is_sanctum_zone else "jungle"]
                        if mask == 15 and ((row * 7 + col * 13) % 5 == 0):
                            tex = t_set["15_alt"]
                        else:
                            tex = t_set[mask]
                        self.autotiled_bricks.append((wx, world_y, tex))

                        # Auto-Plant Lush Foliage on exposed top mossy surfaces (when North is air)
                        if row > 1 and self.grid[row - 1][col] == '.':
                            roll = rng.random()
                            if roll < 0.22:
                                self.props_list.append(("grass", wx, world_y - 8))
                            elif roll < 0.34:
                                self.props_list.append(("fern", wx, world_y - 15))
                            elif roll < 0.41:
                                shroom_kind = rng.choice(["shroom_cyan", "shroom_magenta", "shroom_gold"])
                                self.props_list.append((shroom_kind, wx, world_y - 16))
                            elif (
                                roll < 0.44 and not is_sanctum_zone and
                                col + 1 < self.cols and self.grid[row][col + 1] == '#' and
                                self.grid[row - 1][col + 1] == '.'
                            ):
                                self.props_list.append(("frog_statue", wx, world_y - 32))

                        # Auto-Hang Physics Vines from exposed ceiling undersides (when South is air)
                        if row > 0 and row + 2 < self.rows and self.grid[row + 1][col] == '.' and self.grid[row + 2][col] == '.':
                            if rng.random() < 0.14:
                                segs = rng.randint(5, 9)
                                self.hanging_vines.append(
                                    HangingVine(wx + 8, world_y + 15, num_segments=segs, sinister=is_sanctum_zone)
                                )

                        col += 1

                    merged_width = (col - start_col) * TILE_SIZE
                    self.solid_tiles.append(
                        pygame.Rect(start_col * TILE_SIZE, world_y, merged_width, TILE_SIZE)
                    )
                    continue

                elif char == '~':
                    self.water_hazards.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                elif char == 'G':
                    self.grapple_nodes.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                elif char == 'S':
                    self.default_spawn = (world_x, world_y)

                elif char == 'T':
                    self.props_list.append(("mantis_totem", world_x - 4, world_y - 16))

                elif char in ('E', 'F', 'M'):
                    self.enemy_spawns.append((char, world_x, world_y))

                matched_door = None
                for d_id in self.door_configs:
                    if self.grid[row][col] == d_id[0]:
                        matched_door = d_id
                        break

                if matched_door:
                    tile_rect = pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE)
                    cfg = self.door_configs.get(matched_door, {})
                    is_boss_d = (cfg.get("target_room") == "boss_sanctum") or (self.theme == "sanctum")
                    self.door_tiles.append((world_x, world_y, is_boss_d))
                    if matched_door not in door_bounds:
                        door_bounds[matched_door] = tile_rect
                    else:
                        door_bounds[matched_door] = door_bounds[matched_door].union(tile_rect)

                col += 1

        for door_char, union_rect in door_bounds.items():
            cfg = self.door_configs.get(door_char)
            if cfg:
                self.doors[door_char] = DoorPortal(
                    door_id=door_char,
                    rect=union_rect,
                    target_room=cfg["target_room"],
                    target_door=cfg["target_door"],
                    spawn_offset_x=cfg["spawn_offset_x"],
                    spawn_offset_y=cfg["spawn_offset_y"],
                )

        # Populate floating bioluminescent fireflies / spores across the room
        num_fireflies = max(18, int((self.world_width * self.world_height) / 14000))
        self.fireflies = [
            FireflySpore(self.world_width, self.world_height, sinister=(self.theme == "sanctum"))
            for _ in range(num_fireflies)
        ]

        if respawn_enemies:
            self.spawn_enemies()

    def spawn_enemies(self):
        self.enemies.clear()
        self.boss_projectiles.clear()
        self.particles.clear()
        self.sinister_ambience_active = (self.theme == "sanctum")
        for char, wx, wy in self.enemy_spawns:
            if char == 'E':
                self.enemies.append(MossBeetle(wx, wy, self.enemy_anims))
            elif char == 'F':
                self.enemies.append(BuzzFly(wx, wy, self.enemy_anims))
            elif char == 'M':
                boss = EmperorMantis(wx, wy, self.enemy_anims)
                if self.theme == "sanctum":
                    boss.awaken()
                self.enemies.append(boss)

    def get_active_boss(self):
        for enemy in self.enemies:
            if enemy.alive and enemy.is_boss:
                return enemy
        return None

    def spawn_particle_burst(self, x, y, color, count=12):
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1.0, 3.8)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 1.0
            self.particles.append(Particle(x, y, vx, vy, color, random.randint(14, 26)))

    def update_entities(self, player, audio=None, pulse_timer=0):
        self.active_player_ref = player
        boss = self.get_active_boss()
        had_awakened_boss = (boss is not None and boss.awakened)

        # Check if Froggy just crossed the Boss Awakening threshold!
        if boss is not None and not boss.awakened:
            trigger_x = self.boss_trigger_x if self.boss_trigger_x is not None else (boss.home_x - 220)
            if player.center_x >= trigger_x:
                boss.awaken()
                self.sinister_ambience_active = True
                self.boss_awakening_banner_timer = 190
                self.screen_shake_timer = 45
                if audio:
                    audio.play_sfx("boss_roar")
                    audio.play_music("boss")

        for enemy in self.enemies:
            if enemy.alive:
                enemy.update(self)
        self.enemies = [e for e in self.enemies if e.alive]

        # If the awakened Emperor Mantis was just defeated, restore triumphant groove!
        if had_awakened_boss and self.get_active_boss() is None:
            self.boss_defeated_banner_timer = 260
            self.sinister_ambience_active = False
            if audio:
                audio.play_sfx("select")
                audio.play_music("level")

        if self.boss_defeated_banner_timer > 0:
            self.boss_defeated_banner_timer -= 1
        if self.boss_awakening_banner_timer > 0:
            self.boss_awakening_banner_timer -= 1
        if self.screen_shake_timer > 0:
            self.screen_shake_timer -= 1

        for wave in self.boss_projectiles:
            wave.update(self)
        self.boss_projectiles = [w for w in self.boss_projectiles if w.alive]

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.age < p.lifetime]

        for vine in self.hanging_vines:
            vine.update(player, pulse_timer)
        for ff in self.fireflies:
            ff.update(pulse_timer)

    def paint_tile_at_world_pos(self, world_x, world_y, new_char):
        col = int(world_x // TILE_SIZE)
        row = int(world_y // TILE_SIZE)
        if 0 <= row < self.rows and 0 <= col < self.cols:
            if self.grid[row][col] in self.door_configs:
                return
            if self.grid[row][col] != new_char:
                self.grid[row][col] = new_char
                self.rebuild_geometry(respawn_enemies=True)

    def export_ascii_to_console(self):
        print("\n" + "=" * 68)
        print(f"EXPORTED ASCII LEVEL FOR ROOM: '{self.room_id}' ({self.title})")
        print("=" * 68)
        print('"ascii_grid": [')
        for row_chars in self.grid:
            print(f'    "{"".join(row_chars)}",')
        print("],")
        print("=" * 68 + "\n")

    def get_grapple_node_at(self, x, y):
        for node in self.grapple_nodes:
            if node.inflate(10, 10).collidepoint(x, y):
                return node
        return None

    def get_enemy_at_point(self, x, y):
        for enemy in self.enemies:
            if enemy.alive and not enemy.is_boss and enemy.rect.inflate(8, 8).collidepoint(x, y):
                return enemy
        return None

    def is_point_inside_solid(self, x, y):
        for tile in self.solid_tiles:
            if tile.collidepoint(x, y):
                return True
        return False

    def rect_collides_with_solid(self, rect):
        for tile in self.solid_tiles:
            if rect.colliderect(tile):
                return True
        return False

    def get_touched_door(self, player_rect):
        for door in self.doors.values():
            if door.rect.colliderect(player_rect):
                return door
        return None

    def draw(self, surface, camera_x, camera_y, pulse_timer):
        # 1. MULTI-LAYER PARALLAX BACKGROUND RENDERING
        # If the boss has awakened in Level 1, blend/cross-switch to the sinister Sanctum backdrop!
        active_theme = "sanctum" if self.sinister_ambience_active else self.theme
        bg_surf = self.assets.backgrounds.get(active_theme)
        if bg_surf is not None:
            # Slow 0.15x horizontal parallax scroll with seamless tiling
            bg_w = bg_surf.get_width()
            bg_offset_x = int(camera_x * 0.15) % bg_w
            surface.blit(bg_surf, (-bg_offset_x, 0))
            if bg_offset_x > 0:
                surface.blit(bg_surf, (bg_w - bg_offset_x, 0))
        else:
            surface.fill(self.bg_color)

        # Midground Silhouette Parallax Layer (0.38x scroll speed)
        mid_surf = self.assets.parallax_mid.get(active_theme)
        if mid_surf is not None:
            mw = mid_surf.get_width()
            mid_offset_x = int(camera_x * 0.38) % mw
            surface.blit(mid_surf, (-mid_offset_x, 0))
            if mid_offset_x > 0:
                surface.blit(mid_surf, (mw - mid_offset_x, 0))

        # 2. HANGING JUNGLE VINES (Behind terrain edges)
        for vine in self.hanging_vines:
            vine.draw(surface, camera_x, camera_y)

        # 3. ENVIRONMENTAL STORYTELLING PROPS & SWAYING FOLIAGE
        fern_frames = self.assets.props["fern"]
        grass_frames = self.assets.props["grass"]
        for kind, px, py in self.props_list:
            sx = int(px - camera_x)
            sy = int(py - camera_y)
            if -32 <= sx <= INTERNAL_WIDTH + 32 and -32 <= sy <= INTERNAL_HEIGHT + 32:
                if kind == "fern":
                    f_idx = ((pulse_timer // 18) + (px // 16)) % 3
                    surface.blit(fern_frames[f_idx], (sx, sy))
                elif kind == "grass":
                    g_idx = (px // 16) % 2
                    surface.blit(grass_frames[g_idx], (sx, sy))
                elif kind.startswith("shroom_"):
                    shroom_tex = self.assets.props.get(kind)
                    if shroom_tex:
                        surface.blit(shroom_tex, (sx, sy))
                        l_col = "cyan" if "cyan" in kind else ("magenta" if "magenta" in kind else "gold")
                        lt = self.assets.lights.get(l_col)
                        if lt:
                            surface.blit(lt, (sx + 8 - lt.get_width() // 2, sy + 8 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
                else:
                    prop_tex = self.assets.props.get(kind)
                    if prop_tex:
                        surface.blit(prop_tex, (sx, sy))
                        if kind == "mantis_totem":
                            lt = self.assets.lights.get("crimson")
                            if lt:
                                surface.blit(lt, (sx + 12 - lt.get_width() // 2, sy + 8 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        # 4. 4-BIT AUTO-TILED TERRAIN BLOCKS
        for bx, by, tex in self.autotiled_bricks:
            sx = int(bx - camera_x)
            sy = int(by - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                surface.blit(tex, (sx, sy))

        # 5. ANIMATED BIOLUMINESCENT SWAMP WATER
        water_tex = self.assets.special_tiles["water"][(pulse_timer // 8) % 4]
        for w_rect in self.water_hazards:
            sx = int(w_rect.x - camera_x)
            sy = int(w_rect.y - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                surface.blit(water_tex, (sx, sy))

        # 6. GOLDEN FROG GRAPPLE IDOLS (With Additive Gold Glow)
        grapple_tex = self.assets.special_tiles["grapple"][(pulse_timer // 16) % 2]
        gold_light = self.assets.lights.get("gold")
        for node in self.grapple_nodes:
            sx = int(node.x - camera_x)
            sy = int(node.y - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                if gold_light:
                    surface.blit(gold_light, (sx + 8 - gold_light.get_width() // 2, sy + 8 - gold_light.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
                surface.blit(grapple_tex, (sx, sy))

        # 7. ANIMATED RUNE PORTAL DOORS
        door_frame = (pulse_timer // 6) % 4
        for dx, dy, is_boss_d in self.door_tiles:
            sx = int(dx - camera_x)
            sy = int(dy - camera_y)
            d_tex = self.assets.special_tiles["boss_door" if is_boss_d else "door"][door_frame]
            surface.blit(d_tex, (sx, sy))

        glow_radius = int(2 + math.sin(pulse_timer * 0.12) * 2)
        for door in self.doors.values():
            screen_door = door.rect.move(-int(camera_x), -int(camera_y))
            pygame.draw.rect(surface, COLOR_DOOR_GLOW, screen_door.inflate(glow_radius, glow_radius), 1)

        # 8. ENEMIES, BOSS & PROJECTILES
        for enemy in self.enemies:
            if enemy.alive:
                enemy.draw(surface, camera_x, camera_y, self.assets)

        for wave in self.boss_projectiles:
            wave.draw(surface, camera_x, camera_y, self.assets)

        for p in self.particles:
            p.draw(surface, camera_x, camera_y)

        # 9. FLOATING BIOLUMINESCENT FIREFLIES & SPORES (Foreground Ambiance)
        for ff in self.fireflies:
            ff.draw(surface, camera_x, camera_y, self.assets, pulse_timer)


# =============================================================================
# CHAPTER 9. METROIDVANIA WORLD MANAGER
# =============================================================================

class WorldManager:
    def __init__(self, blueprints, assets, enemy_anims, starting_room_id):
        self.assets = assets
        self.rooms = {}
        for room_id, bp in blueprints.items():
            self.rooms[room_id] = TileMapRoom(room_id, bp, assets, enemy_anims)
        self.current_room = self.rooms[starting_room_id]
        self.visited_rooms = {starting_room_id}
        self.transition_state = "NONE"
        self.fade_alpha = 0
        self.pending_door = None
        self.fade_surface = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
        self.fade_surface.fill((0, 0, 0))

    @property
    def is_transitioning(self):
        return self.transition_state != "NONE"

    def trigger_door_transition(self, door_portal, audio=None):
        if self.transition_state == "NONE":
            self.pending_door = door_portal
            self.transition_state = "FADING_OUT"
            if audio:
                audio.play_sfx("door")

    def warp_directly_to_room(self, room_id, player, camera, audio=None):
        if room_id in self.rooms:
            self.current_room = self.rooms[room_id]
            self.visited_rooms.add(room_id)
            self.current_room.spawn_enemies()
            spawn_x, spawn_y = self.current_room.default_spawn
            player.teleport_to_room(spawn_x, spawn_y)
            camera.set_bounds(self.current_room.world_width, self.current_room.world_height)
            camera.snap_to(player)
            if audio:
                if room_id == "boss_sanctum":
                    self.current_room.boss_awakening_banner_timer = 180
                    self.current_room.screen_shake_timer = 40
                    audio.play_sfx("boss_roar")
                    audio.play_music("boss")
                else:
                    audio.play_music("level")

    def update_transition(self, player, camera, audio=None):
        if self.transition_state == "FADING_OUT":
            self.fade_alpha += TRANSITION_FADE_SPEED
            if self.fade_alpha >= 255:
                self.fade_alpha = 255
                self._execute_room_swap(player, camera, audio)
                self.transition_state = "FADING_IN"
        elif self.transition_state == "FADING_IN":
            self.fade_alpha -= TRANSITION_FADE_SPEED
            if self.fade_alpha <= 0:
                self.fade_alpha = 0
                self.transition_state = "NONE"

    def _execute_room_swap(self, player, camera, audio=None):
        target_room_id = self.pending_door.target_room
        target_door_id = self.pending_door.target_door
        offset_x = self.pending_door.spawn_offset_x
        offset_y = self.pending_door.spawn_offset_y

        self.current_room = self.rooms[target_room_id]
        self.visited_rooms.add(target_room_id)
        self.current_room.spawn_enemies()

        dest_door = self.current_room.doors.get(target_door_id)
        if dest_door is not None:
            spawn_x = dest_door.rect.centerx + offset_x - (player.width * 0.5)
            spawn_y = dest_door.rect.bottom - player.height + offset_y
        else:
            spawn_x, spawn_y = self.current_room.default_spawn

        player.teleport_to_room(spawn_x, spawn_y, facing_right=(offset_x >= 0))
        camera.set_bounds(self.current_room.world_width, self.current_room.world_height)
        camera.snap_to(player)

        if audio:
            if target_room_id == "boss_sanctum":
                self.current_room.boss_awakening_banner_timer = 180
                self.current_room.screen_shake_timer = 40
                audio.play_sfx("boss_roar")
                audio.play_music("boss")
            else:
                audio.play_music("level")

    def draw_fade_overlay(self, surface):
        if self.fade_alpha > 0:
            self.fade_surface.set_alpha(self.fade_alpha)
            surface.blit(self.fade_surface, (0, 0))


# =============================================================================
# CHAPTER 10. SNES CONTROLLER ABSTRACTION LAYER
# =============================================================================

class SNESController:
    def __init__(self):
        pygame.joystick.init()
        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"[SNES Controller] Connected Gamepad: {self.joystick.get_name()}")
        else:
            print("[SNES Controller] No Gamepad detected. Using Keyboard SNES fallback mapping.")

        self.held = {
            "UP": False, "DOWN": False, "LEFT": False, "RIGHT": False,
            "A": False, "B": False, "X": False, "Y": False,
            "L": False, "R": False, "START": False, "SELECT": False
        }
        self.prev_held = self.held.copy()
        self.just_pressed = {k: False for k in self.held}
        self.just_released = {k: False for k in self.held}

    def update(self):
        self.prev_held = self.held.copy()
        keys = pygame.key.get_pressed()

        self.held["LEFT"] = keys[pygame.K_LEFT] or keys[pygame.K_a]
        self.held["RIGHT"] = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        self.held["UP"] = keys[pygame.K_UP] or keys[pygame.K_w]
        self.held["DOWN"] = keys[pygame.K_DOWN] or keys[pygame.K_s]

        self.held["A"] = keys[pygame.K_SPACE] or keys[pygame.K_k] or keys[pygame.K_RETURN]
        self.held["B"] = keys[pygame.K_z]
        self.held["Y"] = keys[pygame.K_x] or keys[pygame.K_j]
        self.held["R"] = keys[pygame.K_c] or keys[pygame.K_u] or keys[pygame.K_LSHIFT]

        if self.joystick:
            if self.joystick.get_numaxes() >= 2:
                axis_x = self.joystick.get_axis(0)
                axis_y = self.joystick.get_axis(1)
                if axis_x < -0.35: self.held["LEFT"] = True
                if axis_x > 0.35: self.held["RIGHT"] = True
                if axis_y < -0.35: self.held["UP"] = True
                if axis_y > 0.35: self.held["DOWN"] = True

            if self.joystick.get_numhats() > 0:
                hat_x, hat_y = self.joystick.get_hat(0)
                if hat_x < 0: self.held["LEFT"] = True
                if hat_x > 0: self.held["RIGHT"] = True
                if hat_y > 0: self.held["UP"] = True
                if hat_y < 0: self.held["DOWN"] = True

            num_btns = self.joystick.get_numbuttons()
            if num_btns > 0 and self.joystick.get_button(0): self.held["B"] = True
            if num_btns > 1 and self.joystick.get_button(1): self.held["A"] = True
            if num_btns > 2 and self.joystick.get_button(2): self.held["Y"] = True
            if num_btns > 5 and self.joystick.get_button(5): self.held["R"] = True

        for btn in self.held:
            self.just_pressed[btn] = self.held[btn] and not self.prev_held[btn]
            self.just_released[btn] = not self.held[btn] and self.prev_held[btn]

    @property
    def jump_held(self):
        return self.held["A"] or self.held["B"]

    @property
    def jump_just_pressed(self):
        return self.just_pressed["A"] or self.just_pressed["B"]

    @property
    def jump_just_released(self):
        return (self.just_released["A"] or self.just_released["B"]) and not self.jump_held

    def get_dpad_vector(self, default_facing_right=True):
        dx = (1 if self.held["RIGHT"] else 0) - (1 if self.held["LEFT"] else 0)
        dy = (1 if self.held["DOWN"] else 0) - (1 if self.held["UP"] else 0)
        if dx == 0 and dy == 0:
            ux = 1.0 if default_facing_right else -1.0
            uy = 0.0
        else:
            length = math.hypot(dx, dy)
            ux = dx / length
            uy = dy / length
        return (dx, dy), (ux, uy)


# =============================================================================
# CHAPTER 11. FROGGY PLAYER ENTITY (AABB PHYSICS & PENDULUM GRAPPLE)
# =============================================================================

class FroggyPlayer:
    def __init__(self, spawn_x, spawn_y, animations):
        self.x = float(spawn_x)
        self.y = float(spawn_y)
        self.width = 14
        self.height = 15
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)

        self.vx = 0.0
        self.vy = 0.0
        self.facing_right = True

        self.hp = PLAYER_MAX_HP
        self.invuln_timer = 0
        self.eaten_count = 0

        self.on_ground = False
        self.touching_wall_dir = 0
        self.coyote_timer = 0
        self.jump_buffer_timer = 0
        self.wall_jump_lock_timer = 0
        self.double_jump_available = True
        self.door_cooldown = 0

        self.tongue_state = "INACTIVE"
        self.tongue_dir_x = 1.0
        self.tongue_dir_y = 0.0
        self.tongue_length = 0.0
        self.tongue_hold_timer = 0
        self.grapple_anchor = pygame.Vector2(0, 0)
        self.yanked_enemy = None

        self.swing_angle = 0.0
        self.swing_angular_vel = 0.0
        self.swing_rope_length = 60.0

        self.projectiles = []
        self.animations = animations
        self.anim_state = "idle"
        self.anim_timer = 0

    @property
    def center_x(self):
        return self.x + self.width * 0.5

    @property
    def center_y(self):
        return self.y + self.height * 0.5

    def teleport_to_room(self, spawn_x, spawn_y, facing_right=True):
        self.x = float(spawn_x)
        self.y = float(spawn_y)
        self.rect.topleft = (int(self.x), int(self.y))
        self.vx = 0.0
        self.vy = 0.0
        self.facing_right = facing_right
        self.tongue_state = "INACTIVE"
        self.tongue_length = 0.0
        self.yanked_enemy = None
        self.projectiles.clear()
        self.double_jump_available = True
        self.door_cooldown = DOOR_COOLDOWN_FRAMES

    def update(self, controller, room, world_manager, audio=None):
        if self.door_cooldown > 0:
            self.door_cooldown -= 1
        if self.invuln_timer > 0:
            self.invuln_timer -= 1

        if controller.just_pressed["R"] and len(self.projectiles) < 2:
            _, (ux, uy) = controller.get_dpad_vector(self.facing_right)
            self.projectiles.append(SporeBoomerang(self.center_x, self.center_y, ux, uy))
            if audio:
                audio.play_sfx("spore")

        for proj in self.projectiles:
            proj.update(room, audio)
        self.projectiles = [p for p in self.projectiles if p.alive]

        if self.tongue_state == "SWINGING":
            self._update_pendulum_swing(controller, room, audio)
        else:
            self._update_tongue_strike_and_yank(controller, room, audio)
            self._update_standard_physics(controller, room, audio)

        self._check_damage_collisions(room, audio)
        self._update_animation_state()

        if self.door_cooldown == 0:
            touched_door = room.get_touched_door(self.rect)
            if touched_door is not None:
                world_manager.trigger_door_transition(touched_door, audio)

    def _update_tongue_strike_and_yank(self, controller, room, audio=None):
        if controller.just_pressed["Y"] and self.tongue_state == "INACTIVE":
            (dx, _), (ux, uy) = controller.get_dpad_vector(self.facing_right)
            if dx != 0:
                self.facing_right = (dx > 0)
            self.tongue_dir_x = ux
            self.tongue_dir_y = uy
            self.tongue_length = 4.0
            self.yanked_enemy = None
            self.tongue_state = "EXTENDING"
            if audio:
                audio.play_sfx("tongue")

        if self.tongue_state == "EXTENDING":
            self.tongue_length += TONGUE_EXTEND_SPEED
            tip_x = self.center_x + self.tongue_dir_x * self.tongue_length
            tip_y = self.center_y + self.tongue_dir_y * self.tongue_length

            boss = room.get_active_boss()
            if boss and boss.alive and boss.awakened and boss.rect.inflate(10, 10).collidepoint(tip_x, tip_y):
                if boss.state == "WEAK_EXPOSED":
                    pearl = boss.yank_exposed_weak_point(room)
                    self.yanked_enemy = pearl
                    self.tongue_state = "RETRACTING"
                    if audio:
                        audio.play_sfx("boss_hit")
                    return
                else:
                    room.spawn_particle_burst(tip_x, tip_y, (220, 220, 240), count=8)
                    self.tongue_state = "HOLDING"
                    self.tongue_hold_timer = 4
                    if audio:
                        audio.play_sfx("latch")
                    return

            hit_enemy = room.get_enemy_at_point(tip_x, tip_y)
            if hit_enemy is not None:
                if hit_enemy.can_yank_immediately or hit_enemy.state == "STUNNED":
                    hit_enemy.state = "YANKED"
                    self.yanked_enemy = hit_enemy
                    self.tongue_state = "RETRACTING"
                    room.spawn_particle_burst(tip_x, tip_y, COLOR_TONGUE_TIP, count=8)
                    if audio:
                        audio.play_sfx("latch")
                else:
                    hit_enemy.stun(knockback_dir_x=self.tongue_dir_x)
                    self.tongue_state = "RETRACTING"
                    room.spawn_particle_burst(tip_x, tip_y, (255, 230, 90), count=12)
                    if audio:
                        audio.play_sfx("stun")
                return

            hit_anchor = room.get_grapple_node_at(tip_x, tip_y)
            if hit_anchor is not None:
                self._attach_to_grapple(hit_anchor)
                if audio:
                    audio.play_sfx("latch")
                return

            if room.is_point_inside_solid(tip_x, tip_y):
                self.tongue_state = "HOLDING"
                self.tongue_hold_timer = TONGUE_HOLD_FRAMES // 2
                return

            if self.tongue_length >= TONGUE_MAX_LENGTH:
                self.tongue_length = TONGUE_MAX_LENGTH
                self.tongue_state = "HOLDING"
                self.tongue_hold_timer = TONGUE_HOLD_FRAMES

        elif self.tongue_state == "HOLDING":
            self.tongue_hold_timer -= 1
            if self.tongue_hold_timer <= 0:
                self.tongue_state = "RETRACTING"

        elif self.tongue_state == "RETRACTING":
            self.tongue_length -= TONGUE_RETRACT_SPEED
            tip_x = self.center_x + self.tongue_dir_x * max(0.0, self.tongue_length)
            tip_y = self.center_y + self.tongue_dir_y * max(0.0, self.tongue_length)

            if self.yanked_enemy is not None and self.yanked_enemy.alive:
                self.yanked_enemy.set_center(tip_x, tip_y)

            if self.tongue_length <= 14.0:
                self._swallow_yanked_enemy(room, audio)

            if self.tongue_length <= 0.0:
                self.tongue_length = 0.0
                self.yanked_enemy = None
                self.tongue_state = "INACTIVE"

    def _swallow_yanked_enemy(self, room, audio=None):
        if self.yanked_enemy is not None:
            self.yanked_enemy.alive = False
            self.yanked_enemy = None
            self.eaten_count += 1
            self.hp = min(PLAYER_MAX_HP, self.hp + 1)
            self.double_jump_available = True
            if not self.on_ground and self.vy > -2.5:
                self.vy = -3.6
            room.spawn_particle_burst(self.center_x, self.center_y, (130, 255, 120), count=16)
            if audio:
                audio.play_sfx("eat")

    def _check_damage_collisions(self, room, audio=None):
        # Check glowing swamp water hazard pits (bounces Froggy up out of the swamp!)
        for w_rect in room.water_hazards:
            if self.rect.colliderect(w_rect):
                self.vy = -8.2
                self.double_jump_available = True
                if self.invuln_timer == 0:
                    self._take_damage(push_from_x=self.center_x, room=room, audio=audio)
                    self.vy = -8.2
                return

        if self.invuln_timer > 0:
            return

        for enemy in room.enemies:
            if not enemy.is_boss and enemy.alive and enemy.state == "PATROL" and self.rect.colliderect(enemy.rect):
                self._take_damage(push_from_x=enemy.center_x, room=room, audio=audio)
                return

        boss = room.get_active_boss()
        if (
            boss and boss.alive and boss.awakened and
            boss.state not in ("WEAK_EXPOSED", "DORMANT", "INTRO_DESCENT") and
            self.rect.colliderect(boss.rect)
        ):
            self._take_damage(push_from_x=boss.center_x, room=room, audio=audio)
            return

        for wave in room.boss_projectiles:
            if wave.alive and self.rect.colliderect(wave.rect):
                wave.alive = False
                self._take_damage(push_from_x=wave.x, room=room, audio=audio)
                return

    def _take_damage(self, push_from_x, room, audio=None):
        self.hp -= 1
        self.invuln_timer = PLAYER_INVULN_FRAMES
        push_dir = -1.0 if self.center_x < push_from_x else 1.0
        self.vx = push_dir * 3.8
        self.vy = -4.8
        self.wall_jump_lock_timer = 10
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_HEART_RED, count=12)
        if audio:
            audio.play_sfx("hurt")

    def _attach_to_grapple(self, anchor_rect):
        self.grapple_anchor = pygame.Vector2(anchor_rect.centerx, anchor_rect.centery)
        rel_x = self.center_x - self.grapple_anchor.x
        rel_y = self.center_y - self.grapple_anchor.y
        self.swing_rope_length = max(SWING_MIN_LENGTH, math.hypot(rel_x, rel_y))
        self.swing_angle = math.atan2(rel_x, rel_y)

        tangent_x = math.cos(self.swing_angle)
        tangent_y = -math.sin(self.swing_angle)
        tangential_speed = self.vx * tangent_x + self.vy * tangent_y
        self.swing_angular_vel = tangential_speed / self.swing_rope_length

        self.double_jump_available = True
        self.on_ground = False
        self.tongue_state = "SWINGING"

    def _update_pendulum_swing(self, controller, room, audio=None):
        (dx, dy), _ = controller.get_dpad_vector(self.facing_right)

        if dy != 0:
            self.swing_rope_length += dy * SWING_REEL_SPEED
            self.swing_rope_length = max(SWING_MIN_LENGTH, min(TONGUE_MAX_LENGTH, self.swing_rope_length))

        gravity_torque = -SWING_GRAVITY * math.sin(self.swing_angle)
        player_pump = dx * SWING_PUMP_FORCE
        self.swing_angular_vel += (gravity_torque + player_pump)
        self.swing_angular_vel *= SWING_DAMPING

        next_angle = self.swing_angle + self.swing_angular_vel
        target_cx = self.grapple_anchor.x + math.sin(next_angle) * self.swing_rope_length
        target_cy = self.grapple_anchor.y + math.cos(next_angle) * self.swing_rope_length

        test_rect = pygame.Rect(
            int(target_cx - self.width * 0.5),
            int(target_cy - self.height * 0.5),
            self.width, self.height
        )

        if room.rect_collides_with_solid(test_rect):
            self.swing_angular_vel *= -0.35
        else:
            self.swing_angle = next_angle
            self.x = target_cx - self.width * 0.5
            self.y = target_cy - self.height * 0.5
            self.rect.topleft = (int(self.x), int(self.y))

        tangent_x = math.cos(self.swing_angle)
        tangent_y = -math.sin(self.swing_angle)
        linear_speed = self.swing_angular_vel * self.swing_rope_length
        self.vx = linear_speed * tangent_x
        self.vy = linear_speed * tangent_y

        if dx != 0:
            self.facing_right = (dx > 0)

        if controller.jump_just_pressed:
            self.tongue_state = "RETRACTING"
            self.tongue_length = self.swing_rope_length
            self.vy = min(self.vy - 3.2, JUMP_VELOCITY * 0.85)
            self.vx *= 1.15
            if audio:
                audio.play_sfx("jump")
        elif controller.just_pressed["Y"]:
            self.tongue_state = "RETRACTING"
            self.tongue_length = self.swing_rope_length

    def _update_standard_physics(self, controller, room, audio=None):
        (dx, _), _ = controller.get_dpad_vector(self.facing_right)

        if self.coyote_timer > 0: self.coyote_timer -= 1
        if self.jump_buffer_timer > 0: self.jump_buffer_timer -= 1
        if self.wall_jump_lock_timer > 0: self.wall_jump_lock_timer -= 1

        if controller.jump_just_pressed:
            self.jump_buffer_timer = JUMP_BUFFER_FRAMES

        if self.wall_jump_lock_timer == 0:
            if dx != 0:
                accel = MOVE_ACCEL if self.on_ground else AIR_ACCEL
                self.vx += dx * accel
                self.vx = max(-MAX_RUN_SPEED, min(MAX_RUN_SPEED, self.vx))
                if self.tongue_state == "INACTIVE":
                    self.facing_right = (dx > 0)
            else:
                friction = GROUND_FRICTION if self.on_ground else AIR_DRAG
                self.vx *= friction
                if abs(self.vx) < 0.08:
                    self.vx = 0.0

        self.vy += GRAVITY
        is_wall_sliding = (
            not self.on_ground and
            self.touching_wall_dir != 0 and
            dx == self.touching_wall_dir and
            self.vy > 0
        )
        if is_wall_sliding:
            self.vy = min(self.vy, WALL_SLIDE_SPEED)
        else:
            self.vy = min(self.vy, MAX_FALL_SPEED)

        if self.jump_buffer_timer > 0:
            if self.coyote_timer > 0:
                self.vy = JUMP_VELOCITY
                self.on_ground = False
                self.coyote_timer = 0
                self.jump_buffer_timer = 0
                if audio:
                    audio.play_sfx("jump")
            elif self.touching_wall_dir != 0:
                self.vx = -self.touching_wall_dir * WALL_JUMP_X_SPEED
                self.vy = WALL_JUMP_Y_SPEED
                self.facing_right = (self.vx > 0)
                self.wall_jump_lock_timer = WALL_JUMP_LOCK_FRAMES
                self.jump_buffer_timer = 0
                self.double_jump_available = True
                if audio:
                    audio.play_sfx("wall_jump")
            elif self.double_jump_available:
                self.vy = DOUBLE_JUMP_VELOCITY
                self.double_jump_available = False
                self.jump_buffer_timer = 0
                if dx != 0:
                    self.vx = dx * MAX_RUN_SPEED * 0.9
                if audio:
                    audio.play_sfx("double_jump")

        if controller.jump_just_released and self.vy < 0:
            self.vy *= VARIABLE_JUMP_CUTOFF

        self._move_and_collide(room)

    def _move_and_collide(self, room):
        self.x += self.vx
        self.rect.x = int(round(self.x))
        self.touching_wall_dir = 0
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vx > 0:
                    self.rect.right = tile.left
                    self.touching_wall_dir = 1
                elif self.vx < 0:
                    self.rect.left = tile.right
                    self.touching_wall_dir = -1
                self.x = float(self.rect.x)
                self.vx = 0.0

        if self.touching_wall_dir == 0 and not self.on_ground:
            if room.rect_collides_with_solid(self.rect.move(-1, 0)):
                self.touching_wall_dir = -1
            elif room.rect_collides_with_solid(self.rect.move(1, 0)):
                self.touching_wall_dir = 1

        self.y += self.vy
        self.rect.y = int(round(self.y))
        self.on_ground = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vy > 0:
                    self.rect.bottom = tile.top
                    self.on_ground = True
                    self.coyote_timer = COYOTE_TIME_FRAMES
                    self.double_jump_available = True
                elif self.vy < 0:
                    self.rect.top = tile.bottom
                self.y = float(self.rect.y)
                self.vy = 0.0

    def _update_animation_state(self):
        self.anim_timer += 1
        if self.tongue_state != "INACTIVE":
            self.anim_state = "tongue"
        elif not self.on_ground:
            if self.touching_wall_dir != 0 and self.vy > 0:
                self.anim_state = "wall_slide"
            else:
                self.anim_state = "jump"
        elif abs(self.vx) > 0.25:
            self.anim_state = "run"
        else:
            self.anim_state = "idle"

    def draw(self, surface, camera_x, camera_y, assets=None):
        # Soft radial player lantern aura so Froggy pops against lush dark backgrounds
        if assets and "player" in assets.lights:
            lt = assets.lights["player"]
            sx_c = int(self.center_x - camera_x)
            sy_c = int(self.center_y - camera_y)
            surface.blit(lt, (sx_c - lt.get_width() // 2, sy_c - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        for proj in self.projectiles:
            proj.draw(surface, camera_x, camera_y, assets)

        if self.tongue_state != "INACTIVE":
            start_pos = (int(self.center_x - camera_x), int(self.center_y - camera_y))
            if self.tongue_state == "SWINGING":
                end_pos = (
                    int(self.grapple_anchor.x - camera_x),
                    int(self.grapple_anchor.y - camera_y)
                )
            else:
                tip_x = self.center_x + self.tongue_dir_x * self.tongue_length
                tip_y = self.center_y + self.tongue_dir_y * self.tongue_length
                end_pos = (int(tip_x - camera_x), int(tip_y - camera_y))

            pygame.draw.line(surface, COLOR_TONGUE_PINK, start_pos, end_pos, 3)
            pygame.draw.circle(surface, COLOR_TONGUE_TIP, end_pos, 4)

        if self.invuln_timer > 0 and (self.invuln_timer // 3) % 2 == 1:
            return

        facing_key = "right" if self.facing_right else "left"
        frames = self.animations[facing_key][self.anim_state]
        frame_index = (self.anim_timer // 8) % len(frames)
        sprite = frames[frame_index]
        draw_x = int(self.rect.x - 2 - camera_x)
        draw_y = int(self.rect.y - 1 - camera_y)
        surface.blit(sprite, (draw_x, draw_y))


# =============================================================================
# CHAPTER 12. SMOOTH HYSTERESIS CAMERA & METROIDVANIA HUD
# =============================================================================

class SmoothCamera:
    """
    Smooth platformer camera with dual-axis Hysteresis (Deadzone Window)
    and support for dramatic Boss Awakening camera rumble!
    """
    def __init__(self, world_width, world_height):
        self.x = 0.0
        self.y = 0.0
        self.shake_offset_x = 0
        self.shake_offset_y = 0
        self.set_bounds(world_width, world_height)
        self.deadzone_w = 64.0
        self.deadzone_h = 42.0

    @property
    def render_x(self):
        return self.x + self.shake_offset_x

    @property
    def render_y(self):
        return self.y + self.shake_offset_y

    def set_bounds(self, world_width, world_height):
        self.world_width = world_width
        self.world_height = world_height

    def snap_to(self, player):
        self.x = player.center_x - (INTERNAL_WIDTH * 0.5)
        self.y = player.center_y - (INTERNAL_HEIGHT * 0.55)
        self._clamp()

    def update(self, player, shake_timer=0):
        center_x = self.x + (INTERNAL_WIDTH * 0.5)
        center_y = self.y + (INTERNAL_HEIGHT * 0.55)

        dx = player.center_x - center_x
        half_w = self.deadzone_w * 0.5
        if dx > half_w:
            target_x = self.x + (dx - half_w)
        elif dx < -half_w:
            target_x = self.x + (dx + half_w)
        else:
            target_x = self.x

        dy = player.center_y - center_y
        half_h = self.deadzone_h * 0.5
        if dy > half_h:
            target_y = self.y + (dy - half_h)
        elif dy < -half_h:
            target_y = self.y + (dy + half_h)
        else:
            target_y = self.y

        self.x += (target_x - self.x) * 0.08
        self.y += (target_y - self.y) * 0.08
        self._clamp()

        if shake_timer > 0:
            self.shake_offset_x = random.randint(-3, 3)
            self.shake_offset_y = random.randint(-2, 2)
        else:
            self.shake_offset_x = 0
            self.shake_offset_y = 0

    def _clamp(self):
        max_x = max(0.0, float(self.world_width - INTERNAL_WIDTH))
        max_y = max(0.0, float(self.world_height - INTERNAL_HEIGHT))
        self.x = max(0.0, min(max_x, self.x))
        self.y = max(0.0, min(max_y, self.y))


def draw_hud_and_minimap(surface, font, player, world_manager, camera, mouse_world_pos, controller, show_builder, pulse_timer):
    room = world_manager.current_room

    # Only draw mouse builder cursor & prompts if in BUILDER mode!
    if show_builder:
        mx_world, my_world = mouse_world_pos
        col = int(mx_world // TILE_SIZE)
        row = int(my_world // TILE_SIZE)
        cursor_sx = int(col * TILE_SIZE - camera.render_x)
        cursor_sy = int(row * TILE_SIZE - camera.render_y)
        pygame.draw.rect(surface, (255, 230, 90), (cursor_sx, cursor_sy, TILE_SIZE, TILE_SIZE), 1)

        help_img = font.render(
            "BUILDER: [Click] '#' | [G+Click] Ring | [E+Click] Beetle | [F+Click] Fly | [R-Click] Erase | [P] Export",
            True, (190, 225, 255)
        )
        surface.blit(help_img, (10, 22))

    # Translucent Top HUD Backing Pill
    pygame.draw.rect(surface, (12, 18, 30), (6, 4, 340, 16), border_radius=4)
    pygame.draw.rect(surface, (55, 85, 120), (6, 4, 340, 16), 1, border_radius=4)

    # 5-Heart SNES Health Bar
    for i in range(PLAYER_MAX_HP):
        hx = 12 + i * 14
        hy = 8
        color = COLOR_HEART_RED if i < player.hp else COLOR_HEART_EMPTY
        pygame.draw.rect(surface, color, (hx, hy, 10, 8), border_radius=2)
        pygame.draw.rect(surface, (255, 255, 255), (hx, hy, 10, 8), 1, border_radius=2)

    score_img = font.render(
        f"EATEN: {player.eaten_count} | {room.title}",
        True, COLOR_HUD_TEXT
    )
    surface.blit(score_img, (86, 6))

    # Super Metroid Style Automap (Top-Right of 640x360 Canvas)
    map_origin_x = INTERNAL_WIDTH - 114
    map_origin_y = 6
    cell_w, cell_h = 22, 12

    for room_id, r_obj in world_manager.rooms.items():
        gx, gy = r_obj.map_coords
        cell_rect = pygame.Rect(
            map_origin_x + gx * (cell_w + 3),
            map_origin_y + gy * (cell_h + 3),
            cell_w, cell_h
        )

        if r_obj is room:
            pygame.draw.rect(surface, (45, 175, 225), cell_rect)
            pygame.draw.rect(surface, (255, 255, 255), cell_rect, 1)

            px_ratio = player.center_x / max(1, r_obj.world_width)
            py_ratio = player.center_y / max(1, r_obj.world_height)
            dot_x = cell_rect.x + int(px_ratio * (cell_w - 4)) + 2
            dot_y = cell_rect.y + int(py_ratio * (cell_h - 4)) + 2
            pygame.draw.circle(surface, (255, 235, 80), (dot_x, dot_y), 2)
        elif room_id in world_manager.visited_rooms:
            fill_col = (120, 35, 65) if room_id == "boss_sanctum" else (45, 68, 112)
            pygame.draw.rect(surface, fill_col, cell_rect)
            pygame.draw.rect(surface, (120, 155, 205), cell_rect, 1)
        else:
            pygame.draw.rect(surface, (35, 44, 68), cell_rect, 1)

    # 8-Way Aim Compass
    _, (ux, uy) = controller.get_dpad_vector(player.facing_right)
    compass_center = (map_origin_x - 18, 13)
    pygame.draw.circle(surface, (30, 42, 68), compass_center, 10)
    pygame.draw.circle(surface, (110, 155, 210), compass_center, 10, 1)
    aim_end = (int(compass_center[0] + ux * 8), int(compass_center[1] + uy * 8))
    pygame.draw.line(surface, COLOR_TONGUE_PINK, compass_center, aim_end, 2)
    pygame.draw.circle(surface, COLOR_BOSS_GOLD, aim_end, 2)

    # Dedicated Boss Health Bar (Shown once Emperor Mantis has awakened!)
    active_boss = room.get_active_boss()
    if active_boss is not None and active_boss.alive and active_boss.awakened:
        bar_w = 260
        bar_h = 11
        bar_x = (INTERNAL_WIDTH - bar_w) // 2
        bar_y = INTERNAL_HEIGHT - 22

        pygame.draw.rect(surface, (22, 12, 28), (bar_x - 3, bar_y - 3, bar_w + 6, bar_h + 6), border_radius=4)
        pygame.draw.rect(surface, (255, 205, 70), (bar_x - 3, bar_y - 3, bar_w + 6, bar_h + 6), 1, border_radius=4)

        hp_ratio = active_boss.hp / active_boss.max_hp
        fill_w = int(bar_w * hp_ratio)
        bar_col = (255, 55, 95) if active_boss.phase == 3 else ((255, 145, 50) if active_boss.phase == 2 else (95, 235, 130))
        if fill_w > 0:
            pygame.draw.rect(surface, bar_col, (bar_x, bar_y, fill_w, bar_h), border_radius=3)

        boss_label = font.render(
            f"EMPEROR MANTIS  [PHASE {active_boss.phase}]  -  STUN WITH [R], YANK CORE WITH [Y]!",
            True, (255, 230, 240)
        )
        surface.blit(boss_label, ((INTERNAL_WIDTH - boss_label.get_width()) // 2, bar_y - 14))

    # Dramatic Boss Awakening Warning Banner
    if room.boss_awakening_banner_timer > 0 and (pulse_timer // 4) % 2 == 0:
        warn_surf = font.render("!! WARNING: THE EMPEROR MANTIS AWAKENS !!", True, (255, 85, 120))
        wx = (INTERNAL_WIDTH - warn_surf.get_width()) // 2
        wy = 48
        pygame.draw.rect(surface, (32, 10, 24), (wx - 10, wy - 4, warn_surf.get_width() + 20, 20), border_radius=4)
        pygame.draw.rect(surface, (255, 85, 120), (wx - 10, wy - 4, warn_surf.get_width() + 20, 20), 1, border_radius=4)
        surface.blit(warn_surf, (wx, wy))

    if room.boss_defeated_banner_timer > 0:
        banner_surf = font.render("VICTORY! EMPEROR MANTIS DEFEATED! PORTAL OPEN!", True, COLOR_BOSS_GOLD)
        bx = (INTERNAL_WIDTH - banner_surf.get_width()) // 2
        by = (INTERNAL_HEIGHT // 2) - 20
        pygame.draw.rect(surface, (20, 24, 42), (bx - 10, by - 5, banner_surf.get_width() + 20, 22), border_radius=4)
        pygame.draw.rect(surface, COLOR_BOSS_GOLD, (bx - 10, by - 5, banner_surf.get_width() + 20, 22), 1, border_radius=4)
        surface.blit(banner_surf, (bx, by))


# =============================================================================
# CHAPTER 13. LUSH 720p TITLE SCREEN, PAUSE MENU & MAIN ENGINE LOOP
# =============================================================================

def draw_title_screen(surface, title_font, menu_font, selected_index, anim_timer, frog_idle_surf, assets):
    # 1. Lush Canopy Pixel-Art Backdrop
    bg_canopy = assets.backgrounds.get("canopy")
    if bg_canopy:
        surface.blit(bg_canopy, (0, 0))
    else:
        surface.fill((16, 24, 38))

    # Animated fireflies drifting across the Title Screen
    for i in range(12):
        fx = int((i * 57 + math.sin(anim_timer * 0.03 + i) * 28) % INTERNAL_WIDTH)
        fy = int((i * 31 + math.cos(anim_timer * 0.025 + i * 2) * 18) % INTERNAL_HEIGHT)
        lt = assets.lights.get("cyan" if i % 2 == 0 else "emerald")
        if lt:
            surface.blit(lt, (fx - lt.get_width() // 2, fy - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.circle(surface, (180, 255, 220), (fx, fy), 2)

    # Center Translucent Stone Frame Card
    card_rect = pygame.Rect(INTERNAL_WIDTH // 2 - 175, 42, 350, 265)
    card_surf = pygame.Surface((card_rect.width, card_rect.height), pygame.SRCALPHA)
    card_surf.fill((12, 20, 34, 205))
    surface.blit(card_surf, card_rect.topleft)
    pygame.draw.rect(surface, (85, 215, 135), card_rect, 2, border_radius=6)

    title_text = "F R O G G Y"
    shadow_img = title_font.render(title_text, True, (10, 16, 24))
    title_img = title_font.render(title_text, True, (105, 245, 130))
    tx = (INTERNAL_WIDTH - title_img.get_width()) // 2
    ty = 58
    surface.blit(shadow_img, (tx + 2, ty + 2))
    surface.blit(title_img, (tx, ty))

    sub_text = "16-BIT METROIDVANIA  -  720p LUSH EDITION"
    sub_img = menu_font.render(sub_text, True, (255, 215, 75))
    sx = (INTERNAL_WIDTH - sub_img.get_width()) // 2
    surface.blit(sub_img, (sx, ty + 38))

    # Bouncing Hero Froggy Showcase with Golden Glow
    frog_bounce_y = int(math.sin(anim_timer * 0.08) * 4)
    fx_center = INTERNAL_WIDTH // 2
    fy_center = 138 + frog_bounce_y
    if "gold" in assets.lights:
        lt = assets.lights["gold"]
        surface.blit(lt, (fx_center - lt.get_width() // 2, fy_center + 8 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
    scaled_frog = pygame.transform.scale(frog_idle_surf, (36, 32))
    surface.blit(scaled_frog, (fx_center - 18, fy_center - 8))

    menu_items = ["START GAME  (CANOPY TO BOSS)", "CREATE LEVEL (SANDBOX BUILDER)"]
    menu_start_y = 188

    for i, item in enumerate(menu_items):
        is_selected = (i == selected_index)
        col = (255, 255, 255) if is_selected else (140, 165, 195)
        item_img = menu_font.render(item, True, col)
        ix = (INTERNAL_WIDTH - item_img.get_width()) // 2
        iy = menu_start_y + i * 28

        if is_selected:
            cursor_col = (255, 215, 70) if (anim_timer // 6) % 2 == 0 else (95, 245, 215)
            pill_rect = pygame.Rect(ix - 14, iy - 4, item_img.get_width() + 28, item_img.get_height() + 8)
            pygame.draw.rect(surface, (32, 54, 82), pill_rect, border_radius=4)
            pygame.draw.rect(surface, cursor_col, pill_rect, 1, border_radius=4)

            arrow_img = menu_font.render(">", True, cursor_col)
            surface.blit(arrow_img, (ix - 24, iy))

        surface.blit(item_img, (ix, iy))

    hint_text = "[UP/DOWN] Select   [SPACE/A] Confirm   [X/J] 8-Way Tongue   [C/Shift] Spore"
    hint_img = menu_font.render(hint_text, True, (175, 210, 235))
    hx = (INTERNAL_WIDTH - hint_img.get_width()) // 2
    surface.blit(hint_img, (hx, INTERNAL_HEIGHT - 24))


def draw_game_over_screen(surface, title_font, menu_font, anim_timer):
    dark_overlay = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    dark_overlay.fill((40, 10, 22))
    dark_overlay.set_alpha(210)
    surface.blit(dark_overlay, (0, 0))

    go_text = "GAME OVER"
    shadow_img = title_font.render(go_text, True, (10, 5, 10))
    go_img = title_font.render(go_text, True, (245, 65, 90))
    gx = (INTERNAL_WIDTH - go_img.get_width()) // 2
    gy = 95
    surface.blit(shadow_img, (gx + 2, gy + 2))
    surface.blit(go_img, (gx, gy))

    info_lines = [
        "FROGGY RAN OUT OF HEARTS!",
        "(Tip: Stun beetles with [R] and eat bugs with [Y] to heal +1 Heart!)",
        "",
        "[SPACE / A / B]  RESPAWN AT ROOM ENTRANCE",
        "[ESCAPE]         RETURN TO TITLE SCREEN",
    ]

    for i, line in enumerate(info_lines):
        col = (255, 230, 90) if "RESPAWN" in line else ((215, 225, 240) if i < 2 else (175, 195, 225))
        img = menu_font.render(line, True, col)
        lx = (INTERNAL_WIDTH - img.get_width()) // 2
        surface.blit(img, (lx, 150 + i * 20))


def draw_pause_screen(surface, title_font, menu_font, selected_index, anim_timer):
    dark_overlay = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    dark_overlay.fill((10, 16, 28))
    dark_overlay.set_alpha(195)
    surface.blit(dark_overlay, (0, 0))

    pause_img = title_font.render("PAUSED", True, (245, 205, 70))
    px = (INTERNAL_WIDTH - pause_img.get_width()) // 2
    surface.blit(pause_img, (px, 90))

    options = ["RESUME ADVENTURE", "RETURN TO TITLE", "QUIT GAME"]
    for i, opt in enumerate(options):
        is_sel = (i == selected_index)
        col = (255, 255, 255) if is_sel else (135, 155, 185)
        img = menu_font.render(opt, True, col)
        ox = (INTERNAL_WIDTH - img.get_width()) // 2
        oy = 155 + i * 26

        if is_sel:
            cursor_col = (80, 245, 210)
            pill_rect = pygame.Rect(ox - 10, oy - 3, img.get_width() + 20, img.get_height() + 6)
            pygame.draw.rect(surface, (35, 52, 82), pill_rect, border_radius=4)
            pygame.draw.rect(surface, cursor_col, pill_rect, 1, border_radius=4)

        surface.blit(img, (ox, oy))


def main():
    pygame.init()
    pygame.display.set_caption(
        "FROGGY - 720p 16-Bit Metroidvania (Lush Canopy, 8-Way Tongue & Sinister Boss)"
    )

    window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    snes_canvas = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    clock = pygame.time.Clock()

    hud_font = pygame.font.SysFont("monospace", 10, bold=True)
    menu_font = pygame.font.SysFont("monospace", 11, bold=True)
    title_font = pygame.font.SysFont("impact", 32, bold=True)

    # 1. Initialize Audio Engine & Hybrid Asset Pipeline
    audio = RetroAudioEngine()
    assets = AssetManager()
    controller = SNESController()

    animations = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()

    # 2. Build Connected World starting in Level 1 ("Lush Canopy to Mantis Sanctum")
    world = WorldManager(WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    spawn_x, spawn_y = world.current_room.default_spawn
    player = FroggyPlayer(spawn_x, spawn_y, animations)

    camera = SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    camera.snap_to(player)

    game_state = "TITLE"
    game_mode = "ADVENTURE"

    title_selected_index = 0
    pause_selected_index = 0

    show_hud = True
    pulse_timer = 0
    running = True

    audio.play_music("title")

    while running:
        pulse_timer += 1

        # =====================================================================
        # STATE A: TITLE SCREEN
        # =====================================================================
        if game_state == "TITLE":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        title_selected_index = (title_selected_index - 1) % 2
                        audio.play_sfx("cursor")
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        title_selected_index = (title_selected_index + 1) % 2
                        audio.play_sfx("cursor")
                    elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_k, pygame.K_z):
                        audio.play_sfx("select")
                        if title_selected_index == 0:
                            game_mode = "ADVENTURE"
                            world.warp_directly_to_room("level_1", player, camera, audio)
                            player.hp = PLAYER_MAX_HP
                            game_state = "PLAYING"
                            audio.play_music("level")
                        elif title_selected_index == 1:
                            game_mode = "BUILDER"
                            world.warp_directly_to_room("sandbox_room", player, camera, audio)
                            player.hp = PLAYER_MAX_HP
                            game_state = "PLAYING"
                            audio.play_music("level")
                    elif event.key == pygame.K_ESCAPE:
                        running = False

            frog_preview = animations["right"]["idle"][0]
            draw_title_screen(
                snes_canvas, title_font, menu_font,
                title_selected_index, pulse_timer, frog_preview, assets
            )

        # =====================================================================
        # STATE B: PLAYING (METROIDVANIA ADVENTURE / SANDBOX BUILDER)
        # =====================================================================
        elif game_state == "PLAYING":
            is_builder_active = (game_mode == "BUILDER")

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game_state = "PAUSED"
                        pause_selected_index = 0
                        audio.play_sfx("cursor")
                    elif event.key == pygame.K_TAB:
                        show_hud = not show_hud
                    elif event.key == pygame.K_p and is_builder_active:
                        world.current_room.export_ascii_to_console()
                        audio.play_sfx("select")
                    elif event.key == pygame.K_b:
                        world.warp_directly_to_room("boss_sanctum", player, camera, audio)

            mouse_win_x, mouse_win_y = pygame.mouse.get_pos()
            canvas_mx = mouse_win_x / WINDOW_SCALE
            canvas_my = mouse_win_y / WINDOW_SCALE
            world_mx = canvas_mx + camera.render_x
            world_my = canvas_my + camera.render_y

            if is_builder_active:
                mouse_buttons = pygame.mouse.get_pressed()
                keys = pygame.key.get_pressed()
                if mouse_buttons[0]:
                    if keys[pygame.K_g]: brush_char = 'G'
                    elif keys[pygame.K_e]: brush_char = 'E'
                    elif keys[pygame.K_f]: brush_char = 'F'
                    elif keys[pygame.K_m]: brush_char = 'M'
                    else: brush_char = '#'
                    world.current_room.paint_tile_at_world_pos(world_mx, world_my, brush_char)
                elif mouse_buttons[2]:
                    world.current_room.paint_tile_at_world_pos(world_mx, world_my, '.')

            controller.update()

            if world.is_transitioning:
                world.update_transition(player, camera, audio)
            else:
                world.current_room.update_entities(player, audio, pulse_timer)
                player.update(controller, world.current_room, world, audio)
                camera.update(player, shake_timer=world.current_room.screen_shake_timer)

                if player.hp <= 0:
                    player.hp = 0
                    game_state = "GAME_OVER"
                    audio.play_sfx("game_over")
                    audio.stop_music()

            world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, pulse_timer)
            player.draw(snes_canvas, camera.render_x, camera.render_y, assets)

            if show_hud:
                draw_hud_and_minimap(
                    snes_canvas, hud_font, player, world, camera,
                    (world_mx, world_my), controller,
                    show_builder=is_builder_active,
                    pulse_timer=pulse_timer
                )

            world.draw_fade_overlay(snes_canvas)

        # =====================================================================
        # STATE C: IN-GAME PAUSE MENU
        # =====================================================================
        elif game_state == "PAUSED":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        pause_selected_index = (pause_selected_index - 1) % 3
                        audio.play_sfx("cursor")
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        pause_selected_index = (pause_selected_index + 1) % 3
                        audio.play_sfx("cursor")
                    elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_k, pygame.K_z):
                        audio.play_sfx("select")
                        if pause_selected_index == 0:
                            game_state = "PLAYING"
                        elif pause_selected_index == 1:
                            game_state = "TITLE"
                            audio.play_music("title")
                        elif pause_selected_index == 2:
                            running = False
                    elif event.key == pygame.K_ESCAPE:
                        game_state = "PLAYING"
                        audio.play_sfx("cursor")

            draw_pause_screen(snes_canvas, title_font, menu_font, pause_selected_index, pulse_timer)

        # =====================================================================
        # STATE D: GAME OVER SCREEN
        # =====================================================================
        elif game_state == "GAME_OVER":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_k, pygame.K_z):
                        player.hp = PLAYER_MAX_HP
                        spawn_x, spawn_y = world.current_room.default_spawn
                        player.teleport_to_room(spawn_x, spawn_y)
                        world.current_room.spawn_enemies()
                        camera.snap_to(player)
                        game_state = "PLAYING"
                        audio.play_sfx("select")
                        if world.current_room.room_id == "boss_sanctum":
                            audio.play_music("boss")
                        else:
                            audio.play_music("level")
                    elif event.key == pygame.K_ESCAPE:
                        game_state = "TITLE"
                        audio.play_music("title")

            draw_game_over_screen(snes_canvas, title_font, menu_font, pulse_timer)

        # Integer-scale 640x360 retro canvas by 2x to fill the 1280x720 (720p HD) window
        pygame.transform.scale(snes_canvas, (WINDOW_WIDTH, WINDOW_HEIGHT), window)
        pygame.display.flip()
        clock.tick(TARGET_FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
