"""
===============================================================================
FROGGY: 16-BIT METROIDVANIA TECH DEMO ENGINE (JAMAICAN GROOVE & SMOOTH CAMERA)
===============================================================================
A complete, self-contained 2D platformer engine inspired by Super Castlevania IV,
Super Metroid, and classic 16-bit SNES titles.

NEW REFINEMENTS IN THIS BUILD:
1. Buttery-Smooth Hysteresis Camera (Zero Whiplash & Zero Screen Sticking):
   - Replaced twitchy instant look-ahead with a dual-axis Deadzone Window.
   - Small steps, turning around in place, and normal platforming hops do NOT
     jerk the camera.
   - Pushing against the edge of the window smoothly glides the viewport forward
     using cushioned exponential dampening (LERP).
2. Level 1 Tutorial Redesign ("FROGGY'S FIRST HOP"):
   - Replaced the impassable obstacle on Screen 2 with a properly spaced 48px
     vertical chimney shaft (Mega Man X / Super Metroid style).
   - Traversable path from start to finish:
     - Hop & Run obstacle
     - Double Jump ledge
     - Combat & Swallow (Stun beetle with R, Eat with Y to heal +1 Heart)
     - 2-Walled Chimney Wall-Jump
     - Overhead Castlevania IV Grapple Swing over a pit
     - Exit Door A into the grand Metroidvania castle!
3. Upgraded Chiptune Audio Synthesizer (Jamaican / Dub Froggy Groove):
   - Synthesizes an authentic 64-step reggae chiptune theme in RAM:
     - Deep, syncopated walking dub bassline
     - Upbeat percussive "skank" chords on the off-beats (the signature reggae chop)
     - One-Drop drums (kick + rimshot landing together on beat 3)
     - Whimsical island froggy melody with pitch-bend vibrato
4. Clean Mode Separation (No Builder Tools in Level 1):
   - In "START GAME" (Adventure Mode), mouse tile highlight boxes, brush prompts,
     and accidental mouse painting are completely disabled for immersion.
   - In "CREATE LEVEL" (Builder Mode), all live mouse painting brushes and export
     shortcuts are fully active in the Sandbox Room.

CONTROLS (Keyboard / SNES Controller):
- D-Pad (8-Way Aim & Move) : Arrow Keys or W/A/S/D | Gamepad D-Pad / Left Stick
- A or B Button (Jump)     : SPACE, Z, or K        | Gamepad A / B
- Y Button (8-Way Tongue)  : X or J                | Gamepad X / Y
- R Button (Spore Weapon)  : C, U, or Left Shift   | Gamepad R1
- Menu Navigation          : UP / DOWN to select   | SPACE / A / ENTER to confirm
- Pause / Return to Menu   : ESCAPE
- Toggle HUD Telemetry     : TAB
- Warp to Boss Chamber     : B (in Adventure mode)
- Export Room ASCII        : P (in Builder mode)
===============================================================================
"""

import io
import math
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

# =============================================================================
# 1. GLOBAL ENGINE CONSTANTS & TUNING PARAMETERS
# =============================================================================

TILE_SIZE = 16

# Low-res retro canvas: 480x270 widescreen pixels (authentic 16:9 SNES resolution)
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 270

# Scaled display window: 1440x810
WINDOW_SCALE = 3
WINDOW_WIDTH = INTERNAL_WIDTH * WINDOW_SCALE
WINDOW_HEIGHT = INTERNAL_HEIGHT * WINDOW_SCALE

TARGET_FPS = 60

# --- Platformer Physics Tuning (Pixels per Frame at 60 FPS) ---
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

# --- Super Castlevania IV Tongue & Grapple Constants ---
TONGUE_EXTEND_SPEED = 14.0
TONGUE_RETRACT_SPEED = 15.0
TONGUE_MAX_LENGTH = 135.0
TONGUE_HOLD_FRAMES = 7
SWING_GRAVITY = 0.011
SWING_DAMPING = 0.992
SWING_PUMP_FORCE = 0.0022
SWING_REEL_SPEED = 1.5
SWING_MIN_LENGTH = 28.0

# --- Health & Combat Constants ---
# Why 5 hits? Froggy starts with 5 health hearts. Every time he touches an
# active enemy or hazard, he loses 1 Heart, gets knocked back, and receives
# 65 frames (~1.1 seconds) of blinking invulnerability frames ("i-frames").
PLAYER_MAX_HP = 5
PLAYER_INVULN_FRAMES = 65
ENEMY_STUN_FRAMES = 210
BOSS_MAX_HP = 6
BOSS_WEAK_EXPOSED_FRAMES = 210

# --- Metroidvania Screen Transitions ---
TRANSITION_FADE_SPEED = 18
DOOR_COOLDOWN_FRAMES = 24

# --- Color Palette (16-Bit SNES Inspired RGB Tuples) ---
COLOR_BG_GRID = (30, 36, 64)
COLOR_TONGUE_PINK = (242, 107, 148)
COLOR_TONGUE_TIP = (255, 168, 196)
COLOR_SPORE_CYAN = (80, 245, 210)
COLOR_HUD_TEXT = (230, 240, 255)
COLOR_DOOR_GLOW = (90, 225, 255)
COLOR_HEART_RED = (235, 65, 85)
COLOR_HEART_EMPTY = (65, 50, 75)
COLOR_BOSS_CORE = (255, 70, 210)
COLOR_BOSS_GOLD = (255, 215, 70)


# =============================================================================
# 2. PROCEDURAL CHIPTUNE AUDIO SYNTHESIZER (JAMAICAN REGGAE GROOVE)
# =============================================================================

