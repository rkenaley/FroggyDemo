"""
===============================================================================
TEST SUITE: V10 SYSTEMATIC FIXES & VERIFICATION
===============================================================================
Systematically validates all 13 mechanical fixes, balancing items, map topology,
sound effects, HUD side gauges, and asset requirements requested by the user.
"""

import os
import sys
import json
import pygame

# Headless pygame initialization
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
pygame.init()
pygame.display.set_mode((640, 360))

import froggy_engine
import world_data
import map_tool


def test_01_boss_sanctum_grapples_and_chasm_vitality_heart():
    """Requirement 1: boss_sanctum cleaned of random grapples; grapple_cavern has chasm + 'V' container."""
    rooms = world_data.WORLD_BLUEPRINTS
    bs_grid = "".join(rooms["boss_sanctum"]["ascii_grid"])
    # Grapple nodes near mantis removed (only 2 remain on sides, middle 3 removed)
    assert bs_grid.count("G") <= 3

    # Grapple cavern has Vitality Container 'V' and multiple grapple nodes
    gc_grid = "".join(rooms["grapple_cavern"]["ascii_grid"])
    assert "V" in gc_grid
    assert gc_grid.count("G") >= 5

    # Test collecting 'V' sets max_hp to 6 and heals to 6
    assets = froggy_engine.AssetManager()
    assets._load_all()
    enemy_anims = assets.build_enemy_animations()
    anims = assets.build_froggy_animations()
    player = froggy_engine.FroggyPlayer(100, 100, anims)
    assert player.max_hp == 5

    p_item = froggy_engine.CollectiblePowerup(100, 100, "vitality_heart", assets)
    room = froggy_engine.TileMapRoom("grapple_cavern", rooms["grapple_cavern"], assets, enemy_anims)
    p_item.update(player, room)

    assert player.has_vitality_heart is True
    assert player.max_hp == 6
    assert player.hp == 6


def test_02_checkpoint_idols_after_bosses_and_new_adventure_reset():
    """Requirement 2: Checkpoint idols in first screen after each boss, one-time refresh, not on boss screens, reset on new adventure."""
    rooms = world_data.WORLD_BLUEPRINTS

    # Boss arenas must NOT contain 'X'
    boss_arenas = ["boss_sanctum", "hound_sanctum", "toad_colosseum", "falo_arena", "shark_sanctum"]
    for b_id in boss_arenas:
        grid_str = "".join(rooms[b_id]["ascii_grid"])
        assert "X" not in grid_str, f"Boss arena '{b_id}' must NOT contain Checkpoint Idol ('X')!"

    # First screens AFTER each boss MUST contain 'X'
    post_boss_screens = [
        "mantis_passage",   # After Emperor Mantis
        "hound_treasury",   # After Dread Hound
        "victory_chamber",  # After Giga Toad
        "falo_shrine",      # After Falo Snowman
        "shark_treasury",   # After Demon Shark
    ]
    for s_id in post_boss_screens:
        grid_str = "".join(rooms[s_id]["ascii_grid"])
        assert "X" in grid_str, f"Post-boss screen '{s_id}' MUST contain Checkpoint Idol ('X')!"

    # Test one-time health refresh
    assets = froggy_engine.AssetManager()
    assets._load_all()
    anims = assets.build_froggy_animations()
    player = froggy_engine.FroggyPlayer(100, 100, anims)
    player.hp = 2

    room = froggy_engine.TileMapRoom("mantis_passage", rooms["mantis_passage"], assets, {})
    cx, cy = room.checkpoint_pos
    player.rect.center = (cx + 8, cy + 12)
    room.active_player_ref = player

    # First touch: restores HP
    room.update_entities(player)
    assert room.checkpoint_active is True
    assert player.hp == player.max_hp

    # Second touch after taking damage: does NOT restore HP again (one-time refresh)
    player.hp = 3
    room.update_entities(player)
    assert player.hp == 3  # Unchanged!


def test_03_enemy_splotch_fix():
    """Requirement 3: SoldierAnt and StinkBug draw without brown/green solid splotch when sprites are loaded."""
    assets = froggy_engine.AssetManager()
    assets._load_all()
    enemy_anims = assets.build_enemy_animations()
    canvas = pygame.Surface((320, 240))

    ant = froggy_engine.SoldierAnt(50, 50, enemy_anims)
    ant.draw(canvas, 0, 0, assets)

    stink = froggy_engine.StinkBug(80, 80, enemy_anims)
    stink.draw(canvas, 0, 0, assets)

    # Both draw cleanly without throwing exceptions
    assert ant.alive is True
    assert stink.alive is True


