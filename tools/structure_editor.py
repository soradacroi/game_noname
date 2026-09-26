import json
import sys
from pathlib import Path
import pygame

pygame.init()

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
JSON_PATH = PROJECT_ROOT / "mods" / "base_game" / "tiles" / "tiles.json"

TILE_DEFS = {}
try:
    with open(JSON_PATH, "r", encoding="utf-8") as file:
        TILE_DEFS = json.load(file)
except FileNotFoundError:
    print(f"Error: Could not find the file at {JSON_PATH}")
except json.JSONDecodeError:
    print(f"Error: {JSON_PATH} contains invalid JSON formatting.")

GRID_COLS = 24
GRID_ROWS = 24
CELL_SIZE = 32

PANEL_WIDTH = 280
CANVAS_WIDTH = GRID_COLS * CELL_SIZE
CANVAS_HEIGHT = GRID_ROWS * CELL_SIZE

WINDOW_WIDTH = CANVAS_WIDTH + PANEL_WIDTH
WINDOW_HEIGHT = max(CANVAS_HEIGHT, 600)

BG_COLOR = (18, 18, 22)
GRID_COLOR = (35, 35, 45)
PANEL_COLOR = (28, 28, 36)
TEXT_COLOR = (220, 220, 220)
HIGHLIGHT_COLOR = (255, 215, 0)
COMMAND_COLOR = (100, 200, 255)
PANEL_HOVER_COLOR = (45, 45, 58)

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Structure Builder Tool")
clock = pygame.time.Clock()
font = pygame.font.SysFont("segoeui", 16)
font_bold = pygame.font.SysFont("segoeui", 16, bold=True)

grid_data = [[0 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]

tile_palette = [int(k) for k in TILE_DEFS.keys()]
selected_tile_idx = 0
palette_scroll_offset = 0
ITEM_HEIGHT = 26

image_cache = {}


def get_tile_image(tile_id):
    t_def = TILE_DEFS.get(str(tile_id), {})
    img_path = t_def.get("image")
    if not img_path:
        return None

    if img_path not in image_cache:
        full_img_path = PROJECT_ROOT / img_path
        if full_img_path.exists():
            img = pygame.image.load(str(full_img_path)).convert_alpha()
            image_cache[img_path] = pygame.transform.scale(img, (CELL_SIZE, CELL_SIZE))
        else:
            image_cache[img_path] = None

    return image_cache[img_path]


def export_structure(structure_name="house"):
    min_x, max_x = GRID_COLS, -1
    min_y, max_y = GRID_ROWS, -1

    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            if grid_data[y][x] != 0:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)

    if max_x == -1:
        return "Cannot save: Canvas is empty!"

    cropped_grid = []
    for y in range(min_y, max_y + 1):
        row = grid_data[y][min_x : max_x + 1]
        cropped_grid.append(row)

    output = {
        "name": structure_name,
        "width": max_x - min_x + 1,
        "height": max_y - min_y + 1,
        "tiles": cropped_grid,
    }

    export_dir = PROJECT_ROOT / "mods" / "base_game" / "structures"
    export_dir.mkdir(parents=True, exist_ok=True)

    filename = export_dir / f"{structure_name.strip()}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return f"Saved to {filename.name}"


drawing = False
erasing = False
command_mode = False
command_text = ""
status_message = "Ready"

