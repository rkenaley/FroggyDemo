# Froggy Under the Hood: Explainer & World Roadmap

Welcome! This guide explains how *Super Froggy* works like a real 16-bit Super Nintendo game—from pixels and physics to sound waves and level maps—and lays out the complete 20-zone adventure.

---

## Part 1: How the Engine Works

### 1. Crisp 16-Bit Pixel Scaling (`640x360` -> `1280x720`)
Instead of drawing tiny sprites directly onto a giant HD window, the game renders every tile, particle, and frog onto a compact `640x360` pixel canvas (`INTERNAL_WIDTH x INTERNAL_HEIGHT`). At the end of each frame, that canvas scales cleanly 2x up to `1280x720` (`WINDOW_WIDTH x WINDOW_HEIGHT`), keeping every pixel edge sharp and authentically retro.

### 2. Smooth Platformer Physics
* **Fixed 60 FPS Loop**: Everything moves in predictable 1/60th-second steps so jumps never change height on faster or slower computers.
* **Coyote Time & Jump Buffering**: Froggy gives you a 6-frame grace window (`COYOTE_TIME_FRAMES = 6`) if you step slightly past a cliff edge before pressing Jump, and remembers a jump pressed 6 frames before touching down (`JUMP_BUFFER_FRAMES = 6`).
* **360-Degree Tongue & Pendulum Swing**: Pressing `[Y]` (`X` / `J`) fires Froggy's tongue up to `145 px` in the direction you hold. Hitting a Golden Grapple Idol (`'G'`) turns Froggy into a real swinging pendulum driven by angular gravity and damping (`SWING_GRAVITY`, `SWING_DAMPING`).

### 3. 4-Bit Autotiling
In every room blueprint, solid terrain is just the single character `'#'`. At load time, `TileMapRoom` checks each `'#'` tile's 4 cardinal neighbors (`North=1, East=2, South=4, West=8`) and sums them into a bitmask `0..15`. A block with open air above automatically picks a mossy grass/ice/volcanic cap, while buried blocks pick solid interior stone—zero manual tile painting needed!

### 4. 32-Bit RGBA Alpha Feathering & Bottom-Center Anchoring
Old 8-bit games had jagged borders or "Sprite Jitter" when idle and running images had different heights. *Super Froggy* avoids both:
* **Uniform 32x32 canvases** (and `80x80` / `96x96` boss canvases) with **Bottom-Center anchoring** `(width/2, height)` keep Froggy's boots locked to the floor across every animation.
* **Sub-pixel 32-bit RGBA alpha feathering** blends outer silhouettes smoothly against dark caves and glowing bioluminescent rooms.

### 5. Audio Synthesis & Multi-Track MIDI
Sound effects (`assets/sfx/`, 38 WAV files) are synthesized mathematically in RAM using sine, triangle, square, sawtooth, and noise waveforms layered through retro echo filters, paired with a 9-track MIDI soundtrack (`assets/music/*.mid` built by `midi_writer.py`).

---

## Part 2: Complete 20-Zone Adventure Roadmap

The world connects **20 JSON zones** (`levels/*.json`) across **8 distinct themes** (`canopy`, `temple`, `cavern`, `sanctum`, `hound_palace`, `ice`, `volcanic`, `underwater`):

### Act I: The Canopy, Temple & Emperor Mantis
1. **`level_1`** (*Lush Canopy to Mantis Sanctum*, `canopy`) — Starting jungle canopy; learn jumping, tongue-whipping, and grapple swinging.
2. **`entrance_hall`** (*Sunken Frog Temple Hall*, `temple`) — Home to **Stomping Boots** (`'J'`) and hub portals linking downward (`B`), upward (`U`), and toward submerged corridors (`Y`).
3. **`chimney_tower`** (*Vine Chimney Ascent*, `cavern`) — Vertical shaft testing wall slides, wall jumps, and grapple chaining.
4. **`grapple_cavern`** (*Bioluminescent Grapple Cavern*, `cavern`) — Glowing mushroom caverns hiding the **Vitality Heart Container** (`'V'`, +1 Max HP).
5. **`boss_sanctum`** (*Emperor Mantis Sanctum*, `sanctum`) — **Boss #1: Emperor Mantis** (6 HP). Rewards the **Red Boomerang** (`'R'`) and the **Mantis Master Key Fragment**.

