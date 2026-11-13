"""
===============================================================================
FROGGY MAP TOOL: ROOM CONNECTIVITY, TOPOLOGY & LEVEL SCANNER
===============================================================================
A command-line and programmatic inspection tool to verify, print, modify, and
re-scan all Metroidvania zones in Froggy.

Features:
1. Visual 2D ASCII World Map of all rooms by `map_coords`.
2. Door Portal Graph & Bidirectional Link Validator.
3. Reachability Analysis (Shortest path from 'level_1' to all rooms, bosses & items).
4. Missing / Orphaned Door and Room Detection.
5. Export & Sync with levels/<zone_id>.json files.

FOR THE NEPHEW:
---------------
A Metroidvania world is like a subway system! Each room is a station, and each
door is a train track connecting two stations. If station A has a track to B,
station B must have a track back to A, or Froggy will get stuck in a one-way trap!
This tool checks every single track so the game world is 100% connected and fun to explore.
===============================================================================
"""

import sys
import os
from collections import deque

import world_data


def get_all_rooms():
    world_data.reload_blueprints()
    return world_data.WORLD_BLUEPRINTS


INTENTIONAL_ONE_WAY_PORTALS = {
    ("victory_chamber", "P"): ("level_1", "A"),
    ("sandbox_room", "A"): ("level_1", "A"),
    ("l2_sky_summit", "6"): ("victory_chamber", "7"),
}


def print_ascii_world_map(rooms=None):
    if rooms is None:
        rooms = get_all_rooms()

    by_grid = {}
    for rid, r in rooms.items():
        by_grid.setdefault(int(r.get("map_grid", 1)), {})[rid] = r

    for grid_id in sorted(by_grid.keys()):
        g_rooms = by_grid[grid_id]
        print("\n" + "=" * 70)
        print(f"FROGGY METROIDVANIA WORLD TOPOLOGY MAP — MAP GRID {grid_id} (2D GRID)")
        print("=" * 70)

        coords = [r.get("map_coords", (0, 0)) for r in g_rooms.values()]
        min_x = min(c[0] for c in coords)
        max_x = max(c[0] for c in coords)
        min_y = min(c[1] for c in coords)
        max_y = max(c[1] for c in coords)

        grid_map = {}
        for rid, r in g_rooms.items():
            gx, gy = r.get("map_coords", (0, 0))
            grid_map.setdefault((gx, gy), []).append(rid)

        cell_width = 16
        for gy in range(min_y, max_y + 1):
            line_top = ""
            line_mid = ""
            line_bot = ""
            for gx in range(min_x, max_x + 1):
                if (gx, gy) in grid_map:
                    rids = grid_map[(gx, gy)]
                    rid = rids[0]
                    theme = g_rooms[rid].get("theme", "")[:3].upper()
                    name_short = rid[:12] if len(rids) == 1 else f"{rid[:9]}!x{len(rids)}"
                    coord_str = f"({gx},{gy})"
                    line_top += f"+{'-' * (cell_width - 2)}+"
                    line_mid += f"|{name_short:^{cell_width - 2}}|"
                    line_bot += f"|[{theme:^3}] {coord_str:<{cell_width - 8}}|"
                else:
                    line_top += " " * cell_width
                    line_mid += " " * cell_width
                    line_bot += " " * cell_width

            if line_mid.strip():
                print(line_top)
                print(line_mid)
                print(line_bot)
                print(line_top)

        print("=" * 70 + "\n")


