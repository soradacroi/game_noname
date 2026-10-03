import pygame
import sys
import esper
from config import *
from ecs import (
    RenderSystem,
    Position,
    Name,
    UIManager,
    TileMap,
    ChunkManager,
)

from systems.interaction import InteractionManager
from mod_loader import ModLoader
from systems.detection import perform_detection
from systems.movement import player_movement
from systems.world_gen import WorldGenerator
import random


debug = "d" in sys.argv
send_seed = 0
if "s" in sys.argv:
    try:
        s_index = sys.argv.index("s")
        send_seed = int(sys.argv[s_index + 1])
    except (ValueError, IndexError):
        send_seed = 0

saved_chunk_data = {}


def main():
    seed = send_seed
    random.seed(seed)

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()

    loader = ModLoader()
    loader.load_mods()

    world_gen = WorldGenerator(seed=seed, chunk_size=16)

    tile_map = TileMap(world_generator=world_gen, tile_defs=loader.tile_defs)
    chunk_manager = ChunkManager(chunk_size=16)
    spatial_hash = {}
    ui = UIManager()
    ui.options_text = "Press WASD to move."

    render_sys = RenderSystem(screen, ui, tile_map)
    esper.add_processor(render_sys, priority=1)

    player = loader.spawn_entity("player", 50, 50)
    goblin_id = loader.spawn_entity("goblin", 52, 50)
    chunk_manager.add_entity(goblin_id, 52, 50)
    chest_id = loader.spawn_entity("chest", 52, 49)
    chunk_manager.add_entity(chest_id, 52, 49)

    interaction_mode = False
    pending_interaction_target = None
    available_actions = {}

    for ent, pos in esper.get_component(Position):
        spatial_hash.setdefault((pos.x, pos.y), []).append(ent)

    perform_detection(50, 50, player, spatial_hash, tile_map, ui)

    steps = 1
    running = True
    MOVE_DELAY = 150
    last_move = 0
    pressed_keys = []

    valid_keys = (pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d)
    if debug:
        valid_keys += (pygame.K_j, pygame.K_k, pygame.K_1, pygame.K_0)

    while running:
        dx, dy = 0, 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # reset everything here when press esc
                    pending_interaction_target = None
                    interaction_mode = False
                    pressed_keys.clear()
                    ui.log("pressed escape reseted everything")

                # MENU HANDLING
                if pending_interaction_target is not None:
                    if event.unicode in available_actions:
                        #  menu key pressed (a, b, c)
                        InteractionManager.execute_action(
                            event.unicode, pending_interaction_target, ui
                        )
                        pending_interaction_target = None
                        interaction_mode = False
                        pressed_keys.clear()
                    continue  # Skip normal key processing while in a menu

                # NORMAL KEY HANDLING
                if event.key == pygame.K_i:
                    interaction_mode = not interaction_mode
                    ui.log(f"interaction mode is {'on' if interaction_mode else 'off'}")
                elif event.key in valid_keys:
                    if event.key not in pressed_keys:
                        pressed_keys.append(event.key)
            elif event.type == pygame.KEYUP:
                if event.key in pressed_keys:
                    pressed_keys.remove(event.key)

        now = pygame.time.get_ticks()
        wait_time = now - last_move

        # only process movement/targeting if we aren't waiting for a menu choice
        if (
            pending_interaction_target is None
            and pressed_keys
            and wait_time >= MOVE_DELAY
        ):
            key = pressed_keys[-1]

            if key == pygame.K_w:
                dy = -steps
            elif key == pygame.K_s:
                dy = steps
            elif key == pygame.K_a:
                dx = -steps
            elif key == pygame.K_d:
                dx = steps

            # debug stuff
            elif debug and key == pygame.K_j:
                render_sys.set_cell_size(render_sys.CELL_SIZE - 1)
            elif debug and key == pygame.K_k:
                render_sys.set_cell_size(render_sys.CELL_SIZE + 1)
            elif debug and key == pygame.K_0:
                steps -= 1
            elif debug and key == pygame.K_1:
                steps += 1

            if dx != 0 or dy != 0:
                if interaction_mode:
                    # target a direction
                    target = InteractionManager.get_target(
                        player, dx, dy, spatial_hash, ui
                    )

                    if target is None:
                        interaction_mode = False

                        ui.log("interaction mode is off")

                    else:
                        actions = InteractionManager.get_available_actions(target)
                        if not actions:
                            ui.log("Nothing happens")
                            interaction_mode = False
                            ui.log("interaction mode is off")

                        else:
                            # Show the menu in the logs and wait
                            ui.log("What do you want to do? (Press key or ESC)")
                            for k_letter, a_name in actions.items():
                                ui.log(f"[{k_letter}] - {a_name}")
                            pending_interaction_target = target
                            available_actions = actions
                else:
                    player_movement(tile_map, dy, dx, spatial_hash, ui)

                last_move = now

        if wait_time >= MOVE_DELAY:
            if player is not None:
                player_pos = esper.component_for_entity(player, Position)

                to_load, to_unload = chunk_manager.update_loaded_area(
                    player_pos.x, player_pos.y, radius=1
                )

                # UNLOAD
                for cx, cy in to_unload:
                    if (cx, cy) not in chunk_manager.chunk_entities:
                        continue

                    chunk_entities_to_save = []
                    for ent_id in list(chunk_manager.chunk_entities[(cx, cy)]):
                        if ent_id == player or not esper.has_component(
                            ent_id, Position
                        ):
                            continue

                        components = esper.components_for_entity(ent_id)
                        chunk_entities_to_save.append(components)

                        pos = esper.component_for_entity(ent_id, Position)
                        grid_key = (pos.x, pos.y)
                        if (
                            grid_key in spatial_hash
                            and ent_id in spatial_hash[grid_key]
                        ):
                            spatial_hash[grid_key].remove(ent_id)

                        esper.delete_entity(ent_id)

                    saved_chunk_data[(cx, cy)] = chunk_entities_to_save
                    del chunk_manager.chunk_entities[(cx, cy)]

                # LOAD
                for cx, cy in to_load:
                    chunk_manager.chunk_entities[(cx, cy)] = set()

                    if (cx, cy) in saved_chunk_data:
                        for saved_components in saved_chunk_data[(cx, cy)]:
                            new_ent = esper.create_entity(*saved_components)

                            pos = esper.component_for_entity(new_ent, Position)
                            chunk_manager.add_entity(new_ent, pos.x, pos.y)
                            spatial_hash.setdefault((pos.x, pos.y), []).append(new_ent)

                    elif random.random() < 0.10:
                        spawn_x = (cx * chunk_manager.chunk_size) + 8
                        spawn_y = (cy * chunk_manager.chunk_size) + 8
                        new_gob = loader.spawn_entity("goblin", spawn_x, spawn_y)
                        chunk_manager.add_entity(new_gob, spawn_x, spawn_y)
                        spatial_hash.setdefault((spawn_x, spawn_y), []).append(new_gob)

        esper.process()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
