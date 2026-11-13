import os
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import froggy_engine as fe
import world_data as wd
import level_studio as ls
import sprite_inspector as si


class _FakeKeyState:
    """Minimal key-state mapping supporting pygame.key.get_pressed() indexing."""

    def __init__(self, active_keys=()):
        self.active = set(active_keys)

    def __getitem__(self, key):
        return 1 if key in self.active else 0


def test_all_door_transitions_and_spawns(assets, enemy_anims, animations, audio):
    print("\n[TEST 1] Simulating All World Door Transitions & Spawn Safety...")
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    player = fe.FroggyPlayer(64, 64, animations)
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)

    total_links = 0
    for src_id, bp in wd.WORLD_BLUEPRINTS.items():
        for door_id, cfg in bp.get("doors", {}).items():
            world.warp_directly_to_room(src_id, player, camera, audio)
            src_room = world.current_room
            src_room.boss_defeated = True
            world.master_door_unlocked = True

            door = src_room.doors.get(door_id)
            assert door is not None, f"{src_id}: missing door {door_id} at runtime"

            world.trigger_door_transition(door, audio)
            steps = 0
            while world.is_transitioning and steps < 120:
                world.update_transition(player, camera, audio)
                steps += 1
            assert not world.is_transitioning, f"{src_id}:{door_id} transition hung"

            dest_room = world.current_room
            assert dest_room.room_id == cfg["target_room"], (
                f"{src_id}:{door_id} arrived in {dest_room.room_id}, expected {cfg['target_room']}"
            )

            # Check player 14x16 collision box upon arrival is free of solid terrain and burrow rocks
            for solid in dest_room.solid_tiles:
                assert not player.rect.colliderect(solid), (
                    f"Spawn overlap with solid tile after {src_id}:{door_id} -> {dest_room.room_id} at {player.rect}"
                )
            for rock in dest_room.burrow_rocks:
                assert not player.rect.colliderect(rock), (
                    f"Spawn overlap with burrow rock after {src_id}:{door_id} -> {dest_room.room_id} at {player.rect}"
                )
            if dest_room.theme == "volcanic":
                for lava in dest_room.water_hazards:
                    assert not player.rect.colliderect(lava), (
                        f"Spawn overlap with volcanic lava after {src_id}:{door_id} -> {dest_room.room_id}"
                    )

            total_links += 1

    # Explicitly check newly assigned numeric portals '1' and '2' + SoldierAnt 'N' preservation
    vc_ants = [e for e in world.rooms["volcanic_chasm"].enemies if isinstance(e, fe.SoldierAnt)]
    vd_ants = [e for e in world.rooms["volcanic_depths"].enemies if isinstance(e, fe.SoldierAnt)]
    assert "1" in world.rooms["shark_sanctum"].doors and "1" in world.rooms["shark_treasury"].doors
    assert "2" in world.rooms["volcanic_chasm"].doors and "2" in world.rooms["volcanic_depths"].doors
    assert len(vc_ants) >= 1 and len(vd_ants) >= 1, "SoldierAnt ('N') must still spawn in volcanic rooms!"
    print(f"  + Verified {total_links} live door transitions with zero solid/lava spawn overlaps! PASS")


