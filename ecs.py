import esper
import pygame
import os
import re
from config import *
import random


# entity propertys
class Position:
    def __init__(self, x=0, y=0):
        self.x, self.y = x, y


class Renderable:
    def __init__(self, char="?", color=(255, 255, 255), layer=0, image=None):
        self.char, self.color, self.layer, self.image = char, color, layer, image


class Blocker:
    pass


class NonDetectable:
    def __init__(self, WHAT) -> None:
        self.WHAT = WHAT


class PlayerInput:
    pass


# Interaction stuff
class Talkable:
    def __init__(self, message="..."):
        self.message = message


class Openable:
    def __init__(self, is_open=False, locked=False):
        self.is_open = is_open
        self.locked = locked


class Pushable:
    def __init__(self, weight=10):
        self.weight = weight


"""
class InteractionMode:
    def __init__(self):
        self.active = False

    def toggle(self):
        self.active = not self.active
"""


class Interaction:
    def __init__(self, type, message=None):
        self.type = type
        self.message = message


class Name:
    def __init__(self, text="Unknown"):
        self.text = text


# logs and ui
class UIManager:
    def __init__(self):
        self.logs = []
        self.options_text = ""

    def log(self, msg):
        self.logs.insert(0, msg)
        if len(self.logs) > 40:
            self.logs.pop()


class TileMap:
    def __init__(self, world_generator, tile_defs=None):
        self.world_gen = world_generator
        self.chunk_size = world_generator.chunk_size
        self.tile_defs = tile_defs or {}

        # Store chunks dynamically: {(cx, cy): {"grid": [...], "variants": [...]}}
        self.chunks = {}

    def _choose_variant(self, tile_type):
        tile_def = self.tile_defs.get(tile_type, {})
        variants = tile_def.get("variants", [])
        if not variants:
            return None
        weights = [variant.get("weight", 1) for variant in variants]
        return random.choices(range(len(variants)), weights=weights, k=1)[0]

    def load_chunk(self, cx, cy):
        """Generates and caches a chunk if it doesn't exist."""
        if (cx, cy) not in self.chunks:
            grid = self.world_gen.generate_chunk(cx, cy)
            variants = [
                [self._choose_variant(tile_id) for tile_id in row] for row in grid
            ]
            self.chunks[(cx, cy)] = {"grid": grid, "variants": variants}

    def _get_local_coords(self, x, y):
        cx, cy = x // self.chunk_size, y // self.chunk_size
        lx, ly = x % self.chunk_size, y % self.chunk_size
        self.load_chunk(cx, cy)  # Ensure it exists
        return cx, cy, lx, ly

    def get_tile_id(self, x, y):
        cx, cy, lx, ly = self._get_local_coords(x, y)
        return self.chunks[(cx, cy)]["grid"][ly][lx]

    def get_tile_variant(self, x, y):
        cx, cy, lx, ly = self._get_local_coords(x, y)
        return self.chunks[(cx, cy)]["variants"][ly][lx]

    def get_tile_def(self, x, y):
        tid = self.get_tile_id(x, y)
        return self.tile_defs.get(tid)

    def set_tile(self, x, y, tile_type):
        cx, cy, lx, ly = self._get_local_coords(x, y)
        self.chunks[(cx, cy)]["grid"][ly][lx] = tile_type
        self.chunks[(cx, cy)]["variants"][ly][lx] = self._choose_variant(tile_type)

    def is_blocked(self, x, y):
        t_def = self.get_tile_def(x, y)
        if t_def is not None:
            return t_def.get("blocked", False)
        return False


class ChunkManager:
    def __init__(self, chunk_size=16):
        self.chunk_size = chunk_size
        self.loaded_chunks = set()
        self.chunk_entities = {}  # maps (cx, cy) -> set of entity ID

    def get_chunk_coords(self, x, y):
        return x // self.chunk_size, y // self.chunk_size

    def add_entity(self, entity_id, x, y):
        """Clean API to add an entity to the correct chunk."""
        cx, cy = self.get_chunk_coords(x, y)
        if (cx, cy) not in self.chunk_entities:
            self.chunk_entities[(cx, cy)] = set()
        self.chunk_entities[(cx, cy)].add(entity_id)

    def remove_entity(self, entity_id, x, y):
        """Clean API to remove an entity from a chunk (e.g., when they die)."""
        cx, cy = self.get_chunk_coords(x, y)
        if (cx, cy) in self.chunk_entities:
            self.chunk_entities[(cx, cy)].discard(entity_id)

    def update_loaded_area(self, player_x, player_y, radius=1):
        player_cx, player_cy = self.get_chunk_coords(player_x, player_y)

        new_loaded_chunks = set()
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                new_loaded_chunks.add((player_cx + dx, player_cy + dy))

        chunks_to_load = new_loaded_chunks - self.loaded_chunks
        chunks_to_unload = self.loaded_chunks - new_loaded_chunks
        self.loaded_chunks = new_loaded_chunks

        return chunks_to_load, chunks_to_unload


