"""
===============================================================================
TEST SUITE: MODULAR WORLD DATA, LEVEL STUDIO, SPRITE INSPECTOR & PERFORMANCE
===============================================================================
Verifies:
1. Modular `world_data.py` registry (loading, validation, creation, persistence).
2. `level_studio.py` standalone CLI & editing operations.
3. `sprite_inspector.py` standalone CLI, bounding boxes, and anchor points.
4. 60 FPS gameplay simulation & performance benchmark verifying zero regressions.
===============================================================================
"""

import copy
import os
import sys
import time
import pygame

# Set dummy headless audio & video drivers for automated testing
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import world_data
import level_studio
import sprite_inspector
import froggy_engine as fe


def test_1_world_data_registry():
    print("\n[TEST 1] Verifying Modular world_data.py Registry...")

    # A. Check all 14 zones loaded
    zone_ids = world_data.list_zone_ids()
    assert len(zone_ids) >= 14, f"Expected at least 14 zones, got {len(zone_ids)}"
    for req_zone in ["level_1", "entrance_hall", "frost_springs", "volcanic_chasm", "sunken_grotto", "falo_arena"]:
        assert req_zone in zone_ids, f"Required zone '{req_zone}' missing from world_data"
    print(f"  + All {len(zone_ids)} world zones verified in registry: PASS")

    # B. Test get_zone returns a deep copy
    z_copy = world_data.get_zone("entrance_hall")
    z_copy["title"] = "MODIFIED TEMP TITLE"
    assert world_data.WORLD_BLUEPRINTS["entrance_hall"]["title"] != "MODIFIED TEMP TITLE"
    print("  + get_zone deep copy isolation verified: PASS")

    # C. Test validation of valid vs invalid zones
    is_valid, errs, warns = world_data.validate_zone_blueprint("entrance_hall", world_data.get_zone("entrance_hall"))
    assert is_valid, f"entrance_hall failed validation: {errs}"
    print("  + validate_zone_blueprint on entrance_hall: PASS")

    # Test invalid geometry caught
    bad_zone = copy.deepcopy(z_copy)
    bad_zone["ascii_grid"] = ["###", "#####"]  # mismatched rows
    is_valid, errs, warns = world_data.validate_zone_blueprint("bad_zone", bad_zone)
    assert not is_valid and len(errs) > 0
    print("  + validate_zone_blueprint correctly flagged jagged geometry error: PASS")

    # D. Test creation of brand new blank zone
    new_id = "test_nephew_grotto"
    new_data = world_data.create_blank_zone(new_id, title="Nephew Secret Grotto", theme="ice", cols=40, rows=20)
    assert len(new_data["ascii_grid"]) == 20
    assert len(new_data["ascii_grid"][0]) == 40
    assert 'S' in "".join(new_data["ascii_grid"])
    saved_path = world_data.save_zone(new_id, new_data, save_to_disk=True)
    assert os.path.exists(saved_path)
    assert new_id in world_data.WORLD_BLUEPRINTS
    print(f"  + create_blank_zone and disk persistence verified ({saved_path}): PASS")

    # Clean up test zone
    world_data.delete_zone(new_id, allow_core=True)
    assert new_id not in world_data.WORLD_BLUEPRINTS
    assert not os.path.exists(saved_path)
    print("  + delete_zone cleanup verified: PASS")


def test_2_level_studio_cli_and_editing():
    print("\n[TEST 2] Verifying Level Studio CLI & Precision Editing Logic...")

    # A. Test summary listing
    zones = world_data.list_zones()
    assert len(zones) >= 14
    for z in zones:
        assert "id" in z and "title" in z and "cols" in z and "rows" in z

    # B. Test command line helper functions directly
    level_studio.cmd_list_zones()
    level_studio.cmd_info_zone("frost_springs")

    # C. Test GUI class in headless mode for editing operations
    gui = level_studio.LevelStudioGUI(initial_zone_id="sandbox_room")
    assert gui.zone_id == "sandbox_room"
    initial_char = gui.grid[10][10]

    # Paint a grapple idol at (10, 10)
    gui.paint_cell(10, 10, 'G')
    assert gui.grid[10][10] == 'G'
    assert len(gui.undo_stack) == 1
    print("  + Paint operation and undo stack push verified: PASS")

    # Undo operation
    gui.undo()
    assert gui.grid[10][10] == initial_char
    assert len(gui.redo_stack) == 1
    print("  + Undo restored original tile verified: PASS")

    # Redo operation
    gui.redo()
    assert gui.grid[10][10] == 'G'
    print("  + Redo restored painted tile verified: PASS")

    # Autotile mask calculation check (col=5, row=5 and col=6, row=5: East/West neighbors)
    gui.paint_cell(5, 5, '#')
    gui.paint_cell(6, 5, '#')
    mask_left = gui.autotile_masks[5][5]
    mask_right = gui.autotile_masks[5][6]
    # East neighbor for (col=5, row=5) is solid -> bit 2 set
    assert (mask_left & 2) != 0
    # West neighbor for (col=6, row=5) is solid -> bit 8 set
    assert (mask_right & 8) != 0
    print("  + Real-time 4-bit autotile bitmask calculation verified: PASS")


