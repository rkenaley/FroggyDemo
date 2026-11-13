import math
import os
import shutil
import struct
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import froggy_engine as fe
import world_data as wd


def _headlessly_init():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    audio = fe.RetroAudioEngine()
    assets = fe.AssetManager()
    anims = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()
    return canvas, audio, assets, anims, enemy_anims


def test_01_falo_84hp_snowflake_shield_cold_beam_and_heat_vents(canvas, audio, assets, anims, enemy_anims):
    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="falo_arena")
    player = fe.FroggyPlayer(120, 200, anims)
    room = world.current_room
    room.active_player_ref = player
    boss = room.get_active_boss()
    assert isinstance(boss, fe.FaloSnowmanBoss)
    assert boss.max_hp == 84 and boss.hp == 84, f"Expected Falo 84 HP, got {boss.hp}/{boss.max_hp}"
    assert boss.ice_shield_hp == 6
    assert len(room.heat_vent_candidates) == 6, f"Expected 6 choice heat vent locations in falo_arena, got {len(room.heat_vent_candidates)}"
    assert len(room.heat_vents) == 2, f"Expected 2 active random heat vents in falo_arena, got {len(room.heat_vents)}"

    # Transient Geothermal Heat Vent warms Froggy quickly when active
    active_vent = next(hv for hv in room.heat_vents if hv.is_active)
    player.x, player.y = active_vent.x, active_vent.y - 16
    player.rect.topleft = (int(player.x), int(player.y))
    player.body_temp = 40.0
    player.update(fe.SNESController(), room, world, audio)
    assert player.body_temp > 41.0, "Active heat vent should rapidly warm Froggy"

    # Shielded Falo is completely invulnerable (hits clang harmlessly without damaging HP or shield count)
    boss.awaken()
    boss.state = "SHIELD_VOLLEY"
    boss.hit_by_spore_boomerang(room, is_red=True)
    boss.take_stomp_damage(room, audio=audio)
    boss.hit_by_tongue_whip(room, audio=audio)
    assert boss.hp == 84 and boss.ice_shield_hp == 6

    # Launches all 6 ShieldSnowflakeProjectiles one-by-one until ice_shield_hp == 0 -> VULNERABLE
    room.boss_projectiles.clear()
    boss.shield_throw_timer = 1
    for _ in range(260):
        boss.update(room)
        if boss.state == "VULNERABLE":
            break
    assert boss.ice_shield_hp == 0 and boss.state == "VULNERABLE"
    flakes = [p for p in room.boss_projectiles if isinstance(p, fe.ShieldSnowflakeProjectile)]
    assert len(flakes) == 6, f"Expected 6 ShieldSnowflakeProjectiles launched, got {len(flakes)}"

    # 2 snowflake hits in a row push body_temp to 0 -> severe Hypothermia frostbite!
    player.hp = 5
    player.body_temp = 100.0
    player.invuln_timer = 0
    for idx in range(2):
        player.invuln_timer = 0
        f = flakes[idx]
        f.x, f.y = player.center_x, player.center_y
        player._check_damage_collisions(room, audio)
    assert player.body_temp == 0.0, f"2 snowflake hits should freeze Froggy to 0.0 body_temp, got {player.body_temp}"
    assert player.hp <= 2, f"2 consecutive snowflake hits should inflict impact + hypothermia shock damage (hp={player.hp})"

    # Hitting Falo while VULNERABLE ALWAYS triggers COLD_BEAM_RECHARGE (FrostWindLayer active + regenerates all 6 flakes)
    boss.hit_by_spore_boomerang(room, is_red=True)
    assert boss.hp == 74
    assert boss.state == "COLD_BEAM_RECHARGE"
    assert room.frost_wind.state == "WARNING"
    for _ in range(140):
        room.frost_wind.update(player=player, room=room, camera_y=0.0, audio=audio)
        boss.update(room)
        if boss.state == "SHIELD_VOLLEY":
            break
    assert boss.ice_shield_hp == 6 and boss.state == "SHIELD_VOLLEY"

    # Taking too long while VULNERABLE ALSO triggers COLD_BEAM_RECHARGE to regenerate flakes!
    boss.ice_shield_hp = 0
    boss.state = "VULNERABLE"
    boss.state_timer = 1
    boss.update(room)
    assert boss.state == "COLD_BEAM_RECHARGE", "Vulnerable timeout must always trigger Cold Beam Recharge!"

    room.draw(canvas, 0, 0, 20, include_screen_layers=False)
    room.draw_screen_layers(canvas, 20)
    print("[PASS] test_01_falo_84hp_snowflake_shield_cold_beam_and_heat_vents")


def test_02_spore_boomerang_blocked_by_solids_and_rocks(assets, anims, enemy_anims):
    room = fe.TileMapRoom("l2_sky_grapples", wd.WORLD_BLUEPRINTS["l2_sky_grapples"], assets, enemy_anims)
    # Fire right into a solid brick column and into a burrow rock column
    assert len(room.solid_tiles) > 0 and len(room.burrow_rocks) > 0
    target_solid = room.solid_tiles[0]
    b1 = fe.SporeBoomerang(target_solid.left - 12, target_solid.centery, 1, 0, is_red=True)
    for _ in range(10):
        b1.update(room)
        if not b1.alive:
            break
    assert b1.alive is False, "Boomerang must stop on solid blocks/ledges instead of penetrating!"

    target_rock = room.burrow_rocks[0]
    b2 = fe.SporeBoomerang(target_rock.left - 12, target_rock.centery, 1, 0, is_red=False)
    for _ in range(10):
        b2.update(room)
        if not b2.alive:
            break
    assert b2.alive is False, "Boomerang must stop on cracked burrow rocks!"
    print("[PASS] test_02_spore_boomerang_blocked_by_solids_and_rocks")