class RetroAudioEngine:
    """
    Synthesizes 16-bit SNES sound effects and loopable background music in RAM.
    Features an authentic Jamaican Dub / Reggae chiptune groove with deep walking
    bass, offbeat skank chords, one-drop drums, and a cheerful froggy lead!
    """

    SAMPLE_RATE = 44100

    def __init__(self):
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.SAMPLE_RATE, -16, 2, 512)
            self.enabled = True
            # Channel 0 is reserved strictly for continuous looping background music
            self.music_channel = pygame.mixer.Channel(0)
            self.music_channel.set_volume(0.48)
            print("[Audio Engine] Synthesizing Jamaican Froggy groove & retro sound effects...")
            self.sfx = self._build_all_sfx()
            self.music_tracks = self._build_all_music()
            self.current_track_name = None
            print("[Audio Engine] Synthesis complete!")
        except Exception as err:
            print(f"[Audio Engine] Notice: Audio device unavailable ({err}). Running in silent mode.")

    @classmethod
    def _create_wav_sound(cls, samples):
        """Converts float samples [-1.0, 1.0] into a pygame.mixer.Sound."""
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

        # 1. Jump: Rising slide (160 Hz -> 480 Hz)
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

        # 10. Door Portal: Shimmering rising arpeggio (C-E-G-C)
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

        return sfx

    def _build_jamaican_track(self, bpm, pattern):
        """
        Synthesizes a multi-layered Jamaican Dub / Reggae chiptune loop.
        Fast numpy path when available, with pure-python fallback.
        """
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

                # 2. Reggae Skank Chords (Short, percussive offbeat pulse chops)
                if sk1 > 0:
                    p1 = (sk1 * t_step) % 1.0
                    p2 = (sk2 * t_step) % 1.0
                    sq1 = np.where(p1 < 0.35, 1.0, -1.0)
                    sq2 = np.where(p2 < 0.35, 1.0, -1.0)
                    env_sk = np.maximum(0.0, 1.0 - t_step * 16.0)
                    s += (sq1 + sq2) * 0.12 * env_sk

                # 3. Whimsical Island Froggy Lead (Pulse wave with vibrato)
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
            # Pure Python Fallback
            samples = []
            for b_freq, (sk1, sk2), l_freq, drum in pattern:
                n_step = int(sr * step_dur)
                for i in range(n_step):
                    t = i / sr
                    s = 0.0
                    if b_freq > 0:
                        p = (b_freq * t) % 1.0
                        tri = 4.0 * abs(p - 0.5) - 1.0
                        s += tri * 0.35 * max(0.0, 1.0 - t / step_dur)
                    if sk1 > 0:
                        p1 = (sk1 * t) % 1.0
                        sq1 = 1.0 if p1 < 0.35 else -1.0
                        s += sq1 * 0.12 * max(0.0, 1.0 - t * 16.0)
                    if l_freq > 0:
                        p = (l_freq * t) % 1.0
                        pulse = 1.0 if p < 0.25 else -1.0
                        s += pulse * 0.18 * max(0.0, 1.0 - t * 2.2)
                    if drum in ('k', 'd'):
                        s += math.sin(2.0 * math.pi * max(35.0, 130.0 - t * 650.0) * t) * 0.40 * max(0.0, 1.0 - t * 14.0)
                    if drum in ('s', 'd', 'f'):
                        s += (random.random() * 2.0 - 1.0) * 0.22 * max(0.0, 1.0 - t * 15.0)
                    if drum == 'h':
                        s += (random.random() * 2.0 - 1.0) * 0.06 * max(0.0, 1.0 - t * 38.0)
                    samples.append(s)
            return self._create_wav_sound(samples)

    def _build_all_music(self):
        # 64-step (4 bars) Jamaican Froggy Groove (G Major / Dub Reggae, 104 BPM)
        pattern_jamaica = [
            # BAR 1: G Major
            (0,     (0,0),         392.0, '.'),
            (98.0,  (0,0),         0,     'h'),
            (0,     (246.9,392.0), 329.6, 'h'), # Skank
            (98.0,  (0,0),         0,     'h'),
            (0,     (0,0),         293.7, 'h'),
            (146.8, (0,0),         0,     'h'),
            (0,     (246.9,392.0), 392.0, 'h'), # Skank
            (0,     (0,0),         0,     'h'),
            (98.0,  (0,0),         440.0, 'd'), # One-Drop (Kick + Snare on 3!)
            (0,     (0,0),         0,     'h'),
            (0,     (246.9,392.0), 392.0, 'h'), # Skank
            (123.5, (0,0),         0,     'h'),
            (146.8, (0,0),         329.6, 'h'),
            (0,     (0,0),         0,     'h'),
            (0,     (246.9,392.0), 293.7, 'h'), # Skank
            (164.8, (0,0),         0,     'f'),

            # BAR 2: C Major (Sweet Island Lift)
            (0,     (0,0),         261.6, '.'),
            (130.8, (0,0),         0,     'h'),
            (0,     (261.6,329.6), 329.6, 'h'), # Skank
            (130.8, (0,0),         0,     'h'),
            (0,     (0,0),         392.0, 'h'),
            (164.8, (0,0),         0,     'h'),
            (0,     (261.6,329.6), 523.2, 'h'), # Skank
            (0,     (0,0),         0,     'h'),
            (130.8, (0,0),         392.0, 'd'), # One-Drop
            (0,     (0,0),         0,     'h'),
            (0,     (261.6,329.6), 329.6, 'h'), # Skank
            (146.8, (0,0),         0,     'h'),
            (164.8, (0,0),         261.6, 'h'),
            (0,     (0,0),         0,     'h'),
            (0,     (261.6,329.6), 293.7, 'h'), # Skank
            (146.8, (0,0),         0,     'f'),

            # BAR 3: E Minor / D Major (Walking Dub Bass)
            (0,     (0,0),         329.6, '.'),
            (82.4,  (0,0),         0,     'h'),
            (0,     (196.0,329.6), 392.0, 'h'), # Skank
            (82.4,  (0,0),         0,     'h'),
            (0,     (0,0),         440.0, 'h'),
            (123.5, (0,0),         0,     'h'),
            (0,     (196.0,329.6), 493.8, 'h'), # Skank
            (0,     (0,0),         0,     'h'),
            (146.8, (0,0),         392.0, 'd'), # One-Drop
            (0,     (0,0),         0,     'h'),
            (0,     (220.0,369.9), 329.6, 'h'), # Skank
            (110.0, (0,0),         0,     'h'),
            (146.8, (0,0),         293.7, 'h'),
            (0,     (0,0),         0,     'h'),
            (0,     (220.0,369.9), 246.9, 'h'), # Skank
            (123.5, (0,0),         0,     'f'),

            # BAR 4: D7 Turnaround (Playful Froggy Crescendo)
            (0,     (0,0),         293.7, '.'),
            (146.8, (0,0),         0,     'h'),
            (0,     (220.0,293.7), 369.9, 'h'), # Skank
            (146.8, (0,0),         0,     'h'),
            (0,     (0,0),         440.0, 'h'),
            (110.0, (0,0),         0,     'h'),
            (0,     (220.0,293.7), 493.8, 'h'), # Skank
            (0,     (0,0),         0,     'h'),
            (146.8, (0,0),         587.3, 'd'), # One-Drop
            (0,     (0,0),         0,     'h'),
            (0,     (220.0,293.7), 493.8, 'h'), # Skank
            (164.8, (0,0),         0,     'h'),
            (146.8, (0,0),         440.0, 'h'),
            (130.8, (0,0),         0,     's'),
            (123.5, (220.0,293.7), 392.0, 's'),
            (110.0, (0,0),         369.9, 'f'),
        ]

        # Fast battle theme for Emperor Mantis (136 BPM)
        pattern_boss = [
            (82.4,  (164.8,246.9), 659.2, 'k'),
            (82.4,  (0,0),         0,     'h'),
            (82.4,  (164.8,246.9), 659.2, 's'),
            (82.4,  (0,0),         0,     'h'),
            (87.3,  (174.6,261.6), 698.4, 'k'),
            (87.3,  (0,0),         0,     'h'),
            (87.3,  (174.6,261.6), 698.4, 's'),
            (87.3,  (0,0),         0,     'h'),
            (98.0,  (196.0,293.7), 784.0, 'k'),
            (98.0,  (0,0),         0,     'h'),
            (98.0,  (196.0,293.7), 784.0, 's'),
            (98.0,  (0,0),         0,     'h'),
            (110.0, (220.0,329.6), 880.0, 'k'),
            (110.0, (0,0),         0,     'h'),
            (123.5, (246.9,369.9), 987.7, 's'),
            (123.5, (0,0),         1046.5,'f'),
        ]

        jamaican_music = self._build_jamaican_track(104, pattern_jamaica)
        boss_music = self._build_jamaican_track(136, pattern_boss)

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
# 3. PROCEDURAL PIXEL-ART SPRITE & TEXTURE GENERATOR
# =============================================================================