running = True
while running:
    mouse_x, mouse_y = pygame.mouse.get_pos()
    cell_x = mouse_x // CELL_SIZE
    cell_y = mouse_y // CELL_SIZE

    palette_start_y = 200

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEWHEEL:
            if mouse_x >= CANVAS_WIDTH:
                palette_scroll_offset = max(0, palette_scroll_offset - event.y)
                max_scroll = max(0, len(tile_palette) - 10)
                palette_scroll_offset = min(palette_scroll_offset, max_scroll)

        elif event.type == pygame.KEYDOWN:
            if command_mode:
                if event.key == pygame.K_RETURN:
                    if command_text.startswith(":w "):
                        struct_name = command_text[3:].strip()
                        if struct_name:
                            status_message = export_structure(struct_name)
                        else:
                            status_message = "Error: Name required after :w"
                    elif command_text == ":w":
                        status_message = export_structure("structure")
                    else:
                        status_message = f"Unknown command: {command_text}"
                    command_mode = False
                    command_text = ""
                elif event.key == pygame.K_ESCAPE:
                    command_mode = False
                    command_text = ""
                elif event.key == pygame.K_BACKSPACE:
                    command_text = command_text[:-1]
                else:
                    command_text += event.unicode
                continue

            if event.key == pygame.K_SEMICOLON and (
                pygame.key.get_mods() & pygame.KMOD_SHIFT
            ):
                command_mode = True
                command_text = ":"
                continue

            if pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(tile_palette):
                    selected_tile_idx = idx

            elif event.key == pygame.K_c:
                grid_data = [[0 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
                status_message = "Canvas cleared"

        elif event.type == pygame.MOUSEBUTTONDOWN and not command_mode:
            if mouse_x >= CANVAS_WIDTH:
                if event.button == 1:
                    if mouse_y >= palette_start_y:
                        clicked_idx = (
                            (mouse_y - palette_start_y) // ITEM_HEIGHT
                        ) + palette_scroll_offset
                        if 0 <= clicked_idx < len(tile_palette):
                            selected_tile_idx = clicked_idx

            else:
                if event.button == 1:
                    if cell_x < GRID_COLS and cell_y < GRID_ROWS:
                        drawing = True
                        if tile_palette:
                            grid_data[cell_y][cell_x] = tile_palette[selected_tile_idx]
                elif event.button == 3:
                    if cell_x < GRID_COLS and cell_y < GRID_ROWS:
                        erasing = True
                        grid_data[cell_y][cell_x] = 0

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                drawing = False
            elif event.button == 3:
                erasing = False

    if (
        not command_mode
        and mouse_x < CANVAS_WIDTH
        and cell_x < GRID_COLS
        and cell_y < GRID_ROWS
    ):
        if drawing and tile_palette:
            grid_data[cell_y][cell_x] = tile_palette[selected_tile_idx]
        elif erasing:
            grid_data[cell_y][cell_x] = 0

    screen.fill(BG_COLOR)

    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            tile_id = grid_data[y][x]

            img = get_tile_image(tile_id)
            if img:
                screen.blit(img, rect)
            else:
                t_def = TILE_DEFS.get(str(tile_id), {})
                color = (70, 70, 70) if t_def.get("blocked") else (35, 45, 35)
                if tile_id == 0:
                    color = (25, 30, 25)
                pygame.draw.rect(screen, color, rect)

            pygame.draw.rect(screen, GRID_COLOR, rect, 1)

    if (
        cell_x < GRID_COLS
        and cell_y < GRID_ROWS
        and mouse_x < CANVAS_WIDTH
        and not command_mode
    ):
        hover_rect = pygame.Rect(
            cell_x * CELL_SIZE, cell_y * CELL_SIZE, CELL_SIZE, CELL_SIZE
        )
        pygame.draw.rect(screen, HIGHLIGHT_COLOR, hover_rect, 2)

    panel_rect = pygame.Rect(CANVAS_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT)
    pygame.draw.rect(screen, PANEL_COLOR, panel_rect)
    pygame.draw.line(
        screen, HIGHLIGHT_COLOR, (CANVAS_WIDTH, 0), (CANVAS_WIDTH, WINDOW_HEIGHT), 2
    )

    y_off = 20
    screen.blit(
        font_bold.render("STRUCTURE BUILDER", True, HIGHLIGHT_COLOR),
        (CANVAS_WIDTH + 15, y_off),
    )
    y_off += 35

    screen.blit(font.render("Controls:", True, TEXT_COLOR), (CANVAS_WIDTH + 15, y_off))
    y_off += 20
    screen.blit(
        font.render("- Left Click: Draw Tile", True, TEXT_COLOR),
        (CANVAS_WIDTH + 20, y_off),
    )
    y_off += 20
    screen.blit(
        font.render("- Right Click: Erase", True, TEXT_COLOR),
        (CANVAS_WIDTH + 20, y_off),
    )
    y_off += 20
    screen.blit(
        font.render("- Type `:w <name>` to save", True, TEXT_COLOR),
        (CANVAS_WIDTH + 20, y_off),
    )
    y_off += 20
    screen.blit(
        font.render("- [C]: Clear Grid", True, TEXT_COLOR), (CANVAS_WIDTH + 20, y_off)
    )
    y_off += 30

    screen.blit(
        font_bold.render("Tile Palette (Click/Scroll):", True, HIGHLIGHT_COLOR),
        (CANVAS_WIDTH + 15, y_off),
    )
    y_off += 25

    visible_start = palette_scroll_offset
    visible_end = min(len(tile_palette), visible_start + 12)

    for i in range(visible_start, visible_end):
        t_id = tile_palette[i]
        t_name = TILE_DEFS.get(str(t_id), {}).get("name", f"Tile {t_id}")
        is_sel = i == selected_tile_idx

        item_rect = pygame.Rect(
            CANVAS_WIDTH + 10, y_off, PANEL_WIDTH - 20, ITEM_HEIGHT - 2
        )

        if item_rect.collidepoint(mouse_x, mouse_y) and not command_mode:
            pygame.draw.rect(screen, PANEL_HOVER_COLOR, item_rect, border_radius=4)

        if is_sel:
            pygame.draw.rect(
                screen, HIGHLIGHT_COLOR, item_rect, width=1, border_radius=4
            )

        col = HIGHLIGHT_COLOR if is_sel else TEXT_COLOR
        prefix = "> " if is_sel else "  "

        lbl = font.render(f"{prefix}{t_id} : {t_name}", True, col)
        screen.blit(lbl, (CANVAS_WIDTH + 15, y_off + 2))
        y_off += ITEM_HEIGHT

    pygame.draw.rect(screen, (15, 15, 20), (0, CANVAS_HEIGHT - 30, CANVAS_WIDTH, 30))
    if command_mode:
        cmd_surf = font.render(command_text, True, COMMAND_COLOR)
        screen.blit(cmd_surf, (10, CANVAS_HEIGHT - 25))
    else:
        status_surf = font.render(f"Status: {status_message}", True, TEXT_COLOR)
        screen.blit(status_surf, (10, CANVAS_HEIGHT - 25))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