def test_combat_rendering_and_caching(assets, enemy_anims, animations, audio):
    print("\n[TEST 2] Verifying PoisonGasCloud, Muhlaser Rock Raycast, Flash & Icon Caching...")
    canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="sunken_grotto")
    room = world.current_room
    player = fe.FroggyPlayer(100, 100, animations)
    player.world_manager_ref = world
    room.active_player_ref = player

    # 2A: PoisonGasCloud .rect and player contact damage
    cloud = fe.PoisonGasCloud(player.center_x, player.center_y)
    assert isinstance(cloud.rect, pygame.Rect)
    room.poison_clouds.append(cloud)
    hp_before = player.hp
    player._check_damage_collisions(room, audio)
    assert player.hp == hp_before - 1, f"Expected PoisonGasCloud contact damage, hp={player.hp}"
    cloud.draw(canvas, 0, 0)

    # 2B: MossBeetle & IceWolfSpider flash & leap direction
    beetle = fe.MossBeetle(160, 120, enemy_anims)
    beetle.flash_timer = 6
    beetle.draw(canvas, 0, 0)

    spider = fe.IceWolfSpider(200, 120, enemy_anims)
    spider.facing_right = True
    spider.state = "SHIVER"
    spider.shiver_timer = 1
    spider.update(room)
    assert spider.state == "AMBUSH_LEAP" and spider.vx > 0
    spider.flash_timer = 6
    spider.draw(canvas, 0, 0)

    # 2C: Muhlaser uncharged (<0.20) MUST stop on burrow rock without hitting enemies behind it
    assert len(room.burrow_rocks) > 0, "Expected burrow rock(s) in sunken_grotto"
    target_rock = room.burrow_rocks[0]
    player.teleport_to_room(target_rock.left - 36, target_rock.centery - 8, facing_right=True)
    behind_enemy = fe.MossBeetle(target_rock.right + 16, target_rock.top, enemy_anims)
    room.enemies.append(behind_enemy)

    weak_beam = fe.MuhlaserBeam(player, player.mouth_x, player.mouth_y, 1.0, 0.0, charge_frames=18)
    assert weak_beam.charge_ratio < 0.20
    weak_beam.update(room, audio=audio)
    assert behind_enemy.alive, "Uncharged (<0.20) Muhlaser beam leaked past Cracked Burrow Rock!"

    # Charged (>=0.20) beam burrows through the rock and persists destruction in WorldManager
    rocks_before = len(room.burrow_rocks)
    strong_beam = fe.MuhlaserBeam(player, player.mouth_x, player.mouth_y, 1.0, 0.0, charge_frames=90)
    strong_beam.update(room, audio=audio)
    assert len(room.burrow_rocks) < rocks_before, "Charged Muhlaser failed to shatter Cracked Burrow Rock!"
    assert len(world.destroyed_burrow_rocks.get("sunken_grotto", set())) >= 1

    # Revisit room: shattered rock stays destroyed
    cam = fe.SmoothCamera(room.world_width, room.world_height)
    world.warp_directly_to_room("level_1", player, cam, audio)
    world.warp_directly_to_room("sunken_grotto", player, cam, audio)
    assert len(world.current_room.burrow_rocks) < rocks_before, "Destroyed burrow rock respawned after revisit!"

    # 2D: Cached relic icons (no disk read required in CollectiblePowerup.draw)
    assert "abyssal_pearl" in assets.relic_icons
    orig_load_png = assets._load_png
    def _forbid_load(*args, **kwargs):
        raise AssertionError("Per-frame AssetManager._load_png call detected during draw!")
    assets._load_png = _forbid_load
    try:
        pearl = fe.CollectiblePowerup(100, 100, "abyssal_pearl", assets)
        pearl.draw(canvas, 0, 0)
    finally:
        assets._load_png = orig_load_png

    print("  + PoisonGasCloud contact, Muhlaser raycast rock stop/persist, flash & icon cache verified! PASS")


def test_five_boss_defeats_abyssal_pearl_and_revisit_silence(assets, enemy_anims, animations, audio):
    print("\n[TEST 3] Verifying All 5 Boss Defeats, Abyssal Pearl & Quiet Revisit...")
    canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    font = pygame.font.SysFont("monospace", 10, bold=True)
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    player = fe.FroggyPlayer(64, 64, animations)
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)

    boss_rooms = [
        ("boss_sanctum", "KEY_MANTIS"),
        ("hound_sanctum", "KEY_HOUND"),
        ("toad_colosseum", "KEY_TOAD"),
        ("falo_arena", "KEY_FALO"),
        ("shark_sanctum", "abyssal_pearl"),
    ]
    expected_biome_tracks = {
        "boss_sanctum": "sanctum",
        "hound_sanctum": "hound_palace",
        "toad_colosseum": "sanctum",
        "falo_arena": "ice",
        "shark_sanctum": "underwater",
    }

    for room_id, drop_kind in boss_rooms:
        world.warp_directly_to_room(room_id, player, camera, audio)
        room = world.current_room
        boss = room.get_active_boss()
        assert boss is not None, f"Boss failed to spawn in {room_id}"
        boss.awaken()
        boss._die(room, audio)
        assert room.boss_defeated, f"{room_id}.boss_defeated not set on boss _die"
        assert room_id in world.defeated_bosses, f"{room_id} missing from world.defeated_bosses"
        assert any(p.kind == drop_kind for p in room.powerups), (
            f"Expected {drop_kind} drop in {room_id}, got {[p.kind for p in room.powerups]}"
        )
        for p in room.powerups:
            if p.kind == drop_kind:
                player.teleport_to_room(p.x, p.y)
                p.update(player, room, audio)
                assert p.collected, f"Expected {drop_kind} pickup to collect on contact"

    # Verify Demon Shark's Abyssal Pearl grant & endless underwater O2
    assert player.has_abyssal_pearl is True
    assert player.eaten_count >= 10
    assert "mantis" in player.key_fragments and "falo" in player.key_fragments
    assert len(player.key_fragments) == 4

    world.warp_directly_to_room("shark_sanctum", player, camera, audio)
    if world.current_room.water_hazards:
        w = world.current_room.water_hazards[0]
        player.teleport_to_room(w.centerx - player.width * 0.5, w.centery - player.height * 0.5)
    player.oxygen = 45.0
    player.update(fe.SNESController(), world.current_room, world, audio)
    assert player.in_water is True, "Expected Froggy submerged in shark_sanctum water"
    assert player.oxygen == 100.0, f"Expected Abyssal Pearl to keep underwater O2 at 100%, got {player.oxygen}"

    # Verify revisiting cleared boss rooms triggers no roar/banner/shake/boss music
    for room_id, _ in boss_rooms:
        world.warp_directly_to_room(room_id, player, camera, audio)
        room = world.current_room
        assert room.get_active_boss() is None, f"Defeated boss respawned in {room_id}!"
        assert room.boss_awakening_banner_timer == 0, f"Awakening banner played on revisit to {room_id}"
        assert room.screen_shake_timer == 0, f"Screen shake triggered on revisit to {room_id}"
        assert audio.current_track_name == expected_biome_tracks[room_id], (
            f"Expected calm track {expected_biome_tracks[room_id]} in cleared {room_id}, got {audio.current_track_name}"
        )

    fe.draw_inventory_screen(canvas, font, font, player, assets, 0, 10)
    print("  + All 5 boss defeats, Abyssal Pearl O2 immunity & quiet revisits verified! PASS")


