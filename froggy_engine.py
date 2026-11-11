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

import asyncio
import io
import json
import math
import os
import random
import struct
import sys
import time
import wave
import pygame

# Initialize high-resolution Windows timer for locked, jitter-free 60 FPS
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


def create_silhouette_flash(sprite_surface, color=(255, 255, 255, 220)):
    """
    Creates an authentic 32-bit sprite silhouette flash matching the exact pixel alpha outline,
    eliminating rectangular bounding-box visual flashing artifacts.
    """
    if sprite_surface is None:
        return None
    flash = sprite_surface.copy()
    flash.fill((color[0], color[1], color[2], 0), special_flags=pygame.BLEND_RGB_MAX)
    return flash


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

try:
    import midi_writer
    HAS_MIDI_WRITER = True
except ImportError:
    HAS_MIDI_WRITER = False


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
# Tuned down slightly per user request for lush, readable 16-bit platformer feel:
GRAVITY = 0.28                 # Downward acceleration added to velocity_y each frame (soft floaty feel)
MAX_FALL_SPEED = 6.8           # Terminal velocity so falls feel smooth and readable
WALL_SLIDE_SPEED = 1.4         # Reduced fall speed when clinging to a vertical wall
MOVE_ACCEL = 0.52              # How fast Froggy builds horizontal speed on the ground
AIR_ACCEL = 0.36               # Horizontal authority while in mid-air
GROUND_FRICTION = 0.72         # Snappy horizontal ground stop with damped sliding
AIR_DRAG = 0.90                # Controlled horizontal air drag (less slippery float)
MAX_RUN_SPEED = 3.6            # Top horizontal running speed
JUMP_VELOCITY = -6.5           # Instant upward velocity when pressing A or B (tuned for 0.28 gravity)
DOUBLE_JUMP_VELOCITY = -5.8    # Boost for the second mid-air jump
VARIABLE_JUMP_CUTOFF = 0.45    # Multiplies upward speed if player releases A/B early
WALL_JUMP_X_SPEED = 4.2        # Horizontal push-off speed when jumping off a wall
WALL_JUMP_Y_SPEED = -6.4       # Vertical launch speed when jumping off a wall
WALL_JUMP_LOCK_FRAMES = 10     # Frames of locked horizontal input so you cleanly leave the wall
COYOTE_TIME_FRAMES = 6         # Grace frames allowing a jump just after walking off a ledge
JUMP_BUFFER_FRAMES = 6         # Remembers a jump press made slightly before touching the ground

# --- Super Castlevania IV Tongue & Pendulum Grapple Constants ---
TONGUE_EXTEND_SPEED = 14.0
TONGUE_RETRACT_SPEED = 15.0
TONGUE_MAX_LENGTH = 145.0
TONGUE_HOLD_FRAMES = 7
SWING_GRAVITY = 0.011
SWING_DAMPING = 0.985          # Increased pendulum damping for controlled, weighted swing motion
SWING_PUMP_FORCE = 0.0022
SWING_REEL_SPEED = 1.5
SWING_MIN_LENGTH = 28.0

# --- Health & Combat Constants ---
PLAYER_MAX_HP = 5
PLAYER_INVULN_FRAMES = 65
ENEMY_STUN_FRAMES = 210
BOSS_MAX_HP = 6
BOSS_MAX_HP_HOUND = 8
BOSS_MAX_HP_TOAD = 50
BOSS_MAX_HP_SHARK = 65
BOSS_WEAK_EXPOSED_FRAMES = 210
MUHLASER_MAX_CHARGE = 180      # Up to 3.0 seconds (180 frames at 60 FPS) for mega frogbeam!

# --- Metroidvania Screen Transitions ---
TRANSITION_FADE_SPEED = 18
DOOR_COOLDOWN_FRAMES = 36

# --- Color Palette (16-Bit SNES Inspired RGB Tuples) ---
COLOR_BG_GRID = (26, 38, 56)
COLOR_TONGUE_PINK = (242, 107, 148)
COLOR_TONGUE_TIP = (255, 175, 205)
COLOR_SPORE_CYAN = (80, 245, 210)
COLOR_BOOMERANG_RED = (255, 60, 80)
COLOR_HUD_TEXT = (230, 245, 255)
COLOR_DOOR_GLOW = (90, 235, 255)
COLOR_HEART_RED = (235, 65, 85)
COLOR_HEART_EMPTY = (60, 45, 70)
COLOR_BOSS_CORE = (255, 70, 210)
COLOR_BOSS_GOLD = (255, 215, 70)
COLOR_GRAPPLE_GOLD = (255, 215, 70)


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
    """
    16-Bit Sound Effect Sample Bank & Multi-Track MIDI / Chiptune Audio Engine:
    Upgrades procedural waveforms to true 16-bit 44.1kHz stereo PCM WAV sample
    files stored in `assets/sfx/*.wav`, processed through an authentic SNES
    S-SMP / SPC700-inspired 8-tap stereo echo & reverb filter, multi-harmonic
    FM synthesis, and crunchy 16-bit transient layering.
    """
    SAMPLE_RATE = 44100

    def __init__(self):
        self.enabled = False
        self.sfx_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sfx")
        os.makedirs(self.sfx_dir, exist_ok=True)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.SAMPLE_RATE, -16, 2, 512)
            self.enabled = True
            self.music_channel = pygame.mixer.Channel(0)
            self.music_channel.set_volume(0.48)

            # 1. Initialize Standard MIDI soundtrack files (.mid)
            music_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "music")
            os.makedirs(music_dir, exist_ok=True)
            if HAS_MIDI_WRITER:
                req_midi = os.path.join(music_dir, "volcanic_magma.mid")
                if not os.path.exists(req_midi):
                    midi_writer.build_all_midi_soundtrack()

            self.midi_files = {
                'level': os.path.join(music_dir, "jungle_vivaldi_reggae.mid"),
                'title': os.path.join(music_dir, "title_theme.mid"),
                'boss': os.path.join(music_dir, "boss_mantis.mid"),
                'boss_mantis': os.path.join(music_dir, "boss_mantis.mid"),
                'boss_hound': os.path.join(music_dir, "boss_hound.mid"),
                'boss_toad': os.path.join(music_dir, "boss_toad.mid"),
                'boss_snowman': os.path.join(music_dir, "boss_snowman.mid"),
                'ice': os.path.join(music_dir, "ice_hot_springs.mid"),
                'volcanic': os.path.join(music_dir, "volcanic_magma.mid"),
                'underwater': os.path.join(music_dir, "sunken_grotto.mid"),
            }

            print("[Audio Engine] Building 16-Bit PCM/WAV Sound Effect Sample Bank & MIDI Soundtrack...")
            self.sfx = self._build_all_sfx()
            self.sounds = self.sfx
            self.music_tracks = self._build_all_music()
            self.current_track_name = None
            print("[Audio Engine] 16-Bit Sample Bank & Audio synthesis complete!")
        except Exception as err:
            print(f"[Audio Engine] Notice: Audio device unavailable ({err}). Running in silent mode.")

    @classmethod
    def _apply_snes_reverb(cls, samples, wet=0.28, decay=0.42, stereo_spread=True):
        """
        Applies an authentic SNES S-SMP / SPC700-style multi-tap stereo echo &
        FIR low-pass reverb tail to a 1D float sample array, returning a
        (N_with_tail, 2) float32 stereo array in [-1.0, 1.0].
        """
        sr = cls.SAMPLE_RATE
        if HAS_NUMPY:
            dry = np.asarray(samples, dtype=np.float32)
            tail_len = int(sr * 0.16) if wet > 0.05 else int(sr * 0.04)
            total_len = len(dry) + tail_len
            padded = np.zeros(total_len, dtype=np.float32)
            padded[:len(dry)] = dry

            # 16-bit DAC quantization crunch (simulating SNES BRR 16-bit sample warmth)
            padded = np.round(padded * 4096.0) / 4096.0

            left = padded.copy()
            right = padded.copy()

            if wet > 0.0:
                # 6-tap stereo echo network (delays in milliseconds inspired by SNES echo buffer)
                taps_l = [(17.0, 0.52), (34.0, 0.36 * decay), (53.0, 0.24 * decay), (79.0, 0.15 * decay * decay)]
                taps_r = [(23.0, 0.50), (41.0, 0.34 * decay), (61.0, 0.22 * decay), (89.0, 0.14 * decay * decay)]
                if not stereo_spread:
                    taps_r = taps_l

                echo_l = np.zeros(total_len, dtype=np.float32)
                echo_r = np.zeros(total_len, dtype=np.float32)
                for delay_ms, gain in taps_l:
                    d_samp = int(sr * (delay_ms / 1000.0))
                    if d_samp < total_len:
                        echo_l[d_samp:] += padded[:-d_samp] * gain
                for delay_ms, gain in taps_r:
                    d_samp = int(sr * (delay_ms / 1000.0))
                    if d_samp < total_len:
                        echo_r[d_samp:] += padded[:-d_samp] * gain

                # 3-point warm FIR low-pass damping on the wet reverb tail
                echo_l[1:-1] = 0.25 * echo_l[:-2] + 0.50 * echo_l[1:-1] + 0.25 * echo_l[2:]
                echo_r[1:-1] = 0.25 * echo_r[:-2] + 0.50 * echo_r[1:-1] + 0.25 * echo_r[2:]

                left = np.clip(left + echo_l * wet, -0.98, 0.98)
                right = np.clip(right + echo_r * wet, -0.98, 0.98)

            return np.column_stack((left, right))
        else:
            return samples

    @classmethod
    def _create_wav_sound(cls, samples, name=None, sfx_dir=None, wet=0.25, decay=0.40):
        """
        Packs float samples into a true 16-bit 44.1kHz stereo PCM WAV file
        (saving to `assets/sfx/<name>.wav` when `name` is provided) and returns
        a `pygame.mixer.Sound` instance.
        """
        wav_path = os.path.join(sfx_dir, f"{name}.wav") if (name and sfx_dir) else None
        if wav_path and os.path.exists(wav_path) and os.path.getsize(wav_path) > 256:
            try:
                return pygame.mixer.Sound(wav_path)
            except Exception:
                pass

        buf = io.BytesIO()
        wav_file = wave.open(buf, 'wb')
        if HAS_NUMPY:
            stereo = cls._apply_snes_reverb(samples, wet=wet, decay=decay)
            pcm16 = np.clip(stereo * 32767.0, -32767, 32767).astype('<i2')
            raw_bytes = pcm16.tobytes()
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(cls.SAMPLE_RATE)
            wav_file.writeframes(raw_bytes)
        else:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(cls.SAMPLE_RATE)
            data = bytearray()
            for s in samples:
                val = int(max(-32767, min(32767, s * 32767)))
                data.extend(struct.pack('<h', val))
            wav_file.writeframes(data)
        wav_file.close()

        wav_bytes = buf.getvalue()
        if wav_path:
            try:
                with open(wav_path, 'wb') as f:
                    f.write(wav_bytes)
            except Exception:
                pass

        buf.seek(0)
        return pygame.mixer.Sound(buf)

    def _register_sample(self, sfx_dict, name, samples, wet=0.26, decay=0.42):
        snd = self._create_wav_sound(samples, name=name, sfx_dir=self.sfx_dir, wet=wet, decay=decay)
        sfx_dict[name] = snd
        return snd

    def _build_all_sfx(self):
        sr = self.SAMPLE_RATE
        sfx = {}
        rng = random.Random(1616)

        # 1. Jump: Warm 16-bit rising FM triangle + sub-octave spring (150 Hz -> 520 Hz)
        n = int(sr * 0.13)
        samples = []
        for i in range(n):
            t = i / sr
            f = 150.0 + ((t / 0.13) ** 1.15) * 370.0
            p = (f * t) % 1.0
            tri = 4.0 * abs(p - 0.5) - 1.0
            sub = math.sin(2.0 * math.pi * (f * 0.5) * t) * 0.35
            overtone = math.sin(2.0 * math.pi * (f * 2.0) * t) * 0.18
            env = (1.0 - t / 0.13) ** 0.85
            samples.append((tri * 0.45 + sub + overtone) * env * 0.65)
        self._register_sample(sfx, 'jump', samples, wet=0.22, decay=0.35)

        # 2. Double Jump: Crisp dual-harmonic air-kick chirp + SNES shimmer
        n = int(sr * 0.15)
        samples = []
        for i in range(n):
            t = i / sr
            f = 340.0 + (t / 0.15) * 520.0
            pulse = 1.0 if ((f * t) % 1.0) < 0.32 else -1.0
            bell = math.sin(2.0 * math.pi * (f * 1.5) * t) * 0.4
            whoosh = (rng.random() * 2.0 - 1.0) * max(0.0, 1.0 - t * 28.0) * 0.25
            env = (1.0 - t / 0.15)
            samples.append((pulse * 0.38 + bell * 0.32 + whoosh) * env)
        self._register_sample(sfx, 'double_jump', samples, wet=0.28, decay=0.45)

        # 3. Wall Jump: Crunchy stone kick-off thud + spring pop
        n = int(sr * 0.13)
        samples = []
        for i in range(n):
            t = i / sr
            f = 260.0 - (t / 0.13) * 110.0 if t < 0.04 else 180.0 + ((t - 0.04) / 0.09) * 320.0
            tri = 4.0 * abs(((f * t) % 1.0) - 0.5) - 1.0
            crunch = (rng.random() * 2.0 - 1.0) * max(0.0, 1.0 - t * 32.0)
            thud = math.sin(2.0 * math.pi * 92.0 * t) * max(0.0, 1.0 - t * 25.0)
            samples.append((tri * 0.38 + crunch * 0.34 + thud * 0.45) * (1.0 - t / 0.13))
        self._register_sample(sfx, 'wall_jump', samples, wet=0.26, decay=0.40)

        # 4. Tongue Whip & SNES Reverb Slap ('tongue' & 'reverb_slap'):
        # High-velocity whip snap transient + wet resonant slap + cathedral stereo echo
        n = int(sr * 0.14)
        samples = []
        for i in range(n):
            t = i / sr
            # Initial whip crack (0..25ms) followed by resonant wet slap (25..75ms)
            crack_noise = (rng.random() * 2.0 - 1.0) * math.exp(-t * 55.0) * 0.65
            slap_burst = (rng.random() * 2.0 - 1.0) * math.exp(-((t - 0.028) ** 2) * 3200.0) * 0.75
            f = 780.0 * math.exp(-t * 18.0) + 140.0
            fm_body = math.sin(2.0 * math.pi * f * t + 2.2 * math.sin(2.0 * math.pi * 240.0 * t)) * 0.48
            env = max(0.0, 1.0 - t / 0.14)
            samples.append((crack_noise + slap_burst + fm_body) * env)
        tongue_snd = self._register_sample(sfx, 'tongue', samples, wet=0.45, decay=0.60)
        sfx['reverb_slap'] = self._register_sample(sfx, 'reverb_slap', samples, wet=0.52, decay=0.68)

        # 5. Grapple Latch: Castlevania-style rich FM metallic temple bell clink
        n = int(sr * 0.22)
        samples = []
        for i in range(n):
            t = i / sr
            mod = math.sin(2.0 * math.pi * 2460.0 * t) * math.exp(-t * 28.0) * 1.8
            s1 = math.sin(2.0 * math.pi * 987.77 * t + mod) * 0.38
            s2 = math.sin(2.0 * math.pi * 1480.0 * t) * 0.28
            s3 = math.sin(2.0 * math.pi * 2960.0 * t) * math.exp(-t * 35.0) * 0.20
            samples.append((s1 + s2 + s3) * math.exp(-t * 16.0))
        self._register_sample(sfx, 'latch', samples, wet=0.38, decay=0.55)

        # 6. Spore Boomerang: Spinning stereo phaser / rotor blade oscillation
        n = int(sr * 0.18)
        samples = []
        for i in range(n):
            t = i / sr
            f = 360.0 + math.sin(2.0 * math.pi * 34.0 * t) * 135.0
            sq = 1.0 if ((f * t) % 1.0) < 0.36 else -1.0
            sine = math.sin(2.0 * math.pi * (f * 1.5) * t) * 0.3
            samples.append((sq * 0.32 + sine) * (1.0 - t / 0.18))
        self._register_sample(sfx, 'spore', samples, wet=0.30, decay=0.45)

        # 7. Enemy Stun: Rich 16-bit FM spring boing & dizzy star warble
        n = int(sr * 0.22)
        samples = []
        for i in range(n):
            t = i / sr
            f = max(120.0, 560.0 - t * 1350.0) + math.sin(2.0 * math.pi * 28.0 * t) * 85.0
            harm = math.sin(2.0 * math.pi * (f * 2.0) * t) * 0.25
            samples.append((math.sin(2.0 * math.pi * f * t) * 0.55 + harm) * (1.0 - t / 0.22))
        self._register_sample(sfx, 'stun', samples, wet=0.28, decay=0.42)

        # 8. Enemy Swallow / Eat: Crunchy chitin gulp + 16-bit restorative harp chime
        n = int(sr * 0.26)
        samples = []
        for i in range(n):
            t = i / sr
            if t < 0.08:
                f = 190.0 + (t / 0.08) * 360.0
                crunch = (rng.random() * 2.0 - 1.0) * 0.28 * math.sin(math.pi * (t / 0.08))
                v = (4.0 * abs(((f * t) % 1.0) - 0.5) - 1.0) * 0.38 + crunch
            else:
                t2 = t - 0.08
                c1 = math.sin(2.0 * math.pi * 523.25 * t2) * 0.28
                c2 = math.sin(2.0 * math.pi * 659.25 * t2) * 0.26
                c3 = math.sin(2.0 * math.pi * 783.99 * t2) * 0.22
                v = (c1 + c2 + c3) * math.exp(-t2 * 12.0)
            samples.append(v)
        self._register_sample(sfx, 'eat', samples, wet=0.32, decay=0.48)

        # 9. Hurt: Heavy 16-bit crunch impact + descending synth groan
        n = int(sr * 0.20)
        samples = []
        for i in range(n):
            t = i / sr
            noise = (rng.random() * 2.0 - 1.0) * 0.48 * math.exp(-t * 14.0)
            f = max(52.0, 195.0 - t * 520.0)
            sq = (1.0 if ((f * t) % 1.0) < 0.5 else -1.0) * 0.35
            sub = math.sin(2.0 * math.pi * (f * 0.5) * t) * 0.40
            samples.append((noise + sq + sub) * (1.0 - t / 0.20))
        self._register_sample(sfx, 'hurt', samples, wet=0.25, decay=0.38)

        # 10. Door Portal: Shimmering crystal rune arpeggio with deep temple reverb
        n = int(sr * 0.32)
        samples = []
        pitches = [440.0, 554.37, 659.25, 880.0]
        for i in range(n):
            t = i / sr
            idx = min(3, int(t / 0.08))
            f = pitches[idx]
            local_t = t % 0.08
            s1 = math.sin(2.0 * math.pi * f * t) * 0.38
            s2 = math.sin(2.0 * math.pi * (f * 2.0) * t) * 0.18
            samples.append((s1 + s2) * (1.0 - local_t / 0.08))
        self._register_sample(sfx, 'door', samples, wet=0.45, decay=0.62)

        # 11. Cursor Move: Crisp 16-bit woodblock/marimba menu tick
        n = int(sr * 0.045)
        samples = []
        for i in range(n):
            t = i / sr
            s = math.sin(2.0 * math.pi * 740.0 * t + math.sin(2.0 * math.pi * 1480.0 * t)) * math.exp(-t * 65.0) * 0.45
            samples.append(s)
        self._register_sample(sfx, 'cursor', samples, wet=0.18, decay=0.25)

        # 12. Cursor Select: Two-tone 16-bit brass/bell affirmative fanfare
        n = int(sr * 0.16)
        samples = []
        for i in range(n):
            t = i / sr
            f = 523.25 if t < 0.075 else 783.99
            local_t = t if t < 0.075 else (t - 0.075)
            s = math.sin(2.0 * math.pi * f * t) * 0.35 + math.sin(2.0 * math.pi * (f * 2.0) * t) * 0.20
            samples.append(s * math.exp(-local_t * 14.0))
        self._register_sample(sfx, 'select', samples, wet=0.30, decay=0.45)

        # 13. Game Over: Dramatic descending cathedral pipe organ chords
        n = int(sr * 0.68)
        samples = []
        sad_pitches = [392.0, 349.23, 329.63, 261.63]
        for i in range(n):
            t = i / sr
            idx = min(3, int(t / 0.17))
            f = sad_pitches[idx]
            local_t = t % 0.17
            o1 = math.sin(2.0 * math.pi * f * t) * 0.32
            o2 = math.sin(2.0 * math.pi * (f * 0.5) * t) * 0.25
            o3 = math.sin(2.0 * math.pi * (f * 1.5) * t) * 0.15
            samples.append((o1 + o2 + o3) * (1.0 - local_t / 0.17))
        self._register_sample(sfx, 'game_over', samples, wet=0.48, decay=0.65)

        # 14. Boss Core Hit: Heavy metallic armor clang + sub-bass impact
        n = int(sr * 0.25)
        samples = []
        for i in range(n):
            t = i / sr
            c1 = math.sin(2.0 * math.pi * 920.0 * t + 1.5 * math.sin(2.0 * math.pi * 1380.0 * t)) * 0.35
            c2 = math.sin(2.0 * math.pi * 1540.0 * t) * 0.28
            sub = math.sin(2.0 * math.pi * 75.0 * t) * math.exp(-t * 22.0) * 0.45
            noise = (rng.random() * 2.0 - 1.0) * 0.35 * math.exp(-t * 28.0)
            samples.append((c1 + c2 + sub + noise) * math.exp(-t * 12.0))
        self._register_sample(sfx, 'boss_hit', samples, wet=0.42, decay=0.58)

        # 15. Boss Awakening Roar: Menacing colossus screech + cavern sub-bass tremor
        n = int(sr * 0.58)
        samples = []
        for i in range(n):
            t = i / sr
            env = (1.0 - t / 0.58)
            screech_f = 580.0 - t * 420.0 + math.sin(2.0 * math.pi * 48.0 * t) * 95.0
            saw = 2.0 * ((screech_f * t) % 1.0) - 1.0
            sub = math.sin(2.0 * math.pi * 56.0 * t) * 0.48
            noise = (rng.random() * 2.0 - 1.0) * 0.24
            samples.append((saw * 0.32 + sub + noise) * env)
        self._register_sample(sfx, 'boss_roar', samples, wet=0.48, decay=0.65)

        # 16. Water Splash: Bubbly plunge & resonant droplet cascade
        n = int(sr * 0.24)
        samples = []
        for i in range(n):
            t = i / sr
            f = 220.0 + math.sin(2.0 * math.pi * 38.0 * t) * 95.0 + t * 260.0
            sine = math.sin(2.0 * math.pi * max(45.0, f) * t) * 0.38
            noise = (rng.random() * 2.0 - 1.0) * 0.32 * math.exp(-t * 14.0)
            env = max(0.0, 1.0 - t / 0.24)
            samples.append((sine + noise) * env)
        self._register_sample(sfx, 'splash', samples, wet=0.35, decay=0.50)

        # 17. Crunchy Stomp Thud ('stomp'):
        # Deep 62Hz sub-bass thud + bitcrushed 16-bit shell crunch + rising rebound pop
        n = int(sr * 0.19)
        samples = []
        held_noise = 0.0
        for i in range(n):
            t = i / sr
            # Sample-and-hold decimated crunch noise (every 6 samples = ~7.3kHz gritty SNES crunch)
            if i % 6 == 0:
                held_noise = (rng.random() * 2.0 - 1.0)
            crunch = held_noise * math.exp(-t * 26.0) * 0.52
            # Heavy sub-bass thud sweeping 135Hz -> 48Hz
            thud_f = 48.0 + 87.0 * math.exp(-t * 32.0)
            thud = math.sin(2.0 * math.pi * thud_f * t) * math.exp(-t * 16.0) * 0.68
            # Rising rebound harmonic pop after 35ms
            rebound = 0.0
            if t > 0.035:
                rt = t - 0.035
                rf = 165.0 + (rt / 0.155) * 410.0
                rebound = (4.0 * abs(((rf * rt) % 1.0) - 0.5) - 1.0) * (1.0 - rt / 0.155) * 0.38
            samples.append(crunch + thud + rebound)
        self._register_sample(sfx, 'stomp', samples, wet=0.32, decay=0.45)

        # 18. Power-Up Fanfare: Rich 16-bit triad fanfare (C4 - E4 - G4 - C5)
        n = int(sr * 0.40)
        samples = []
        fanfare_notes = [261.63, 329.63, 392.00, 523.25]
        for i in range(n):
            t = i / sr
            idx = min(3, int(t / 0.10))
            f = fanfare_notes[idx]
            local_t = t % 0.10
            sq = (1.0 if ((f * t) % 1.0) < 0.45 else -1.0) * 0.26
            sine = math.sin(2.0 * math.pi * f * t) * 0.28 + math.sin(2.0 * math.pi * (f * 1.5) * t) * 0.14
            env = max(0.0, 1.0 - local_t / 0.10)
            samples.append((sq + sine) * env)
        self._register_sample(sfx, 'powerup', samples, wet=0.38, decay=0.55)

        # 19. Dread Hound Bark: Deep mechanical beast bark with pitch drop
        n = int(sr * 0.24)
        samples = []
        for i in range(n):
            t = i / sr
            f = max(65.0, 240.0 - t * 750.0)
            saw = 2.0 * ((f * t) % 1.0) - 1.0
            noise = (rng.random() * 2.0 - 1.0) * 0.35
            env = max(0.0, 1.0 - t / 0.24)
            samples.append((saw * 0.4 + noise * 0.3) * env)
        self._register_sample(sfx, 'hound_bark', samples, wet=0.34, decay=0.48)

        # 20. Dread Hound Colossus Roar: Low sub-bass growl & resonant beast tremor
        n = int(sr * 0.65)
        samples = []
        for i in range(n):
            t = i / sr
            mod = math.sin(2.0 * math.pi * 18.0 * t) * 35.0
            f = max(45.0, 160.0 - t * 140.0 + mod)
            saw = 2.0 * ((f * t) % 1.0) - 1.0
            sub = math.sin(2.0 * math.pi * 52.0 * t) * 0.5
            noise = (rng.random() * 2.0 - 1.0) * 0.32
            env = math.sin(math.pi * (t / 0.65)) * (1.0 - t * 0.5)
            samples.append((saw * 0.35 + sub + noise) * env)
        self._register_sample(sfx, 'hound_roar', samples, wet=0.45, decay=0.62)

        # 21. Giga Toad Seismic Ground Pound Slam: Deep bass tremor + stone crash
        n = int(sr * 0.34)
        samples = []
        for i in range(n):
            t = i / sr
            f = max(38.0, 115.0 - t * 240.0)
            sub = math.sin(2.0 * math.pi * f * t) * 0.58
            noise = (rng.random() * 2.0 - 1.0) * 0.48 * max(0.0, 1.0 - t * 7.5)
            env = max(0.0, 1.0 - t / 0.34)
            samples.append((sub + noise) * env)
        self._register_sample(sfx, 'toad_slam', samples, wet=0.40, decay=0.58)

        # 22. Giga Toad Brawler Grunt: Guttural bullfrog combat roar
        n = int(sr * 0.22)
        samples = []
        for i in range(n):
            t = i / sr
            f = 95.0 + math.sin(2.0 * math.pi * 18.0 * t) * 25.0
            saw = (2.0 * ((f * t) % 1.0) - 1.0) * 0.45
            noise = (rng.random() * 2.0 - 1.0) * 0.25
            env = max(0.0, 1.0 - t / 0.22)
            samples.append((saw + noise) * env)
        self._register_sample(sfx, 'toad_grunt', samples, wet=0.32, decay=0.46)

        # 23. Crystal Ice Shattering ('ice_shatter'):
        # 6 inharmonic crystalline bell partials + high-frequency ice shard bursts + stereo reverb
        n = int(sr * 0.30)
        samples = []
        crystal_freqs = [1760.0, 2380.0, 3120.0, 3950.0, 4820.0, 5680.0]
        shard_offsets = [0.0, 0.025, 0.055, 0.095]
        for i in range(n):
            t = i / sr
            chime_sum = 0.0
            for idx, cf in enumerate(crystal_freqs):
                t_start = shard_offsets[idx % len(shard_offsets)]
                if t >= t_start:
                    lt = t - t_start
                    chime_sum += math.sin(2.0 * math.pi * cf * lt) * math.exp(-lt * (18.0 + idx * 3.5)) * 0.16
            shard_crack = (rng.random() * 2.0 - 1.0) * math.exp(-t * 28.0) * 0.42
            samples.append(chime_sum + shard_crack)
        self._register_sample(sfx, 'ice_shatter', samples, wet=0.50, decay=0.68)

        # 24. Waterfall Cooling Mist Sizzle ('sizzle_mist'):
        # Refreshing cool waterfall mist hiss + soothing harmonic fifth chime
        n = int(sr * 0.26)
        samples = []
        for i in range(n):
            t = i / sr
            mist_noise = (rng.random() * 2.0 - 1.0) * math.sin(math.pi * (t / 0.26)) * 0.28
            c1 = math.sin(2.0 * math.pi * 587.33 * t) * math.exp(-t * 10.0) * 0.25
            c2 = math.sin(2.0 * math.pi * 880.00 * t) * math.exp(-t * 10.0) * 0.22
            samples.append(mist_noise + c1 + c2)
        self._register_sample(sfx, 'sizzle_mist', samples, wet=0.44, decay=0.60)

        # 25. Submarine Air Bubble Refill Pop ('bubble_pop'):
        # Deep submarine resonant water bloop + crisp oxygen bubble pop
        n = int(sr * 0.20)
        samples = []
        for i in range(n):
            t = i / sr
            if t < 0.09:
                f = 260.0 + ((t / 0.09) ** 1.6) * 580.0
                bloop = math.sin(2.0 * math.pi * f * t) * math.sin(math.pi * (t / 0.09)) * 0.52
            else:
                t2 = t - 0.09
                f2 = 420.0 + ((t2 / 0.11) ** 1.8) * 760.0
                bloop = math.sin(2.0 * math.pi * f2 * t2) * math.exp(-t2 * 22.0) * 0.58
            samples.append(bloop)
        self._register_sample(sfx, 'bubble_pop', samples, wet=0.42, decay=0.58)

        # 26. Friendly NPC Frog Voice Blip ('npc_talk'):
        # Expressive 16-bit amphibian ribbit/croak formant blip for comic speech bubbles
        n = int(sr * 0.065)
        samples = []
        for i in range(n):
            t = i / sr
            f = 280.0 + math.sin(2.0 * math.pi * 24.0 * t) * 90.0 + (t / 0.065) * 140.0
            ribbit = math.sin(2.0 * math.pi * f * t + 1.4 * math.sin(2.0 * math.pi * (f * 2.0) * t))
            env = math.sin(math.pi * (t / 0.065))
            samples.append(ribbit * env * 0.36)
        self._register_sample(sfx, 'npc_talk', samples, wet=0.22, decay=0.32)

        # 27. Village Shopkeeper Purchase Chime ('shop_buy'):
        # Classic 16-bit merchant coin clink + bright major triad bell register
        n = int(sr * 0.28)
        samples = []
        for i in range(n):
            t = i / sr
            if t < 0.07:
                s = math.sin(2.0 * math.pi * 987.77 * t) * math.exp(-t * 24.0) * 0.45
            else:
                t2 = t - 0.07
                s = (
                    math.sin(2.0 * math.pi * 1318.51 * t2) * 0.35 +
                    math.sin(2.0 * math.pi * 1975.53 * t2) * 0.25
                ) * math.exp(-t2 * 12.0)
            samples.append(s)
        self._register_sample(sfx, 'shop_buy', samples, wet=0.38, decay=0.52)

        # 28. Slush Meltdown Splat ('splat'):
        n = int(sr * 0.28)
        samples = []
        for i in range(n):
            t = i / sr
            f = 180.0 - t * 320.0 + math.sin(2.0 * math.pi * 35.0 * t) * 45.0
            squelch = math.sin(2.0 * math.pi * max(40.0, f) * t) * 0.42
            noise = (rng.random() * 2.0 - 1.0) * 0.35 * math.exp(-t * 10.0)
            samples.append((squelch + noise) * (1.0 - t / 0.28))
        self._register_sample(sfx, 'splat', samples, wet=0.35, decay=0.48)

        # 29. Muhlaser Frogbeam Blast ('laser_beam'):
        # Sci-fi 16-bit plasma cannon discharge + resonant sub-bass beam hum
        n = int(sr * 0.38)
        samples = []
        for i in range(n):
            t = i / sr
            f = 880.0 * math.exp(-t * 4.5) + 140.0 + math.sin(2.0 * math.pi * 55.0 * t) * 45.0
            saw = (2.0 * ((f * t) % 1.0) - 1.0) * 0.38
            sub = math.sin(2.0 * math.pi * 82.0 * t) * 0.42
            spark = (rng.random() * 2.0 - 1.0) * 0.25 * math.exp(-t * 12.0)
            env = max(0.0, 1.0 - t / 0.38)
            samples.append((saw + sub + spark) * env)
        self._register_sample(sfx, 'laser_beam', samples, wet=0.42, decay=0.60)

        # 30. Shield Clang ('shield_clang'):
        # Metallic deflection ring when hitting an armored boss shield
        n = int(sr * 0.16)
        samples = []
        for i in range(n):
            t = i / sr
            ring = (
                math.sin(2.0 * math.pi * 1240.0 * t) * 0.38 +
                math.sin(2.0 * math.pi * 1890.0 * t) * 0.28 +
                math.sin(2.0 * math.pi * 2720.0 * t) * 0.18
            ) * math.exp(-t * 24.0)
            samples.append(ring)
        self._register_sample(sfx, 'shield_clang', samples, wet=0.35, decay=0.48)

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

        # 1. Prefer high-fidelity Standard MIDI soundtrack (.mid)
        midi_path = self.midi_files.get(track_name)
        if midi_path and os.path.exists(midi_path):
            try:
                pygame.mixer.music.load(midi_path)
                pygame.mixer.music.set_volume(0.65)
                pygame.mixer.music.play(-1)
                self.current_track_name = track_name
                return
            except Exception as err:
                print(f"[Audio Engine] Notice: MIDI playback error ({err}), falling back to synthesized track.")

        # 2. Fall back to synthesized Chiptune PCM sample buffers
        track = self.music_tracks.get(track_name)
        if track:
            self.current_track_name = track_name
            self.music_channel.play(track, loops=-1)

    def stop_music(self):
        if self.enabled:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
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
        if getattr(sys, 'frozen', False):
            _bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
            self.base_dir = os.path.join(_bundle_dir, "assets")
            if not os.path.exists(self.base_dir):
                self.base_dir = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "assets")
        else:
            self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        if HAS_ASSET_GENERATOR:
            generate_assets.build_all_assets(force=False)

        self.autotiles = {"jungle": {}, "sanctum": {}, "ice": {}, "volcanic": {}, "underwater": {}}
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
        # 1. Load 16-variant 4-bit Auto-Tile Sets (Jungle, Sanctum, Glacial Ice, Volcanic & Underwater)
        fallback_colors = {
            "jungle": (56, 72, 102),
            "sanctum": (62, 28, 54),
            "ice": (65, 125, 195),
            "volcanic": (95, 32, 24),
            "underwater": (28, 95, 118),
        }
        for theme, prefix in [
            ("jungle", "terrain"),
            ("sanctum", "sanctum"),
            ("ice", "ice"),
            ("volcanic", "volcanic"),
            ("underwater", "underwater"),
        ]:
            for mask in range(16):
                surf = self._load_png("tiles", f"{prefix}_{mask}.png")
                if surf is None:
                    surf = pygame.Surface((16, 16))
                    surf.fill(fallback_colors.get(theme, (56, 72, 102)))
                self.autotiles[theme][mask] = surf
            alt = self._load_png("tiles", f"{prefix}_15_alt.png")
            self.autotiles[theme]["15_alt"] = alt if alt else self.autotiles[theme][15]

        # 2. Load Special Interactive Tiles (Grapple Idol, Doors, Animated Water, Magma, Waterfall Mist, Bubble Vents)
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
        self.special_tiles["lava"] = [
            self._load_png("tiles", f"lava_{i}.png") for i in range(4)
        ]
        self.special_tiles["waterfall"] = [
            self._load_png("tiles", f"waterfall_{i}.png") for i in range(4)
        ]
        self.special_tiles["bubble_vent"] = [
            self._load_png("tiles", f"bubble_vent_{i}.png") for i in range(2)
        ]
        self.special_tiles["burrow_rock"] = [
            self._load_png("tiles", f"burrow_rock_{i}.png") for i in range(2)
        ]
        self.special_tiles["master_key_door"] = self._load_png("tiles", "master_key_door.png")
        self.special_tiles["master_key_door_states"] = [
            self._load_png("tiles", f"master_key_door_state_{i}.png") for i in range(5)
        ]
        self.special_tiles["metroid_door_cyan"] = self._load_png("tiles", "metroid_door_cyan.png")
        self.special_tiles["metroid_door_red"] = self._load_png("tiles", "metroid_door_red.png")

        # 2B. Key Fragments & Master Key Icons
        self.key_icons = {
            "mantis": self._load_png("sprites", "key_fragment_mantis.png"),
            "hound": self._load_png("sprites", "key_fragment_hound.png"),
            "toad": self._load_png("sprites", "key_fragment_toad.png"),
            "falo": self._load_png("sprites", "key_fragment_falo.png"),
            "master": self._load_png("sprites", "master_key.png"),
        }

        # 3. Load Lush Foliage & Storytelling Props
        self.props["fern"] = [self._load_png("props", f"fern_{i}.png") for i in range(3)]
        self.props["grass"] = [self._load_png("props", f"grass_{i}.png") for i in range(2)]
        self.props["shroom_cyan"] = self._load_png("props", "shroom_cyan.png")
        self.props["shroom_magenta"] = self._load_png("props", "shroom_magenta.png")
        self.props["shroom_gold"] = self._load_png("props", "shroom_gold.png")
        self.props["frog_statue"] = self._load_png("props", "frog_statue.png")
        self.props["mantis_totem"] = self._load_png("props", "mantis_totem.png")
        self.props["checkpoint_totem"] = self._load_png("props", "checkpoint_totem.png")

        # 4. Load Additive Radial Light Maps (`BLEND_RGB_ADD`)
        for lname in ("cyan", "emerald", "gold", "magenta", "crimson", "orange", "player"):
            lsurf = self._load_png("fx", f"light_{lname}.png", convert_alpha=False)
            if lsurf is None:
                lsurf = pygame.Surface((64, 64))
            self.lights[lname] = lsurf

        # 5. Load 640x360 16-Bit Pixel-Art Backgrounds & Parallax Layers
        for bg_key in ("canopy", "temple", "cavern", "sanctum", "ice", "volcanic", "underwater"):
            ai_bg = self._load_png("backgrounds", f"bg_{bg_key}.png", convert_alpha=False)
            proc_bg = self._load_png("backgrounds", f"proc_{bg_key}_sky.png", convert_alpha=False)
            self.backgrounds[bg_key] = ai_bg if ai_bg is not None else proc_bg
            self.parallax_mid[bg_key] = self._load_png("backgrounds", f"parallax_{bg_key}_mid.png", convert_alpha=True)

        # 5B. High-Fidelity Hand-Drawn Legend of Mana Style Layered Backgrounds
        jungle_bg = self._load_png("backgrounds", "jungle_ruins_bg.png", convert_alpha=False)
        if jungle_bg is not None:
            self.backgrounds["canopy"] = jungle_bg
            self.backgrounds["temple"] = jungle_bg

    def build_froggy_animations(self):
        """Loads upgraded multi-shaded Froggy sprites (with flip for left-facing)."""
        raw_frames = {
            "idle": [
                self._load_png("sprites", "froggy_idle_0.png"),
                self._load_png("sprites", "froggy_idle_1.png"),
                self._load_png("sprites", "froggy_idle_2.png"),
                self._load_png("sprites", "froggy_idle_3.png"),
            ],
            "run": [
                self._load_png("sprites", "froggy_run_0.png"),
                self._load_png("sprites", "froggy_run_1.png"),
                self._load_png("sprites", "froggy_run_2.png"),
                self._load_png("sprites", "froggy_run_3.png"),
            ],
            "jump": [
                self._load_png("sprites", "froggy_jump_0.png"),
                self._load_png("sprites", "froggy_jump_1.png"),
            ],
            "fall": [
                self._load_png("sprites", "froggy_fall_0.png"),
                self._load_png("sprites", "froggy_fall_1.png"),
            ],
            "wall_slide": [
                self._load_png("sprites", "froggy_wall_0.png"),
                self._load_png("sprites", "froggy_wall_1.png"),
            ],
            "tongue": [
                self._load_png("sprites", "froggy_tongue_0.png"),
                self._load_png("sprites", "froggy_tongue_1.png"),
            ],
            "swim": [
                self._load_png("sprites", "froggy_swim_0.png"),
                self._load_png("sprites", "froggy_swim_1.png"),
                self._load_png("sprites", "froggy_swim_2.png"),
                self._load_png("sprites", "froggy_swim_3.png"),
            ],
            "swing": [
                self._load_png("sprites", "froggy_swing_0.png"),
                self._load_png("sprites", "froggy_swing_1.png"),
            ],
            "hurt": [
                self._load_png("sprites", "froggy_hurt_0.png"),
            ],
        }
        animations = {"right": {}, "left": {}}
        for state_name, surface_list in raw_frames.items():
            valid_list = [s for s in surface_list if s is not None]
            if not valid_list:
                fallback = pygame.Surface((32, 32), pygame.SRCALPHA)
                fallback.fill((65, 175, 75))
                valid_list = [fallback]
            animations["right"][state_name] = valid_list
            animations["left"][state_name] = [
                pygame.transform.flip(surf, True, False) for surf in valid_list
            ]
        return animations

    def build_enemy_animations(self):
        """Loads all troop enemies, Colossus bosses, and power-up relics."""
        # 1. Spiked Moss Beetle
        b0 = self._load_png("sprites", "beetle_0.png")
        b1 = self._load_png("sprites", "beetle_1.png")
        if b0 is None: b0 = pygame.Surface((24, 20), pygame.SRCALPHA)
        if b1 is None: b1 = b0
        b_stun = pygame.transform.flip(b0, False, True)

        # 2. Neon Buzzfly
        f0 = self._load_png("sprites", "fly_0.png")
        f1 = self._load_png("sprites", "fly_1.png")
        if f0 is None: f0 = pygame.Surface((20, 20), pygame.SRCALPHA)
        if f1 is None: f1 = f0

        # 3. Soldier Ant ('N')
        a0 = self._load_png("sprites", "ant_0.png")
        a1 = self._load_png("sprites", "ant_1.png")
        a_chg = self._load_png("sprites", "ant_charge.png")
        if a0 is None: a0 = pygame.Surface((24, 22), pygame.SRCALPHA)
        if a1 is None: a1 = a0
        if a_chg is None: a_chg = a0
        a_stun = pygame.transform.flip(a0, False, True)

        # 4. Shadow Spider ('W')
        sp0 = self._load_png("sprites", "spider_0.png")
        sp1 = self._load_png("sprites", "spider_1.png")
        sp_drop = self._load_png("sprites", "spider_drop.png")
        if sp0 is None: sp0 = pygame.Surface((24, 22), pygame.SRCALPHA)
        if sp1 is None: sp1 = sp0
        if sp_drop is None: sp_drop = sp0
        sp_stun = pygame.transform.flip(sp0, False, True)

        # 5. Emperor Mantis Boss ('M')
        m_arm_r = self._load_png("sprites", "mantis_armored.png")
        m_arm_l = pygame.transform.flip(m_arm_r, True, False) if m_arm_r else None
        m_exp_r = self._load_png("sprites", "mantis_exposed.png")
        m_exp_l = pygame.transform.flip(m_exp_r, True, False) if m_exp_r else None

        # 6. The Dread Hound Colossus Boss ('H')
        h_idle = self._load_png("sprites", "hound_idle.png")
        h_idle_1 = self._load_png("sprites", "hound_idle_1.png")
        h_lunge = self._load_png("sprites", "hound_lunge.png")
        h_dazed = self._load_png("sprites", "hound_dazed.png")
        h_howl = self._load_png("sprites", "hound_howl.png")
        h_proj = self._load_png("sprites", "hound_projectile.png")

        # 6B. Giga Toad Melee Brawler Boss ('Q')
        t_idle = self._load_png("sprites", "toad_idle.png")
        t_idle_1 = self._load_png("sprites", "toad_idle_1.png")
        t_walk_0 = self._load_png("sprites", "toad_walk_0.png")
        t_walk_1 = self._load_png("sprites", "toad_walk_1.png")
        t_slam = self._load_png("sprites", "toad_slam.png")
        t_punch = self._load_png("sprites", "toad_punch.png")
        t_dazed = self._load_png("sprites", "toad_dazed.png")
        t_enrage = self._load_png("sprites", "toad_enraged.png")

        # 7. Collectible Power-ups & Special Weapon Sprites
        p_boots = self._load_png("sprites", "powerup_boots.png")
        p_red_boom = self._load_png("sprites", "powerup_red_boomerang.png")
        p_muhlaser = self._load_png("sprites", "powerup_muhlaser.png")
        boom_red = self._load_png("sprites", "boomerang_red.png")

        # 8. Icy World Enemies: Stink Bug, Ice Wolf Spider & Falo Snowman Boss
        sb0 = self._load_png("sprites", "stink_bug_0.png")
        sb1 = self._load_png("sprites", "stink_bug_1.png")
        sp_camo = self._load_png("sprites", "ice_spider_camo.png")
        sp_stalk = self._load_png("sprites", "ice_spider_stalk.png")
        sp_leap = self._load_png("sprites", "ice_spider_leap.png")
        f_idle = self._load_png("sprites", "falo_idle.png")
        f_throw = self._load_png("sprites", "falo_throw.png")
        f_melt = self._load_png("sprites", "falo_melt.png")

        # 8B. Underwater Enemies & Demon Shark Boss
        pir0 = self._load_png("sprites", "piranha_0.png")
        pir1 = self._load_png("sprites", "piranha_1.png")
        if pir0 is None: pir0 = pygame.Surface((28, 20), pygame.SRCALPHA)
        if pir1 is None: pir1 = pir0
        ang0 = self._load_png("sprites", "angler_0.png")
        ang1 = self._load_png("sprites", "angler_1.png")
        if ang0 is None: ang0 = pygame.Surface((32, 26), pygame.SRCALPHA)
        if ang1 is None: ang1 = ang0
        jel0 = self._load_png("sprites", "jelly_0.png")
        jel1 = self._load_png("sprites", "jelly_1.png")
        if jel0 is None: jel0 = pygame.Surface((24, 28), pygame.SRCALPHA)
        if jel1 is None: jel1 = jel0
        sh_idle = self._load_png("sprites", "shark_idle.png")
        sh_idle_1 = self._load_png("sprites", "shark_idle_1.png")
        sh_charge = self._load_png("sprites", "shark_charge.png")
        sh_dazed = self._load_png("sprites", "shark_dazed.png")
        sh_enraged = self._load_png("sprites", "shark_enraged.png")

        # 9. Friendly NPC Frogs (Elder Tree Frog & Village Shopkeeper)
        elder_frames = [self._load_png("sprites", f"npc_elder_{i}.png") for i in range(4)]
        shop_frames = [self._load_png("sprites", f"npc_shopkeeper_{i}.png") for i in range(4)]

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
            "ant": {
                "right": [a0, a1],
                "left": [pygame.transform.flip(a0, True, False), pygame.transform.flip(a1, True, False)],
                "charge_right": a_chg,
                "charge_left": pygame.transform.flip(a_chg, True, False),
                "stunned": [a_stun, pygame.transform.flip(a_stun, True, False)],
            },
            "spider": {
                "idle": [sp0, sp1],
                "drop": sp_drop,
                "stunned": [sp_stun],
            },
            "mantis": {
                "armored_right": m_arm_r,
                "armored_left": m_arm_l,
                "exposed_right": m_exp_r,
                "exposed_left": m_exp_l,
            },
            "hound": {
                "idle": h_idle,
                "idle_1": h_idle_1 if h_idle_1 is not None else h_idle,
                "lunge": h_lunge,
                "dazed": h_dazed,
                "howl": h_howl,
                "projectile": h_proj,
            },
            "toad": {
                "idle": t_idle,
                "idle_1": t_idle_1 if t_idle_1 is not None else t_idle,
                "walk_0": t_walk_0 if t_walk_0 is not None else t_idle,
                "walk_1": t_walk_1 if t_walk_1 is not None else t_idle,
                "slam": t_slam,
                "punch": t_punch,
                "dazed": t_dazed,
                "enraged": t_enrage,
            },
            "powerups": {
                "stomping_boots": p_boots,
                "red_boomerang": p_red_boom,
                "muhlaser": p_muhlaser,
                "boomerang_red": boom_red,
            },
            "stink_bug": {
                "right": [sb0, sb1] if sb0 and sb1 else [],
                "left": [pygame.transform.flip(sb0, True, False), pygame.transform.flip(sb1, True, False)] if sb0 and sb1 else [],
            },
            "ice_spider": {
                "camo": sp_camo,
                "stalk_right": sp_stalk,
                "stalk_left": pygame.transform.flip(sp_stalk, True, False) if sp_stalk else None,
                "leap": sp_leap,
                "leap_right": sp_leap,
                "leap_left": pygame.transform.flip(sp_leap, True, False) if sp_leap else None,
            },
            "falo": {
                "idle": f_idle,
                "throw": f_throw,
                "melt": f_melt,
            },
            "piranha": {
                "right": [pir0, pir1],
                "left": [pygame.transform.flip(pir0, True, False), pygame.transform.flip(pir1, True, False)],
            },
            "angler": {
                "right": [ang0, ang1],
                "left": [pygame.transform.flip(ang0, True, False), pygame.transform.flip(ang1, True, False)],
            },
            "jelly": {
                "idle": [jel0, jel1],
            },
            "shark": {
                "idle": sh_idle,
                "idle_1": sh_idle_1 if sh_idle_1 is not None else sh_idle,
                "charge": sh_charge if sh_charge is not None else sh_idle,
                "dazed": sh_dazed if sh_dazed is not None else sh_idle,
                "enraged": sh_enraged if sh_enraged is not None else sh_idle,
            },
            "npc_elder": [s for s in elder_frames if s is not None],
            "npc_shopkeeper": [s for s in shop_frames if s is not None],
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