def test_03_emperor_mantis_p3_upgrade_and_sprites(assets, anims, enemy_anims):
    assert fe.BOSS_MAX_HP == 7, f"Expected 7 HP (+50% P3), got {fe.BOSS_MAX_HP}"
    room = fe.TileMapRoom("boss_sanctum", wd.WORLD_BLUEPRINTS["boss_sanctum"], assets, enemy_anims)
    player = fe.FroggyPlayer(220, 240, anims)
    room.active_player_ref = player
    boss = fe.EmperorMantis(320, 120, enemy_anims)
    assert boss.max_hp == 7 and boss.hp == 7
    boss.awaken()

    # Check 64x64 upgraded mantis sprites
    for key in ("armored_right", "armored_left", "exposed_right", "exposed_left"):
        assert key in boss.anims and boss.anims[key].get_size() == (64, 64), f"Expected 64x64 mantis '{key}'"

    # Force Phase 3 (hp=3) -> verify 5-way scythe barrage and faster P3 dive speed
    boss.hp = 3
    assert boss.phase == 3
    boss.state = "HOVER"
    boss.attack_cooldown = 1
    boss.attack_cycle = 1  # triggers wave branch on increment -> even cycle
    room.boss_projectiles.clear()
    boss.update(room)
    assert len(room.boss_projectiles) == 5, f"Expected 5 Phase 3 scythe projectiles, got {len(room.boss_projectiles)}"

    boss.state = "DIVE_TELEGRAPH"
    boss.state_timer = 1
    boss.update(room)
    assert boss.state == "DIVE_ATTACK"
    assert abs(boss.dive_vx) + abs(boss.dive_vy) >= 9.9
    print("[PASS] test_03_emperor_mantis_p3_upgrade_and_sprites")


def test_04_unique_boss_backgrounds_even_when_awakened(canvas, assets, enemy_anims):
    boss_rooms = {
        "boss_sanctum": "sanctum",
        "hound_sanctum": "hound_palace",
        "toad_colosseum": "toad_colosseum",
        "falo_arena": "falo_arena",
        "shark_sanctum": "shark_sanctum",
    }
    assert len(set(boss_rooms.values())) == 5
    for room_id, bg_key in boss_rooms.items():
        bg = assets.backgrounds.get(bg_key)
        assert bg is not None and bg.get_size() == (640, 360), f"Missing 640x360 bg '{bg_key}' for {room_id}"
        room = fe.TileMapRoom(room_id, wd.WORLD_BLUEPRINTS[room_id], assets, enemy_anims)
        boss = room.get_active_boss()
        if boss:
            boss.awaken()
        room.sinister_ambience_active = True
        room.draw(canvas, 0, 0, 15)
    print("[PASS] test_04_unique_boss_backgrounds_even_when_awakened")


def test_05_dread_hound_fakeout_feint_and_phases(assets, anims, enemy_anims):
    room = fe.TileMapRoom("hound_sanctum", wd.WORLD_BLUEPRINTS["hound_sanctum"], assets, enemy_anims)
    player = fe.FroggyPlayer(120, 260, anims)
    room.active_player_ref = player
    hound = room.get_active_boss()
    assert isinstance(hound, fe.DreadHoundBoss)
    assert hound.max_hp == 16
    for pose in ("idle", "lunge", "dazed", "howl", "flame"):
        assert hound.anims[pose].get_size() == (96, 96)

    hound.awaken()
    hound.state = "FAKEOUT_FEINT"
    hound.vx = -7.0
    hound.state_timer = 15
    room.boss_projectiles.clear()
    for _ in range(18):
        hound.update(room)
        if hound.state == "HOWL":
            break
    assert hound.state == "HOWL", f"Expected FAKEOUT_FEINT to pivot into HOWL, got {hound.state}"
    assert hound.x >= 140.0, "Feint should brake well short of the left wall"
    assert len(room.boss_projectiles) >= 2, "HOWL after fake-out feint must hurl fireballs"
    print("[PASS] test_05_dread_hound_fakeout_feint_and_phases")


def test_06_gigatoad_heavy_sfx_and_sprites(audio, assets, anims, enemy_anims):
    for sfx_key in ("toad_land_heavy", "toad_stomp_impact", "toad_punch_whoosh", "toad_wall_crash"):
        assert sfx_key in audio.sfx, f"Missing Giga Toad SFX '{sfx_key}'"
    room = fe.TileMapRoom("toad_colosseum", wd.WORLD_BLUEPRINTS["toad_colosseum"], assets, enemy_anims)
    world = fe.WorldManager({"toad_colosseum": wd.WORLD_BLUEPRINTS["toad_colosseum"]}, assets, enemy_anims, starting_room_id="toad_colosseum")
    world.audio = audio
    room = world.current_room
    player = fe.FroggyPlayer(160, 260, anims)
    room.active_player_ref = player
    toad = room.get_active_boss()
    assert isinstance(toad, fe.GigaToadBoss)
    for k in ("idle", "slam", "punch", "dazed", "enraged"):
        assert toad.anims[k].get_size() == (96, 96)
    toad.awaken()
    toad.state = "JUMP_SLAM"
    toad.vy = 6.0
    toad.y = float(room.world_height - 96)
    toad.update(room)
    audio.play_sfx("toad_stomp_impact")
    audio.play_sfx("toad_punch_whoosh")
    audio.play_sfx("toad_wall_crash")
    print("[PASS] test_06_gigatoad_heavy_sfx_and_sprites")


def test_07_demon_shark_no_self_stun_in_open_water(assets, anims, enemy_anims):
    for k in ("idle", "idle_1", "charge", "dazed", "enraged"):
        assert enemy_anims["shark"][k].get_size() == (96, 64)
    room = fe.TileMapRoom("shark_sanctum", wd.WORLD_BLUEPRINTS["shark_sanctum"], assets, enemy_anims)
    player = fe.FroggyPlayer(200, 180, anims)
    room.active_player_ref = player
    shark = room.get_active_boss()
    assert isinstance(shark, fe.DemonSharkBoss)
    shark.awaken()

    # Short open-water charge with room center well clear of walls must NOT self-stun!
    shark.state = "TORPEDO_CHARGE"
    shark.x = 520.0
    shark.y = 140.0
    shark.rect.topleft = (int(shark.x), int(shark.y))
    shark.vx = -2.0
    shark.state_timer = 10
    for _ in range(12):
        shark.update(room)
    assert shark.state != "DAZED", "Shark must NOT self-stun in open water without hitting a wall!"
    assert shark.state == "ABYSS_PROWL"

    # Hitting left wall MUST stun into DAZED
    shark.state = "TORPEDO_CHARGE"
    shark.x = 34.0
    shark.y = 180.0
    shark.rect.topleft = (int(shark.x), int(shark.y))
    shark.vx = -8.0
    shark.state_timer = 90
    shark.update(room)
    assert shark.state == "DAZED", f"Expected DAZED on wall slam, got {shark.state}"
    print("[PASS] test_07_demon_shark_no_self_stun_in_open_water")