def test_master_key_shop_controls_and_save_roundtrip(assets, enemy_anims, animations, audio):
    print("\n[TEST 4] Verifying Master Key Unseal, Shop Stock, [R] Key & Save/Restore Round-Trip...")
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="toad_colosseum")
    player = fe.FroggyPlayer(64, 64, animations)
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    world.warp_directly_to_room("toad_colosseum", player, camera, audio)

    # 4A: Verify pygame.K_r binds to SNESController["R"]
    ctrl = fe.SNESController()
    orig_get_pressed = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: _FakeKeyState({pygame.K_r})
    try:
        ctrl.update()
        assert ctrl.held["R"] is True, "Expected pygame.K_r to activate controller.held['R']"
    finally:
        pygame.key.get_pressed = orig_get_pressed

    # 4B: Master Key Door unseal in toad_colosseum
    colosseum = world.current_room
    colosseum.boss_defeated = True
    world.defeated_bosses.add("toad_colosseum")
    door_l = colosseum.doors["L"]
    assert door_l.is_master_key_door
    player.teleport_to_room(door_l.rect.centerx - player.width * 0.5, door_l.rect.bottom - player.height)
    player.key_fragments = {"mantis", "hound", "toad", "falo"}

    ctrl_up = fe.SNESController()
    ctrl_up.just_pressed["UP"] = True
    player.in_water = False
    player.update(ctrl_up, colosseum, world, audio)
    assert world.master_door_unlocked is True and player.has_master_key is True

    # 4C: Shopkeeper Life Talisman (has_vitality_heart & persistent stock=0)
    player.eaten_count = 15
    shop = fe.ShopMenu("ELDER MOSSMANTLE", world_manager=world)
    talisman_idx = next(i for i, it in enumerate(shop.catalog) if it["id"] == "vitality_heart")
    shop.selected_index = talisman_idx
    buy_ctrl = fe.SNESController()
    buy_ctrl.just_pressed["A"] = True
    shop.handle_input(buy_ctrl, player, colosseum, audio)
    assert player.has_vitality_heart is True and player.max_hp == 6
    assert "vitality_heart" in world.shop_purchased
    shop_reopen = fe.ShopMenu("ELDER MOSSMANTLE", world_manager=world)
    assert shop_reopen.catalog[talisman_idx]["stock"] == 0, "Life Talisman stock should remain 0!"

    # 4D: SaveManager.save_to_disk -> load_from_disk -> restore_to_game round-trip
    orig_save = fe.SaveManager.SAVE_FILE
    temp_save = "test_v11_save_game.json"
    fe.SaveManager.SAVE_FILE = temp_save
    if os.path.exists(temp_save):
        os.remove(temp_save)
    try:
        player.has_abyssal_pearl = True
        player.has_falo_heart = True
        world.activated_checkpoints.add("frost_springs")
        world.destroyed_burrow_rocks["sunken_grotto"] = {(5, 10)}
        assert fe.SaveManager.save_to_disk(
            "toad_colosseum", player, world.defeated_bosses, world.visited_rooms, world
        )
        loaded = fe.SaveManager.load_from_disk()
        assert loaded is not None
        r_world, r_player = fe.SaveManager.restore_to_game(
            loaded, fe.WORLD_BLUEPRINTS, assets, enemy_anims, animations, camera, audio
        )
        assert r_world.current_room.room_id == "toad_colosseum"
        assert r_world.master_door_unlocked is True
        assert "toad_colosseum" in r_world.defeated_bosses
        assert "frost_springs" in r_world.activated_checkpoints
        assert (5, 10) in r_world.destroyed_burrow_rocks.get("sunken_grotto", set())
        assert "vitality_heart" in r_world.shop_purchased
        assert r_player.has_abyssal_pearl is True
        assert r_player.has_vitality_heart is True and r_player.max_hp == 6
        assert r_player.has_master_key is True and len(r_player.key_fragments) == 4
    finally:
        fe.SaveManager.SAVE_FILE = orig_save
        if os.path.exists(temp_save):
            os.remove(temp_save)

    # 4E: BossRushManager cross-room stage_clear_Pending safety & Builder isolation check
    orig_records = fe.BossRushManager.RECORDS_FILE
    temp_rec = "test_v11_rush_records.json"
    fe.BossRushManager.RECORDS_FILE = temp_rec
    if os.path.exists(temp_rec):
        os.remove(temp_rec)
    try:
        rush = fe.BossRushManager()
        rush.start_rush(world, player, camera, audio)
        assert world.game_mode == "BOSS_RUSH"
        boss = world.current_room.get_active_boss()
        if boss:
            boss.alive = False
        world.current_room.boss_defeated = True
        rush.update(world, player, camera, audio)
        assert rush.stage_clear_Pending is True
        # Walk into another room while stage_clear_Pending countdown runs; rush MUST still advance!
        world.warp_directly_to_room("level_1", player, camera, audio)
        for _ in range(115):
            rush.update(world, player, camera, audio)
        assert world.current_room.room_id == "hound_sanctum" and rush.stage_index == 1
    finally:
        fe.BossRushManager.RECORDS_FILE = orig_records
        if os.path.exists(temp_rec):
            os.remove(temp_rec)

    print("  + Master Key unseal, persistent Shop stock, [R] binding, BossRush & Save/Restore verified! PASS")