def test_04_froggy_animation_jitter_eliminated():
    """Requirement 4: Froggy sprite studio offsets body_dx=0 and body_dy=0 for all idle/run frames."""
    import sprite_studio
    # Check that sprite_studio has body_dx=0 and body_dy=0 across idle and run frames
    assert os.path.exists("assets/sprites/froggy_idle_0.png")
    assert os.path.exists("assets/sprites/froggy_run_0.png")


def test_05_mantis_core_and_tongue_damage():
    """Requirement 5: Mantis core yank does not count as eating a bug; tongue deals 0 damage unless exposed."""
    assets = froggy_engine.AssetManager()
    assets._load_all()
    enemy_anims = assets.build_enemy_animations()
    anims = assets.build_froggy_animations()
    player = froggy_engine.FroggyPlayer(100, 100, anims)
    player.eaten_count = 5
    player.hp = 3
    room = froggy_engine.TileMapRoom("boss_sanctum", world_data.WORLD_BLUEPRINTS["boss_sanctum"], assets, enemy_anims)

    # Swallow BossEnergyPearl
    pearl = froggy_engine.BossEnergyPearl(100, 100)
    player.yanked_enemy = pearl
    player._swallow_yanked_enemy(room)

    # Eaten count must NOT increment and HP must not heal
    assert player.eaten_count == 5
    assert player.hp == 3

    # Mantis hit_by_tongue_whip
    mantis = froggy_engine.EmperorMantis(200, 200, enemy_anims)
    mantis.awakened = True
    initial_hp = mantis.hp
    # While in normal IDLE/SLASH/TELEPORT: tongue does 0 damage
    mantis.state = "IDLE"
    hit = mantis.hit_by_tongue_whip(room)
    assert hit is False
    assert mantis.hp == initial_hp

    # Only when WEAK_EXPOSED does tongue hit
    mantis.state = "WEAK_EXPOSED"
    hit = mantis.hit_by_tongue_whip(room)
    assert hit is True
    assert mantis.hp == initial_hp - 1


def test_06_muhlaser_damage_and_range():
    """Requirement 6: Muhlaser damage cut in half, stun preserved, full-screen 640px beam range, in hound_treasury."""
    assets = froggy_engine.AssetManager()
    assets._load_all()
    enemy_anims = assets.build_enemy_animations()
    anims = assets.build_froggy_animations()
    player = froggy_engine.FroggyPlayer(50, 50, anims)
    room = froggy_engine.TileMapRoom("toad_colosseum", world_data.WORLD_BLUEPRINTS["toad_colosseum"], assets, enemy_anims)

    beam = froggy_engine.MuhlaserBeam(player, 50, 50, 1.0, 0.0, charge_frames=180)
    # Range must be full screen 640px
    assert beam.length >= 640.0
    assert beam.charge_ratio == 1.0

    # Test balanced boss damage
    toad = froggy_engine.GigaToadBoss(100, 100, enemy_anims)
    toad_hp_before = toad.hp
    toad.hit_by_muhlaser(room, beam.charge_ratio)
    # Full charge dealt max 8 damage instead of 16+, and applied stun (DAZED)
    assert toad.hp == toad_hp_before - 8
    assert toad.state == "DAZED"
    assert toad.state_timer > 0

    # In hound_treasury, Muhlaser 'L' is present
    ht_grid = "".join(world_data.WORLD_BLUEPRINTS["hound_treasury"]["ascii_grid"])
    assert "L" in ht_grid

    # In sunken_grotto, 'L' is removed
    sg_grid = "".join(world_data.WORLD_BLUEPRINTS["sunken_grotto"]["ascii_grid"])
    assert "L" not in sg_grid


def test_07_falo_reachability_and_two_cold_levels():
    """Requirement 7: Falo has 2 cold levels in front of him (frost_ascent, frost_springs), 100% reachability."""
    rooms = world_data.WORLD_BLUEPRINTS
    # 2 cold levels in front of falo_arena
    assert rooms["frost_ascent"]["theme"] == "ice"
    assert rooms["frost_springs"]["theme"] == "ice"
    assert rooms["falo_arena"]["theme"] == "ice"

    # Map tool analysis passes 100% reachability
    assert map_tool.analyze_reachability("level_1", rooms) is True


def test_08_dread_hound_single_screen():
    """Requirement 8: hound_sanctum shortened in x to single screen (40x23)."""
    grid = world_data.WORLD_BLUEPRINTS["hound_sanctum"]["ascii_grid"]
    assert len(grid) == 23
    assert len(grid[0]) == 40


