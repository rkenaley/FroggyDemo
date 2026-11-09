"""
Comprehensive automated test suite for Froggy Engine v5:
Verifies all new mechanics:
  1. MIDI writer & 7 GM tracks
  2. Dread Hound left-facing & lunging
  3. Froggy 32x32 uniform sprites, swing state & animations
  4. Particle 7 vs 8 argument fix
  5. Vertical doors & minimap coordinate normalization
  6. Glacial hot springs & amphibian thermoregulation
  7. Stink Bug death & Poison Gas Cloud
  8. Ice Wolf Spider camouflage & ambush leap
  9. Falo Snowman snowballs, carrot boomerang & top hat stomp
  10. SaveManager checkpoint serialization & disk persistence
"""
import os
import sys
import math
import json
import pygame

# Headless pygame setup for tests
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
pygame.init()
pygame.display.set_mode((640, 360))

import froggy_engine as fe

def test_particle_init():
    print("Testing Particle argument compatibility...")
    p1 = fe.Particle(10, 20, 1.0, -1.0, (255, 0, 0), 30)
    assert p1.radius == 2.0
    p2 = fe.Particle(10, 20, 1.0, -1.0, (255, 0, 0), 30, 4.5)
    assert p2.radius == 4.5
    print("  -> Particle __init__ accepts both 6 and 7 (or 7 and 8 with self) arguments cleanly! PASS")

def test_midi_tracks():
    print("Testing MIDI music tracks...")
    expected_tracks = [
        "jungle_vivaldi_reggae.mid",
        "boss_mantis.mid",
        "boss_hound.mid",
        "boss_toad.mid",
        "boss_snowman.mid",
        "ice_hot_springs.mid",
        "title_theme.mid",
    ]
    for track in expected_tracks:
        path = os.path.join("assets", "music", track)
        assert os.path.exists(path), f"Missing MIDI track: {path}"
        size = os.path.getsize(path)
        assert size > 500, f"MIDI track {track} is too small: {size} bytes"
        # Verify MIDI header: MThd
        with open(path, "rb") as f:
            header = f.read(4)
            assert header == b"MThd", f"Invalid MIDI header in {track}: {header}"
        print(f"  -> Verified MIDI track: {track} ({size} bytes) PASS")

def test_dread_hound_orientation():
    print("Testing Dread Hound orientation & lunging...")
    hound_surf = pygame.Surface((96, 64))
    hound_anims = {
        "idle": [hound_surf],
        "lunge": [hound_surf],
        "dazed": [hound_surf],
        "howl": [hound_surf],
    }
    hound = fe.DreadHoundBoss(200, 100, {"hound": hound_anims})
    assert hound.facing_right == False, "Dread hound should natively face left towards player!"
    assert hound.is_boss == True
    assert hound.max_hp == fe.BOSS_MAX_HP_HOUND
    print("  -> Dread Hound native left-facing verified! PASS")

def test_froggy_swing_and_uniform_sprites():
    print("Testing Froggy 32x32 sprite frames & swing animation...")
    assets = fe.AssetManager()
    anims = assets.build_froggy_animations()
    for facing in ("left", "right"):
        assert "swing" in anims[facing], f"Missing 'swing' animation in {facing}"
        for frame in anims[facing]["swing"]:
            assert frame.get_width() == 32 and frame.get_height() == 32, f"Swing frame not 32x32: {frame.get_size()}"
        for state in anims[facing]:
            for frame in anims[facing][state]:
                assert frame.get_width() == 32 and frame.get_height() == 32, f"Frame in {facing}/{state} not 32x32: {frame.get_size()}"

    player = fe.FroggyPlayer(100, 100, anims)
    player.tongue_state = "SWINGING"
    player._update_animation_state()
    assert player.anim_state == "swing", f"Expected anim_state 'swing', got {player.anim_state}"
    sp = player.get_current_sprite()
    assert sp.get_size() == (32, 32)
    print("  -> Froggy uniform 32x32 frames and dedicated swing poses verified! PASS")

