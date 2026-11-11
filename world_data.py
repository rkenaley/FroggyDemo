"""
===============================================================================
FROGGY: MODULAR WORLD DATA & METROIDVANIA ZONE REGISTRY
===============================================================================
This module decouples all level blueprints, tile legends, zone themes, and
room geometry from the monolithic engine. 

FOR THE NEPHEW (UNDER THE HOOD WALKTHROUGH):
-------------------------------------------------------------------------------
1. WHAT IS A TILEMAP?
   Instead of drawing an entire 2000-pixel level by hand in Photoshop, retro
   games use a *Tilemap*: a 2D grid of small repeating squares (here 16x16 px).
   In Froggy, we represent each level as a list of ASCII strings!
   For example:
       "####################"   <- Solid ceiling (row 0)
       "#..S.............G..#"   <- Spawn 'S', air '.', grapple ring 'G'
       "####################"   <- Solid floor

2. COORDINATE SYSTEMS (GRID VS WORLD PIXELS):
   - Grid Coordinates: (col, row), starting from top-left (0, 0).
   - World Coordinates:
         world_x = col * 16
         world_y = row * 16
   If col=5 and row=10, the entity is placed at pixel (80, 160) in the game world!

3. HOW 4-BIT BITMASK AUTO-TILING WORKS:
   When the engine sees a '#' block, it checks its 4 neighbors (North, East,
   South, West). Depending on which neighbors are also solid, it computes a
   number from 0 to 15:
       Mask = (North*1) + (East*2) + (South*4) + (West*8)
   That mask tells the engine whether to draw a top mossy grass edge, a corner,
   a vertical wall, or an interior cave brick!

4. MODULAR LEVEL STORAGE:
   - Built-in zones are stored in BUILTIN_BLUEPRINTS.
   - Any customized or newly created levels are saved directly to levels/<zone_id>.json.
   - When the game boots, it loads both! You can edit levels/<zone_id>.json directly
     with any text editor, or use py level_studio.py for visual editing!
===============================================================================
"""

import copy
import json
import os

TILE_SIZE = 16

# =============================================================================
# ASCII TILE LEGEND & OBJECT DICTIONARY
# =============================================================================
TILE_LEGEND = {
    '#': {
        'name': 'Solid Terrain',
        'category': 'terrain',
        'solid': True,
        'desc': 'Autotiled stone, roots & moss blocks. Stops Froggy and enemies.',
        'color': (70, 120, 80),
    },
    '.': {
        'name': 'Air / Empty',
        'category': 'air',
        'solid': False,
        'desc': 'Empty walkable space.',
        'color': (20, 30, 45),
    },
    '~': {
        'name': 'Swamp Water',
        'category': 'hazard',
        'solid': False,
        'desc': 'Bioluminescent swamp water hazard (or swim lagoon in underwater biome).',
        'color': (30, 140, 190),
    },
    'v': {
        'name': 'Molten Magma / Lava',
        'category': 'hazard',
        'solid': False,
        'desc': 'Scorching lava pool causing rapid heat rise toward 200%.',
        'color': (220, 70, 30),
    },
    'c': {
        'name': 'Waterfall Mist',
        'category': 'hazard',
        'solid': False,
        'desc': 'Cascading cold waterfall mist that cools Froggy down toward 100%.',
        'color': (140, 220, 240),
    },
    'o': {
        'name': 'Air Bubble Vent',
        'category': 'hazard',
        'solid': False,
        'desc': 'Submarine air bubble vent that refills oxygen gauge to 100%.',
        'color': (90, 200, 255),
    },
    '<': {
        'name': 'Westward Water Current',
        'category': 'hazard',
        'solid': False,
        'desc': 'Strong underwater current jet that sweeps Froggy velocity to the LEFT.',
        'color': (55, 195, 245),
    },
    '>': {
        'name': 'Eastward Water Current',
        'category': 'hazard',
        'solid': False,
        'desc': 'Strong underwater current jet that sweeps Froggy velocity to the RIGHT.',
        'color': (55, 225, 255),
    },
    'r': {
        'name': 'Cracked Burrow Rock',
        'category': 'terrain',
        'solid': True,
        'desc': 'Crystalline fissure rock that can only be burrowed through with a Charged Muhlaser beam!',
        'color': (95, 220, 240),
    },
    'G': {
        'name': 'Golden Frog Grapple Idol',
        'category': 'mechanic',
        'solid': False,
        'desc': 'Golden Idol for tongue whipping & pendulum swinging with [Y].',
        'color': (255, 215, 70),
    },
    'S': {
        'name': 'Player Default Spawn',
        'category': 'mechanic',
        'solid': False,
        'desc': 'Froggy default spawn point when entering the zone.',
        'color': (80, 240, 90),
    },
    'T': {
        'name': 'Mantis Warning Totem',
        'category': 'prop',
        'solid': False,
        'desc': 'Ancient stone totem warning of the Emperor Mantis Sanctum.',
        'color': (180, 120, 200),
    },
    'X': {
        'name': 'Checkpoint Totem',
        'category': 'mechanic',
        'solid': False,
        'desc': 'Restorative totem that heals HP, resets warmth, and auto-saves to disk.',
        'color': (255, 230, 90),
    },
    'e': {
        'name': 'Elder NPC Frog',
        'category': 'npc',
        'solid': False,
        'desc': 'Elder Mossbeard NPC providing story lore & advice.',
        'color': (60, 180, 110),
    },
    'k': {
        'name': 'Village Shopkeeper Frog',
        'category': 'npc',
        'solid': False,
        'desc': 'Shopkeeper Ribbit trading eaten bugs for healing tonics.',
        'color': (200, 150, 70),
    },
    'J': {
        'name': 'Stomping Boots Relic',
        'category': 'relic',
        'solid': False,
        'desc': 'Power-up relic enabling Mario-style downward stomp crushing.',
        'color': (240, 160, 50),
    },
    'R': {
        'name': 'Red Boomerang Relic',
        'category': 'relic',
        'solid': False,
        'desc': 'Power-up relic giving long-range curved projectile attacks with [R].',
        'color': (255, 60, 80),
    },
    'L': {
        'name': 'Muhlaser Frogbeam Relic',
        'category': 'relic',
        'solid': False,
        'desc': 'Mouth-based frogbeam weapon! Hold [R] up to 3s for massive damage & rock burrowing!',
        'color': (75, 245, 255),
    },
    'E': {
        'name': 'Spiked Moss Beetle',
        'category': 'enemy',
        'solid': False,
        'desc': 'Ground patrol troop beetle (stun with tongue or boots, then swallow!).',
        'color': (140, 180, 60),
    },
    'F': {
        'name': 'Neon Buzzfly',
        'category': 'enemy',
        'solid': False,
        'desc': 'Airborne sine-wave flying bug (instant swallow with tongue!).',
        'color': (240, 240, 80),
    },
    'N': {
        'name': 'Soldier Ant',
        'category': 'enemy',
        'solid': False,
        'desc': 'Fast charging ground ant with high aggressive sprint.',
        'color': (190, 80, 60),
    },
    'W': {
        'name': 'Shadow Spider',
        'category': 'enemy',
        'solid': False,
        'desc': 'Ceiling spider that ambushes and drops down on thread.',
        'color': (110, 70, 140),
    },
    'b': {
        'name': 'Stink Bug',
        'category': 'enemy',
        'solid': False,
        'desc': 'Patrolling stink bug that bursts into poison gas when stomped.',
        'color': (160, 140, 40),
    },
    'w': {
        'name': 'Ice Wolf Spider',
        'category': 'enemy',
        'solid': False,
        'desc': 'Camouflaged glacial spider that springs an ambush leap.',
        'color': (130, 200, 240),
    },
    'p': {
        'name': 'Razor Piranha',
        'category': 'enemy',
        'solid': False,
        'desc': 'Ferocious schooling fish predator that lunges horizontally when Froggy enters its lane.',
        'color': (235, 65, 75),
    },
    'a': {
        'name': 'Abyssal Anglerfish',
        'category': 'enemy',
        'solid': False,
        'desc': 'Deep-sea lure predator that stalks and snaps with needle jaws.',
        'color': (120, 95, 225),
    },
    'j': {
        'name': 'Bio-Electric Jellyfish',
        'category': 'enemy',
        'solid': False,
        'desc': 'Pulsing vertical-drifting jellyfish that periodically discharges a shock ring.',
        'color': (85, 245, 255),
    },
    'M': {
        'name': 'Emperor Mantis Boss',
        'category': 'boss',
        'solid': False,
        'desc': 'Colossal 3-Phase flying boss with scythe sweeps and weak-point pearl.',
        'color': (220, 60, 120),
    },
    'H': {
        'name': 'The Dread Hound Boss',
        'category': 'boss',
        'solid': False,
        'desc': 'Cybernetic canine colossus anchored to cavern wall.',
        'color': (220, 90, 40),
    },
    'Q': {
        'name': 'Giga Toad Boss',
        'category': 'boss',
        'solid': False,
        'desc': 'Muscular heavyweight brawler boss with seismic shockwaves.',
        'color': (80, 180, 120),
    },
    'O': {
        'name': 'Falo the Snowman Boss',
        'category': 'boss',
        'solid': False,
        'desc': 'Blizzard summit boss throwing rolling snowballs and carrot boomerang.',
        'color': (200, 230, 255),
    },
    's': {
        'name': 'Demon Shark Boss',
        'category': 'boss',
        'solid': False,
        'desc': 'Colossal abyssal apex shark boss! Weak to charged Muhlaser frogbeams.',
        'color': (255, 55, 85),
    },
}

