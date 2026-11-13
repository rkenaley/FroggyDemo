# Tools & Modular Architecture Guide

*Super Froggy* cleanly separates level data, visual tools, asset inspectors, and topology checks from the main game engine so you can build, edit, and verify content rapidly.

---

## 1. Modular World Data (`world_data.py` & `levels/*.json`)

`world_data.py` centralizes all **23 Metroidvania & Skyfrog zones** across Map Grids 1 & 2 (backed by JSON files in `levels/`) and exports:
* `WORLD_BLUEPRINTS`: Dictionary of all 23 loaded rooms (19 Grid-1 adventure/boss/treasury rooms, 3 Grid-2 Skyfrog Tree/Nimbus zones, plus `sandbox_room`).
* `TILE_LEGEND`: Canonical registry of **53 active ASCII characters** (terrain, hazards, currents, Cracked Burrow Rocks `'r'`, grapple/totems, relics, enemies, all 5 bosses, NPCs, letter doors, and numeric portals `'0'..'9'`).
* Helper APIs: `reload_blueprints()`, `list_zones()`, `get_zone()`, `create_blank_zone()`, `save_zone()`, and `validate_zone_blueprint()`.

---

## 2. Froggy Level Studio (`level_studio.py`)

A full interactive 2D tilemap editor and instant playtest runner.

### CLI Commands
```powershell
py level_studio.py                               # Launch GUI (defaults to level_1)
py level_studio.py --zone frost_springs          # Open GUI directly in a specific zone
py level_studio.py --list                        # Print summary table of all 23 zones
py level_studio.py --info entrance_hall          # Inspect zone metadata, doors & counts
py level_studio.py --play frost_springs          # Playtest a zone directly (no main menu)
py level_studio.py --new my_cavern --theme cavern --cols 60 --rows 23
py level_studio.py --export toad_colosseum       # Print Python ASCII block for a zone
py level_studio.py --reset level_1               # Restore zone JSON to built-in default
```

*Supported `--theme` values (all 10 biome themes):* `canopy`, `temple`, `cavern`, `sanctum`, `hound_palace`, `ice`, `volcanic`, `underwater`, `tree_ascent`, `sky_clouds`.

### GUI Features & Controls
* **Full Scrollable Brush Palette**: Covers all active terrain tiles (`#`, `.`, `r`, `~`, `<`, `>`, `v`, `c`, `o`), mechanics (`G`, `S`, `X`, `T`), power-ups/relics (`J`, `R`, `L`, `V`), enemies (`E`, `F`, `N`, `W`, `b`, `w`, `p`, `a`, `j`), all 5 bosses (`M`, `H`, `Q`, `O`, `s`), NPCs (`e`, `k`), and doors (`A`, `B`, `C`, `D`, `I`, `K`, `P`, `U`, `Y`, `Z`, plus portal IDs `1`, `2`). Scroll vertically with the mouse wheel when hovering the sidebar.
* **Scrollable Zone Picker (`[ZONES]`)**: Scroll with mouse wheel, `Up`/`Down`, `PageUp`/`PageDown`, `Home`/`End` across all 20+ zones cleanly inside the modal.
* **Live Autotiling & Biome Previews**: Renders 4-bit autotiled walls and themed backdrops across all 8 zone themes.
* **Instant Playtest (`F5` or `[PLAY]`)**: Saves your zone, launches a live `640x360` -> `1280x720` playtest (supporting room transitions, Shopkeeper, `[Tab / I]` Inventory, and `[R / Space]` respawn on `hp <= 0`), and returns cleanly to the Studio window when closed.
* **Shortcuts**:
  * `Left Click / Drag`: Paint active brush
  * `Right Click / Drag`: Erase (`'.'`)
  * `Middle Click / Drag` or `W A S D` / `Arrows`: Pan camera
  * `Mouse Wheel` (on canvas): Cursor-centered zoom
  * `1 / 2 / G / S / E / F / M / H`: Quick-select Solid, Air, Grapple, Spawn, Beetle, Buzzfly, Mantis Boss, or Dread Hound Boss
  * `Ctrl + Z` / `Ctrl + Y`: Undo / Redo (40-step history)
  * `Ctrl + S`: Save JSON to `levels/<zone_id>.json`
  * `F1` or `?` (`/`) : Toggle Help modal (kept separate from `H` Dread Hound brush)