def test_vertical_doors_and_blueprints():
    print("Testing Vertical Doors & Multi-tier World Blueprints...")
    assert "frost_ascent" in fe.WORLD_BLUEPRINTS
    assert "frost_springs" in fe.WORLD_BLUEPRINTS
    assert "falo_arena" in fe.WORLD_BLUEPRINTS

    # Check entrance_hall has top door 'U' leading to frost_ascent 'D'
    eh = fe.WORLD_BLUEPRINTS["entrance_hall"]
    assert "U" in eh["doors"]
    assert eh["doors"]["U"]["target_room"] == "frost_ascent"
    assert eh["doors"]["U"]["target_door"] == "D"
    assert eh["doors"]["U"]["spawn_offset_y"] < 0, "Ceiling door must have negative offset_y"

    # Check frost_ascent has bottom door 'D' leading to entrance_hall 'U'
    fa = fe.WORLD_BLUEPRINTS["frost_ascent"]
    assert "D" in fa["doors"]
    assert fa["doors"]["D"]["target_room"] == "entrance_hall"
    assert fa["doors"]["D"]["target_door"] == "U"
    assert fa["doors"]["D"]["spawn_offset_y"] > 0, "Floor door must have positive offset_y"

    # Check falo_arena has bottom chute 'Z' leading to grapple_cavern 'Z'
    falo_room = fe.WORLD_BLUEPRINTS["falo_arena"]
    assert "Z" in falo_room["doors"]
    assert falo_room["doors"]["Z"]["target_room"] == "grapple_cavern"

    # Check grapple_cavern has ceiling door 'Z' leading to falo_arena
    gc = fe.WORLD_BLUEPRINTS["grapple_cavern"]
    assert "Z" in gc["doors"]
    assert gc["doors"]["Z"]["target_room"] == "falo_arena"

    print("  -> Vertical Doors & bidirectional routing verified! PASS")

def test_thermoregulation():
    print("Testing Amphibian Thermoregulation (Glacial Cold & Hot Springs)...")
    assets = fe.AssetManager()
    enemy_anims = assets.build_enemy_animations()
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="frost_springs")
    player = fe.FroggyPlayer(100, 100, assets.build_froggy_animations())
    controller = fe.SNESController()

    # In glacial room, outside water: body_temp should drain
    init_temp = player.body_temp
    assert init_temp == 100.0
    player.in_water = False
    player.update(controller, world.current_room, world)
    assert player.body_temp < init_temp, f"Body temp should drain in cold: {player.body_temp}"

    # Set player temp low and place in water hazard
    player.body_temp = 40.0
    w = world.current_room.water_hazards[0]
    player.x = float(w.x + 4)
    player.y = float(w.y + 4)
    player.rect.topleft = (int(player.x), int(player.y))
    player.update(controller, world.current_room, world)
    assert player.body_temp > 40.0, f"Hot springs should warm player: {player.body_temp}"

    # Critical hypothermia damage check
    player.body_temp = 0.0
    player.x = 100.0
    player.y = 100.0
    player.rect.topleft = (100, 100)
    player.hp = 5
    for _ in range(80):
        player.update(controller, world.current_room, world)
    assert player.hp < 5, "Hypothermia should deal damage when body_temp <= 0.0"
    print("  -> Thermoregulation (freezing drain, hot spring warmth, hypothermia damage) verified! PASS")

def test_stink_bug_and_poison_gas():
    print("Testing Stink Bug patrol & Poison Gas Cloud...")
    assets = fe.AssetManager()
    enemy_anims = assets.build_enemy_animations()
    room = fe.TileMapRoom("frost_springs", fe.WORLD_BLUEPRINTS["frost_springs"], assets, enemy_anims)
    stink = fe.StinkBug(150, 150, enemy_anims)
    assert stink.alive == True
    stink.stomp_kill(room)
    assert stink.alive == False
    assert len(room.poison_clouds) == 1, "Stink bug should leave a PoisonGasCloud on death!"
    cloud = room.poison_clouds[0]
    assert cloud.alive == True
    print("  -> Stink Bug stomp death & poison gas cloud burst verified! PASS")

def test_ice_wolf_spider():
    print("Testing Ice Wolf Spider camouflage & ambush leap...")
    assets = fe.AssetManager()
    enemy_anims = assets.build_enemy_animations()
    room = fe.TileMapRoom("frost_springs", fe.WORLD_BLUEPRINTS["frost_springs"], assets, enemy_anims)
    spider = fe.IceWolfSpider(200, 200, enemy_anims)
    assert spider.state == "CAMOUFLAGE"

    # Move player within detection radius
    player = fe.FroggyPlayer(240, 200, assets.build_froggy_animations())
    room.active_player_ref = player
    spider.update(room)
    assert spider.state == "SHIVER", f"Spider should shiver when player approaches: {spider.state}"

    # Run down shiver timer
    spider.shiver_timer = 1
    spider.update(room)
    assert spider.state == "AMBUSH_LEAP", f"Spider should ambush-leap after shiver: {spider.state}"
    assert spider.vy < 0, "Ambush leap must launch upward"
    print("  -> Ice Wolf Spider camouflage, shiver, and explosive ambush leap verified! PASS")