# Add standard Door Portal characters ('A' through 'Z')
for char_code in range(ord('A'), ord('Z') + 1):
    char = chr(char_code)
    if char not in TILE_LEGEND:
        TILE_LEGEND[char] = {
            'name': f'Door Portal [{char}]',
            'category': 'door',
            'solid': False,
            'desc': f'Connecting door portal [{char}] linked to another room.',
            'color': (90, 235, 255),
        }

# =============================================================================
# ZONE THEMES & BIOMES
# =============================================================================
ZONE_THEMES = {
    'canopy': {
        'name': 'Sunlit Jungle Canopy',
        'bg_color': (16, 28, 42),
        'autotile_prefix': 'terrain',
        'music': 'level',
        'ambient_particles': 'fireflies',
        'description': 'Lush jungle treetops with swinging vines and mossy tree trunks.',
    },
    'sanctum': {
        'name': 'Ancient Mantis Sanctum',
        'bg_color': (28, 14, 28),
        'autotile_prefix': 'sanctum',
        'music': 'boss_mantis',
        'ambient_particles': 'sinister_spores',
        'description': 'Gothic purple stone temples with ominous carved totems.',
    },
    'ice': {
        'name': 'Glacial Peak & Hot Springs',
        'bg_color': (14, 28, 48),
        'autotile_prefix': 'ice',
        'music': 'ice',
        'ambient_particles': 'snow_spores',
        'description': 'Freezing mountain summit with hypothermia chill & soothing hot springs.',
    },
    'volcanic': {
        'name': 'Volcanic Magma Chasm',
        'bg_color': (36, 12, 12),
        'autotile_prefix': 'volcanic',
        'music': 'volcanic',
        'ambient_particles': 'ash_embers',
        'description': 'Scorching underground chasm with molten lava & cooling waterfalls.',
    },
    'underwater': {
        'name': 'Sunken Submarine Grotto',
        'bg_color': (8, 24, 38),
        'autotile_prefix': 'underwater',
        'music': 'underwater',
        'ambient_particles': 'bubbles',
        'description': 'Deep underwater coral caverns with swimming currents & oxygen vents.',
    },
}