def test_08_door_and_perimeter_sealing_no_infinity_fall(canvas, audio, assets, anims, enemy_anims):
    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="toad_colosseum")
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    ctrl = fe.SNESController()
    hud_font = pygame.font.SysFont("monospace", 10, bold=True)

    for room_id in ("level_1", "toad_colosseum", "boss_sanctum", "frost_ascent"):
        world.warp_directly_to_room(room_id, fe.FroggyPlayer(100, 100, anims), camera, audio)
        room = world.current_room
        player = fe.FroggyPlayer(room.world_width - 20, room.world_height - 48, anims)
        player.door_cooldown = 60  # simulate arriving/cooldown where door transitions are disabled
        ctrl.held["RIGHT"] = True
        for _ in range(30):
            player.vx = 6.0
            player.vy = 6.0
            player.update(ctrl, room, world, audio)
            assert 0.0 <= player.x <= room.world_width - player.width, f"{room_id} escaped X: {player.x}"
            assert 0.0 <= player.y <= room.world_height - player.height, f"{room_id} escaped Y: {player.y}"

        # Test SWINGING clamp too
        player.tongue_state = "SWINGING"
        player.grapple_anchor = pygame.math.Vector2(room.world_width - 10, 80)
        player.swing_rope_length = 40.0
        player.swing_angle = 0.2
        player.swing_angular_vel = 0.2
        ctrl.held["Y"] = True
        player.update(ctrl, room, world, audio)
        assert 0.0 <= player.x <= room.world_width - player.width
        assert 0.0 <= player.y <= room.world_height - player.height
        ctrl.held["RIGHT"] = False
        ctrl.held["Y"] = False

        # Draw minimap even if extreme coordinates are queried -> no error and stays bounded
        fe.draw_hud_and_minimap(canvas, hud_font, player, world, camera, (0, 0), ctrl, False, 10)
    print("[PASS] test_08_door_and_perimeter_sealing_no_infinity_fall")


def test_09_real_save_load_master_door_unlock_and_level2_banner(audio, assets, anims, enemy_anims):
    # A. Non-destructive check that on-disk save_game.json (if present) loads cleanly into its saved zone
    save_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save_game.json")
    if os.path.exists(save_src):
        temp_real = "test_v12_readonly_real_copy.json"
        orig_save = fe.SaveManager.SAVE_FILE
        shutil.copyfile(save_src, temp_real)
        fe.SaveManager.SAVE_FILE = temp_real
        try:
            real_data = fe.SaveManager.load_from_disk()
            assert real_data is not None and real_data["room_id"] in wd.WORLD_BLUEPRINTS
            cam_r = fe.SmoothCamera(640, 360)
            w_r, p_r = fe.SaveManager.restore_to_game(
                real_data, wd.WORLD_BLUEPRINTS, assets, enemy_anims, anims, cam_r, audio
            )
            assert w_r.current_room.room_id == real_data["room_id"]
            assert len(p_r.key_fragments) == len(real_data.get("key_fragments", []))
        finally:
            fe.SaveManager.SAVE_FILE = orig_save
            if os.path.exists(temp_real):
                os.remove(temp_real)

    # B. Deterministic regression check: saved in toad_colosseum with 4 fragments & Master Key -> Door 'L' unseals & unlocks Level 2
    import json
    temp_save = "test_v12_master_door_save.json"
    orig_save = fe.SaveManager.SAVE_FILE
    sample_save = {
        "room_id": "toad_colosseum",
        "player_x": 930.0,
        "player_y": 288.0,
        "hp": 6,
        "max_hp": 6,
        "eaten_count": 20,
        "has_stomping_boots": True,
        "has_red_boomerang": True,
        "has_muhlaser": True,
        "has_vitality_heart": True,
        "has_falo_heart": True,
        "has_abyssal_pearl": True,
        "key_fragments": ["mantis", "hound", "toad", "falo"],
        "has_master_key": True,
        "master_door_unlocked": False,
        "level_2_unlocked": False,
        "defeated_bosses": ["toad_colosseum", "boss_sanctum", "hound_sanctum", "falo_arena"],
        "cleared_rocks": [],
        "collected_items": [],
        "opened_chests": [],
        "activated_crystals": ["toad_colosseum"],
        "lit_torches": [],
    }
    with open(temp_save, "w", encoding="utf-8") as f:
        json.dump(sample_save, f)
    fe.SaveManager.SAVE_FILE = temp_save
    try:
        save_data = fe.SaveManager.load_from_disk()
        assert save_data is not None and save_data["room_id"] == "toad_colosseum"
        camera = fe.SmoothCamera(640, 360)
        world, player = fe.SaveManager.restore_to_game(
            save_data, wd.WORLD_BLUEPRINTS, assets, enemy_anims, anims, camera, audio
        )

        assert world.current_room.room_id == "toad_colosseum"
        assert len(player.key_fragments) == 4 and player.has_master_key is True
        assert world.current_room.boss_defeated is True
        assert round(player.x) == 930 and round(player.y) == 288

        # Walk right from saved position (930, 288) into Door 'L' at col 59 (x=944)!
        ctrl = fe.SNESController()
        ctrl.held["RIGHT"] = True
        player.door_cooldown = 0
        for _ in range(12):
            player.update(ctrl, world.current_room, world, audio)
            if world.master_door_unlocked or world.is_transitioning:
                break
        assert world.master_door_unlocked is True, "Door 'L' failed to unseal with Master Key from save position!"
        assert world.level_2_unlocked is True
        assert world.is_transitioning, "Touching unlocked Door 'L' should start transition to victory_chamber"
        while world.is_transitioning:
            world.update_transition(player, camera, audio)
        assert world.current_room.room_id == "victory_chamber"
        assert "LEVEL 2 UNLOCKED" in world.current_room.custom_banner_text
        print("[PASS] test_09_real_save_load_master_door_unlock_and_level2_banner")
    finally:
        fe.SaveManager.SAVE_FILE = orig_save
        if os.path.exists(temp_save):
            os.remove(temp_save)


def test_10_level2_map_grid_tree_and_skyfrog_gauntlet(canvas, audio, assets, anims, enemy_anims):
    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="victory_chamber")
    world.level_2_unlocked = True
    player = fe.FroggyPlayer(64, 64, anims)
    camera = fe.SmoothCamera(640, 360)
    ctrl = fe.SNESController()
    hud_font = pygame.font.SysFont("monospace", 10, bold=True)

    # Check map_grid separation and scale
    tree = world.rooms["l2_tree_ascent"]
    sky = world.rooms["l2_sky_grapples"]
    summit = world.rooms["l2_sky_summit"]
    assert tree.map_grid == 2 and sky.map_grid == 2 and summit.map_grid == 2
    assert world.rooms["level_1"].map_grid == 1
    assert tree.world_height >= 3 * fe.INTERNAL_HEIGHT, f"Tree ascent height {tree.world_height} < 3 screens"
    assert sky.world_width >= 3 * fe.INTERNAL_WIDTH, f"Sky gauntlet width {sky.world_width} < 3 screens"
    assert sky.has_bottomless_pit is True

    # Test Skyfrog bottomless pit respawn + damage
    world.warp_directly_to_room("l2_sky_grapples", player, camera, audio)
    player.hp = 5
    safe_x, safe_y = player.last_safe_pos
    player.y = float(sky.world_height + 24)
    player.rect.y = int(player.y)
    player.update(ctrl, sky, world, audio)
    assert player.hp == 4, f"Expected 1 damage from sky pit fall, got hp={player.hp}"
    assert abs(player.x - safe_x) < 2 and abs(player.y - safe_y) < 2
    assert "SKY" in sky.custom_banner_text

    # Render minimap in Grid 2 cleanly
    fe.draw_hud_and_minimap(canvas, hud_font, player, world, camera, (0, 0), ctrl, False, 15)
    print("[PASS] test_10_level2_map_grid_tree_and_skyfrog_gauntlet")


