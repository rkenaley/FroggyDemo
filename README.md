# FROGGY: 16-Bit Metroidvania Tech Demo Engine 🐸

A complete, self-contained 2D platformer engine built in Python with `pygame-ce`. Inspired by *Super Castlevania IV*, *Super Metroid*, and *Yoshi's Island*.

Designed specifically for learning: every physics formula, state transition, procedural sprite generator, and collision step is written for maximum legibility with thorough comments.

---

## 🎮 How to Run

1. Open a terminal in the project directory:
   ```bash
   cd c:\AGProj\FroggyDemo
   ```
2. Install `pygame-ce` (if not already installed):
   ```bash
   py -3.12 -m pip install pygame-ce
   ```
3. Run the engine:
   ```bash
   py -3.12 froggy_engine.py
   ```

---

## 🕹️ Controls (Keyboard & SNES Controller)

| Action | Keyboard Mapping | Physical SNES / Gamepad |
| :--- | :--- | :--- |
| **8-Way Aim & Move** | Arrow Keys or `W`/`A`/`S`/`D` | D-Pad / Left Analog Stick |
| **Jump (Ground / Wall / Double)** | `SPACE`, `Z`, or `K` | Face Buttons (`A` or `B`) |
| **8-Directional Tongue Whip** | `X` or `J` | Face Button (`Y` or `X`) |
| **Spore Boomerang Sub-Weapon** | `C`, `U`, or `Left Shift` | Right Shoulder (`R1`) |
| **Toggle Telemetry HUD** | `TAB` | — |
| **Instant Warp to Boss Chamber** | `B` | — |
| **Export Edited ASCII Map** | `P` | — |
| **Exit Game** | `ESCAPE` | — |

---

## 🧱 Live In-Game Mouse Level Builder

You can modify the level in real time while playing! Click anywhere on the screen:

- **Left-Click**: Place a Solid Stone/Moss Brick (`#`)
- **Hold `G` + Left-Click**: Place a Gold Grapple Anchor Ring (`G`)
- **Hold `E` + Left-Click**: Place a Spiked Moss Beetle (`E`)
- **Hold `F` + Left-Click**: Place a Flying Neon Buzzfly (`F`)
- **Hold `M` + Left-Click**: Place Emperor Mantis Boss (`M`)
- **Right-Click**: Erase tile/enemy to empty air (`.`)
- **Press `P`**: Prints the modified ASCII character grid directly to the terminal so you can copy and paste your level permanently into `WORLD_BLUEPRINTS`!

---

## 🔬 Systems Breakdown for Your Nephew

### 1. Authentic 16-Bit Resolution & Pixel-Art Generation
- The entire game renders to an authentic low-resolution internal retro canvas (**480×270** pixels).
- The canvas is cleanly scaled up by `3x` to **1440×810** without blurring.
- All sprites and tiles are generated procedurally in RAM from ASCII text grids in `SpriteSheetGenerator`. No external PNG files or missing file paths!

### 2. Separated-Axis AABB Physics (No Corner Snagging)
Movement is evaluated in two distinct phases every frame:
1. **Horizontal Phase**: Move by $v_x$, check bounding box collisions against solid tiles, and detect left/right walls.
2. **Vertical Phase**: Move by $v_y$, check vertical collisions, and detect floor/ceiling contact.
Separating the axes guarantees that sliding down a wall or landing on a platform edge never glitches into horizontal walls.

### 3. "SNES Crisp" Controls: Coyote Time & Jump Buffering
- **Coyote Time (`COYOTE_TIME_FRAMES = 6`)**: When Froggy walks off a ledge into empty air, the engine gives 6 frames (~0.1 seconds) where a jump press will still trigger.
- **Jump Buffer (`JUMP_BUFFER_FRAMES = 6`)**: If the jump button is pressed right before touching the floor, the input is remembered and executed immediately upon landing.
- **Variable Jump Cutoff**: Releasing the jump button early cuts $v_y$ by $45\%$, allowing precise short hops.

### 4. *Super Castlevania IV* Pendulum Grapple
- When pressing `Y`, the tongue shoots in one of 8 directions using a normalized unit vector:
  $$\hat{d} = \frac{(dx, dy)}{\sqrt{dx^2 + dy^2}}$$
- When the tongue tip hits a gold grapple ring (`G`), linear velocity is projected onto the pendulum's tangent vector to calculate angular velocity $\omega$:
  $$\omega = \frac{v_{\text{tangent}}}{L}$$
- While swinging:
  - **Left / Right** on the D-Pad applies angular pump force.
  - **Up / Down** on the D-Pad reels the rope in or out.
  - Pressing **Jump** detaches and converts angular momentum back into a launch arc.

### 5. Stun, Yank, and Swallow Combat Loop
- **Moss Beetle (`E`)**: Features a downward cliff-feeler sensor. Hit with Spore Boomerang (`R`) or Tongue (`Y`) to flip it upside-down into a stunned state, then hit it again with the tongue to yank and swallow it.
- **Buzzfly (`F`)**: Flies in a harmonic sine wave. Hitting it immediately latches and yanks it into Froggy's mouth.
- **Swallowing Rewards**: Eating any bug restores **+1 Heart** and immediately **resets your mid-air Double Jump**!

### 6. Multi-Phase Boss: Emperor Mantis (`M`)
Located in Room 4 (*Emperor Mantis Sanctum*):
- **Phase 1 (6–5 HP)**: Lissajous figure-8 flight + aimed scythe waves.
- **Phase 2 (4–3 HP)**: 40% speed boost + high-speed dive-bombs + summons Buzzfly minions for mid-battle healing.
- **Phase 3 (2–1 HP)**: Enraged crimson aura + 3-way spread shots.
- **The Combat Puzzle**:
  1. Throw the Spore Boomerang (`R`) to short out its scythe armor and drop it into `WEAK_EXPOSED` state.
  2. Aim your 8-way tongue (`Y`) into the glowing magenta chest core to rip out an Energy Pearl and swallow it!