BUILTIN_BLUEPRINTS = {
    # -------------------------------------------------------------------------
    # LEVEL 1: LUSH CANOPY TRAIL -> TEMPLE CHIMNEY -> EMPEROR MANTIS SANCTUM
    # A complete, seamless 3-act showcase level (116 cols x 23 rows = 1856x368 px):
    #   - Act I   (Cols 0..38) : Sunlit Lush Canopy (Hops, Double Jump, First Beetle)
    #   - Act II  (Cols 39..76): Temple Wall-Jump Chimney & Grapple Water Chasm
    #   - Act III (Cols 77..115): Ominous Totems & The Emperor Mantis Boss Arena!
    # When Froggy crosses into Act III, the Emperor Mantis awakens and the music
    # dynamically shifts from the Jamaican groove to the Sinister Boss Theme!
    # -------------------------------------------------------------------------
    "level_1": {
        "title": "LEVEL 1: LUSH CANOPY TO MANTIS SANCTUM",
        "theme": "canopy",
        "bg_color": (16, 28, 42),
        "map_coords": (0, 0),
        "boss_trigger_x": 1220,  # Crossing X=1220 awakens the Emperor Mantis & sinister music!
        "npcs": [
            {
                "kind": "elder",
                "name": "ELDER MOSSBEARD",
                "x": 144,
                "y": 272,
                "dialogue": [
                    "Ribbit! Welcome, young Froggy. Dark times have fallen upon our jungle ruins... evil giant insects have overrun the canopy!",
                    "Remember: as an amphibian, you are cold-blooded! In our temperate ruins you are safe, but beware freezing blizzards and boiling magma!",
                    "Whip bugs with your 8-way tongue [Y] to eat them. Trade eaten bugs at my shop in the Sunken Temple!",
                    "Slay the 4 Colossi guarding the realm to gather their Key Fragments and unseal the Sacred Sanctuary!"
                ],
            }
        ],
        "doors": {
            "A": {
                "target_room": "entrance_hall",
                "target_door": "A",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "####################################################################################################################", # 0
            "#..................................................................................................................#", # 1
            "#..................................................................................................................#", # 2
            "#..................................................................................................................#", # 3
            "#.............................................................G....................................................#", # 4
            "#....................................................................................G..........G..........G.......#", # 5
            "#...............................................#...#.######.......................................................#", # 6
            "#...............................................#...#..............................................................#", # 7
            "#...............................................#...#..............................................................#", # 8
            "#.........................F.....................#...#....................................................M.........#", # 9
            "#.......................#####...................#...#...................#######....................................#", # 10
            "#...............................................#...#.........................T......#####.................#####...#", # 11
            "#.............................##############....#...#..............................................................#", # 12
            "#....................................E..........#...#.......................................G..........G...........#", # 13
            "#...............................................#...#..............................................................#", # 14
            "#................####...........................#...#..........F...................................................#", # 15
            "#...................................................#....................................#####.........#####.......#", # 16
            "#....S..............................................#..............................................................A", # 17
            "#..###########......................................#..............................................................A", # 18
            "#.......................E...........................#.........................T....................................A", # 19
            "#....................#######........................#...................#############..............................#", # 20
            "#####################################################~~~~~~~~~~~~~~~~~~~############################################", # 21
            "####################################################################################################################", # 22
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 2: SUNKEN FROG TEMPLE HALL
    # Features swimming lagoons and the ancient Stomping Boots power-up pedestal!
    # -------------------------------------------------------------------------
    "entrance_hall": {
        "title": "2. SUNKEN FROG TEMPLE HALL",
        "theme": "temple",
        "bg_color": (18, 24, 44),
        "map_coords": (1, 0),
        "npcs": [
            {
                "kind": "shopkeeper",
                "name": "ELDER MOSSMANTLE, THE ANCIENT MERCHANT",
                "x": 288,
                "y": 240,
                "shop_cost": 1,
                "shop_item": "ANCIENT APOTHECARY WARES",
                "dialogue": [
                    "Greetings, Froggy! I am Elder Mossmantle. Press [UP] to browse my ancient apothecary wares!",
                    "Exchange eaten bugs for Heart Nectar (+HP), Glacial Chill Draughts (Cooling), and Oxygen Reeds!"
                ],
            }
        ],
        "doors": {
            "A": {
                "target_room": "level_1",
                "target_door": "A",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "B": {
                "target_room": "chimney_tower",
                "target_door": "B",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
            "U": {
                "target_room": "frost_ascent",
                "target_door": "D",
                "spawn_offset_x": 0,
                "spawn_offset_y": -24,
            },
            "Y": {
                "target_room": "sunken_grotto",
                "target_door": "Y",
                "spawn_offset_x": 0,
                "spawn_offset_y": 24,
            },
        },
        "ascii_grid": [
            "############################UUUU############################",
            "#..........................................................#",
            "#............................G.............................#",
            "#................G........................G................#",
            "#..........................................................#",
            "#............................F.............................#",
            "#...................................................########",
            "#............................E.............................#",
            "#.........................########.........................#",
            "#.........F......................................F.........#",
            "#.............######....................######.............#",
            "#..........................................................#",
            "#..................J.......................................#", # 'J' = Stomping Boots Relic Pedestal!
            "#...............######........................N............#", # 'N' = Soldier Ant Patrol
            "#..........................................######..........#",
            "#..........................................................#",
            "#...............##########.................................#",
            "A..........................................................B",
            "A..........................................................B",
            "A###.......................................E...............B",
            "#..........................................#######.........#",
            "########################~~~~~~~~~~~~########################", # Swimming lagoon!
            "############################YYYY############################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 3: VINE CHIMNEY TOWER
    # High vertical climb guarded by Soldier Ants and ceiling Shadow Spiders!
    # -------------------------------------------------------------------------
    "chimney_tower": {
        "title": "3. VINE CHIMNEY ASCENT",
        "theme": "cavern",
        "bg_color": (22, 20, 44),
        "map_coords": (1, 1),
        "doors": {
            "B": {
                "target_room": "entrance_hall",
                "target_door": "B",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "C": {
                "target_room": "grapple_cavern",
                "target_door": "C",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################",
            "#........W......................W..........#", # 'W' = Ceiling Shadow Spiders!
            "#.....................G....................#",
            "#..........................................C",
            "#..................................N.......C",
            "#............................###############",
            "#..................###.....#...............#",
            "#........F.........###.....#...............#",
            "#..................###.....#...............#",
            "#........G.........###.....#...............#",
            "#..................###.....#...............#",
            "#..................###.....#...............#",
            "#..................###...........F.........#",
            "#..................###...............E.....#",
            "#..................###............######...#",
            "#........W.........###.....................#",
            "#..................###.....................#",
            "#..................###.............G.......#",
            "#..........N.......###.....................#",
            "#.......######.....###.....................#",
            "#..................###............E........#",
            "B..............................######......#",
            "B............E.............................#",
            "B.........######...........................#",
            "############################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 4: BIOLUMINESCENT GRAPPLE CAVERN (DOUBLE-GRAPPLE CHALLENGE)
    # Mid-air void requiring two consecutive grapple swings to reach Door D!
    # -------------------------------------------------------------------------
    "grapple_cavern": {
        "title": "4. BIOLUMINESCENT GRAPPLE CAVERN",
        "theme": "cavern",
        "bg_color": (14, 30, 42),
        "map_coords": (2, 1),
        "doors": {
            "C": {
                "target_room": "chimney_tower",
                "target_door": "C",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "D": {
                "target_room": "boss_sanctum",
                "target_door": "D",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
            "Z": {
                "target_room": "falo_arena",
                "target_door": "Z",
                "spawn_offset_x": 0,
                "spawn_offset_y": -24,
            },
            "Y": {
                "target_room": "volcanic_chasm",
                "target_door": "Y",
                "spawn_offset_x": 0,
                "spawn_offset_y": 24,
            },
        },
        "ascii_grid": [
            "################################ZZZZ################################",
            "#..................................................................#",
            "#..................................................................#",
            "C..................................................................#",
            "C............G...............G.....................................#",
            "######.............................................................#",
            "#..................................................................#",
            "#..................................................................#",
            "#..................................................................#",
            "#..................................................................#",
            "#.........######.............................######................#",
            "#..................................................................#",
            "#..................................................................#",
            "#..................G...............G...............................#", # DOUBLE GRAPPLE IN MID-AIR!
            "#..................................................................#",
            "#..................................................................#",
            "#...E...........................................................E..D",
            "#######.......................................................######D",
            "#..................................................................D",
            "#..................................................................#",
            "#..................................................................#",
            "#################~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~##################", # Swimming lagoon safety net!
            "################################YYYY################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 5: EMPEROR MANTIS SANCTUM (FIRST BOSS LAIR)
    # Defeating the Emperor Mantis drops the Red Spore Boomerang Relic!
    # -------------------------------------------------------------------------
    "boss_sanctum": {
        "title": "5. EMPEROR MANTIS SANCTUM",
        "theme": "sanctum",
        "bg_color": (34, 12, 28),
        "map_coords": (3, 1),
        "boss_trigger_x": 60,
        "doors": {
            "D": {
                "target_room": "grapple_cavern",
                "target_door": "D",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "V": {
                "target_room": "hound_sanctum",
                "target_door": "V",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################",
            "#..........................................#",
            "#..........................................#",
            "#.........G..........G..........G..........#",
            "#..........................................#",
            "#..........................................#",
            "#..............................M...........#", # 'M' = Emperor Mantis Boss!
            "#..........................................#",
            "#....######......................######....#",
            "#..........................................#",
            "#..............G............G..............#",
            "#..........................................#",
            "#..........................................#",
            "#.........######............######.........#",
            "#..........................................#",
            "#..........................................#",
            "#..........................................#",
            "D......T............................T......V",
            "D...#######......................#######...V",
            "D..........................................V",
            "#..........................................#",
            "############################################",
            "############################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 5B: THE HOUND'S SANCTUM (SECOND BOSS - 16-BIT WALL COLOSSUS)
    # The Dread Hound: Colossal snapping jaw boss anchored to the right wall!
    # -------------------------------------------------------------------------
    "hound_sanctum": {
        "title": "5B. THE HOUND'S SANCTUM",
        "theme": "sanctum",
        "bg_color": (32, 14, 26),
        "map_coords": (4, 1),
        "boss_trigger_x": 80,
        "doors": {
            "V": {
                "target_room": "boss_sanctum",
                "target_door": "V",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "K": {
                "target_room": "toad_colosseum",
                "target_door": "K",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#............G.................G.................G.........#", # Overhead grapple rings within tongue reach!
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "V..........................................................K",
            "V..........................................................K",
            "V.....T............................................H.......K", # 'H' = The Dread Hound Boss on flat floor!
            "############################################################",
            "############################################################",
            "############################################################",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 5C: GIGA TOAD'S BRAWLER COLOSSEUM (THIRD BOSS - HEAVYWEIGHT BRAWLER)
    # Wide-open colosseum floor with overhead grapple idols for aerial combat!
    # -------------------------------------------------------------------------
    "toad_colosseum": {
        "title": "5C. GIGA TOAD'S BRAWLER COLOSSEUM",
        "theme": "sanctum",
        "bg_color": (28, 16, 32),
        "map_coords": (5, 1),
        "boss_trigger_x": 80,
        "doors": {
            "K": {
                "target_room": "hound_sanctum",
                "target_door": "K",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "L": {
                "target_room": "victory_chamber",
                "target_door": "L",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
                "is_master_key_door": True,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#............G.................G.................G.........#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "K..........................................................L",
            "K..........................................................L",
            "K.....T......................................Q.............L",
            "############################################################",
            "############################################################",
            "############################################################",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 6: SACRED LILYPAD SANCTUARY (VICTORY REWARD CHAMBER)
    # Sacred tranquil haven after vanquishing all ancient colossi!
    # -------------------------------------------------------------------------
    "victory_chamber": {
        "title": "6. SACRED LILYPAD SANCTUARY",
        "theme": "canopy",
        "bg_color": (12, 34, 30),
        "map_coords": (6, 1),
        "doors": {
            "L": {
                "target_room": "toad_colosseum",
                "target_door": "L",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "P": {
                "target_room": "level_1",
                "target_door": "START",
                "spawn_offset_x": 0,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################",
            "#..........................................#",
            "#..........................................#",
            "#....................G.....................#",
            "#..........................................#",
            "#..........................................#",
            "#..........................................#",
            "#..........................................#",
            "#..........................................#",
            "#....................T.....................#",
            "#.................#######..................#",
            "#..........................................#",
            "#..........................................#",
            "#..........................................#",
            "#.........F......................F.........#",
            "#.......#####..................#####.......#",
            "L..........................................P",
            "L..........................................P",
            "L..........................................P",
            "############################################",
            "############################################",
            "############################################",
            "############################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 7: FROST ASCENT TO GLACIAL SUMMIT (ICY WORLD ENTRY)
    # The air grows freezing cold! Amphibian thermometer begins draining!
    # Features slippery frost ledges, grapple idols, and Stink Bug sentinels.
    # -------------------------------------------------------------------------
    "frost_ascent": {
        "title": "7. FROST ASCENT TO GLACIAL SUMMIT",
        "theme": "ice",
        "bg_color": (16, 24, 45),
        "map_coords": (1, -1),
        "doors": {
            "D": {
                "target_room": "entrance_hall",
                "target_door": "U",
                "spawn_offset_x": 0,
                "spawn_offset_y": 24,
            },
            "E": {
                "target_room": "frost_springs",
                "target_door": "E",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#................G........................G................#",
            "#..........................................................#",
            "#............................b.............................#",
            "#.........................########.........................#",
            "#.........b......................................b.........#",
            "#......######..................................######......#",
            "#............................G.............................#",
            "#..........................................................#",
            "#.................######............######.................#",
            "#..........................................................#",
            "#............................b.............................#",
            "#.........................########.........................#",
            "#.........G......................................G.........#",
            "#..........................................................#",
            "#......######..................................######......E",
            "#..........................................................E",
            "#..........................................................E",
            "#..........................................................#",
            "#..........................................................#",
            "############################....############################",
            "############################DDDD############################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 8: STEAMY GLACIAL HOT SPRINGS (CHECKPOINT HAVEN)
    # Geothermal hot springs emit rising steam vapor! Froggy can bathe here
    # to warm his thermometer back up to 100%!
    # Checkpoint Totem ('X') permanently saves HP, warmth & inventory to disk!
    # Guarded by poisonous Stink Bugs ('b') and camouflaged Ice Wolf Spiders ('w').
    # -------------------------------------------------------------------------
    "frost_springs": {
        "title": "8. STEAMY GLACIAL HOT SPRINGS",
        "theme": "ice",
        "bg_color": (18, 28, 52),
        "map_coords": (2, -1),
        "npcs": [
            {
                "kind": "elder",
                "name": "ELDER FROSTCROAK",
                "x": 416,
                "y": 176,
                "dialogue": [
                    "Brrr! Bathe in the steamy hot springs below to warm your amphibian blood to 100%!",
                    "Ahead lies Falo the Evil Snowman! Jump on his black top hat or melt him with Red Spores!"
                ],
            }
        ],
        "doors": {
            "E": {
                "target_room": "frost_ascent",
                "target_door": "E",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "F": {
                "target_room": "falo_arena",
                "target_door": "F",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#..........................................................#",
            "#............G...................G...................G.....#",
            "#..........................................................#",
            "#..........................................................#",
            "#............................w.............................#",
            "#.........................########.........................#",
            "#.........b......................................b.........#",
            "#......######..................................######......#",
            "#..........................................................#",
            "#............................X.............................#",
            "#.........................########.........................#",
            "#..........................................................#",
            "#.........w......................................w.........#",
            "#......######..................................######......#",
            "#..........................................................#",
            "E..........................................................F",
            "E..........................................................F",
            "E..........................................................F",
            "#..........................................................#",
            "#################~~~~~~~~~~~~~~~~~~~~~~~~~~~~###############",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 9: BLIZZARD PEAK - FALO THE EVIL SNOWMAN'S ARENA
    # Colossal snowman boss who hurls rolling snowballs and throws his razor
    # carrot nose boomerang! Jump on his top hat to squash him Mario-style!
    # Bottom chute ('Z') drops directly into Cavern Room 4!
    # -------------------------------------------------------------------------
    "falo_arena": {
        "title": "9. BLIZZARD PEAK - FALO'S LAIR",
        "theme": "ice",
        "bg_color": (22, 16, 42),
        "map_coords": (3, -1),
        "boss_trigger_x": 60,
        "doors": {
            "F": {
                "target_room": "frost_springs",
                "target_door": "F",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "Z": {
                "target_room": "grapple_cavern",
                "target_door": "Z",
                "spawn_offset_x": 0,
                "spawn_offset_y": 24,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#..........................................................#",
            "#..........................................................#",
            "#............G...................G...................G.....#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "#....######......................................######....#",
            "#..........................................................#",
            "#..........................................................#",
            "#............................G.............................#",
            "#..........................................................#",
            "#.........######............O...............######.........#",
            "#..........................................................#",
            "#..........................................................#",
            "#..........................................................#",
            "F..........................................................#",
            "F...#######......................................#######...#",
            "F..........................................................#",
            "#..........................................................#",
            "############################....############################",
            "############################ZZZZ############################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 10: SUNKEN SUBMARINE GROTTO (MULTI-SCREEN AQUATIC GAUNTLET)
    # A 3-screen-wide underwater reef (110 cols x 23 rows) featuring:
    #   - 3 Aquatic Fish Enemies: Razor Piranhas ('p'), Abyssal Anglerfish ('a'),
    #     and Bio-Electric Jellyfish ('j').
    #   - Underwater Currents ('<' and '>') that sweep Froggy's velocity in one
    #     direction, making dodging tricky!
    #   - The Muhlaser Frogbeam Relic ('L') in the eastern reef shrine!
    #   - Cracked Burrow Rocks ('r') sealing off the western passage (Door 'U')
    #     into Demon Shark's Abyssal Lair!
    # -------------------------------------------------------------------------
    "sunken_grotto": {
        "title": "10. SUNKEN SUBMARINE GROTTO",
        "theme": "underwater",
        "bg_color": (8, 28, 48),
        "map_coords": (1, 2),
        "npcs": [
            {
                "kind": "elder",
                "name": "ELDER NAUTILUS",
                "x": 768,
                "y": 272,
                "dialogue": [
                    "Welcome to the Sunken Grotto! Watch out for Underwater Currents ('<' and '>') that sweep your velocity!",
                    "Claim the MUHLASER Relic ('L') in the eastern reef! Hold [R] up to 3s for a mega beam that burrows through Cracked Rocks!",
                    "Blast through the western Cracked Rock barrier ('r') to enter the Abyssal Trench and face DEMON SHARK!"
                ],
            }
        ],
        "doors": {
            "Y": {
                "target_room": "entrance_hall",
                "target_door": "Y",
                "spawn_offset_x": 0,
                "spawn_offset_y": -24,
            },
            "I": {
                "target_room": "volcanic_chasm",
                "target_door": "I",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
            "U": {
                "target_room": "shark_sanctum",
                "target_door": "U",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "####################################################YYYY######################################################",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~....~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~>>>>>>>>>>~~~~~~~~~~~~~~~~~~~##########~~~~~~~~~~~~~~~~~~~~<<<<<<<<<<~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~p~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#~~~~~~~~#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~p~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~j~~~~~~~~~~~~~~~#~~~~~~~~#~~~~~~~~~~~~~~~~j~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~######~~~~~~~~~~~~######~~~~~~~~~~~~~#~~~o~~~~#~~~~~~~~~~~~~~######~~~~~~~~~~~######~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#~~~~~~~~#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~<<<<<<<<<<~~~~~~~~~~~a~~~~~~~~~~#~~~~~~~~#~~~~~~~~~~~a~~~~~~~~~~>>>>>>>>>>~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#~~~~~~~~#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~#####################~~~~~~~~#####################~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~p~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~p~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~G~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~G~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~############~~~~~~~~~~~~~~~~~~~~~~~~>>>>>>>>>>~~~~~~~~~~~~~~~~~~~~~~~~############~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~rr~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~o~~~~~~rr~~~~~~~j~~~~~~~~~~~o~~~~~~~~~~~~~~##########~~~~~~~~~~~~~~~o~~~~~~~~~~~~~j~~~~~~~~~~~L~~~~~~~~~#",
            "#~~~~~~~~~~~rr~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#~~~~~~~~#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~######~~~~~~~#",
            "U~~~~X~~~~~~rr~~~~~~~~~~~~p~~~~~~~~~~~~~~~~S~~~e#~~~o~~~~#~~~~~~~~~~~~~~~~~a~~~~~~~~~~~~~~~~~~~~~~~~~~~k~~~~~I",
            "U#########~~rr~~~~#######~~~~~~~~~~~~~~~~########~~~~~~~~#########~~~~~~~~~~~~~~~~~~~~#######~~~~~~~~~~######I",
            "U~~~~~~~~~~~rr~~~~~~~~~~~~~~~~~~~~<<<<<<<<<<~~~~~~~~~~~~~~~~~~~~~~~~>>>>>>>>>>~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~I",
            "#~~~~~~~~~~~rr~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~rr~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "##############################################################################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 10B: ABYSSAL TRENCH - DEMON SHARK'S LAIR (SWIMMING AREA BOSS)
    # Colossal underwater apex predator arena with cross-currents, bubble vents,
    # and DEMON SHARK ('s'), who is armored against standard attacks but WEAK
    # to charged Muhlaser frogbeam shots!
    # -------------------------------------------------------------------------
    "shark_sanctum": {
        "title": "10B. ABYSSAL TRENCH - DEMON SHARK",
        "theme": "underwater",
        "bg_color": (6, 18, 36),
        "map_coords": (0, 2),
        "doors": {
            "U": {
                "target_room": "sunken_grotto",
                "target_door": "U",
                "spawn_offset_x": 26,
                "spawn_offset_y": 0,
            },
        },
        "ascii_grid": [
            "############################################################",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~o~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~o~~~~~~#",
            "#~~~~~~~~~~~~~>>>>>>>>~~~~~~~~~~~~~~~~<<<<<<<<~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~#####~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#####~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~G~~~~~~~~~~G~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~<<<<<<<<~~~~~~~~~~~~~~~~>>>>>>>>~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~s~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~################~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "#~~~~~~o~~~~~~~~~~~~~~~~~~~~~o~~~~~~~~~~~~~~~~~~~~~~o~~~~~~#",
            "#~~~~S~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~U",
            "#~~#######~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#######~~U",
            "#~~~~~~~~~~~~~~~~~~~~~>>>>>>>><<<<<<<<~~~~~~~~~~~~~~~~~~~~~U",
            "#~~~~~~o~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~o~~~~~~#",
            "#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # ROOM 11: VOLCANIC MAGMA CHASM (OVERHEAT & COLD WATERFALL MIST BIOME)
    # Scorching volcanic heat drives Froggy's body_temp UP above 100% toward 200%!
    # Stand inside cascading Cold Waterfall Mist columns ('c') to cool back down!
    # -------------------------------------------------------------------------
    "volcanic_chasm": {
        "title": "11. VOLCANIC MAGMA CHASM",
        "theme": "volcanic",
        "bg_color": (38, 12, 10),
        "map_coords": (2, 2),
        "npcs": [
            {
                "kind": "elder",
                "name": "HERMIT PYRO",
                "x": 112,
                "y": 272,
                "dialogue": [
                    "Whew, it's boiling in the Magma Chasm! If your TEMP hits 200%, volcanic heat burns you!",
                    "Dash through cascading Cold Waterfall Mist columns to cool your amphibian skin right back down!"
                ],
            }
        ],
        "doors": {
            "I": {
                "target_room": "sunken_grotto",
                "target_door": "I",
                "spawn_offset_x": -26,
                "spawn_offset_y": 0,
            },
            "Y": {
                "target_room": "grapple_cavern",
                "target_door": "Y",
                "spawn_offset_x": 0,
                "spawn_offset_y": -24,
            },
        },
        "ascii_grid": [
            "############################YYYY############################",
            "#..............cc..........................cc..............#",
            "#..............cc..........................cc..............#",
            "#..............cc...........G..............cc..............#",
            "#..............cc..........................cc..............#",
            "#......G.......cc...................G......cc.......G......#",
            "#..............cc..........................cc..............#",
            "#..............cc.........######...........cc..............#",
            "#..............cc..........................cc..............#",
            "#.........#######..........................#######.........#",
            "#..............cc...........X..............cc..............#",
            "#..............cc........########..........cc..............#",
            "#..............cc..........................cc..............#",
            "#....N.........cc..........................cc.........N....#",
            "#..######......cc.....G..............G.....cc......######..#",
            "#..............cc..........................cc..............#",
            "#..............cc..........................cc..............#",
            "I....S.........cc............E.............cc.........e....#",
            "I##########....cc.........#######..........cc....##########",
            "I..............cc..........................cc..............#",
            "#..............cc..........................cc..............#",
            "###########~~~~~~~~~~##################~~~~~~~~~~###########",
            "############################################################",
        ],
    },

    # -------------------------------------------------------------------------
    # SANDBOX ROOM: CLEAN CANVAS FOR "CREATE LEVEL" MODE
    # -------------------------------------------------------------------------
    "sandbox_room": {
        "title": "BUILDER'S SANDBOX",
        "theme": "canopy",
        "bg_color": (18, 24, 38),
        "map_coords": (-1, 2),
        "doors": {
            "A": {
                "target_room": "level_1",
                "target_door": "A",
                "spawn_offset_x": -22,
                "spawn_offset_y": 0,
            }
        },
        "ascii_grid": [
            "##################################################",
            "#................................................#",
            "#................................................#",
            "#..................G..........G..................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#................................................#",
            "#....S...........................................A",
            "#..######..............######....................A",
            "#................................................A",
            "#................................................#",
            "##################################################",
            "##################################################",
        ],
    },
}


# =============================================================================
# MODULAR LEVEL STORAGE & RUNTIME REGISTRY
# =============================================================================
LEVELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")

# Active runtime blueprints registry (combines built-ins + custom levels)
WORLD_BLUEPRINTS = {}


def reload_blueprints():
    """
    Reloads all zone blueprints from BUILTIN_BLUEPRINTS and merges any
    custom/tweaked level JSON files found in the levels/ directory.
    """
    global WORLD_BLUEPRINTS
    WORLD_BLUEPRINTS.clear()

    # 1. Load all built-in zones (deep copy so original stays clean)
    for zone_id, data in BUILTIN_BLUEPRINTS.items():
        WORLD_BLUEPRINTS[zone_id] = copy.deepcopy(data)

    # 2. Check for custom / overridden levels in levels/ directory
    if os.path.isdir(LEVELS_DIR):
        for fname in os.listdir(LEVELS_DIR):
            if fname.endswith(".json"):
                zone_id = fname[:-5]
                fpath = os.path.join(LEVELS_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        custom_data = json.load(f)
                    # Convert tuples that JSON turned into lists
                    if "bg_color" in custom_data and isinstance(custom_data["bg_color"], list):
                        custom_data["bg_color"] = tuple(custom_data["bg_color"])
                    if "map_coords" in custom_data and isinstance(custom_data["map_coords"], list):
                        custom_data["map_coords"] = tuple(custom_data["map_coords"])
                    WORLD_BLUEPRINTS[zone_id] = custom_data
                except Exception as e:
                    print(f"[world_data] Warning: Failed to load custom level '{fname}': {e}")

    return WORLD_BLUEPRINTS


def list_zone_ids():
    """Returns a list of all active zone string IDs."""
    return list(WORLD_BLUEPRINTS.keys())


def list_zones():
    """
    Returns a rich list of dictionaries summarizing each zone:
      - id: exact zone ID (e.g. 'level_1', 'frost_springs')
      - title: display title
      - theme: theme name
      - cols: width in tiles
      - rows: height in tiles
      - width_px: width in pixels
      - height_px: height in pixels
      - doors: list of door portal IDs
      - npcs: count of NPCs
      - enemies: count of spawned enemies
      - has_boss: whether a boss exists in the room
      - is_custom: whether it has a custom file on disk in levels/
    """
    summaries = []
    for zone_id, data in WORLD_BLUEPRINTS.items():
        grid = data.get("ascii_grid", [])
        rows = len(grid)
        cols = max(len(r) for r in grid) if rows > 0 else 0
        doors = list(data.get("doors", {}).keys())
        npc_count = len(data.get("npcs", []))

        # Count enemies and bosses from grid
        enemy_chars = {'E', 'F', 'N', 'W', 'b', 'w', 'p', 'a', 'j'}
        boss_chars = {'M', 'H', 'Q', 'O', 's'}
        enemy_count = 0
        has_boss = False
        for row in grid:
            for ch in row:
                if ch in enemy_chars:
                    enemy_count += 1
                elif ch in boss_chars:
                    has_boss = True

        custom_path = os.path.join(LEVELS_DIR, f"{zone_id}.json")
        is_custom = os.path.exists(custom_path)

        summaries.append({
            "id": zone_id,
            "title": data.get("title", zone_id),
            "theme": data.get("theme", "canopy"),
            "cols": cols,
            "rows": rows,
            "width_px": cols * TILE_SIZE,
            "height_px": rows * TILE_SIZE,
            "doors": doors,
            "npcs": npc_count,
            "enemies": enemy_count,
            "has_boss": has_boss,
            "is_custom": is_custom,
        })
    return summaries


def get_zone(zone_id):
    """Returns a deep copy of the requested zone blueprint dictionary."""
    if zone_id not in WORLD_BLUEPRINTS:
        available = ", ".join(repr(z) for z in list_zone_ids())
        raise KeyError(f"Zone '{zone_id}' not found! Available zones: {available}")
    return copy.deepcopy(WORLD_BLUEPRINTS[zone_id])


def create_blank_zone(zone_id, title=None, theme="canopy", cols=60, rows=23, fill_char="."):
    """
    Creates a brand-new, fully playable zone from scratch with solid outer
    boundaries ('#'), air interior ('.'), and a default player spawn point ('S').
    """
    cols = max(20, min(240, int(cols)))
    rows = max(15, min(80, int(rows)))

    if title is None:
        clean_title = zone_id.replace("_", " ").title()
        title = f"ZONE: {clean_title}"

    theme_info = ZONE_THEMES.get(theme, ZONE_THEMES["canopy"])
    bg_color = theme_info["bg_color"]

    # Build ASCII grid: solid outer walls, empty interior
    ascii_grid = []
    for r in range(rows):
        if r == 0 or r == rows - 1 or r == rows - 2:
            # Ceiling and 2-block solid floor
            ascii_grid.append("#" * cols)
        else:
            row_chars = ["#"] + [fill_char] * (cols - 2) + ["#"]
            # Place default spawn point 'S' near left floor
            if r == rows - 3:
                row_chars[4] = "S"
            ascii_grid.append("".join(row_chars))

    zone_data = {
        "title": title,
        "theme": theme,
        "bg_color": bg_color,
        "map_coords": (0, 0),
        "npcs": [],
        "doors": {},
        "ascii_grid": ascii_grid,
    }

    return zone_data


def save_zone(zone_id, zone_data, save_to_disk=True):
    """
    Saves the zone into the active WORLD_BLUEPRINTS registry and persists
    it as levels/<zone_id>.json.
    """
    WORLD_BLUEPRINTS[zone_id] = copy.deepcopy(zone_data)

    if save_to_disk:
        os.makedirs(LEVELS_DIR, exist_ok=True)
        file_path = os.path.join(LEVELS_DIR, f"{zone_id}.json")
        serializable = copy.deepcopy(zone_data)
        if isinstance(serializable.get("bg_color"), tuple):
            serializable["bg_color"] = list(serializable["bg_color"])
        if isinstance(serializable.get("map_coords"), tuple):
            serializable["map_coords"] = list(serializable["map_coords"])

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
        return file_path
    return None


def delete_zone(zone_id, allow_core=False):
    """
    Deletes a custom zone. Core zones cannot be deleted unless allow_core=True.
    """
    if zone_id in BUILTIN_BLUEPRINTS and not allow_core:
        raise ValueError(f"Cannot delete core built-in zone '{zone_id}'! You can reset it instead.")

    if zone_id in WORLD_BLUEPRINTS:
        del WORLD_BLUEPRINTS[zone_id]

    file_path = os.path.join(LEVELS_DIR, f"{zone_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False


def reset_zone_to_builtin(zone_id):
    """
    Resets an edited core zone back to its factory default built-in state
    by removing any custom JSON override file.
    """
    if zone_id not in BUILTIN_BLUEPRINTS:
        raise KeyError(f"Zone '{zone_id}' is not a built-in core zone.")

    file_path = os.path.join(LEVELS_DIR, f"{zone_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)

    WORLD_BLUEPRINTS[zone_id] = copy.deepcopy(BUILTIN_BLUEPRINTS[zone_id])
    return True


def validate_zone_blueprint(zone_id, zone_data):
    """
    Validates a zone blueprint for geometry correctness and game engine rules.
    Returns (is_valid, list_of_errors, list_of_warnings).
    """
    errors = []
    warnings = []

    if "title" not in zone_data:
        warnings.append("Missing 'title' field.")
    if "theme" not in zone_data:
        warnings.append("Missing 'theme' field; defaulting to 'canopy'.")
    elif zone_data["theme"] not in ZONE_THEMES:
        warnings.append(f"Unknown theme '{zone_data['theme']}'; fallback will be used.")

    grid = zone_data.get("ascii_grid", [])
    if not grid or len(grid) == 0:
        errors.append("ascii_grid is empty!")
        return False, errors, warnings

    rows = len(grid)
    cols = len(grid[0])
    if rows < 5:
        errors.append(f"Zone has too few rows ({rows} < 5).")
    if cols < 10:
        errors.append(f"Zone has too few columns ({cols} < 10).")

    has_spawn = False
    for r_idx, row in enumerate(grid):
        if len(row) != cols:
            errors.append(f"Row {r_idx} length mismatch ({len(row)} vs expected {cols}).")
        if 'S' in row:
            has_spawn = True

    if not has_spawn:
        warnings.append("No player spawn point ('S') found in grid; will use default (64, 64).")

    # Check door connections
    doors = zone_data.get("doors", {})
    for door_char, door_cfg in doors.items():
        # Check door character appears in grid
        found_in_grid = any(door_char in row for row in grid)
        if not found_in_grid:
            warnings.append(f"Door portal '{door_char}' is configured in doors dict but missing from ASCII grid.")

    is_valid = (len(errors) == 0)
    return is_valid, errors, warnings


def export_zone_to_ascii(zone_id):
    """Returns a clean, ready-to-paste Python ASCII code snippet for this zone."""
    zone = get_zone(zone_id)
    grid = zone.get("ascii_grid", [])
    out = []
    out.append(f"    # {zone.get('title', zone_id)}")
    out.append(f'    "{zone_id}": {{')
    out.append(f'        "title": {zone.get("title", zone_id)!r},')
    out.append(f'        "theme": {zone.get("theme", "canopy")!r},')
    out.append(f'        "bg_color": {zone.get("bg_color", (16, 28, 42))!r},')
    out.append(f'        "map_coords": {zone.get("map_coords", (0, 0))!r},')
    if "boss_trigger_x" in zone and zone["boss_trigger_x"] is not None:
        out.append(f'        "boss_trigger_x": {zone["boss_trigger_x"]},')
    if "npcs" in zone and zone["npcs"]:
        out.append('        "npcs": [')
        for npc in zone["npcs"]:
            out.append('            {')
            for k, val in npc.items():
                out.append(f'                "{k}": {val!r},')
            out.append('            },')
        out.append('        ],')
    if "doors" in zone and zone["doors"]:
        out.append('        "doors": {')
        for dchar, dcfg in zone["doors"].items():
            out.append(f'            "{dchar}": {{')
            for k, val in dcfg.items():
                out.append(f'                "{k}": {val!r},')
            out.append('            },')
        out.append('        },')
    out.append('        "ascii_grid": [')
    for row in grid:
        out.append(f'            "{row}",')
    out.append('        ],')
    out.append('    },')
    return "\n".join(out)


def sync_all_to_levels_dir(overwrite=False):
    """
    Exports all 14 built-in zones to levels/<zone_id>.json files
    so that users can inspect and tweak every room directly as standalone JSON.
    """
    os.makedirs(LEVELS_DIR, exist_ok=True)
    exported = []
    for zone_id, data in BUILTIN_BLUEPRINTS.items():
        fpath = os.path.join(LEVELS_DIR, f"{zone_id}.json")
        if not os.path.exists(fpath) or overwrite:
            save_zone(zone_id, data, save_to_disk=True)
            exported.append(zone_id)
    return exported


# Initialize on import
reload_blueprints()