def test_studio_and_sprite_inspector_integration():
    print("\n[TEST 5] Verifying Level Studio (45 Brushes / 8 Themes) & Sprite Inspector Flip...")
    studio = ls.LevelStudioGUI("level_1")
    all_brushes = [item[0] for cat in ls.BRUSH_PALETTES for item in cat["items"]]
    assert len(all_brushes) >= 45, f"Expected >= 45 brushes, got {len(all_brushes)}"
    for portal_ch in ("1", "2"):
        assert portal_ch in all_brushes, f"Portal '{portal_ch}' missing from BRUSH_PALETTES"
    for theme in ("canopy", "temple", "cavern", "sanctum", "hound_palace", "ice", "volcanic", "underwater"):
        assert theme in ls.STUDIO_THEMES and theme in ls.AUTOTILE_THEME_MAP

    palette_rect, _, items, _, _ = studio._get_palette_layout()
    assert len(items) == len(all_brushes)
    assert all(r.width > 0 and r.left >= palette_rect.left for _, _, r in items)

    inspector = si.SpriteInspectorGUI(target_sprite="idle")
    total_seqs = sum(len(c["sprites"]) for c in inspector.catalog.categories.values())
    total_frames = sum(len(s["files"]) for c in inspector.catalog.categories.values() for s in c["sprites"].values())
    assert total_seqs == 50 and total_frames >= 170, f"Unexpected catalog size: {total_seqs} seqs / {total_frames} frames"

    inspector.flip_h = False
    _, normal_surf = inspector._get_displayed_frame()
    inspector.flip_h = True
    _, flipped_surf = inspector._get_displayed_frame()
    assert normal_surf.get_size() == flipped_surf.get_size()
    w, h = normal_surf.get_size()
    mismatches = sum(1 for x in range(w) for y in range(h) if normal_surf.get_at((x, y)) != flipped_surf.get_at((w - 1 - x, y)))
    assert mismatches == 0, "Flipped surface pixels did not match horizontal mirror!"
    print(f"  + Level Studio 45+ brushes/8 themes & Sprite Inspector {total_seqs}/{total_frames} catalog + flip verified! PASS")


def main():
    pygame.init()
    pygame.display.set_mode((fe.WINDOW_WIDTH, fe.WINDOW_HEIGHT))
    audio = fe.RetroAudioEngine()
    assets = fe.AssetManager()
    animations = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()

    print("=" * 72)
    print("RUNNING V11 END-TO-END PLAYTEST & BUGFIX VERIFICATION SUITE")
    print("=" * 72)

    test_all_door_transitions_and_spawns(assets, enemy_anims, animations, audio)
    test_combat_rendering_and_caching(assets, enemy_anims, animations, audio)
    test_five_boss_defeats_abyssal_pearl_and_revisit_silence(assets, enemy_anims, animations, audio)
    test_master_key_shop_controls_and_save_roundtrip(assets, enemy_anims, animations, audio)
    test_studio_and_sprite_inspector_integration()

    print("\n" + "=" * 72)
    print("ALL V11 PLAYTEST & VERIFICATION SUITES PASSED 100%!")
    print("=" * 72)


if __name__ == "__main__":
    main()