def _simulate_door_spawn(target_room_id, target_room_data, target_door_char, spawn_offset_x, spawn_offset_y):
    """
    Simulates Froggy's 14x16 spawn bounding box inside target_room_data using exact
    froggy_engine.py door swap positioning rules, returning a list of collision error strings.
    """
    t_grid = target_room_data.get("ascii_grid", [])
    if not t_grid:
        return [f"Target room '{target_room_id}' has empty ascii_grid!"]

    t_rows = len(t_grid)
    t_cols = len(t_grid[0])
    t_width = t_cols * 16
    t_height = t_rows * 16
    t_theme = target_room_data.get("theme", "canopy")

    positions = [
        (rr, cc)
        for rr, row in enumerate(t_grid)
        for cc, ch in enumerate(row)
        if ch == target_door_char
    ]
    if not positions:
        return [f"Target door '{target_door_char}' missing from '{target_room_id}' ascii_grid!"]

    d_left = min(c for _, c in positions) * 16
    d_right = (max(c for _, c in positions) + 1) * 16
    d_top = min(r for r, _ in positions) * 16
    d_bottom = (max(r for r, _ in positions) + 1) * 16
    cx = (d_left + d_right) // 2

    is_ceiling_door = (d_top <= 16)
    is_floor_door = (not is_ceiling_door) and (d_bottom >= t_height - 16)

    if is_ceiling_door:
        sx = cx + spawn_offset_x - 7
        sy = d_bottom + 4 + max(0, spawn_offset_y)
    elif is_floor_door:
        sx = cx + spawn_offset_x - 7
        sy = d_top - 16 - 4 + min(0, spawn_offset_y)
    else:
        sx = cx + spawn_offset_x - 7
        sy = d_bottom - 16 + spawn_offset_y

    errs = []
    if sx < 0 or sx + 14 > t_width or sy < 0 or sy + 16 > t_height:
        errs.append(
            f"Spawn rect ({sx},{sy},14,16) in '{target_room_id}:{target_door_char}' exceeds room bounds ({t_width}x{t_height})!"
        )
        return errs

    c0 = sx // 16
    c1 = (sx + 13) // 16
    r0 = sy // 16
    r1 = (sy + 15) // 16

    solid_or_door_hits = []
    hazard_hits = []
    hazard_chars = {'v', '~'} if t_theme == 'volcanic' else {'v'}
    for rr in range(r0, r1 + 1):
        for cc in range(c0, c1 + 1):
            ch = t_grid[rr][cc]
            if ch in ('#', 'r'):
                solid_or_door_hits.append((rr, cc, ch))
            elif ch == target_door_char:
                solid_or_door_hits.append((rr, cc, f"DOOR:{ch}"))
            elif ch in hazard_chars:
                hazard_hits.append((rr, cc, ch))

    if solid_or_door_hits:
        errs.append(
            f"Spawn rect ({sx},{sy},14,16) at '{target_room_id}:{target_door_char}' overlaps {solid_or_door_hits}!"
        )
    if hazard_hits:
        errs.append(
            f"Spawn rect ({sx},{sy},14,16) at '{target_room_id}:{target_door_char}' spawns directly in hazard {hazard_hits}!"
        )

    # Check vertical drop safety in non-underwater rooms (landing straight onto lava/spikes)
    if t_theme != 'underwater':
        all_cols_hit_hazard = True
        for cc in range(c0, c1 + 1):
            col_safe = False
            for rr in range(r1, t_rows):
                ch = t_grid[rr][cc]
                if ch in ('#', 'r'):
                    col_safe = True
                    break
                if ch in hazard_chars:
                    break
            else:
                col_safe = True
            if col_safe:
                all_cols_hit_hazard = False
                break
        if all_cols_hit_hazard:
            errs.append(
                f"Spawn rect ({sx},{sy},14,16) at '{target_room_id}:{target_door_char}' drops straight onto hazard without floor!"
            )

    return errs