class SpriteSheetGenerator:
    PALETTE = {
        '.': None,
        'G': (76, 187, 73),
        'D': (43, 122, 48),
        'L': (168, 230, 110),
        'W': (255, 255, 255),
        'K': (20, 20, 30),
        'R': (220, 55, 65),
        'P': (242, 107, 148),
        'M': (255, 65, 200),
        'S': (72, 88, 118),
        'B': (46, 58, 82),
        'H': (108, 130, 168),
        'Y': (245, 200, 66),
        'O': (225, 125, 40),
        'C': (70, 215, 255),
        'V': (155, 85, 225),
    }

    @classmethod
    def make_surface_from_grid(cls, grid_lines):
        height = len(grid_lines)
        width = len(grid_lines[0])
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        for y, row in enumerate(grid_lines):
            for x, char in enumerate(row):
                color = cls.PALETTE.get(char)
                if color is not None:
                    surface.set_at((x, y), color)
        return surface

    @classmethod
    def build_tile_textures(cls):
        brick_grid = [
            "HHHHHHHHGGGGHHHH",
            "SSSSSSSDGGGGDSSS",
            "SSSSSSSSDGGDSSSS",
            "BBBBBBBBSBBSBBBB",
            "KKKKKKKKSKKSKKKK",
            "HHHSSSSSSSSHHHHH",
            "SSSSSSSSSSSSSSSS",
            "BBBBBBBBBBBBBBBB",
            "KKKKKKKKKKKKKKKK",
            "HHHHHHHSSSSHHHHH",
            "SSSSSSSSSSSSSSSS",
            "SSSSSSSSSSSSSSSS",
            "BBBBBBBBBBBBBBBB",
            "KKKKKKKKKKKKKKKK",
            "SSSSHHHHHHHHSSSS",
            "BBBBBBBBBBBBBBBB",
        ]
        grapple_grid = [
            "....OOOOOOOO....",
            "..OOYYYYYYYYOO..",
            ".OYYWWWWWWWWYYO.",
            ".OYWOOOOOOOOYYO.",
            "OYYO........OYYO",
            "OYWO...YY...OYYO",
            "OYWO..YYYY..OYYO",
            "OYWO..YYYY..OYYO",
            "OYWO...YY...OYYO",
            "OYYO........OYYO",
            ".OYWOOOOOOOOYYO.",
            ".OYYWWWWWWWWYYO.",
            "..OOYYYYYYYYOO..",
            "....OOOOOOOO....",
            "......OOOO......",
            "................",
        ]
        door_grid = [
            "KKKKCCCCCCCCKKKK",
            "KKCCWWWWWWWWCCKK",
            "KCWWCCCCCCCCWWCK",
            "KCWCCWWWWWWCCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCWCCCCCCWCWCK",
            "KCWCCWWWWWWCCWCK",
            "KCWWCCCCCCCCWWCK",
            "KKCCWWWWWWWWCCKK",
            "KKKKCCCCCCCCKKKK",
        ]
        return {
            '#': cls.make_surface_from_grid(brick_grid),
            'G': cls.make_surface_from_grid(grapple_grid),
            'DOOR': cls.make_surface_from_grid(door_grid),
        }

    @classmethod
    def build_froggy_animations(cls):
        idle_1 = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            ".RGGGGGGGGGGGG..",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "..DDGGGGGGGGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGG......GGG..",
            ".DDDD......DDDD.",
            "................",
        ]
        idle_2 = [
            "................",
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "..DDGGGGGGGGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGGG....GGGG..",
            ".DDDDD....DDDDD.",
            "................",
        ]
        run_1 = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "...DGLLLLLLGDD..",
            "...DGGGGGGGGD...",
            "....GGGGGGGG....",
            "..GGG......GGG..",
            ".GGG........GGG.",
            "DDDD.........DDD",
            "................",
            "................",
        ]
        run_2 = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "...DGGGGGGGGD...",
            "...GGGG..GGGG...",
            "...GGG....GGG...",
            "....DDDD..DDDD..",
            "................",
            "................",
            "................",
        ]
        jump_up = [
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGGGGGR.",
            "..GGGLLLLLLGGG..",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGG......GGG..",
            "..GG........GG..",
            ".DDD........DDD.",
            "................",
            "................",
            "................",
        ]
        wall_slide = [
            "................",
            ".....WW...WW....",
            "....WKKW.WKKW...",
            "....GGGGGGGGGG..",
            "...RRRRRRRRRRRR.",
            "...GGGGGGGGGGGGD",
            "....GGLLLLLLGGGD",
            "....GLLLLLLLLGGD",
            "....DGLLLLLLGDDD",
            ".....GGGGGGGGDD.",
            "....GGG....GGGD.",
            "...GGG......DDD.",
            "...DDD..........",
            "................",
            "................",
            "................",
        ]
        mouth_open = [
            "................",
            "....WW....WW....",
            "...WKKW..WKKW...",
            "...GGGGGGGGGG...",
            "..RRRRRRRRRRRR..",
            "RRGGGGGGGGPPPPPP",
            "..GGGGGGGPPPPPPP",
            "..GGGLLLLGGGG...",
            "..GGLLLLLLLLGG..",
            "..DDGLLLLLLGDD..",
            "..DDGGGGGGGGDD..",
            "...DGGGGGGGGD...",
            "...GGG....GGG...",
            "..GGG......GGG..",
            ".DDDD......DDDD.",
            "................",
        ]

        raw_frames = {
            "idle": [cls.make_surface_from_grid(idle_1), cls.make_surface_from_grid(idle_2)],
            "run": [
                cls.make_surface_from_grid(run_1),
                cls.make_surface_from_grid(idle_1),
                cls.make_surface_from_grid(run_2),
                cls.make_surface_from_grid(idle_1),
            ],
            "jump": [cls.make_surface_from_grid(jump_up)],
            "wall_slide": [cls.make_surface_from_grid(wall_slide)],
            "tongue": [cls.make_surface_from_grid(mouth_open)],
        }

        animations = {"right": {}, "left": {}}
        for state_name, surface_list in raw_frames.items():
            animations["right"][state_name] = surface_list
            animations["left"][state_name] = [
                pygame.transform.flip(surf, True, False) for surf in surface_list
            ]
        return animations

    @classmethod
    def build_enemy_animations(cls):
        beetle_1 = [
            "................",
            "....W......W....",
            "....W..WW..W....",
            "...RRRRRRRRRR...",
            "..RROOOOOOOORR..",
            ".RROOYYYYYYOORR.",
            ".RROOOOOOOOOORR.",
            "RROOOOOOOOOOWWRR",
            "RRRRRRRRRRRRWKWR",
            ".KKKKKKKKKKKKKK.",
            "..YYYYYYYYYYYY..",
            "..KK...KK...KK..",
            ".KK....KK....KK.",
            ".K.....K......K.",
            "................",
            "................",
        ]
        beetle_2 = [
            "................",
            "................",
            "....W......W....",
            "....W..WW..W....",
            "...RRRRRRRRRR...",
            "..RROOOOOOOORR..",
            ".RROOYYYYYYOORR.",
            ".RROOOOOOOOOORR.",
            "RROOOOOOOOOOWWRR",
            "RRRRRRRRRRRRWKWR",
            ".KKKKKKKKKKKKKK.",
            "..YYYYYYYYYYYY..",
            "...KK..KK..KK...",
            "...KK..KK..KK...",
            "....K...K...K...",
            "................",
        ]
        fly_1 = [
            "................",
            "..CCCC....CCCC..",
            ".CWWWWC..CWWWWC.",
            ".CWWWWCCCCWWWWC.",
            "..CCCCVVVVCCCC..",
            ".....VVVVVV.....",
            "....VVVVVVWR....",
            "....VVLLLLWR....",
            "....VVVVVVVV....",
            ".....VV..VV.....",
            "....KK....KK....",
            "................",
            "................",
            "................",
            "................",
            "................",
        ]
        fly_2 = [
            "................",
            "................",
            "................",
            ".....VVVVVV.....",
            "....VVVVVVWR....",
            "..CCCCLLLLWRCC..",
            ".CWWWWVVVVWWWWC.",
            ".CWWWWC..CWWWWC.",
            "..CCCC....CCCC..",
            ".....VV..VV.....",
            "....KK....KK....",
            "................",
            "................",
            "................",
            "................",
            "................",
        ]
        mantis_armored = [
            ".....YY..................YY.....",
            "......YY................YY......",
            "..CCC..YY....GGGGGG....YY..CCC..",
            ".CWWWC..YY..GLLLLLLG..YY..CWWWC.",
            ".CWWWWC..RRRRLLLLLLRRRR..CWWWWC.",
            ".CWWWWCCRRRRKLLLLLLKRRRRCCWWWWC.",
            "..CWWWWCCCGGGGLLLLGGGGCCCWWWWC..",
            "...CCCC..GGGGGGGGGGGGGG..CCCC...",
            ".........DDDDGGGGGGDDDD.........",
            "....YYYYDDDDYYYYYYYYDDDDYYYY....",
            "...YYLLLDDDYYYYYYYYYYDDDLLLYY...",
            "..YYLLLLLDDYYYOOOOYYYDDLLLLLYY..",
            ".YYLLLLLLLDDYYOOOOYYDDLLLLLLLYY.",
            ".YWLLLLLLLDDYYYYYYYYDDLLLLLLLWY.",
            "YWWLLLLLL...DDDDDDDD...LLLLLLWWY",
            "YWWLLLL.....GGGGGGGG.....LLLLWWY",
            "YWWLL......GGLLLLLLGG......LLWWY",
            ".YWW.......GGLLLLLLGG.......WWY.",
            "..YW.......DDDDDDDDDD.......WY..",
            "...........GGLLLLLLGG...........",
            "..........GGGLLLLLLGGG..........",
            ".........DDDDDDDDDDDDDD.........",
            "........GGGGGGGGGGGGGGGG........",
            ".......DDGGGGGGGGGGGGGGDD.......",
            "......DDD..DDDDDDDDDD..DDD......",
            ".....DDD......DDDD......DDD.....",
            "....DDD..................DDD....",
            "...YY......................YY...",
            "..YY........................YY..",
            "................................",
            "................................",
            "................................",
        ]
        mantis_exposed = [
            "................................",
            "......Y........YY........Y......",
            ".....Y...Y............Y...Y.....",
            "..........RRRR....RRRR..........",
            ".........RRRRGGGGGGGRRRR........",
            ".........RRGGLLLLLLGGRRR........",
            "...CCCC...GGGGGGGGGGGG...CCCC...",
            "..CWWWWCCCDDDDGGGGDDDDCCCWWWWC..",
            "..CWWWWC.DDDDMMPPMMDDDD.CWWWWC..",
            "...CCCC..DDDMMWWWWMMDDD..CCCC...",
            ".........DDMMPWWWWPMMDD.........",
            ".........DDMPWWWWWWPMDD.........",
            ".........DDMMPWWWWPMMDD.........",
            ".........DDDMMWWWWMMDDD.........",
            "....YYYY..DDDDMMPPMMDDDD..YYYY..",
            "...YYLLL...DDDDDDDDDD...LLLYY...",
            "..YYLLLL....GGGGGGGG....LLLLYY..",
            ".YYLLLL....GGLLLLLLGG....LLLLYY.",
            ".YWLLL.....GGLLLLLLGG.....LLLWY.",
            "..YWW......DDDDDDDDDD......WWY..",
            "...........GGLLLLLLGG...........",
            "..........GGGLLLLLLGGG..........",
            ".........DDDDDDDDDDDDDD.........",
            "........GGGGGGGGGGGGGGGG........",
            "......DDDDGGGGGGGGGGGGDDDD......",
            "....DDDD...DDDDDDDDDD...DDDD....",
            "..DDDD........DDDD........DDDD..",
            ".YY..........................YY.",
            "................................",
            "................................",
            "................................",
            "................................",
        ]

        b1_surf = cls.make_surface_from_grid(beetle_1)
        b2_surf = cls.make_surface_from_grid(beetle_2)
        b_stun = pygame.transform.flip(b1_surf, False, True)

        f1_surf = cls.make_surface_from_grid(fly_1)
        f2_surf = cls.make_surface_from_grid(fly_2)

        m_arm_r = cls.make_surface_from_grid(mantis_armored)
        m_arm_l = pygame.transform.flip(m_arm_r, True, False)
        m_exp_r = cls.make_surface_from_grid(mantis_exposed)
        m_exp_l = pygame.transform.flip(m_exp_r, True, False)

        return {
            "beetle": {
                "right": [b1_surf, b2_surf],
                "left": [pygame.transform.flip(b1_surf, True, False), pygame.transform.flip(b2_surf, True, False)],
                "stunned": [b_stun, pygame.transform.flip(b_stun, True, False)],
            },
            "fly": {
                "right": [f1_surf, f2_surf],
                "left": [pygame.transform.flip(f1_surf, True, False), pygame.transform.flip(f2_surf, True, False)],
            },
            "mantis": {
                "armored_right": m_arm_r,
                "armored_left": m_arm_l,
                "exposed_right": m_exp_r,
                "exposed_left": m_exp_l,
            },
        }