def test_11_swinging_boomerang_and_muhlaser_rock_break(audio, assets, anims, enemy_anims):
    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="l2_sky_grapples")
    room = world.current_room
    player = fe.FroggyPlayer(2040, 140, anims)
    player.world_manager_ref = world
    player.has_red_boomerang = True
    player.has_muhlaser = True
    player.facing_right = True
    room.active_player_ref = player

    # Anchor Froggy in SWINGING state facing right toward cracked rocks around col 132 (x=2112)
    player.tongue_state = "SWINGING"
    player.grapple_anchor = pygame.math.Vector2(2048, 128)
    player.swing_rope_length = 48.0
    player.swing_angle = 0.0
    player.swing_angular_vel = 0.0

    ctrl = fe.SNESController()
    ctrl.held["Y"] = True
    ctrl.held["RIGHT"] = True
    ctrl.held["R"] = True
    ctrl.just_pressed["R"] = True

    # Frame 1 of holding R while SWINGING launches SporeBoomerang!
    player.update(ctrl, room, world, audio)
    assert len(player.projectiles) >= 1, "Boomerang failed to fire while SWINGING!"
    assert player.tongue_state == "SWINGING"

    # Continue holding Y+R while SWINGING to charge Muhlaser (>= 36 frames -> 0.20 charge_ratio), then release to break rocks!
    ctrl.just_pressed["R"] = False
    for _ in range(42):
        player.update(ctrl, room, world, audio)
    assert player.tongue_state == "SWINGING"
    assert player.laser_charge >= 36
    ctrl.held["R"] = False
    initial_rocks = len(room.burrow_rocks)
    assert initial_rocks > 0
    player.update(ctrl, room, world, audio)
    for _ in range(18):
        room.update_entities(player, audio, 0)
        player.update(fe.SNESController(), room, world, audio)
    assert len(room.burrow_rocks) < initial_rocks, "Mid-swing Muhlaser failed to shatter Skyfrog Cracked Rocks!"
    print("[PASS] test_11_swinging_boomerang_and_muhlaser_rock_break")


def _measure_midi_stats(filepath):
    data = open(filepath, "rb").read()
    assert data[:4] == b"MThd"
    _, ntrks, div = struct.unpack(">HHH", data[8:14])
    pos = 14
    us_per_q = 500000
    max_t = 0
    empty_tracks = 0
    for ti in range(ntrks):
        assert data[pos:pos + 4] == b"MTrk"
        ln = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        tb = data[pos + 8:pos + 8 + ln]
        pos += 8 + ln
        p, t, rs, tr_notes = 0, 0, 0, 0
        while p < len(tb):
            v = 0
            while True:
                c = tb[p]; p += 1
                v = (v << 7) | (c & 0x7F)
                if not (c & 0x80):
                    break
            t += v
            st = tb[p]
            if st == 0xFF:
                mt = tb[p + 1]; p += 2
                ml = 0
                while True:
                    c = tb[p]; p += 1
                    ml = (ml << 7) | (c & 0x7F)
                    if not (c & 0x80):
                        break
                if mt == 0x51 and ml == 3:
                    us_per_q = (tb[p] << 16) | (tb[p + 1] << 8) | tb[p + 2]
                p += ml
            elif st >= 0xF0:
                p += 1
            else:
                if st & 0x80:
                    rs = st; p += 1
                else:
                    st = rs
                cmd = st & 0xF0
                p += 1 if cmd in (0xC0, 0xD0) else 2
                if cmd == 0x90:
                    tr_notes += 1
        max_t = max(max_t, t)
        if ti > 0 and tr_notes == 0:
            empty_tracks += 1
    bars = (max_t / div) / 4.0
    secs = (max_t / div) * (us_per_q / 1_000_000.0)
    return bars, secs, empty_tracks


def test_12_all_levels_and_bosses_have_midi_soundtracks(audio, assets, enemy_anims):
    for key, path in audio.midi_files.items():
        assert os.path.exists(path), f"Missing MIDI file for '{key}': {path}"
        assert os.path.getsize(path) > 5000, f"MIDI file too small for '{key}': {path}"
        bars, secs, empty_tracks = _measure_midi_stats(path)
        assert bars >= 47.9, f"MIDI '{key}' too short ({bars:.2f} bars)"
        assert secs >= 85.0, f"MIDI '{key}' loop too short ({secs:.1f}s)"
        assert empty_tracks == 0, f"MIDI '{key}' has {empty_tracks} silent track(s)"

    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    for room_id, room in world.rooms.items():
        audio.current_track_name = None
        audio.play_room_music(room)
        assert audio.current_track_name in audio.midi_files, f"Room '{room_id}' resolved to unknown track {audio.current_track_name}"
        assert os.path.exists(audio.midi_files[audio.current_track_name])

    for boss_room_id, (_, track_name) in fe.WorldManager._BOSS_ROOM_AUDIO.items():
        assert track_name in audio.midi_files and os.path.exists(audio.midi_files[track_name]), f"Missing boss track {track_name}"
    print("[PASS] test_12_all_levels_and_bosses_have_midi_soundtracks")


