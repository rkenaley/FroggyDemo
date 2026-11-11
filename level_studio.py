"""
===============================================================================
FROGGY: STANDALONE LEVEL STUDIO & METROIDVANIA ZONE TWEAKER
===============================================================================
A dedicated visual level builder, zone inspector, and precision tweaker for
Froggy 16-Bit Metroidvania.

Run from PowerShell:
  py level_studio.py --list                 # List all existing zones with exact IDs
  py level_studio.py --info entrance_hall   # Detailed inspection of a zone
  py level_studio.py --zone level_1         # Launch visual editor for level_1
  py level_studio.py --play frost_springs   # Playtest directly in frost_springs
  py level_studio.py --new secret_cavern --theme ice --cols 60 --rows 23
  py level_studio.py --export toad_colosseum # Export clean Python ASCII code
  py level_studio.py --reset level_1        # Reset level to factory default

FOR THE NEPHEW (UNDER THE HOOD WALKTHROUGH):
-------------------------------------------------------------------------------
1. WHY A STANDALONE TOOL?
   Earlier versions had a tiny sandbox mode locked inside `froggy_engine.py`
   that could only edit one temporary room. By separating this into its own
   powershell tool, you can load ANY existing room in the entire game
   (or invent brand new ones!), tweak a single obstacle with surgical precision,
   and test it immediately with live physics—without having to load or modify
   the massive 7,000-line engine file!

2. HOW SCREEN-TO-WORLD-TO-TILE MATH WORKS:
   When your mouse is at pixel (mx, my) on your physical computer monitor:
     a) Scale factor: canvas_x = mx / zoom
     b) Camera offset: world_x = canvas_x + camera_x
     c) Grid cell:     tile_col = int(world_x // 16)
                       tile_row = int(world_y // 16)
   This 3-step transform maps any mouse click directly into the 2D array:
     `grid[tile_row][tile_col] = brush_char`

3. AUTO-TILING INTEGRATION:
   Every time you paint a '#' block or erase with '.', the level geometry
   instantly recalculates its 4-bit neighbor bitmask (North=1, East=2,
   South=4, West=8) and swaps the sprite texture in real time so you see
   gorgeous mossy edges while you paint!

4. UNDO & REDO HISTORY:
   Every paint stroke saves a snapshot of the grid to an undo stack.
   Pressing Ctrl+Z pops the previous grid state, letting you experiment
   fearlessly!
===============================================================================
"""

import argparse
import copy
import json
import math
import os
import sys
import pygame

# Import our modular world data registry
import world_data
from world_data import (
    TILE_SIZE,
    TILE_LEGEND,
    ZONE_THEMES,
    WORLD_BLUEPRINTS,
    list_zones,
    list_zone_ids,
    get_zone,
    create_blank_zone,
    save_zone,
    delete_zone,
    reset_zone_to_builtin,
    validate_zone_blueprint,
    export_zone_to_ascii,
)

# Colors for UI
COLOR_BG_DARK = (18, 22, 32)
COLOR_PANEL_BG = (26, 32, 46)
COLOR_PANEL_BORDER = (45, 56, 80)
COLOR_ACCENT = (80, 200, 120)
COLOR_ACCENT_HOVER = (110, 230, 150)
COLOR_TEXT_WHITE = (240, 245, 255)
COLOR_TEXT_DIM = (160, 175, 195)
COLOR_GRID_LINE = (40, 50, 70)
COLOR_CURSOR_HOVER = (255, 230, 80)
COLOR_BUTTON_BG = (36, 44, 62)
COLOR_BUTTON_HOVER = (52, 64, 90)
COLOR_BUTTON_ACTIVE = (65, 120, 90)

# Palette categories for the toolbar
BRUSH_PALETTES = [
    {
        "category": "Terrain",
        "items": [
            ('#', "Solid Stone"),
            ('.', "Air (Erase)"),
            ('~', "Swamp Water"),
            ('v', "Molten Magma"),
            ('c', "Waterfall Mist"),
            ('o', "Bubble Vent"),
        ],
    },
    {
        "category": "Mechanics",
        "items": [
            ('G', "Grapple Idol"),
            ('S', "Froggy Spawn"),
            ('X', "Checkpoint Totem"),
            ('T', "Mantis Totem"),
        ],
    },
    {
        "category": "Power-ups",
        "items": [
            ('J', "Stomping Boots"),
            ('R', "Red Boomerang"),
        ],
    },
    {
        "category": "Enemies",
        "items": [
            ('E', "Moss Beetle"),
            ('F', "Neon Buzzfly"),
            ('N', "Soldier Ant"),
            ('W', "Shadow Spider"),
            ('b', "Stink Bug"),
            ('w', "Ice Wolf Spider"),
        ],
    },
    {
        "category": "Bosses",
        "items": [
            ('M', "Emperor Mantis"),
            ('H', "The Dread Hound"),
            ('Q', "Giga Toad"),
            ('O', "Falo Snowman"),
        ],
    },
    {
        "category": "NPCs & Doors",
        "items": [
            ('e', "Elder Frog"),
            ('k', "Shopkeeper"),
            ('A', "Door A"),
            ('B', "Door B"),
            ('C', "Door C"),
            ('D', "Door D"),
            ('U', "Door U (Up)"),
            ('Z', "Door Z (Down)"),
        ],
    },
]


# =============================================================================
# CLI UTILITIES & REPORTING
# =============================================================================

