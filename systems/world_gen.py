import math
import random


class WorldGenerator:
    """Generates procedural world chunks using layered Perlin-like noise.

    Supports dynamic bounds (0 to 2000+), biome elevation thresholds, and easy
    extensibility for future biomes like mountains, forests, etc.
    """

    def __init__(self, seed=0, chunk_size=16, world_width=2000, world_height=2000):
        self.seed = seed
        self.chunk_size = chunk_size
        self.world_width = world_width
        self.world_height = world_height

        self.TILE_WALL = 1
        self.TILE_WATER = 0
        self.TILE_SAND = 3
        self.TILE_GRASS = 2

        self._init_noise_perm()

    def _init_noise_perm(self):
        """Initializes a deterministic permutation table for noise generation."""
        rng = random.Random(self.seed)
        p = list(range(256))
        rng.shuffle(p)
        self.perm = p * 2

    def _fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _lerp(self, a, b, t):
        return a + t * (b - a)

    def _grad(self, hash_val, x, y):
        h = hash_val & 7
        u = x if h < 4 else y
        v = y if h < 4 else x
        return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)

    def noise2d(self, x, y):
        """Standard 2D Perlin Noise implementation (returns values in roughly [-1, 1])."""
        X = int(math.floor(x)) & 255
        Y = int(math.floor(y)) & 255

        x -= math.floor(x)
        y -= math.floor(y)

        u = self._fade(x)
        v = self._fade(y)

        p = self.perm
        A = p[X] + Y
        B = p[X + 1] + Y

        return self._lerp(
            self._lerp(self._grad(p[A], x, y), self._grad(p[B], x - 1, y), u),
            self._lerp(
                self._grad(p[A + 1], x, y - 1),
                self._grad(p[B + 1], x - 1, y - 1),
                u,
            ),
            v,
        )

    def get_elevation(self, world_x, world_y):
        """Combines multiple octaves of noise to determine terrain height.

        Returns a normalized value between 0.0 and 1.0.
        """
        scale = 0.015

        # Octave 1: Main
        n1 = self.noise2d(world_x * scale, world_y * scale)
        # Octave 2: Smaller pond
        n2 = self.noise2d(world_x * scale * 2.5, world_y * scale * 2.5) * 0.5
        # Octave 3: Fine variation
        n3 = self.noise2d(world_x * scale * 5.0, world_y * scale * 5.0) * 0.25

        total = (n1 + n2 + n3) / (1.0 + 0.5 + 0.25)

        normalized = (total + 1.0) / 2.0
        return max(0.0, min(1.0, normalized))

    def get_moisture(self, world_x, world_y):
        """Secondary noise map for biomes like forests, swamps, or deserts later."""
        scale = 0.02
        # Offset coordinates so moisture doesn't perfectly mirror elevation
        n = self.noise2d(
            (world_x + 5000) * scale,
            (world_y + 5000) * scale,
        )
        return max(0.0, min(1.0, (n + 1.0) / 2.0))

    def get_tile_type(self, world_x, world_y):
        """Maps coordinate height and moisture to tile IDs.

        Bounds the 2000x2000 world with deep water to keep player inside bounds.
        """
        if (
            world_x < 0
            or world_x >= self.world_width
            or world_y < 0
            or world_y >= self.world_height
        ):
            return self.TILE_WATER

        elevation = self.get_elevation(world_x, world_y)
        moisture = self.get_moisture(world_x, world_y)

        if elevation < 0.30:
            return self.TILE_WATER
        elif elevation < 0.33:
            return self.TILE_SAND
        else:
            # mountains and stuff
            # if elevation > 0.82:
            #     return self.TILE_SNOW
            # elif elevation > 0.72:
            #     return self.TILE_MOUNTAIN
            # elif moisture > 0.65:
            #     return self.TILE_FOREST

            return self.TILE_GRASS

    def generate_chunk(self, cx, cy):
        """Generates a 2D list grid of tile IDs for chunk (cx, cy)."""
        grid = []
        start_x = cx * self.chunk_size
        start_y = cy * self.chunk_size

        for ly in range(self.chunk_size):
            row = []
            for lx in range(self.chunk_size):
                world_x = start_x + lx
                world_y = start_y + ly
                tile_id = self.get_tile_type(world_x, world_y)
                row.append(tile_id)
            grid.append(row)

        return grid