def test_13_level2_wrap_boundary_and_unjumpable_walls(canvas, audio, assets, anims, enemy_anims):
    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="l2_tree_ascent")
    tree_room = world.current_room
    assert tree_room.horizontal_wrap is True
    assert tree_room.world_width == fe.INTERNAL_WIDTH == 640

    # 1. Exiting right wraps cleanly onto left edge (and vice versa)
    player = fe.FroggyPlayer(632.0, 960.0, anims)
    player.vx = 5.0
    player._move_and_collide(tree_room)
    assert player.x < 32.0, f"Expected wrap from right to left, got x={player.x}"

    player.x = -4.0
    player.rect.x = -4
    player.vx = -5.0
    player._move_and_collide(tree_room)
    assert player.x > 600.0, f"Expected wrap from left to right, got x={player.x}"

    # SporeBoomerang also wraps across loop boundary cleanly
    spore = fe.SporeBoomerang(638.0, 900.0, 1, 0, is_red=False)
    spore.update(tree_room)
    assert spore.alive and spore.x < 32.0, f"Expected boomerang wrap, got x={spore.x}"
    player.active_room_wrap_width = tree_room.world_width
    player.x = -4.0
    player.draw(canvas, 0, 800)

    # 2. Level 2 outer side walls cannot be wall-jumped (touching_wall_dir cleared)
    sky_room = world.rooms["l2_sky_grapples"]
    p2 = fe.FroggyPlayer(float(sky_room.world_width - 30), 160.0, anims)
    p2.on_ground = False
    p2.vx = 4.0
    p2.double_jump_available = False
    p2._move_and_collide(sky_room)
    assert p2.touching_wall_dir == 0, "Level 2 outer side walls must remain unjumpable"

    # 3. Level 1 keeps the super-jumpy wall-jump + double_jump_available restoration!
    l1_room = world.rooms["entrance_hall"]
    p1 = fe.FroggyPlayer(float(l1_room.world_width - 30), 160.0, anims)
    p1.on_ground = False
    p1.vx = 4.0
    p1.double_jump_available = False
    p1._move_and_collide(l1_room)
    assert p1.touching_wall_dir == 1, "Level 1 wall-jump contact must remain active"
    ctrl = fe.SNESController()
    ctrl.held["B"] = True
    ctrl.just_pressed["B"] = True
    p1._update_standard_physics(ctrl, l1_room, audio)
    assert p1.double_jump_available is True and p1.vy == fe.WALL_JUMP_Y_SPEED
    print("[PASS] test_13_level2_wrap_boundary_and_unjumpable_walls")


def test_14_boss_rebalance_no_rush_muhlaser_hound_flamethrower_and_toad_guard(canvas, audio, assets, anims, enemy_anims):
    # 1. Boss Rush must NOT grant Muhlaser
    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    player = fe.FroggyPlayer(100, 200, anims)
    camera = fe.SmoothCamera(640, 360)
    rush = fe.BossRushManager()
    rush.start_rush(world, player, camera, audio)
    assert player.has_muhlaser is False, "Boss Rush must NOT grant Muhlaser"
    assert player.has_stomping_boots is True and player.has_red_boomerang is True

    # 2. Dread Hound proximity-biased 50/50 rush vs feint, guaranteed rush after 2 feints, and Phase 3 Flamethrower
    hound_room = world.rooms["hound_sanctum"]
    hound = hound_room.get_active_boss()
    hound_room.active_player_ref = player
    hound.awaken()
    player.x = 120.0
    far_prob = hound._compute_rush_probability(player)
    player.x = hound.center_x - 70.0
    close_prob = hound._compute_rush_probability(player)
    assert 0.30 <= close_prob < 0.50 < far_prob <= 0.75, f"Unexpected proximity probs: close={close_prob}, far={far_prob}"
    hound.consecutive_feints = 2
    assert hound._compute_rush_probability(player) == 1.0, "After 2 feints, next attack must guarantee rush"

    hound.hp = 2  # Phase 3
    hound.state = "WALL_IDLE"
    hound.state_timer = 1
    hound.attack_counter = 1  # Next even turn -> Phase 3 FLAMETHROWER
    hound_room.boss_projectiles.clear()
    hound.update(hound_room)
    assert hound.state == "FLAMETHROWER"
    for _ in range(30):
        hound.update(hound_room)
    flames = [p for p in hound_room.boss_projectiles if isinstance(p, fe.HoundFireball) and p.is_flamethrower]
    assert len(flames) >= 4, f"Phase 3 Flamethrower should emit a continuous flame stream, got {len(flames)}"

    # 3. Giga Toad 90 HP and no consecutive head-stomp or HURT chain exploits
    toad_room = world.rooms["toad_colosseum"]
    toad = toad_room.get_active_boss()
    toad_room.active_player_ref = player
    toad.awaken()
    assert toad.max_hp == 90 and toad.hp == 90
    top_rect = pygame.Rect(int(toad.center_x - 6), int(toad.y - 6), 12, 16)
    toad.state = "BRAWLER_IDLE"
    assert toad.check_stomp(top_rect, player_vy=4.0) is False, "Must NOT allow stomping BRAWLER_IDLE"
    toad.state = "PANTING"
    assert toad.check_stomp(top_rect, player_vy=4.0) is True
    toad.take_stomp_damage(toad_room, audio)
    assert toad.state == "HURT" and toad.hp == 82
    assert toad.check_stomp(top_rect, player_vy=4.0) is False, "Must NOT allow consecutive chain stomps during HURT"
    assert toad.shield_active is True, "Brawler shield must protect during HURT recovery"
    hp_during_hurt = toad.hp
    toad.hit_by_spore_boomerang(toad_room, is_red=True)
    assert toad.hp == hp_during_hurt, "Extra boomerangs must be deflected during HURT recovery"
    print("[PASS] test_14_boss_rebalance_no_rush_muhlaser_hound_flamethrower_and_toad_guard")