### Act II: Sanctum Depths, The Dread Hound & Giga Toad
6. **`mantis_passage`** (*Ancient Mantis Passage*, `sanctum`) — Connecting sanctum corridor with checkpoint (`'X'`) leading onward.
7. **`hound_sanctum`** (*The Hound's Palace*, `hound_palace`) — **Boss #2: The Dread Hound** (8 HP). Drops the **Hound Master Key Fragment** and guards passage to its vault.
8. **`hound_treasury`** (*Vault of the Muhlaser*, `hound_palace`) — Houses **The Muhlaser** (`'L'`), unlocked behind the Dread Hound's lair (hold `[R]` 3 seconds to fire a wall-shattering beam!).
9. **`toad_colosseum`** (*Giga Toad's Brawler Colosseum*, `sanctum`) — **Boss #3: Giga Toad** (50 HP). Drops the **Toad Master Key Fragment** and holds the 4-slot **Master Key Door**.
10. **`victory_chamber`** (*Sacred Lilypad Sanctuary*, `canopy`) — Unlocks once all 4 Master Key Fragments from Bosses 1–4 are assembled!

### Act III: Glacial Peaks & Volcanic Depths
11. **`frost_ascent`** (*Frost Ascent to Glacial Summit*, `ice`) — Sub-zero cliffs where `body_temp` drops steadily.
12. **`frost_springs`** (*Steamy Glacial Hot Springs*, `ice`) — Safe haven with Checkpoint Totem (`'X'`) and warm steam recovery.
13. **`falo_arena`** (*Blizzard Peak - Falo's Lair*, `ice`) — **Boss #4: Falo the Snowman**. Rewards **Falo's Heart** (`[L]` Heat Guard) and the **Frost Shard Master Key Fragment**.
14. **`falo_shrine`** (*Falo's Glacial Shrine*, `ice`) — High-altitude ice passage linking toward volcanic chasms (`J`, `Z`).
15. **`volcanic_chasm`** (*Volcanic Magma Chasm*, `volcanic`) — Sweltering lava cavern featuring Waterfall Mist cooling (`'c'`), Elder NPC guidance (`'e'`), and multi-route doors.
16. **`volcanic_depths`** (*Volcanic Magma Depths*, `volcanic`) — Deep geothermal magma gauntlet beyond the chasm.

### Act IV: The Abyssal Ocean & Builder's Sandbox
17. **`sunken_grotto`** (*Sunken Submarine Grotto*, `underwater`) — Underwater grotto with **Elder Nautilus** (`'e'`), **Cracked Burrow Rocks** (`'r'`), oxygen vents (`'o'`), and current streams (`'<'`, `'>'`) — stock up with the Shopkeeper back in `entrance_hall` before diving in!
18. **`shark_sanctum`** (*Abyssal Trench - Demon Shark*, `underwater`) — **Boss #5: Demon Shark** (65 HP, Boss Rush Stage 5). Charge your **Muhlaser** (`[R]`) to break through and earn the **Abyssal Pearl** (infinite underwater breathing)!
19. **`shark_treasury`** (*Abyssal Pearl Sanctuary*, `underwater`) — Peaceful deep-sea sanctuary chamber unsealed beyond Demon Shark via portal `'1'`.
20. **`sandbox_room`** (*Builder's Sandbox*, `canopy`) — Open playground room (`py level_studio.py --zone sandbox_room`) for experimenting with tiles, enemies, and physics!

---

## Part 3: Try Building & Inspecting Yourself!

* **Design your own level**: Run `py level_studio.py`, pick `sandbox_room`, place Golden Grapple Idols (`'G'`) 3–6 tiles above hazards, press `Ctrl + S`, then press **`F5`** to playtest your edits immediately!
* **Inspect Froggy's pixels**: Run `py sprite_inspector.py --sprite run`, pause with `Space`, step frame-by-frame with `Left` / `Right`, flip horizontally with `F`, and hover the canvas to probe live RGBA pixel values!
* **Trace the world map**: Run `py map_tool.py reach` to verify how all 20 zones connect from `level_1`.