# =============================================================================
# CHAPTER 5. MODULAR WORLD BLUEPRINTS & METROIDVANIA ZONE REGISTRY
# =============================================================================
# Level blueprints and room geometry have been cleanly modularized into `world_data.py`.
# This allows viewing, editing, adding, and tweaking levels via `py level_studio.py`
# without needing to modify or load the entire 7,000+ line engine context!
import world_data
from world_data import (
    WORLD_BLUEPRINTS,
    TILE_LEGEND,
    ZONE_THEMES,
    list_zones,
    get_zone,
    create_blank_zone,
    save_zone,
)


# =============================================================================
# CHAPTER 6. PARTICLES & BOOMERANG / SCYTHE PROJECTILES
# =============================================================================

class Particle:
    def __init__(self, x, y, vx, vy, color, lifetime, radius=2.0):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.color = color
        self.lifetime = lifetime
        self.radius = float(radius)
        self.age = 0

    def update(self):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.14

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        size = int(max(1, round(self.radius * max(0.2, (self.lifetime - self.age) / self.lifetime))))
        if size <= 1:
            surface.set_at((sx, sy), self.color)
        else:
            pygame.draw.circle(surface, self.color, (sx, sy), size)


class SporeBoomerang:
    """
    Froggy's Special Weapon (R Button):
    Launches a glowing bioluminescent spore along the 8-way D-Pad aim
    vector, then decelerates and accelerates backward to return like a boomerang!
    
    When upgraded with the Red Spore Boomerang Relic (vanquishing the Mantis):
      - Fires up to 4 simultaneous boomerangs
      - Flies with increased speed (8.2 px/frame) and extended range (175 frames)
      - Crimson trail and piercing force that damages bosses and shatters armor!
    """
    def __init__(self, x, y, dir_x, dir_y, is_red=False):
        self.x = float(x)
        self.y = float(y)
        self.is_red = is_red
        speed = 8.2 if is_red else 6.6
        self.vx = dir_x * speed
        self.vy = dir_y * speed
        accel = 0.08 if is_red else 0.14
        self.return_ax = -dir_x * accel
        self.return_ay = -dir_y * accel
        self.age = 0
        self.max_age = 175 if is_red else 115
        self.radius = 6 if is_red else 5
        self.alive = True

    def update(self, room, audio=None):
        self.age += 1
        self.vx += self.return_ax
        self.vy += self.return_ay
        self.x += self.vx
        self.y += self.vy

        # Trail particles
        if self.age % 4 == 0:
            p_col = COLOR_BOOMERANG_RED if self.is_red else COLOR_SPORE_CYAN
            room.spawn_particle_burst(self.x, self.y, p_col, count=2)

        hit_box = pygame.Rect(int(self.x - 7), int(self.y - 7), 14, 14)

        for enemy in room.enemies:
            if enemy.alive and enemy.state not in ("YANKED",) and not enemy.is_boss and enemy.rect.colliderect(hit_box):
                enemy.stun(knockback_dir_x=(1.0 if self.vx >= 0 else -1.0))
                p_col = COLOR_BOOMERANG_RED if self.is_red else COLOR_SPORE_CYAN
                room.spawn_particle_burst(enemy.center_x, enemy.center_y, p_col, count=10)
                if audio:
                    audio.play_sfx("stun")

        boss = room.get_active_boss()
        if boss and boss.alive and boss.awakened and boss.rect.colliderect(hit_box):
            if hasattr(boss, "hit_by_spore_boomerang"):
                if boss.hit_by_spore_boomerang(room, is_red=self.is_red):
                    self.alive = False
                    if audio:
                        audio.play_sfx("stun")

        if self.age >= self.max_age:
            self.alive = False

    def draw(self, surface, camera_x, camera_y, assets=None):
        screen_x = int(self.x - camera_x)
        screen_y = int(self.y - camera_y)
        l_key = "crimson" if self.is_red else "cyan"
        if assets and l_key in assets.lights:
            lt = assets.lights[l_key]
            surface.blit(lt, (screen_x - lt.get_width() // 2, screen_y - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        
        main_col = COLOR_BOOMERANG_RED if self.is_red else COLOR_SPORE_CYAN
        angle = self.age * (0.45 if self.is_red else 0.35)
        for i in range(4):
            blade_angle = angle + i * (math.pi * 0.5)
            length = 7 if self.is_red else 6
            bx = screen_x + int(math.cos(blade_angle) * length)
            by = screen_y + int(math.sin(blade_angle) * length)
            pygame.draw.line(surface, main_col, (screen_x, screen_y), (bx, by), 2)
        pygame.draw.circle(surface, (255, 255, 255), (screen_x, screen_y), 2)


class HoundFireball:
    """Cursed fireball launched by The Dread Hound Colossus."""
    def __init__(self, x, y, vx, vy, is_flame=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.is_flame = is_flame
        self.radius = 7
        self.age = 0
        self.max_age = 180
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x - 6), int(self.y - 6), 12, 12)

    def update(self, room):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        if self.is_flame:
            self.y += math.sin(self.age * 0.14) * 0.9
        if self.age >= self.max_age or room.is_point_inside_solid(self.x, self.y):
            self.alive = False
            room.spawn_particle_burst(self.x, self.y, (255, 90, 50), count=6)

    def draw(self, surface, camera_x, camera_y, assets=None):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        if assets and "crimson" in assets.lights:
            lt = assets.lights["crimson"]
            surface.blit(lt, (sx - lt.get_width() // 2, sy - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        sp = None
        if assets and hasattr(assets, "enemy_anims") and "hound" in assets.enemy_anims:
            sp = assets.enemy_anims["hound"].get("projectile")
        elif assets:
            sp = getattr(assets, "hound_projectile_cache", None)
            if sp is None:
                sp = assets._load_png("sprites", "hound_projectile.png")
                assets.hound_projectile_cache = sp
        if sp:
            surface.blit(sp, (sx - sp.get_width() // 2, sy - sp.get_height() // 2))
        else:
            pygame.draw.circle(surface, (255, 55, 45), (sx, sy), self.radius)
            pygame.draw.circle(surface, (255, 235, 90), (sx, sy), 3)


class CollectiblePowerup:
    """
    Collectible Metroidvania Relics & Colossi Key Fragments:
      - 'stomping_boots' / 'J': Enables Mario-style enemy stomping by jumping on top of them.
      - 'red_boomerang' / 'R': Upgrades Spore Boomerang to 4 simultaneous shots, extended range & higher damage.
      - 'KEY_MANTIS': Mantis Jade Crest (from Emperor Mantis).
      - 'KEY_HOUND': Hound Obsidian Fang (from The Dread Hound).
      - 'KEY_TOAD': Toad Ruby Sigil (from Giga Toad).
      - 'KEY_FALO': Falo Glacial Core (from Falo the Snowman).
      - 'MASTER_KEY': Master Key of the Ancients.
    """
    def __init__(self, x, y, kind, assets=None):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.assets = assets
        self.width = 24 if "KEY" in str(kind) else 20
        self.height = 24 if "KEY" in str(kind) else 20
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        self.anim_timer = 0
        self.collected = False

    @property
    def center_x(self):
        return self.x + self.width * 0.5

    @property
    def center_y(self):
        return self.y + self.height * 0.5

    def update(self, player, room, audio=None):
        if self.collected:
            return
        self.anim_timer += 1
        hover_offset = math.sin(self.anim_timer * 0.08) * 3.0
        self.rect.y = int(self.y + hover_offset)

        if self.rect.colliderect(player.rect):
            self.collected = True
            frag_map = {
                "KEY_MANTIS": ("mantis", "MANTIS JADE CREST", (40, 230, 110)),
                "KEY_HOUND": ("hound", "HOUND OBSIDIAN FANG", (245, 65, 55)),
                "KEY_TOAD": ("toad", "TOAD RUBY SIGIL", (255, 205, 45)),
                "KEY_FALO": ("falo", "FALO GLACIAL CORE", (85, 220, 255)),
            }
            if self.kind in frag_map:
                fid, fname, pcol = frag_map[self.kind]
                player.key_fragments.add(fid)
                room.spawn_particle_burst(self.center_x, self.center_y, pcol, count=35)
                count = len(player.key_fragments)
                if count >= 4:
                    player.has_master_key = True
                    room.show_banner("ALL 4 FRAGMENTS ASSEMBLED INTO THE MASTER KEY!")
                else:
                    room.show_banner(f"KEY FRAGMENT ({count}/4): {fname}!")
                if audio:
                    audio.play_sfx("powerup")
            elif self.kind == "MASTER_KEY":
                player.has_master_key = True
                room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=45)
                room.show_banner("ACQUIRED THE MASTER KEY OF THE ANCIENTS!")
                if audio:
                    audio.play_sfx("powerup")
            elif self.kind in ("stomping_boots", "J"):
                player.has_stomping_boots = True
                room.spawn_particle_burst(self.center_x, self.center_y, (255, 215, 70), count=25)
                room.show_banner("POWER-UP: STOMPING BOOTS! JUMP ON TOP OF FOES TO CRUSH THEM!")
                if audio:
                    audio.play_sfx("powerup")
            elif self.kind in ("red_boomerang", "R"):
                player.has_red_boomerang = True
                room.spawn_particle_burst(self.center_x, self.center_y, (255, 60, 80), count=25)
                room.show_banner("UPGRADE: RED SPORE BOOMERANG! QUAD SHOT & PIERCING POWER!")
                if audio:
                    audio.play_sfx("powerup")

    def draw(self, surface, camera_x, camera_y):
        if self.collected:
            return
        sx = int(self.x - camera_x)
        sy = int(self.rect.y - camera_y)
        
        # Light aura
        light_key = "gold"
        if self.kind in ("red_boomerang", "R", "KEY_HOUND"):
            light_key = "crimson"
        elif self.kind == "KEY_MANTIS":
            light_key = "emerald"
        elif self.kind == "KEY_FALO":
            light_key = "cyan"
        elif self.kind in ("stomping_boots", "J", "KEY_TOAD", "MASTER_KEY"):
            light_key = "gold"

        if self.assets and light_key in getattr(self.assets, "lights", {}):
            lt = self.assets.lights[light_key]
            surface.blit(lt, (sx + self.width // 2 - lt.get_width() // 2, sy + self.height // 2 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        # Draw Sprite
        sprite = None
        if self.assets:
            if self.kind in ("stomping_boots", "J"):
                sprite = self.assets._load_png("sprites", "powerup_boots.png")
            elif self.kind in ("red_boomerang", "R"):
                sprite = self.assets._load_png("sprites", "powerup_red_boomerang.png")
            elif self.kind == "KEY_MANTIS":
                sprite = getattr(self.assets, "key_icons", {}).get("mantis") or self.assets._load_png("sprites", "key_fragment_mantis.png")
            elif self.kind == "KEY_HOUND":
                sprite = getattr(self.assets, "key_icons", {}).get("hound") or self.assets._load_png("sprites", "key_fragment_hound.png")
            elif self.kind == "KEY_TOAD":
                sprite = getattr(self.assets, "key_icons", {}).get("toad") or self.assets._load_png("sprites", "key_fragment_toad.png")
            elif self.kind == "KEY_FALO":
                sprite = getattr(self.assets, "key_icons", {}).get("falo") or self.assets._load_png("sprites", "key_fragment_falo.png")
            elif self.kind == "MASTER_KEY":
                sprite = getattr(self.assets, "key_icons", {}).get("master") or self.assets._load_png("sprites", "master_key.png")

        if sprite:
            surface.blit(sprite, (sx + (self.width - sprite.get_width()) // 2, sy + (self.height - sprite.get_height()) // 2))
        else:
            col = (255, 215, 70)
            if self.kind == "KEY_MANTIS": col = (40, 230, 110)
            elif self.kind == "KEY_HOUND": col = (245, 65, 55)
            elif self.kind == "KEY_TOAD": col = (255, 205, 45)
            elif self.kind == "KEY_FALO": col = (85, 220, 255)
            elif self.kind in ("red_boomerang", "R"): col = (255, 60, 80)
            pygame.draw.rect(surface, col, (sx, sy, self.width, self.height), border_radius=4)


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
        self.flash_timer = 0
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

    def stomp_kill(self, room):
        """Mario-style stomp: defeats enemy and scatters star particles."""
        self.alive = False
        room.spawn_particle_burst(self.center_x, self.center_y, (255, 230, 90), count=14)


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
        f_timer = getattr(self, "flash_timer", 0)
        if f_timer > 0 and (f_timer // 2) % 2 == 1:
            flash_surf = create_silhouette_flash(sprite)
            if flash_surf:
                surface.blit(flash_surf, (sx, sy))

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
        f_timer = getattr(self, "flash_timer", 0)
        if f_timer > 0 and (f_timer // 2) % 2 == 1:
            flash_surf = create_silhouette_flash(sprite)
            if flash_surf:
                surface.blit(flash_surf, (sx, sy))


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
        f_timer = getattr(self, "flash_timer", 0)
        if f_timer > 0 and (f_timer // 2) % 2 == 1:
            flash_surf = create_silhouette_flash(sprite)
            if flash_surf:
                surface.blit(flash_surf, (sx, sy))


class SoldierAnt(BaseEnemy):
    """
    Soldier Ant ('N') - Armored Ground Charger:
    Patrols stone platforms, sensing ledges and walls so it never falls off cliffs.
    When Froggy enters its horizontal line-of-sight, the ant stops, quivers its
    antennae, and charges forward with snapping mandibles at high velocity!
    Can be stunned with the tongue/boomerang, eaten, or stomped with Stomping Boots.
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y + 2, width=18, height=16)
        self.anims = enemy_anims.get("ant", {})
        self.patrol_speed = 0.95
        self.charge_speed = 3.2
        self.facing_right = True
        self.vx = self.patrol_speed
        self.state = "PATROL"  # "PATROL", "WINDUP", "CHARGING", "STUNNED", "YANKED"
        self.windup_timer = 0
        self.charge_timer = 0
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

        player = room.active_player_ref

        if self.state == "PATROL":
            self.vx = self.patrol_speed if self.facing_right else -self.patrol_speed
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=True)

            # Line of Sight detection to initiate mandibular charge!
            if player and abs(player.center_y - self.center_y) < 24:
                dist_x = player.center_x - self.center_x
                if (self.facing_right and 0 < dist_x < 140) or (not self.facing_right and -140 < dist_x < 0):
                    self.state = "WINDUP"
                    self.windup_timer = 18
                    self.vx = 0.0

        elif self.state == "WINDUP":
            self.windup_timer -= 1
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=False)
            if self.windup_timer <= 0:
                self.state = "CHARGING"
                self.charge_timer = 65
                self.vx = self.charge_speed if self.facing_right else -self.charge_speed

        elif self.state == "CHARGING":
            self.charge_timer -= 1
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=False)
            if self.charge_timer <= 0:
                self.state = "PATROL"
                self.facing_right = not self.facing_right

    def _move_and_collide(self, room, turn_at_ledges):
        self.x += self.vx
        self.rect.x = int(round(self.x))
        hit_wall = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vx > 0:
                    self.rect.right = tile.left
                    self.facing_right = False
                elif self.vx < 0:
                    self.rect.left = tile.right
                    self.facing_right = True
                self.x = float(self.rect.x)
                hit_wall = True
                if self.state == "CHARGING":
                    self.state = "PATROL"
                    room.spawn_particle_burst(self.center_x, self.center_y, (255, 180, 70), count=6)
                break

        if hit_wall and self.state == "PATROL":
            self.vx = self.patrol_speed if self.facing_right else -self.patrol_speed

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

        if turn_at_ledges and on_ground and self.state == "PATROL":
            feeler_x = self.rect.right + 3 if self.facing_right else self.rect.left - 3
            feeler_y = self.rect.bottom + 3
            if not room.is_point_inside_solid(feeler_x, feeler_y):
                self.facing_right = not self.facing_right

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return
        sx = int(self.rect.x - 3 - camera_x)
        sy = int(self.rect.y - 3 - camera_y)
        facing_key = "right" if self.facing_right else "left"

        if self.state in ("STUNNED", "YANKED"):
            frames = self.anims.get("stunned", [])
            sprite = frames[0] if frames else None
        elif self.state in ("WINDUP", "CHARGING"):
            sprite = self.anims.get(f"charge_{facing_key}")
        else:
            frames = self.anims.get(facing_key, [])
            sprite = frames[(self.anim_timer // 6) % len(frames)] if frames else None

        if sprite:
            surface.blit(sprite, (sx, sy))
        f_timer = getattr(self, "flash_timer", 0)
        if f_timer > 0 and (f_timer // 2) % 2 == 1:
            flash_surf = create_silhouette_flash(sprite)
            if flash_surf:
                surface.blit(flash_surf, (sx, sy))
        else:
            col = (220, 80, 50) if self.state == "CHARGING" else (160, 65, 45)
            pygame.draw.rect(surface, col, (int(self.x - camera_x), int(self.y - camera_y), self.width, self.height))


class ShadowSpider(BaseEnemy):
    """
    Shadow Spider ('W') - Ceiling Web Ambusher:
    Hangs high above on an invisible silk anchor point. When Froggy passes
    underneath, it drops down rapidly on a glistening silk thread, snapping
    its venomous fangs, before reeling back up to the ceiling shadows!
    Froggy can whip it directly with his tongue or stomp it with Stomping Boots.
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y, width=18, height=16)
        self.anims = enemy_anims.get("spider", {})
        self.anchor_x = float(spawn_x + 9)
        self.anchor_y = float(spawn_y)
        self.silk_length = 4.0
        self.max_drop_length = 95.0
        self.state = "CEILING"  # "CEILING", "DROP", "HANG", "ASCEND", "STUNNED", "YANKED"
        self.hang_timer = 0
        self.can_yank_immediately = True

    def update(self, room):
        self.anim_timer += 1
        if self.state == "YANKED":
            return

        if self.state == "STUNNED":
            self.stun_timer -= 1
            self.silk_length += 0.5
            self.y = self.anchor_y + self.silk_length
            self.rect.y = int(round(self.y))
            if self.stun_timer <= 0:
                self.state = "ASCEND"
            return

        player = room.active_player_ref

        if self.state == "CEILING":
            self.silk_length = 4.0
            if player and abs(player.center_x - self.anchor_x) < 36 and player.y > self.anchor_y:
                self.state = "DROP"

        elif self.state == "DROP":
            self.silk_length += 4.5
            if (self.silk_length >= self.max_drop_length or
                    room.is_point_inside_solid(self.anchor_x, self.anchor_y + self.silk_length + 8)):
                self.state = "HANG"
                self.hang_timer = 45

        elif self.state == "HANG":
            self.hang_timer -= 1
            if self.hang_timer <= 0:
                self.state = "ASCEND"

        elif self.state == "ASCEND":
            self.silk_length -= 1.8
            if self.silk_length <= 4.0:
                self.silk_length = 4.0
                self.state = "CEILING"

        self.x = self.anchor_x - self.width * 0.5
        self.y = self.anchor_y + self.silk_length
        self.rect.topleft = (int(round(self.x)), int(round(self.y)))

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return
        ax_s = int(self.anchor_x - camera_x)
        ay_s = int(self.anchor_y - camera_y)
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        # Draw glowing silk web thread
        pygame.draw.line(surface, (230, 245, 255), (ax_s, ay_s), (sx + self.width // 2, sy + 3), 1)

        if self.state in ("STUNNED", "YANKED"):
            frames = self.anims.get("stunned", [])
            sprite = frames[0] if frames else None
        elif self.state == "DROP":
            sprite = self.anims.get("drop")
        else:
            frames = self.anims.get("idle", [])
            sprite = frames[(self.anim_timer // 8) % len(frames)] if frames else None

        if sprite:
            surface.blit(sprite, (sx - 3, sy - 3))
        else:
            pygame.draw.circle(surface, (60, 45, 80), (sx + self.width // 2, sy + self.height // 2), 7)


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
         Energy Pearl (-1 Boss HP, +1 Froggy Heart!) OR jump on top and
         stomp his core with the Stomping Boots (-2 Boss HP!).
      4. Defeating the Mantis permanently drops the RED SPORE BOOMERANG Relic!
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y - 80, width=32, height=34)
        self.anims = enemy_anims["mantis"]
        self.is_boss = True
        self.name = "EMPEROR MANTIS"
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

    def hit_by_spore_boomerang(self, room, is_red=False):
        if self.state in ("HOVER", "DIVE_TELEGRAPH", "DIVE_ATTACK"):
            self.state = "WEAK_EXPOSED"
            self.stun_timer = BOSS_WEAK_EXPOSED_FRAMES
            self.vx = 0.0
            self.vy = 1.2
            self.flash_timer = 12
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_SPORE_CYAN, count=20)
            if is_red:
                self.hp -= 1
                if self.hp <= 0:
                    self._die(room)
            return True
        return False

    def check_stomp(self, player_rect, player_vy):
        """Allows Mario-style stomping when weak core is exposed!"""
        if self.state == "WEAK_EXPOSED" and player_vy > 0:
            stomp_rect = pygame.Rect(self.x + 4, self.y - 6, self.width - 8, 16)
            return player_rect.colliderect(stomp_rect)
        return False

    def take_stomp_damage(self, room, audio=None):
        self.hp -= 2
        self.flash_timer = 25
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=35)
        if self.hp <= 0:
            self._die(room, audio)
        else:
            self.state = "RECOVERING"
            self.state_timer = 40

    def yank_exposed_weak_point(self, room):
        self.hp -= 1
        self.flash_timer = 20
        pearl = BossEnergyPearl(self.center_x, self.center_y)
        room.enemies.append(pearl)
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=26)

        if self.hp <= 0:
            self._die(room)
        else:
            self.state = "RECOVERING"
            self.state_timer = 45
            fly_count = sum(1 for e in room.enemies if isinstance(e, BuzzFly) and e.alive)
            if self.phase >= 2 and fly_count < 1:
                room.enemies.append(BuzzFly(self.home_x - 90, self.home_y - 20, room.enemy_anims))

        return pearl

    def _die(self, room, audio=None):
        self.alive = False
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=55)
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=45)
        # Slaying the Emperor Mantis yields Red Spore Boomerang Relic AND Mantis Jade Crest!
        room.powerups.append(CollectiblePowerup(self.center_x - 12, self.center_y, "red_boomerang", room.assets))
        room.powerups.append(CollectiblePowerup(self.center_x + 12, self.center_y, "KEY_MANTIS", room.assets))
        if audio:
            audio.play_sfx("boss_hit")

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
        f_timer = getattr(self, "flash_timer", 0)
        if f_timer > 0 and (f_timer // 2) % 2 == 1:
            flash_surf = create_silhouette_flash(sprite)
            if flash_surf:
                surface.blit(flash_surf, (sx, sy))

        if self.state == "WEAK_EXPOSED":
            pulse_r = 6 + int(math.sin(self.anim_timer * 0.35) * 2)
            pygame.draw.circle(surface, COLOR_BOSS_CORE, (cx_screen, cy_screen - 2), pulse_r, 1)
            for i in range(3):
                ang = self.anim_timer * 0.16 + i * (math.tau / 3.0)
                star_x = cx_screen + int(math.cos(ang) * 14)
                star_y = int(self.rect.top - 5 - camera_y + math.sin(ang) * 3)
                pygame.draw.circle(surface, COLOR_BOSS_GOLD, (star_x, star_y), 2)


class DreadHoundBoss(BaseEnemy):
    """
    Chapter 8: 16-Bit Colossus Side-of-Screen Boss: THE DREAD HOUND!
    A massive 72x72 mechanical/beast hound head anchored to the right wall.
    
    Phases & Attack Patterns:
      1. WALL_IDLE: Prowls along the right wall, bobbing menacingly with crimson eyes.
      2. LUNGE: Massive horizontal snapping jaw bite charging across the cavern!
      3. DAZED: Upon hitting the far wall, gets stunned & lodged for ~180 frames!
         Froggy can jump on top and STOMP its glowing forehead crest (with Stomping Boots)
         for 2 damage, or whip it with the tongue / shoot it with the Red Boomerang!
      4. HOWL: Howls sonic shockwaves and cursed fireballs sweeping across the arena!
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y, width=80, height=76)
        self.anims = enemy_anims.get("hound", {})
        self.is_boss = True
        self.name = "THE DREAD HOUND"
        self.home_x = float(spawn_x)
        self.home_y = float(spawn_y)
        self.max_hp = BOSS_MAX_HP_HOUND
        self.hp = BOSS_MAX_HP_HOUND
        self.awakened = False
        self.state = "DORMANT"
        self.state_timer = 0
        self.anim_timer = 0
        self.flash_timer = 0
        self.attack_counter = 0
        self.facing_right = False

    def awaken(self):
        if not self.awakened:
            self.awakened = True
            self.state = "WALL_IDLE"
            self.state_timer = 65
            self.facing_right = False

    @property
    def phase(self):
        if self.hp <= 3:
            return 3
        elif self.hp <= 6:
            return 2
        return 1

    def check_stomp(self, player_rect, player_vy):
        """Allows Mario-style stomping when dazed!"""
        if self.state == "DAZED" and player_vy > 0:
            stomp_rect = pygame.Rect(int(self.x + 4), int(self.y - 16), self.width - 8, 32)
            return player_rect.colliderect(stomp_rect)
        return False

    def take_stomp_damage(self, room, audio=None):
        self.hp -= 2
        self.flash_timer = 25
        room.spawn_particle_burst(self.center_x, self.y + 8, COLOR_BOSS_GOLD, count=30)
        self.state = "RETRACT"
        self.facing_right = False
        self.vx = 5.2
        if self.hp <= 0:
            self._die(room, audio)
        elif audio:
            audio.play_sfx("boss_hit")

    def hit_by_spore_boomerang(self, room, is_red=False):
        if self.state == "DAZED":
            dmg = 2 if is_red else 1
            self.hp -= dmg
            self.flash_timer = 20
            p_col = COLOR_BOOMERANG_RED if is_red else COLOR_SPORE_CYAN
            room.spawn_particle_burst(self.center_x, self.center_y, p_col, count=20)
            if self.hp <= 0:
                self._die(room)
            else:
                self.state = "RETRACT"
                self.facing_right = False
                self.vx = 5.2
            return True
        return False

    def hit_by_tongue_whip(self, room, audio=None):
        if self.state == "DAZED":
            self.hp -= 1
            self.flash_timer = 20
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=20)
            if self.hp <= 0:
                self._die(room, audio)
            else:
                self.state = "RETRACT"
                self.facing_right = False
                self.vx = 5.2
            if audio:
                audio.play_sfx("boss_hit")
            return True
        return False

    def _die(self, room, audio=None):
        self.alive = False
        room.boss_defeated = True
        room.boss_defeated_banner_timer = 280
        room.screen_shake_timer = 60
        # Drops the Hound Obsidian Fang key fragment!
        room.powerups.append(CollectiblePowerup(self.center_x - 12, self.center_y - 12, "KEY_HOUND", room.assets))
        for _ in range(6):
            rx = self.center_x + random.randint(-24, 24)
            ry = self.center_y + random.randint(-24, 24)
            room.spawn_particle_burst(rx, ry, (255, 60, 40), count=25)
            room.spawn_particle_burst(rx, ry, COLOR_BOSS_GOLD, count=25)
        if audio:
            audio.play_sfx("hound_roar")
            audio.play_music("level")

    def update(self, room):
        if not self.alive or not self.awakened or self.state == "DORMANT":
            return
        self.anim_timer += 1
        self.state_timer -= 1
        if self.flash_timer > 0:
            self.flash_timer -= 1

        player = getattr(room, "active_player_ref", None)

        if self.state == "WALL_IDLE":
            self.facing_right = (player.center_x > self.center_x) if player is not None else False
            self.y = self.home_y
            self.x = self.home_x
            if self.state_timer <= 0:
                self.attack_counter += 1
                if self.attack_counter % 2 == 1:
                    # Snapping Jaw Lunge across the arena!
                    self.state = "LUNGE"
                    speed = -6.8 if self.phase == 1 else (-8.2 if self.phase == 2 else -9.5)
                    self.vx = speed
                    self.state_timer = 135
                    self.facing_right = False
                    if hasattr(room, "world_manager") and hasattr(room.world_manager, "audio"):
                        room.world_manager.audio.play_sfx("hound_bark")
                else:
                    # Howl fireball barrage!
                    self.state = "HOWL"
                    self.state_timer = 65
                    self.facing_right = False
                    self._fire_howl_barrage(room)

        elif self.state == "LUNGE":
            self.facing_right = (self.vx > 0)
            self.x += self.vx
            if self.x <= 48 or self.state_timer <= 0:
                self.x = max(48.0, self.x)
                self.vx = 0.0
                self.state = "DAZED"
                self.state_timer = 180
                room.screen_shake_timer = 25
                room.spawn_particle_burst(self.x + 10, self.center_y, (255, 200, 70), count=25)
                if hasattr(room, "world_manager") and hasattr(room.world_manager, "audio"):
                    room.world_manager.audio.play_sfx("stun")

        elif self.state == "DAZED":
            self.facing_right = False
            if self.anim_timer % 12 == 0:
                room.spawn_particle_burst(self.center_x, self.y - 4, (255, 235, 90), count=4)
            if self.state_timer <= 0:
                self.state = "RETRACT"
                self.facing_right = False
                self.vx = 5.2

        elif self.state == "RETRACT":
            # Backs up toward his right-wall post while keeping jaws aimed left at Froggy!
            self.facing_right = False
            self.x += self.vx
            if self.x >= self.home_x:
                self.x = self.home_x
                self.vx = 0.0
                self.facing_right = False
                self.state = "WALL_IDLE"
                self.state_timer = 60

        elif self.state == "HOWL":
            self.facing_right = False
            if self.anim_timer % 14 == 0:
                room.spawn_particle_burst(self.x + 8, self.center_y + 12, (255, 60, 40), count=6)
            if self.state_timer <= 0:
                self.state = "WALL_IDLE"
                self.state_timer = 50

        self.rect.topleft = (int(round(self.x)), int(round(self.y)))

    def _fire_howl_barrage(self, room):
        room.screen_shake_timer = 20
        if hasattr(room, "world_manager") and hasattr(room.world_manager, "audio"):
            room.world_manager.audio.play_sfx("hound_roar")
        count = 2 if self.phase == 1 else (3 if self.phase == 2 else 4)
        angles = [-0.25, 0.0, 0.25, -0.45][:count]
        for a in angles:
            vx = -4.5 * math.cos(a)
            vy = 4.5 * math.sin(a)
            room.boss_projectiles.append(HoundFireball(self.x + 10, self.center_y + 8, vx, vy, is_flame=True))

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        if assets and "crimson" in assets.lights:
            lt = assets.lights["crimson"]
            surface.blit(lt, (sx + self.width // 2 - lt.get_width() // 2, sy + self.height // 2 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        if self.state == "LUNGE":
            sprite_key = "lunge"
        elif self.state == "DAZED":
            sprite_key = "dazed"
        elif self.state == "HOWL":
            sprite_key = "howl"
        else:
            sprite_key = "idle_1" if ((self.anim_timer // 16) % 2 == 1 and "idle_1" in self.anims) else "idle"

        sprite = self.anims.get(sprite_key) or self.anims.get("idle")
        if sprite:
            draw_x = sx + (self.width - sprite.get_width()) // 2
            draw_y = sy + self.height - sprite.get_height() + 5
            if self.facing_right:
                flipped = pygame.transform.flip(sprite, True, False)
                surface.blit(flipped, (draw_x, draw_y))
                if self.flash_timer > 0 and (self.flash_timer // 2) % 2 == 1:
                    flash_surf = create_silhouette_flash(flipped)
                    if flash_surf:
                        surface.blit(flash_surf, (draw_x, draw_y))
            else:
                surface.blit(sprite, (draw_x, draw_y))
                if self.flash_timer > 0 and (self.flash_timer // 2) % 2 == 1:
                    flash_surf = create_silhouette_flash(sprite)
                    if flash_surf:
                        surface.blit(flash_surf, (draw_x, draw_y))
        else:
            col = (180, 40, 40) if self.state == "DAZED" else (120, 30, 30)
            pygame.draw.rect(surface, col, (sx, sy, self.width, self.height), border_radius=6)


class GigaShockwave:
    """
    Seismic shockwave projectile launched by Giga Toad's ground pound.
    Ripples across the arena floor to force Froggy to jump or grapple.
    """
    def __init__(self, x, y, dir_x, speed=3.6):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(dir_x * speed)
        self.width = 16
        self.height = 14
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        self.lifetime = 110
        self.alive = True
        self.anim_timer = 0

    def update(self, room):
        self.lifetime -= 1
        self.anim_timer += 1
        if self.lifetime <= 0:
            self.alive = False
            return
        self.x += self.vx
        self.rect.x = int(round(self.x))
        # Dissolve if colliding with solid walls
        if room.rect_collides_with_solid(self.rect):
            self.alive = False
            room.spawn_particle_burst(self.rect.centerx, self.rect.centery, (240, 190, 80), count=6)
            return
        # Dust trail
        if self.anim_timer % 3 == 0:
            room.particles.append(
                Particle(self.rect.centerx, self.rect.bottom - 2,
                         random.uniform(-0.6, 0.6), random.uniform(-1.8, -0.4),
                         (220, 180, 100), 16, 2.5)
            )

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return
        sx = int(self.rect.x - camera_x)
        sy = int(self.rect.y - camera_y)
        # Additive ambient glow
        if assets and "gold" in assets.lights:
            lt = assets.lights["gold"]
            surface.blit(lt, (sx + 8 - lt.get_width() // 2, sy + 7 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        # Spiky jagged energy wave
        pulse = 1.0 + 0.25 * math.sin(self.anim_timer * 0.45)
        h = int(self.height * pulse)
        pts = [
            (sx, sy + self.height),
            (sx + self.width // 2, sy + self.height - h),
            (sx + self.width, sy + self.height),
        ]
        pygame.draw.polygon(surface, (255, 235, 120), pts)
        pygame.draw.polygon(surface, (220, 130, 40), pts, 1)


class GigaToadBoss(BaseEnemy):
    """
    Chapter 8B: Heavyweight Melee Brawler Boss: GIGA TOAD!
    A massive muscular heavyweight brawler bullfrog built for brutal physical combat.

    Phases & Combat Loop:
      - Phase 1 (10..7 HP): Heavy ground pounds and charge haymaker dash punches.
      - Phase 2 (6..4 HP): High belly flop leaps and rapid alternating slam combos.
      - Phase 3 (<= 3 HP): ENRAGED! Crimson battle aura, high velocity, accelerated attacks!

    Combat Puzzle:
      1. Dodge his high jump slam to avoid direct impact.
      2. When he lands with a seismic tremor, jump or grapple over the bilateral shockwaves!
      3. Dodge his charge punch by jumping onto an elevated ledge or grappling. If he hits a
         wall or finishes his combo, he enters PANTING / DAZED state from exhaustion.
      4. While PANTING:
         - Froggy can jump on his back/head to STOMP him with Stomping Boots for 2 damage!
         - Froggy can whip him with the Tongue for 1 damage!
         - Froggy can shoot him with the Spore Boomerang (Red = 2 dmg, Cyan = 1 dmg)!
      5. Defeating Giga Toad unseals the ancient gate to the Sacred Sanctuary!
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y, width=64, height=64)
        self.anims = enemy_anims.get("toad", {})
        self.is_boss = True
        self.name = "GIGA TOAD"
        self.home_x = float(spawn_x)
        self.home_y = float(spawn_y)
        self.x = float(spawn_x)
        self.y = float(spawn_y)
        self.max_hp = BOSS_MAX_HP_TOAD
        self.hp = BOSS_MAX_HP_TOAD
        self.awakened = False
        self.state = "DORMANT"
        self.state_timer = 0
        self.anim_timer = 0
        self.flash_timer = 0
        self.facing_right = False
        self.on_ground = True
        self.vx = 0.0
        self.vy = 0.0
        self.attack_counter = 0

    def awaken(self):
        if not self.awakened:
            self.awakened = True
            self.state = "BRAWLER_IDLE"
            self.state_timer = 50

    @property
    def phase(self):
        if self.hp <= 3:
            return 3
        elif self.hp <= 6:
            return 2
        return 1

    def check_stomp(self, player_rect, player_vy):
        """Allows Mario-style stomping when panting, dazed, or stalking on the ground!"""
        if self.state in ("PANTING", "DAZED", "BRAWLER_IDLE", "HURT") and player_vy > 0:
            stomp_rect = pygame.Rect(int(self.x - 4), int(self.y - 16), self.width + 8, 34)
            return player_rect.colliderect(stomp_rect)
        return False

    def take_stomp_damage(self, room, audio=None):
        self.hp -= 2
        self.flash_timer = 25
        room.spawn_particle_burst(self.center_x, self.y + 4, COLOR_BOSS_GOLD, count=30)
        if self.hp <= 0:
            self._die(room, audio)
        else:
            self.state = "HURT"
            self.state_timer = 25
            self.vx = 2.5 if not self.facing_right else -2.5
            if audio:
                audio.play_sfx("boss_hit")

    def hit_by_spore_boomerang(self, room, is_red=False):
        if self.state in ("PANTING", "DAZED"):
            dmg = 2 if is_red else 1
            self.hp -= dmg
            self.flash_timer = 20
            p_col = COLOR_BOOMERANG_RED if is_red else COLOR_SPORE_CYAN
            room.spawn_particle_burst(self.center_x, self.center_y, p_col, count=25)
            if self.hp <= 0:
                self._die(room)
            else:
                self.state = "HURT"
                self.state_timer = 25
                self.vx = 2.0 if not self.facing_right else -2.0
            return True
        elif self.state in ("BRAWLER_IDLE", "JUMP_SLAM_WINDUP", "CHARGE_PUNCH_WINDUP") and self.flash_timer == 0:
            self.hp -= 1
            self.flash_timer = 14
            p_col = COLOR_BOOMERANG_RED if is_red else COLOR_SPORE_CYAN
            room.spawn_particle_burst(self.center_x, self.center_y, p_col, count=16)
            if self.hp <= 0:
                self._die(room)
            return True
        return False

    def hit_by_tongue_whip(self, room, audio=None):
        if self.state in ("PANTING", "DAZED"):
            self.hp -= 1
            self.flash_timer = 20
            room.spawn_particle_burst(self.center_x, self.center_y, (255, 230, 90), count=25)
            if self.hp <= 0:
                self._die(room, audio)
            else:
                self.state = "HURT"
                self.state_timer = 25
                self.vx = 2.5 if not self.facing_right else -2.5
            if audio:
                audio.play_sfx("boss_hit")
            return True
        elif self.state in ("BRAWLER_IDLE", "JUMP_SLAM_WINDUP", "CHARGE_PUNCH_WINDUP") and self.flash_timer == 0:
            self.hp -= 1
            self.flash_timer = 14
            room.spawn_particle_burst(self.center_x, self.center_y, (255, 230, 90), count=16)
            if self.hp <= 0:
                self._die(room, audio)
            if audio:
                audio.play_sfx("boss_hit")
            return True
        return False

    def _die(self, room, audio=None):
        self.alive = False
        room.boss_defeated = True
        room.boss_defeated_banner_timer = 280
        room.screen_shake_timer = 60
        # Drops the Toad Ruby Sigil key fragment!
        room.powerups.append(CollectiblePowerup(self.center_x - 12, self.center_y - 12, "KEY_TOAD", room.assets))
        for _ in range(8):
            rx = self.center_x + random.randint(-28, 28)
            ry = self.center_y + random.randint(-28, 28)
            room.spawn_particle_burst(rx, ry, (255, 140, 30), count=25)
            room.spawn_particle_burst(rx, ry, COLOR_BOSS_GOLD, count=25)
        if audio:
            audio.play_sfx("toad_grunt")
            audio.play_music("level")

    def _apply_physics(self, room):
        # Horizontal movement and solid tile collision
        self.x += self.vx
        self.rect.x = int(round(self.x))
        hit_wall = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vx > 0:
                    self.rect.right = tile.left
                    hit_wall = True
                elif self.vx < 0:
                    self.rect.left = tile.right
                    hit_wall = True
                self.x = float(self.rect.x)
                self.vx = 0.0

        # Keep inside colosseum arena bounds (away from sealed side doors)
        min_x = 36.0
        max_x = float(max(200, room.world_width - self.width - 36))
        if self.x < min_x:
            self.x = min_x
            self.rect.x = int(round(self.x))
            self.vx = 0.0
            hit_wall = True
        elif self.x > max_x:
            self.x = max_x
            self.rect.x = int(round(self.x))
            self.vx = 0.0
            hit_wall = True

        # Vertical movement and gravity
        self.vy = min(self.vy + 0.35, 9.5)
        self.y += self.vy
        self.rect.y = int(round(self.y))
        self.on_ground = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vy > 0:
                    self.rect.bottom = tile.top
                    self.on_ground = True
                elif self.vy < 0:
                    self.rect.top = tile.bottom
                self.y = float(self.rect.y)
                self.vy = 0.0

        return hit_wall

    def update(self, room):
        if not self.alive or not self.awakened or self.state == "DORMANT":
            return

        self.anim_timer += 1
        self.state_timer -= 1
        if self.flash_timer > 0:
            self.flash_timer -= 1

        player = room.active_player_ref
        audio = getattr(room.world_manager, "audio", None) if hasattr(room, "world_manager") else None

        if self.state == "BRAWLER_IDLE":
            if player is not None:
                dx = player.center_x - self.center_x
                self.facing_right = (dx > 0)
                walk_spd = 1.4 if self.phase == 1 else (1.8 if self.phase == 2 else 2.3)
                if abs(dx) > 42.0:
                    self.vx = walk_spd if dx > 0 else -walk_spd
                else:
                    self.vx *= 0.8
            else:
                self.vx *= 0.8
            self._apply_physics(room)

            if self.state_timer <= 0:
                self.attack_counter += 1
                if self.phase == 3:
                    chosen = "SLAM" if (self.attack_counter % 2 == 1) else "PUNCH"
                elif self.phase == 2:
                    pattern = ["SLAM", "PUNCH", "SLAM", "PUNCH"]
                    chosen = pattern[self.attack_counter % len(pattern)]
                else:
                    chosen = "SLAM" if (self.attack_counter % 2 == 1) else "PUNCH"

                if chosen == "SLAM":
                    self.state = "JUMP_SLAM_WINDUP"
                    self.state_timer = 30 if self.phase < 3 else 22
                    if audio:
                        audio.play_sfx("toad_grunt")
                else:
                    self.state = "CHARGE_PUNCH_WINDUP"
                    self.state_timer = 32 if self.phase < 3 else 22
                    if audio:
                        audio.play_sfx("toad_grunt")

        elif self.state == "JUMP_SLAM_WINDUP":
            if player is not None:
                self.facing_right = (player.center_x > self.center_x)
            self.vx *= 0.7
            self._apply_physics(room)
            if self.anim_timer % 4 == 0:
                room.spawn_particle_burst(self.center_x, self.rect.bottom, (220, 200, 160), count=3)
            if self.state_timer <= 0:
                self.state = "JUMP_SLAM_AIR"
                self.vy = -8.6 if self.phase < 3 else -9.4
                if player is not None:
                    dx = player.center_x - self.center_x
                    dist = abs(dx)
                    spd = min(5.2, max(2.2, dist / 32.0))
                    self.vx = spd if dx > 0 else -spd
                    self.facing_right = (dx > 0)
                else:
                    self.vx = 2.8 if self.facing_right else -2.8

        elif self.state == "JUMP_SLAM_AIR":
            if self.vy > 0:
                self.vy = min(self.vy + 0.45, 10.0)
            self._apply_physics(room)
            if self.on_ground:
                room.screen_shake_timer = 32
                if audio:
                    audio.play_sfx("toad_slam")
                room.spawn_particle_burst(self.center_x, self.rect.bottom, COLOR_BOSS_GOLD, count=30)
                room.spawn_particle_burst(self.center_x, self.rect.bottom, (255, 120, 40), count=25)

                speed = 4.2 if self.phase >= 2 else 3.2
                room.boss_projectiles.append(GigaShockwave(self.rect.left - 12, self.rect.bottom - 14, dir_x=-1, speed=speed))
                room.boss_projectiles.append(GigaShockwave(self.rect.right - 4, self.rect.bottom - 14, dir_x=1, speed=speed))

                self.state = "PANTING"
                self.state_timer = 135 if self.phase == 1 else (105 if self.phase == 2 else 85)
                self.vx = 0.0

        elif self.state == "CHARGE_PUNCH_WINDUP":
            if player is not None:
                self.facing_right = (player.center_x > self.center_x)
            self.vx *= 0.7
            self._apply_physics(room)
            if self.anim_timer % 4 == 0:
                p_col = (255, 60, 60) if self.phase == 3 else (255, 200, 70)
                room.spawn_particle_burst(self.center_x, self.center_y, p_col, count=4)
            if self.state_timer <= 0:
                self.state = "CHARGE_PUNCH_DASH"
                self.state_timer = 48
                dash_speed = 6.4 if self.phase == 1 else (7.6 if self.phase == 2 else 8.5)
                self.vx = dash_speed if self.facing_right else -dash_speed

        elif self.state == "CHARGE_PUNCH_DASH":
            hit_wall = self._apply_physics(room)
            if self.anim_timer % 3 == 0:
                room.spawn_particle_burst(self.center_x, self.rect.bottom, (220, 180, 120), count=4)
            if hit_wall or self.state_timer <= 0:
                room.screen_shake_timer = 22
                if audio:
                    audio.play_sfx("stun")
                room.spawn_particle_burst(self.center_x, self.center_y, (255, 230, 90), count=20)
                self.state = "DAZED"
                self.state_timer = 145 if self.phase == 1 else (115 if self.phase == 2 else 85)
                self.vx = 0.0

        elif self.state in ("PANTING", "DAZED"):
            if player is not None:
                self.facing_right = (player.center_x > self.center_x)
            self.vx *= 0.75
            self._apply_physics(room)
            if self.anim_timer % 12 == 0:
                room.spawn_particle_burst(self.center_x, self.y - 4, (255, 235, 90), count=4)
            if self.state_timer <= 0:
                self.state = "BRAWLER_IDLE"
                self.state_timer = 45 if self.phase < 3 else 30

        elif self.state == "HURT":
            self.vx *= 0.82
            self._apply_physics(room)
            if self.state_timer <= 0:
                self.state = "BRAWLER_IDLE"
                self.state_timer = 35 if self.phase < 3 else 24

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return

        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        # Dynamic additive boss lighting aura
        if assets:
            if self.phase == 3:
                lt = assets.lights.get("crimson")
            elif self.state in ("PANTING", "DAZED"):
                lt = assets.lights.get("gold")
            else:
                lt = assets.lights.get("emerald")
            if lt:
                surface.blit(lt, (sx + self.width // 2 - lt.get_width() // 2,
                                  sy + self.height // 2 - lt.get_height() // 2),
                             special_flags=pygame.BLEND_RGB_ADD)

        # Action states take priority over static phase idle so attacks & stun always animate!
        if self.state in ("JUMP_SLAM_WINDUP", "JUMP_SLAM_AIR"):
            sprite_key = "slam"
        elif self.state in ("CHARGE_PUNCH_WINDUP", "CHARGE_PUNCH_DASH"):
            sprite_key = "punch"
        elif self.state in ("PANTING", "DAZED", "HURT"):
            sprite_key = "dazed"
        elif abs(self.vx) > 0.4 and "walk_0" in self.anims:
            if self.phase == 3 and (self.anim_timer // 8) % 2 == 0 and "enraged" in self.anims:
                sprite_key = "enraged"
            else:
                sprite_key = "walk_0" if (self.anim_timer // 8) % 2 == 0 else "walk_1"
        elif self.phase == 3 and "enraged" in self.anims:
            sprite_key = "enraged" if (self.anim_timer // 14) % 2 == 0 else "idle_1"
        else:
            sprite_key = "idle" if (self.anim_timer // 16) % 2 == 0 else "idle_1"

        sprite = self.anims.get(sprite_key) or self.anims.get("idle")
        if sprite:
            draw_x = sx + (self.width - sprite.get_width()) // 2
            draw_y = sy + self.height - sprite.get_height() + 4
            if self.facing_right:
                flipped = pygame.transform.flip(sprite, True, False)
                surface.blit(flipped, (draw_x, draw_y))
                if self.flash_timer > 0 and (self.flash_timer // 2) % 2 == 1:
                    flash_surf = create_silhouette_flash(flipped)
                    if flash_surf:
                        surface.blit(flash_surf, (draw_x, draw_y))
            else:
                surface.blit(sprite, (draw_x, draw_y))
                if self.flash_timer > 0 and (self.flash_timer // 2) % 2 == 1:
                    flash_surf = create_silhouette_flash(sprite)
                    if flash_surf:
                        surface.blit(flash_surf, (draw_x, draw_y))
        else:
            col = (220, 60, 60) if self.state in ("PANTING", "DAZED") else (60, 160, 80)
            pygame.draw.rect(surface, col, (sx, sy, self.width, self.height), border_radius=6)


# =============================================================================
# CHAPTER 7C. ICY WORLD PROJECTILES, AMBUSH PREDATORS & FALO THE SNOWMAN BOSS
# =============================================================================

class SteamParticle:
    """Rising warm steam vapor bubble emitted by geothermal hot spring waters."""
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = random.uniform(-0.35, 0.35)
        self.vy = random.uniform(-0.95, -0.45)
        self.radius = random.uniform(2.5, 5.0)
        self.lifetime = random.randint(45, 90)
        self.age = 0
        self.alive = True

    def update(self, room=None):
        self.age += 1
        self.x += self.vx
        self.y += self.vy
        self.radius += 0.04
        if self.age >= self.lifetime:
            self.alive = False

    def draw(self, surface, camera_x, camera_y):
        if not self.alive:
            return
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        alpha = max(0, int(150 * (1.0 - (self.age / self.lifetime))))
        r = int(round(self.radius))
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (220, 245, 255, alpha), (r + 1, r + 1), r)
        surface.blit(surf, (sx - r - 1, sy - r - 1))


class PoisonGasCloud:
    """Lingering toxic gas cloud left behind when a Stink Bug is defeated or ruptured."""
    def __init__(self, x, y, lifetime=240):
        self.x = float(x)
        self.y = float(y)
        self.radius = 5.0
        self.max_radius = 26.0
        self.lifetime = lifetime
        self.age = 0
        self.alive = True

    def update(self, room=None):
        self.age += 1
        if self.radius < self.max_radius:
            self.radius += 0.26
        if self.age >= self.lifetime:
            self.alive = False

    def check_player_contact(self, player_rect):
        dist_sq = (self.x - player_rect.centerx) ** 2 + (self.y - player_rect.centery) ** 2
        return dist_sq <= (self.radius + 6.0) ** 2

    def draw(self, surface, camera_x, camera_y):
        if not self.alive:
            return
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        alpha = max(0, int(145 * (1.0 - (self.age / self.lifetime) ** 2)))
        r = int(round(self.radius))
        surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(surf, (95, 225, 45, alpha), (r + 2, r + 2), r)
        pygame.draw.circle(surf, (180, 255, 90, int(alpha * 0.7)), (r + 2, r + 2), max(2, r - 6))
        surface.blit(surf, (sx - r - 2, sy - r - 2))


class SnowballProjectile:
    """Rolling and bouncing snowball launched by Falo the Snowman."""
    def __init__(self, x, y, vx, vy=0.0):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.radius = 7.0
        self.max_radius = 15.0
        self.alive = True
        self.lifetime = 175
        self.rect = pygame.Rect(int(self.x - 7), int(self.y - 7), 14, 14)

    def update(self, room):
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.alive = False
            return
        if self.radius < self.max_radius:
            self.radius += 0.05

        self.vy += 0.22
        self.x += self.vx
        self.y += self.vy
        r_int = int(round(self.radius))
        self.rect = pygame.Rect(int(self.x - r_int), int(self.y - r_int), r_int * 2, r_int * 2)

        if room.rect_collides_with_solid(self.rect):
            if self.vy > 0:
                self.vy = -self.vy * 0.65
                self.y -= 2
            else:
                self.alive = False
                room.spawn_particle_burst(self.x, self.y, (240, 245, 255), count=12)

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        r = int(round(self.radius))
        pygame.draw.circle(surface, (230, 240, 255), (sx, sy), r)
        pygame.draw.circle(surface, (255, 255, 255), (sx - 2, sy - 2), max(1, r - 3))
        pygame.draw.circle(surface, (180, 210, 240), (sx, sy), r, 1)


class CarrotBoomerang:
    """Detachable razor carrot nose thrown by Falo the Evil Snowman!"""
    def __init__(self, x, y, target_x, target_y, owner_boss):
        self.x = float(x)
        self.y = float(y)
        self.owner = owner_boss
        dx = target_x - x
        dy = target_y - y
        dist = max(1.0, math.hypot(dx, dy))
        speed = 6.4
        self.vx = (dx / dist) * speed
        self.vy = (dy / dist) * speed
        self.returning = False
        self.age = 0
        self.max_outward_frames = 65
        self.alive = True
        self.rect = pygame.Rect(int(self.x - 6), int(self.y - 6), 12, 12)

    def update(self, room):
        self.age += 1
        if not self.returning:
            self.x += self.vx
            self.y += self.vy
            if self.age >= self.max_outward_frames:
                self.returning = True
        else:
            dest_x = self.owner.center_x
            dest_y = self.owner.y + 16
            dx = dest_x - self.x
            dy = dest_y - self.y
            dist = math.hypot(dx, dy)
            if dist < 12:
                self.alive = False
                self.owner.carrot_attached = True
                return
            speed = 7.5
            self.x += (dx / dist) * speed
            self.y += (dy / dist) * speed

        self.rect.topleft = (int(self.x - 6), int(self.y - 6))
        if self.age % 3 == 0:
            room.spawn_particle_burst(self.x, self.y, (255, 140, 20), count=2)

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        angle = self.age * 0.45
        pts = [
            (sx + math.cos(angle) * 8, sy + math.sin(angle) * 8),
            (sx + math.cos(angle + 2.5) * 5, sy + math.sin(angle + 2.5) * 5),
            (sx + math.cos(angle - 2.5) * 5, sy + math.sin(angle - 2.5) * 5)
        ]
        pygame.draw.polygon(surface, (255, 120, 10), pts)
        stem_x = int(pts[1][0] + pts[2][0]) // 2
        stem_y = int(pts[1][1] + pts[2][1]) // 2
        pygame.draw.circle(surface, (80, 220, 60), (stem_x, stem_y), 2)


class StinkBug(BaseEnemy):
    """
    Stink Bug ('b') - Glacial Toxic Ground Patroller:
    Patrols icy platforms using cliff-feeler AI so it never walks off edges.
    When Froggy defeats it (tongue whip, Mario-stomp, or spore boomerang),
    its noxious abdominal gland bursts, leaving a lingering PoisonGasCloud
    that damages Froggy if he touches it!
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y + 2, width=16, height=14)
        self.anims = enemy_anims.get("stink_bug", {})
        self.patrol_speed = 0.75
        self.can_yank_immediately = True

    def stomp_kill(self, room):
        self.alive = False
        room.spawn_particle_burst(self.center_x, self.center_y, (120, 240, 60), count=18)
        room.poison_clouds.append(PoisonGasCloud(self.center_x, self.center_y, lifetime=240))

    def hit_by_spore_boomerang(self, room):
        self.alive = False
        room.spawn_particle_burst(self.center_x, self.center_y, (120, 240, 60), count=18)
        room.poison_clouds.append(PoisonGasCloud(self.center_x, self.center_y, lifetime=240))
        return True

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
        if not self.alive:
            return
        sx = int(self.rect.x - 4 - camera_x)
        sy = int(self.rect.y - 4 - camera_y)
        facing_key = "right" if self.dir_x > 0 else "left"
        frames = self.anims.get(facing_key, [])
        if frames:
            sprite = frames[(self.anim_timer // 8) % len(frames)]
            surface.blit(sprite, (sx, sy))
        f_timer = getattr(self, "flash_timer", 0)
        if f_timer > 0 and (f_timer // 2) % 2 == 1:
            flash_surf = create_silhouette_flash(sprite)
            if flash_surf:
                surface.blit(flash_surf, (sx, sy))
        else:
            pygame.draw.ellipse(surface, (80, 160, 40), (sx + 4, sy + 4, 16, 12))
            pygame.draw.circle(surface, (140, 230, 45), (sx + 8, sy + 7), 3)


class IceWolfSpider(BaseEnemy):
    """
    Ice Wolf Spider ('w') - Glacial Ambush Predator:
    Starts in 'CAMOUFLAGE' mode, appearing as a harmless, glittering frost crystal
    mound sitting innocently on an icy ledge.
    When Froggy ventures close (< 95 px and line-of-sight):
      - Shivers for 14 frames ('SHIVER') telegraphing the leap.
      - Springs high into the air with sudden explosive momentum ('AMBUSH_LEAP')!
      - Lands and stalks Froggy relentlessly across the platform ('STALKING')!
    Can be stunned, stomped with Stomping Boots, or whipped with the tongue.
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y + 4, width=16, height=14)
        self.anims = enemy_anims.get("ice_spider", {})
        self.state = "CAMOUFLAGE"
        self.shiver_timer = 0
        self.facing_right = True
        self.can_yank_immediately = False
        self.stalk_speed = 1.6

    def stomp_kill(self, room):
        self.alive = False
        room.spawn_particle_burst(self.center_x, self.center_y, (185, 230, 255), count=16)
        room.spawn_particle_burst(self.center_x, self.center_y, (255, 255, 255), count=12)

    def update(self, room):
        self.anim_timer += 1
        if self.state == "YANKED":
            return

        player = room.active_player_ref

        if self.state == "CAMOUFLAGE":
            self.vx = 0.0
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=False)
            if player:
                dx = player.center_x - self.center_x
                dy = player.center_y - self.center_y
                dist = math.hypot(dx, dy)
                if dist < 95.0 and abs(dy) < 55.0:
                    self.state = "SHIVER"
                    self.shiver_timer = 15
                    self.facing_right = (dx > 0)
            return

        elif self.state == "SHIVER":
            self.shiver_timer -= 1
            if self.anim_timer % 3 == 0:
                room.spawn_particle_burst(self.center_x, self.rect.top, (180, 235, 255), count=2)
            if self.shiver_timer <= 0:
                self.state = "AMBUSH_LEAP"
                self.vy = -6.5
                self.vx = 4.2 if self.facing_right else -4.2
                room.spawn_particle_burst(self.center_x, self.rect.bottom, (220, 245, 255), count=10)

        elif self.state == "AMBUSH_LEAP":
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            hit_ground = self._move_and_collide(room, turn_at_ledges=False)
            if hit_ground and self.vy == 0.0:
                self.state = "STALKING"
                self.can_yank_immediately = True

        elif self.state == "STALKING":
            if player:
                self.facing_right = (player.center_x > self.center_x)
            self.vx = self.stalk_speed if self.facing_right else -self.stalk_speed
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=True)

        elif self.state == "STUNNED":
            self.stun_timer -= 1
            self.vx *= 0.85
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self._move_and_collide(room, turn_at_ledges=False)
            if self.stun_timer <= 0:
                self.state = "STALKING"

    def _move_and_collide(self, room, turn_at_ledges):
        self.x += self.vx
        self.rect.x = int(round(self.x))
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vx > 0:
                    self.rect.right = tile.left
                    self.facing_right = False
                elif self.vx < 0:
                    self.rect.left = tile.right
                    self.facing_right = True
                self.x = float(self.rect.x)
                if self.state == "STALKING":
                    self.vx = self.stalk_speed if self.facing_right else -self.stalk_speed
                break

        self.y += self.vy
        self.rect.y = int(round(self.y))
        hit_ground = False
        for tile in room.solid_tiles:
            if self.rect.colliderect(tile):
                if self.vy > 0:
                    self.rect.bottom = tile.top
                    hit_ground = True
                elif self.vy < 0:
                    self.rect.top = tile.bottom
                self.y = float(self.rect.y)
                self.vy = 0.0
                break

        if turn_at_ledges and hit_ground and self.state == "STALKING":
            feeler_x = self.rect.right + 3 if self.facing_right else self.rect.left - 3
            feeler_y = self.rect.bottom + 3
            if not room.is_point_inside_solid(feeler_x, feeler_y):
                self.facing_right = not self.facing_right

        return hit_ground

    def draw(self, surface, camera_x, camera_y, assets=None):
        if not self.alive:
            return
        sx = int(self.rect.x - 4 - camera_x)
        sy = int(self.rect.y - 4 - camera_y)

        if self.state == "CAMOUFLAGE":
            camo_sp = self.anims.get("camo")
            if camo_sp:
                surface.blit(camo_sp, (sx, sy))
            else:
                pygame.draw.polygon(surface, (180, 220, 245), [(sx + 8, sy), (sx + 2, sy + 14), (sx + 14, sy + 14)])
        elif self.state == "SHIVER":
            camo_sp = self.anims.get("camo")
            shake_x = sx + random.randint(-1, 1)
            if camo_sp:
                surface.blit(camo_sp, (shake_x, sy))
            else:
                pygame.draw.polygon(surface, (210, 240, 255), [(shake_x + 8, sy), (shake_x + 2, sy + 14), (shake_x + 14, sy + 14)])
        elif self.state == "AMBUSH_LEAP":
            leap_sp = self.anims.get("leap")
            if leap_sp:
                surface.blit(leap_sp, (sx, sy))
            else:
                pygame.draw.circle(surface, (200, 235, 255), (sx + 8, sy + 8), 7)
        else:
            stalk_sp = self.anims.get("stalk_right" if self.facing_right else "stalk_left")
            if stalk_sp:
                surface.blit(stalk_sp, (sx, sy))
            else:
                pygame.draw.circle(surface, (170, 215, 250), (sx + 8, sy + 8), 7)


class FaloSnowmanBoss(BaseEnemy):
    """
    Chapter 7D: Glacial Snowman Colossus: FALO THE EVIL SNOWMAN!
    An imposing frozen snow demon with glowing red coal eyes, jagged mouth,
    crooked black top hat, and a detachable razor carrot nose.

    Phases & Combat Loop:
      - Phase 1 (12..8 HP):
          Rolls snowballs across the floor ('ROLL_SNOWBALL').
          Throws his carrot nose boomerang ('THROW_CARROT').
          While carrot is flying, Falo loses his nose and is 'VULNERABLE'!
      - Phase 2 (7..4 HP) - "BLIZZARD VOLLEY":
          Attacks faster; fires a spread of 3 snowballs in an arcing volley.
      - Phase 3 (<= 3 HP) - "MELTDOWN ENRAGED":
          Falo turns into an enraged slush demon with bright red eyes and high speed.
      - Defeating Falo:
          Melts down into a slush puddle with his crooked top hat resting on top,
          scattering victory particles and unsealing the escape chute / gate!

    Vulnerability & Counters:
      - Mario Stomp: When Froggy jumps on Falo's top hat with Stomping Boots,
        it squashes him for 2 damage and bounces Froggy high!
      - Spore Boomerang: Red Spore Boomerang deals 2 damage and melts snow;
        cyan deals 1 damage.
      - Tongue: Whipping him when vulnerable or dazed deals 1 damage!
    """
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y - 20, width=38, height=48)
        self.anims = enemy_anims.get("falo", {})
        self.is_boss = True
        self.name = "FALO THE EVIL SNOWMAN"
        self.max_hp = 12
        self.hp = 12
        self.home_x = float(spawn_x)
        self.home_y = float(spawn_y)
        self.facing_right = False
        self.carrot_attached = True
        self.state = "DORMANT"
        self.state_timer = 0
        self.flash_timer = 0
        self.awakened = False
        self.attack_cycle = 0

    def awaken(self):
        if not self.awakened:
            self.awakened = True
            self.state = "INTRO"
            self.state_timer = 90

    @property
    def phase(self):
        if self.hp >= 8:
            return 1
        elif self.hp >= 4:
            return 2
        return 3

    def check_stomp(self, player_rect, player_vy):
        """Allows Mario-style stomping onto Falo's black top hat!"""
        if player_vy > 0 and self.alive and self.awakened and self.state != "DORMANT":
            return (player_rect.bottom >= self.rect.top - 4 and
                    player_rect.bottom <= self.rect.top + 14 and
                    player_rect.right > self.rect.left + 4 and
                    player_rect.left < self.rect.right - 4)
        return False

    def take_stomp_damage(self, room, audio=None):
        dmg = 2
        self.hp -= dmg
        self.flash_timer = 18
        room.spawn_particle_burst(self.center_x, self.rect.top + 4, COLOR_BOSS_GOLD, count=24)
        room.spawn_particle_burst(self.center_x, self.rect.top + 4, (240, 245, 255), count=20)
        if self.hp <= 0:
            self._die(room, audio)
        else:
            self.state = "DAZED"
            self.state_timer = 45

    def hit_by_spore_boomerang(self, room, is_red=False):
        if not self.alive or not self.awakened or self.state == "DORMANT":
            return False
        dmg = 2 if is_red else 1
        self.hp -= dmg
        self.flash_timer = 16
        p_col = COLOR_BOOMERANG_RED if is_red else (180, 235, 255)
        room.spawn_particle_burst(self.center_x, self.center_y, p_col, count=20)
        if is_red:
            room.spawn_particle_burst(self.center_x, self.center_y, (255, 120, 40), count=15)
        if self.hp <= 0:
            self._die(room)
        elif self.state == "VULNERABLE":
            self.state = "DAZED"
            self.state_timer = 40
        return True

    def hit_by_tongue_whip(self, room, audio=None):
        if not self.alive or not self.awakened or self.state == "DORMANT":
            return False
        if self.state in ("VULNERABLE", "DAZED"):
            self.hp -= 1
            self.flash_timer = 16
            room.spawn_particle_burst(self.center_x, self.center_y, (255, 220, 80), count=20)
            if self.hp <= 0:
                self._die(room, audio)
            if audio:
                audio.play_sfx("boss_hit")
            return True
        return False

    def _die(self, room, audio=None):
        self.alive = False
        self.state = "DEFEATED"
        room.boss_defeated = True
        room.boss_defeated_banner_timer = 280
        room.screen_shake_timer = 65
        # Drops the Falo Glacial Core key fragment!
        room.powerups.append(CollectiblePowerup(self.center_x - 12, self.center_y - 12, "KEY_FALO", room.assets))
        for _ in range(8):
            rx = self.center_x + random.randint(-24, 24)
            ry = self.center_y + random.randint(-24, 24)
            room.spawn_particle_burst(rx, ry, (240, 250, 255), count=20)
            room.spawn_particle_burst(rx, ry, (120, 215, 255), count=15)
            room.spawn_particle_burst(rx, ry, COLOR_BOSS_GOLD, count=15)
        if audio:
            audio.play_sfx("splat")
            audio.play_music("level")

    def update(self, room):
        if not self.alive or not self.awakened or self.state == "DORMANT":
            return

        self.anim_timer += 1
        if self.flash_timer > 0:
            self.flash_timer -= 1

        player = room.active_player_ref

        if self.state == "INTRO":
            self.state_timer -= 1
            self.y += 0.8
            self.rect.y = int(round(self.y))
            if self.anim_timer % 4 == 0:
                room.spawn_particle_burst(self.center_x, self.center_y, (240, 250, 255), count=6)
            if self.state_timer <= 0:
                self.state = "IDLE"
                self.state_timer = 60

        elif self.state == "IDLE":
            self.state_timer -= 1
            if player:
                self.facing_right = (player.center_x > self.center_x)
            if self.state_timer <= 0:
                self.attack_cycle = (self.attack_cycle + 1) % 3
                if self.attack_cycle == 0:
                    self.state = "ROLL_SNOWBALL"
                    self.state_timer = 40
                elif self.attack_cycle == 1 and self.carrot_attached:
                    self.state = "THROW_CARROT"
                    self.state_timer = 50
                else:
                    self.state = "BLIZZARD_BURST"
                    self.state_timer = 45

        elif self.state == "ROLL_SNOWBALL":
            self.state_timer -= 1
            if self.state_timer == 20:
                sb_vx = 3.6 if self.facing_right else -3.6
                room.boss_projectiles.append(
                    SnowballProjectile(self.center_x + (16 if self.facing_right else -16), self.rect.bottom - 12, sb_vx)
                )
                if self.phase >= 2:
                    room.boss_projectiles.append(
                        SnowballProjectile(self.center_x + (16 if self.facing_right else -16), self.rect.bottom - 18, sb_vx * 1.3, vy=-2.5)
                    )
            if self.state_timer <= 0:
                self.state = "IDLE"
                self.state_timer = 45 if self.phase == 1 else 30

        elif self.state == "THROW_CARROT":
            self.state_timer -= 1
            if self.state_timer == 35 and self.carrot_attached and player:
                self.carrot_attached = False
                room.boss_projectiles.append(
                    CarrotBoomerang(self.center_x, self.y + 16, player.center_x, player.center_y, owner_boss=self)
                )
            if self.state_timer <= 0:
                self.state = "VULNERABLE"
                self.state_timer = 120

        elif self.state == "VULNERABLE":
            self.state_timer -= 1
            self.vx = 0.5 if self.facing_right else -0.5
            self.x += self.vx
            self.rect.x = int(round(self.x))
            if self.carrot_attached or self.state_timer <= 0:
                self.carrot_attached = True
                self.state = "IDLE"
                self.state_timer = 50

        elif self.state == "BLIZZARD_BURST":
            self.state_timer -= 1
            if self.state_timer == 25:
                base_dir = 1.0 if self.facing_right else -1.0
                room.boss_projectiles.append(SnowballProjectile(self.center_x, self.y + 12, base_dir * 3.2, vy=-4.5))
                room.boss_projectiles.append(SnowballProjectile(self.center_x, self.y + 12, base_dir * 4.8, vy=-3.2))
                room.boss_projectiles.append(SnowballProjectile(self.center_x, self.y + 12, base_dir * 2.0, vy=-5.2))
                room.screen_shake_timer = 18
            if self.state_timer <= 0:
                self.state = "IDLE"
                self.state_timer = 40 if self.phase == 1 else 25

        elif self.state == "DAZED":
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "IDLE"
                self.state_timer = 30

    def draw(self, surface, camera_x, camera_y, assets=None):
        sx = int(self.rect.x - camera_x)
        sy = int(self.rect.y - camera_y)

        if not self.alive:
            melt_sp = self.anims.get("melt")
            if melt_sp:
                surface.blit(melt_sp, (sx - 1, sy))
            return

        sp_key = "throw" if self.state in ("ROLL_SNOWBALL", "THROW_CARROT", "BLIZZARD_BURST") else "idle"
        sprite = self.anims.get(sp_key)

        if sprite:
            draw_x = sx + (self.width - sprite.get_width()) // 2
            draw_y = sy + (self.height - sprite.get_height())
            if self.facing_right:
                flipped = pygame.transform.flip(sprite, True, False)
                surface.blit(flipped, (draw_x, draw_y))
                if self.flash_timer > 0 and (self.flash_timer // 2) % 2 == 1:
                    flash_surf = create_silhouette_flash(flipped)
                    if flash_surf:
                        surface.blit(flash_surf, (draw_x, draw_y))
            else:
                surface.blit(sprite, (draw_x, draw_y))
                if self.flash_timer > 0 and (self.flash_timer // 2) % 2 == 1:
                    flash_surf = create_silhouette_flash(sprite)
                    if flash_surf:
                        surface.blit(flash_surf, (draw_x, draw_y))
        else:
            pygame.draw.circle(surface, (230, 240, 255), (sx + self.width // 2, sy + self.height - 14), 16)
            pygame.draw.circle(surface, (230, 240, 255), (sx + self.width // 2, sy + self.height - 30), 12)
            pygame.draw.circle(surface, (230, 240, 255), (sx + self.width // 2, sy + 10), 9)


class AirBubble:
    """
    Rising submarine oxygen bubble spawned from hydrothermal air vents ('o')
    in the Sunken Grotto. Swimming into an AirBubble or its vent refills
    Froggy's oxygen gauge to 100%!
    """
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.base_x = float(x)
        self.vy = random.uniform(-1.05, -0.65)
        self.radius = random.uniform(3.5, 5.5)
        self.age = 0
        self.lifetime = random.randint(75, 135)
        self.alive = True

    @property
    def rect(self):
        r = int(round(self.radius))
        return pygame.Rect(int(self.x - r), int(self.y - r), r * 2, r * 2)

    def update(self, room=None):
        self.age += 1
        self.y += self.vy
        self.x = self.base_x + math.sin(self.age * 0.14) * 2.5
        if self.age >= self.lifetime:
            self.alive = False
        elif room and room.is_point_inside_solid(self.x, self.y):
            self.alive = False

    def draw(self, surface, camera_x, camera_y):
        if not self.alive:
            return
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        r = max(2, int(round(self.radius)))
        pygame.draw.circle(surface, (90, 235, 255), (sx, sy), r, 1)
        pygame.draw.circle(surface, (230, 255, 255), (sx - 1, sy - 1), max(1, r // 3))


class FriendlyNPC:
    """
    Chapter 7F: Friendly NPC Frogs & Comic-Style Dialogue Bubbles!
    Supports:
      - 'elder': Elder Tree Frog with white beard, mystic robe, and glowing staff.
      - 'shopkeeper': Village Shopkeeper Frog with crimson vest, apron, and potion vial.
    When Froggy approaches within 64 px, a comic-book speech bubble with a triangular
    pointer tail and typewriter text reveal pops up above the NPC!
    Pressing [UP] (or calling `interact()`) cycles dialogue lines or purchases/claims
    the shopkeeper's tonic or the elder's blessing!
    """
    def __init__(self, x, y, kind="elder", name=None, dialogue=None, shop_cost=1, shop_item=None, enemy_anims=None):
        self.x = float(x)
        self.y = float(y)
        self.width = 32
        self.height = 42
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        self.kind = kind  # "elder" or "shopkeeper"
        if name:
            self.name = name
        else:
            self.name = "ELDER TREE FROG" if kind == "elder" else "VILLAGE SHOPKEEPER"
        if dialogue:
            self.dialogue_lines = list(dialogue)
        elif kind == "shopkeeper":
            self.dialogue_lines = [
                f"Welcome to my shop, Froggy! Press [UP] to trade {shop_cost} Bug for a Healing Tonic!",
                "Submarine vents ('o') refill Oxygen, and Cold Waterfalls ('c') cool volcanic heat!",
            ]
        else:
            self.dialogue_lines = [
                "Greetings, young amphibian! Use your 8-way tongue [Y] to swing across chasms!",
                "Seek the Cold Waterfall Mist in the Magma Chasm and Air Vents in the Sunken Grotto!",
            ]
        self.shop_cost = int(shop_cost)
        self.shop_item = shop_item or ("HEART NECTAR (+2 HP)" if kind == "shopkeeper" else "ELDER'S BLESSING")
        self.frames = []
        if enemy_anims:
            key = "npc_shopkeeper" if kind == "shopkeeper" else "npc_elder"
            self.frames = enemy_anims.get(key, [])

        self.anim_timer = random.randint(0, 40)
        self.facing_right = True
        self.player_near = False
        self.line_index = 0
        self.revealed_chars = 0
        self.typewriter_timer = 0
        self.purchases_made = 0

    def snap_to_ground(self, room):
        """Snaps the NPC's hitbox bottom flush onto the nearest solid platform tile below."""
        if room is None:
            return
        best_top = None
        probe_x = int(self.center_x)
        for tile in room.solid_tiles:
            if tile.left <= probe_x <= tile.right and tile.top >= int(self.y) - 8:
                if best_top is None or tile.top < best_top:
                    best_top = tile.top
        if best_top is not None and (best_top - self.y) <= 96:
            self.rect.bottom = best_top
            self.y = float(self.rect.y)

    @property
    def center_x(self):
        return self.x + self.width * 0.5

    @property
    def center_y(self):
        return self.y + self.height * 0.5

    @property
    def current_text(self):
        if not self.dialogue_lines:
            return ""
        return self.dialogue_lines[self.line_index % len(self.dialogue_lines)]

    def update(self, player, room, audio=None):
        self.anim_timer += 1
        if player is None:
            self.player_near = False
            return

        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        dist = math.hypot(dx, dy)
        was_near = self.player_near
        self.player_near = (dist <= 68.0)

        if self.player_near:
            self.facing_right = (dx >= 0)
            if not was_near:
                self.revealed_chars = 0
                self.typewriter_timer = 0
                if audio:
                    audio.play_sfx("npc_talk")
            full_len = len(self.current_text)
            if self.revealed_chars < full_len:
                self.typewriter_timer += 1
                self.revealed_chars = min(full_len, self.revealed_chars + 2)
                if self.typewriter_timer % 4 == 0 and audio:
                    audio.play_sfx("npc_talk")
        else:
            self.revealed_chars = 0

    def interact(self, player, room, audio=None):
        """
        Advances comic dialogue or triggers interactive shopkeeper emporium / elder blessing!
        Returns True if an interaction occurred.
        """
        if player is None:
            return False
        full_len = len(self.current_text)
        if self.revealed_chars < full_len:
            self.revealed_chars = full_len
            if audio:
                audio.play_sfx("npc_talk")
            return True

        if self.kind == "shopkeeper":
            # Chapter 7G: Launch modular interactive ShopMenu emporium!
            wm = getattr(room, "world_manager", None)
            if wm is not None:
                wm.active_shop = ShopMenu(self.name)
            if audio:
                audio.play_sfx("select")
            return True
        else:
            # Advance to next line of dialogue
            self.line_index = (self.line_index + 1) % max(1, len(self.dialogue_lines))
            self.revealed_chars = 0
            # Elder Tree Frog bestows ancient wisdom & restores warmth/oxygen
            player.body_temp = 100.0
            player.oxygen = 100.0
            max_h = getattr(player, "max_hp", PLAYER_MAX_HP)
            if player.hp < max_h:
                player.hp = min(max_h, player.hp + 1)
            if room:
                room.show_banner(f"{self.name} BESTOWS ANCIENT AMPHIBIAN BLESSING!")
                room.spawn_particle_burst(self.center_x, self.center_y, (100, 245, 255), count=18)
            if audio:
                audio.play_sfx("npc_talk")
        return True

    def draw(self, surface, camera_x, camera_y, assets=None):
        sx = int(self.rect.centerx - camera_x)
        sy = int(self.rect.centery - camera_y)
        if assets:
            l_key = "gold" if self.kind == "shopkeeper" else "cyan"
            lt = assets.lights.get(l_key)
            if lt:
                surface.blit(lt, (sx - lt.get_width() // 2, sy - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        if self.frames:
            frame = self.frames[(self.anim_timer // 16) % len(self.frames)]
            if not self.facing_right:
                frame = pygame.transform.flip(frame, True, False)
            draw_x = int(self.rect.centerx - frame.get_width() // 2 - camera_x)
            # 48x48 NPC sprites have feet anchored at y=46 (2px from bottom)
            draw_y = int(self.rect.bottom - frame.get_height() + 2 - camera_y)
            surface.blit(frame, (draw_x, draw_y))
        else:
            col = (210, 80, 60) if self.kind == "shopkeeper" else (70, 195, 115)
            pygame.draw.rect(surface, col, (int(self.rect.x - camera_x), int(self.rect.y - camera_y), self.width, self.height), border_radius=4)

    def draw_dialogue_bubble(self, surface, font, camera_x, camera_y):
        """
        Renders a crisp comic-book speech bubble above the NPC with:
          - Rounded parchment/comic card + drop shadow + ink border
          - Triangular pointer tail aimed at the NPC's head
          - Speaker title pill + wrapped typewriter text + '[UP] Talk/Trade' prompt
        """
        if not self.player_near or font is None:
            return

        shown_text = self.current_text[:max(1, self.revealed_chars)]
        # Word-wrap into up to 2 concise comic lines (~42 chars/line)
        words = shown_text.split(" ")
        lines = []
        current_line = ""
        for w in words:
            test = (current_line + " " + w).strip()
            if len(test) <= 44 or not current_line:
                current_line = test
            else:
                lines.append(current_line)
                current_line = w
        if current_line:
            lines.append(current_line)
        lines = lines[:3]

        prompt_str = "[UP] Trade/Buy" if self.kind == "shopkeeper" else "[UP] Next / Blessing"
        header_str = f"{self.name}  ({prompt_str})"

        line_surfs = [font.render(line, True, (20, 26, 38)) for line in lines]
        header_surf = font.render(header_str, True, (255, 235, 110) if self.kind == "shopkeeper" else (130, 245, 255))

        content_w = max([header_surf.get_width()] + [s.get_width() for s in line_surfs] + [140])
        bubble_w = content_w + 16
        bubble_h = 18 + len(line_surfs) * 13 + 8

        npc_screen_x = int(self.center_x - camera_x)
        npc_screen_y = int(self.rect.top - camera_y)

        bx = max(8, min(INTERNAL_WIDTH - bubble_w - 8, npc_screen_x - bubble_w // 2))
        by = max(24, npc_screen_y - bubble_h - 12)

        bubble_rect = pygame.Rect(bx, by, bubble_w, bubble_h)
        shadow_rect = bubble_rect.move(2, 3)

        # 1. Drop shadow & comic speech bubble body
        pygame.draw.rect(surface, (10, 14, 24), shadow_rect, border_radius=6)
        pygame.draw.rect(surface, (248, 246, 236), bubble_rect, border_radius=6)
        border_col = (225, 165, 45) if self.kind == "shopkeeper" else (45, 165, 195)
        pygame.draw.rect(surface, border_col, bubble_rect, 2, border_radius=6)

        # 2. Speaker Header Ribbon inside top of bubble
        header_rect = pygame.Rect(bx + 2, by + 2, bubble_w - 4, 14)
        pygame.draw.rect(surface, (24, 32, 52), header_rect, border_radius=4)
        surface.blit(header_surf, (bx + 8, by + 3))

        # 3. Comic Speech Pointer Tail (Triangle pointing to NPC)
        tail_tip_x = max(bx + 12, min(bx + bubble_w - 12, npc_screen_x))
        tail_tip_y = by + bubble_h + 7
        tail_pts = [
            (tail_tip_x - 6, by + bubble_h - 1),
            (tail_tip_x + 6, by + bubble_h - 1),
            (tail_tip_x, tail_tip_y),
        ]
        pygame.draw.polygon(surface, (248, 246, 236), tail_pts)
        pygame.draw.lines(surface, border_col, False, [tail_pts[0], tail_pts[2], tail_pts[1]], 2)

        # 4. Render Typewriter Comic Text Lines
        for idx, l_surf in enumerate(line_surfs):
            surface.blit(l_surf, (bx + 8, by + 19 + idx * 13))


class ShopMenu:
    """
    Chapter 7G: Modular Interactive Shopkeeper Emporium
    Provides an interactive menu beyond a single button press. Froggy can browse
    wares, check item prices, inspect descriptions, trade captured bugs, and carry
    items into his inventory pouch. Modularly portable across all future levels.
    """
    def __init__(self, shopkeeper_name="ELDER MOSSMANTLE", catalog=None):
        self.shopkeeper_name = shopkeeper_name
        self.catalog = catalog or [
            {
                "id": "heart_nectar",
                "name": "Heart Nectar",
                "cost": 3,
                "desc": "Rich floral honeydew. Restores +3 HP instantly when used from inventory.",
                "type": "consumable",
            },
            {
                "id": "chill_draught",
                "name": "Glacial Draught",
                "cost": 4,
                "desc": "Essence of high-altitude frost. Resets body heat to 100% and gives 30s Lava Flame Guard.",
                "type": "consumable",
            },
            {
                "id": "warmth_broth",
                "name": "Pyro Broth",
                "cost": 4,
                "desc": "Spicy volcanic pepper broth. Warms chilled blood to 100% and gives 30s Frost Guard.",
                "type": "consumable",
            },
            {
                "id": "oxygen_reed",
                "name": "Grotto Air Reed",
                "cost": 2,
                "desc": "Hollow aerated marsh stalk. Restores +100% oxygen underwater instantly.",
                "type": "consumable",
            },
            {
                "id": "vitality_heart",
                "name": "Life Talisman",
                "cost": 10,
                "desc": "Ancient carved amphibian talisman. Permanently expands Max HP by +1!",
                "type": "upgrade",
                "stock": 1,
            },
            {
                "id": "map_cartography",
                "name": "Ruins Cartography",
                "cost": 6,
                "desc": "Ancient parchment chart revealing all zones on Froggy's Automap.",
                "type": "upgrade",
                "stock": 1,
            },
        ]
        self.selected_index = 0
        self.feedback_msg = "Welcome, traveler! Spend captured bugs to acquire vital remedies."
        self.feedback_color = (245, 235, 180)
        self.feedback_timer = 0
        self.is_open = True

    def handle_input(self, controller, player, room, audio=None):
        if not self.is_open:
            return False

        # Close shop first if [ESC/START] or [TAB/SELECT] is pressed
        if controller.just_pressed["SELECT"] or controller.just_pressed.get("START", False):
            self.is_open = False
            if audio:
                audio.play_sfx("select")
            return False

        if controller.just_pressed["UP"]:
            self.selected_index = (self.selected_index - 1) % len(self.catalog)
            if audio:
                audio.play_sfx("cursor")
        elif controller.just_pressed["DOWN"]:
            self.selected_index = (self.selected_index + 1) % len(self.catalog)
            if audio:
                audio.play_sfx("cursor")

        # Purchase / Trade with [A/ENTER], Jump [SPACE/Z], or Action [X/Y]
        elif controller.just_pressed["A"] or controller.jump_just_pressed or controller.just_pressed["Y"]:
            item = self.catalog[self.selected_index]
            stock = item.get("stock", None)
            if stock is not None and stock <= 0:
                self.feedback_msg = f"{item['name']} is OUT OF STOCK!"
                self.feedback_color = (255, 140, 100)
                if audio:
                    audio.play_sfx("hurt")
            elif player.eaten_count < item["cost"]:
                needed = item["cost"] - player.eaten_count
                self.feedback_msg = f"Need {item['cost']} Bugs! You are short {needed} bug(s)."
                self.feedback_color = (255, 120, 100)
                if audio:
                    audio.play_sfx("hurt")
            else:
                player.eaten_count -= item["cost"]
                if item["type"] == "consumable":
                    if not hasattr(player, "consumables"):
                        player.consumables = {}
                    player.consumables[item["id"]] = player.consumables.get(item["id"], 0) + 1
                    self.feedback_msg = f"Purchased {item['name']}! Added to your Inventory pouch."
                elif item["id"] == "vitality_heart":
                    player.max_hp = getattr(player, "max_hp", PLAYER_MAX_HP) + 1
                    player.hp = player.max_hp
                    item["stock"] = 0
                    self.feedback_msg = f"Acquired Life Talisman! Max HP expanded to {player.max_hp}!"
                elif item["id"] == "map_cartography":
                    if hasattr(room, "world_manager") and room.world_manager:
                        room.world_manager.visited_rooms.update(room.world_manager.rooms.keys())
                    item["stock"] = 0
                    self.feedback_msg = "Ancient Cartography studied! All zones revealed on Automap!"

                self.feedback_color = (120, 255, 160)
                if audio:
                    audio.play_sfx("shop_buy")
                if room:
                    room.spawn_particle_burst(player.center_x, player.center_y, COLOR_BOSS_GOLD, count=16)

        return True

    def draw(self, surface, title_font, menu_font, player, assets=None):
        overlay = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
        overlay.fill((8, 14, 24))
        overlay.set_alpha(215)
        surface.blit(overlay, (0, 0))

        frame_rect = pygame.Rect(40, 24, 560, 312)
        pygame.draw.rect(surface, (16, 24, 38), frame_rect, border_radius=8)
        pygame.draw.rect(surface, (230, 185, 60), frame_rect, 2, border_radius=8)
        pygame.draw.rect(surface, (60, 95, 135), frame_rect.inflate(-6, -6), 1, border_radius=6)

        header_rect = pygame.Rect(frame_rect.left + 4, frame_rect.top + 4, frame_rect.width - 8, 28)
        pygame.draw.rect(surface, (28, 42, 66), header_rect, border_radius=6)

        short_name = self.shopkeeper_name.split(",")[0].strip()
        title_surf = title_font.render(f"{short_name}'S EMPORIUM", True, (255, 225, 90))
        surface.blit(title_surf, (frame_rect.left + 16, frame_rect.top + 7))

        pouch_text = f"BUG POUCH: {player.eaten_count} Bugs"
        pouch_surf = menu_font.render(pouch_text, True, (130, 245, 210))
        surface.blit(pouch_surf, (frame_rect.right - pouch_surf.get_width() - 16, frame_rect.top + 10))

        list_x = frame_rect.left + 16
        list_y = frame_rect.top + 40
        for i, item in enumerate(self.catalog):
            is_sel = (i == self.selected_index)
            y_pos = list_y + i * 26
            row_rect = pygame.Rect(list_x, y_pos, 260, 22)

            stock = item.get("stock", None)
            is_sold_out = (stock is not None and stock <= 0)

            if is_sel:
                pygame.draw.rect(surface, (36, 60, 92), row_rect, border_radius=4)
                pygame.draw.rect(surface, (80, 245, 210), row_rect, 1, border_radius=4)
                arrow = "> "
                text_col = (255, 255, 255)
            else:
                arrow = "  "
                text_col = (175, 195, 215) if not is_sold_out else (110, 115, 125)

            if is_sold_out:
                price_str = "SOLD OUT"
                price_col = (255, 100, 100)
            else:
                price_str = f"{item['cost']} Bugs"
                price_col = (255, 215, 80) if player.eaten_count >= item["cost"] else (220, 110, 100)

            label = f"{arrow}{item['name']}"
            surface.blit(menu_font.render(label, True, text_col), (list_x + 6, y_pos + 4))

            p_surf = menu_font.render(price_str, True, price_col)
            surface.blit(p_surf, (list_x + 254 - p_surf.get_width(), y_pos + 4))

        detail_rect = pygame.Rect(frame_rect.left + 290, list_y, 250, 170)
        pygame.draw.rect(surface, (12, 18, 30), detail_rect, border_radius=6)
        pygame.draw.rect(surface, (55, 80, 115), detail_rect, 1, border_radius=6)

        sel_item = self.catalog[self.selected_index]
        item_title = menu_font.render(f"[ {sel_item['name'].upper()} ]", True, (255, 225, 90))
        surface.blit(item_title, (detail_rect.left + 12, detail_rect.top + 10))

        type_str = f"Category: {sel_item['type'].capitalize()}"
        surface.blit(menu_font.render(type_str, True, (135, 175, 205)), (detail_rect.left + 12, detail_rect.top + 28))

        if sel_item["type"] == "consumable":
            owned = player.consumables.get(sel_item["id"], 0) if hasattr(player, "consumables") else 0
            owned_str = f"Carrying: {owned} in Pouch"
        else:
            stock = sel_item.get("stock", None)
            owned_str = "Status: AVAILABLE" if stock is None or stock > 0 else "Status: ACQUIRED"
        surface.blit(menu_font.render(owned_str, True, (120, 245, 175)), (detail_rect.left + 12, detail_rect.top + 44))

        desc_words = sel_item["desc"].split(" ")
        lines = []
        cur_line = ""
        for word in desc_words:
            test_line = f"{cur_line} {word}".strip()
            if menu_font.size(test_line)[0] > 224:
                lines.append(cur_line)
                cur_line = word
            else:
                cur_line = test_line
        if cur_line:
            lines.append(cur_line)

        for li, line in enumerate(lines):
            surface.blit(menu_font.render(line, True, (215, 225, 235)), (detail_rect.left + 12, detail_rect.top + 68 + li * 16))

        fb_rect = pygame.Rect(frame_rect.left + 16, frame_rect.bottom - 68, frame_rect.width - 32, 26)
        pygame.draw.rect(surface, (12, 18, 30), fb_rect, border_radius=4)
        pygame.draw.rect(surface, (45, 68, 98), fb_rect, 1, border_radius=4)
        fb_surf = menu_font.render(self.feedback_msg, True, self.feedback_color)
        surface.blit(fb_surf, (fb_rect.centerx - fb_surf.get_width() // 2, fb_rect.top + 6))

        guide_text = "[UP/DOWN] Select Ware  |  [A / SPACE] Trade Bugs  |  [B / ESC / TAB] Leave Shop"
        guide_surf = menu_font.render(guide_text, True, (145, 165, 190))
        surface.blit(guide_surf, (frame_rect.centerx - guide_surf.get_width() // 2, frame_rect.bottom - 28))


def draw_inventory_screen(surface, title_font, menu_font, player, assets=None, selected_item_idx=0, pulse_timer=0):
    """
    Chapter 7H: Comprehensive Metroidvania Inventory Screen
    Displays Froggy's physiology stats, thermal gauges, discovered boss key fragments,
    assembled Master Key, mobility relics, and usable consumables pouch.
    """
    dark_overlay = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    dark_overlay.fill((6, 12, 20))
    dark_overlay.set_alpha(225)
    surface.blit(dark_overlay, (0, 0))

    frame_rect = pygame.Rect(30, 16, 580, 328)
    pygame.draw.rect(surface, (14, 20, 32), frame_rect, border_radius=8)
    pygame.draw.rect(surface, (65, 140, 195), frame_rect, 2, border_radius=8)
    pygame.draw.rect(surface, (30, 60, 90), frame_rect.inflate(-6, -6), 1, border_radius=6)

    header_rect = pygame.Rect(frame_rect.left + 4, frame_rect.top + 4, frame_rect.width - 8, 26)
    pygame.draw.rect(surface, (22, 34, 52), header_rect, border_radius=6)
    title_surf = title_font.render("FROGGY'S INVENTORY & GEAR", True, (245, 215, 75))
    surface.blit(title_surf, (frame_rect.centerx - title_surf.get_width() // 2, frame_rect.top + 6))

    col_w = 265
    left_x = frame_rect.left + 16
    right_x = frame_rect.left + 295
    cur_y = frame_rect.top + 36

    # 1. Physiology & Vitals
    sec1_rect = pygame.Rect(left_x, cur_y, col_w, 134)
    pygame.draw.rect(surface, (18, 26, 42), sec1_rect, border_radius=6)
    pygame.draw.rect(surface, (45, 75, 110), sec1_rect, 1, border_radius=6)

    surface.blit(menu_font.render("— AMPHIBIAN PHYSIOLOGY —", True, (110, 220, 245)), (sec1_rect.left + 10, sec1_rect.top + 8))

    max_hp = getattr(player, "max_hp", PLAYER_MAX_HP)
    hp_str = f"Health: {player.hp} / {max_hp} HP"
    surface.blit(menu_font.render(hp_str, True, (255, 110, 120)), (sec1_rect.left + 10, sec1_rect.top + 26))
    for hi in range(max_hp):
        hx = sec1_rect.left + 130 + hi * 14
        hy = sec1_rect.top + 28
        h_col = COLOR_HEART_RED if hi < player.hp else COLOR_HEART_EMPTY
        pygame.draw.rect(surface, h_col, (hx, hy, 10, 8), border_radius=2)
        pygame.draw.rect(surface, (255, 255, 255), (hx, hy, 10, 8), 1, border_radius=2)

    b_temp = getattr(player, "body_temp", 100.0)
    if b_temp < 35.0:
        temp_state = "CRITICAL FREEZE!"
        temp_col = (110, 215, 255)
    elif b_temp < 90.0:
        temp_state = "Chilled"
        temp_col = (140, 225, 255)
    elif b_temp > 165.0:
        temp_state = "CRITICAL OVERHEAT!"
        temp_col = (255, 80, 50)
    elif b_temp > 110.0:
        temp_state = "Warm / Heated"
        temp_col = (255, 180, 70)
    else:
        temp_state = "Optimal (Stable)"
        temp_col = (120, 245, 160)
    surface.blit(menu_font.render(f"Body Temp: {b_temp:.1f}% ({temp_state})", True, temp_col), (sec1_rect.left + 10, sec1_rect.top + 46))

    hg = getattr(player, "heat_guard_timer", 0) // 60
    cg = getattr(player, "cold_guard_timer", 0) // 60
    if hg > 0 or cg > 0:
        guard_text = f"Buffs: " + (f"FlameGuard {hg}s " if hg > 0 else "") + (f"FrostGuard {cg}s" if cg > 0 else "")
        surface.blit(menu_font.render(guard_text, True, (255, 220, 110)), (sec1_rect.left + 10, sec1_rect.top + 64))
    else:
        surface.blit(menu_font.render("Buffs: None Active", True, (135, 155, 175)), (sec1_rect.left + 10, sec1_rect.top + 64))

    o2 = getattr(player, "oxygen", 100.0)
    o2_col = (100, 235, 255) if o2 > 35.0 else (255, 100, 110)
    surface.blit(menu_font.render(f"Submarine O2: {o2:.1f}%", True, o2_col), (sec1_rect.left + 10, sec1_rect.top + 82))

    surface.blit(menu_font.render(f"Captured Bugs: {player.eaten_count} Bugs", True, (255, 215, 80)), (sec1_rect.left + 10, sec1_rect.top + 104))

    # 2. Relics & Mobility Gear
    sec2_rect = pygame.Rect(left_x, cur_y + 140, col_w, 116)
    pygame.draw.rect(surface, (18, 26, 42), sec2_rect, border_radius=6)
    pygame.draw.rect(surface, (45, 75, 110), sec2_rect, 1, border_radius=6)

    surface.blit(menu_font.render("— ANCIENT RELICS & GEAR —", True, (110, 220, 245)), (sec2_rect.left + 10, sec2_rect.top + 8))

    relics = [
        ("Stomping Boots", getattr(player, "has_stomping_boots", False), "Breaks stone floors & stomps foes"),
        ("Red Boomerang", getattr(player, "has_red_boomerang", False), "Throws 4 high-speed piercing spores"),
        ("Chameleon Lash", True, "8-way tongue grapple & enemy yank"),
        ("Webbed Amphibian", True, "Wall cling, wall-jump & swim"),
    ]
    for ri, (r_name, r_active, r_tip) in enumerate(relics):
        ry = sec2_rect.top + 28 + ri * 20
        status_col = (120, 245, 160) if r_active else (100, 115, 130)
        status_tag = "[EQUIPPED]" if r_active else "[LOCKED]"
        surface.blit(menu_font.render(f"{r_name[:16]:<16} {status_tag}", True, status_col), (sec2_rect.left + 10, ry))

    # 3. Ancient Key Fragments & Master Key (Requirement 2)
    sec3_rect = pygame.Rect(right_x, cur_y, col_w, 134)
    pygame.draw.rect(surface, (18, 26, 42), sec3_rect, border_radius=6)
    pygame.draw.rect(surface, (45, 75, 110), sec3_rect, 1, border_radius=6)

    surface.blit(menu_font.render("— ANCIENT MASTER KEYSTONE —", True, (255, 215, 80)), (sec3_rect.left + 10, sec3_rect.top + 8))

    key_frags = getattr(player, "key_fragments", set())
    has_master = getattr(player, "has_master_key", False) or len(key_frags) >= 4

    frag_data = [
        ("mantis", "Mantis Crest", "Emperor Mantis", (110, 245, 140)),
        ("hound", "Hound Fang", "Dread Hound", (255, 100, 100)),
        ("toad", "Toad Sigil", "Giga Toad", (255, 215, 80)),
        ("falo", "Frost Shard", "Falo Snowman", (110, 225, 255)),
    ]

    for fi, (fid, fname, fboss, fcol) in enumerate(frag_data):
        fy = sec3_rect.top + 26 + fi * 18
        found = (fid in key_frags)
        badge = "[FOUND]" if found else "[MISSING]"
        col = fcol if found else (90, 105, 120)
        surface.blit(menu_font.render(f"{fname:<12} {badge} ({fboss[:9]})", True, col), (sec3_rect.left + 10, fy))

    mk_y = sec3_rect.top + 100
    if has_master:
        pulse_col = (255, 235, 90) if (pulse_timer // 8) % 2 == 0 else (255, 195, 45)
        surface.blit(menu_font.render("★ MASTER KEY: FULLY ASSEMBLED! ★", True, pulse_col), (sec3_rect.left + 10, mk_y))
        surface.blit(menu_font.render("Unlocks Toad Colosseum Sacred Gate", True, (160, 240, 200)), (sec3_rect.left + 10, mk_y + 14))
    else:
        surface.blit(menu_font.render(f"Progress: {len(key_frags)}/4 Fragments Restored", True, (190, 205, 225)), (sec3_rect.left + 10, mk_y))
        surface.blit(menu_font.render("Defeat all 4 bosses to forge key!", True, (135, 155, 175)), (sec3_rect.left + 10, mk_y + 14))

    # 4. Consumables Pouch
    sec4_rect = pygame.Rect(right_x, cur_y + 140, col_w, 104)
    pygame.draw.rect(surface, (18, 26, 42), sec4_rect, border_radius=6)
    pygame.draw.rect(surface, (45, 75, 110), sec4_rect, 1, border_radius=6)

    surface.blit(menu_font.render("— CONSUMABLES POUCH (USE ITEM) —", True, (110, 220, 245)), (sec4_rect.left + 10, sec4_rect.top + 6))

    consumables_list = [
        ("heart_nectar", "Heart Nectar", "Restores +3 HP instantly"),
        ("chill_draught", "Glacial Draught", "Cools body heat & 30s FireGuard"),
        ("warmth_broth", "Pyro Broth", "Warms frostbite & 30s FrostGuard"),
        ("oxygen_reed", "Grotto Air Reed", "Refills 100% O2 underwater"),
    ]

    sel_tip = ""
    for ci, (cid, cname, ctip) in enumerate(consumables_list):
        cy = sec4_rect.top + 22 + ci * 16
        is_sel = (ci == selected_item_idx)
        count = player.consumables.get(cid, 0) if hasattr(player, "consumables") else 0

        row_r = pygame.Rect(sec4_rect.left + 6, cy - 1, col_w - 12, 15)
        if is_sel:
            pygame.draw.rect(surface, (36, 60, 92), row_r, border_radius=3)
            pygame.draw.rect(surface, (80, 245, 210), row_r, 1, border_radius=3)
            cursor = "> "
            c_col = (255, 255, 255)
            sel_tip = ctip
        else:
            cursor = "  "
            c_col = (180, 200, 220) if count > 0 else (100, 115, 130)

        use_tag = "[READY]" if count > 0 else "[EMPTY]"
        label = f"{cursor}{cname:<15} x{count:<2} {use_tag}"
        surface.blit(menu_font.render(label, True, c_col), (sec4_rect.left + 10, cy))

    if sel_tip:
        surface.blit(menu_font.render(f"Effect: {sel_tip}", True, (255, 225, 110)), (sec4_rect.left + 10, sec4_rect.bottom - 16))

    # Status / Feedback Banner inside Inventory Modal
    fb_msg = getattr(player, "inventory_feedback_msg", "Select a remedy with [UP/DOWN] and press [SPACE / ENTER / A] to use.")
    fb_col = getattr(player, "inventory_feedback_col", (170, 225, 245))
    fb_rect = pygame.Rect(frame_rect.left + 16, frame_rect.bottom - 44, frame_rect.width - 32, 18)
    pygame.draw.rect(surface, (10, 16, 26), fb_rect, border_radius=4)
    pygame.draw.rect(surface, (55, 95, 135), fb_rect, 1, border_radius=4)
    fb_surf = menu_font.render(fb_msg, True, fb_col)
    surface.blit(fb_surf, (fb_rect.centerx - fb_surf.get_width() // 2, fb_rect.top + 2))

    footer_rect = pygame.Rect(frame_rect.left + 16, frame_rect.bottom - 24, frame_rect.width - 32, 18)
    pygame.draw.rect(surface, (12, 18, 30), footer_rect, border_radius=4)
    pygame.draw.rect(surface, (45, 68, 98), footer_rect, 1, border_radius=4)

    footer_text = "[UP/DOWN] Select  |  [SPACE / ENTER / A] Use Remedy  |  [TAB / I / ESC] Close"
    f_surf = menu_font.render(footer_text, True, (160, 225, 245))
    surface.blit(f_surf, (footer_rect.centerx - f_surf.get_width() // 2, footer_rect.top + 2))


class SpeedrunTimer:
    """
    High-precision 60 FPS Speedrun Split Timer with MM:SS.xx formatting,
    stage split tracking, and personal best comparison.
    """
    def __init__(self):
        self.total_frames = 0
        self.stage_frames = 0
        self.running = False
        self.splits = []  # List of (stage_label, stage_frames, cumulative_frames)

    def reset(self):
        self.total_frames = 0
        self.stage_frames = 0
        self.running = False
        self.splits.clear()

    def start(self):
        self.reset()
        self.running = True

    def tick(self):
        if self.running:
            self.total_frames += 1
            self.stage_frames += 1

    def record_split(self, stage_label):
        entry = (stage_label, self.stage_frames, self.total_frames)
        self.splits.append(entry)
        self.stage_frames = 0
        return entry

    @staticmethod
    def format_frames(frames):
        total_seconds = max(0.0, frames / float(TARGET_FPS))
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        hundredths = int(round((total_seconds - int(total_seconds)) * 100)) % 100
        return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"


class BossRushManager:
    """
    Chapter 7G: Arcade Boss Rush & Speedrun Split Timer!
    A dedicated time-attack mode challenging players to defeat all 4 bosses
    back-to-back with a competitive split timer and personal best tracking:
      Stage 1: Emperor Mantis ('boss_sanctum')
      Stage 2: The Dread Hound ('hound_sanctum')
      Stage 3: Giga Toad ('toad_colosseum')
      Stage 4: Falo the Evil Snowman ('falo_arena')
    """
    RECORDS_FILE = "boss_rush_records.json"
    STAGES = [
        ("boss_sanctum", "1. EMPEROR MANTIS"),
        ("hound_sanctum", "2. DREAD HOUND"),
        ("toad_colosseum", "3. GIGA TOAD"),
        ("falo_arena", "4. FALO SNOWMAN"),
    ]

    def __init__(self):
        self.timer = SpeedrunTimer()
        self.active = False
        self.completed = False
        self.stage_index = 0
        self.stage_clear_Pending = False
        self.advance_timer = 0
        self.best_total_frames = None
        self.best_splits = {}
        self.load_records()

    def load_records(self):
        if os.path.exists(self.RECORDS_FILE):
            try:
                with open(self.RECORDS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.best_total_frames = data.get("best_total_frames")
                self.best_splits = data.get("best_splits", {})
            except Exception:
                pass

    def save_records(self):
        data = {
            "best_total_frames": self.best_total_frames,
            "best_splits": self.best_splits,
        }
        try:
            with open(self.RECORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def start_rush(self, world, player, camera, audio=None):
        self.active = True
        self.completed = False
        self.stage_index = 0
        self.stage_clear_Pending = False
        self.advance_timer = 0
        self.timer.start()

        # Reset all boss rooms so all 4 bosses are alive and ready
        world.defeated_bosses.clear()
        for room_id, _ in self.STAGES:
            if room_id in world.rooms:
                world.rooms[room_id].boss_defeated = False

        # Equip Froggy with full kit for competitive Boss Rush time-attack!
        player.hp = PLAYER_MAX_HP
        player.body_temp = 100.0
        player.oxygen = 100.0
        player.has_stomping_boots = True
        player.has_red_boomerang = True

        first_room_id, first_label = self.STAGES[0]
        world.warp_directly_to_room(first_room_id, player, camera, audio)
        boss = world.current_room.get_active_boss()
        if boss and not boss.awakened:
            boss.awaken()
        world.current_room.show_banner(f"BOSS RUSH STAGE 1/4: {first_label} - GO!")

    def update(self, world, player, camera, audio=None):
        if not self.active or self.completed:
            return

        room = world.current_room
        if not self.stage_clear_Pending:
            self.timer.tick()
            # Check if current stage boss is defeated
            if room.boss_defeated or room.get_active_boss() is None:
                room.boss_defeated = True
                _, stage_label = self.STAGES[self.stage_index]
                _, stage_f, cum_f = self.timer.record_split(stage_label)
                if stage_label not in self.best_splits or stage_f < self.best_splits[stage_label]:
                    self.best_splits[stage_label] = stage_f

                if self.stage_index + 1 >= len(self.STAGES):
                    # All 4 bosses defeated!
                    self.completed = True
                    self.timer.running = False
                    is_pb = (self.best_total_frames is None) or (self.timer.total_frames < self.best_total_frames)
                    if is_pb:
                        self.best_total_frames = self.timer.total_frames
                    self.save_records()
                    final_str = SpeedrunTimer.format_frames(self.timer.total_frames)
                    pb_tag = " [NEW RECORD!]" if is_pb else ""
                    room.show_banner(f"BOSS RUSH CLEAR! TIME: {final_str}{pb_tag}")
                    if audio:
                        audio.play_sfx("powerup")
                else:
                    self.stage_clear_Pending = True
                    self.advance_timer = 75
                    player.hp = min(PLAYER_MAX_HP, player.hp + 2)
                    player.body_temp = 100.0
                    split_str = SpeedrunTimer.format_frames(cum_f)
                    room.show_banner(f"SPLIT {self.stage_index + 1}/4 CLEAR ({split_str})! NEXT BOSS...")
        else:
            self.advance_timer -= 1
            if self.advance_timer <= 0:
                self.stage_clear_Pending = False
                self.stage_index += 1
                next_room_id, next_label = self.STAGES[self.stage_index]
                world.warp_directly_to_room(next_room_id, player, camera, audio)
                boss = world.current_room.get_active_boss()
                if boss and not boss.awakened:
                    boss.awaken()
                world.current_room.show_banner(f"BOSS RUSH STAGE {self.stage_index + 1}/4: {next_label}!")

    def draw_split_hud(self, surface, font):
        """Renders the competitive Arcade Boss Rush Split Timer panel on the top-right HUD."""
        if not self.active or font is None:
            return

        panel_w = 176
        panel_h = 28 + len(self.STAGES) * 12 + (14 if self.best_total_frames is not None else 2)
        px = INTERNAL_WIDTH - panel_w - 6
        py = 38

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((10, 14, 26, 215))
        surface.blit(panel_surf, (px, py))
        border_col = (255, 215, 70) if self.completed else (90, 235, 255)
        pygame.draw.rect(surface, border_col, (px, py, panel_w, panel_h), 1, border_radius=4)

        total_str = SpeedrunTimer.format_frames(self.timer.total_frames)
        header = font.render(f"BOSS RUSH  {total_str}", True, (255, 235, 95))
        surface.blit(header, (px + 6, py + 4))

        recorded_map = {lbl: (sf, cf) for lbl, sf, cf in self.timer.splits}
        for idx, (_, label) in enumerate(self.STAGES):
            ry = py + 18 + idx * 12
            if label in recorded_map:
                sf, cf = recorded_map[label]
                t_str = SpeedrunTimer.format_frames(cf)
                col = (110, 250, 150)
            elif idx == self.stage_index and not self.completed:
                t_str = SpeedrunTimer.format_frames(self.timer.stage_frames)
                col = (255, 255, 255)
            else:
                t_str = "--:--.--"
                col = (120, 140, 165)

            row_img = font.render(f"{label[:12]:<12} {t_str}", True, col)
            surface.blit(row_img, (px + 6, ry))

        if self.best_total_frames is not None:
            pb_str = SpeedrunTimer.format_frames(self.best_total_frames)
            pb_img = font.render(f"BEST RECORD: {pb_str}", True, (255, 195, 80))
            surface.blit(pb_img, (px + 6, py + panel_h - 13))



class SaveManager:
    """
    Chapter 7E: Checkpoint & Progress Persistence Manager
    Saves Froggy's adventure state to 'save_game.json' when touching Checkpoint
    Totems or saving via the Pause Menu, and restores state upon continue or respawn.
    """
    SAVE_FILE = "save_game.json"

    @classmethod
    def save_to_disk(cls, room_id, player, defeated_bosses=None, visited_rooms=None, world_manager=None):
        data = {
            "version": 1,
            "room_id": room_id,
            "player_x": float(player.x),
            "player_y": float(player.y),
            "hp": int(player.hp),
            "body_temp": float(getattr(player, "body_temp", 100.0)),
            "eaten_count": int(player.eaten_count),
            "has_stomping_boots": bool(getattr(player, "has_stomping_boots", False)),
            "has_red_boomerang": bool(getattr(player, "has_red_boomerang", False)),
            "key_fragments": list(getattr(player, "key_fragments", set())),
            "has_master_key": bool(getattr(player, "has_master_key", False)),
            "consumables": dict(getattr(player, "consumables", {})),
            "master_door_unlocked": bool(getattr(world_manager, "master_door_unlocked", False)) if world_manager else False,
            "defeated_bosses": list(defeated_bosses) if defeated_bosses else [],
            "visited_rooms": list(visited_rooms) if visited_rooms else [room_id],
        }
        try:
            with open(cls.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"[SaveManager] Error saving game: {e}")
            return False

    @classmethod
    def load_from_disk(cls):
        if not os.path.exists(cls.SAVE_FILE):
            return None
        try:
            with open(cls.SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SaveManager] Error loading game: {e}")
            return None

    @classmethod
    def has_save(cls):
        return os.path.exists(cls.SAVE_FILE)

    @classmethod
    def delete_save(cls):
        if os.path.exists(cls.SAVE_FILE):
            try:
                os.remove(cls.SAVE_FILE)
            except Exception:
                pass


# =============================================================================
# CHAPTER 8. ASCII TILEMAP ROOM PARSER, AUTO-TILER & LUSH DECORATOR
# =============================================================================

class DoorPortal:
    def __init__(self, door_id, rect, target_room, target_door, spawn_offset_x, spawn_offset_y, is_master_key_door=False):
        self.door_id = door_id
        self.rect = rect
        self.target_room = target_room
        self.target_door = target_door
        self.spawn_offset_x = spawn_offset_x
        self.spawn_offset_y = spawn_offset_y
        self.is_master_key_door = is_master_key_door


class TileMapRoom:
    def __init__(self, room_id, blueprint, assets, enemy_anims):
        self.room_id = room_id
        self.title = blueprint["title"]
        self.theme = blueprint.get("theme", "canopy")
        self.bg_color = blueprint["bg_color"]
        self.map_coords = blueprint["map_coords"]
        self.boss_trigger_x = blueprint.get("boss_trigger_x", None)
        self.door_configs = blueprint.get("doors", {})
        self.npc_configs = blueprint.get("npcs", [])
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
        self.water_hazards = []      # List of pygame.Rect for glowing swamp pits / magma / submarine water
        self.waterfall_mists = []    # List of pygame.Rect for cooling waterfall mist ('c')
        self.bubble_vents = []       # List of pygame.Rect for submarine air bubble refill vents ('o')
        self.air_bubbles = []        # List of rising AirBubble entities
        self.grapple_nodes = []
        self.door_tiles = []         # List of (world_x, world_y, is_boss_door)
        self.doors = {}
        self.enemy_spawns = []
        self.npc_spawns = []         # List of (char, world_x, world_y) for 'e' and 'k'
        self.npcs = []               # List of FriendlyNPC instances
        self.powerup_spawns = []     # List of (char, world_x, world_y)
        self.enemies = []
        self.powerups = []           # List of CollectiblePowerup instances
        self.boss_projectiles = []
        self.particles = []
        self.poison_clouds = []
        self.steam_particles = []
        self.checkpoint_pos = None
        self.checkpoint_active = False

        # Lush Ambiance Collections (Auto-populated from terrain geometry!)
        self.props_list = []         # List of (kind, world_x, world_y)
        self.hanging_vines = []      # List of HangingVine physics chains
        self.fireflies = []          # List of FireflySpore glowing particles

        self.default_spawn = (64, 64)
        self.active_player_ref = None
        self.boss_defeated = False       # Defeated bosses stay dead; unseals arena doors!
        self.boss_defeated_banner_timer = 0
        self.boss_awakening_banner_timer = 0
        self.custom_banner_text = ""
        self.custom_banner_timer = 0
        self.door_locked_hint_timer = 0  # Timer showing "Gate Sealed" warning prompt
        self.screen_shake_timer = 0
        self.sinister_ambience_active = (self.theme == "sanctum")

        self.rebuild_geometry(respawn_enemies=True)

    def show_banner(self, text):
        """Displays a prominent banner message across the top-center HUD."""
        self.custom_banner_text = text
        self.custom_banner_timer = 220

    def _is_solid_cell(self, r, c):
        """Returns True if (r, c) is a solid '#' tile (or outside map bounds)."""
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return True
        return self.grid[r][c] == '#'

    def rebuild_geometry(self, respawn_enemies=True):
        self.solid_tiles.clear()
        self.autotiled_bricks.clear()
        self.water_hazards.clear()
        self.waterfall_mists.clear()
        self.bubble_vents.clear()
        self.air_bubbles.clear()
        self.grapple_nodes.clear()
        self.door_tiles.clear()
        self.doors.clear()
        self.enemy_spawns.clear()
        self.npc_spawns.clear()
        self.powerup_spawns.clear()
        self.powerups.clear()
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
                        if self.theme in ("ice", "volcanic", "underwater"):
                            t_set = self.assets.autotiles[self.theme]
                        elif is_sanctum_zone:
                            t_set = self.assets.autotiles["sanctum"]
                        else:
                            t_set = self.assets.autotiles["jungle"]
                        if mask == 15 and ((row * 7 + col * 13) % 5 == 0):
                            tex = t_set["15_alt"]
                        else:
                            tex = t_set[mask]
                        self.autotiled_bricks.append((wx, world_y, tex))

                        if self.theme not in ("ice", "volcanic"):
                            # Auto-Plant Lush Foliage on exposed top mossy surfaces (when North is air)
                            if row > 1 and self.grid[row - 1][col] in ('.', '~'):
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

                elif char in ('~', 'v'):
                    self.water_hazards.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                elif char == 'c':
                    self.waterfall_mists.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                elif char == 'o':
                    vent_rect = pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE)
                    self.bubble_vents.append(vent_rect)
                    if self.theme == "underwater":
                        self.water_hazards.append(vent_rect)

                elif char in ('e', 'k'):
                    self.npc_spawns.append((char, world_x, world_y))

                elif char == 'G':
                    self.grapple_nodes.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))
                    if self.theme == "underwater":
                        self.water_hazards.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                elif char == 'S':
                    self.default_spawn = (world_x, world_y)

                elif char == 'T':
                    self.props_list.append(("mantis_totem", world_x - 4, world_y - 16))

                elif char == 'X':
                    self.checkpoint_pos = (world_x, world_y - 16)
                    self.props_list.append(("checkpoint_totem", world_x, world_y - 16))

                # 1-to-1 exact character matching for Door Portals ('A', 'B', 'C', 'D', 'V', 'P', 'Y', 'I', etc.)
                elif char in self.door_configs:
                    tile_rect = pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE)
                    cfg = self.door_configs[char]
                    is_boss_d = (cfg.get("target_room") == "boss_sanctum") or (self.theme == "sanctum") or (self.boss_trigger_x is not None)
                    self.door_tiles.append((world_x, world_y, is_boss_d, char))
                    if char not in door_bounds:
                        door_bounds[char] = tile_rect
                    else:
                        door_bounds[char] = door_bounds[char].union(tile_rect)

                elif char in ('E', 'F', 'N', 'W', 'M', 'H', 'Q', 'b', 'w', 'O'):
                    self.enemy_spawns.append((char, world_x, world_y))
                    if self.theme == "underwater":
                        self.water_hazards.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                elif char in ('J', 'R'):
                    self.powerup_spawns.append((char, world_x, world_y))

                col += 1

        for door_char, union_rect in door_bounds.items():
            cfg = self.door_configs.get(door_char)
            if cfg:
                is_master = bool(cfg.get("is_master_key_door")) or (cfg.get("target_room") == "victory_chamber")
                self.doors[door_char] = DoorPortal(
                    door_id=door_char,
                    rect=union_rect,
                    target_room=cfg["target_room"],
                    target_door=cfg["target_door"],
                    spawn_offset_x=cfg["spawn_offset_x"],
                    spawn_offset_y=cfg["spawn_offset_y"],
                    is_master_key_door=is_master,
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
        self.npcs.clear()
        self.powerups.clear()
        self.boss_projectiles.clear()
        self.particles.clear()
        self.poison_clouds.clear()
        self.steam_particles.clear()
        self.air_bubbles.clear()
        self.sinister_ambience_active = (self.theme == "sanctum")

        # Spawn Friendly NPC Frogs (Elders & Shopkeepers) from blueprint configs & ASCII grid ('e', 'k')
        for npc_cfg in self.npc_configs:
            npc = FriendlyNPC(
                x=npc_cfg["x"],
                y=npc_cfg["y"],
                kind=npc_cfg.get("kind", "elder"),
                name=npc_cfg.get("name"),
                dialogue=npc_cfg.get("dialogue"),
                shop_cost=npc_cfg.get("shop_cost", 1),
                shop_item=npc_cfg.get("shop_item"),
                enemy_anims=self.enemy_anims,
            )
            npc.snap_to_ground(self)
            self.npcs.append(npc)
        for char, wx, wy in self.npc_spawns:
            kind = "shopkeeper" if char == 'k' else "elder"
            # Avoid duplicating if a blueprint npc_cfg is already at the same spot
            if not any(math.hypot(n.x - wx, n.y - (wy - 12)) < 48 for n in self.npcs):
                npc = FriendlyNPC(wx, wy - 12, kind=kind, enemy_anims=self.enemy_anims)
                npc.snap_to_ground(self)
                self.npcs.append(npc)

        # Spawn relic pedestals (if not already collected by Froggy)
        for char, wx, wy in self.powerup_spawns:
            if char == 'J':
                if not (self.active_player_ref and getattr(self.active_player_ref, "has_stomping_boots", False)):
                    self.powerups.append(CollectiblePowerup(wx, wy, "stomping_boots", self.assets))
            elif char == 'R':
                if not (self.active_player_ref and getattr(self.active_player_ref, "has_red_boomerang", False)):
                    self.powerups.append(CollectiblePowerup(wx, wy, "red_boomerang", self.assets))

        # Spawn troop enemies and colossi
        for char, wx, wy in self.enemy_spawns:
            if char == 'E':
                self.enemies.append(MossBeetle(wx, wy, self.enemy_anims))
            elif char == 'F':
                self.enemies.append(BuzzFly(wx, wy, self.enemy_anims))
            elif char == 'N':
                self.enemies.append(SoldierAnt(wx, wy, self.enemy_anims))
            elif char == 'W':
                self.enemies.append(ShadowSpider(wx, wy, self.enemy_anims))
            elif char == 'b':
                self.enemies.append(StinkBug(wx, wy, self.enemy_anims))
            elif char == 'w':
                self.enemies.append(IceWolfSpider(wx, wy, self.enemy_anims))
            elif char == 'M':
                # Defeated bosses NEVER respawn! Once slain, they remain permanently defeated!
                if not self.boss_defeated:
                    boss = EmperorMantis(wx, wy, self.enemy_anims)
                    if self.theme == "sanctum":
                        boss.awaken()
                    self.enemies.append(boss)
            elif char == 'H':
                if not self.boss_defeated:
                    # Dread Hound is 80x76; align his feet with the bottom of the spawn tile (wy + TILE_SIZE)
                    hound_y = wy + TILE_SIZE - 76
                    boss = DreadHoundBoss(wx, hound_y, self.enemy_anims)
                    if self.theme == "sanctum":
                        boss.awaken()
                    self.enemies.append(boss)
            elif char == 'Q':
                if not self.boss_defeated:
                    # Giga Toad is 64x64; align his feet with the bottom of the spawn tile (wy + TILE_SIZE)
                    toad_y = wy + TILE_SIZE - 64
                    boss = GigaToadBoss(wx, toad_y, self.enemy_anims)
                    if self.theme == "sanctum":
                        boss.awaken()
                    self.enemies.append(boss)
            elif char == 'O':
                if not self.boss_defeated:
                    boss = FaloSnowmanBoss(wx, wy, self.enemy_anims)
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

        # Check if Froggy just crossed the Boss Awakening threshold!
        if boss is not None and not boss.awakened:
            trigger_x = self.boss_trigger_x if self.boss_trigger_x is not None else (boss.home_x - 220)
            if player.center_x >= trigger_x:
                boss.awaken()
                self.sinister_ambience_active = True
                self.boss_awakening_banner_timer = 190
                self.screen_shake_timer = 45
                if audio:
                    boss_n = getattr(boss, "name", "")
                    if boss_n == "THE DREAD HOUND":
                        audio.play_sfx("hound_roar")
                        audio.play_music("boss_hound")
                    elif boss_n == "GIGA TOAD":
                        audio.play_sfx("toad_grunt")
                        audio.play_music("boss_toad")
                    elif boss_n == "FALO THE EVIL SNOWMAN":
                        audio.play_sfx("boss_roar")
                        audio.play_music("boss_snowman")
                    else:
                        audio.play_sfx("boss_roar")
                        audio.play_music("boss_mantis")

        for enemy in self.enemies:
            if enemy.alive:
                enemy.update(self)
        self.enemies = [e for e in self.enemies if e.alive]

        for npc in self.npcs:
            npc.update(player, self, audio)

        for p in self.powerups:
            p.update(player, self, audio)
        self.powerups = [p for p in self.powerups if not p.collected]

        # Checkpoint Totem interaction & Auto-Save
        if self.checkpoint_pos and player is not None:
            cx, cy = self.checkpoint_pos
            c_rect = pygame.Rect(cx - 8, cy - 8, 32, 40)
            if c_rect.colliderect(player.rect):
                if not self.checkpoint_active:
                    self.checkpoint_active = True
                    player.hp = PLAYER_MAX_HP
                    player.body_temp = 100.0
                    player.oxygen = 100.0
                    self.show_banner("CHECKPOINT SAVED - HEALTH & WARMTH RESTORED")
                    if audio:
                        audio.play_sfx("powerup")
                    self.spawn_particle_burst(cx + 8, cy + 12, (100, 240, 255), count=30)
                    world_mgr = getattr(player, "world_manager_ref", None)
                    def_bosses = getattr(world_mgr, "defeated_bosses", set()) if world_mgr else set()
                    vis_rooms = getattr(world_mgr, "visited_rooms", set()) if world_mgr else {self.room_id}
                    SaveManager.save_to_disk(self.room_id, player, def_bosses, vis_rooms, world_mgr)

        # Poison gas clouds update
        for cloud in self.poison_clouds:
            cloud.update()
        self.poison_clouds = [c for c in self.poison_clouds if c.alive]

        # Steam particles update
        for sp in self.steam_particles:
            sp.update()
        self.steam_particles = [sp for sp in self.steam_particles if sp.alive]

        # Submarine air bubbles update & emission from bubble vents ('o')
        for ab in self.air_bubbles:
            ab.update(self)
        self.air_bubbles = [ab for ab in self.air_bubbles if ab.alive]

        if self.bubble_vents and (pulse_timer % 16 == 0):
            for v_rect in self.bubble_vents:
                if random.random() < 0.70:
                    self.air_bubbles.append(AirBubble(v_rect.centerx + random.uniform(-3, 3), v_rect.top))

        # Glacial hot springs steam generation
        if self.theme == "ice" and self.water_hazards and (pulse_timer % 3 == 0):
            for w_rect in self.water_hazards:
                if random.random() < 0.28:
                    sx = random.uniform(w_rect.left, w_rect.right)
                    sy = w_rect.top + random.uniform(0, 4)
                    self.steam_particles.append(SteamParticle(sx, sy))

        # Volcanic magma embers & cooling waterfall mist spray
        if self.theme == "volcanic" and (pulse_timer % 4 == 0):
            for w_rect in self.water_hazards:
                if random.random() < 0.22:
                    ex = random.uniform(w_rect.left, w_rect.right)
                    ey = w_rect.top
                    self.particles.append(Particle(ex, ey, random.uniform(-0.4, 0.4), random.uniform(-2.2, -1.0), (255, 165, 40), 22))
            for m_rect in self.waterfall_mists:
                if random.random() < 0.14:
                    mx = random.uniform(m_rect.left, m_rect.right)
                    my = random.uniform(m_rect.top, m_rect.bottom)
                    self.steam_particles.append(SteamParticle(mx, my))

        # If this room contains a boss encounter ('M', 'H', 'Q', or 'O') and no alive boss remains,
        # trigger the one-shot Boss Defeat sequence, unsealing all locked doors permanently!
        room_has_boss = any(char in ('M', 'H', 'Q', 'O') for char, _, _ in self.enemy_spawns)
        if room_has_boss and not self.boss_defeated and self.get_active_boss() is None:
            self.boss_defeated = True
            self.boss_defeated_banner_timer = 260
            self.sinister_ambience_active = False
            world_mgr = getattr(player, "world_manager_ref", None)
            if world_mgr:
                world_mgr.defeated_bosses.add(self.room_id)
            for door in self.doors.values():
                self.spawn_particle_burst(door.rect.centerx, door.rect.centery, COLOR_BOSS_GOLD, count=35)
                self.spawn_particle_burst(door.rect.centerx, door.rect.centery, COLOR_DOOR_GLOW, count=30)
            if audio:
                audio.play_sfx("select")
                audio.play_music("ice" if self.theme == "ice" else "level")

        if self.boss_defeated_banner_timer > 0:
            self.boss_defeated_banner_timer -= 1
        if self.boss_awakening_banner_timer > 0:
            self.boss_awakening_banner_timer -= 1
        if self.custom_banner_timer > 0:
            self.custom_banner_timer -= 1
        if self.door_locked_hint_timer > 0:
            self.door_locked_hint_timer -= 1
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

    def get_grapple_node_along_line(self, x1, y1, x2, y2, threshold=22.0):
        """
        True continuous whip/shaft collision: checks if ANY part of the tongue shaft
        (tip, shaft, or sides) intersects or grazes within threshold distance of a grapple node.
        Matches Super Castlevania IV whip behavior where whipping past or grazing a ring latches on!
        """
        ab_x = x2 - x1
        ab_y = y2 - y1
        len_sq = ab_x * ab_x + ab_y * ab_y

        for node in self.grapple_nodes:
            # 1. Expanded box clip: generous 22px expansion around the 16x16 node
            if node.inflate(22, 22).clipline(x1, y1, x2, y2):
                return node

            # 2. Continuous capsule distance check from node center to tongue segment
            cx, cy = node.centerx, node.centery
            if len_sq < 0.01:
                dist = math.hypot(cx - x1, cy - y1)
            else:
                t = max(0.0, min(1.0, ((cx - x1) * ab_x + (cy - y1) * ab_y) / len_sq))
                close_x = x1 + t * ab_x
                close_y = y1 + t * ab_y
                dist = math.hypot(cx - close_x, cy - close_y)

            if dist <= threshold:
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

    def is_door_locked(self, door_id):
        """
        Boss Arena & Master Key Sanctuary Lockdown System:
        Exit doors are sealed shut by ancient crimson force fields during boss battles.
        The Sacred Master Door in the Toad Colosseum requires all 4 Boss Key Fragments to unseal!
        """
        door = self.doors.get(door_id)
        if door and getattr(door, "is_master_key_door", False):
            wm = getattr(self, "world_manager", None)
            if not (wm and getattr(wm, "master_door_unlocked", False)):
                return True
        if self.boss_defeated:
            return False
        # If an active boss is in this room, doors are locked!
        if self.get_active_boss() is not None:
            return True
        for char, _, _ in self.enemy_spawns:
            if char in ('M', 'H', 'Q', 'O'):
                return True
        return False

    def get_touched_door(self, player_rect):
        for door in self.doors.values():
            if door.rect.colliderect(player_rect):
                if self.is_door_locked(door.door_id):
                    self.door_locked_hint_timer = 45
                    if getattr(door, "is_master_key_door", False):
                        wm = getattr(self, "world_manager", None)
                        n_frags = len(getattr(wm, "key_fragments_cache", set())) if wm else 0
                        self.show_banner(f"ANCIENT SANCTUARY SEAL: 4 KEY FRAGMENTS REQUIRED ({n_frags}/4 RESTORED)")
                    return None
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
                        elif kind == "checkpoint_totem":
                            lt = self.assets.lights.get("cyan")
                            if lt:
                                surface.blit(lt, (sx + 8 - lt.get_width() // 2, sy + 12 - lt.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

        # 4. 4-BIT AUTO-TILED TERRAIN BLOCKS
        for bx, by, tex in self.autotiled_bricks:
            sx = int(bx - camera_x)
            sy = int(by - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                surface.blit(tex, (sx, sy))

        # 5. ANIMATED BIOLUMINESCENT SWAMP WATER OR MOLTEN VOLCANIC MAGMA
        if self.theme == "volcanic" and "lava" in self.assets.special_tiles:
            water_tex = self.assets.special_tiles["lava"][(pulse_timer // 6) % 4]
        else:
            water_tex = self.assets.special_tiles["water"][(pulse_timer // 8) % 4]
        if water_tex is None:
            water_tex = self.assets.special_tiles["water"][0]
        for w_rect in self.water_hazards:
            sx = int(w_rect.x - camera_x)
            sy = int(w_rect.y - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                if water_tex:
                    surface.blit(water_tex, (sx, sy))

        # 5B. CASCADING COLD WATERFALL MIST COLUMNS ('c' in Volcanic Magma Chasm)
        wf_frames = self.assets.special_tiles.get("waterfall", [])
        wf_tex = wf_frames[(pulse_timer // 4) % len(wf_frames)] if wf_frames else None
        for m_rect in self.waterfall_mists:
            sx = int(m_rect.x - camera_x)
            sy = int(m_rect.y - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                if wf_tex:
                    surface.blit(wf_tex, (sx, sy))
                else:
                    pygame.draw.rect(surface, (140, 235, 255), (sx, sy, TILE_SIZE, TILE_SIZE))

        # 5C. SUBMARINE OXYGEN BUBBLE VENTS ('o' in Sunken Grotto)
        bv_frames = self.assets.special_tiles.get("bubble_vent", [])
        bv_tex = bv_frames[(pulse_timer // 12) % len(bv_frames)] if bv_frames else None
        cyan_light = self.assets.lights.get("cyan")
        for v_rect in self.bubble_vents:
            sx = int(v_rect.x - camera_x)
            sy = int(v_rect.y - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                if cyan_light:
                    surface.blit(cyan_light, (sx + 8 - cyan_light.get_width() // 2, sy + 8 - cyan_light.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
                if bv_tex:
                    surface.blit(bv_tex, (sx, sy))
                else:
                    pygame.draw.circle(surface, (95, 240, 255), (sx + 8, sy + 8), 5, 1)

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

        # 7. ANIMATED RUNE PORTAL DOORS, METROID AIRLOCKS & MASTER KEY GATE
        door_frame = (pulse_timer // 6) % 4
        for dx, dy, is_boss_d, d_char in self.door_tiles:
            sx = int(dx - camera_x)
            sy = int(dy - camera_y)
            d_tex = self.assets.special_tiles["boss_door" if is_boss_d else "door"][door_frame]
            surface.blit(d_tex, (sx, sy))

        glow_radius = int(2 + math.sin(pulse_timer * 0.12) * 2)
        for door_id, door in self.doors.items():
            screen_door = door.rect.move(-int(camera_x), -int(camera_y))
            is_locked = self.is_door_locked(door_id)
            is_master = getattr(door, "is_master_key_door", False)

            if is_master:
                # Colossal 48x64 Master Key Door with 4 glowing runic fragment sockets & amphibian eye
                wm = getattr(self, "world_manager", None)
                is_unlocked = getattr(wm, "master_door_unlocked", False) if wm else False
                frags = getattr(wm, "key_fragments_cache", set()) if wm else set()
                num_frags = 4 if is_unlocked else min(4, len(frags))
                mk_states = self.assets.special_tiles.get("master_key_door_states", [])
                mk_surf = mk_states[num_frags] if num_frags < len(mk_states) else self.assets.special_tiles.get("master_key_door")
                if mk_surf:
                    draw_x = screen_door.centerx - mk_surf.get_width() // 2
                    draw_y = screen_door.bottom - mk_surf.get_height()
                    surface.blit(mk_surf, (draw_x, draw_y))
                    aura_col = COLOR_BOSS_GOLD if is_unlocked else (255, 60, 80)
                    pygame.draw.rect(surface, aura_col, pygame.Rect(draw_x, draw_y, mk_surf.get_width(), mk_surf.get_height()), 2, border_radius=4)
                    # Pulsing runic eye glow
                    eye_y = draw_y + 12
                    eye_pulse = int(2 + math.sin(pulse_timer * 0.18) * 2)
                    eye_col = (255, 235, 120) if is_unlocked else (255, 45, 65)
                    pygame.draw.circle(surface, eye_col, (screen_door.centerx, eye_y), eye_pulse)
            else:
                # Metroid Airlock Doors (Cyan normal / Red boss blast shield)
                m_surf = self.assets.special_tiles.get("metroid_door_red" if is_locked else "metroid_door_cyan")
                if m_surf:
                    mx = screen_door.centerx - m_surf.get_width() // 2
                    my = screen_door.bottom - m_surf.get_height()
                    surface.blit(m_surf, (mx, my))

            if is_locked:
                seal_col = (255, 45, 65) if (pulse_timer // 5) % 2 == 0 else (210, 20, 40)
                pygame.draw.rect(surface, seal_col, screen_door.inflate(glow_radius, glow_radius), 2)
                pygame.draw.line(surface, seal_col, screen_door.topleft, screen_door.bottomright, 2)
                pygame.draw.line(surface, seal_col, screen_door.bottomleft, screen_door.topright, 2)
                pygame.draw.circle(surface, (255, 200, 210), screen_door.center, 3)
            else:
                pygame.draw.rect(surface, COLOR_DOOR_GLOW, screen_door.inflate(glow_radius, glow_radius), 1)

        # 8. RELIC POWER-UPS, FRIENDLY NPCS, ENEMIES, BOSS & PROJECTILES
        for npc in self.npcs:
            npc.draw(surface, camera_x, camera_y, self.assets)

        for powerup in self.powerups:
            powerup.draw(surface, camera_x, camera_y)

        for enemy in self.enemies:
            if enemy.alive:
                enemy.draw(surface, camera_x, camera_y, self.assets)

        for wave in self.boss_projectiles:
            wave.draw(surface, camera_x, camera_y, self.assets)

        for p in self.particles:
            p.draw(surface, camera_x, camera_y)

        for cloud in self.poison_clouds:
            cloud.draw(surface, camera_x, camera_y)

        for sp in self.steam_particles:
            sp.draw(surface, camera_x, camera_y)

        for ab in self.air_bubbles:
            ab.draw(surface, camera_x, camera_y)

        # 9. FLOATING BIOLUMINESCENT FIREFLIES & SPORES (Foreground Ambiance)
        for ff in self.fireflies:
            ff.draw(surface, camera_x, camera_y, self.assets, pulse_timer)

    def draw_npc_dialogues(self, surface, font, camera_x, camera_y):
        for npc in self.npcs:
            if npc.player_near:
                npc.draw_dialogue_bubble(surface, font, camera_x, camera_y)


# =============================================================================
# CHAPTER 9. METROIDVANIA WORLD MANAGER
# =============================================================================

class WorldManager:
    def __init__(self, blueprints, assets, enemy_anims, starting_room_id):
        self.assets = assets
        self.rooms = {}
        for room_id, bp in blueprints.items():
            r = TileMapRoom(room_id, bp, assets, enemy_anims)
            r.world_manager = self
            self.rooms[room_id] = r
        self.current_room = self.rooms[starting_room_id]
        self.visited_rooms = {starting_room_id}
        self.defeated_bosses = set()
        self.transition_state = "NONE"
        self.fade_alpha = 0
        self.pending_door = None
        self.show_hints = False       # Hidden by default; toggled via L Trigger / LB / Q / L / H
        self.master_door_unlocked = False
        self.active_shop = None
        self.key_fragments_cache = set()
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
            if self.current_room.room_id in self.defeated_bosses:
                self.current_room.boss_defeated = True
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
                    audio.play_music("boss_mantis")
                elif room_id == "hound_sanctum":
                    self.current_room.boss_awakening_banner_timer = 180
                    self.current_room.screen_shake_timer = 40
                    audio.play_sfx("hound_roar")
                    audio.play_music("boss_hound")
                elif room_id == "toad_colosseum":
                    self.current_room.boss_awakening_banner_timer = 180
                    self.current_room.screen_shake_timer = 40
                    audio.play_sfx("toad_grunt")
                    audio.play_music("boss_toad")
                elif room_id == "falo_arena":
                    self.current_room.boss_awakening_banner_timer = 180
                    self.current_room.screen_shake_timer = 40
                    audio.play_sfx("boss_roar")
                    audio.play_music("boss_snowman")
                elif self.current_room.theme == "ice":
                    audio.play_music("ice")
                elif self.current_room.theme == "volcanic":
                    audio.play_music("volcanic")
                elif self.current_room.theme == "underwater":
                    audio.play_music("underwater")
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
        if self.current_room.room_id in self.defeated_bosses:
            self.current_room.boss_defeated = True
        self.current_room.spawn_enemies()

        dest_door = self.current_room.doors.get(target_door_id)
        if dest_door is not None:
            is_ceiling_door = (dest_door.rect.top <= 16)
            is_floor_door = (dest_door.rect.bottom >= self.current_room.world_height - 16)
            if is_ceiling_door:
                spawn_x = dest_door.rect.centerx - (player.width * 0.5) + offset_x
                spawn_y = dest_door.rect.bottom + 4 + max(0, offset_y)
            elif is_floor_door:
                spawn_x = dest_door.rect.centerx - (player.width * 0.5) + offset_x
                spawn_y = dest_door.rect.top - player.height - 4 + min(0, offset_y)
            else:
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
                audio.play_music("boss_mantis")
            elif target_room_id == "hound_sanctum":
                self.current_room.boss_awakening_banner_timer = 180
                self.current_room.screen_shake_timer = 40
                audio.play_sfx("hound_roar")
                audio.play_music("boss_hound")
            elif target_room_id == "toad_colosseum":
                self.current_room.boss_awakening_banner_timer = 180
                self.current_room.screen_shake_timer = 40
                audio.play_sfx("toad_grunt")
                audio.play_music("boss_toad")
            elif target_room_id == "falo_arena":
                self.current_room.boss_awakening_banner_timer = 180
                self.current_room.screen_shake_timer = 40
                audio.play_sfx("boss_roar")
                audio.play_music("boss_snowman")
            elif self.current_room.theme == "ice":
                audio.play_music("ice")
            elif self.current_room.theme == "volcanic":
                audio.play_music("volcanic")
            elif self.current_room.theme == "underwater":
                audio.play_music("underwater")
            else:
                audio.play_music("level")

    def draw_fade_overlay(self, surface):
        if self.fade_alpha > 0:
            self.fade_surface.set_alpha(self.fade_alpha)
            surface.blit(self.fade_surface, (0, 0))


# =============================================================================
# CHAPTER 10. SNES / XBOX CONTROLLER ABSTRACTION LAYER
# =============================================================================
# XBOX 360 / XBOX SERIES X|S USB CONTROLLER MAPPING (SDL2 XInput on Windows):
#   - D-Pad (Hat 0) or Left Stick (Axes 0 & 1) : 8-Way Movement & Tongue Aim
#   - Xbox A (Button 0) or Xbox B (Button 1)   : Jump / Double Jump / Wall Jump / Menu Confirm
#   - Xbox X (Button 2) or Xbox Y (Button 3)   : 8-Way Tongue Whip & Grapple Swing
#   - RB (Btn 5), RT (Axis 5), LB (Btn 4), LT  : Spore Boomerang Special Weapon
#   - Start / Menu (Button 7)                  : Pause Game / Confirm Menu
#   - Back / View (Button 6)                   : Toggle HUD (in-game) / Back to Title

class SNESController:
    def __init__(self):
        pygame.joystick.init()
        self.joystick = None
        self._connect_first_gamepad()

        self.held = {
            "UP": False, "DOWN": False, "LEFT": False, "RIGHT": False,
            "A": False, "B": False, "X": False, "Y": False,
            "L": False, "R": False, "START": False, "SELECT": False
        }
        self.prev_held = self.held.copy()
        self.just_pressed = {k: False for k in self.held}
        self.just_released = {k: False for k in self.held}

    def _connect_first_gamepad(self):
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            print(
                f"[Controller] Connected USB Gamepad: {self.joystick.get_name()} "
                f"({self.joystick.get_numbuttons()} buttons, {self.joystick.get_numaxes()} axes, "
                f"{self.joystick.get_numhats()} D-pad hat)"
            )
        else:
            self.joystick = None
            print("[Controller] No Gamepad detected. Using Keyboard SNES fallback mapping.")

    def handle_hotplug_event(self, event):
        """Automatically reconnects if the USB Xbox controller is plugged/unplugged."""
        if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self._connect_first_gamepad()

    def update(self):
        self.prev_held = self.held.copy()
        keys = pygame.key.get_pressed()

        # 1. Keyboard Fallback Mapping
        self.held["LEFT"] = bool(keys[pygame.K_LEFT] or keys[pygame.K_a])
        self.held["RIGHT"] = bool(keys[pygame.K_RIGHT] or keys[pygame.K_d])
        self.held["UP"] = bool(keys[pygame.K_UP] or keys[pygame.K_w])
        self.held["DOWN"] = bool(keys[pygame.K_DOWN] or keys[pygame.K_s])

        self.held["A"] = bool(keys[pygame.K_SPACE] or keys[pygame.K_k] or keys[pygame.K_RETURN])
        self.held["B"] = bool(keys[pygame.K_z])
        self.held["X"] = False
        self.held["Y"] = bool(keys[pygame.K_x] or keys[pygame.K_j])
        self.held["L"] = bool(keys[pygame.K_q] or keys[pygame.K_l] or keys[pygame.K_h])
        self.held["R"] = bool(keys[pygame.K_c] or keys[pygame.K_u] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        self.held["START"] = bool(keys[pygame.K_ESCAPE])
        self.held["SELECT"] = bool(keys[pygame.K_TAB])

        # 2. USB Xbox / XInput Gamepad Mapping
        if self.joystick:
            try:
                num_axes = self.joystick.get_numaxes()
                # Left Analog Stick (Axis 0 = Horizontal, Axis 1 = Vertical)
                if num_axes >= 2:
                    axis_x = self.joystick.get_axis(0)
                    axis_y = self.joystick.get_axis(1)
                    # Radial deadzone of 0.28 for clean 8-directional aiming
                    if math.hypot(axis_x, axis_y) > 0.28:
                        if axis_x < -0.28: self.held["LEFT"] = True
                        if axis_x > 0.28:  self.held["RIGHT"] = True
                        if axis_y < -0.28: self.held["UP"] = True
                        if axis_y > 0.28:  self.held["DOWN"] = True

                # Left Trigger (Axis 4) -> L (Toggle Hints)
                # Right Trigger (Axis 5) -> R (Spore Boomerang Special Weapon)
                # Note: On Windows SDL2 XInput, triggers rest at -1.0 and go to +1.0 when pulled!
                if num_axes >= 5 and self.joystick.get_axis(4) > 0.15:
                    self.held["L"] = True
                if num_axes >= 6 and self.joystick.get_axis(5) > 0.15:
                    self.held["R"] = True

                # Physical D-Pad (Hat 0)
                if self.joystick.get_numhats() > 0:
                    hat_x, hat_y = self.joystick.get_hat(0)
                    if hat_x < 0: self.held["LEFT"] = True
                    if hat_x > 0: self.held["RIGHT"] = True
                    if hat_y > 0: self.held["UP"] = True
                    if hat_y < 0: self.held["DOWN"] = True

                # Face, Bumper & Menu Buttons (Xbox 360 / Series XInput layout)
                num_btns = self.joystick.get_numbuttons()
                # Button 0 (Xbox A - bottom) & Button 1 (Xbox B - right) -> Jump!
                if num_btns > 0 and self.joystick.get_button(0): self.held["B"] = True
                if num_btns > 1 and self.joystick.get_button(1): self.held["A"] = True
                # Button 2 (Xbox X - left, SNES Y position) & Button 3 (Xbox Y - top, "Y" label) -> Tongue!
                if num_btns > 2 and self.joystick.get_button(2): self.held["Y"] = True
                if num_btns > 3 and self.joystick.get_button(3): self.held["Y"] = True
                # Button 4 (LB) -> L (Toggle Tactical Hints)
                # Button 5 (RB) -> R (Spore Boomerang Special Weapon)
                if num_btns > 4 and self.joystick.get_button(4):
                    self.held["L"] = True
                if num_btns > 5 and self.joystick.get_button(5):
                    self.held["R"] = True
                # Button 6 (Back / View) -> SELECT (HUD Toggle)
                if num_btns > 6 and self.joystick.get_button(6):
                    self.held["SELECT"] = True
                # Button 7 (Start / Menu) -> START (Pause / Confirm)
                if num_btns > 7 and self.joystick.get_button(7):
                    self.held["START"] = True
            except pygame.error:
                self.joystick = None

        # 3. Compute Single-Frame Edge Triggers (just_pressed & just_released)
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
        self.height = 16
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)

        self.vx = 0.0
        self.vy = 0.0
        self.facing_right = True

        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.invuln_timer = 0
        self.eaten_count = 0

        # Metroidvania Power-ups & Relics
        self.has_stomping_boots = False
        self.has_red_boomerang = False
        self.key_fragments = set()
        self.has_master_key = False
        self.consumables = {
            "heart_nectar": 1,
            "chill_draught": 0,
            "warmth_broth": 0,
            "oxygen_reed": 0,
        }
        self.heat_guard_timer = 0
        self.cold_guard_timer = 0
        self.in_water = False
        self.prev_in_water = False
        self.in_waterfall_mist = False
        self.prev_in_waterfall_mist = False
        self.in_bubble_vent = False
        self.body_temp = 100.0
        self.hypothermia_timer = 0
        self.overheat_timer = 0
        self.oxygen = 100.0
        self.drown_timer = 0
        self.world_manager_ref = None

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
        self.retract_can_grapple = False

        self.inventory_feedback_msg = "Select a remedy with [UP/DOWN] and press [SPACE / ENTER / A] to use."
        self.inventory_feedback_col = (170, 225, 245)

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
        self.retract_can_grapple = False
        self.projectiles.clear()
        self.double_jump_available = True
        self.door_cooldown = DOOR_COOLDOWN_FRAMES

    def use_consumable(self, item_id, room=None, audio=None):
        """Uses a consumable remedy from Froggy's inventory pouch."""
        item_label = item_id.replace("_", " ").upper()
        count = self.consumables.get(item_id, 0)
        if count <= 0:
            self.inventory_feedback_msg = f"POUCH EMPTY: No {item_label} remaining! Trade bugs at the Shopkeeper."
            self.inventory_feedback_col = (255, 120, 110)
            if room:
                room.show_banner(f"NO {item_label} IN POUCH!")
            if audio:
                audio.play_sfx("hurt")
            return False

        self.consumables[item_id] -= 1
        max_h = getattr(self, "max_hp", PLAYER_MAX_HP)
        if item_id == "heart_nectar":
            old_hp = self.hp
            self.hp = min(max_h, self.hp + 3)
            healed = self.hp - old_hp
            self.inventory_feedback_msg = f"USED HEART NECTAR! Restored +{healed} HP (Health: {self.hp}/{max_h})."
            self.inventory_feedback_col = (120, 255, 160)
            if room:
                room.show_banner(f"USED HEART NECTAR! (+{healed} HP)")
                room.spawn_particle_burst(self.center_x, self.center_y, (120, 255, 140), count=20)
        elif item_id == "chill_draught":
            self.body_temp = 100.0
            self.heat_guard_timer = 60 * 30
            self.inventory_feedback_msg = "USED GLACIAL DRAUGHT! Body cooled to 100% + 30s Lava Flame Guard!"
            self.inventory_feedback_col = (110, 235, 255)
            if room:
                room.show_banner("USED GLACIAL DRAUGHT! (COOLED & 30s FIRE GUARD)")
                room.spawn_particle_burst(self.center_x, self.center_y, (110, 230, 255), count=20)
        elif item_id == "warmth_broth":
            self.body_temp = 100.0
            self.cold_guard_timer = 60 * 30
            self.inventory_feedback_msg = "USED PYRO BROTH! Blood warmed to 100% + 30s Glacial Frost Guard!"
            self.inventory_feedback_col = (255, 185, 95)
            if room:
                room.show_banner("USED PYRO BROTH! (WARMED & 30s FROST GUARD)")
                room.spawn_particle_burst(self.center_x, self.center_y, (255, 140, 60), count=20)
        elif item_id == "oxygen_reed":
            self.oxygen = 100.0
            self.inventory_feedback_msg = "USED GROTTO AIR REED! Submarine Oxygen restored to 100%!"
            self.inventory_feedback_col = (120, 245, 255)
            if room:
                room.show_banner("USED GROTTO AIR REED! (+100% OXYGEN RESTORED)")
                room.spawn_particle_burst(self.center_x, self.center_y, (120, 245, 255), count=16)

        if audio:
            audio.play_sfx("select")
        return True

    def update(self, controller, room, world_manager, audio=None):
        self.world_manager_ref = world_manager
        if world_manager:
            world_manager.key_fragments_cache = self.key_fragments

        if self.door_cooldown > 0:
            self.door_cooldown -= 1
        if self.invuln_timer > 0:
            self.invuln_timer -= 1

        # Check water hazard immersion (Swimming Physics)
        self.in_water = any(self.rect.colliderect(w) for w in room.water_hazards)
        if self.in_water and not self.prev_in_water:
            if audio:
                audio.play_sfx("splash")
            room.spawn_particle_burst(self.center_x, self.rect.bottom, (180, 235, 255), count=14)
            self.vy *= 0.35
        elif not self.in_water and self.prev_in_water and self.vy < 0:
            # Water surface breach jump
            self.vy = min(self.vy, -5.2)
            if audio:
                audio.play_sfx("splash")
            room.spawn_particle_burst(self.center_x, self.rect.bottom, (180, 235, 255), count=14)
        self.prev_in_water = self.in_water

        # Check Cold Waterfall Mist immersion ('c' in Volcanic Magma Chasm)
        self.in_waterfall_mist = any(self.rect.colliderect(m) for m in getattr(room, "waterfall_mists", []))
        if self.in_waterfall_mist and not self.prev_in_waterfall_mist:
            if audio:
                audio.play_sfx("sizzle_mist")
            room.spawn_particle_burst(self.center_x, self.center_y, (140, 240, 255), count=14)
        self.prev_in_waterfall_mist = self.in_waterfall_mist

        # Buff Timers
        if self.heat_guard_timer > 0:
            self.heat_guard_timer -= 1
        if self.cold_guard_timer > 0:
            self.cold_guard_timer -= 1

        # Thermoregulation (Amphibian Thermometer in Glacial & Volcanic Biomes)
        if room.theme == "ice":
            self.overheat_timer = 0
            if self.in_water or self.cold_guard_timer > 0:
                # Steamy geothermal hot springs or Frost Guard protect Froggy!
                self.body_temp = min(100.0, self.body_temp + 0.85)
                self.hypothermia_timer = 0
            else:
                # Freezing glacial air gradually chills cold-blooded amphibian
                self.body_temp = max(0.0, self.body_temp - 0.12)
                if self.body_temp <= 0.0:
                    self.hypothermia_timer += 1
                    # Rapid hypothermia frost damage every 75 frames (1.25s)
                    if self.hypothermia_timer >= 75:
                        self.hypothermia_timer = 0
                        self.hp -= 1
                        self.invuln_timer = PLAYER_INVULN_FRAMES // 2
                        room.spawn_particle_burst(self.center_x, self.center_y, (140, 220, 255), count=14)
                        if audio:
                            audio.play_sfx("hurt")
        elif room.theme == "volcanic":
            self.hypothermia_timer = 0
            if self.in_waterfall_mist or self.heat_guard_timer > 0:
                # Cold waterfall mist or Flame Guard rapidly cools Froggy back down toward 100.0!
                if self.body_temp > 100.0:
                    self.body_temp = max(100.0, self.body_temp - 1.25)
                else:
                    self.body_temp = min(100.0, self.body_temp + 0.65)
                self.overheat_timer = 0
            else:
                # Volcanic heat (and magma pools) drive body_temp UP above 100% toward 200%!
                heat_rate = 0.65 if self.in_water else 0.16
                self.body_temp = min(200.0, self.body_temp + heat_rate)
                if self.body_temp >= 200.0:
                    self.overheat_timer += 1
                    if self.overheat_timer >= 75:
                        self.overheat_timer = 0
                        self.hp -= 1
                        self.invuln_timer = PLAYER_INVULN_FRAMES // 2
                        room.spawn_particle_burst(self.center_x, self.center_y, (255, 95, 35), count=16)
                        if audio:
                            audio.play_sfx("hurt")
        else:
            # Standard tropical/sanctum biomes naturally restore ambient body temperature (100.0)
            if self.body_temp < 100.0:
                self.body_temp = min(100.0, self.body_temp + 0.4)
            elif self.body_temp > 100.0:
                self.body_temp = max(100.0, self.body_temp - 0.6)
            self.hypothermia_timer = 0
            self.overheat_timer = 0

        # Submarine Oxygen & Air Bubble Refill Spots ('o' in Sunken Grotto)
        self.in_bubble_vent = any(self.rect.colliderect(v.inflate(8, 8)) for v in getattr(room, "bubble_vents", []))
        touched_bubble = None
        for ab in getattr(room, "air_bubbles", []):
            if ab.alive and self.rect.colliderect(ab.rect.inflate(8, 8)):
                touched_bubble = ab
                break

        if self.in_bubble_vent or touched_bubble is not None:
            if touched_bubble is not None:
                touched_bubble.alive = False
            if self.oxygen < 98.5 and audio:
                audio.play_sfx("bubble_pop")
            self.oxygen = 100.0
            self.drown_timer = 0
            if random.random() < 0.25:
                room.spawn_particle_burst(self.center_x, self.rect.top, (110, 245, 255), count=4)
        elif room.theme == "underwater" and self.in_water:
            self.oxygen = max(0.0, self.oxygen - 0.15)
            if self.oxygen <= 0.0:
                self.drown_timer += 1
                if self.drown_timer >= 75:
                    self.drown_timer = 0
                    self.hp -= 1
                    self.invuln_timer = PLAYER_INVULN_FRAMES // 2
                    room.spawn_particle_burst(self.center_x, self.center_y, (80, 200, 255), count=14)
                    if audio:
                        audio.play_sfx("hurt")
        else:
            self.oxygen = min(100.0, self.oxygen + 1.2)
            self.drown_timer = 0

        # Friendly NPC & Master Key Door Interaction ([UP] button)
        if controller.just_pressed["UP"] and not self.in_water:
            # 1. Master Key Door unseal interaction check
            interacted_door = False
            for door in getattr(room, "doors", {}).values():
                if getattr(door, "is_master_key_door", False):
                    if abs(self.center_x - door.rect.centerx) < 48 and abs(self.center_y - door.rect.centery) < 48:
                        interacted_door = True
                        if not getattr(world_manager, "master_door_unlocked", False):
                            if len(self.key_fragments) < 4:
                                room.show_banner(f"ANCIENT SANCTUARY SEAL: 4 KEY FRAGMENTS REQUIRED ({len(self.key_fragments)}/4 RESTORED)")
                                room.screen_shake_timer = 20
                                if audio:
                                    audio.play_sfx("boss_hit")
                            else:
                                world_manager.master_door_unlocked = True
                                self.has_master_key = True
                                room.show_banner("★ MASTER KEY AWAKENS! ANCIENT SANCTUARY SEAL SHATTERS! ★")
                                room.screen_shake_timer = 60
                                room.spawn_particle_burst(door.rect.centerx, door.rect.centery, COLOR_BOSS_GOLD, count=50)
                                if audio:
                                    audio.play_sfx("checkpoint")
                            break
            # 2. Friendly NPCs
            if not interacted_door:
                for npc in getattr(room, "npcs", []):
                    if npc.player_near:
                        npc.interact(self, room, audio)
                        break

        # Special Weapon (R Button): Up to 4 active boomerangs if upgraded with Red Boomerang!
        max_spores = 4 if self.has_red_boomerang else 2
        if controller.just_pressed["R"] and len(self.projectiles) < max_spores:
            _, (ux, uy) = controller.get_dpad_vector(self.facing_right)
            self.projectiles.append(SporeBoomerang(self.center_x, self.center_y, ux, uy, is_red=self.has_red_boomerang))
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
            self.retract_can_grapple = True
            self.tongue_state = "EXTENDING"
            if audio:
                audio.play_sfx("tongue")

        if self.tongue_state == "EXTENDING":
            self.tongue_length += TONGUE_EXTEND_SPEED
            tip_x = self.center_x + self.tongue_dir_x * self.tongue_length
            tip_y = self.center_y + self.tongue_dir_y * self.tongue_length

            boss = room.get_active_boss()
            if boss and boss.alive and boss.awakened and boss.rect.inflate(10, 10).collidepoint(tip_x, tip_y):
                if boss.state == "WEAK_EXPOSED" and hasattr(boss, "yank_exposed_weak_point"):
                    pearl = boss.yank_exposed_weak_point(room)
                    self.yanked_enemy = pearl
                    self.tongue_state = "RETRACTING"
                    if audio:
                        audio.play_sfx("boss_hit")
                    return
                elif hasattr(boss, "hit_by_tongue_whip") and boss.hit_by_tongue_whip(room, audio):
                    self.tongue_state = "RETRACTING"
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

            # Raycast grappling check: allows latching if ANY point along the tongue shaft touches an idol!
            hit_anchor = room.get_grapple_node_along_line(self.center_x, self.center_y, tip_x, tip_y)
            if hit_anchor is not None:
                # The tongue is only grabby while holding the button (Y on SNES, X/Y on Xbox, X/J on keyboard)!
                # If the player released the button before contact, it creates sparks and retracts.
                if controller.held["Y"]:
                    self._attach_to_grapple(hit_anchor)
                    if audio:
                        audio.play_sfx("latch")
                else:
                    room.spawn_particle_burst(tip_x, tip_y, COLOR_GRAPPLE_GOLD, count=8)
                    self.tongue_state = "RETRACTING"
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
            tip_x = self.center_x + self.tongue_dir_x * self.tongue_length
            tip_y = self.center_y + self.tongue_dir_y * self.tongue_length

            # Continuous whip grapple check during hold
            if controller.held["Y"]:
                hit_anchor = room.get_grapple_node_along_line(self.center_x, self.center_y, tip_x, tip_y)
                if hit_anchor is not None:
                    self._attach_to_grapple(hit_anchor)
                    if audio:
                        audio.play_sfx("latch")
                    return

            self.tongue_hold_timer -= 1
            if self.tongue_hold_timer <= 0:
                self.tongue_state = "RETRACTING"

        elif self.tongue_state == "RETRACTING":
            self.tongue_length -= TONGUE_RETRACT_SPEED
            tip_x = self.center_x + self.tongue_dir_x * max(0.0, self.tongue_length)
            tip_y = self.center_y + self.tongue_dir_y * max(0.0, self.tongue_length)

            # Continuous whip grapple check during retract (only if we didn't just jump-detach from a swing!)
            if controller.held["Y"] and self.retract_can_grapple and self.yanked_enemy is None and self.tongue_length > 8.0:
                hit_anchor = room.get_grapple_node_along_line(self.center_x, self.center_y, tip_x, tip_y)
                if hit_anchor is not None:
                    self._attach_to_grapple(hit_anchor)
                    if audio:
                        audio.play_sfx("latch")
                    return

            if self.yanked_enemy is not None and self.yanked_enemy.alive:
                self.yanked_enemy.set_center(tip_x, tip_y)

            if self.tongue_length <= 14.0:
                self._swallow_yanked_enemy(room, audio)

            if self.tongue_length <= 0.0:
                self.tongue_length = 0.0
                self.yanked_enemy = None
                self.retract_can_grapple = False
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
        # 1. Mario-Style Stomp with Stomping Boots
        # When Froggy has Stomping Boots and is falling (vy > 0), landing on an enemy's head
        # crushes/damages them and grants a high Mario-style bounce rebound!
        if self.has_stomping_boots and self.vy > 0:
            for enemy in room.enemies:
                if enemy.alive and not enemy.is_boss and enemy.state != "YANKED":
                    # Check if Froggy's feet intersect the top 12 pixels of the enemy
                    if (self.rect.bottom >= enemy.rect.top - 3 and
                        self.rect.bottom <= enemy.rect.top + 12 and
                        self.rect.right > enemy.rect.left + 2 and
                        self.rect.left < enemy.rect.right - 2):
                        enemy.stomp_kill(room)
                        self.vy = -6.4  # High Mario-style rebound jump!
                        self.double_jump_available = True
                        room.spawn_particle_burst(self.center_x, enemy.rect.top, (255, 230, 90), count=16)
                        if audio:
                            audio.play_sfx("ice_shatter" if isinstance(enemy, IceWolfSpider) else "stomp")
                        return

            # Check Stomping on Colossus Bosses!
            boss = room.get_active_boss()
            if boss and boss.alive and boss.awakened:
                if hasattr(boss, "check_stomp") and boss.check_stomp(self.rect, self.vy):
                    boss.take_stomp_damage(room, audio)
                    self.vy = -7.0  # High rebound jump!
                    self.double_jump_available = True
                    room.spawn_particle_burst(self.center_x, self.rect.bottom, COLOR_BOSS_GOLD, count=25)
                    if audio:
                        audio.play_sfx("stomp")
                    return

        # 2. Invulnerability Frame Gate
        if self.invuln_timer > 0:
            return

        # 3. Enemy Contact Damage
        for enemy in room.enemies:
            if not enemy.is_boss and enemy.alive and enemy.state in ("PATROL", "WINDUP", "CHARGING", "DROP", "HANG", "ASCEND", "STALKING", "AMBUSH_LEAP") and self.rect.colliderect(enemy.rect):
                self._take_damage(push_from_x=enemy.center_x, room=room, audio=audio)
                return

        # 4. Boss Contact Damage
        boss = room.get_active_boss()
        if (
            boss and boss.alive and boss.awakened and
            boss.state not in ("WEAK_EXPOSED", "DAZED", "PANTING", "HURT", "VULNERABLE", "DORMANT", "INTRO_DESCENT") and
            self.rect.colliderect(boss.rect)
        ):
            self._take_damage(push_from_x=boss.center_x, room=room, audio=audio)
            return

        # 5. Boss Projectile Contact Damage
        for wave in room.boss_projectiles:
            if wave.alive and self.rect.colliderect(wave.rect):
                wave.alive = False
                self._take_damage(push_from_x=wave.x, room=room, audio=audio)
                return

        # 6. Poison Gas Cloud Contact Damage
        for cloud in getattr(room, "poison_clouds", []):
            if cloud.alive and cloud.rect.colliderect(self.rect):
                self._take_damage(push_from_x=cloud.x, room=room, audio=audio)
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
        elif abs(self.swing_angular_vel) > 0.01:
            self.facing_right = (self.swing_angular_vel >= 0)

        if controller.jump_just_pressed:
            # Jumping off the rope releases the grapple with a strong upward & forward boost!
            rel_x = self.grapple_anchor.x - self.center_x
            rel_y = self.grapple_anchor.y - self.center_y
            dist = max(1.0, math.hypot(rel_x, rel_y))
            self.tongue_dir_x = rel_x / dist
            self.tongue_dir_y = rel_y / dist
            self.tongue_length = dist
            self.retract_can_grapple = False
            self.tongue_state = "RETRACTING"
            self.vy = min(self.vy - 3.8, JUMP_VELOCITY * 1.08)
            self.vx = self.vx * 1.35 + dx * 1.4
            self.double_jump_available = True
            self.jump_buffer_timer = 0
            room.spawn_particle_burst(self.center_x, self.rect.bottom, COLOR_GRAPPLE_GOLD, count=14)
            if audio:
                audio.play_sfx("jump")
        elif not controller.held["Y"]:
            # Hold-to-Grapple Mechanic:
            # As soon as the player releases the tongue button (Y on SNES, X/Y on Xbox),
            # Froggy immediately releases his grip, flinging along the swing tangent with full momentum!
            rel_x = self.grapple_anchor.x - self.center_x
            rel_y = self.grapple_anchor.y - self.center_y
            dist = max(1.0, math.hypot(rel_x, rel_y))
            self.tongue_dir_x = rel_x / dist
            self.tongue_dir_y = rel_y / dist
            self.tongue_length = dist
            self.retract_can_grapple = False
            self.tongue_state = "RETRACTING"

    def _update_standard_physics(self, controller, room, audio=None):
        # ---------------------------------------------------------------------
        # WATER SWIMMING FLUID DYNAMICS (Zero Damage, 4-Way Swimming & Swim Kick)
        # ---------------------------------------------------------------------
        if self.in_water:
            (dx, dy), _ = controller.get_dpad_vector(self.facing_right)
            # Buoyant gentle sinking (low terminal velocity in water)
            self.vy = min(self.vy + 0.08, 1.8)
            # Fluid drag damping
            self.vx *= 0.88
            self.vy *= 0.90

            # 4-Way Swimming Authority
            if dx != 0:
                self.vx += dx * 0.42
                self.vx = max(-2.4, min(2.4, self.vx))
                self.facing_right = (dx > 0)
            if dy < 0:
                self.vy -= 0.45
                self.vy = max(-2.8, self.vy)
            elif dy > 0:
                self.vy += 0.35
                self.vy = min(2.2, self.vy)

            # Frog Stroke Swim Kick on Jump Press!
            if controller.jump_just_pressed:
                self.vy = -3.8 if dy >= 0 else -4.6
                self.vx += (1.2 if self.facing_right else -1.2)
                self.double_jump_available = True
                room.spawn_particle_burst(self.center_x, self.rect.bottom, (180, 235, 255), count=8)
                if audio:
                    audio.play_sfx("splash")

            self.coyote_timer = COYOTE_TIME_FRAMES
            self.double_jump_available = True
            self._move_and_collide(room)
            return

        # ---------------------------------------------------------------------
        # STANDARD 2D PLATFORMER MOVEMENT & COLLISION
        # ---------------------------------------------------------------------
        (dx, _), _ = controller.get_dpad_vector(self.facing_right)

        if self.coyote_timer > 0: self.coyote_timer -= 1
        if self.jump_buffer_timer > 0: self.jump_buffer_timer -= 1
        if self.wall_jump_lock_timer > 0: self.wall_jump_lock_timer -= 1

        if controller.jump_just_pressed:
            self.jump_buffer_timer = JUMP_BUFFER_FRAMES

        if self.wall_jump_lock_timer == 0:
            if dx != 0:
                accel = MOVE_ACCEL if self.on_ground else AIR_ACCEL
                # Active Turn-Around Damping: crisply brakes momentum when reversing direction
                if (dx > 0 and self.vx < -0.2) or (dx < 0 and self.vx > 0.2):
                    self.vx *= 0.66
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

        # Physical force field barrier collision against sealed boss arena doors!
        for door_id, door in room.doors.items():
            if room.is_door_locked(door_id):
                if self.rect.colliderect(door.rect):
                    if self.vx > 0:
                        self.rect.right = door.rect.left
                        self.touching_wall_dir = 1
                    elif self.vx < 0:
                        self.rect.left = door.rect.right
                        self.touching_wall_dir = -1
                    self.x = float(self.rect.x)
                    self.vx = 0.0
                    room.door_locked_hint_timer = 45
                    room.spawn_particle_burst(self.center_x, self.center_y, (255, 60, 80), count=4)

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
        if self.invuln_timer > PLAYER_INVULN_FRAMES - 18:
            self.anim_state = "hurt"
        elif self.tongue_state == "SWINGING":
            self.anim_state = "swing"
        elif self.in_water:
            self.anim_state = "swim"
        elif self.tongue_state != "INACTIVE":
            self.anim_state = "tongue"
        elif not self.on_ground:
            if self.touching_wall_dir != 0 and self.vy > 0:
                self.anim_state = "wall_slide"
            elif self.vy < 0:
                self.anim_state = "jump"
            else:
                self.anim_state = "fall"
        elif abs(self.vx) > 0.25:
            self.anim_state = "run"
        else:
            self.anim_state = "idle"

    def get_current_sprite(self):
        facing_key = "right" if self.facing_right else "left"
        state = self.anim_state
        if state not in self.animations[facing_key]:
            state = "idle"
        frames = self.animations[facing_key][state]
        if state == "idle":
            cycle = self.anim_timer % 120
            if cycle < 60:
                frame_index = 0                         # Calm resting pose (1.0s)
            elif cycle < 85:
                frame_index = min(1, len(frames) - 1)   # Gentle chest expansion (0.42s)
            elif cycle < 96:
                frame_index = min(2, len(frames) - 1)   # Quick natural blink (0.18s)
            else:
                frame_index = min(3, len(frames) - 1)   # Headband breeze flutter (0.40s)
        elif state == "swim":
            frame_index = (self.anim_timer // 14) % len(frames)
        elif state == "swing":
            frame_index = 0 if abs(self.swing_angular_vel) < 0.02 else 1
            frame_index = min(frame_index, len(frames) - 1)
        else:
            frame_index = (self.anim_timer // 6) % len(frames)
        return frames[frame_index]

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

        sprite = self.get_current_sprite()
        draw_x = int(self.center_x - sprite.get_width() * 0.5 - camera_x)
        draw_y = int(self.rect.bottom - sprite.get_height() - camera_y)
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


def draw_hud_and_minimap(surface, font, player, world_manager, camera, mouse_world_pos, controller, show_builder, pulse_timer, boss_rush=None):
    room = world_manager.current_room
    show_hints = getattr(world_manager, "show_hints", False)

    # Render comic-style speech bubbles for any nearby Friendly NPC Frogs!
    if hasattr(room, "draw_npc_dialogues"):
        room.draw_npc_dialogues(surface, font, camera.render_x, camera.render_y)

    # Only draw mouse builder cursor & prompts if in BUILDER mode!
    if show_builder:
        mx_world, my_world = mouse_world_pos
        col = int(mx_world // TILE_SIZE)
        row = int(my_world // TILE_SIZE)
        cursor_sx = int(col * TILE_SIZE - camera.render_x)
        cursor_sy = int(row * TILE_SIZE - camera.render_y)
        pygame.draw.rect(surface, (255, 230, 90), (cursor_sx, cursor_sy, TILE_SIZE, TILE_SIZE), 1)

        if show_hints:
            help_img = font.render(
                "BUILDER: [Click] '#' | [G+Click] Ring | [E+Click] Beetle | [F+Click] Fly | [R-Click] Erase | [P] Export",
                True, (190, 225, 255)
            )
            surface.blit(help_img, (10, 22))

    # Translucent Top HUD Backing Pill
    # Calculate dynamic width to cleanly fit health, eaten count, room title, and equipped powerup badges!
    score_img = font.render(
        f"EATEN: {player.eaten_count} | {room.title}",
        True, COLOR_HUD_TEXT
    )
    badge_start_x = 86 + score_img.get_width() + 10

    # Calculate badge layout
    badges = []
    if getattr(player, "has_stomping_boots", False):
        badges.append(("[BOOTS]", (255, 220, 80), (45, 35, 12), (255, 200, 60)))
    if getattr(player, "has_red_boomerang", False):
        badges.append(("[RED SPORE x4]", (255, 90, 100), (48, 12, 18), (255, 70, 90)))
    else:
        badges.append(("[SPORE]", (80, 245, 210), (14, 32, 38), (80, 245, 210)))

    # Amphibian Thermometer Gauge (Glacial & Volcanic Biomes)
    body_temp = getattr(player, "body_temp", 100.0)
    if room.theme == "ice" or body_temp < 99.0:
        t_int = int(body_temp)
        if body_temp <= 0.0:
            badges.append(("[FREEZING! 0%]", (255, 70, 80), (55, 12, 18), (255, 60, 60)))
        elif body_temp < 35.0:
            badges.append((f"[CHILLED: {t_int}%]", (255, 175, 50), (45, 28, 10), (255, 150, 40)))
        else:
            badges.append((f"[TEMP: {t_int}%]", (110, 235, 255), (14, 34, 48), (100, 220, 255)))
    elif room.theme == "volcanic" or body_temp > 101.0:
        t_int = int(body_temp)
        if getattr(player, "in_waterfall_mist", False):
            badges.append((f"[MIST COOL: {t_int}%]", (125, 245, 255), (12, 38, 48), (90, 230, 255)))
        elif body_temp >= 200.0:
            badges.append(("[OVERHEAT! 200%]", (255, 70, 60), (62, 12, 12), (255, 90, 40)))
        elif body_temp >= 150.0:
            badges.append((f"[SCORCHING: {t_int}%]", (255, 165, 50), (52, 24, 10), (255, 145, 35)))
        else:
            badges.append((f"[HEAT: {t_int}%]", (255, 210, 95), (42, 26, 12), (255, 185, 65)))

    # Submarine Oxygen Gauge (Sunken Grotto)
    oxygen = getattr(player, "oxygen", 100.0)
    if room.theme == "underwater" or oxygen < 99.0:
        o_int = int(oxygen)
        if oxygen <= 0.0:
            badges.append(("[DROWNING! 0% O2]", (255, 70, 85), (58, 12, 20), (255, 60, 75)))
        elif oxygen < 35.0:
            badges.append((f"[LOW O2: {o_int}%]", (255, 185, 60), (46, 28, 12), (255, 165, 45)))
        else:
            badges.append((f"[O2: {o_int}%]", (95, 245, 255), (12, 36, 48), (80, 225, 250)))

    # Hint toggle status badge & Exact Backend Room ID (Requirement 7)
    if show_hints:
        badges.append((f"[ZONE: {room.room_id}]", (255, 235, 90), (42, 34, 12), (255, 220, 60)))
        badges.append(("[LT: HINTS ON]", (120, 255, 180), (14, 38, 24), (80, 240, 140)))
    else:
        badges.append(("[LT: HINTS OFF]", (135, 155, 180), (18, 22, 30), (60, 75, 95)))

    # Compute total width needed
    total_hud_w = badge_start_x
    for b_text, _, _, _ in badges:
        total_hud_w += font.size(b_text)[0] + 10
    total_hud_w = max(330, total_hud_w + 4)

    pygame.draw.rect(surface, (12, 18, 30), (6, 4, total_hud_w, 16), border_radius=4)
    pygame.draw.rect(surface, (55, 85, 120), (6, 4, total_hud_w, 16), 1, border_radius=4)

    # 5-Heart SNES Health Bar
    for i in range(PLAYER_MAX_HP):
        hx = 12 + i * 14
        hy = 8
        color = COLOR_HEART_RED if i < player.hp else COLOR_HEART_EMPTY
        pygame.draw.rect(surface, color, (hx, hy, 10, 8), border_radius=2)
        pygame.draw.rect(surface, (255, 255, 255), (hx, hy, 10, 8), 1, border_radius=2)

    surface.blit(score_img, (86, 6))

    # Render Equipped Power-Up & Weapon Badges
    cur_bx = badge_start_x
    for b_text, text_col, bg_col, border_col in badges:
        b_surf = font.render(b_text, True, text_col)
        bw, bh = b_surf.get_width() + 6, 12
        pygame.draw.rect(surface, bg_col, (cur_bx, 6, bw, bh), border_radius=2)
        pygame.draw.rect(surface, border_col, (cur_bx, 6, bw, bh), 1, border_radius=2)
        surface.blit(b_surf, (cur_bx + 3, 6))
        cur_bx += bw + 4

    # Super Metroid Style Multi-Story Automap (Normalized Grid)
    all_rooms = list(world_manager.rooms.values())
    min_gx = min(r.map_coords[0] for r in all_rooms)
    min_gy = min(r.map_coords[1] for r in all_rooms)
    max_gx = max(r.map_coords[0] for r in all_rooms)
    max_gy = max(r.map_coords[1] for r in all_rooms)
    grid_w_cells = (max_gx - min_gx + 1)
    cell_w, cell_h = 13, 8
    map_total_w = grid_w_cells * (cell_w + 2)
    map_origin_x = INTERNAL_WIDTH - map_total_w - 6
    map_origin_y = 6

    for room_id, r_obj in world_manager.rooms.items():
        gx, gy = r_obj.map_coords
        norm_gx = gx - min_gx
        norm_gy = gy - min_gy
        cell_rect = pygame.Rect(
            map_origin_x + norm_gx * (cell_w + 2),
            map_origin_y + norm_gy * (cell_h + 2),
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
            if room_id in ("boss_sanctum", "hound_sanctum", "toad_colosseum", "falo_arena"):
                fill_col = (130, 32, 60)
            elif room_id == "victory_chamber":
                fill_col = (30, 115, 80)
            elif getattr(r_obj, "theme", "") == "ice":
                fill_col = (40, 95, 140)
            elif getattr(r_obj, "theme", "") == "volcanic":
                fill_col = (145, 55, 28)
            elif getattr(r_obj, "theme", "") == "underwater":
                fill_col = (24, 115, 138)
            else:
                fill_col = (45, 68, 112)
            pygame.draw.rect(surface, fill_col, cell_rect)
            pygame.draw.rect(surface, (120, 155, 205), cell_rect, 1)
        else:
            pygame.draw.rect(surface, (35, 44, 68), cell_rect, 1)

    # 8-Way Aim Compass
    _, (ux, uy) = controller.get_dpad_vector(player.facing_right)
    compass_center = (map_origin_x - 14, map_origin_y + 10)
    pygame.draw.circle(surface, (30, 42, 68), compass_center, 9)
    pygame.draw.circle(surface, (110, 155, 210), compass_center, 9, 1)
    aim_end = (int(compass_center[0] + ux * 7), int(compass_center[1] + uy * 7))
    pygame.draw.line(surface, COLOR_TONGUE_PINK, compass_center, aim_end, 2)
    pygame.draw.circle(surface, COLOR_BOSS_GOLD, aim_end, 2)

    # Arcade Boss Rush & Speedrun Split Timer HUD
    if boss_rush is not None and boss_rush.active:
        boss_rush.draw_split_hud(surface, font)

    # Flashing Hypothermia / Overheat / Drowning Critical Warnings
    if body_temp <= 0.0 and (pulse_timer // 8) % 2 == 0:
        freeze_surf = font.render("!! WARNING: HYPOTHERMIA CRITICAL - WARM UP IN HOT SPRING !!", True, (130, 240, 255))
        fx = (INTERNAL_WIDTH - freeze_surf.get_width()) // 2
        fy = 24
        pygame.draw.rect(surface, (14, 28, 48), (fx - 8, fy - 3, freeze_surf.get_width() + 16, 16), border_radius=4)
        pygame.draw.rect(surface, (130, 240, 255), (fx - 8, fy - 3, freeze_surf.get_width() + 16, 16), 1, border_radius=4)
        surface.blit(freeze_surf, (fx, fy))
    elif body_temp >= 200.0 and (pulse_timer // 8) % 2 == 0:
        heat_surf = font.render("!! WARNING: VOLCANIC OVERHEAT - COOL OFF IN WATERFALL MIST !!", True, (255, 120, 60))
        fx = (INTERNAL_WIDTH - heat_surf.get_width()) // 2
        fy = 24
        pygame.draw.rect(surface, (48, 14, 12), (fx - 8, fy - 3, heat_surf.get_width() + 16, 16), border_radius=4)
        pygame.draw.rect(surface, (255, 120, 60), (fx - 8, fy - 3, heat_surf.get_width() + 16, 16), 1, border_radius=4)
        surface.blit(heat_surf, (fx, fy))
    elif oxygen <= 0.0 and (pulse_timer // 8) % 2 == 0:
        o2_surf = font.render("!! WARNING: OXYGEN DEPLETED - SWIM TO AIR BUBBLE VENT !!", True, (100, 240, 255))
        fx = (INTERNAL_WIDTH - o2_surf.get_width()) // 2
        fy = 24
        pygame.draw.rect(surface, (12, 32, 48), (fx - 8, fy - 3, o2_surf.get_width() + 16, 16), border_radius=4)
        pygame.draw.rect(surface, (100, 240, 255), (fx - 8, fy - 3, o2_surf.get_width() + 16, 16), 1, border_radius=4)
        surface.blit(o2_surf, (fx, fy))

    # Dedicated Boss Health Bar (Shown once Emperor Mantis, Dread Hound, Giga Toad, or Falo has awakened!)
    active_boss = room.get_active_boss()
    if active_boss is not None and active_boss.alive and active_boss.awakened:
        bar_w = 280
        bar_h = 11
        bar_x = (INTERNAL_WIDTH - bar_w) // 2
        bar_y = INTERNAL_HEIGHT - 22

        pygame.draw.rect(surface, (22, 12, 28), (bar_x - 3, bar_y - 3, bar_w + 6, bar_h + 6), border_radius=4)
        pygame.draw.rect(surface, (255, 205, 70), (bar_x - 3, bar_y - 3, bar_w + 6, bar_h + 6), 1, border_radius=4)

        hp_ratio = max(0.0, min(1.0, active_boss.hp / active_boss.max_hp))
        fill_w = int(bar_w * hp_ratio)
        bar_col = (255, 55, 95) if active_boss.phase == 3 else ((255, 145, 50) if active_boss.phase == 2 else (95, 235, 130))
        if fill_w > 0:
            pygame.draw.rect(surface, bar_col, (bar_x, bar_y, fill_w, bar_h), border_radius=3)

        boss_name = getattr(active_boss, "name", "BOSS")
        if show_hints:
            if boss_name == "THE DREAD HOUND":
                hint_txt = " - JUMP ON HEAD TO STOMP WHEN DAZED! WHIP WITH [Y]!"
            elif boss_name == "GIGA TOAD":
                hint_txt = " - DODGE GROUND POUND! STOMP OR WHIP WHEN PANTING!"
            elif boss_name == "FALO THE EVIL SNOWMAN":
                hint_txt = " - DODGE SNOWBALLS! JUMP ON TOP HAT TO STOMP! MELT WITH [R]!"
            else:
                hint_txt = " - STUN WITH [R], YANK CORE WITH [Y]!"
        else:
            hint_txt = ""

        boss_label = font.render(
            f"{boss_name}  [PHASE {active_boss.phase}]{hint_txt}",
            True, (255, 230, 240)
        )
        surface.blit(boss_label, ((INTERNAL_WIDTH - boss_label.get_width()) // 2, bar_y - 14))

    # Dramatic Boss Awakening Warning Banner
    if room.boss_awakening_banner_timer > 0 and (pulse_timer // 4) % 2 == 0:
        boss = room.get_active_boss()
        bname = boss.name if boss else ("THE DREAD HOUND" if room.room_id == "hound_sanctum" else ("GIGA TOAD" if room.room_id == "toad_colosseum" else "THE EMPEROR MANTIS"))
        warn_surf = font.render(f"!! WARNING: {bname} AWAKENS !!", True, (255, 85, 120))
        wx = (INTERNAL_WIDTH - warn_surf.get_width()) // 2
        wy = 48
        pygame.draw.rect(surface, (32, 10, 24), (wx - 10, wy - 4, warn_surf.get_width() + 20, 20), border_radius=4)
        pygame.draw.rect(surface, (255, 85, 120), (wx - 10, wy - 4, warn_surf.get_width() + 20, 20), 1, border_radius=4)
        surface.blit(warn_surf, (wx, wy))

    # Boss Defeated Victory Banner
    if room.boss_defeated_banner_timer > 0:
        bname = "THE DREAD HOUND" if room.room_id == "hound_sanctum" else ("GIGA TOAD" if room.room_id == "toad_colosseum" else "EMPEROR MANTIS")
        banner_surf = font.render(f"VICTORY! {bname} DEFEATED! GATE UNLOCKED!", True, COLOR_BOSS_GOLD)
        bx = (INTERNAL_WIDTH - banner_surf.get_width()) // 2
        by = (INTERNAL_HEIGHT // 2) - 20
        pygame.draw.rect(surface, (20, 24, 42), (bx - 10, by - 5, banner_surf.get_width() + 20, 22), border_radius=4)
        pygame.draw.rect(surface, COLOR_BOSS_GOLD, (bx - 10, by - 5, banner_surf.get_width() + 20, 22), 1, border_radius=4)
        surface.blit(banner_surf, (bx, by))

    # Custom Power-Up / Relic Acquisition Banner
    if getattr(room, "custom_banner_timer", 0) > 0:
        c_text = room.custom_banner_text
        c_surf = font.render(c_text, True, (255, 235, 110))
        cx = (INTERNAL_WIDTH - c_surf.get_width()) // 2
        cy = 30
        pygame.draw.rect(surface, (18, 24, 38), (cx - 10, cy - 4, c_surf.get_width() + 20, 20), border_radius=4)
        pygame.draw.rect(surface, (80, 220, 240), (cx - 10, cy - 4, c_surf.get_width() + 20, 20), 1, border_radius=4)
        surface.blit(c_surf, (cx, cy))

    # Gate Sealed Warning Banner (Shown when player bumps into locked boss doors and hints are enabled)
    if show_hints and getattr(room, "door_locked_hint_timer", 0) > 0 and (pulse_timer // 4) % 2 == 0:
        bname = "THE DREAD HOUND" if room.room_id == "hound_sanctum" else ("GIGA TOAD" if room.room_id == "toad_colosseum" else "THE EMPEROR MANTIS")
        lock_surf = font.render(f"GATE SEALED! DEFEAT {bname} TO PASS!", True, (255, 75, 95))
        lx = (INTERNAL_WIDTH - lock_surf.get_width()) // 2
        ly = 72
        pygame.draw.rect(surface, (36, 12, 18), (lx - 10, ly - 4, lock_surf.get_width() + 20, 20), border_radius=4)
        pygame.draw.rect(surface, (255, 75, 95), (lx - 10, ly - 4, lock_surf.get_width() + 20, 20), 1, border_radius=4)
        surface.blit(lock_surf, (lx, ly))


# =============================================================================
# CHAPTER 13. LUSH 720p TITLE SCREEN, PAUSE MENU & MAIN ENGINE LOOP
# =============================================================================

def draw_title_screen(surface, title_font, menu_font, selected_index, anim_timer, frog_idle_surf, assets, has_save=False):
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

    if has_save:
        menu_items = [
            "CONTINUE CHECKPOINT",
            "NEW ADVENTURE (START)",
            "ARCADE BOSS RUSH (TIME ATTACK)",
            "CREATE LEVEL (SANDBOX)",
        ]
    else:
        menu_items = [
            "START GAME  (CANOPY TO BOSS)",
            "ARCADE BOSS RUSH (TIME ATTACK)",
            "CREATE LEVEL (SANDBOX BUILDER)",
        ]
    menu_start_y = 182
    row_step = 21 if has_save else 25

    for i, item in enumerate(menu_items):
        is_selected = (i == selected_index)
        col = (255, 255, 255) if is_selected else (140, 165, 195)
        item_img = menu_font.render(item, True, col)
        ix = (INTERNAL_WIDTH - item_img.get_width()) // 2
        iy = menu_start_y + i * row_step

        if is_selected:
            cursor_col = (255, 215, 70) if (anim_timer // 6) % 2 == 0 else (95, 245, 215)
            pill_rect = pygame.Rect(ix - 14, iy - 4, item_img.get_width() + 28, item_img.get_height() + 8)
            pygame.draw.rect(surface, (32, 54, 82), pill_rect, border_radius=4)
            pygame.draw.rect(surface, cursor_col, pill_rect, 1, border_radius=4)

            arrow_img = menu_font.render(">", True, cursor_col)
            surface.blit(arrow_img, (ix - 24, iy))

        surface.blit(item_img, (ix, iy))

    hint_text = "[D-Pad/Stick] Move & Aim  [Xbox A/B] Jump  [Xbox X/Y] Tongue  [RB/RT] Spore"
    hint_img = menu_font.render(hint_text, True, (175, 210, 235))
    hx = (INTERNAL_WIDTH - hint_img.get_width()) // 2
    surface.blit(hint_img, (hx, INTERNAL_HEIGHT - 24))


def draw_game_over_screen(surface, title_font, menu_font, anim_timer, has_save=False):
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

    respawn_label = "[SPACE / A / B]  CONTINUE FROM CHECKPOINT" if has_save else "[SPACE / A / B]  RESPAWN AT ROOM ENTRANCE"
    info_lines = [
        "FROGGY RAN OUT OF HEARTS!",
        "(Tip: Stun beetles with [R] and eat bugs with [Y] to heal +1 Heart!)",
        "",
        respawn_label,
        "[ESCAPE]         RETURN TO TITLE SCREEN",
    ]

    for i, line in enumerate(info_lines):
        col = (255, 230, 90) if "CONTINUE" in line or "RESPAWN" in line else ((215, 225, 240) if i < 2 else (175, 195, 225))
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
    surface.blit(pause_img, (px, 70))

    options = ["RESUME ADVENTURE", "VIEW INVENTORY", "SAVE TO DISK", "RETURN TO TITLE", "QUIT GAME"]
    for i, opt in enumerate(options):
        is_sel = (i == selected_index)
        col = (255, 255, 255) if is_sel else (135, 155, 185)
        img = menu_font.render(opt, True, col)
        ox = (INTERNAL_WIDTH - img.get_width()) // 2
        oy = 135 + i * 26

        if is_sel:
            cursor_col = (80, 245, 210)
            pill_rect = pygame.Rect(ox - 10, oy - 3, img.get_width() + 20, img.get_height() + 6)
            pygame.draw.rect(surface, (35, 52, 82), pill_rect, border_radius=4)
            pygame.draw.rect(surface, cursor_col, pill_rect, 1, border_radius=4)

        surface.blit(img, (ox, oy))


async def main():
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
    boss_rush = BossRushManager()

    game_state = "TITLE"
    game_mode = "ADVENTURE"

    title_selected_index = 0
    pause_selected_index = 0
    inventory_selected_idx = 0

    show_hud = True
    pulse_timer = 0
    running = True

    audio.play_music("title")

    while running:
        pulse_timer += 1

        # =====================================================================
        # STATE A: TITLE SCREEN (Supports both Xbox Controller & Keyboard!)
        # =====================================================================
        if game_state == "TITLE":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                controller.handle_hotplug_event(event)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            controller.update()

            has_save = SaveManager.has_save()
            num_options = 4 if has_save else 3

            if controller.just_pressed["UP"]:
                title_selected_index = (title_selected_index - 1) % num_options
                audio.play_sfx("cursor")
            elif controller.just_pressed["DOWN"]:
                title_selected_index = (title_selected_index + 1) % num_options
                audio.play_sfx("cursor")
            elif controller.jump_just_pressed or controller.just_pressed["START"]:
                audio.play_sfx("select")
                if has_save and title_selected_index == 0:
                    boss_rush.active = False
                    save_data = SaveManager.load_from_disk()
                    saved_room = save_data.get("room_id", "level_1") if save_data else "level_1"
                    if saved_room not in WORLD_BLUEPRINTS:
                        saved_room = "level_1"
                    game_mode = "ADVENTURE"
                    world = WorldManager(WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id=saved_room)
                    if save_data:
                        world.visited_rooms = set(save_data.get("visited_rooms", [saved_room]))
                        world.defeated_bosses = set(save_data.get("defeated_bosses", []))
                        for r_id in world.defeated_bosses:
                            if r_id in world.rooms:
                                world.rooms[r_id].boss_defeated = True
                        px = float(save_data.get("player_x", 64))
                        py = float(save_data.get("player_y", 64))
                        player = FroggyPlayer(px, py, animations)
                        player.hp = int(save_data.get("hp", PLAYER_MAX_HP))
                        player.body_temp = float(save_data.get("body_temp", 100.0))
                        player.eaten_count = int(save_data.get("eaten_count", 0))
                        player.has_stomping_boots = bool(save_data.get("has_stomping_boots", False))
                        player.has_red_boomerang = bool(save_data.get("has_red_boomerang", False))
                        player.key_fragments = set(save_data.get("key_fragments", []))
                        player.has_master_key = bool(save_data.get("has_master_key", False))
                        player.consumables = save_data.get("consumables", {"heart_nectar": 1, "chill_draught": 0, "warmth_broth": 0, "oxygen_reed": 0})
                        world.master_door_unlocked = bool(save_data.get("master_door_unlocked", False))
                    else:
                        player = FroggyPlayer(0, 0, animations)
                    world.current_room.spawn_enemies()
                    camera.set_bounds(world.current_room.world_width, world.current_room.world_height)
                    camera.snap_to(player)
                    game_state = "PLAYING"
                    if world.current_room.theme == "ice":
                        audio.play_music("ice")
                    elif world.current_room.theme == "volcanic":
                        audio.play_music("volcanic")
                    elif world.current_room.theme == "underwater":
                        audio.play_music("underwater")
                    elif world.current_room.theme == "sanctum":
                        audio.play_music("boss_mantis")
                    else:
                        audio.play_music("level")
                elif (not has_save and title_selected_index == 0) or (has_save and title_selected_index == 1):
                    boss_rush.active = False
                    game_mode = "ADVENTURE"
                    world = WorldManager(WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
                    player = FroggyPlayer(0, 0, animations)
                    world.warp_directly_to_room("level_1", player, camera, audio)
                    player.hp = PLAYER_MAX_HP
                    game_state = "PLAYING"
                    audio.play_music("level")
                elif (not has_save and title_selected_index == 1) or (has_save and title_selected_index == 2):
                    game_mode = "BOSS_RUSH"
                    world = WorldManager(WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="boss_sanctum")
                    player = FroggyPlayer(0, 0, animations)
                    boss_rush.start_rush(world, player, camera, audio)
                    game_state = "PLAYING"
                elif (not has_save and title_selected_index == 2) or (has_save and title_selected_index == 3):
                    boss_rush.active = False
                    game_mode = "BUILDER"
                    world.warp_directly_to_room("sandbox_room", player, camera, audio)
                    player.hp = PLAYER_MAX_HP
                    game_state = "PLAYING"
                    audio.play_music("level")

            frog_preview = animations["right"]["idle"][0]
            draw_title_screen(
                snes_canvas, title_font, menu_font,
                title_selected_index, pulse_timer, frog_preview, assets,
                has_save=has_save
            )

        # =====================================================================
        # STATE B: PLAYING (METROIDVANIA ADVENTURE / BOSS RUSH / BUILDER)
        # =====================================================================
        elif game_state == "PLAYING":
            is_builder_active = (game_mode == "BUILDER")

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                controller.handle_hotplug_event(event)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p and is_builder_active:
                        world.current_room.export_ascii_to_console()
                        audio.play_sfx("select")
                    elif event.key == pygame.K_b:
                        world.warp_directly_to_room("boss_sanctum", player, camera, audio)
                    elif event.key in (pygame.K_TAB, pygame.K_i):
                        game_state = "INVENTORY"
                        inventory_selected_idx = 0
                        audio.play_sfx("cursor")

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

            # Pause via Xbox START button or Keyboard ESCAPE
            if controller.just_pressed["START"]:
                game_state = "PAUSED"
                pause_selected_index = 0
                audio.play_sfx("cursor")
            # Open Inventory via Xbox BACK/SELECT or Keyboard TAB/I
            elif controller.just_pressed["SELECT"]:
                game_state = "INVENTORY"
                inventory_selected_idx = 0
                audio.play_sfx("cursor")

            # Toggle Note & Tactical Hint Overlays via Left Trigger / Left Bumper / Key [Q/L/H] (Requirement 7)
            if controller.just_pressed["L"]:
                world.show_hints = not world.show_hints
                audio.play_sfx("select")
                status = "ON" if world.show_hints else "OFF"
                world.current_room.show_banner(f"HINTS: {status} | BACKEND LEVEL: '{world.current_room.room_id}'")

            # Check if an interactive shop was opened
            if world.active_shop is not None:
                game_state = "SHOP"

            if world.is_transitioning:
                world.update_transition(player, camera, audio)
            else:
                world.current_room.update_entities(player, audio, pulse_timer)
                player.update(controller, world.current_room, world, audio)
                if game_mode == "BOSS_RUSH":
                    boss_rush.update(world, player, camera, audio)
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
                    pulse_timer=pulse_timer,
                    boss_rush=boss_rush,
                )

            world.draw_fade_overlay(snes_canvas)

        # =====================================================================
        # STATE C: IN-GAME PAUSE MENU (Xbox Controller & Keyboard)
        # =====================================================================
        elif game_state == "PAUSED":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                controller.handle_hotplug_event(event)

            controller.update()

            if controller.just_pressed["UP"]:
                pause_selected_index = (pause_selected_index - 1) % 5
                audio.play_sfx("cursor")
            elif controller.just_pressed["DOWN"]:
                pause_selected_index = (pause_selected_index + 1) % 5
                audio.play_sfx("cursor")
            elif controller.jump_just_pressed or controller.just_pressed["START"]:
                audio.play_sfx("select")
                if pause_selected_index == 0:
                    game_state = "PLAYING"
                elif pause_selected_index == 1:
                    game_state = "INVENTORY"
                    inventory_selected_idx = 0
                elif pause_selected_index == 2:
                    SaveManager.save_to_disk(world.current_room.room_id, player, world.defeated_bosses, world.visited_rooms, world)
                    world.current_room.show_banner("CHECKPOINT SAVED TO DISK")
                    game_state = "PLAYING"
                elif pause_selected_index == 3:
                    game_state = "TITLE"
                    audio.play_music("title")
                elif pause_selected_index == 4:
                    running = False

            draw_pause_screen(snes_canvas, title_font, menu_font, pause_selected_index, pulse_timer)

        # =====================================================================
        # STATE D: GAME OVER SCREEN (Xbox Controller & Keyboard)
        # =====================================================================
        elif game_state == "GAME_OVER":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                controller.handle_hotplug_event(event)

            controller.update()

            has_save = SaveManager.has_save()
            if controller.jump_just_pressed or controller.just_pressed["START"]:
                audio.play_sfx("select")
                if has_save:
                    save_data = SaveManager.load_from_disk()
                    saved_room = save_data.get("room_id", "level_1") if save_data else "level_1"
                    if saved_room not in WORLD_BLUEPRINTS:
                        saved_room = "level_1"
                    world = WorldManager(WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id=saved_room)
                    if save_data:
                        world.visited_rooms = set(save_data.get("visited_rooms", [saved_room]))
                        world.defeated_bosses = set(save_data.get("defeated_bosses", []))
                        for r_id in world.defeated_bosses:
                            if r_id in world.rooms:
                                world.rooms[r_id].boss_defeated = True
                        px = float(save_data.get("player_x", 64))
                        py = float(save_data.get("player_y", 64))
                        player = FroggyPlayer(px, py, animations)
                        player.hp = int(save_data.get("hp", PLAYER_MAX_HP))
                        player.body_temp = float(save_data.get("body_temp", 100.0))
                        player.eaten_count = int(save_data.get("eaten_count", 0))
                        player.has_stomping_boots = bool(save_data.get("has_stomping_boots", False))
                        player.has_red_boomerang = bool(save_data.get("has_red_boomerang", False))
                        player.key_fragments = set(save_data.get("key_fragments", []))
                        player.has_master_key = bool(save_data.get("has_master_key", False))
                        player.consumables = save_data.get("consumables", {"heart_nectar": 1, "chill_draught": 0, "warmth_broth": 0, "oxygen_reed": 0})
                        world.master_door_unlocked = bool(save_data.get("master_door_unlocked", False))
                    world.current_room.spawn_enemies()
                    camera.set_bounds(world.current_room.world_width, world.current_room.world_height)
                    camera.snap_to(player)
                    game_state = "PLAYING"
                    if world.current_room.theme == "ice":
                        audio.play_music("ice")
                    elif world.current_room.theme == "sanctum":
                        audio.play_music("boss_mantis")
                    else:
                        audio.play_music("level")
                else:
                    player.hp = PLAYER_MAX_HP
                    spawn_x, spawn_y = world.current_room.default_spawn
                    player.teleport_to_room(spawn_x, spawn_y)
                    world.current_room.spawn_enemies()
                    camera.snap_to(player)
                    game_state = "PLAYING"
                    if world.current_room.room_id == "boss_sanctum":
                        audio.play_music("boss_mantis")
                    else:
                        audio.play_music("level")
            elif controller.just_pressed["SELECT"]:
                game_state = "TITLE"
                audio.play_music("title")

            draw_game_over_screen(snes_canvas, title_font, menu_font, pulse_timer, has_save=has_save)

        # =====================================================================
        # STATE E: MODULAR INTERACTIVE SHOP EMPORIUM (Requirement 1)
        # =====================================================================
        elif game_state == "SHOP":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                controller.handle_hotplug_event(event)

            controller.update()
            if world.active_shop:
                is_open = world.active_shop.handle_input(controller, player, world.current_room, audio)
                if not is_open:
                    world.active_shop = None
                    game_state = "PLAYING"
            else:
                game_state = "PLAYING"

            world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, pulse_timer)
            player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
            if world.active_shop:
                world.active_shop.draw(snes_canvas, title_font, menu_font, player, assets)

        # =====================================================================
        # STATE F: METROIDVANIA INVENTORY SCREEN (Requirements 1 & 2)
        # =====================================================================
        elif game_state == "INVENTORY":
            closed_via_key = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                controller.handle_hotplug_event(event)
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_TAB, pygame.K_i, pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    closed_via_key = True

            controller.update()
            if closed_via_key or controller.just_pressed["SELECT"] or controller.just_pressed["START"]:
                game_state = "PLAYING"
                audio.play_sfx("cursor")
            elif controller.just_pressed["UP"]:
                inventory_selected_idx = (inventory_selected_idx - 1) % 4
                audio.play_sfx("cursor")
            elif controller.just_pressed["DOWN"]:
                inventory_selected_idx = (inventory_selected_idx + 1) % 4
                audio.play_sfx("cursor")
            elif controller.just_pressed["A"] or controller.jump_just_pressed or controller.just_pressed["Y"]:
                c_keys = ["heart_nectar", "chill_draught", "warmth_broth", "oxygen_reed"]
                sel_cid = c_keys[inventory_selected_idx]
                player.use_consumable(sel_cid, room=world.current_room, audio=audio)

            world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, pulse_timer)
            player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
            draw_inventory_screen(snes_canvas, title_font, menu_font, player, assets, inventory_selected_idx, pulse_timer)

        # Integer-scale 640x360 retro canvas by 2x to fill the 1280x720 (720p HD) window
        pygame.transform.scale(snes_canvas, (WINDOW_WIDTH, WINDOW_HEIGHT), window)
        pygame.display.flip()
        clock.tick_busy_loop(TARGET_FPS)
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