def test_15_v13_battletoad_flamethrower_thermometer_and_trial(canvas, audio, assets, anims, enemy_anims):
    hud_font = pygame.font.SysFont("monospace", 10, bold=True)
    title_font = pygame.font.SysFont("impact", 32, bold=True)
    menu_font = pygame.font.SysFont("monospace", 11, bold=True)

    # 1. Dread Hound high grapple hooks + full-screen Flamethrower range across 640px arena
    world = fe.WorldManager(wd.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="hound_sanctum")
    hound_room = world.current_room
    assert len(hound_room.grapple_nodes) >= 5, f"Expected >=5 high grapple hooks in hound_sanctum, got {len(hound_room.grapple_nodes)}"
    jet = fe.HoundFireball(540.0, 260.0, -7.8, 0.0, is_flame=True, is_flamethrower=True)
    min_x = jet.x
    for _ in range(100):
        jet.update(hound_room)
        min_x = min(min_x, jet.x)
        if not jet.alive:
            break
    assert min_x <= 64.0, f"Full-screen flamethrower should cross entire arena to far wall, stopped at x={min_x}"

    # 2. Giga Toad smooth multi-frame generative sprites + continuous HP speed escalation + fearsome stomp
    toad_anims = enemy_anims["toad"]
    for seq_key, min_len in (("idle_frames", 4), ("walk_frames", 6), ("slam_frames", 4), ("punch_frames", 4), ("dazed_frames", 4), ("enraged_frames", 4)):
        frames = toad_anims.get(seq_key, [])
        assert len(frames) >= min_len, f"Expected >= {min_len} frames in toad['{seq_key}'], got {len(frames)}"
        for fr in frames:
            assert fr.get_size() == (96, 96)

    toad_room = world.rooms["toad_colosseum"]
    toad = toad_room.get_active_boss()
    toad.awaken()
    s90 = (toad.current_walk_speed, toad.current_dash_speed, toad.current_shockwave_speed)
    toad.hp = 60
    s60 = (toad.current_walk_speed, toad.current_dash_speed, toad.current_shockwave_speed)
    toad.hp = 30
    s30 = (toad.current_walk_speed, toad.current_dash_speed, toad.current_shockwave_speed)
    toad.hp = 1
    s1 = (toad.current_walk_speed, toad.current_dash_speed, toad.current_shockwave_speed)
    assert s90 < s60 < s30 < s1, f"Speeds must increase continuously as HP drops: {s90}, {s60}, {s30}, {s1}"
    assert s1[0] >= 3.90 and s1[1] >= 14.4 and s1[2] >= 7.1, f"Near-death speed must include +15% max boost, got {s1}"

    # Stomp landing triggers heavy shake + taller bilateral GigaShockwave
    toad_room.boss_projectiles.clear()
    toad.state = "JUMP_SLAM_AIR"
    toad.vy = 6.0
    toad.y = 260.0
    for _ in range(30):
        toad.update(toad_room)
        if toad.state == "PANTING":
            break
    assert toad.state == "PANTING" and toad_room.screen_shake_timer >= 42
    waves = [p for p in toad_room.boss_projectiles if isinstance(p, fe.GigaShockwave)]
    assert len(waves) == 2 and all(w.height >= 20 for w in waves)

    # 3. Falo choice heat vents: never vanish untouched, overshoot temp over 3.5s use, then respawn
    falo_room = world.rooms["falo_arena"]
    player = fe.FroggyPlayer(200, 200, anims)
    falo_room.active_player_ref = player
    ctrl = fe.SNESController()
    initial_ids = {id(hv) for hv in falo_room.heat_vents}
    # Idle 420 frames away from vents -> untouched vents remain active!
    player.x, player.y = 320.0, 60.0
    player.rect.topleft = (320, 60)
    for pt in range(420):
        if any(player.rect.colliderect(hv.warm_zone) for hv in falo_room.heat_vents):
            player.y += 16
            player.rect.y = int(player.y)
        falo_room.update_entities(player, audio, pt)
    assert {id(hv) for hv in falo_room.heat_vents} == initial_ids, "Untouched heat vents must NOT disappear on their own!"

    # Now stand inside first vent for 220 frames (~3.67s) -> overshoots temp > 100 and despawns/replenishes!
    target_vent = falo_room.heat_vents[0]
    target_xy = (int(target_vent.x), int(target_vent.y))
    player.body_temp = 75.0
    for pt in range(220):
        player.x, player.y = target_vent.x, target_vent.y - 8
        player.rect.topleft = (int(player.x), int(player.y))
        player.update(ctrl, falo_room, world, audio)
        falo_room.update_entities(player, audio, pt)
    assert player.body_temp > 105.0, f"Using heat vent ~3.5s should normalize and safely overshoot temp, got {player.body_temp}"
    assert target_vent.use_frames_left == 0, "Vent should be fully consumed after 210+ frames of use"
    assert len(falo_room.heat_vents) == 2 and target_vent not in falo_room.heat_vents, "Spent vent must vanish and respawn a replacement"
    assert (int(falo_room.heat_vents[0].x), int(falo_room.heat_vents[0].y)) != target_xy or len(falo_room.heat_vent_candidates) <= 2

    # 4. Unified Thermometer HUD rendering across cold, normal, and overheat bands
    camera = fe.SmoothCamera(falo_room.world_width, falo_room.world_height)
    world.current_room = falo_room
    for t_val in (12.0, 100.0, 182.0):
        player.body_temp = t_val
        fe.draw_hud_and_minimap(canvas, hud_font, player, world, camera, (0, 0), ctrl, False, 16)

    # 5. Individual Boss Time Trial mode + PB persistence + selector screen rendering
    camera = fe.SmoothCamera(640, 360)
    rush = fe.BossRushManager()
    fe.draw_title_screen(canvas, title_font, menu_font, 3, 12, anims["right"]["idle"][0], assets, has_save=True)
    fe.draw_boss_trial_select_screen(canvas, title_font, menu_font, 2, 12, assets, rush)
    rush.start_individual_trial(2, world, player, camera, audio)
    assert world.game_mode == "BOSS_TRIAL" and rush.individual_mode is True
    assert world.current_room.room_id == "toad_colosseum" and player.has_muhlaser is False
    for _ in range(45):
        rush.update(world, player, camera, audio)
    assert rush.timer.total_frames == 45
    world.current_room.boss_defeated = True
    rush.update(world, player, camera, audio)
    assert rush.completed is True and rush.is_new_pb is True
    assert rush.get_individual_best("toad_colosseum") == 46
    rush.draw_split_hud(canvas, hud_font)
    # Verify slower run does NOT overwrite faster PB
    rush2 = fe.BossRushManager()
    assert rush2.get_individual_best("toad_colosseum") == 46
    print("[PASS] test_15_v13_battletoad_flamethrower_thermometer_and_trial")