# =============================================================================
# 4. VISUAL ASCII WORLD BLUEPRINTS
# =============================================================================

WORLD_BLUEPRINTS = {
    # -------------------------------------------------------------------------
    # LEVEL 1: FROGGY'S FIRST HOP (100% Traversable Paced Tutorial Demo!)
    # -------------------------------------------------------------------------
    "level_1": {
        "title": "LEVEL 1: FROGGY'S FIRST HOP",
        "bg_color": (18, 28, 44),
        "map_coords": (0, 0),
        "doors": {
            "A": {
                "target_room": "entrance_hall",
                "target_door": "A_IN",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "################################################################################", # 0
            "#..............................................................................#", # 1
            "#..............................................................G...............#", # 2
            "#..............................................................................#", # 3
            "#...............................................#...#.######...................#", # 4 (Chimney + Roof)
            "#...............................................#...#..........................#", # 5
            "#...............................................#...#..........................#", # 6
            "#...............................................#...#..........................#", # 7
            "#.......................#####...................#...#...................######.#", # 8 (Double Jump Ledge)
            "#.............................##############....#...#..........................#", # 9 (Combat Platform)
            "#....................................E..........#...#..........................#", # 10 (Moss Beetle Patrol)
            "#...............................................#...#..........................#", # 11
            "#................####...........................#...#..........................#", # 12 (First Step)
            "#....S..............................................#..........................A", # 13 (Open Chimney Entry)
            "#..######...##......................................#..........................A", # 14 (Hop Obstacle)
            "#..............................................................................A", # 15 (Smooth Floor)
            "############################################################...#################", # 16 (Chasm Hazard Pit)
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 2: MOSSY ENTRANCE HALL (Connects West to Level 1, East to Chimney)
    # -------------------------------------------------------------------------
    "entrance_hall": {
        "title": "2. MOSSY ENTRANCE HALL",
        "bg_color": (20, 26, 46),
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
            "##################################################",
            "#................................................#",
            "#................................................#",
            "#.............G....................G.............#",
            "#.......................F........................#",
            "#.........................................########",
            "#.......................E........................#",
            "#....................########....................#",
            "#.......F................................F.......#",
            "#...........######..............######...........#",
            "#................................................#",
            "#.....................................E..........#",
            "A_IN.................................######......#",
            "A_IN##................E..........................A",
            "A_IN................######.......................A",
            "#..................................E.............A",
            "##################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 3: WALL-JUMP CHIMNEY TOWER
    # -------------------------------------------------------------------------
    "chimney_tower": {
        "title": "3. WALL-JUMP CHIMNEY TOWER",
        "bg_color": (28, 22, 48),
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
            "####################################",
            "#..................................#",
            "#.................G................#",
            "#..................................B",
            "#...........................E......B",
            "#......................#############",
            "#..............###.....#...........#",
            "#......F.......###.....#...........#",
            "#..............###.....#...........#",
            "#......G.......###.....#...........#",
            "#..............###.....#...........#",
            "#..............###.....#...........#",
            "#..............###.........F.......#",
            "#..............###............E....#",
            "#..............###.........######..#",
            "#......F.......###.................#",
            "#..............###.................#",
            "#..............###..........G......#",
            "#........E.....###.................#",
            "#.....######...###.................#",
            "#..............###.........E.......#",
            "A........................######....#",
            "A..........E.......................#",
            "A.......######.....................#",
            "####################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 4: GRAPPLE SWING CAVERN
    # -------------------------------------------------------------------------
    "grapple_cavern": {
        "title": "4. GRAPPLE SWING CAVERN",
        "bg_color": (16, 34, 44),
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
            "#...................G.............G.............G..........C",
            "#........................................................E.C",
            "#......................................................#####",
            "#..........E...............................................#",
            "#.......#####.............F.............F..................#",
            "#...................###.........###.........###......E.....#",
            "#...................###.........###.........###....#####...#",
            "#...................###.........###.........###............#",
            "#...................###.........###.........###............#",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 5: EMPEROR MANTIS BOSS SANCTUM ('M' spawns the 3-Phase Boss!)
    # -------------------------------------------------------------------------
    "boss_sanctum": {
        "title": "5. EMPEROR MANTIS SANCTUM",
        "bg_color": (38, 16, 32),
        "map_coords": (3, 1),
        "doors": {
            "C": {
                "target_room": "grapple_cavern",
                "target_door": "C",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "####################################",
            "#..................................#",
            "#.......G........G........G........#",
            "#..................................#",
            "#..................................#",
            "#........................M.........#",
            "#...#####..................#####...#",
            "#..................................#",
            "#............G........G............#",
            "#..................................#",
            "#..................................#",
            "#.......#####..........#####.......#",
            "#..................................#",
            "C..................................#",
            "C..................................#",
            "C..######..................######..#",
            "####################################",
        ],
    },

    # -------------------------------------------------------------------------
    # SANDBOX ROOM: CLEAN CANVAS FOR "CREATE LEVEL" MODE
    # -------------------------------------------------------------------------
    "sandbox_room": {
        "title": "BUILDER'S SANDBOX",
        "bg_color": (22, 24, 38),
        "map_coords": (0, 2),
        "doors": {
            "A": {
                "target_room": "level_1",
                "target_door": "A",
                "spawn_offset_x": 22,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "##################################################",
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
            "#....S...........................................A",
            "#..######..............######....................A",
            "#................................................A",
            "#................................................A",
            "##################################################",
        ],
    },
}


# =============================================================================
# 5. PARTICLES & PROJECTILES
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
        self.vy += 0.15

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        size = 3 if (self.lifetime - self.age) > 8 else 2
        pygame.draw.rect(surface, self.color, (sx, sy, size, size))


class SporeBoomerang:
    def __init__(self, x, y, dir_x, dir_y):
        self.x = float(x)
        self.y = float(y)
        self.vx = dir_x * 6.5
        self.vy = dir_y * 6.5
        self.return_ax = -dir_x * 0.14
        self.return_ay = -dir_y * 0.14
        self.age = 0
        self.max_age = 110
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
        if boss and boss.alive and boss.rect.colliderect(hit_box):
            if boss.hit_by_spore_boomerang(room):
                self.alive = False
                if audio:
                    audio.play_sfx("stun")

        if self.age >= self.max_age:
            self.alive = False

    def draw(self, surface, camera_x, camera_y):
        screen_x = int(self.x - camera_x)
        screen_y = int(self.y - camera_y)
        angle = self.age * 0.35
        for i in range(4):
            blade_angle = angle + i * (math.pi * 0.5)
            bx = screen_x + int(math.cos(blade_angle) * 6)
            by = screen_y + int(math.sin(blade_angle) * 6)
            pygame.draw.line(surface, COLOR_SPORE_CYAN, (screen_x, screen_y), (bx, by), 2)
        pygame.draw.circle(surface, (255, 255, 255), (screen_x, screen_y), 2)


class BossScytheWave:
    def __init__(self, x, y, vx, vy, enraged=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.enraged = enraged
        self.radius = 7
        self.age = 0
        self.max_age = 150
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

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        outer_col = (255, 90, 110) if self.enraged else (140, 255, 130)
        pygame.draw.circle(surface, outer_col, (sx, sy), self.radius, 2)
        pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 3)


# =============================================================================
# 6. ENEMY ENTITIES & 3-PHASE BOSS AI
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
    def __init__(self, x, y):
        super().__init__(x, y, width=12, height=12)
        self.state = "YANKED"
        self.can_yank_immediately = True

    def update(self, room):
        self.anim_timer += 1

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.center_x - camera_x)
        sy = int(self.center_y - camera_y)
        pygame.draw.circle(surface, COLOR_BOSS_CORE, (sx, sy), 6)
        pygame.draw.circle(surface, COLOR_BOSS_GOLD, (sx, sy), 4)
        pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 2)


class MossBeetle(BaseEnemy):
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

    def draw(self, surface, camera_x, camera_y):
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

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.rect.x - 1 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)
        facing_key = "right" if self.dir_x > 0 else "left"
        frames = self.anims[facing_key]
        sprite = frames[(self.anim_timer // 4) % len(frames)]
        surface.blit(sprite, (sx, sy))


class EmperorMantis(BaseEnemy):
    def __init__(self, spawn_x, spawn_y, enemy_anims):
        super().__init__(spawn_x, spawn_y, width=28, height=30)
        self.anims = enemy_anims["mantis"]
        self.is_boss = True
        self.max_hp = BOSS_MAX_HP
        self.hp = BOSS_MAX_HP
        self.home_x = float(spawn_x)
        self.home_y = float(spawn_y)
        self.flight_timer = 0.0
        self.attack_cooldown = 95

        self.state = "HOVER"
        self.state_timer = 0
        self.dive_vx = 0.0
        self.dive_vy = 0.0
        self.flash_timer = 0

    @property
    def phase(self):
        if self.hp >= 5:
            return 1
        elif self.hp >= 3:
            return 2
        return 3

    @property
    def weak_point_rect(self):
        return pygame.Rect(int(self.center_x - 10), int(self.center_y - 10), 20, 20)

    def hit_by_spore_boomerang(self, room):
        if self.state in ("HOVER", "DIVE_TELEGRAPH", "DIVE_ATTACK"):
            self.state = "WEAK_EXPOSED"
            self.stun_timer = BOSS_WEAK_EXPOSED_FRAMES
            self.vx = 0.0
            self.vy = 1.2
            self.flash_timer = 12
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_SPORE_CYAN, count=18)
            return True
        return False

    def yank_exposed_weak_point(self, room):
        self.hp -= 1
        self.flash_timer = 20
        pearl = BossEnergyPearl(self.center_x, self.center_y)
        room.enemies.append(pearl)
        room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=24)

        if self.hp <= 0:
            self.alive = False
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=45)
            room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_CORE, count=35)
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

        player = room.active_player_ref
        if player is not None:
            self.dir_x = 1 if player.center_x >= self.center_x else -1

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
            self.x += (self.home_x - self.x) * 0.07
            self.y += (self.home_y - self.y) * 0.07
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
                dive_speed = 6.2 if self.phase == 2 else 7.4
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
                room.spawn_particle_burst(self.center_x, self.center_y, COLOR_BOSS_GOLD, count=10)
                self.state = "RECOVERING"
                self.state_timer = 40
            return

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
        wave_speed = 3.6 if self.phase < 3 else 4.4
        angles = [base_angle] if self.phase < 3 else [base_angle - 0.28, base_angle, base_angle + 0.28]
        for ang in angles:
            vx = math.cos(ang) * wave_speed
            vy = math.sin(ang) * wave_speed
            room.boss_projectiles.append(
                BossScytheWave(self.center_x, self.center_y, vx, vy, enraged=(self.phase == 3))
            )

    def draw(self, surface, camera_x, camera_y):
        sx = int(self.rect.x - 2 - camera_x)
        sy = int(self.rect.y - 1 - camera_y)

        if self.state == "WEAK_EXPOSED":
            key = "exposed_right" if self.dir_x > 0 else "exposed_left"
        else:
            key = "armored_right" if self.dir_x > 0 else "armored_left"
        sprite = self.anims[key]

        if self.phase == 3 or self.state == "DIVE_TELEGRAPH":
            aura_col = (255, 60, 90) if (self.anim_timer // 3) % 2 == 0 else COLOR_BOSS_GOLD
            pygame.draw.circle(
                surface, aura_col,
                (int(self.center_x - camera_x), int(self.center_y - camera_y)), 20, 1
            )

        surface.blit(sprite, (sx, sy))

        if self.state == "WEAK_EXPOSED":
            core_x = int(self.center_x - camera_x)
            core_y = int(self.center_y - 2 - camera_y)
            pulse_r = 5 + int(math.sin(self.anim_timer * 0.35) * 2)
            pygame.draw.circle(surface, COLOR_BOSS_CORE, (core_x, core_y), pulse_r, 1)

            for i in range(3):
                ang = self.anim_timer * 0.16 + i * (math.tau / 3.0)
                star_x = core_x + int(math.cos(ang) * 12)
                star_y = int(self.rect.top - 5 - camera_y + math.sin(ang) * 3)
                pygame.draw.circle(surface, COLOR_BOSS_GOLD, (star_x, star_y), 2)


# =============================================================================
# 7. ASCII TILEMAP ROOM PARSER & LIVE LEVEL BUILDER
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
    def __init__(self, room_id, blueprint, tile_textures, enemy_anims):
        self.room_id = room_id
        self.title = blueprint["title"]
        self.bg_color = blueprint["bg_color"]
        self.map_coords = blueprint["map_coords"]
        self.door_configs = blueprint.get("doors", {})
        self.tile_textures = tile_textures
        self.enemy_anims = enemy_anims

        raw_lines = blueprint["ascii_grid"]
        self.rows = len(raw_lines)
        self.cols = max(len(line) for line in raw_lines)
        self.grid = [list(line.ljust(self.cols, '.')) for line in raw_lines]

        self.world_width = self.cols * TILE_SIZE
        self.world_height = self.rows * TILE_SIZE

        self.solid_tiles = []
        self.visual_bricks = []
        self.grapple_nodes = []
        self.door_tiles = []
        self.doors = {}
        self.enemy_spawns = []
        self.enemies = []
        self.boss_projectiles = []
        self.particles = []
        self.default_spawn = (64, 64)
        self.active_player_ref = None
        self.boss_defeated_banner_timer = 0

        self.rebuild_geometry(respawn_enemies=True)

    def rebuild_geometry(self, respawn_enemies=True):
        self.solid_tiles.clear()
        self.visual_bricks.clear()
        self.grapple_nodes.clear()
        self.door_tiles.clear()
        self.doors.clear()
        self.enemy_spawns.clear()

        door_bounds = {}

        for row in range(self.rows):
            col = 0
            while col < self.cols:
                char = self.grid[row][col]
                world_x = col * TILE_SIZE
                world_y = row * TILE_SIZE

                if char == '#':
                    start_col = col
                    while col < self.cols and self.grid[row][col] == '#':
                        self.visual_bricks.append((col * TILE_SIZE, world_y))
                        col += 1
                    merged_width = (col - start_col) * TILE_SIZE
                    self.solid_tiles.append(
                        pygame.Rect(start_col * TILE_SIZE, world_y, merged_width, TILE_SIZE)
                    )
                    continue

                elif char == 'G':
                    self.grapple_nodes.append(pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE))

                elif char == 'S':
                    self.default_spawn = (world_x, world_y)

                elif char in ('E', 'F', 'M'):
                    self.enemy_spawns.append((char, world_x, world_y))

                matched_door = None
                for d_id in self.door_configs:
                    if self.grid[row][col] == d_id[0]:
                        matched_door = d_id
                        break

                if matched_door:
                    tile_rect = pygame.Rect(world_x, world_y, TILE_SIZE, TILE_SIZE)
                    self.door_tiles.append((world_x, world_y))
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

        if respawn_enemies:
            self.spawn_enemies()

    def spawn_enemies(self):
        self.enemies.clear()
        self.boss_projectiles.clear()
        self.particles.clear()
        for char, wx, wy in self.enemy_spawns:
            if char == 'E':
                self.enemies.append(MossBeetle(wx, wy, self.enemy_anims))
            elif char == 'F':
                self.enemies.append(BuzzFly(wx, wy, self.enemy_anims))
            elif char == 'M':
                self.enemies.append(EmperorMantis(wx, wy, self.enemy_anims))

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

    def update_entities(self, player, audio=None):
        self.active_player_ref = player
        had_boss = self.get_active_boss() is not None

        for enemy in self.enemies:
            if enemy.alive:
                enemy.update(self)
        self.enemies = [e for e in self.enemies if e.alive]

        if had_boss and self.get_active_boss() is None:
            self.boss_defeated_banner_timer = 240
            if audio:
                audio.play_sfx("select")

        if self.boss_defeated_banner_timer > 0:
            self.boss_defeated_banner_timer -= 1

        for wave in self.boss_projectiles:
            wave.update(self)
        self.boss_projectiles = [w for w in self.boss_projectiles if w.alive]

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.age < p.lifetime]

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
        print("Copy and paste this list into WORLD_BLUEPRINTS in froggy_engine.py:")
        print("=" * 68)
        print('"ascii_grid": [')
        for row_chars in self.grid:
            line_str = "".join(row_chars)
            print(f'    "{line_str}",')
        print("],")
        print("=" * 68 + "\n")

    def get_grapple_node_at(self, x, y):
        for node in self.grapple_nodes:
            if node.inflate(8, 8).collidepoint(x, y):
                return node
        return None

    def get_enemy_at_point(self, x, y):
        for enemy in self.enemies:
            if enemy.alive and enemy.rect.inflate(8, 8).collidepoint(x, y):
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
        grid_size = 32
        parallax_x = int(camera_x * 0.5) % grid_size
        parallax_y = int(camera_y * 0.5) % grid_size
        for x in range(-parallax_x, INTERNAL_WIDTH, grid_size):
            pygame.draw.line(surface, COLOR_BG_GRID, (x, 0), (x, INTERNAL_HEIGHT))
        for y in range(-parallax_y, INTERNAL_HEIGHT, grid_size):
            pygame.draw.line(surface, COLOR_BG_GRID, (0, y), (INTERNAL_WIDTH, y))

        brick_tex = self.tile_textures['#']
        for bx, by in self.visual_bricks:
            sx = int(bx - camera_x)
            sy = int(by - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                surface.blit(brick_tex, (sx, sy))

        grapple_tex = self.tile_textures['G']
        for node in self.grapple_nodes:
            sx = int(node.x - camera_x)
            sy = int(node.y - camera_y)
            if -TILE_SIZE <= sx <= INTERNAL_WIDTH and -TILE_SIZE <= sy <= INTERNAL_HEIGHT:
                surface.blit(grapple_tex, (sx, sy))

        door_tex = self.tile_textures['DOOR']
        for dx, dy in self.door_tiles:
            sx = int(dx - camera_x)
            sy = int(dy - camera_y)
            surface.blit(door_tex, (sx, sy))

        glow_radius = int(2 + math.sin(pulse_timer * 0.12) * 2)
        for door in self.doors.values():
            screen_door = door.rect.move(-int(camera_x), -int(camera_y))
            pygame.draw.rect(surface, COLOR_DOOR_GLOW, screen_door.inflate(glow_radius, glow_radius), 1)

        for enemy in self.enemies:
            if enemy.alive:
                enemy.draw(surface, camera_x, camera_y)

        for wave in self.boss_projectiles:
            wave.draw(surface, camera_x, camera_y)

        for p in self.particles:
            p.draw(surface, camera_x, camera_y)


# =============================================================================
# 8. METROIDVANIA WORLD MANAGER
# =============================================================================

class WorldManager:
    def __init__(self, blueprints, tile_textures, enemy_anims, starting_room_id):
        self.rooms = {}
        for room_id, bp in blueprints.items():
            self.rooms[room_id] = TileMapRoom(room_id, bp, tile_textures, enemy_anims)
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
                audio.play_music("boss")
            else:
                audio.play_music("level")

    def draw_fade_overlay(self, surface):
        if self.fade_alpha > 0:
            self.fade_surface.set_alpha(self.fade_alpha)
            surface.blit(self.fade_surface, (0, 0))


# =============================================================================
# 9. SNES CONTROLLER ABSTRACTION LAYER
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
# 10. FROGGY PLAYER ENTITY
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
            if boss and boss.alive and boss.rect.inflate(8, 8).collidepoint(tip_x, tip_y):
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
        if self.invuln_timer > 0:
            return

        for enemy in room.enemies:
            if enemy.alive and enemy.state == "PATROL" and self.rect.colliderect(enemy.rect):
                self._take_damage(push_from_x=enemy.center_x, room=room, audio=audio)
                return

        boss = room.get_active_boss()
        if boss and boss.alive and boss.state != "WEAK_EXPOSED" and self.rect.colliderect(boss.rect):
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

    def draw(self, surface, camera_x, camera_y):
        for proj in self.projectiles:
            proj.draw(surface, camera_x, camera_y)

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
        draw_x = int(self.rect.x - 1 - camera_x)
        draw_y = int(self.rect.y - 1 - camera_y)
        surface.blit(sprite, (draw_x, draw_y))


# =============================================================================
# 11. SMOOTH HYSTERESIS CAMERA & HUD
# =============================================================================

class SmoothCamera:
    """
    Smooth platformer camera with dual-axis Hysteresis (Deadzone Window).
    Eliminates camera whiplash when turning around and vertical bounce when hopping!
    """
    def __init__(self, world_width, world_height):
        self.x = 0.0
        self.y = 0.0
        self.set_bounds(world_width, world_height)
        # Dimensions of the inner deadzone window
        self.deadzone_w = 54.0
        self.deadzone_h = 36.0

    def set_bounds(self, world_width, world_height):
        self.world_width = world_width
        self.world_height = world_height

    def snap_to(self, player):
        """Snaps directly to player without damping (used on room change/warp)."""
        self.x = player.center_x - (INTERNAL_WIDTH * 0.5)
        self.y = player.center_y - (INTERNAL_HEIGHT * 0.55)
        self._clamp()

    def update(self, player):
        # Center of the current camera view
        center_x = self.x + (INTERNAL_WIDTH * 0.5)
        center_y = self.y + (INTERNAL_HEIGHT * 0.55)

        # 1. Horizontal Hysteresis (Deadzone)
        dx = player.center_x - center_x
        half_w = self.deadzone_w * 0.5
        if dx > half_w:
            target_x = self.x + (dx - half_w)
        elif dx < -half_w:
            target_x = self.x + (dx + half_w)
        else:
            target_x = self.x

        # 2. Vertical Hysteresis (Prevents camera jitter on hops)
        dy = player.center_y - center_y
        half_h = self.deadzone_h * 0.5
        if dy > half_h:
            target_y = self.y + (dy - half_h)
        elif dy < -half_h:
            target_y = self.y + (dy + half_h)
        else:
            target_y = self.y

        # 3. Cushioned LERP Smoothing
        self.x += (target_x - self.x) * 0.08
        self.y += (target_y - self.y) * 0.08
        self._clamp()

    def _clamp(self):
        max_x = max(0.0, float(self.world_width - INTERNAL_WIDTH))
        max_y = max(0.0, float(self.world_height - INTERNAL_HEIGHT))
        self.x = max(0.0, min(max_x, self.x))
        self.y = max(0.0, min(max_y, self.y))


def draw_hud_and_minimap(surface, font, player, world_manager, camera, mouse_world_pos, controller, show_builder):
    # Only draw mouse builder cursor & prompts if in BUILDER mode!
    if show_builder:
        mx_world, my_world = mouse_world_pos
        col = int(mx_world // TILE_SIZE)
        row = int(my_world // TILE_SIZE)
        cursor_sx = int(col * TILE_SIZE - camera.x)
        cursor_sy = int(row * TILE_SIZE - camera.y)
        pygame.draw.rect(surface, (255, 230, 90), (cursor_sx, cursor_sy, TILE_SIZE, TILE_SIZE), 1)

        help_img = font.render(
            "BUILDER: [Click] '#' | [G+Click] Ring | [E+Click] Beetle | [F+Click] Fly | [R-Click] Erase | [P] Export",
            True, (190, 215, 255)
        )
        surface.blit(help_img, (8, 18))

    # 5-Heart SNES Health Bar
    for i in range(PLAYER_MAX_HP):
        hx = 8 + i * 13
        hy = 6
        color = COLOR_HEART_RED if i < player.hp else COLOR_HEART_EMPTY
        pygame.draw.rect(surface, color, (hx, hy, 10, 8), border_radius=2)
        pygame.draw.rect(surface, (255, 255, 255), (hx, hy, 10, 8), 1, border_radius=2)

    score_img = font.render(
        f"EATEN: {player.eaten_count} | {world_manager.current_room.title}",
        True, COLOR_HUD_TEXT
    )
    surface.blit(score_img, (78, 5))

    # Super Metroid Style Automap
    map_origin_x = INTERNAL_WIDTH - 110
    map_origin_y = 6
    cell_w, cell_h = 22, 12

    for room_id, room in world_manager.rooms.items():
        gx, gy = room.map_coords
        cell_rect = pygame.Rect(
            map_origin_x + gx * (cell_w + 3),
            map_origin_y + gy * (cell_h + 3),
            cell_w, cell_h
        )

        if room is world_manager.current_room:
            pygame.draw.rect(surface, (45, 165, 220), cell_rect)
            pygame.draw.rect(surface, (255, 255, 255), cell_rect, 1)

            px_ratio = player.center_x / max(1, room.world_width)
            py_ratio = player.center_y / max(1, room.world_height)
            dot_x = cell_rect.x + int(px_ratio * (cell_w - 4)) + 2
            dot_y = cell_rect.y + int(py_ratio * (cell_h - 4)) + 2
            pygame.draw.circle(surface, (255, 230, 80), (dot_x, dot_y), 2)
        elif room_id in world_manager.visited_rooms:
            fill_col = (110, 35, 60) if room_id == "boss_sanctum" else (45, 65, 110)
            pygame.draw.rect(surface, fill_col, cell_rect)
            pygame.draw.rect(surface, (120, 150, 200), cell_rect, 1)
        else:
            pygame.draw.rect(surface, (35, 42, 65), cell_rect, 1)

    # 8-Way Aim Compass
    _, (ux, uy) = controller.get_dpad_vector(player.facing_right)
    compass_center = (map_origin_x - 16, 12)
    pygame.draw.circle(surface, (45, 55, 85), compass_center, 10)
    pygame.draw.circle(surface, (120, 150, 200), compass_center, 10, 1)
    aim_end = (int(compass_center[0] + ux * 8), int(compass_center[1] + uy * 8))
    pygame.draw.line(surface, COLOR_TONGUE_PINK, compass_center, aim_end, 2)
    pygame.draw.circle(surface, COLOR_BOSS_GOLD, aim_end, 2)

    # Dedicated Boss Health Bar
    active_boss = world_manager.current_room.get_active_boss()
    if active_boss is not None and active_boss.alive:
        bar_w = 200
        bar_h = 10
        bar_x = (INTERNAL_WIDTH - bar_w) // 2
        bar_y = INTERNAL_HEIGHT - 18

        pygame.draw.rect(surface, (20, 15, 30), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=3)
        pygame.draw.rect(surface, (255, 215, 70), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), 1, border_radius=3)

        hp_ratio = active_boss.hp / active_boss.max_hp
        fill_w = int(bar_w * hp_ratio)
        bar_col = (255, 60, 90) if active_boss.phase == 3 else ((255, 140, 50) if active_boss.phase == 2 else (80, 220, 120))
        if fill_w > 0:
            pygame.draw.rect(surface, bar_col, (bar_x, bar_y, fill_w, bar_h), border_radius=2)

        boss_label = font.render(
            f"EMPEROR MANTIS  [PHASE {active_boss.phase}]",
            True, COLOR_HUD_TEXT
        )
        surface.blit(boss_label, (bar_x + 30, bar_y - 12))

    if world_manager.current_room.boss_defeated_banner_timer > 0:
        banner_surf = font.render("VICTORY! EMPEROR MANTIS DEFEATED!", True, COLOR_BOSS_GOLD)
        bx = (INTERNAL_WIDTH - banner_surf.get_width()) // 2
        by = (INTERNAL_HEIGHT // 2) - 20
        pygame.draw.rect(surface, (20, 20, 40), (bx - 8, by - 4, banner_surf.get_width() + 16, 20), border_radius=4)
        pygame.draw.rect(surface, COLOR_BOSS_GOLD, (bx - 8, by - 4, banner_surf.get_width() + 16, 20), 1, border_radius=4)
        surface.blit(banner_surf, (bx, by))


# =============================================================================
# 12. TITLE SCREEN, PAUSE OVERLAY & GAME OVER RENDERERS
# =============================================================================

def draw_title_screen(surface, title_font, menu_font, selected_index, anim_timer, frog_idle_surf):
    surface.fill((16, 20, 36))

    for x in range(0, INTERNAL_WIDTH, 24):
        pygame.draw.line(surface, (25, 32, 54), (x, 0), (x, INTERNAL_HEIGHT))
    for y in range(0, INTERNAL_HEIGHT, 24):
        pygame.draw.line(surface, (25, 32, 54), (0, y), (INTERNAL_WIDTH, y))

    title_text = "F R O G G Y"
    shadow_img = title_font.render(title_text, True, (15, 18, 30))
    title_img = title_font.render(title_text, True, (80, 235, 120))
    tx = (INTERNAL_WIDTH - title_img.get_width()) // 2
    ty = 46
    surface.blit(shadow_img, (tx + 2, ty + 2))
    surface.blit(title_img, (tx, ty))

    sub_text = "16-BIT METROIDVANIA TECH DEMO"
    sub_img = menu_font.render(sub_text, True, (245, 200, 66))
    sx = (INTERNAL_WIDTH - sub_img.get_width()) // 2
    surface.blit(sub_img, (sx, ty + 30))

    frog_bounce_y = int(math.sin(anim_timer * 0.08) * 4)
    surface.blit(frog_idle_surf, ((INTERNAL_WIDTH // 2) - 8, 102 + frog_bounce_y))

    menu_items = ["START GAME", "CREATE LEVEL"]
    menu_start_y = 142

    for i, item in enumerate(menu_items):
        is_selected = (i == selected_index)
        col = (255, 255, 255) if is_selected else (130, 145, 175)
        item_img = menu_font.render(item, True, col)
        ix = (INTERNAL_WIDTH - item_img.get_width()) // 2
        iy = menu_start_y + i * 22

        if is_selected:
            cursor_col = (255, 215, 70) if (anim_timer // 6) % 2 == 0 else (242, 107, 148)
            arrow_img = menu_font.render(">", True, cursor_col)
            surface.blit(arrow_img, (ix - 16, iy))
            surface.blit(arrow_img, (ix + item_img.get_width() + 8, iy))

            pill_rect = pygame.Rect(ix - 6, iy - 2, item_img.get_width() + 12, item_img.get_height() + 4)
            pygame.draw.rect(surface, (45, 60, 95), pill_rect, border_radius=3)
            pygame.draw.rect(surface, cursor_col, pill_rect, 1, border_radius=3)

        surface.blit(item_img, (ix, iy))

    hint_text = "[UP / DOWN] Select   [SPACE / A / ENTER] Confirm"
    hint_img = menu_font.render(hint_text, True, (160, 185, 220))
    hx = (INTERNAL_WIDTH - hint_img.get_width()) // 2
    surface.blit(hint_img, (hx, INTERNAL_HEIGHT - 28))


def draw_game_over_screen(surface, title_font, menu_font, anim_timer):
    dark_overlay = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    dark_overlay.fill((45, 10, 20))
    dark_overlay.set_alpha(205)
    surface.blit(dark_overlay, (0, 0))

    go_text = "GAME OVER"
    shadow_img = title_font.render(go_text, True, (10, 5, 10))
    go_img = title_font.render(go_text, True, (245, 65, 85))
    gx = (INTERNAL_WIDTH - go_img.get_width()) // 2
    gy = 75
    surface.blit(shadow_img, (gx + 2, gy + 2))
    surface.blit(go_img, (gx, gy))

    info_lines = [
        "FROGGY RAN OUT OF HEARTS!",
        "(Tip: Eat bugs with your Tongue to restore +1 Heart!)",
        "",
        "[SPACE / A / B]  RESPAWN AT ENTRANCE",
        "[ESCAPE]         RETURN TO TITLE",
    ]

    for i, line in enumerate(info_lines):
        col = (255, 230, 90) if "RESPAWN" in line else ((200, 210, 230) if i < 2 else (170, 185, 215))
        img = menu_font.render(line, True, col)
        lx = (INTERNAL_WIDTH - img.get_width()) // 2
        surface.blit(img, (lx, 120 + i * 16))


def draw_pause_screen(surface, title_font, menu_font, selected_index, anim_timer):
    dark_overlay = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    dark_overlay.fill((10, 15, 25))
    dark_overlay.set_alpha(190)
    surface.blit(dark_overlay, (0, 0))

    pause_img = title_font.render("PAUSED", True, (245, 200, 66))
    px = (INTERNAL_WIDTH - pause_img.get_width()) // 2
    surface.blit(pause_img, (px, 70))

    options = ["RESUME", "RETURN TO TITLE", "QUIT GAME"]
    for i, opt in enumerate(options):
        is_sel = (i == selected_index)
        col = (255, 255, 255) if is_sel else (130, 145, 175)
        img = menu_font.render(opt, True, col)
        ox = (INTERNAL_WIDTH - img.get_width()) // 2
        oy = 125 + i * 22

        if is_sel:
            cursor_col = (80, 245, 210)
            pill_rect = pygame.Rect(ox - 8, oy - 2, img.get_width() + 16, img.get_height() + 4)
            pygame.draw.rect(surface, (35, 48, 75), pill_rect, border_radius=3)
            pygame.draw.rect(surface, cursor_col, pill_rect, 1, border_radius=3)

        surface.blit(img, (ox, oy))


# =============================================================================
# 13. MAIN ENGINE LOOP & STATE MACHINE
# =============================================================================

def main():
    pygame.init()
    pygame.display.set_caption("FROGGY - 16-Bit Metroidvania (SNES Physics, 8-Way Tongue & Jamaican Groove)")

    window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    snes_canvas = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    clock = pygame.time.Clock()

    hud_font = pygame.font.SysFont("monospace", 9, bold=True)
    menu_font = pygame.font.SysFont("monospace", 10, bold=True)
    title_font = pygame.font.SysFont("impact", 26, bold=True)

    # Initialize Procedural Audio Engine
    audio = RetroAudioEngine()

    controller = SNESController()
    animations = SpriteSheetGenerator.build_froggy_animations()
    tile_textures = SpriteSheetGenerator.build_tile_textures()
    enemy_anims = SpriteSheetGenerator.build_enemy_animations()

    world = WorldManager(WORLD_BLUEPRINTS, tile_textures, enemy_anims, starting_room_id="level_1")
    spawn_x, spawn_y = world.current_room.default_spawn
    player = FroggyPlayer(spawn_x, spawn_y, animations)

    # Smooth Hysteresis Camera
    camera = SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    camera.snap_to(player)

    # Game State Machine: "TITLE", "PLAYING", "PAUSED", "GAME_OVER"
    game_state = "TITLE"
    # Mode: "ADVENTURE" (no builder tools on Level 1!) or "BUILDER" (Sandbox)
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
                            # START GAME -> Clean Adventure Mode in Level 1 (Builder tools hidden!)
                            game_mode = "ADVENTURE"
                            world.warp_directly_to_room("level_1", player, camera, audio)
                            player.hp = PLAYER_MAX_HP
                            game_state = "PLAYING"
                            audio.play_music("level")
                        elif title_selected_index == 1:
                            # CREATE LEVEL -> Sandbox Room with full Builder tools enabled!
                            game_mode = "BUILDER"
                            world.warp_directly_to_room("sandbox_room", player, camera, audio)
                            player.hp = PLAYER_MAX_HP
                            game_state = "PLAYING"
                            audio.play_music("level")
                    elif event.key == pygame.K_ESCAPE:
                        running = False

            frog_preview = animations["right"]["idle"][0]
            draw_title_screen(snes_canvas, title_font, menu_font, title_selected_index, pulse_timer, frog_preview)

        # =====================================================================
        # STATE B: PLAYING (METROIDVANIA GAMEPLAY / LEVEL BUILDER)
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

            # Live Mouse Level Builder Coordinates (ONLY active in Builder mode!)
            mouse_win_x, mouse_win_y = pygame.mouse.get_pos()
            canvas_mx = mouse_win_x / WINDOW_SCALE
            canvas_my = mouse_win_y / WINDOW_SCALE
            world_mx = canvas_mx + camera.x
            world_my = canvas_my + camera.y

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

            # Update Simulation
            controller.update()

            if world.is_transitioning:
                world.update_transition(player, camera, audio)
            else:
                world.current_room.update_entities(player, audio)
                player.update(controller, world.current_room, world, audio)
                camera.update(player)

                if player.hp <= 0:
                    player.hp = 0
                    game_state = "GAME_OVER"
                    audio.play_sfx("game_over")
                    audio.stop_music()

            # Render Active Room & Entities
            snes_canvas.fill(world.current_room.bg_color)
            world.current_room.draw(snes_canvas, camera.x, camera.y, pulse_timer)
            player.draw(snes_canvas, camera.x, camera.y)

            if show_hud:
                draw_hud_and_minimap(
                    snes_canvas, hud_font, player, world, camera,
                    (world_mx, world_my), controller,
                    show_builder=is_builder_active
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

        # Upscale 480x270 retro canvas to desktop window
        pygame.transform.scale(snes_canvas, (WINDOW_WIDTH, WINDOW_HEIGHT), window)
        pygame.display.flip()
        clock.tick(TARGET_FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
