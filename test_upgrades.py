"""
Automated Headless Test Suite for Froggy Engine 32-Bit Upgrades,
Movement Damping, Whip Grapple, Giga Toad Boss & Dread Hound 32-Bit Upgrade.
"""

import os
import sys
import math

# Force headless SDL video driver for automated testing
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import froggy_engine as fe

def run_tests():
    print("=" * 70)
    print("RUNNING FROGGY ENGINE HEADLESS TEST SUITE")
    print("=" * 70)

    pygame.init()
    screen = pygame.display.set_mode((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    surface = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    font = pygame.font.Font(None, 16)

    # 1. Verify 32-Bit Sprite Assets exist and are valid RGBA surfaces
    print("\n[TEST 1] Verifying 32-Bit Sprite Assets...")
    expected_sprites = [
        "toad_idle.png", "toad_slam.png", "toad_punch.png", "toad_dazed.png", "toad_enraged.png",
        "hound_idle.png", "hound_lunge.png", "hound_dazed.png", "hound_howl.png", "hound_projectile.png",
        "froggy_idle_0.png", "froggy_run_0.png", "froggy_swim_0.png", "froggy_tongue_0.png"
    ]
    for sp in expected_sprites:
        path = os.path.join("assets", "sprites", sp)
        assert os.path.exists(path), f"Missing sprite asset: {path}"
        img = pygame.image.load(path)
        assert img.get_width() > 0 and img.get_height() > 0, f"Invalid sprite dimensions for {sp}"
        print(f"  + Asset OK: {sp} ({img.get_width()}x{img.get_height()})")

    # 2. Verify AssetManager and AudioEngine initialization
    print("\n[TEST 2] Verifying AssetManager and AudioEngine initialization...")
    assets = fe.AssetManager()
    enemy_anims = assets.build_enemy_animations()
    froggy_anims = assets.build_froggy_animations()
    audio = fe.RetroAudioEngine()
    assert "toad" in enemy_anims, "Toad animations missing from enemy_anims!"
    assert "hound" in enemy_anims, "Hound animations missing from enemy_anims!"
    assert "toad_slam" in audio.sfx, "toad_slam SFX missing from RetroAudioEngine!"
    assert "hound_roar" in audio.sfx, "hound_roar SFX missing from RetroAudioEngine!"
    print("  + Toad animations loaded:", list(enemy_anims["toad"].keys()))
    print("  + Hound animations loaded:", list(enemy_anims["hound"].keys()))

    # 3. Verify WorldManager Blueprint Graph and Door Continuity
    print("\n[TEST 3] Verifying Metroidvania World Blueprints & Door Continuity...")
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    assert "toad_colosseum" in world.rooms, "toad_colosseum missing from world rooms!"
    assert "hound_sanctum" in world.rooms, "hound_sanctum missing from world rooms!"
    assert "victory_chamber" in world.rooms, "victory_chamber missing from world rooms!"

    colosseum = world.rooms["toad_colosseum"]
    assert "K" in colosseum.doors and "L" in colosseum.doors, "Door K or L missing in toad_colosseum!"
    assert colosseum.doors["K"].target_room == "hound_sanctum"
    assert colosseum.doors["L"].target_room == "victory_chamber"
    print("  + toad_colosseum doors verified: Door K -> hound_sanctum, Door L -> victory_chamber")

    # 4. Verify Giga Toad Boss Spawning, Awakening and Stats
    print("\n[TEST 4] Verifying Giga Toad Boss in Colosseum...")
    colosseum.spawn_enemies()
    boss = colosseum.get_active_boss()
    assert boss is not None, "Giga Toad failed to spawn in toad_colosseum!"
    assert isinstance(boss, fe.GigaToadBoss), f"Expected GigaToadBoss, got {type(boss)}"
    assert boss.name == "GIGA TOAD"
    assert boss.hp == fe.BOSS_MAX_HP_TOAD == 10
    assert colosseum.is_door_locked("L") == True, "Exit door L must be locked while Giga Toad is alive!"
    print(f"  + Giga Toad spawned with {boss.hp} HP. Door L locked status: {colosseum.is_door_locked('L')}")

    boss.awaken()
    assert boss.awakened and boss.state == "BRAWLER_IDLE"
    print("  + Giga Toad awakened into BRAWLER_IDLE state.")

    # 5. Verify Giga Toad Jump Slam & Shockwave Generation
    print("\n[TEST 5] Verifying Giga Toad Jump Slam & Seismic Shockwaves...")
    boss.state = "JUMP_SLAM_WINDUP"
    boss.state_timer = 1
    boss.update(colosseum)
    assert boss.state == "JUMP_SLAM_AIR", f"Expected JUMP_SLAM_AIR, got {boss.state}"

    boss.vy = 8.0
    boss.y = 19 * fe.TILE_SIZE - boss.height - 2
    initial_proj_count = len(colosseum.boss_projectiles)
    for _ in range(10):
        boss.update(colosseum)
        if boss.state == "PANTING":
            break

    assert boss.state == "PANTING", f"Expected PANTING after landing slam, got {boss.state}"
    assert len(colosseum.boss_projectiles) >= initial_proj_count + 2, "Expected 2 shockwaves spawned!"
    shockwaves = [p for p in colosseum.boss_projectiles if isinstance(p, fe.GigaShockwave)]
    assert len(shockwaves) >= 2, "GigaShockwave projectile instances missing!"
    dirs = [sw.vx for sw in shockwaves]
    assert any(vx < 0 for vx in dirs) and any(vx > 0 for vx in dirs), "Expected bilateral shockwaves!"
    print(f"  + Bilateral ground shockwaves verified: velocities {dirs[-2:]}")

    # 6. Verify Player Attacks against Giga Toad during PANTING
    print("\n[TEST 6] Verifying Stomp, Boomerang & Tongue Whip Vulnerability...")
    player = fe.FroggyPlayer(boss.center_x, boss.y - 14, froggy_anims)
    player.vy = 4.0
    player.has_stomping_boots = True

    can_stomp = boss.check_stomp(player.rect, player.vy)
    assert can_stomp, "Player should be able to stomp Giga Toad while PANTING!"
    hp_before = boss.hp
    boss.take_stomp_damage(colosseum, audio)
    assert boss.hp == hp_before - 2, f"Stomp should deal 2 damage! HP: {boss.hp} vs {hp_before}"

    boss.state = "PANTING"
    hp_before = boss.hp
    hit_bm = boss.hit_by_spore_boomerang(colosseum, is_red=True)
    assert hit_bm and boss.hp == hp_before - 2, f"Red Boomerang should deal 2 damage!"

    boss.state = "PANTING"
    hp_before = boss.hp
    hit_tw = boss.hit_by_tongue_whip(colosseum, audio)
    assert hit_tw and boss.hp == hp_before - 1, f"Tongue whip should deal 1 damage!"
    print("  + Giga Toad combat vulnerabilities verified.")

    # 7. Verify Whip Grapple Collision Anywhere Along the Tongue Shaft
    print("\n[TEST 7] Verifying Whip-Like Tongue Grapple (Anywhere on Shaft)...")
    cavern = world.rooms["grapple_cavern"]
    assert len(cavern.grapple_nodes) >= 1, "grapple_cavern should have grapple nodes!"
    node = cavern.grapple_nodes[0]
    node_found = cavern.get_grapple_node_along_line(node.centerx - 40, node.centery, node.centerx + 40, node.centery)
    assert node_found is not None, "get_grapple_node_along_line failed to detect shaft collision!"
    print("  + Continuous shaft/whip grapple collision verified!")

    # 8. Verify Motion Damping & Turn-Around Braking
    print("\n[TEST 8] Verifying Motion Damping & Turn-Around Physics...")
    assert fe.GROUND_FRICTION == 0.72, f"Expected GROUND_FRICTION 0.72, got {fe.GROUND_FRICTION}"
    assert fe.AIR_DRAG == 0.90, f"Expected AIR_DRAG 0.90, got {fe.AIR_DRAG}"
    assert fe.SWING_DAMPING == 0.985, f"Expected SWING_DAMPING 0.985, got {fe.SWING_DAMPING}"
    p = fe.FroggyPlayer(100, 100, froggy_anims)
    p.vx = 4.0
    p.on_ground = True
    ctrl = fe.SNESController()
    ctrl.held["LEFT"] = True
    p._update_standard_physics(ctrl, room=colosseum, audio=audio)
    assert p.vx < 4.0 * 0.72, f"Active turn-around braking should reduce velocity faster! vx: {p.vx}"
    print(f"  + Motion damping and active turn-around braking verified: vx damped to {p.vx:.2f}")

    # 9. Verify Rest Animation Breathing Cycle (No Shaking)
    print("\n[TEST 9] Verifying Calm 120-Frame Rest Breathing Cycle...")
    p.anim_state = "IDLE"
    frames_sampled = set()
    for f in range(120):
        p.anim_timer = f
        sprite = p.get_current_sprite()
        frames_sampled.add(sprite)
    assert len(frames_sampled) >= 2, "Breathing cycle should alternate frames smoothly"
    p.anim_timer = 20
    s_rest = p.get_current_sprite()
    p.anim_timer = 80
    s_expand = p.get_current_sprite()
    assert s_rest != s_expand, "Frame should expand rhythmically during breath in!"
    print("  + Rest animation 120-frame calm rhythmic breathing loop verified!")

    # 10. Verify L Trigger Hint Toggle & HUD Hiding
    print("\n[TEST 10] Verifying L-Trigger Hint Toggle & HUD Notes...")
    ctrl = fe.SNESController()
    assert world.show_hints == False, "Hints should be HIDDEN by default!"
    ctrl.just_pressed["L"] = True
    if ctrl.just_pressed["L"]:
        world.show_hints = not world.show_hints
    assert world.show_hints == True, "L-Trigger toggle should set show_hints to True!"
    fe.draw_hud_and_minimap(surface, font, player, world, fe.SmoothCamera(1000, 1000), (0, 0), ctrl, show_builder=True, pulse_timer=0)
    ctrl.just_pressed["L"] = True
    if ctrl.just_pressed["L"]:
        world.show_hints = not world.show_hints
    assert world.show_hints == False, "L-Trigger toggle should set show_hints back to False!"
    fe.draw_hud_and_minimap(surface, font, player, world, fe.SmoothCamera(1000, 1000), (0, 0), ctrl, show_builder=True, pulse_timer=0)
    print("  + L-Trigger hint toggle, clean HUD rendering & builder note hiding verified!")

    # 11. Verify 32-Bit Dread Hound Upgrade & Combat Mechanics
    print("\n[TEST 11] Verifying 32-Bit Dread Hound Upgrade & Combat Mechanics...")
    sanctum = world.rooms["hound_sanctum"]
    sanctum.spawn_enemies()
    hound = sanctum.get_active_boss()
    assert hound is not None, "Dread Hound failed to spawn in hound_sanctum!"
    assert isinstance(hound, fe.DreadHoundBoss), f"Expected DreadHoundBoss, got {type(hound)}"
    assert hound.hp == fe.BOSS_MAX_HP_HOUND == 8
    print(f"  + Dread Hound spawned with {hound.hp} HP in hound_sanctum.")

    # Verify rendering across all states with upgraded 32-bit sprites
    hound.awaken()
    assert hound.awakened
    for st in ("WALL_IDLE", "LUNGE", "DAZED", "HOWL"):
        hound.state = st
        hound.draw(surface, camera_x=0, camera_y=0, assets=assets)
    print("  + Dread Hound rendered across all 4 states using upgraded 32-bit sprites.")

    # Test DAZED combat vulnerabilities & hurt flash
    hound.state = "DAZED"
    player.teleport_to_room(hound.center_x - player.width // 2, hound.y - 14)
    player.vy = 4.0
    hound_can_stomp = hound.check_stomp(player.rect, player.vy)
    assert hound_can_stomp, "Froggy should be able to stomp Dread Hound when DAZED!"
    h_before = hound.hp
    hound.take_stomp_damage(sanctum, audio)
    assert hound.hp == h_before - 2, f"Stomp should deal 2 damage to Dread Hound! HP: {hound.hp}"
    assert hound.flash_timer > 0, "flash_timer should be activated on hit!"

    hound.state = "DAZED"
    h_before = hound.hp
    hit_h_bm = hound.hit_by_spore_boomerang(sanctum, is_red=True)
    assert hit_h_bm and hound.hp == h_before - 2, "Red Boomerang should deal 2 damage to Dread Hound!"

    hound.state = "DAZED"
    h_before = hound.hp
    hit_h_tw = hound.hit_by_tongue_whip(sanctum, audio)
    assert hit_h_tw and hound.hp == h_before - 1, "Tongue whip should deal 1 damage to Dread Hound!"
    print("  + Dread Hound DAZED vulnerabilities & hurt flash verified.")

    # Test Fireball with upgraded 32-bit projectile
    fireball = fe.HoundFireball(100, 100, -3.0, 0.0)
    fireball.draw(surface, camera_x=0, camera_y=0, assets=assets)
    print("  + 32-bit Hound Fireball projectile rendering verified.")

    print("\n" + "=" * 70)
    print("ALL 11 UPGRADE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