def test_16_v14_boss_overhaul_and_sprites(canvas, audio, assets, anims, enemy_anims):
    # 1. Pre-v14 sprite backups preserved for all 5 bosses
    bak_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sprites", "_backup_pre_v14")
    assert os.path.isdir(bak_dir), "Missing pre-v14 boss sprite backup directory"
    for sample in ("mantis_armored.png", "hound_idle.png", "toad_idle.png", "falo_idle.png", "shark_idle.png"):
        assert os.path.exists(os.path.join(bak_dir, sample)), f"Missing backed-up sprite: {sample}"

    # 2. All 5 bosses carry redone generative animation keys & upgraded 96x96 larger Giga Toad
    for k in ("armored_right", "armored_1_right", "dive_right", "exposed_right", "exposed_1_right", "enraged_right"):
        assert enemy_anims["mantis"].get(k) is not None and enemy_anims["mantis"][k].get_size() == (64, 64)
    for k in ("idle", "idle_1", "lunge", "howl", "flame", "dazed"):
        assert enemy_anims["hound"].get(k) is not None and enemy_anims["hound"][k].get_size() == (96, 96)
    for k in ("idle", "idle_1", "throw", "throw_1", "vulnerable", "melt"):
        assert enemy_anims["falo"].get(k) is not None and enemy_anims["falo"][k].get_size() == (64, 64)
    for k in ("idle", "idle_1", "charge", "roar", "dazed", "enraged"):
        assert enemy_anims["shark"].get(k) is not None and enemy_anims["shark"][k].get_size() == (96, 64)
    assert enemy_anims["toad"]["idle"].get_size() == (96, 96)

    # 3. Demon Shark: +30% HP (85), head-stomp removed in water, and AbyssalVortex summon impedes swim
    assert fe.BOSS_MAX_HP_SHARK == 85
    shark_room = fe.TileMapRoom("shark_sanctum", wd.WORLD_BLUEPRINTS["shark_sanctum"], assets, enemy_anims)
    player = fe.FroggyPlayer(220, 160, anims)
    player.has_stomping_boots = True
    player.in_water = True
    shark_room.active_player_ref = player
    shark = shark_room.get_active_boss()
    assert shark.max_hp == 85 and shark.hp == 85
    shark.awaken()
    shark.state = "DAZED"
    player.x, player.y, player.vy = shark.center_x - 10, shark.y - 6, 4.0
    player.rect.topleft = (int(player.x), int(player.y))
    assert shark.check_stomp(player.rect, player.vy) is False, "Demon Shark must NOT be stompable in water!"
    hp_before_touch = player.hp
    player._check_damage_collisions(shark_room, audio)
    assert shark.hp == 85, "Falling onto Demon Shark's head must NOT stomp-damage Shark!"

    # Shark Maelstrom Barrage summons AbyssalVortex pulling player inside radius
    shark_room.abyssal_vortices.clear()
    shark.state = "ABYSS_PROWL"
    shark.attack_cycle = 1
    shark.state_timer = 1
    shark.update(shark_room)
    assert shark.state == "MAELSTROM_BARRAGE" and len(shark_room.abyssal_vortices) >= 1
    vx_obj = shark_room.abyssal_vortices[0]
    player.x = vx_obj.x + 40.0
    player.y = vx_obj.y
    player.rect.topleft = (int(player.x), int(player.y))
    player.vx, player.vy = 0.0, 0.0
    assert vx_obj.apply_to_player(player) is True
    assert player.vx < 0.0 and abs(player.vy) > 0.1, f"AbyssalVortex should pull and swirl player, got {(player.vx, player.vy)}"
    shark_room.draw(canvas, 0, 0, 12)

    # 4. Emperor Mantis: +15% faster in ALL phases (1, 2, 3)
    m_room = fe.TileMapRoom("boss_sanctum", wd.WORLD_BLUEPRINTS["boss_sanctum"], assets, enemy_anims)
    m_room.active_player_ref = player
    mantis = m_room.get_active_boss()
    mantis.awaken()
    mantis.state = "HOVER"
    for hp_val, min_ft_step, min_proj_spd in ((7, 0.036, 4.10), (5, 0.050, 4.10), (2, 0.086, 5.95)):
        mantis.hp = hp_val
        t0 = mantis.flight_timer
        mantis.update(m_room)
        assert mantis.flight_timer - t0 >= min_ft_step, f"Mantis HP={hp_val} hover speed too slow: {mantis.flight_timer - t0}"
        m_room.boss_projectiles.clear()
        mantis._fire_scythe_attack(m_room, player)
        spd = math.hypot(m_room.boss_projectiles[0].vx, m_room.boss_projectiles[0].vy)
        assert spd >= min_proj_spd, f"Mantis HP={hp_val} scythe speed too slow: {spd}"

    # 5. Dread Hound: 16 HP (weighted toward P2/P3) + Howl Ground Spikes forcing aerial grapples
    assert fe.BOSS_MAX_HP_HOUND == 16
    h_room = fe.TileMapRoom("hound_sanctum", wd.WORLD_BLUEPRINTS["hound_sanctum"], assets, enemy_anims)
    h_room.active_player_ref = player
    hound = h_room.get_active_boss()
    assert hound.max_hp == 16
    hound.hp = 16
    assert hound.phase == 1
    hound.hp = 13
    assert hound.phase == 2
    hound.hp = 7
    assert hound.phase == 3

    hound.awaken()
    h_room.boss_projectiles.clear()
    hound.hp = 13
    hound._fire_howl_barrage(h_room)
    spikes = [p for p in h_room.boss_projectiles if isinstance(p, fe.HoundGroundSpike)]
    assert len(spikes) >= 4, f"Expected >=4 P2 HoundGroundSpikes on Howl, got {len(spikes)}"
    assert all(not sp.is_damaging for sp in spikes), "Spikes must telegraph safely before erupting"
    for _ in range(48):
        for sp in spikes:
            sp.update(h_room)
    assert any(sp.is_damaging and sp.current_height >= 40 for sp in spikes), "Spikes must erupt to full height after telegraph"
    hound.draw(canvas, 0, 0, assets)

    # 6. Giga Toad: +15% baseline (1.67 / 7.36 / 3.68) AND max (3.97 / 14.66 / 7.25) speed
    toad_room = fe.TileMapRoom("toad_colosseum", wd.WORLD_BLUEPRINTS["toad_colosseum"], assets, enemy_anims)
    toad = toad_room.get_active_boss()
    toad.hp = toad.max_hp
    assert abs(toad.current_walk_speed - 1.67) < 0.02
    assert abs(toad.current_dash_speed - 7.36) < 0.02
    assert abs(toad.current_shockwave_speed - 3.68) < 0.02
    toad.hp = 0
    assert abs(toad.current_walk_speed - 3.97) < 0.02
    assert abs(toad.current_dash_speed - 14.66) < 0.02
    assert abs(toad.current_shockwave_speed - 7.25) < 0.02
    print("[PASS] test_16_v14_boss_overhaul_and_sprites")


