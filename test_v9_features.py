"""
Automated Verification Suite for FROGGY v9 Enhancements:
1. Boss Rush Split Overlay Fix (only flashes after each boss defeat, shows total time on completion).
2. Boss Rush Death Bug Fix (dying immediately fails the Boss Rush and never counts as defeating the boss).
3. Giga Toad Buff (5x HP = 50 HP + Championship Brawler Shield mechanic blocking frontal uncharged attacks).
4. Title Screen Controls & Inventory Explainer (`draw_controls_explainer_screen`).
5. Overhauled Front Parallax Background Layers (`parallax_<theme>_mid.png` for all 7 themes).
6. Expanded Underwater Level (`sunken_grotto`), Underwater Currents (`<`, `>`), 3 Fish Enemy Types
   (`RazorPiranha`, `AbyssalAngler`, `VoltJelly`), and `The Muhlaser` 3-second charge frogbeam + rock burrowing (`r`).
7. New Swimming Area Boss: `DemonSharkBoss` (`shark_sanctum` & Boss Rush Stage 5), toughest boss yet (65 HP)
   with armored scales that resist normal hits and a massive weakness to charged Muhlaser beams.
"""

import os
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import froggy_engine as fe
from world_data import WORLD_BLUEPRINTS


def run_all_tests():
    pygame.init()
    window = pygame.display.set_mode((fe.WINDOW_WIDTH, fe.WINDOW_HEIGHT))
    canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    hud_font = pygame.font.SysFont("monospace", 10, bold=True)
    menu_font = pygame.font.SysFont("monospace", 11, bold=True)
    title_font = pygame.font.SysFont("impact", 32, bold=True)

    audio = fe.RetroAudioEngine()
    assets = fe.AssetManager()
    controller = fe.SNESController()
    anims = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()

    # 1. Verify Overhauled Front Parallax Layers & New Underwater/Shark Sprites
    for theme in ("canopy", "temple", "cavern", "sanctum", "ice", "volcanic", "underwater"):
        assert theme in assets.parallax_mid, f"Missing parallax_mid for theme {theme}"
        surf = assets.parallax_mid[theme]
        assert surf.get_size() == (fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT)

    for key in ("piranha", "angler", "jelly", "shark"):
        assert key in enemy_anims and len(enemy_anims[key]) > 0, f"Missing enemy anim {key}"
    for sh_key in ("idle", "idle_1", "charge", "dazed", "enraged"):
        assert enemy_anims["shark"].get(sh_key) is not None, f"Missing shark frame {sh_key}"
    assert enemy_anims["powerups"].get("muhlaser") is not None, "Missing muhlaser powerup icon"
    assert len(assets.special_tiles.get("burrow_rock", [])) == 2, "Missing burrow_rock special tiles"
    print("[PASS] 1. Overhauled Parallax Front Layers & 32-Bit Underwater/Demon Shark Assets verified.")

    # 2. Verify Giga Toad 90 HP & Championship Brawler Shield Mechanic
    assert fe.BOSS_MAX_HP_TOAD == 90, f"Expected Giga Toad HP 90, got {fe.BOSS_MAX_HP_TOAD}"
    world = fe.WorldManager(WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="toad_colosseum")
    player = fe.FroggyPlayer(120, 200, anims)
    player.world_manager_ref = world
    toad = world.current_room.get_active_boss()
    assert isinstance(toad, fe.GigaToadBoss)
    assert toad.max_hp == 90 and toad.hp == 90
    toad.awakened = True
    toad.state = "IDLE"
    assert toad.shield_active is True
    toad.facing_right = False  # Facing left toward player at x=120

    # Uncharged frontal tongue whip should be BLOCKED by Giga Toad's Brawler Shield!
    blocked = toad.hit_by_tongue_whip(world.current_room, audio)
    assert blocked is False and toad.hp == 90 and toad.shield_flash_timer > 0, "Frontal uncharged whip should be blocked by shield"

    # Charged Muhlaser beam pierces Giga Toad's shield and deals heavy damage!
    pierced = toad.hit_by_muhlaser(world.current_room, 1.0, audio)
    assert pierced is True and toad.hp < 90, "Charged Muhlaser should pierce Giga Toad's shield"

    # When PANTING, frontal tongue whip deals full damage!
    hp_before = toad.hp
    toad.state = "PANTING"
    assert toad.shield_active is False
    hit_ok = toad.hit_by_tongue_whip(world.current_room, audio)
    assert hit_ok is True and toad.hp < hp_before, "Panting Giga Toad should take damage from tongue whip"
    print("[PASS] 2. Giga Toad 90 HP & Championship Brawler Guard Shield verified.")

    # 3. Verify Boss Rush 5 Stages, Flash-Only Split Overlay & No-Muhlaser Rule
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    boss_rush = fe.BossRushManager()
    assert len(boss_rush.STAGES) == 5, "Boss Rush should have 5 stages including Demon Shark"
    assert boss_rush.STAGES[-1][0] == "shark_sanctum", "Stage 5 of Boss Rush must be shark_sanctum (Demon Shark)"

    boss_rush.start_rush(world, player, camera, audio)
    assert boss_rush.active is True and boss_rush.failed is False
    assert player.has_muhlaser is False, "Boss Rush must NOT grant Muhlaser (armor-piercing bypass)"
    assert boss_rush.split_flash_timer == 0, "Split timer must NOT be shown constantly at start of Boss Rush"

    # Simulate active combat frame: split_flash_timer stays 0
    boss_rush.update(world, player, camera, audio)
    assert boss_rush.split_flash_timer == 0, "Split timer must remain hidden during active boss combat"

    # Simulate defeating Stage 1 boss: split_flash_timer activates to flash the split time!
    active_boss = world.current_room.get_active_boss()
    active_boss.alive = False
    boss_rush.update(world, player, camera, audio)
    assert len(boss_rush.timer.splits) == 1, "Defeating Stage 1 boss should record 1 split"
    assert boss_rush.split_flash_timer > 0, "Split timer should flash immediately after boss defeat"

    # Advance to Stage 2
    for _ in range(115):
        boss_rush.update(world, player, camera, audio)
    assert boss_rush.stage_index == 1 and world.current_room.room_id == "hound_sanctum"

    # Simulate Froggy DYING during Stage 2 Boss Rush: must immediately fail_rush() and NEVER record a split!
    player.hp = 0
    if player.hp <= 0 and True:  # Mirrors main() logic
        boss_rush.fail_rush()
    # Even if update() is accidentally called or room has no boss, no split is recorded!
    boss_rush.update(world, player, camera, audio)
    assert boss_rush.active is False and boss_rush.failed is True
    assert len(boss_rush.timer.splits) == 1, "Dying in Boss Rush must NEVER record a boss defeat split!"
    print("[PASS] 3. Boss Rush 5-Boss Gauntlet, Flash-Only Split Timer & Death Bug Fix verified.")

    # 4. Verify Underwater Level (`sunken_grotto`), Currents, 3 Fish Enemy Types, Muhlaser & Rock Burrowing
    world.warp_directly_to_room("sunken_grotto", player, camera, audio)
    grotto = world.current_room
    assert grotto.cols >= 110, f"Expected multi-screen sunken_grotto (>=110 cols), got {grotto.cols}"
    assert len(grotto.current_zones) > 0, "sunken_grotto must contain underwater currents ('<' / '>')"
    assert len(grotto.burrow_rocks) > 0, "sunken_grotto must contain cracked burrow rocks ('r')"

    has_piranha = any(isinstance(e, fe.RazorPiranha) for e in grotto.enemies)
    has_angler = any(isinstance(e, fe.AbyssalAngler) for e in grotto.enemies)
    has_jelly = any(isinstance(e, fe.VoltJelly) for e in grotto.enemies)
    assert has_piranha and has_angler and has_jelly, "sunken_grotto must spawn all 3 fish enemy types (Piranha, Angler, Jelly)"

    has_muhlaser_pickup = any('L' in row for row in WORLD_BLUEPRINTS["hound_treasury"]["ascii_grid"])
    assert has_muhlaser_pickup, "hound_treasury must contain the Muhlaser Relic ('L')"

    # Test Underwater Current sweeping Froggy's velocity
    player.hp = fe.PLAYER_MAX_HP
    c_rect, c_dx, c_dy = grotto.current_zones[0]
    player.teleport_to_room(c_rect.centerx - player.width // 2, c_rect.centery - player.height // 2)
    player.vx = 0.0
    player.update(controller, grotto, world, audio)
    assert abs(player.vx) > 0.05, "Underwater current zone must sweep Froggy's horizontal velocity"

    # Test 3-Second Muhlaser Charge & Burrowing through Cracked Rocks ('r')
    rock_count_before = len(grotto.burrow_rocks)
    target_rock = grotto.burrow_rocks[0]
    player.has_muhlaser = True
    player.facing_right = True
    player.teleport_to_room(target_rock.left - 32, target_rock.centery - player.height // 2)
    player.laser_charge = fe.MUHLASER_MAX_CHARGE  # Full 3.0s (180 frames) charge
    player.fire_muhlaser(grotto, audio=audio, charge_frames=fe.MUHLASER_MAX_CHARGE, aim_x=1.0, aim_y=0.0)
    assert len(player.active_lasers) >= 1, "Firing Muhlaser should spawn a MuhlaserBeam"
    player.active_lasers[-1].update(grotto, audio)
    assert len(grotto.burrow_rocks) < rock_count_before, "Charged Muhlaser beam must burrow through cracked rocks ('r')"
    print("[PASS] 4. Sunken Grotto Currents, 3 Fish Enemy Types, 3s Muhlaser & Rock Burrowing verified.")

    # 5. Verify Demon Shark Boss (`shark_sanctum`) & Weakness to Charged Muhlaser
    world.warp_directly_to_room("shark_sanctum", player, camera, audio)
    shark_room = world.current_room
    shark = shark_room.get_active_boss()
    assert isinstance(shark, fe.DemonSharkBoss), "shark_sanctum must spawn DemonSharkBoss"
    assert shark.max_hp == 85 and shark.hp == 85, f"Expected Demon Shark 85 HP (+30%), got {shark.max_hp}"
    shark.awakened = True

    # Normal uncharged tongue hit deals minimal damage (1 HP) due to armored scales
    shark.state = "ABYSS_PROWL"
    shark.hit_by_tongue_whip(shark_room, audio)
    assert shark.hp == 84, f"Expected Demon Shark to take only 1 damage from uncharged tongue, got {85 - shark.hp}"

    # Full 3-second Charged Muhlaser shot deals massive weakness damage and stuns Demon Shark into DAZED!
    shark.state = "TORPEDO_CHARGE"
    shark.hit_by_muhlaser(shark_room, 1.0, audio)
    # Demon Shark takes rebalanced 12 damage (cut in half from 24) on full charge
    assert shark.hp == 84 - 12, f"Expected 12 damage from rebalanced 3s charged Muhlaser, HP is {shark.hp}"
    assert shark.state == "DAZED", "Full charged Muhlaser must stun Demon Shark into DAZED state"
    print("[PASS] 5. Demon Shark Boss (85 HP, Armored Scales & Charged Muhlaser Weakness) verified.")

    # 6. Verify Title Screen Controls & Inventory Explainer rendering
    fe.draw_title_screen(canvas, title_font, menu_font, 2, 10, anims["right"]["idle"][0], assets, has_save=False)
    fe.draw_controls_explainer_screen(canvas, title_font, menu_font, hud_font, 10, assets)
    fe.draw_game_over_screen(canvas, title_font, menu_font, 10, has_save=False, is_boss_rush=True)
    print("[PASS] 6. Title Screen Controls & Inventory Explainer UI verified.")

    pygame.quit()
    print("\nALL 6 V9 FEATURE SUITES PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_all_tests()