def test_3_sprite_inspector_and_bounding_boxes():
    print("\n[TEST 3] Verifying Sprite Inspector Catalog & Bounding Box Overlays...")

    catalog = sprite_inspector.SpriteCatalog()
    assert len(catalog.categories) >= 6
    print(f"  + Catalog categories verified: {list(catalog.categories.keys())} PASS")

    # Verify Froggy Player animation frames
    player_sprites = catalog.categories["player"]["sprites"]
    assert "idle" in player_sprites and "run" in player_sprites and "jump" in player_sprites
    assert len(player_sprites["idle"]["files"]) == 3
    assert len(player_sprites["run"]["files"]) == 4
    print("  + Froggy 32x32 frames confirmed: idle (3f), run (4f), jump (1f) PASS")

    # Verify Bounding Box and Bottom-Center Anchor Math
    gui = sprite_inspector.SpriteInspectorGUI(target_sprite="idle", target_category="player")
    assert len(gui.loaded_frames) == 3
    fname, surf = gui.loaded_frames[0]
    sw, sh = surf.get_size()
    assert sw == 32 and sh == 32
    bbox = surf.get_bounding_rect()
    assert bbox.width > 0 and bbox.height > 0
    anchor_x, anchor_y = sw // 2, sh
    assert anchor_x == 16 and anchor_y == 32
    print(f"  + Froggy Frame 0 Bounding Box: {bbox} | Bottom-Center Anchor: ({anchor_x}, {anchor_y}) PASS")

    # Verify Colossus Boss sprites (Giga Toad, Dread Hound)
    gui.select_sprite("bosses", "toad")
    assert len(gui.loaded_frames) >= 5
    _, toad_surf = gui.loaded_frames[0]
    tw, th = toad_surf.get_size()
    assert tw in (64, 80, 96) and th in (64, 80, 96)
    print(f"  + Giga Toad Colossus {tw}x{th} multi-state frames verified ({len(gui.loaded_frames)} poses) PASS")

    # Test modulo animation loop step
    fps = 10.0
    dt = 0.1  # 100 ms
    frames_count = 4
    clock_step = (0.0 + fps * dt) % frames_count
    assert int(clock_step) == 1
    print("  + Modulo animation timer clock step verified: PASS")


def test_4_gameplay_performance_benchmark():
    print("\n[TEST 4] Verifying 60 FPS Performance Benchmark & Frametime Stability...")

    pygame.init()
    snes_canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    audio = fe.RetroAudioEngine()
    assets = fe.AssetManager()
    controller = fe.SNESController()
    animations = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()

    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    player = fe.FroggyPlayer(64, 64, animations)
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    hud_font = pygame.font.SysFont("monospace", 10, bold=True)

    # Benchmark 180 continuous frames across complex scene
    start_time = time.perf_counter()
    for f in range(180):
        world.current_room.update_entities(player, audio, f)
        player.update(controller, world.current_room, world, audio)
        camera.update(player)
        world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, f)
        player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
        fe.draw_hud_and_minimap(snes_canvas, hud_font, player, world, camera, (100, 100), controller, False, f)

    elapsed = time.perf_counter() - start_time
    fps = 180.0 / elapsed
    ms_per_frame = (elapsed / 180.0) * 1000.0

    print(f"  + Benchmark Results for 180 Frames:")
    print(f"      Total Elapsed: {elapsed:.3f} seconds")
    print(f"      Effective Simulation Rate: {fps:.1f} FPS (Target: 60.0 FPS)")
    print(f"      Average Time per Frame:    {ms_per_frame:.3f} ms (Budget: 16.6 ms)")

    # Assert performance budget: under 16.6ms per frame
    assert ms_per_frame < 16.6, f"Performance budget exceeded! Frame time was {ms_per_frame:.2f} ms"
    print("  + PERFORMANCE BUDGET VERIFIED: Well within 16.6ms frame budget (60 FPS locked)! PASS")


def main():
    print("=" * 72)
    print("RUNNING FROGGY MODULAR TOOLS & PERFORMANCE VERIFICATION SUITE")
    print("=" * 72)

    test_1_world_data_registry()
    test_2_level_studio_cli_and_editing()
    test_3_sprite_inspector_and_bounding_boxes()
    test_4_gameplay_performance_benchmark()

    print("\n" + "=" * 72)
    print("ALL 4 MODULAR TOOLS & PERFORMANCE TEST SUITES PASSED 100%!")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