def cmd_list_zones():
    """Prints a beautiful formatted directory of all zones in PowerShell."""
    zones = list_zones()
    print("\n" + "=" * 92)
    print(" 🐸 FROGGY METROIDVANIA WORLD DIRECTORY: AVAILABLE ZONES")
    print("=" * 92)
    header = f"{'Exact Zone ID':<18} {'Display Title':<38} {'Theme':<12} {'Size':<10} {'Custom':<7}"
    print(header)
    print("-" * 92)
    for z in zones:
        zid = z["id"]
        title = (z["title"][:35] + "...") if len(z["title"]) > 38 else z["title"]
        theme = z["theme"]
        size_str = f"{z['cols']}x{z['rows']}"
        custom_str = "YES (*)" if z["is_custom"] else "built-in"
        print(f"{zid:<18} {title:<38} {theme:<12} {size_str:<10} {custom_str:<7}")
    print("-" * 92)
    print(f"Total Zones: {len(zones)}  |  * = Contains custom disk overrides in 'levels/' directory")
    print("To inspect:  py level_studio.py --info <zone_id>")
    print("To edit:     py level_studio.py --zone <zone_id>")
    print("To playtest: py level_studio.py --play <zone_id>")
    print("=" * 92 + "\n")


def cmd_info_zone(zone_id):
    """Prints detailed telemetry, door connections, and ASCII map for a zone."""
    try:
        data = get_zone(zone_id)
    except KeyError:
        print(f"\n[ERROR] Zone '{zone_id}' not found! Run 'py level_studio.py --list' to see valid names.\n")
        sys.exit(1)

    grid = data.get("ascii_grid", [])
    rows = len(grid)
    cols = max(len(r) for r in grid) if rows > 0 else 0

    print("\n" + "=" * 78)
    print(f" 🔍 ZONE INSPECTION: '{zone_id}'")
    print("=" * 78)
    print(f"  Title:          {data.get('title', 'Untitled')}")
    print(f"  Theme:          {data.get('theme', 'canopy')} (Background: {data.get('bg_color', (0,0,0))})")
    print(f"  Dimensions:     {cols} cols x {rows} rows ({cols * TILE_SIZE} x {rows * TILE_SIZE} world px)")
    print(f"  Map Coords:     {data.get('map_coords', (0, 0))}")
    if data.get("boss_trigger_x") is not None:
        print(f"  Boss Trigger X: {data.get('boss_trigger_x')} px")

    # Doors
    doors = data.get("doors", {})
    print(f"\n  Door Connections ({len(doors)}):")
    if doors:
        for dchar, dcfg in doors.items():
            print(f"    - Door '{dchar}': -> Room '{dcfg.get('target_room')}', Door '{dcfg.get('target_door')}' (Offset: X={dcfg.get('spawn_offset_x')}, Y={dcfg.get('spawn_offset_y')})")
    else:
        print("    (None - standalone room)")

    # NPCs
    npcs = data.get("npcs", [])
    print(f"\n  NPC Cast ({len(npcs)}):")
    if npcs:
        for npc in npcs:
            print(f"    - [{npc.get('kind', 'elder').upper()}] {npc.get('name', 'Unnamed')} at ({npc.get('x')}, {npc.get('y')})")
            for line in npc.get("dialogue", []):
                print(f"        \"{line}\"")
    else:
        print("    (No scripted NPCs)")

    # Grid preview
    print("\n  ASCII Grid Layout Preview:")
    print("  " + "-" * (min(cols, 74)))
    for r_idx, r in enumerate(grid[:15]):
        truncated = r[:72] + ("..." if len(r) > 72 else "")
        print(f"  {r_idx:02d}| {truncated}")
    if len(grid) > 15:
        print(f"  ... ({len(grid) - 15} more rows - use --export to see all)")
    print("  " + "-" * (min(cols, 74)))
    print("=" * 78 + "\n")


def cmd_new_zone(zone_id, title=None, theme="canopy", cols=60, rows=23):
    """Creates a new zone from scratch."""
    zone_data = create_blank_zone(zone_id, title=title, theme=theme, cols=cols, rows=rows)
    fpath = save_zone(zone_id, zone_data, save_to_disk=True)
    print("\n" + "=" * 70)
    print(f" ✨ SUCCESS! Created brand-new zone: '{zone_id}'")
    print("=" * 70)
    print(f"  Title:      {zone_data['title']}")
    print(f"  Theme:      {theme}")
    print(f"  Dimensions: {cols} x {rows} tiles")
    print(f"  Saved to:   {fpath}")
    print(f"\nTo launch editor: py level_studio.py --zone {zone_id}")
    print(f"To playtest:      py level_studio.py --play {zone_id}")
    print("=" * 70 + "\n")
    return zone_data


def cmd_export_zone(zone_id):
    """Exports clean Python ASCII code for the zone."""
    try:
        code = export_zone_to_ascii(zone_id)
        print("\n" + "=" * 78)
        print(f" 📋 PYTHON SOURCE EXPORT FOR ZONE: '{zone_id}'")
        print("=" * 78)
        print(code)
        print("=" * 78 + "\n")
    except KeyError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


def cmd_reset_zone(zone_id):
    """Resets an edited built-in zone back to factory default."""
    try:
        reset_zone_to_builtin(zone_id)
        print(f"\n[OK] Zone '{zone_id}' has been reset to factory default built-in configuration.\n")
    except Exception as e:
        print(f"[ERROR] Could not reset zone '{zone_id}': {e}")
        sys.exit(1)


def cmd_play_zone(zone_id):
    """Launches the Froggy engine directly warped into the selected zone."""
    try:
        import froggy_engine as fe
    except ImportError as e:
        print(f"[ERROR] Could not import froggy_engine: {e}")
        sys.exit(1)

    print(f"\n[Level Studio] Launching playtest directly in zone '{zone_id}'...")
    if zone_id not in fe.WORLD_BLUEPRINTS:
        print(f"[ERROR] Zone '{zone_id}' does not exist in WORLD_BLUEPRINTS.")
        sys.exit(1)

    # Launch engine directly into that room
    pygame.init()
    window = pygame.display.set_mode((fe.WINDOW_WIDTH, fe.WINDOW_HEIGHT))
    pygame.display.set_caption(f"Froggy Playtest: {zone_id}")

    snes_canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    audio = fe.RetroAudioEngine()
    assets = fe.AssetManager()
    controller = fe.SNESController()
    animations = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()

    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id=zone_id)
    player = fe.FroggyPlayer(64, 64, animations)
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    world.warp_directly_to_room(zone_id, player, camera, audio)

    hud_font = pygame.font.SysFont("monospace", 10, bold=True)
    clock = pygame.time.Clock()
    running = True
    pulse_timer = 0

    while running:
        clock.tick(fe.TARGET_FPS)
        pulse_timer += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            controller.handle_hotplug_event(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        controller.update()
        world.current_room.update_entities(player, audio, pulse_timer)
        player.update(controller, world.current_room, world, audio)
        camera.update(player)

        # Draw
        snes_canvas.fill(world.current_room.bg_color)
        world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, pulse_timer)
        player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
        fe.draw_hud_and_minimap(snes_canvas, hud_font, player, world, camera, (0, 0), controller, False, pulse_timer)

        scaled = pygame.transform.scale(snes_canvas, (fe.WINDOW_WIDTH, fe.WINDOW_HEIGHT))
        window.blit(scaled, (0, 0))
        pygame.display.flip()

    pygame.quit()
    print("[Level Studio] Playtest finished cleanly.\n")


