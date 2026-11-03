# FROGGY: 16-Bit Metroidvania Tech Demo Engine 🐸

A complete, self-contained 2D platformer engine built in Python with `pygame-ce`. Inspired by *Super Castlevania IV*, *Super Metroid*, and *Yoshi's Island*.

---

## 🎮 How to Run

1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd c:\AGProj\FroggyDemo
   ```
2. Run the game:
   ```powershell
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
| **Instant Warp to Boss Chamber** | `B` | — |
| **Export Edited ASCII Map** | `P` | — |

---

## 💡 Quick Explainer: Why Did You Die After 5 Hits?

1. **The 5-Heart Health Bar (`PLAYER_MAX_HP = 5`)**:
   - Froggy starts with 5 health hearts (displayed in the top-left HUD).
   - Colliding with any active enemy (like the Spiked Moss Beetle) or an enemy attack deals **1 Heart of damage**.
   - Froggy is knocked backward and granted **65 frames (~1.1 seconds)** of blinking invulnerability ("i-frames") so you don't take multiple hits instantly.
2. **How to Heal**:
   - Hitting a Buzzfly (`F`) with the tongue or stunning a Moss Beetle (`E`) and then striking it with the tongue yanks it straight into Froggy's mouth.
   - **Swallowing any bug restores +1 Heart** and immediately refreshes your mid-air Double Jump!
3. **New Death & Respawn Screen**:
   - When all 5 Hearts are depleted, a retro **GAME OVER** screen appears.
   - Press **`SPACE` / `A` / `B`** to instantly respawn at the room entrance with full 5-heart health, or press **`ESC`** to return to the Title Screen.

---

## 🌟 What's New in This Build

### 1. Title Screen & State Machine
- Authentic retro title screen with animated Froggy, pulsing cursor, and two main options:
  - **`START GAME`**: Launches the curated Level 1 tutorial demo.
  - **`CREATE LEVEL`**: Opens a clean sandbox chamber with all level-builder brushes ready.
- In-game Pause menu (`ESCAPE`) to resume, return to title, or quit.

### 2. Level 1 Tutorial Demo ("FROGGY'S FIRST HOP")
A dedicated learning course designed for your nephew:
- **Zone 1 (Run & Hop)**: Flat mossy floor with a 1-tile hop over a stone block.
- **Zone 2 (Double Jump)**: A 3-tile high ledge requiring a mid-air double jump.
- **Zone 3 (Combat & Eating)**: A platform with an isolated Moss Beetle to practice throwing `R` (Spore Boomerang) to stun and `Y` (Tongue) to yank, eat, and heal.
- **Zone 4 (Wall Jumps)**: A vertical chimney to practice sliding down walls and kicking off them.
- **Zone 5 (Grapple Swing)**: An overhead Gold Grapple Ring (`G`) to practice 8-way pendulum swings over a gap.
- **Zone 6 (Exit Door)**: Glowing Door `A` that connects to the rest of the Metroidvania castle!

### 3. Procedural Chiptune Audio Synthesizer (Zero External Files!)
Generated in under 0.5s at startup directly in RAM using Python's built-in `wave` and `math` modules:
- **14 Sound Effects**: Rising jumps, double jump chirps, wall jump pings, whip snaps, metallic grapple clinks, boomerang whirs, funny boing stuns, eating/health chimes, damage thuds, and menu blips.
- **3 Multi-Track Music Themes**:
  - **Title Fanfare**: Bouncy, heroic 16-bit intro theme.
  - **Damp Caverns**: Atmospheric, rhythmic exploration theme with driving bassline and chiptune drums.
  - **Boss Overdrive**: Fast, intense battle music for Emperor Mantis!