class RenderSystem(esper.Processor):
    def __init__(self, screen, ui_manager, tile_map, CELL_SIZE=CELL_SIZE):
        self.screen = screen
        self.ui = ui_manager
        self.tile_map = tile_map
        self.font = pygame.font.SysFont("segoeuiemoji", 16)
        self.font_bold = pygame.font.SysFont("segoeuiemoji", 16, bold=True)
        self.image_cache = {}
        self.tileset_cache = {}
        self.tile_cache = {}
        self.text_surface_cache = {}

        self.cam_x = 0.0
        self.cam_y = 0.0
        self.camera_speed = 0.12
        self.CELL_SIZE = CELL_SIZE

        self.sorted_tags = sorted(TEXT_STYLES.keys(), key=len, reverse=True)
        regex_parts = [
            f"{re.escape(tag)}.*?{re.escape(tag)}" for tag in self.sorted_tags
        ]
        self.rich_text_regex = re.compile(f"({'|'.join(regex_parts)})")

    def get_image(self, img_path):
        if not img_path:
            return None
        if img_path not in self.image_cache:
            if os.path.exists(img_path):
                img = pygame.image.load(img_path).convert_alpha()
                self.image_cache[img_path] = pygame.transform.scale(
                    img, (self.CELL_SIZE, self.CELL_SIZE)
                )
            else:
                self.image_cache[img_path] = None
        return self.image_cache[img_path]

    def get_tileset(self, path):
        if not path:
            return None
        if path not in self.tileset_cache:
            if os.path.exists(path):
                self.tileset_cache[path] = pygame.image.load(path).convert_alpha()
            else:
                self.tileset_cache[path] = None
        return self.tileset_cache[path]

    def get_tile_image(self, tile_def, variant_index, tile_id):
        cache_key = (tile_id, variant_index, self.CELL_SIZE)

        if cache_key not in self.tile_cache:
            variants = tile_def.get("variants", [])
            if variant_index is None or variant_index >= len(variants):
                return None
            sheet = self.get_tileset(tile_def.get("tileset"))
            if not sheet:
                return None

            variant = variants[variant_index]
            tile_size = tile_def.get("tile_size", 32)
            rect = pygame.Rect(
                variant["x"] * tile_size, variant["y"] * tile_size, tile_size, tile_size
            )
            sub = sheet.subsurface(rect)
            self.tile_cache[cache_key] = pygame.transform.scale(
                sub, (self.CELL_SIZE, self.CELL_SIZE)
            )

        return self.tile_cache[cache_key]

    def set_cell_size(self, new_size):
        self.CELL_SIZE = max(8, min(64, new_size))
        self.image_cache.clear()
        self.tile_cache.clear()

    def process(self):
        self.screen.fill(BG_MAIN)
        self.draw_map()
        self.draw_ui()
        pygame.display.flip()

    def draw_map(self):
        map_rect = pygame.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT)
        self.screen.set_clip(map_rect)

        target_cam_x = 0
        target_cam_y = 0
        for ent, (pos, _) in esper.get_components(Position, PlayerInput):
            target_cam_x = (
                (pos.x * self.CELL_SIZE) - (MAP_WIDTH // 2) + (self.CELL_SIZE // 2)
            )
            target_cam_y = (
                (pos.y * self.CELL_SIZE) - (MAP_HEIGHT // 2) + (self.CELL_SIZE // 2)
            )

        self.cam_x += (target_cam_x - self.cam_x) * self.camera_speed
        self.cam_y += (target_cam_y - self.cam_y) * self.camera_speed

        offset_x = int(self.cam_x)
        offset_y = int(self.cam_y)

        start_col = offset_x // self.CELL_SIZE - 1
        end_col = (offset_x + MAP_WIDTH) // self.CELL_SIZE + 2
        start_row = offset_y // self.CELL_SIZE - 1
        end_row = (offset_y + MAP_HEIGHT) // self.CELL_SIZE + 2

        for ty in range(start_row, end_row):
            for tx in range(start_col, end_col):
                t_def = self.tile_map.get_tile_def(tx, ty)

                draw_x = (tx * self.CELL_SIZE) - offset_x
                draw_y = (ty * self.CELL_SIZE) - offset_y
                rect = pygame.Rect(draw_x, draw_y, self.CELL_SIZE, self.CELL_SIZE)

                if t_def:
                    if t_def.get("tileset"):
                        tile_id = self.tile_map.get_tile_id(tx, ty)
                        img = self.get_tile_image(
                            t_def, self.tile_map.get_tile_variant(tx, ty), tile_id
                        )
                    else:
                        img = self.get_image(t_def.get("image"))

                    if img:
                        self.screen.blit(img, rect)
                    else:
                        is_blocked = t_def.get("blocked", False)
                        fallback_color = (60, 60, 60) if is_blocked else (34, 70, 34)
                        pygame.draw.rect(self.screen, fallback_color, rect)
                        char = "#" if is_blocked else "."
                        txt = self.font.render(char, True, (120, 120, 120))
                        self.screen.blit(txt, txt.get_rect(center=rect.center))
                else:
                    pygame.draw.rect(self.screen, (0, 0, 0), rect)

        visible_entities = []
        for ent, (pos, rend) in esper.get_components(Position, Renderable):
            draw_x = (pos.x * self.CELL_SIZE) - offset_x
            draw_y = (pos.y * self.CELL_SIZE) - offset_y

            if (
                -self.CELL_SIZE <= draw_x <= MAP_WIDTH
                and -self.CELL_SIZE <= draw_y <= MAP_HEIGHT
            ):
                visible_entities.append((draw_x, draw_y, rend))

        # Sort ONLY the visible entities
        visible_entities.sort(key=lambda item: item[2].layer)

        for draw_x, draw_y, rend in visible_entities:
            rect = pygame.Rect(draw_x, draw_y, self.CELL_SIZE, self.CELL_SIZE)
            img = self.get_image(rend.image) if rend.image else None
            if img:
                self.screen.blit(img, rect)
            else:
                text_surf = self.font.render(rend.char, True, rend.color)
                self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

        self.screen.set_clip(None)

    def draw_ui(self):
        # World Events Panel
        pygame.draw.rect(
            self.screen, BG_LOGS, (LOG_PANEL_X, 0, LOG_PANEL_WIDTH, LOG_PANEL_HEIGHT)
        )
        pygame.draw.line(
            self.screen, C_WHITE, (LOG_PANEL_X, 0), (LOG_PANEL_X, LOG_PANEL_HEIGHT), 2
        )
        self.screen.blit(
            self.font_bold.render("WORLD EVENTS", True, C_BLUE), (LOG_PANEL_X + 10, 10)
        )

        curr_y = 40
        log_width = LOG_PANEL_WIDTH - 20

        # Draw cached log surfaces
        for msg in self.ui.logs:
            cache_key = (msg, log_width)
            if cache_key not in self.text_surface_cache:
                self.text_surface_cache[cache_key] = self.render_rich_surface(
                    msg, log_width
                )

            surf = self.text_surface_cache[cache_key]
            if curr_y + surf.get_height() > LOG_PANEL_HEIGHT:
                break
            self.screen.blit(surf, (LOG_PANEL_X + 10, curr_y))
            curr_y += surf.get_height() + 6

        # Options / Action Panel
        pygame.draw.rect(
            self.screen, BG_OPTS, (0, OPT_PANEL_Y, OPT_PANEL_WIDTH, OPT_PANEL_HEIGHT)
        )
        pygame.draw.line(
            self.screen, C_WHITE, (0, OPT_PANEL_Y), (OPT_PANEL_WIDTH, OPT_PANEL_Y), 2
        )
        self.screen.blit(
            self.font_bold.render("ACTIONS / INFO", True, C_BLUE),
            (10, OPT_PANEL_Y + 10),
        )

        if self.ui.options_text:
            opt_width = OPT_PANEL_WIDTH - 20
            cache_key = (self.ui.options_text, opt_width)
            if cache_key not in self.text_surface_cache:
                self.text_surface_cache[cache_key] = self.render_rich_surface(
                    self.ui.options_text, opt_width
                )
            opt_surf = self.text_surface_cache[cache_key]
            self.screen.blit(opt_surf, (10, OPT_PANEL_Y + 40))

    def render_rich_surface(self, text, max_width):
        """Renders rich-text tokens ONCE into a pygame.Surface with line-wrapping."""
        tokens = []
        parts = self.rich_text_regex.split(text)

        for part in parts:
            if not part:
                continue
            color, font, clean_part = C_WHITE, self.font, part

            for tag in self.sorted_tags:
                if (
                    part.startswith(tag)
                    and part.endswith(tag)
                    and len(part) >= len(tag) * 2
                ):
                    style = TEXT_STYLES[tag]
                    color = style["color"]
                    font = self.font_bold if style.get("bold") else self.font
                    clean_part = part[len(tag) : -len(tag)]
                    break

            for w in clean_part.split(" "):
                tokens.append((w + " ", font, color))

        lines = []
        current_line = []
        current_line_width = 0

        for word, font, color in tokens:
            word_surf = font.render(word, True, color)
            w_w = word_surf.get_width()

            if current_line_width + w_w > max_width and current_line:
                lines.append(current_line)
                current_line = []
                current_line_width = 0

            current_line.append((word_surf, w_w))
            current_line_width += w_w

        if current_line:
            lines.append(current_line)

        line_height = 20
        total_height = max(line_height, len(lines) * line_height)

        surf = pygame.Surface((max_width, total_height), pygame.SRCALPHA)
        y = 0
        for line in lines:
            x = 0
            for word_surf, w_w in line:
                surf.blit(word_surf, (x, y))
                x += w_w
            y += line_height

        return surf