def test_17_v15_froggy_styles_and_main_menu_options(canvas, audio, assets, anims, enemy_anims):
    # 1. Pre-v15 classic Froggy sprite backup preserved cleanly
    bak_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sprites", "_backup_pre_v15_froggy")
    assert os.path.isdir(bak_dir), "Missing pre-v15 Froggy backup directory"
    assert len([f for f in os.listdir(bak_dir) if f.endswith(".png")]) == 23

    # 2. Exactly 3 hero styles: classic + 2 generative palettes
    assert len(fe.FROGGY_STYLES) == 3
    style_ids = [s["id"] for s in fe.FROGGY_STYLES]
    assert style_ids == ["classic", "azure_shinobi", "crimson_dart"]

    expected_states = ("idle", "run", "jump", "fall", "wall_slide", "tongue", "swim", "swing", "hurt")
    style_anims = {}
    signatures = {}
    for sid in style_ids:
        a = assets.build_froggy_animations(sid)
        style_anims[sid] = a
        for d in ("right", "left"):
            for st in expected_states:
                assert st in a[d] and len(a[d][st]) >= 1, f"{sid}/{d}/{st} missing"
                for fr in a[d][st]:
                    assert fr.get_size() == (32, 32), f"{sid}/{d}/{st} wrong size {fr.get_size()}"
                    assert fr.get_at((0, 0)).a == 0, f"{sid}/{d}/{st} (0,0) not transparent"
        idle0 = a["right"]["idle"][0]
        assert any(idle0.get_at((x, 31)).a > 0 for x in range(32)), f"{sid} idle_0 boots float above y=31"
        run0 = a["right"]["run"][0]
        assert any(run0.get_at((x, 31)).a > 0 for x in range(32)), f"{sid} run_0 boots float above y=31"
        signatures[sid] = pygame.image.tobytes(idle0, "RGBA")

    assert len(set(signatures.values())) == 3, "All 3 Froggy styles must have distinct pixel art"

    # 3. SettingsManager persistence across all 3 styles + graceful fallback (without touching save_game.json)
    if os.path.exists(fe.SettingsManager.SETTINGS_FILE):
        os.remove(fe.SettingsManager.SETTINGS_FILE)
    assert fe.SettingsManager.load_style() == fe.DEFAULT_FROGGY_STYLE
    for sid in style_ids:
        assert fe.SettingsManager.save_style(sid) is True
        assert fe.SettingsManager.load_style() == sid
    assert fe.SettingsManager.save_style("nonexistent_style") is True
    assert fe.SettingsManager.load_style() == fe.DEFAULT_FROGGY_STYLE

    # 4. Title screen, Main Menu Options & Controls Alias screens render cleanly
    title_font = pygame.font.SysFont("impact", 32, bold=True)
    menu_font = pygame.font.SysFont("monospace", 11, bold=True)
    hud_font = pygame.font.SysFont("monospace", 10, bold=True)
    for has_save in (True, False):
        fe.draw_title_screen(
            canvas, title_font, menu_font, 4 if has_save else 3, 24,
            style_anims["azure_shinobi"]["right"]["idle"][0], assets,
            has_save=has_save, active_style="azure_shinobi"
        )
    for cursor_idx in range(len(fe.FROGGY_STYLES) + 1):
        fe.draw_options_screen(
            canvas, title_font, menu_font, hud_font,
            cursor_idx, "crimson_dart", cursor_idx * 35 + 10, assets,
            style_animations=style_anims, toast_timer=(40 if cursor_idx == 2 else 0)
        )
    fe.draw_controls_explainer_screen(canvas, title_font, menu_font, hud_font, 12, assets)

    # 5. FroggyPlayer visually switches cleanly across all 3 styles inside level_1
    room = fe.TileMapRoom("level_1", wd.WORLD_BLUEPRINTS["level_1"], assets, enemy_anims)
    sx, sy = room.default_spawn
    for sid in style_ids:
        p = fe.FroggyPlayer(sx, sy, style_anims[sid])
        p.draw(canvas, 0, 0, assets)
    print("[PASS] test_17_v15_froggy_styles_and_main_menu_options")


def main():
    temp_save = "test_v12_temp_save.json"
    temp_records = "test_v12_temp_records.json"
    temp_settings = "test_v12_temp_settings.json"
    orig_save = fe.SaveManager.SAVE_FILE
    orig_records = fe.BossRushManager.RECORDS_FILE
    orig_settings = fe.SettingsManager.SETTINGS_FILE
    fe.SaveManager.SAVE_FILE = temp_save
    fe.BossRushManager.RECORDS_FILE = temp_records
    fe.SettingsManager.SETTINGS_FILE = temp_settings

    try:
        canvas, audio, assets, anims, enemy_anims = _headlessly_init()
        print("========================================================================")
        print("RUNNING V12-V15 /GOAL VERIFICATION & PLAYTEST SUITE")
        print("========================================================================")
        test_01_falo_84hp_snowflake_shield_cold_beam_and_heat_vents(canvas, audio, assets, anims, enemy_anims)
        test_02_spore_boomerang_blocked_by_solids_and_rocks(assets, anims, enemy_anims)
        test_03_emperor_mantis_p3_upgrade_and_sprites(assets, anims, enemy_anims)
        test_04_unique_boss_backgrounds_even_when_awakened(canvas, assets, enemy_anims)
        test_05_dread_hound_fakeout_feint_and_phases(assets, anims, enemy_anims)
        test_06_gigatoad_heavy_sfx_and_sprites(audio, assets, anims, enemy_anims)
        test_07_demon_shark_no_self_stun_in_open_water(assets, anims, enemy_anims)
        test_08_door_and_perimeter_sealing_no_infinity_fall(canvas, audio, assets, anims, enemy_anims)
        fe.SaveManager.SAVE_FILE = orig_save
        test_09_real_save_load_master_door_unlock_and_level2_banner(audio, assets, anims, enemy_anims)
        fe.SaveManager.SAVE_FILE = temp_save
        test_10_level2_map_grid_tree_and_skyfrog_gauntlet(canvas, audio, assets, anims, enemy_anims)
        test_11_swinging_boomerang_and_muhlaser_rock_break(audio, assets, anims, enemy_anims)
        test_12_all_levels_and_bosses_have_midi_soundtracks(audio, assets, enemy_anims)
        test_13_level2_wrap_boundary_and_unjumpable_walls(canvas, audio, assets, anims, enemy_anims)
        test_14_boss_rebalance_no_rush_muhlaser_hound_flamethrower_and_toad_guard(canvas, audio, assets, anims, enemy_anims)
        test_15_v13_battletoad_flamethrower_thermometer_and_trial(canvas, audio, assets, anims, enemy_anims)
        test_16_v14_boss_overhaul_and_sprites(canvas, audio, assets, anims, enemy_anims)
        test_17_v15_froggy_styles_and_main_menu_options(canvas, audio, assets, anims, enemy_anims)
        print("\n========================================================================")
        print("ALL 17 V12-V15 /GOAL VERIFICATION TESTS PASSED 100%!")
        print("========================================================================")
    finally:
        fe.SaveManager.SAVE_FILE = orig_save
        fe.BossRushManager.RECORDS_FILE = orig_records
        fe.SettingsManager.SETTINGS_FILE = orig_settings
        for p in (temp_save, temp_records, temp_settings):
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    main()