def validate_door_connections(rooms=None):
    if rooms is None:
        rooms = get_all_rooms()

    print("\n" + "=" * 70)
    print("DOOR CONNECTIVITY, SPAWN & TOPOLOGY AUDIT")
    print("=" * 70)

    errors = []
    warnings = []
    notes = []
    success_count = 0

    # Check map_coords collisions across rooms
    coord_collisions = world_data.find_map_coord_collisions(rooms)
    for coords, zids in sorted(coord_collisions.items()):
        errors.append(f"Duplicate map_coords {coords} shared by rooms: {zids}")

    for rid, r in rooms.items():
        grid = r.get("ascii_grid", [])
        grid_str = "".join(grid)
        doors = r.get("doors", {})

        for dchar, dcfg in doors.items():
            # 0. Reject reserved structural/hazard/prop/NPC chars
            if dchar in world_data.RESERVED_NON_DOOR_CHARS:
                errors.append(
                    f"[{rid}] Door '{dchar}' collides with reserved non-door tile character!"
                )

            # 1. Check if door character exists in ASCII grid & bounding box <= 6x6
            positions = [
                (rr, cc)
                for rr, row in enumerate(grid)
                for cc, ch in enumerate(row)
                if ch == dchar
            ]
            if not positions:
                errors.append(f"[{rid}] Door '{dchar}' configured in 'doors' dict but MISSING from ascii_grid!")
                continue

            span_r = max(rr for rr, _ in positions) - min(rr for rr, _ in positions) + 1
            span_c = max(cc for _, cc in positions) - min(cc for _, cc in positions) + 1
            if span_c > 6 or span_r > 6:
                errors.append(
                    f"[{rid}] Door '{dchar}' bounding box spans {span_c}x{span_r} tiles (> 6 cols/rows); "
                    f"likely merged with another character!"
                )

            target_room = dcfg.get("target_room")
            target_door = dcfg.get("target_door")

            # 2. Check target room exists
            if target_room not in rooms:
                errors.append(f"[{rid}] Door '{dchar}' points to NON-EXISTENT room '{target_room}'!")
                continue

            # 3. Check target door exists in target room
            target_r_data = rooms[target_room]
            target_doors = target_r_data.get("doors", {})
            if target_door not in target_doors:
                errors.append(f"[{rid}] Door '{dchar}' -> '{target_room}' door '{target_door}' which DOES NOT EXIST in '{target_room}'!")
                continue

            # 4. Simulate Froggy's 14x16 spawn inside target room
            spawn_errs = _simulate_door_spawn(
                target_room,
                target_r_data,
                target_door,
                int(dcfg.get("spawn_offset_x", 0)),
                int(dcfg.get("spawn_offset_y", 0)),
            )
            for se in spawn_errs:
                errors.append(f"[{rid}:{dchar} -> {target_room}:{target_door}] {se}")

            # 5. Check bidirectional return (allow documented intentional one-way portals)
            reverse_cfg = target_doors[target_door]
            rev_target_room = reverse_cfg.get("target_room")
            rev_target_door = reverse_cfg.get("target_door")

            if rev_target_room != rid or rev_target_door != dchar:
                expected_one_way = INTENTIONAL_ONE_WAY_PORTALS.get((rid, dchar))
                if expected_one_way == (target_room, target_door):
                    notes.append(
                        f"[ONE-WAY RETURN PORTAL] {rid}:{dchar} -> {target_room}:{target_door} "
                        f"(reverse '{target_room}:{target_door}' -> '{rev_target_room}:{rev_target_door}')"
                    )
                else:
                    errors.append(
                        f"[{rid}] Door '{dchar}' -> '{target_room}:{target_door}', but reverse points to "
                        f"'{rev_target_room}:{rev_target_door}' (broken/asymmetric link)!"
                    )
            else:
                success_count += 1

    print(f"Validated {success_count} bidirectional door links.")
    if notes:
        print(f"\n[i] ONE-WAY PORTALS ({len(notes)}):")
        for n in notes:
            print("  *", n)
    if warnings:
        print(f"\n[!] WARNINGS ({len(warnings)}):")
        for w in warnings:
            print("  *", w)
    if errors:
        print(f"\n[X] ERRORS ({len(errors)}):")
        for e in errors:
            print("  *", e)
    else:
        print("\n[PASS] No broken door links, spawn collisions, or map_coords duplicates detected!")

    print("=" * 70 + "\n")
    return len(errors) == 0


def analyze_reachability(start_room="level_1", rooms=None):
    if rooms is None:
        rooms = get_all_rooms()

    print("\n" + "=" * 70)
    print(f"REACHABILITY & SHORTEST PATH ANALYSIS (START: '{start_room}')")
    print("=" * 70)

    if start_room not in rooms:
        print(f"[X] Start room '{start_room}' not found in blueprints!")
        return False

    queue = deque([(start_room, [start_room])])
    visited = {start_room: [start_room]}

    while queue:
        curr, path = queue.popleft()
        r_data = rooms[curr]
        for dchar, dcfg in r_data.get("doors", {}).items():
            tgt = dcfg.get("target_room")
            if tgt in rooms and tgt not in visited:
                new_path = path + [tgt]
                visited[tgt] = new_path
                queue.append((tgt, new_path))

    unreachable = set(rooms.keys()) - set(visited.keys()) - {"sandbox_room"}

    for rid in sorted(rooms.keys()):
        if rid == "sandbox_room":
            continue
        theme = rooms[rid].get("theme", "")
        if rid in visited:
            dist = len(visited[rid]) - 1
            path_str = " -> ".join(visited[rid])
            print(f"[OK] {rid:<18} ({theme:<10}) [Dist: {dist:2d}] Path: {path_str}")
        else:
            print(f"[UNREACHABLE] {rid:<18} ({theme:<10}) *** CANNOT BE REACHED FROM {start_room} ***")

    if unreachable:
        print(f"\n[X] {len(unreachable)} UNREACHABLE ROOM(S): {unreachable}")
        print("=" * 70 + "\n")
        return False
    else:
        print("\n[PASS] All adventure zones are 100% reachable from start!")
        print("=" * 70 + "\n")
        return True