---

## 3. Sprite & Animation Inspector (`sprite_inspector.py`)

A 32-bit RGBA sprite, tile, and prop inspector with frame scrubbing, bounding-box telemetry, and live cursor RGBA probing.

### CLI Commands
```powershell
py sprite_inspector.py                    # Launch Inspector GUI
py sprite_inspector.py --list             # Print table of 48 sequences / 132 frames
py sprite_inspector.py --dump             # Output full JSON manifest with bboxes
py sprite_inspector.py --sprite run       # Jump directly to Froggy's Sprint Cycle
py sprite_inspector.py --sprite shark     # Inspect Demon Shark Boss frames
py sprite_inspector.py --category bosses  # Open Bosses category
```

### Coverage & Features
* **Complete Asset Catalog (48 sequences / 132 frames)**:
  * **Player (`player`)**: `idle` (3f), `idle_blink` (`froggy_idle_3.png`), `run` (4f), `jump` (2f), `fall` (2f), `wall_slide` (2f), `tongue` (2f), `swim` (4f), `swing` (2f), `hurt` (1f) — all 23 Froggy player frames.
  * **Troop Enemies (`enemies`)**: `beetle`, `fly`, `ant`, `spider`, `stink_bug`, `ice_spider`, `piranha`, `angler`, `jelly` (21 frames).
  * **Colossus Bosses (`bosses`)**: `mantis`, `hound`, `toad`, `falo`, `shark` (24 frames).
  * **Friendly NPCs (`npcs`)**: `elder` (4f), `shopkeeper` (4f).
  * **Interactive Tiles (`tiles`)**: `grapple`, `water`, `lava`, `waterfall`, `bubble_vent`, `burrow_rock`, `door`, `boss_door`, `master_key_door`, `metroid_door`.
  * **Relics & Props (`props`)**: `boots`, `boomerang`, `muhlaser`, `vitality_heart`, `falo_heart`, `key_fragments`, `master_key`, `totem`, `mantis_totem`, `statue`, `flora`, `shrooms`.
* **Scrollable Explorer Sidebar**: Navigate long lists with mouse wheel over the sidebar or `Up`/`Down`/`PageUp`/`PageDown`/`Home`/`End`.
* **Orientation-Aware Telemetry**: Press `F` to flip horizontally (`flip_h`); both the stage render, green bounding box (`B`), and live cursor RGBA pixel probe read from the displayed (flipped) surface.
* **Shortcuts**: `Space` Play/Pause, `Left`/`Right` or `[`/`]` Step frames, `+`/`-` or Wheel Zoom, `B` Bounding Box, `A` Anchor `(width/2, height)`, `C` Center, `G` Pixel Grid, `F` Flip Horizontal.

---

## 4. World Map & Connectivity Tool (`map_tool.py`)

Audits door connections, tile distribution, and Metroidvania progression reachability across all 20 zones.

```powershell
py map_tool.py                # Full world summary + ASCII world graph
py map_tool.py map            # Print ASCII Metroidvania progression map
py map_tool.py doors          # Inspect every DoorPortal link across rooms
py map_tool.py reach          # BFS reachability audit from level_1
py map_tool.py room <id>      # Inspect grid dimensions, doors & entities for one zone
py map_tool.py sync           # Check consistency between levels/*.json and defaults
```

---

## 5. Procedural Generators & Verification Tests

* **Asset Pipeline**: `generate_assets.py`, `sprite_studio.py`, `generate_hound_and_powerup_assets.py`, `process_v7_assets.py`, `midi_writer.py`.
* **Verification Suite**:
  ```powershell
  py test_tools_and_modularity.py   # Verifies world_data, sprite_inspector & level_studio
  py test_v9_features.py
  py test_v10_systematic_fixes.py
  py test_v11_playtest.py           # End-to-end 20-zone traversal, combat, UI & save/load playtest
  ```