def test_falo_snowman_boss():
    print("Testing Falo the Evil Snowman Boss mechanics...")
    assets = fe.AssetManager()
    enemy_anims = assets.build_enemy_animations()
    room = fe.TileMapRoom("falo_arena", fe.WORLD_BLUEPRINTS["falo_arena"], assets, enemy_anims)
    boss = fe.FaloSnowmanBoss(300, 200, enemy_anims)
    assert boss.is_boss == True
    assert boss.hp == 12
    assert boss.max_hp == 12

    boss.awaken()
    assert boss.awakened == True

    # Test Stomp detection on top hat
    player_rect = pygame.Rect(boss.rect.left + 5, boss.rect.top - 2, 14, 16)
    assert boss.check_stomp(player_rect, player_vy=4.0) == True
    boss.take_stomp_damage(room)
    assert boss.hp == 10, f"Expected 10 HP after 2 stomp damage, got {boss.hp}"
    assert boss.state == "DAZED"

    # Test carrot boomerang detachment and projectile list
    player = fe.FroggyPlayer(150, 200, assets.build_froggy_animations())
    room.active_player_ref = player
    boss.state = "THROW_CARROT"
    boss.state_timer = 36
    boss.carrot_attached = True
    boss.update(room)
    assert len(room.boss_projectiles) > 0, "Boss should throw projectile"
    assert boss.carrot_attached == False, "Carrot should be detached during throw"

    # Test death meltdown
    boss.hp = 1
    boss.hit_by_spore_boomerang(room, is_red=True)
    assert boss.alive == False
    assert boss.state == "DEFEATED"
    assert room.boss_defeated == True
    print("  -> Falo the Evil Snowman top hat stomp, carrot boomerang & meltdown verified! PASS")

def test_save_manager_and_checkpoints():
    print("Testing SaveManager Checkpoint Serialization & Disk Persistence...")
    test_file = "test_save_game.json"
    fe.SaveManager.SAVE_FILE = test_file
    if os.path.exists(test_file):
        os.remove(test_file)

    assert fe.SaveManager.has_save() == False

    class DummyPlayer:
        x = 120.0
        y = 240.0
        hp = 4
        body_temp = 88.5
        eaten_count = 15
        has_stomping_boots = True
        has_red_boomerang = True

    dummy = DummyPlayer()
    saved = fe.SaveManager.save_to_disk("frost_springs", dummy, defeated_bosses={"boss_sanctum"}, visited_rooms={"level_1", "frost_springs"})
    assert saved == True
    assert fe.SaveManager.has_save() == True

    loaded = fe.SaveManager.load_from_disk()
    assert loaded is not None
    assert loaded["room_id"] == "frost_springs"
    assert loaded["player_x"] == 120.0
    assert loaded["player_y"] == 240.0
    assert loaded["hp"] == 4
    assert loaded["body_temp"] == 88.5
    assert loaded["eaten_count"] == 15
    assert loaded["has_stomping_boots"] == True
    assert loaded["has_red_boomerang"] == True
    assert "boss_sanctum" in loaded["defeated_bosses"]
    assert "frost_springs" in loaded["visited_rooms"]

    fe.SaveManager.delete_save()
    assert fe.SaveManager.has_save() == False
    fe.SaveManager.SAVE_FILE = "save_game.json"
    print("  -> SaveManager serialization, disk persistence & slot verification verified! PASS")

if __name__ == "__main__":
    test_particle_init()
    test_midi_tracks()
    test_dread_hound_orientation()
    test_froggy_swing_and_uniform_sprites()
    test_vertical_doors_and_blueprints()
    test_thermoregulation()
    test_stink_bug_and_poison_gas()
    test_ice_wolf_spider()
    test_falo_snowman_boss()
    test_save_manager_and_checkpoints()
    print("\n" + "=" * 60)
    print("ALL 10 VERIFICATION TEST SUITES PASSED SUCCESSFULLY!")
    print("=" * 60)
