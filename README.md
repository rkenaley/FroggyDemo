# FROGGY: 16-Bit Metroidvania Tech Demo Engine 🐸

A complete, self-contained 2D platformer engine built in Python with `pygame-ce`. Inspired by *Super Castlevania IV*, *Super Metroid*, and *Yoshi's Island*.

---

## 🎮 How to Run

In PowerShell:
```powershell
cd c:\AGProj\FroggyDemo
py -3.12 froggy_engine.py
```

---

## 🕹️ Controls (Keyboard & SNES Controller)

| Action | Keyboard Mapping | Gamepad (SNES / XInput) |
| :--- | :--- | :--- |
| **8-Way Aim & Move** | Arrow Keys or `W`/`A`/`S`/`D` | D-Pad / Left Analog Stick |
| **Jump (Ground / Wall / Double)** | `SPACE`, `Z`, or `K` | Face Buttons (`A` or `B`) |
| **8-Directional Tongue Whip** | `X` or `J` | Face Button (`Y` or `X`) |
| **Spore Boomerang Sub-Weapon** | `C`, `U`, or `Left Shift` | Right Shoulder (`R1`) |
| **Menu Navigation (Title / Pause)** | `UP` / `DOWN` (Select), `SPACE` / `ENTER` (Confirm) | D-Pad + `A` Button |
| **Pause / Return to Title** | `ESCAPE` | — |
| **Toggle Telemetry HUD** | `TAB` | — |
| **Instant Warp to Boss Chamber** | `B` (in Adventure mode) | — |
| **Export Edited ASCII Map** | `P` (in Builder mode) | — |

---

## 🌴 What's New in This Build

### 1. Buttery-Smooth Hysteresis Camera (Zero Whiplash & Zero Sticking)
- **Deadzone Window**: Replaced the twitchy instant look-ahead with a dual-axis comfort window.
  - Small adjustments, turning around in place, and normal platforming hops do **NOT** jerk or bounce the camera.
  - When Froggy pushes against the forward edge of the window, the viewport glides forward with smooth exponential damping (LERP).
  - Perfectly clamped to room boundaries so it never shows out-of-bounds void.

### 2. Level 1 Tutorial Redesign ("FROGGY'S FIRST HOP")
- Fixed the obstacle on Screen 2: the old wall has been replaced by a **48px-wide vertical chimney shaft**.
- Pacing & flow:
  1. **Hop & Run**: Low stone obstacle on flat ground.
  2. **Double Jump**: 3-tile and 4-tile high ledges to practice mid-air boost.
  3. **Combat & Eating**: Platform with an isolated Moss Beetle to practice throwing `R` (Spore Boomerang) to stun and `Y` (Tongue) to eat and heal +1 Heart.
  4. **Chimney Wall Jump**: Slide down and kick back and forth between two walls to reach the high rooftop.
  5. **Grapple Swing Chasm**: Overhead Gold Grapple Ring (`G`) to practice 8-way pendulum swings over a pit.
  6. **Exit Door**: Glowing Door `A` linking to the rest of the Metroidvania castle!

### 3. Jamaican / Dub Chiptune Audio Synthesizer
- A full 64-step loop (~9.3 seconds of structured music) synthesizing:
  - **Walking Dub Bassline**: Warm, syncopated bass with sub-bass depth.
  - **Offbeat Skank Chords**: The signature percussive reggae "chop" on the offbeats.
  - **One-Drop Drums**: Low kick + resonant rimshot landing together on beat 3.
  - **Island Froggy Melody**: Cheerful, whimsical lead with subtle pitch-bend vibrato.
- High-speed vector synthesis runs in **under 0.3s** on launch with NumPy (and has a pure-Python fallback).

### 4. Clean Mode Separation (No Builder Tools in Level 1)
- **"START GAME" (Adventure Mode)**:
  - Level 1 and all castle rooms are pristine, immersive platformer stages.
  - Mouse builder highlight squares and painting prompts are completely hidden.
  - Mouse clicks do not accidentally alter the level while playing.
- **"CREATE LEVEL" (Builder Mode)**:
  - Opens the dedicated **Sandbox Room**.
  - All mouse painting brushes (`#`, `G`, `E`, `F`, `M`), tile eraser, cursor snap grid, and `P` export shortcuts are active.
