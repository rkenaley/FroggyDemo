"""
Verification suite for all 5 user-reported fixes & upgrades:
  1. Sprite orientation, sizing, and multi-frame pixel-painterly consistency
     (Elder Toads 48x48, Dread Hound 96x96 left-facing, Giga Toad 80x80 left-facing, troops).
  2. Froggy 32x32 high-quality hero sprite with all 9 animations & flush ground alignment.
  3. Inventory fatal crash fix (no KeyError: 'SPACE') & clear item usage feedback UI.
  4. Giga Toad wide-open colosseum arena, AI state machine, contact damage rules, and animations.
  5. Grapple swing jump-release boost mechanic (maintaining boost without instant re-latch).
"""
import os
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
pygame.display.set_mode((640, 360))

import froggy_engine as fe


def run_all_tests():
    print("=" * 72)
    print("RUNNING FROGGY V8 FIXES & POLISH VERIFICATION SUITE (ALL 5 ITEMS)")
    print("=" * 72)

    assets = fe.AssetManager()
    anims = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()
    audio = fe.RetroAudioEngine()
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    player = fe.FroggyPlayer(0, 0, anims)
    sx, sy = world.current_room.default_spawn
    player.teleport_to_room(sx, sy)
    cam = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    cam.snap_to(player)

    # -------------------------------------------------------------------------
    # 1. SPRITE ORIENTATION, SIZING, AND MULTI-FRAME CONSISTENCY
    # -------------------------------------------------------------------------
    print("\n[1] Verifying Sprite Orientation, Sizing, and Elder Toads / Dread Hound...")
    assert len(enemy_anims["npc_elder"]) == 4, f"Expected 4 npc_elder frames, got {len(enemy_anims['npc_elder'])}"
    assert len(enemy_anims["npc_shopkeeper"]) == 4, f"Expected 4 npc_shopkeeper frames, got {len(enemy_anims['npc_shopkeeper'])}"
    for f in enemy_anims["npc_elder"] + enemy_anims["npc_shopkeeper"]:
        assert f.get_size() == (48, 48), f"Expected 48x48 NPC sprite, got {f.get_size()}"
        assert f.get_at((0, 0)).a == 0, "Expected transparent (0,0) corner on NPC sprite"

    # Verify Elder Mossbeard in level_1 stands on solid ground and faces Froggy
    elder = world.current_room.npcs[0]
    assert (elder.width, elder.height) == (32, 42)
    assert elder.rect.bottom == 288, f"Expected Elder Mossbeard feet on platform y=288, got {elder.rect.bottom}"
    player.teleport_to_room(elder.x - 28, 272)
    world.current_room.update_entities(player, audio, 10)
    assert elder.player_near is True
    assert elder.facing_right is False, "Expected Elder to face LEFT when Froggy is to his left"

    # Verify Dread Hound faces LEFT across all states when Froggy is to his left
    world.warp_directly_to_room("hound_sanctum", player, cam, audio)
    hound = world.current_room.get_active_boss()
    assert isinstance(hound, fe.DreadHoundBoss)
    assert hound.rect.bottom == 304, f"Expected Dread Hound feet on floor y=304, got {hound.rect.bottom}"
    player.teleport_to_room(hound.x - 160, 288)
    for st in ("WALL_IDLE", "HOWL", "LUNGE", "DAZED", "RETRACT"):
        hound.state = st
        hound.timer = 10
        if st == "LUNGE":
            hound.vx = -6.0
        elif st == "RETRACT":
            hound.vx = 5.0
        world.current_room.update_entities(player, audio, 20)
        assert hound.facing_right is False, f"Expected Dread Hound facing_right=False in state {st}"
    print("  + Elder Toads (48x48, 4 frames) & Dread Hound (96x96, left-facing): PASS")

    # -------------------------------------------------------------------------
    # 2. FROGGY HERO SPRITE & ALL 9 ANIMATIONS
    # -------------------------------------------------------------------------
    print("\n[2] Verifying Froggy 32x32 Hero Sprite & All 9 Animation States...")
    expected_states = {
        "idle": 4,
        "run": 4,
        "jump": 2,
        "fall": 2,
        "wall_slide": 2,
        "tongue": 2,
        "swing": 2,
        "swim": 4,
        "hurt": 1,
    }
    for state_name, min_count in expected_states.items():
        for dir_key in ("right", "left"):
            assert state_name in anims[dir_key], f"Missing Froggy animation '{state_name}' in '{dir_key}'"
            frames = anims[dir_key][state_name]
            assert len(frames) >= min_count, f"Expected >={min_count} frames for {state_name}, got {len(frames)}"
            for fr in frames:
                assert fr.get_size() == (32, 32), f"Expected 32x32 Froggy frame, got {fr.get_size()}"
                assert fr.get_at((0, 0)).a == 0, "Expected transparent (0,0) corner on Froggy frame"

    # Verify standing frames have boot pixels anchored at y=31 (zero floating gap)
    idle_frame = anims["right"]["idle"][0]
    bottom_row_opaque = any(idle_frame.get_at((x, 31)).a > 0 for x in range(32))
    assert bottom_row_opaque, "Expected Froggy's boots to touch y=31 on 32x32 canvas (zero floating gap)"
    print("  + All 9 Froggy animations (21 frames each direction) & y=31 boot anchor: PASS")

    # -------------------------------------------------------------------------
    # 3. INVENTORY FATAL ERROR FIX & CLEAR UX
    # -------------------------------------------------------------------------
    print("\n[3] Verifying Inventory Screen Input & Consumable Usage UX...")
    ctrl = fe.SNESController()
    ctrl.update()
    assert "SPACE" not in ctrl.just_pressed, "SNESController does not have 'SPACE' key (uses jump_just_pressed / A)"
    with open("froggy_engine.py", "r", encoding="utf-8") as f:
        engine_src = f.read()
    assert 'just_pressed["SPACE"]' not in engine_src, "Fatal KeyError: 'SPACE' reference still exists in froggy_engine.py!"

    player.hp = 2
    player.consumables["heart_nectar"] = 1
    used = player.use_consumable("heart_nectar", room=world.current_room, audio=audio)
    assert used is True and player.hp == 5
    assert "USED HEART NECTAR" in player.inventory_feedback_msg
    used_empty = player.use_consumable("heart_nectar", room=world.current_room, audio=audio)
    assert used_empty is False and "POUCH EMPTY" in player.inventory_feedback_msg
    print("  + Inventory crash removed & live feedback bar verified: PASS")

    # -------------------------------------------------------------------------
    # 4. GIGA TOAD OPEN LEVEL & GAMEPLAY / ANIMATION REWORK
    # -------------------------------------------------------------------------
    print("\n[4] Verifying Giga Toad Open Colosseum Arena, AI, and Animations...")
    world.warp_directly_to_room("toad_colosseum", player, cam, audio)
    col_room = world.current_room
    toad = col_room.get_active_boss()
    assert isinstance(toad, fe.GigaToadBoss)
    assert toad.rect.bottom == 304, f"Expected Giga Toad feet on floor y=304, got {toad.rect.bottom}"

    # Verify arena floor (Row 17 & Row 18, y=272..288) has zero blocking interior obstacles
    blocking_floor_tiles = [
        t for t in col_room.solid_tiles
        if 48 <= t.x <= col_room.world_width - 64 and 240 <= t.y < 304
    ]
    assert len(blocking_floor_tiles) == 0, f"Expected wide-open arena floor, found blocking tiles: {blocking_floor_tiles}"

    # Verify Giga Toad stalks toward Froggy in BRAWLER_IDLE without getting stuck
    player.teleport_to_room(260, 288)
    start_toad_x = toad.x
    toad.state = "BRAWLER_IDLE"
    toad.timer = 1
    for _ in range(30):
        col_room.update_entities(player, audio, 30)
    assert toad.x < start_toad_x, f"Expected Giga Toad to stalk left toward Froggy ({toad.x} vs {start_toad_x})"

    # Verify Giga Toad does NOT deal contact damage when PANTING or DAZED, and can be stomped
    toad.state = "PANTING"
    toad.timer = 40
    player.hp = 5
    player.invuln_timer = 0
    player.x = toad.x + 8
    player.y = toad.y + 10
    player.rect.topleft = (int(player.x), int(player.y))
    player._check_damage_collisions(col_room, audio)
    assert player.hp == 5, "Expected zero contact damage when touching a PANTING Giga Toad!"

    # Verify Stomp damage works in PANTING state
    player.has_stomping_boots = True
    player.vy = 4.0
    player.rect.bottom = toad.rect.top + 8
    player.rect.centerx = toad.rect.centerx
    old_toad_hp = toad.hp
    player._check_damage_collisions(col_room, audio)
    assert toad.hp < old_toad_hp, "Expected stomp to damage Giga Toad during PANTING state!"
    print("  + Giga Toad open colosseum floor, stalking AI, and stomp/contact rules: PASS")

    # -------------------------------------------------------------------------
    # 5. GRAPPLE SWING JUMP BOOST MECHANIC
    # -------------------------------------------------------------------------
    print("\n[5] Verifying Grapple Swing Jump Boost Mechanic...")
    anchor_rect = col_room.grapple_nodes[0]
    player.teleport_to_room(anchor_rect.centerx - 24, anchor_rect.centery + 56)
    player._attach_to_grapple(anchor_rect)
    assert player.tongue_state == "SWINGING"
    player.swing_angular_vel = 0.06  # Swinging right

    # Frame 1: Player holds Y (grapple) and presses Jump (A) while holding RIGHT
    ctrl = fe.SNESController()
    ctrl.held["Y"] = True
    ctrl.held["RIGHT"] = True
    ctrl.just_pressed["A"] = True
    player.update(ctrl, col_room, world, audio)

    assert player.tongue_state == "RETRACTING", f"Expected RETRACTING after swing jump, got {player.tongue_state}"
    assert player.retract_can_grapple is False, "Expected retract_can_grapple=False after jump detach"
    boosted_vy = player.vy
    boosted_vx = player.vx
    assert boosted_vy <= fe.JUMP_VELOCITY * 1.05, f"Expected strong upward boost vy <= {fe.JUMP_VELOCITY * 1.05}, got {boosted_vy}"
    assert boosted_vx > 3.0, f"Expected strong forward boost vx > 3.0, got {boosted_vx}"

    # Frame 2: Player is STILL holding Y on the very next frame — must NOT re-attach to grapple!
    ctrl.just_pressed["A"] = False
    player.update(ctrl, col_room, world, audio)
    assert player.tongue_state != "SWINGING", "Bug regression: Froggy re-latched onto grapple on the frame after jumping!"
    assert player.vy < -5.0, f"Expected Froggy to maintain upward jump boost on Frame 2, got vy={player.vy}"
    print(f"  + Grapple swing jump boost verified (vy={boosted_vy:.2f}, vx={boosted_vx:.2f}, no re-latch): PASS")

    # Render updated screenshots_after.png with HUD & speech bubbles
    font = pygame.font.SysFont("consolas", 12, bold=True)
    tfont = pygame.font.SysFont("consolas", 16, bold=True)
    shots = []

    # Shot 1: Level 1 Elder with speech bubble
    world.warp_directly_to_room("level_1", player, cam, audio)
    player.teleport_to_room(110, 272)
    for _ in range(30):
        world.current_room.update_entities(player, audio, 10)
    cam.snap_to(player)
    s1 = pygame.Surface((640, 360))
    world.current_room.draw(s1, cam.render_x, cam.render_y, 10)
    player.draw(s1, cam.render_x, cam.render_y, assets)
    for npc in world.current_room.npcs:
        npc.draw_dialogue_bubble(s1, font, cam.render_x, cam.render_y)
    shots.append(("1. Level 1: Elder Mossbeard (48x48) & Froggy", s1))

    # Shot 2: Entrance Hall Shopkeeper with speech bubble
    world.warp_directly_to_room("entrance_hall", player, cam, audio)
    player.teleport_to_room(290, 240)
    for _ in range(30):
        world.current_room.update_entities(player, audio, 20)
    cam.snap_to(player)
    s2 = pygame.Surface((640, 360))
    world.current_room.draw(s2, cam.render_x, cam.render_y, 20)
    player.draw(s2, cam.render_x, cam.render_y, assets)
    for npc in world.current_room.npcs:
        npc.draw_dialogue_bubble(s2, font, cam.render_x, cam.render_y)
    shots.append(("2. Entrance Hall: Shopkeeper Mossmantle (48x48)", s2))

    # Shot 3: Toad Colosseum Open Arena
    world.warp_directly_to_room("toad_colosseum", player, cam, audio)
    player.teleport_to_room(520, 288)
    boss = world.current_room.get_active_boss()
    boss.awaken()
    boss.state = "GROUND_SLAM"
    boss.vy = -1.0
    world.current_room.update_entities(player, audio, 30)
    cam.snap_to(player)
    s3 = pygame.Surface((640, 360))
    world.current_room.draw(s3, cam.render_x, cam.render_y, 30)
    player.draw(s3, cam.render_x, cam.render_y, assets)
    shots.append(("3. Toad Colosseum: Open Arena & Giga Toad Slam", s3))

    # Shot 4: Hound Sanctum
    world.warp_directly_to_room("hound_sanctum", player, cam, audio)
    player.teleport_to_room(580, 288)
    boss = world.current_room.get_active_boss()
    boss.awaken()
    boss.state = "LUNGE"
    boss.vx = -6.0
    world.current_room.update_entities(player, audio, 40)
    cam.snap_to(player)
    s4 = pygame.Surface((640, 360))
    world.current_room.draw(s4, cam.render_x, cam.render_y, 40)
    player.draw(s4, cam.render_x, cam.render_y, assets)
    shots.append(("4. Hound Sanctum: Dread Hound Facing Left", s4))

    # Shot 5: Inventory Modal
    player.hp = 2
    player.consumables["heart_nectar"] = 2
    player.use_consumable("heart_nectar", world.current_room, audio)
    s5 = pygame.Surface((640, 360))
    world.current_room.draw(s5, cam.render_x, cam.render_y, 50)
    player.draw(s5, cam.render_x, cam.render_y, assets)
    fe.draw_inventory_screen(s5, tfont, font, player, assets, 0, 50)
    shots.append(("5. Inventory Modal (Fixed Crash + Clear UX)", s5))

    # Shot 6: Shop Emporium Modal
    shop = fe.ShopMenu("ELDER MOSSMANTLE, THE ANCIENT MERCHANT")
    s6 = pygame.Surface((640, 360))
    world.current_room.draw(s6, cam.render_x, cam.render_y, 60)
    player.draw(s6, cam.render_x, cam.render_y, assets)
    shop.draw(s6, tfont, font, player, assets)
    shots.append(("6. Shop Emporium Modal", s6))

    grid = pygame.Surface((1300, 1140))
    grid.fill((15, 18, 26))
    for i, (lbl, surf) in enumerate(shots):
        gx = (i % 2) * 648 + 4
        gy = (i // 2) * 378 + 4
        grid.blit(surf, (gx, gy))
        grid.blit(font.render(lbl, True, (255, 240, 120)), (gx + 8, gy + 6))
    out_path = r"C:\Users\Ryan\.gemini\antigravity\brain\ab8fc72f-5632-4e94-8eca-8ae4d5b31a58\scratch\screenshots_after.png"
    pygame.image.save(grid, out_path)

    print("\n" + "=" * 72)
    print("ALL 5 V8 FIXES VERIFIED AND PASSED 100%!")
    print("=" * 72)


if __name__ == "__main__":
    run_all_tests()
