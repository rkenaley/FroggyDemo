# FROGGY: 720p 16-Bit Metroidvania Tech Demo

A self-contained, nephew-friendly 2D platformer engine built in Python (`pygame-ce`, `Pillow`, and `NumPy`), inspired by *Super Castlevania IV*, *Super Metroid*, and *Donkey Kong Country*.

---

## Quick Start (PowerShell)

```powershell
cd C:\AGProj\FroggyDemo
py -3.12 -m pip install pygame-ce numpy Pillow
py -3.12 froggy_engine.py
```

*(Note: All `.png` sprites, auto-tiled mossy terrain blocks, foliage props, lighting maps, and 16-bit backgrounds live in `assets/`. If `assets/` is ever missing, running `froggy_engine.py` or `py -3.12 generate_assets.py` automatically regenerates them!)*

---

## Controls (SNES Gamepad & Keyboard)

| SNES Button | Keyboard Fallback | Action |
| :--- | :--- | :--- |
| **D-Pad** | `Arrow Keys` or `W`/`A`/`S`/`D` | Run Left/Right & Aim in all **8 Directions** |
| **A / B** | `SPACE`, `Z`, or `K` | **Jump**, **Double Jump**, and **Wall Jump** |
| **Y** | `X` or `J` | **8-Way Tongue Whip** (Grapple Swing, Stun & Swallow Bugs) |
| **R** | `C`, `U`, or `Left Shift` | **Spore Boomerang** (Stuns Armored Beetles & Cracks Boss Armor) |
| **START** | `ESCAPE` | Pause Menu / Return to Title Screen |
| **SELECT** | `TAB` | Toggle HUD & Automap Telemetry |
| **Debug Warp** | `B` | Warp directly to the **Emperor Mantis Sanctum** |

---

## Creator's Explainer: How Every System Works (Chapter by Chapter)

The engine is organized into **13 numbered chapters** inside [`froggy_engine.py`](file:///c:/AGProj/FroggyDemo/froggy_engine.py) and paired with the procedural asset builder [`generate_assets.py`](file:///c:/AGProj/FroggyDemo/generate_assets.py) so a single creator can understand and modify every mechanic:

### 1. Crisp 720p Resolution via Integer Scaling (Chapter 1)
* **How it works**: Drawing tiny `16x16` pixel-art tiles directly onto a `1280x720` monitor would make everything look microscopic. Instead, the engine draws each frame onto a `640x360` widescreen internal surface (`snes_canvas`) and scales it by an exact integer factor of `2x` (`WINDOW_SCALE = 2`) to fill the **`1280x720` (720p HD)** window. Every pixel becomes an exact `2x2` block with zero blur.

### 2. Procedural Audio & Dynamic Sinister Boss Music (Chapter 2: `RetroAudioEngine`)
* **Jamaican / Dub Reggae Level Groove (`_build_jamaican_track`)**: Synthesizes a 64-step island groove at 104 BPM using a triangle + sub-sine walking dub bassline, off-beat percussive "skank" chords, one-drop drums (kick + rimshot landing together on beat 3), and a vibrato pulse lead.
* **Sinister Emperor Mantis Boss Theme (`_build_sinister_boss_track`)**: Written in **D Harmonic Minor / Phrygian Dominant** at 140 BPM. Uses a menacing sawtooth + sub-octave bass ostinato, dissonant Gothic cathedral organ chords, driving double-kick industrial percussion, and a screeching chromatic lead.
* **Dynamic Transition**: As Froggy explores Level 1, the upbeat Jamaican groove plays. The moment he crosses into the Sanctum arena (`boss_trigger_x`) or enters `boss_sanctum`, the boss awakens with a roar (`boss_roar`), the screen rumbles, the backdrop shifts to the dark Sanctum, and the music dynamically switches to the sinister boss theme.

### 3. 4-Bit Neighbor Auto-Tiling (Chapter 3: `AssetManager` & `TileMapRoom`)
* **How a single `#` character becomes lush mossy terrain**:
  When building the room from `WORLD_BLUEPRINTS`, each `#` tile checks its 4 neighbors:
  * **North** (`row - 1`) = `+1`
  * **East** (`col + 1`) = `+2`
  * **South** (`row + 1`) = `+4`
  * **West** (`col - 1`) = `+8`
* This produces a bitmask from `0` to `15`. If North is empty (`bit 1 == 0`), the tile automatically picks a texture with overhanging jungle moss and grass (`terrain_0..15.png`). Near the boss, it switches to the obsidian-and-crimson `sanctum_0..15.png` tileset.

### 4. Lush Ambiance: Interactive Vines, Fireflies & Additive Lighting (Chapter 4)
* **`HangingVine`**: Multi-segment pendulum chains hanging from cave ceilings. When Froggy runs or jumps through a vine, his horizontal velocity (`player.vx`) pushes the vine's angular velocity so it sways and ripples.
* **`FireflySpore` & Radial Lighting (`BLEND_RGB_ADD`)**: Pre-computed radial glow maps (`assets/fx/light_*.png`) are blitted with `pygame.BLEND_RGB_ADD` around fireflies, glowing bioluminescent mushrooms, golden grapple idols, projectiles, and the boss's exposed core.

### 5. Separated-Axis AABB Physics & Castlevania IV Pendulum Swing (Chapter 11: `FroggyPlayer`)
* **Separated-Axis Collision**: Moves Froggy along X and resolves wall collisions first, then moves along Y and resolves floor/ceiling collisions. This prevents corner-snagging and makes wall-sliding deterministic.
* **8-Way Pendulum Grapple**: Latching onto a golden grapple idol (`G`) converts Froggy's linear velocity $(v_x, v_y)$ into angular velocity $\omega$ around the idol. Gravity pulls the pendulum ($\ddot{\theta} = -\frac{g}{L}\sin\theta$), D-Pad Left/Right pumps the swing, Up/Down reels the tongue in or out, and jumping converts angular speed back into a launch arc.

### 6. The 3-Phase Emperor Mantis Boss Puzzle (Chapter 7: `EmperorMantis`)
1. **Dodge**: The Mantis flies in a figure-8 pattern firing crescent scythe waves (and high-speed diagonal dives in Phases 2 & 3).
2. **Stun (`R` Button)**: Hit the Mantis with a **Spore Boomerang** to crack open his golden breastplate (`WEAK_EXPOSED`).
3. **Yank (`Y` Button)**: Aim your **Tongue** into his exposed magenta chest core to yank out an **Energy Pearl**, dealing 1 damage to the boss and restoring **+1 Heart** to Froggy!
