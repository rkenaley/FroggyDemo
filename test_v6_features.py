"""
Automated Verification Suite for Froggy v6 Features:
  1. 16-Bit Sound Effect Sample Bank (Stereo 44.1kHz 16-bit PCM WAVs + SNES Reverb)
  2. Volcanic Magma Chasm (Overheating & Cold Waterfall Mist) & Sunken Grotto (Submarine Swimming & Air Bubble Refills)
  3. Friendly NPC Frogs (Elder Tree Frogs & Village Shopkeepers) & Comic-Style Dialogue Bubbles
  4. Arcade Boss Rush & Competitive Speedrun Split Timer (4-Boss Time-Attack + PB Records)
"""
import os
import wave
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import froggy_engine as fe


def test_16bit_sfx_sample_bank(audio):
    print("\n[TEST 1] Verifying 16-Bit PCM/WAV Sound Effect Sample Bank...")
    expected_keys = [
        "tongue", "reverb_slap", "latch", "jump", "double_jump", "wall_jump",
        "eat", "spore", "stun", "stomp", "ice_shatter", "sizzle_mist",
        "bubble_pop", "npc_talk", "shop_buy", "hurt", "door", "splash",
        "boss_roar", "hound_roar", "toad_grunt", "boss_hit", "powerup",
        "cursor", "select", "game_over", "splat"
    ]
    for key in expected_keys:
        assert key in audio.sounds, f"Missing SFX key in RetroAudioEngine: {key}"
        wav_path = os.path.join(audio.sfx_dir, f"{key}.wav")
        assert os.path.exists(wav_path), f"Missing 16-bit WAV file on disk: {wav_path}"
        with wave.open(wav_path, "rb") as wf:
            assert wf.getnchannels() == 2, f"{key}.wav must be 2-channel stereo"
            assert wf.getsampwidth() == 2, f"{key}.wav must be 16-bit PCM (2 bytes)"
            assert wf.getframerate() == 44100, f"{key}.wav must be 44100 Hz"
            assert wf.getnframes() > 1000, f"{key}.wav has too few frames"
    print(f"  + All {len(expected_keys)} stereo 16-bit 44.1kHz WAV samples verified in assets/sfx/! PASS")