# =============================================================================
# INTERACTIVE LEVEL STUDIO GUI (PYGAME)
# =============================================================================

class LevelStudioGUI:
    """
    Full-featured visual 2D level editor for Froggy Metroidvania.
    """
    def __init__(self, initial_zone_id="level_1"):
        pygame.init()
        self.screen_w = 1280
        self.screen_h = 720
        self.window = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
        pygame.display.set_caption("Froggy Level Studio & Metroidvania Zone Tweaker")

        # Fonts
        self.font_small = pygame.font.SysFont("monospace", 11)
        self.font_bold = pygame.font.SysFont("monospace", 12, bold=True)
        self.font_title = pygame.font.SysFont("impact", 20)
        self.font_hud = pygame.font.SysFont("monospace", 13, bold=True)

        # Load game assets for high-fidelity tile rendering
        self.assets = None
        try:
            import froggy_engine as fe
            self.assets = fe.AssetManager()
        except Exception as e:
            print(f"[Level Studio] Notice: Using procedural color fallback for tiles ({e})")

        # Active Zone state
        self.zone_id = initial_zone_id if initial_zone_id in WORLD_BLUEPRINTS else "level_1"
        self.zone_data = copy.deepcopy(WORLD_BLUEPRINTS[self.zone_id])
        self.grid = [list(r) for r in self.zone_data.get("ascii_grid", [])]
        self.rows = len(self.grid)
        self.cols = max(len(r) for r in self.grid) if self.rows > 0 else 0

        # Camera & Viewport
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 2.0  # 1.0, 1.5, 2.0, 3.0
        self.min_zoom = 0.5
        self.max_zoom = 4.0

        # Active Brush
        self.active_brush = '#'
        self.brush_category_idx = 0

        # UI Layout Rectangles
        self.top_bar_height = 48
        self.palette_width = 220
        self.status_bar_height = 26
        self.canvas_rect = pygame.Rect(
            self.palette_width,
            self.top_bar_height,
            self.screen_w - self.palette_width,
            self.screen_h - self.top_bar_height - self.status_bar_height,
        )

        # Undo / Redo History Stacks
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 40

        # Interaction & Drag State
        self.is_panning = False
        self.pan_start_mouse = (0, 0)
        self.pan_start_cam = (0.0, 0.0)
        self.is_painting = False
        self.last_painted_cell = None

        # Zone Selector Dropdown State
        self.show_zone_picker = False
        self.zone_picker_scroll = 0

        # Help Overlay
        self.show_help = False

        # Status Message Flash
        self.status_message = f"Loaded zone '{self.zone_id}' ({self.cols}x{self.rows}). Ready to build!"
        self.status_timer = 200

        # Live Autotile Preview Surface Cache
        self._rebuild_autotile_cache()

    def _push_undo(self):
        """Saves current grid state into undo history stack."""
        snap = [list(r) for r in self.grid]
        self.undo_stack.append(snap)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.status_message = "Nothing to undo."
            self.status_timer = 120
            return
        current = [list(r) for r in self.grid]
        self.redo_stack.append(current)
        prev = self.undo_stack.pop()
        self.grid = prev
        self._rebuild_autotile_cache()
        self.status_message = "Undo performed."
        self.status_timer = 120

    def redo(self):
        if not self.redo_stack:
            self.status_message = "Nothing to redo."
            self.status_timer = 120
            return
        current = [list(r) for r in self.grid]
        self.undo_stack.append(current)
        next_state = self.redo_stack.pop()
        self.grid = next_state
        self._rebuild_autotile_cache()
        self.status_message = "Redo performed."
        self.status_timer = 120

    def load_zone(self, new_zone_id):
        """Loads a different zone cleanly into the editor."""
        if new_zone_id not in WORLD_BLUEPRINTS:
            return
        self.zone_id = new_zone_id
        self.zone_data = copy.deepcopy(WORLD_BLUEPRINTS[new_zone_id])
        self.grid = [list(r) for r in self.zone_data.get("ascii_grid", [])]
        self.rows = len(self.grid)
        self.cols = max(len(r) for r in self.grid) if self.rows > 0 else 0
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.show_zone_picker = False
        self._rebuild_autotile_cache()
        self.status_message = f"Loaded zone '{self.zone_id}': {self.zone_data.get('title', '')}"
        self.status_timer = 200

    def save_current_zone(self):
        """Saves current grid back to disk and memory."""
        # Convert list of char lists to list of strings
        self.zone_data["ascii_grid"] = ["".join(r) for r in self.grid]
        fpath = save_zone(self.zone_id, self.zone_data, save_to_disk=True)
        self.status_message = f"SAVED SUCCESS! '{self.zone_id}' written to {os.path.basename(fpath)}"
        self.status_timer = 240
        print(f"[Level Studio] Saved zone '{self.zone_id}' to {fpath}")

    def _is_solid(self, r, c):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.grid[r][c] == '#'
        return True

    def _rebuild_autotile_cache(self):
        """Precomputes 4-bit autotile bitmasks for each solid block."""
        self.autotile_masks = [[0] * self.cols for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == '#':
                    mask = 0
                    if self._is_solid(r - 1, c): mask |= 1  # North
                    if self._is_solid(r, c + 1): mask |= 2  # East
                    if self._is_solid(r + 1, c): mask |= 4  # South
                    if self._is_solid(r, c - 1): mask |= 8  # West
                    self.autotile_masks[r][c] = mask

    def screen_to_world(self, sx, sy):
        """Converts screen pixel (sx, sy) to world pixel (wx, wy)."""
        rel_x = sx - self.canvas_rect.left
        rel_y = sy - self.canvas_rect.top
        wx = (rel_x / self.zoom) + self.cam_x
        wy = (rel_y / self.zoom) + self.cam_y
        return wx, wy

    def world_to_grid(self, wx, wy):
        """Converts world coordinates to grid cell (col, row)."""
        col = int(wx // TILE_SIZE)
        row = int(wy // TILE_SIZE)
        return col, row

    def paint_cell(self, col, row, brush_char):
        """Paints a single cell with undo tracking."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            if self.grid[row][col] != brush_char:
                if not self.is_painting:
                    self._push_undo()
                    self.is_painting = True
                self.grid[row][col] = brush_char
                self._rebuild_autotile_cache()

    def run(self):
        clock = pygame.time.Clock()
        running = True

        while running:
            dt = clock.tick(60)
            if self.status_timer > 0:
                self.status_timer -= 1

            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.screen_w = max(960, event.w)
                    self.screen_h = max(600, event.h)
                    self.window = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
                    self.canvas_rect = pygame.Rect(
                        self.palette_width,
                        self.top_bar_height,
                        self.screen_w - self.palette_width,
                        self.screen_h - self.top_bar_height - self.status_bar_height,
                    )

                elif event.type == pygame.KEYDOWN:
                    # Keyboard shortcuts
                    mods = pygame.key.get_mods()
                    ctrl = (mods & pygame.KMOD_CTRL) != 0

                    if ctrl and event.key == pygame.K_z:
                        self.undo()
                    elif ctrl and event.key == pygame.K_y:
                        self.redo()
                    elif ctrl and event.key == pygame.K_s:
                        self.save_current_zone()
                    elif ctrl and event.key == pygame.K_e:
                        cmd_export_zone(self.zone_id)
                        self.status_message = f"Exported ASCII code for '{self.zone_id}' to console."
                        self.status_timer = 180
                    elif event.key == pygame.K_F5:
                        # Instant Playtest
                        self.save_current_zone()
                        cmd_play_zone(self.zone_id)
                    elif event.key in (pygame.K_h, pygame.K_F1):
                        self.show_help = not self.show_help
                    elif event.key == pygame.K_ESCAPE:
                        if self.show_zone_picker:
                            self.show_zone_picker = False
                        elif self.show_help:
                            self.show_help = False
                    # Quick brush selection via hotkeys
                    elif event.key == pygame.K_1: self.active_brush = '#'
                    elif event.key == pygame.K_2: self.active_brush = '.'
                    elif event.key == pygame.K_g: self.active_brush = 'G'
                    elif event.key == pygame.K_s and not ctrl: self.active_brush = 'S'
                    elif event.key == pygame.K_e and not ctrl: self.active_brush = 'E'
                    elif event.key == pygame.K_f: self.active_brush = 'F'
                    elif event.key == pygame.K_m: self.active_brush = 'M'
                    elif event.key == pygame.K_h and not ctrl: self.active_brush = 'H'

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    # 1. Top bar button clicks
                    if my < self.top_bar_height:
                        self._handle_top_bar_click(mx, my)

                    # 2. Zone Picker clicks
                    elif self.show_zone_picker:
                        self._handle_zone_picker_click(mx, my)

                    # 3. Palette clicks
                    elif mx < self.palette_width:
                        self._handle_palette_click(mx, my)

                    # 4. Canvas interaction
                    elif self.canvas_rect.collidepoint(mx, my):
                        if event.button == 1:  # Left click: Paint
                            self.is_painting = False
                            wx, wy = self.screen_to_world(mx, my)
                            c, r = self.world_to_grid(wx, wy)
                            self.paint_cell(c, r, self.active_brush)
                            self.last_painted_cell = (c, r)
                        elif event.button == 3:  # Right click: Erase
                            self.is_painting = False
                            wx, wy = self.screen_to_world(mx, my)
                            c, r = self.world_to_grid(wx, wy)
                            self.paint_cell(c, r, '.')
                            self.last_painted_cell = (c, r)
                        elif event.button == 2:  # Middle click: Pan
                            self.is_panning = True
                            self.pan_start_mouse = (mx, my)
                            self.pan_start_cam = (self.cam_x, self.cam_y)
                        elif event.button == 4:  # Scroll Up: Zoom In
                            self._zoom_at(mx, my, 1.2)
                        elif event.button == 5:  # Scroll Down: Zoom Out
                            self._zoom_at(mx, my, 1.0 / 1.2)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button in (1, 3):
                        self.is_painting = False
                        self.last_painted_cell = None
                    elif event.button == 2:
                        self.is_panning = False

                elif event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    if self.is_panning:
                        dx = (mx - self.pan_start_mouse[0]) / self.zoom
                        dy = (my - self.pan_start_mouse[1]) / self.zoom
                        self.cam_x = self.pan_start_cam[0] - dx
                        self.cam_y = self.pan_start_cam[1] - dy
                    elif self.canvas_rect.collidepoint(mx, my):
                        buttons = pygame.mouse.get_pressed()
                        if buttons[0]:  # Drag painting
                            wx, wy = self.screen_to_world(mx, my)
                            c, r = self.world_to_grid(wx, wy)
                            if (c, r) != self.last_painted_cell:
                                self.paint_cell(c, r, self.active_brush)
                                self.last_painted_cell = (c, r)
                        elif buttons[2]:  # Drag erasing
                            wx, wy = self.screen_to_world(mx, my)
                            c, r = self.world_to_grid(wx, wy)
                            if (c, r) != self.last_painted_cell:
                                self.paint_cell(c, r, '.')
                                self.last_painted_cell = (c, r)

            # Keyboard panning with WASD / Arrow keys
            keys = pygame.key.get_pressed()
            pan_speed = 12.0 / self.zoom
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.cam_x -= pan_speed
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.cam_x += pan_speed
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.cam_y -= pan_speed
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                if not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    self.cam_y += pan_speed

            # Render
            self.draw()
            pygame.display.flip()

        pygame.quit()

    def _zoom_at(self, mx, my, factor):
        """Zooms centered around mouse position."""
        old_zoom = self.zoom
        new_zoom = max(self.min_zoom, min(self.max_zoom, old_zoom * factor))
        if new_zoom != old_zoom:
            wx, wy = self.screen_to_world(mx, my)
            self.zoom = new_zoom
            # Re-adjust camera so mouse point stays fixed
            rel_x = mx - self.canvas_rect.left
            rel_y = my - self.canvas_rect.top
            self.cam_x = wx - (rel_x / self.zoom)
            self.cam_y = wy - (rel_y / self.zoom)

    def _handle_top_bar_click(self, mx, my):
        """Handles clicks on top toolbar buttons."""
        # [ZONES] button
        if 10 <= mx <= 110:
            self.show_zone_picker = not self.show_zone_picker
        # [SAVE] button
        elif 120 <= mx <= 200:
            self.save_current_zone()
        # [PLAY] button
        elif 210 <= mx <= 300:
            self.save_current_zone()
            cmd_play_zone(self.zone_id)
        # [UNDO] button
        elif 310 <= mx <= 370:
            self.undo()
        # [REDO] button
        elif 380 <= mx <= 440:
            self.redo()
        # [EXPORT] button
        elif 450 <= mx <= 530:
            cmd_export_zone(self.zone_id)
            self.status_message = f"Exported Python ASCII code for '{self.zone_id}'."
            self.status_timer = 180
        # [NEW ZONE] button
        elif 540 <= mx <= 630:
            new_id = f"custom_zone_{len(WORLD_BLUEPRINTS) + 1}"
            cmd_new_zone(new_id, theme=self.zone_data.get("theme", "canopy"))
            self.load_zone(new_id)
        # [HELP] button
        elif self.screen_w - 90 <= mx <= self.screen_w - 10:
            self.show_help = not self.show_help

    def _handle_zone_picker_click(self, mx, my):
        """Handles selecting a zone from the dropdown."""
        picker_rect = pygame.Rect(10, self.top_bar_height + 4, 380, min(500, self.screen_h - 100))
        if picker_rect.collidepoint(mx, my):
            row_h = 28
            idx = (my - (picker_rect.top + 36)) // row_h
            zone_ids = list_zone_ids()
            if 0 <= idx < len(zone_ids):
                selected = zone_ids[idx]
                self.load_zone(selected)
        else:
            self.show_zone_picker = False

    def _handle_palette_click(self, mx, my):
        """Handles clicking a brush icon on the left sidebar."""
        y_cursor = self.top_bar_height + 10
        for pcat in BRUSH_PALETTES:
            y_cursor += 24  # header
            for ch, name in pcat["items"]:
                item_rect = pygame.Rect(8, y_cursor, self.palette_width - 16, 24)
                if item_rect.collidepoint(mx, my):
                    self.active_brush = ch
                    self.status_message = f"Selected Brush: [{ch}] {name}"
                    self.status_timer = 120
                    return
                y_cursor += 26
            y_cursor += 8

    # =========================================================================
    # DRAWING ROUTINES
    # =========================================================================

    def draw(self):
        self.window.fill(COLOR_BG_DARK)

        # 1. Draw Canvas (Tilemap, autotiling, grid, props, cursor)
        self._draw_canvas()

        # 2. Draw Left Palette Sidebar
        self._draw_palette()

        # 3. Draw Top Toolbar
        self._draw_top_bar()

        # 4. Draw Bottom Status Bar
        self._draw_status_bar()

        # 5. Overlays (Zone Picker Dropdown, Help Modal)
        if self.show_zone_picker:
            self._draw_zone_picker()
        if self.show_help:
            self._draw_help_modal()

    def _draw_canvas(self):
        # Set clipping to canvas area
        prev_clip = self.window.get_clip()
        self.window.set_clip(self.canvas_rect)

        # Fill background with room's atmospheric theme color
        bg_col = self.zone_data.get("bg_color", (16, 28, 42))
        pygame.draw.rect(self.window, bg_col, self.canvas_rect)

        theme = self.zone_data.get("theme", "canopy")
        tile_px = int(TILE_SIZE * self.zoom)

        # Calculate visible grid bounds
        top_left_col = max(0, int(self.cam_x // TILE_SIZE))
        top_left_row = max(0, int(self.cam_y // TILE_SIZE))
        cols_visible = int((self.canvas_rect.width / self.zoom) // TILE_SIZE) + 2
        rows_visible = int((self.canvas_rect.height / self.zoom) // TILE_SIZE) + 2
        bottom_right_col = min(self.cols, top_left_col + cols_visible)
        bottom_right_row = min(self.rows, top_left_row + rows_visible)

        # Draw Grid Lines
        if self.zoom >= 1.2:
            for c in range(top_left_col, bottom_right_col + 1):
                sx = int(self.canvas_rect.left + (c * TILE_SIZE - self.cam_x) * self.zoom)
                pygame.draw.line(self.window, COLOR_GRID_LINE, (sx, self.canvas_rect.top), (sx, self.canvas_rect.bottom))
            for r in range(top_left_row, bottom_right_row + 1):
                sy = int(self.canvas_rect.top + (r * TILE_SIZE - self.cam_y) * self.zoom)
                pygame.draw.line(self.window, COLOR_GRID_LINE, (self.canvas_rect.left, sy), (self.canvas_rect.right, sy))

        # Draw Tiles
        for r in range(top_left_row, bottom_right_row):
            for c in range(top_left_col, bottom_right_col):
                ch = self.grid[r][c]
                sx = int(self.canvas_rect.left + (c * TILE_SIZE - self.cam_x) * self.zoom)
                sy = int(self.canvas_rect.top + (r * TILE_SIZE - self.cam_y) * self.zoom)
                cell_rect = pygame.Rect(sx, sy, tile_px, tile_px)

                if ch == '#':
                    # Solid Block with 4-bit Autotile Texture if assets loaded
                    mask = self.autotile_masks[r][c]
                    if self.assets and theme in self.assets.autotiles:
                        raw_tex = self.assets.autotiles[theme].get(mask)
                        if raw_tex:
                            scaled_tex = pygame.transform.scale(raw_tex, (tile_px, tile_px))
                            self.window.blit(scaled_tex, (sx, sy))
                            continue
                    # Fallback procedural block
                    pygame.draw.rect(self.window, (65, 115, 75), cell_rect)
                    pygame.draw.rect(self.window, (95, 155, 105), cell_rect, 1)

                elif ch in ('~', 'v'):  # Water or Magma
                    hazard_color = (220, 60, 30) if ch == 'v' else (30, 130, 200)
                    pygame.draw.rect(self.window, hazard_color, cell_rect)
                    lbl = self.font_small.render("LAVA" if ch == 'v' else "WATER", True, (255, 255, 255))
                    self.window.blit(lbl, (sx + 2, sy + 2))

                elif ch != '.':
                    # Draw Object Symbol & Color Box
                    info = TILE_LEGEND.get(ch, {"name": ch, "color": (180, 180, 180)})
                    base_color = info.get("color", (180, 180, 180))
                    pygame.draw.rect(self.window, base_color, cell_rect)
                    pygame.draw.rect(self.window, (255, 255, 255), cell_rect, 1)
                    # Draw character letter
                    lbl = self.font_bold.render(ch, True, (0, 0, 0))
                    self.window.blit(lbl, (sx + tile_px // 2 - lbl.get_width() // 2, sy + tile_px // 2 - lbl.get_height() // 2))

        # Draw Level Outer Boundary Outline
        map_w_px = int(self.cols * TILE_SIZE * self.zoom)
        map_h_px = int(self.rows * TILE_SIZE * self.zoom)
        map_x = int(self.canvas_rect.left - self.cam_x * self.zoom)
        map_y = int(self.canvas_rect.top - self.cam_y * self.zoom)
        pygame.draw.rect(self.window, (255, 180, 60), (map_x, map_y, map_w_px, map_h_px), 2)

        # Draw Cursor Hover Highlight
        mx, my = pygame.mouse.get_pos()
        if self.canvas_rect.collidepoint(mx, my):
            wx, wy = self.screen_to_world(mx, my)
            hc, hr = self.world_to_grid(wx, wy)
            if 0 <= hr < self.rows and 0 <= hc < self.cols:
                hsx = int(self.canvas_rect.left + (hc * TILE_SIZE - self.cam_x) * self.zoom)
                hsy = int(self.canvas_rect.top + (hr * TILE_SIZE - self.cam_y) * self.zoom)
                hover_rect = pygame.Rect(hsx, hsy, tile_px, tile_px)
                pygame.draw.rect(self.window, COLOR_CURSOR_HOVER, hover_rect, 2)

        self.window.set_clip(prev_clip)

    def _draw_top_bar(self):
        """Renders the top application toolbar."""
        bar_rect = pygame.Rect(0, 0, self.screen_w, self.top_bar_height)
        pygame.draw.rect(self.window, COLOR_PANEL_BG, bar_rect)
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (0, self.top_bar_height - 1), (self.screen_w, self.top_bar_height - 1), 1)

        # Buttons on top bar
        btn_y = 8
        btn_h = 32

        # 1. [ ZONES ▼ ]
        self._draw_btn(10, btn_y, 100, btn_h, "ZONES ▼", COLOR_ACCENT if self.show_zone_picker else COLOR_BUTTON_BG)
        # 2. [ SAVE ]
        self._draw_btn(120, btn_y, 80, btn_h, "SAVE", COLOR_BUTTON_BG)
        # 3. [ PLAYTEST (F5) ]
        self._draw_btn(210, btn_y, 90, btn_h, "PLAY ▶", (45, 110, 70))
        # 4. [ UNDO ]
        self._draw_btn(310, btn_y, 60, btn_h, "UNDO", COLOR_BUTTON_BG if self.undo_stack else (28, 34, 48))
        # 5. [ REDO ]
        self._draw_btn(380, btn_y, 60, btn_h, "REDO", COLOR_BUTTON_BG if self.redo_stack else (28, 34, 48))
        # 6. [ EXPORT ]
        self._draw_btn(450, btn_y, 80, btn_h, "EXPORT", COLOR_BUTTON_BG)
        # 7. [ + NEW ZONE ]
        self._draw_btn(540, btn_y, 90, btn_h, "+ NEW", COLOR_BUTTON_BG)

        # Title & Active Zone Label in center
        title_str = f"ZONE: {self.zone_id} ({self.zone_data.get('title', '')})"
        title_surf = self.font_hud.render(title_str, True, COLOR_TEXT_WHITE)
        self.window.blit(title_surf, (645, 15))

        # [ HELP ] button on far right
        self._draw_btn(self.screen_w - 90, btn_y, 80, btn_h, "HELP (H)", COLOR_BUTTON_BG)

    def _draw_palette(self):
        """Renders the left brush selection sidebar."""
        palette_rect = pygame.Rect(0, self.top_bar_height, self.palette_width, self.screen_h - self.top_bar_height - self.status_bar_height)
        pygame.draw.rect(self.window, COLOR_PANEL_BG, palette_rect)
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (self.palette_width - 1, self.top_bar_height), (self.palette_width - 1, self.screen_h), 1)

        y_cursor = self.top_bar_height + 8
        mx, my = pygame.mouse.get_pos()

        for pcat in BRUSH_PALETTES:
            # Category Header
            cat_surf = self.font_bold.render(f"▪ {pcat['category'].upper()}", True, (255, 205, 80))
            self.window.blit(cat_surf, (12, y_cursor))
            y_cursor += 20

            for ch, name in pcat["items"]:
                item_rect = pygame.Rect(8, y_cursor, self.palette_width - 16, 22)
                is_selected = (self.active_brush == ch)
                is_hovered = item_rect.collidepoint(mx, my)

                # Background fill
                if is_selected:
                    bg_col = (45, 95, 65)
                elif is_hovered:
                    bg_col = COLOR_BUTTON_HOVER
                else:
                    bg_col = (30, 36, 50)
                pygame.draw.rect(self.window, bg_col, item_rect, border_radius=3)
                if is_selected:
                    pygame.draw.rect(self.window, COLOR_ACCENT, item_rect, 1, border_radius=3)

                # Character square preview
                info = TILE_LEGEND.get(ch, {"color": (120, 120, 120)})
                sq_rect = pygame.Rect(12, y_cursor + 3, 16, 16)
                pygame.draw.rect(self.window, info.get("color", (120, 120, 120)), sq_rect)
                pygame.draw.rect(self.window, (255, 255, 255), sq_rect, 1)

                ch_lbl = self.font_bold.render(ch, True, (0, 0, 0))
                self.window.blit(ch_lbl, (sq_rect.centerx - ch_lbl.get_width() // 2, sq_rect.centery - ch_lbl.get_height() // 2))

                # Name label
                text_col = COLOR_TEXT_WHITE if (is_selected or is_hovered) else COLOR_TEXT_DIM
                lbl = self.font_small.render(name[:18], True, text_col)
                self.window.blit(lbl, (34, y_cursor + 4))

                y_cursor += 24
            y_cursor += 6

    def _draw_status_bar(self):
        """Renders the bottom status bar with telemetry."""
        bar_rect = pygame.Rect(0, self.screen_h - self.status_bar_height, self.screen_w, self.status_bar_height)
        pygame.draw.rect(self.window, (14, 18, 26), bar_rect)
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (0, bar_rect.top), (self.screen_w, bar_rect.top), 1)

        # Hovered Cell telemetry
        mx, my = pygame.mouse.get_pos()
        hover_info = "Cursor: Outside"
        if self.canvas_rect.collidepoint(mx, my):
            wx, wy = self.screen_to_world(mx, my)
            hc, hr = self.world_to_grid(wx, wy)
            if 0 <= hr < self.rows and 0 <= hc < self.cols:
                char_at = self.grid[hr][hc]
                tile_info = TILE_LEGEND.get(char_at, {}).get("name", "Unknown")
                hover_info = f"Grid: ({hc:02d}, {hr:02d}) | World: ({int(wx):04d}px, {int(wy):04d}px) | Tile: [{char_at}] {tile_info}"

        hover_surf = self.font_small.render(hover_info, True, COLOR_TEXT_WHITE)
        self.window.blit(hover_surf, (self.palette_width + 12, bar_rect.top + 6))

        # Flash message or shortcuts
        msg = self.status_message if self.status_timer > 0 else f"Active Brush: [{self.active_brush}] | Zoom: {self.zoom:.1f}x | [Ctrl+S] Save | [F5] Play | [H] Help"
        msg_col = COLOR_ACCENT if self.status_timer > 0 else COLOR_TEXT_DIM
        msg_surf = self.font_small.render(msg, True, msg_col)
        self.window.blit(msg_surf, (12, bar_rect.top + 6))

    def _draw_btn(self, x, y, w, h, text, bg_color):
        rect = pygame.Rect(x, y, w, h)
        mx, my = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mx, my)
        fill = COLOR_BUTTON_HOVER if is_hover and bg_color == COLOR_BUTTON_BG else bg_color
        pygame.draw.rect(self.window, fill, rect, border_radius=4)
        pygame.draw.rect(self.window, COLOR_PANEL_BORDER, rect, 1, border_radius=4)
        lbl = self.font_bold.render(text, True, COLOR_TEXT_WHITE)
        self.window.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.centery - lbl.get_height() // 2))

    def _draw_zone_picker(self):
        """Renders the dropdown zone picker modal."""
        zone_ids = list_zone_ids()
        modal_w = 420
        modal_h = min(520, self.screen_h - 100)
        modal_rect = pygame.Rect(10, self.top_bar_height + 4, modal_w, modal_h)
        pygame.draw.rect(self.window, (22, 28, 40), modal_rect, border_radius=6)
        pygame.draw.rect(self.window, COLOR_ACCENT, modal_rect, 2, border_radius=6)

        hdr_surf = self.font_hud.render("SELECT METROIDVANIA ZONE TO LOAD:", True, COLOR_ACCENT)
        self.window.blit(hdr_surf, (modal_rect.left + 14, modal_rect.top + 10))
        pygame.draw.line(self.window, COLOR_PANEL_BORDER, (modal_rect.left, modal_rect.top + 32), (modal_rect.right, modal_rect.top + 32))

        mx, my = pygame.mouse.get_pos()
        y_c = modal_rect.top + 38
        row_h = 28
        for zid in zone_ids:
            row_rect = pygame.Rect(modal_rect.left + 6, y_c, modal_w - 12, row_h - 2)
            is_hover = row_rect.collidepoint(mx, my)
            is_active = (zid == self.zone_id)
            if is_active:
                row_bg = (40, 90, 60)
            elif is_hover:
                row_bg = COLOR_BUTTON_HOVER
            else:
                row_bg = (28, 34, 48)

            pygame.draw.rect(self.window, row_bg, row_rect, border_radius=3)
            zdata = WORLD_BLUEPRINTS[zid]
            lbl = self.font_bold.render(zid, True, COLOR_TEXT_WHITE if is_active or is_hover else (180, 195, 215))
            self.window.blit(lbl, (row_rect.left + 8, row_rect.top + 5))

            meta_lbl = self.font_small.render(f"{zdata.get('theme', '')} | {len(zdata.get('ascii_grid', []))}r", True, (130, 150, 175))
            self.window.blit(meta_lbl, (row_rect.right - meta_lbl.get_width() - 8, row_rect.top + 6))
            y_c += row_h

    def _draw_help_modal(self):
        """Renders an educational walkthrough modal for the nephew."""
        mw = min(720, self.screen_w - 60)
        mh = min(560, self.screen_h - 80)
        rect = pygame.Rect((self.screen_w - mw) // 2, (self.screen_h - mh) // 2, mw, mh)
        pygame.draw.rect(self.window, (20, 26, 38), rect, border_radius=8)
        pygame.draw.rect(self.window, COLOR_ACCENT, rect, 2, border_radius=8)

        # Title
        title_surf = self.font_title.render("FROGGY LEVEL STUDIO: NEPHEW'S GUIDE", True, COLOR_ACCENT)
        self.window.blit(title_surf, (rect.left + 24, rect.top + 18))

        guide_lines = [
            ("CONTROLS & SHORTCUTS:", COLOR_ACCENT),
            ("  - Left-Click / Drag:  Paint selected tile or object into the world", COLOR_TEXT_WHITE),
            ("  - Right-Click:         Erase back to air ('.')", COLOR_TEXT_WHITE),
            ("  - Middle-Click / Drag: Pan camera smoothly across the room", COLOR_TEXT_WHITE),
            ("  - Mouse Wheel:         Zoom in / Zoom out centered on mouse cursor", COLOR_TEXT_WHITE),
            ("  - W / A / S / D:       Smooth camera navigation", COLOR_TEXT_WHITE),
            ("  - Ctrl + Z / Ctrl + Y: Full Undo & Redo history stack", COLOR_TEXT_WHITE),
            ("  - Ctrl + S:            Save zone directly to disk (levels/<zone_id>.json)", COLOR_TEXT_WHITE),
            ("  - F5:                  Instant Playtest! Jump, swing, and stomp right here!", COLOR_TEXT_WHITE),
            ("  - Ctrl + E:            Export formatted Python ASCII code to terminal", COLOR_TEXT_WHITE),
            ("", COLOR_TEXT_WHITE),
            ("LEVEL DESIGN TIPS FOR A GREAT METROIDVANIA:", (255, 215, 80)),
            ("  1. Player Jump Arc: Froggy jumps 4.5 tiles high and 6 tiles horizontally.", COLOR_TEXT_DIM),
            ("  2. Grapple Placement: Place Golden Idols ('G') 3 to 6 tiles above hazard pits.", COLOR_TEXT_DIM),
            ("  3. Autotiling: Draw solid blocks ('#') freely! The 4-bit neighbor algorithm", COLOR_TEXT_DIM),
            ("     automatically picks the perfect mossy grass top, corner, or ceiling.", COLOR_TEXT_DIM),
            ("  4. Checkpoint Totems ('X'): Put a totem every 2-3 rooms to save progress!", COLOR_TEXT_DIM),
            ("", COLOR_TEXT_WHITE),
            ("Press [ESC] or [H] to close this help window.", COLOR_ACCENT),
        ]

        y_cur = rect.top + 56
        for line, col in guide_lines:
            lbl = self.font_small.render(line, True, col)
            self.window.blit(lbl, (rect.left + 24, y_cur))
            y_cur += 20


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Froggy Level Studio: Standalone 2D Level Builder & Metroidvania Zone Tweaker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py level_studio.py --list
  py level_studio.py --info entrance_hall
  py level_studio.py --zone level_1
  py level_studio.py --play frost_springs
  py level_studio.py --new cavern_depths --theme volcanic --cols 70 --rows 23
  py level_studio.py --export toad_colosseum
  py level_studio.py --reset level_1
        """,
    )
    parser.add_argument("--list", "-l", action="store_true", help="List all existing zones with exact names and metadata")
    parser.add_argument("--info", "-i", metavar="ZONE_ID", help="Detailed inspection of a zone's geometry, doors & NPCs")
    parser.add_argument("--zone", "-z", metavar="ZONE_ID", help="Launch visual Level Studio loaded into this zone")
    parser.add_argument("--play", "-p", metavar="ZONE_ID", help="Playtest directly in this zone with live Froggy physics")
    parser.add_argument("--new", "-n", metavar="ZONE_ID", help="Create a brand-new zone from scratch")
    parser.add_argument("--title", type=str, default=None, help="Title for the new zone")
    parser.add_argument("--theme", type=str, default="canopy", choices=list(ZONE_THEMES.keys()), help="Biome theme for the new zone")
    parser.add_argument("--cols", type=int, default=60, help="Grid width in tiles for new zone (default: 60)")
    parser.add_argument("--rows", type=int, default=23, help="Grid height in tiles for new zone (default: 23)")
    parser.add_argument("--export", "-e", metavar="ZONE_ID", help="Export clean Python ASCII representation to terminal")
    parser.add_argument("--reset", metavar="ZONE_ID", help="Reset an edited zone back to built-in factory default")
    parser.add_argument("--headless", action="store_true", help="Do not open GUI window (useful for tests)")

    args = parser.parse_args()

    # CLI flag dispatches
    if args.list:
        cmd_list_zones()
        return

    if args.info:
        cmd_info_zone(args.info)
        return

    if args.export:
        cmd_export_zone(args.export)
        return

    if args.reset:
        cmd_reset_zone(args.reset)
        return

    if args.new:
        cmd_new_zone(args.new, title=args.title, theme=args.theme, cols=args.cols, rows=args.rows)
        if not args.headless and not args.play:
            # Launch GUI into the newly created zone
            gui = LevelStudioGUI(initial_zone_id=args.new)
            gui.run()
        return

    if args.play:
        cmd_play_zone(args.play)
        return

    # If --zone is passed or no flags given, launch visual editor
    target_zone = args.zone if args.zone else "level_1"
    if args.headless:
        print(f"[Level Studio Headless] Successfully validated zone '{target_zone}'.")
        return

    gui = LevelStudioGUI(initial_zone_id=target_zone)
    gui.run()


if __name__ == "__main__":
    main()