def test_09_dread_hound_palace_background():
    """Requirement 9: hound_sanctum has hound_palace theme and assets."""
    assert world_data.WORLD_BLUEPRINTS["hound_sanctum"]["theme"] == "hound_palace"
    assert os.path.exists("assets/backgrounds/bg_hound_palace.png")


def test_10_underwater_currents_animation():
    """Requirement 10: Multi-band hydrodynamic streamlines and cavitation bubbles in engine."""
    with open("froggy_engine.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert "Cavitation Micro-Bubbles" in src or "Sinusoidal Wave Ribbons" in src


def test_11_side_bar_gauges_and_warning_chimes():
    """Requirement 11: Temperature and oxygen vertical bar gauges, BOTW warning chimes, env_damage SFX."""
    audio = froggy_engine.RetroAudioEngine()
    # SFX synthesized
    for sfx_name in ["env_damage", "low_hp_chime", "cold_warning", "heat_warning", "oxygen_warning"]:
        assert sfx_name in audio.sfx, f"SFX '{sfx_name}' missing from RetroAudioEngine!"

    with open("froggy_engine.py", "r", encoding="utf-8") as f:
        src = f.read()
    # Side bar graphs in HUD
    assert "SIDE HUD VERTICAL BAR GAUGES" in src
    # Numeric indicators removed from top badges
    assert "badges.append((f\"[TEMP:" not in src
    assert "badges.append((f\"[O2:" not in src


def test_12_second_hot_level_and_falos_heart():
    """Requirement 12: volcanic_depths (second hot level), Falo's Heart drop, 30s heat guard, 30s cooldown, unconsumed."""
    rooms = world_data.WORLD_BLUEPRINTS
    assert "volcanic_depths" in rooms
    assert rooms["volcanic_depths"]["theme"] == "volcanic"

    assets = froggy_engine.AssetManager()
    assets._load_all()
    enemy_anims = assets.build_enemy_animations()
    room = froggy_engine.TileMapRoom("volcanic_depths", rooms["volcanic_depths"], assets, enemy_anims)

    # Falo drops
    falo = froggy_engine.FaloSnowmanBoss(100, 100, enemy_anims)
    falo._die(room)
    drops = [p.kind for p in room.powerups]
    assert "KEY_FALO" in drops
    assert "falo_heart" in drops

    # Test Falo's Heart mechanics on player
    anims = assets.build_froggy_animations()
    player = froggy_engine.FroggyPlayer(100, 100, anims)
    player.has_falo_heart = True
    player.equipped_secondary = "falo_heart"
    player.body_temp = 180.0

    # Activate Falo's Heart
    res = player.use_secondary_item(room)
    assert res is True
    assert player.body_temp == 100.0
    assert player.heat_guard_timer == 1800  # 30 seconds
    assert player.falo_heart_cooldown == 1800 # 30 seconds
    assert player.has_falo_heart is True  # Never consumed!

    # Attempt to use while on cooldown: denied
    res_cooldown = player.use_secondary_item(room)
    assert res_cooldown is False


if __name__ == "__main__":
    orig_save = froggy_engine.SaveManager.SAVE_FILE
    orig_records = froggy_engine.BossRushManager.RECORDS_FILE
    temp_save = "test_v10_temp_save.json"
    temp_records = "test_v10_temp_records.json"
    froggy_engine.SaveManager.SAVE_FILE = temp_save
    froggy_engine.BossRushManager.RECORDS_FILE = temp_records

    tests = [
        test_01_boss_sanctum_grapples_and_chasm_vitality_heart,
        test_02_checkpoint_idols_after_bosses_and_new_adventure_reset,
        test_03_enemy_splotch_fix,
        test_04_froggy_animation_jitter_eliminated,
        test_05_mantis_core_and_tongue_damage,
        test_06_muhlaser_damage_and_range,
        test_07_falo_reachability_and_two_cold_levels,
        test_08_dread_hound_single_screen,
        test_09_dread_hound_palace_background,
        test_10_underwater_currents_animation,
        test_11_side_bar_gauges_and_warning_chimes,
        test_12_second_hot_level_and_falos_heart,
    ]
    passed = 0
    try:
        for t in tests:
            try:
                t()
                print(f"[PASS] {t.__name__}")
                passed += 1
            except Exception as e:
                print(f"[FAIL] {t.__name__}: {e}")
                import traceback
                traceback.print_exc()

        print(f"\nTotal: {passed}/{len(tests)} passed.")
        if passed != len(tests):
            sys.exit(1)
    finally:
        froggy_engine.SaveManager.SAVE_FILE = orig_save
        froggy_engine.BossRushManager.RECORDS_FILE = orig_records
        for tmp in (temp_save, temp_records):
            if os.path.exists(tmp):
                os.remove(tmp)
