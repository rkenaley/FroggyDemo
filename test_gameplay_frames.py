import os
import asyncio
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import froggy_engine as fe

async def test_loop():
    pygame.init()
    window = pygame.display.set_mode((1280, 720))
    snes_canvas = pygame.Surface((640, 360))

    audio = fe.RetroAudioEngine()
    assets = fe.AssetManager()
    controller = fe.SNESController()
    animations = assets.build_froggy_animations()
    enemy_anims = assets.build_enemy_animations()

    world = fe.WorldManager(fe.WORLD_BLUEPRINTS, assets, enemy_anims, starting_room_id="level_1")
    player = fe.FroggyPlayer(64, 64, animations)
    camera = fe.SmoothCamera(world.current_room.world_width, world.current_room.world_height)
    camera.snap_to(player)

    hud_font = pygame.font.SysFont("monospace", 10, bold=True)
    menu_font = pygame.font.SysFont("monospace", 11, bold=True)
    title_font = pygame.font.SysFont("impact", 32, bold=True)

    print("Simulating Title Screen...")
    frog_preview = animations["right"]["idle"][0]
    fe.draw_title_screen(snes_canvas, title_font, menu_font, 0, 10, frog_preview, assets, has_save=True)

    print("Simulating 60 frames in level_1...")
    for f in range(60):
        world.current_room.update_entities(player, audio, f)
        player.update(controller, world.current_room, world, audio)
        camera.update(player)
        world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, f)
        player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
        fe.draw_hud_and_minimap(snes_canvas, hud_font, player, world, camera, (100, 100), controller, False, f)

    print("Warping to entrance_hall and ascending to frost_ascent...")
    world.warp_directly_to_room("entrance_hall", player, camera, audio)
    # Move through ceiling door U to frost_ascent
    door_u = world.current_room.doors.get("U")
    assert door_u is not None
    world.trigger_door_transition(door_u, audio)
    while world.is_transitioning:
        world.update_transition(player, camera, audio)
    assert world.current_room.room_id == "frost_ascent"
    print(f"  -> Arrived in: {world.current_room.title}")

    print("Simulating 60 frames in frost_ascent...")
    for f in range(60):
        world.current_room.update_entities(player, audio, f)
        player.update(controller, world.current_room, world, audio)
        camera.update(player)
        world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, f)
        player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
        fe.draw_hud_and_minimap(snes_canvas, hud_font, player, world, camera, (100, 100), controller, False, f)

    print("Warping to frost_springs (Hot Springs & Checkpoint)...")
    world.warp_directly_to_room("frost_springs", player, camera, audio)
    assert world.current_room.checkpoint_pos is not None
    print(f"  -> Checkpoint Totem found at: {world.current_room.checkpoint_pos}")

    print("Simulating player touching checkpoint totem...")
    cx, cy = world.current_room.checkpoint_pos
    player.x = float(cx)
    player.y = float(cy)
    player.rect.topleft = (int(player.x), int(player.y))
    world.current_room.update_entities(player, audio, 70)
    assert world.current_room.checkpoint_active == True
    assert player.hp == fe.PLAYER_MAX_HP
    assert player.body_temp == 100.0
    print("  -> Checkpoint activated, HP and warmth restored!")

    print("Warping to falo_arena (Boss Arena)...")
    world.warp_directly_to_room("falo_arena", player, camera, audio)
    assert world.current_room.get_active_boss() is not None
    boss = world.current_room.get_active_boss()
    print(f"  -> Boss detected: {boss.name}")

    print("Simulating 120 frames in falo_arena...")
    for f in range(120):
        world.current_room.update_entities(player, audio, f)
        player.update(controller, world.current_room, world, audio)
        camera.update(player)
        world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, f)
        player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
        fe.draw_hud_and_minimap(snes_canvas, hud_font, player, world, camera, (100, 100), controller, False, f)

    print("Dropping down chute Z into grapple_cavern...")
    door_z = world.current_room.doors.get("Z")
    assert door_z is not None
    # Simulate boss defeat to unlock arena chute
    world.current_room.boss_defeated = True
    world.trigger_door_transition(door_z, audio)
    while world.is_transitioning:
        world.update_transition(player, camera, audio)
    assert world.current_room.room_id == "grapple_cavern"
    print(f"  -> Arrived in: {world.current_room.title}")

    print("Simulating 60 frames in grapple_cavern...")
    for f in range(60):
        world.current_room.update_entities(player, audio, f)
        player.update(controller, world.current_room, world, audio)
        camera.update(player)
        world.current_room.draw(snes_canvas, camera.render_x, camera.render_y, f)
        player.draw(snes_canvas, camera.render_x, camera.render_y, assets)
        fe.draw_hud_and_minimap(snes_canvas, hud_font, player, world, camera, (100, 100), controller, False, f)

    print("\nALL GAMEPLAY SIMULATION FRAMES PASSED WITH ZERO ERRORS!")

if __name__ == "__main__":
    asyncio.run(test_loop())