def test_volcanic_and_underwater_biomes(world, player, controller, audio):
    print("\n[TEST 2] Verifying Volcanic Magma Chasm & Sunken Grotto Biomes...")
    assert "volcanic_chasm" in world.rooms, "Missing volcanic_chasm room"
    assert "sunken_grotto" in world.rooms, "Missing sunken_grotto room"

    # A. Test Volcanic Magma Chasm overheating & Cold Waterfall Mist cooling
    v_room = world.rooms["volcanic_chasm"]
    assert v_room.theme == "volcanic"
    assert len(v_room.waterfall_mists) > 0, "volcanic_chasm must have cold waterfall mist tiles ('c')"
    world.current_room = v_room

    # Place Froggy in dry volcanic air away from waterfall mist
    player.teleport_to_room(32, 32)
    player.body_temp = 100.0
    for _ in range(30):
        player.update(controller, v_room, world, audio)
    assert player.body_temp > 103.0, f"Expected volcanic heat to raise body_temp above 100, got {player.body_temp}"
    print(f"  + Volcanic heat raised Froggy's body_temp from 100.0 to {player.body_temp:.1f}%! PASS")

    # Move Froggy into Cold Waterfall Mist ('c') and verify cooling back toward 100.0
    mist_rect = v_room.waterfall_mists[0]
    player.teleport_to_room(mist_rect.x, mist_rect.y)
    player.body_temp = 175.0
    for _ in range(40):
        player.update(controller, v_room, world, audio)
    assert player.body_temp < 135.0, f"Expected cold waterfall mist to cool Froggy, got {player.body_temp}"
    print(f"  + Cold Waterfall Mist cooled Froggy from 175.0% down to {player.body_temp:.1f}%! PASS")

    # Verify overheat damage at 200.0%
    player.teleport_to_room(32, 32)
    player.hp = 5
    player.body_temp = 199.9
    player.overheat_timer = 74
    player.update(controller, v_room, world, audio)
    assert player.hp == 4, "Expected 1 HP heatstroke damage at 200% overheat"
    print("  + Overheat damage at 200.0% temperature verified! PASS")

    # B. Test Sunken Grotto submarine swimming & Air Bubble Refill Spots ('o')
    u_room = world.rooms["sunken_grotto"]
    assert u_room.theme == "underwater"
    assert len(u_room.bubble_vents) > 0, "sunken_grotto must have submarine air bubble vents ('o')"
    world.current_room = u_room

    # Place Froggy in deep water away from bubble vents
    water_rect = [w for w in u_room.water_hazards if not any(w.colliderect(v.inflate(16, 16)) for v in u_room.bubble_vents)][0]
    player.teleport_to_room(water_rect.x, water_rect.y)
    player.oxygen = 100.0
    for _ in range(40):
        player.update(controller, u_room, world, audio)
    assert player.in_water, "Expected Froggy to be submerged in sunken_grotto"
    assert player.oxygen < 96.0, f"Expected submarine oxygen to drain, got {player.oxygen}"
    print(f"  + Submarine swimming drained oxygen from 100.0% to {player.oxygen:.1f}%! PASS")

    # Swim onto an Air Bubble Refill Spot ('o') and verify instant refill to 100.0%
    vent_rect = u_room.bubble_vents[0]
    player.teleport_to_room(vent_rect.x, vent_rect.y)
    player.oxygen = 25.0
    player.update(controller, u_room, world, audio)
    assert player.oxygen == 100.0, f"Expected air bubble vent to refill oxygen to 100%, got {player.oxygen}"
    print("  + Submarine Air Bubble Vent refilled oxygen from 25.0% -> 100.0%! PASS")


def test_friendly_npcs_and_dialogue_bubbles(world, player, audio):
    print("\n[TEST 3] Verifying Friendly NPC Frogs & Comic-Style Dialogue Bubbles...")
    canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    font = pygame.font.SysFont("monospace", 10, bold=True)

    # Check Elder Tree Frog in level_1
    r1 = world.rooms["level_1"]
    elders = [n for n in r1.npcs if n.kind == "elder"]
    assert len(elders) >= 1, "Expected Elder Tree Frog NPC in level_1"
    elder = elders[0]

    # Move Froggy next to Elder Mossbeard
    player.teleport_to_room(elder.x, elder.y)
    for _ in range(25):
        elder.update(player, r1, audio)
    assert elder.player_near, "Expected elder.player_near to be True when Froggy stands beside him"
    assert elder.revealed_chars > 0, "Expected typewriter reveal to advance"
    elder.draw(canvas, 0, 0, world.assets)
    elder.draw_dialogue_bubble(canvas, font, 0, 0)
    print(f"  + Elder Tree Frog ('{elder.name}') comic dialogue bubble & typewriter verified! PASS")

    # Check Village Shopkeeper in entrance_hall
    r2 = world.rooms["entrance_hall"]
    shops = [n for n in r2.npcs if n.kind == "shopkeeper"]
    assert len(shops) >= 1, "Expected Village Shopkeeper NPC in entrance_hall"
    shop = shops[0]

    player.teleport_to_room(shop.x, shop.y)
    player.hp = 3
    player.eaten_count = 3
    shop.update(player, r2, audio)
    # First interact finishes typewriter reveal; second interact opens the interactive ShopMenu!
    shop.interact(player, r2, audio)
    shop.interact(player, r2, audio)
    assert world.active_shop is not None, "Expected ShopMenu to open upon interacting with shopkeeper"
    controller = fe.SNESController()
    controller.just_pressed["A"] = True
    world.active_shop.handle_input(controller, player, r2, audio)
    assert player.consumables.get("heart_nectar", 0) >= 1, "Expected Heart Nectar in pouch"
    player.use_consumable("heart_nectar", room=r2, audio=audio)
    assert player.hp == 5, f"Expected consuming Heart Nectar to heal Froggy to 5 HP, got {player.hp}"
    assert player.eaten_count == 0, f"Expected shop purchase to cost 3 eaten bugs, got {player.eaten_count}"
    shop.draw(canvas, 0, 0, world.assets)
    shop.draw_dialogue_bubble(canvas, font, 0, 0)
    world.active_shop.draw(canvas, font, font, player, world.assets)
    print(f"  + Village Shopkeeper ('{shop.name}') bug trade & healing tonic verified! PASS")