def inspect_room(room_id, rooms=None):
    """
    Detailed inspection of a single room: dimensions, theme, spawns, relics, and doors.
    """
    if rooms is None:
        rooms = get_all_rooms()

    if room_id not in rooms:
        print(f"[X] Room '{room_id}' not found!")
        return

    r = rooms[room_id]
    grid = r.get("ascii_grid", [])
    doors = r.get("doors", {})
    theme = r.get("theme", "canopy")
    coords = r.get("map_coords", (0, 0))

    print("\n" + "=" * 60)
    print(f"ROOM INSPECTOR: {room_id.upper()} (Theme: {theme}, Coords: {coords})")
    print(f"Dimensions: {len(grid)} rows x {len(grid[0]) if grid else 0} cols ({len(grid[0]) if grid else 0} * 16 = {(len(grid[0]) if grid else 0)*16}px wide)")
    print("=" * 60)
    print("DOORS:")
    for dchar, dcfg in doors.items():
        print(f"  Door '{dchar}': -> {dcfg.get('target_room')}:{dcfg.get('target_door')} (Offset: {dcfg.get('spawn_offset_x')}, {dcfg.get('spawn_offset_y')})")

    grid_str = "".join(grid)
    door_chars = set(doors.keys())
    relics_found = []
    if 'J' in grid_str and 'J' not in door_chars: relics_found.append("Stomping Boots ('J')")
    if 'R' in grid_str and 'R' not in door_chars: relics_found.append("Red Boomerang ('R')")
    if 'L' in grid_str and 'L' not in door_chars: relics_found.append("The Muhlaser ('L')")
    if 'V' in grid_str and 'V' not in door_chars: relics_found.append("Vitality Heart Container ('V')")
    if 'X' in grid_str and 'X' not in door_chars: relics_found.append("Checkpoint Idol ('X')")
    if 'G' in grid_str and 'G' not in door_chars: relics_found.append(f"Grapple Nodes ('G' x{grid_str.count('G')})")
    print(f"KEY OBJECTS & RELICS: {', '.join(relics_found) if relics_found else 'None'}")
    print("=" * 60 + "\n")


def run_full_scan():
    rooms = get_all_rooms()
    print_ascii_world_map(rooms)

    blueprints_ok = True
    bp_errors = []
    bp_warnings = []
    for rid, rdata in sorted(rooms.items()):
        ok, errs, warns = world_data.validate_zone_blueprint(rid, rdata)
        if not ok:
            blueprints_ok = False
        for e in errs:
            bp_errors.append(f"[{rid}] {e}")
        for w in warns:
            bp_warnings.append(f"[{rid}] {w}")

    print("=" * 70)
    print(f"BLUEPRINT GEOMETRY & REGISTRY CHECK ({len(rooms)} ZONES)")
    print("=" * 70)
    if bp_warnings:
        print(f"[!] WARNINGS ({len(bp_warnings)}):")
        for w in bp_warnings:
            print("  *", w)
    if bp_errors:
        print(f"[X] ERRORS ({len(bp_errors)}):")
        for e in bp_errors:
            print("  *", e)
    else:
        print("[PASS] All room blueprints passed geometry & hazard checks!")
    print("=" * 70 + "\n")

    doors_ok = validate_door_connections(rooms)
    reach_ok = analyze_reachability("level_1", rooms)
    return blueprints_ok and doors_ok and reach_ok


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower().strip("-")
        if cmd == "map":
            print_ascii_world_map()
        elif cmd == "doors":
            validate_door_connections()
        elif cmd == "reach":
            analyze_reachability()
        elif cmd == "room" and len(sys.argv) > 2:
            inspect_room(sys.argv[2])
        elif cmd == "sync":
            world_data.sync_all_to_levels_dir(overwrite=True)
            print("Synced all zones to levels/ directory.")
        else:
            run_full_scan()
    else:
        run_full_scan()