def test_arcade_boss_rush_and_split_timer(world, player, camera, audio):
    print("\n[TEST 4] Verifying Arcade Boss Rush & Competitive Speedrun Split Timer...")
    canvas = pygame.Surface((fe.INTERNAL_WIDTH, fe.INTERNAL_HEIGHT))
    font = pygame.font.SysFont("monospace", 10, bold=True)

    expected_rooms = ["boss_sanctum", "hound_sanctum", "toad_colosseum", "falo_arena", "shark_sanctum"]
    orig_records = fe.BossRushManager.RECORDS_FILE
    temp_records = "test_v6_boss_rush_records.json"
    fe.BossRushManager.RECORDS_FILE = temp_records
    if os.path.exists(temp_records):
        os.remove(temp_records)
    try:
        rush = fe.BossRushManager()
        rush.start_rush(world, player, camera, audio)
        assert rush.active and not rush.completed
        assert world.current_room.room_id == "boss_sanctum"
        assert player.has_stomping_boots and player.has_red_boomerang

        for idx, expected_r in enumerate(expected_rooms):
            assert world.current_room.room_id == expected_r, f"Stage {idx+1} room mismatch: {world.current_room.room_id}"
            for _ in range(30):
                rush.update(world, player, camera, audio)
            # Defeat current boss
            boss = world.current_room.get_active_boss()
            if boss:
                boss.alive = False
            world.current_room.boss_defeated = True
            rush.update(world, player, camera, audio)
            rush.draw_split_hud(canvas, font)

            if idx < len(expected_rooms) - 1:
                assert rush.stage_clear_Pending
                for _ in range(115):
                    rush.update(world, player, camera, audio)

        assert rush.completed, "Expected Boss Rush to mark completed after defeating all 5 bosses!"
        assert len(rush.timer.splits) == 5, f"Expected 5 recorded boss splits, got {len(rush.timer.splits)}"
        assert rush.best_total_frames is not None and rush.best_total_frames > 0
        assert os.path.exists(temp_records), "Expected temporary boss rush records file to be saved"
        formatted = fe.SpeedrunTimer.format_frames(rush.timer.total_frames)
        print(f"  + All 5 Boss Rush stages cleared! Final Split Time: {formatted} (Verified records save) PASS")
    finally:
        fe.BossRushManager.RECORDS_FILE = orig_records
        if os.path.exists(temp_records):
            os.remove(temp_records)


def main():
    pygame.init()
    pygame.display.set_mode((fe.WINDOW_WIDTH, fe.WINDOW_HEIGHT))
    audio = fe.RetroAudioEngine()
    assets = fe.AssetManager()
    controller = fe.SNESController()
    anims = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()
    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    player = fe.FroggyPlayer(64, 64, anims)
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)

    test_16bit_sfx_sample_bank(audio)
    test_volcanic_and_underwater_biomes(world, player, controller, audio)
    test_friendly_npcs_and_dialogue_bubbles(world, player, audio)
    test_arcade_boss_rush_and_split_timer(world, player, camera, audio)

    print("\n" + "=" * 68)
    print("ALL V6 FEATURE VERIFICATION TESTS PASSED 100%!")
    print("=" * 68)
    pygame.quit()


if __name__ == "__main__":
    main()
