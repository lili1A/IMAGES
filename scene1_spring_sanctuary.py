"""
Scene 1 - Spring Sanctuary
===========================
Bloomie wakes up in a cherry blossom garden partially corrupted by The Wilt.
This scene is the game's tutorial: move, jump, collect petals to charge the
Healing Bloom meter, and heal wilted flowers to bring the garden back to
life. Healing a flower spawns grass/butterflies/petals and, for the two
flowers guarding crumbled sections of path, grows a magical platform that
lets Bloomie keep advancing. Once every flower is healed, a rising platform
carries Bloomie up to a floating gem; collecting it plays a short memory
that introduces the boss before the level-complete screen.

Run with:
    pip install pygame pillow
    python3 "scene1_spring_sanctuary.py"

This file must stay in the same folder as the "ISE " and "Imaging Movements"
asset folders (same place as bloomie_animations.py / wilt_animations.py) -
assets are located automatically by filename, so no paths need to be edited.

Asset -> usage map (from the storyboard / asset notes)
--------------------------------------------------------
ISE /Scene 1/Spring Sanctuary Background .png   -> scrolling level background
ISE /Scene 1/Sakura Flower.png                  -> wilted flower -> full bloom
                                                    (small/desaturated while
                                                    wilted, procedurally grows
                                                    to full size/color on heal;
                                                    Blloming Flower Animation.gif
                                                    is missing from the asset
                                                    folder, so this static image
                                                    + tween replaces it)
ISE /Scene 1/Grass Texture .png                 -> appears once a flower heals
ISE /Scene 1/Sakura Petal Single.png            -> petal pickups, the heal
                                                    burst effect, and the
                                                    level-complete petal drift
ISE /Scene 1/Butterfly Sprite .png              -> spawns after a flower heals
ISE /Scene 2/Crystal Activation Animation .gif  -> the end-of-level gem
ISE /Sounds/Spring Garden Theme Scene 1.mp3     -> scene BGM
ISE /Sounds/Bloomie Greeting Scene 1.mp3        -> plays on the title/intro card
ISE /Sounds/Butterfly Spawn Sound  Scene 1.mp3  -> plays when a butterfly spawns
ISE /Sounds/Flower Bloom Sound Scene 1, 4 .mp3  -> plays when a flower finishes healing
ISE /Sounds/Crystal Activation Sound Scene 2.mp3-> plays when the gem is collected
Imaging Movements/Bloomie/*                     -> Bloomie idle/walk/jump/heal frames
Imaging Movements/Wilt/Wilt BG REMOVED.png      -> Wilt's corrupted idle pose
Imaging Movements/Wilt/Evil Appearance/*        -> Wilt's corruption reaction
Imaging Movements/Wilt/Ultimate Attack/*        -> looms in the boss-intro memory

Note: the asset folder's "Characters" set (which would normally hold a
dedicated boss portrait) isn't present, so the memory-playback ending uses
Wilt's own imagery, scaled up dramatically, to tease the boss instead.
"""

import os
import sys
import math
import random
import pygame

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import numpy as np
except ImportError:
    np = None


# ---------------------------------------------------------------------------
# Setup & constants
# ---------------------------------------------------------------------------

pygame.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass  # no audio device available - the scene still runs silently

ASSET_DIR = os.path.dirname(os.path.abspath(__file__))

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 576
FPS = 60

GRAVITY = 0.75
MOVE_SPEED = 4.5
JUMP_SPEED = -14.5

GROUND_Y = SCREEN_HEIGHT - 90
LEVEL_WIDTH = 3600

BLOOMIE_SIZE = (120, 120)   # used for Bloomie's collision hitbox only
BLOOMIE_HEIGHT = 140        # rendered sprite height (see load_character_frame)
WILT_HEIGHT = 210           # rendered sprite height for Wilt
BUTTERFLY_SIZE = (46, 46)
GRASS_SIZE = (140, 60)
FLOWER_SIZE = (110, 90)
PETAL_SPRITE_SIZE = 40      # base size of the single-petal sprite (scaled per use)
GEM_SIZE = (70, 90)

# Healing Bloom is fuelled by petals: the meter fills as Bloomie collects
# them, lights up as "boosted" once it passes BOOST, and Healing Bloom can
# only be used once the meter is completely FULL (it then empties back to
# zero, so the next heal needs a fresh 10 petals).
HEAL_METER_FULL = 10
HEAL_METER_BOOST = 3

WHITE = (255, 255, 255)
CREAM = (255, 248, 235)
PINK = (255, 182, 210)
DARK_PINK = (200, 90, 140)
CORRUPT_PURPLE = (90, 60, 110)
SKY_TOP = (255, 214, 232)
SKY_BOTTOM = (255, 244, 226)


# ---------------------------------------------------------------------------
# Asset index - find every file once by name so we never have to hardcode
# fragile absolute paths (several asset folders on disk are duplicated).
# ---------------------------------------------------------------------------

_FILE_INDEX = {}
for _root, _dirs, _files in os.walk(ASSET_DIR):
    for _f in _files:
        _FILE_INDEX.setdefault(_f, os.path.join(_root, _f))


def find_asset(filename):
    path = _FILE_INDEX.get(filename)
    if path is None:
        raise FileNotFoundError(f"Could not find asset '{filename}' under {ASSET_DIR}")
    return path


def _placeholder_image(size):
    """A bright, obviously-a-placeholder image used when an expected asset
    file can't be found, so a missing/moved file degrades gracefully
    instead of crashing the whole scene."""
    w, h = size if size else (64, 64)
    surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    surf.fill((255, 0, 200, 120))
    pygame.draw.rect(surf, (255, 255, 255, 200), surf.get_rect(), 2)
    return surf


_image_cache = {}


def load_image(filename, size=None):
    key = (filename, size)
    if key in _image_cache:
        return _image_cache[key]
    try:
        img = pygame.image.load(find_asset(filename)).convert_alpha()
    except FileNotFoundError:
        print(f"[scene1] WARNING: '{filename}' is missing from the asset "
              f"folder - using a placeholder image instead.")
        img = _placeholder_image(size)
        _image_cache[key] = img
        return img
    if size is not None:
        img = pygame.transform.smoothscale(img, size)
    _image_cache[key] = img
    return img


def _frame_has_real_alpha(pil_img, threshold=0.6):
    """
    Sample the border of an RGBA frame. A majority (not just one) of the
    sampled border pixels must be meaningfully transparent before we assume
    a frame already has a genuine cut-out background. Requiring only a
    single non-opaque sample is wrong: a limb, foot, or hair strand can
    easily poke into one sample point in a walk/jump pose while the rest of
    that same frame's border is still a solid baked-in background - which
    made cleanup randomly skip on just some frames of an animation. That's
    exactly what shows up as flashing/twitching, since neighboring frames
    that DO get cleaned suddenly look different.
    """
    w, h = pil_img.size
    if w == 0 or h == 0:
        return True
    alpha = pil_img.split()[-1]
    xs = [0, w // 4, w // 2, (3 * w) // 4, w - 1]
    ys = [0, h // 4, h // 2, (3 * h) // 4, h - 1]
    points = set()
    for x in xs:
        points.add((x, 0))
        points.add((x, h - 1))
    for y in ys:
        points.add((0, y))
        points.add((w - 1, y))
    transparent = sum(1 for pt in points if alpha.getpixel(pt) < 250)
    return (transparent / len(points)) >= threshold


def _auto_key_out_background(pil_img, tolerance=34, feather=40):
    """
    Removes a flat/solid baked-in background from a character frame that
    has no real alpha channel, using the border color as the reference
    background color. Produces a soft (anti-aliased) alpha edge via
    `feather` so the cutout doesn't look jagged or pop between frames.
    Requires numpy; returns the image unchanged if numpy isn't installed.
    """
    if np is None:
        return pil_img
    arr = np.array(pil_img).astype(np.int16)
    border = np.concatenate([
        arr[0, :, :3], arr[-1, :, :3], arr[:, 0, :3], arr[:, -1, :3]
    ], axis=0)
    bg_color = np.median(border, axis=0)
    diff = np.sqrt(((arr[:, :, :3] - bg_color) ** 2).sum(axis=2))
    low, high = tolerance, tolerance + feather
    keep_alpha = np.clip((diff - low) / max(1e-6, (high - low)), 0.0, 1.0) * 255
    arr[:, :, 3] = np.minimum(arr[:, :, 3], keep_alpha).astype(np.int16)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


_character_frame_cache = {}


def load_character_frame(filename, target_height):
    """
    Load a single character-animation frame, cropped to its actual (non-
    transparent) content and scaled by height, preserving aspect ratio.

    Two separate problems were stacked here:
    1) The Bloomie/Wilt frame PNGs were exported at inconsistent canvas
       sizes (some 2048x2048, some ~300x400) with very different amounts of
       empty transparent padding. Naively stretching every frame to one
       fixed WxH box makes the character visibly pop/resize between frames.
    2) Some individual frames don't have a real cut-out alpha channel at
       all (still a solid baked-in background), while sibling frames in the
       same animation do - swapping between "properly transparent" and
       "solid background box" frames reads as flashing/twitching.
    Fixing only #1 (content-crop + scale-by-height) isn't enough on its own
    if #2 is also present, so frames without real alpha are auto-keyed out
    first, then cropped to content and scaled by height - keeping the
    character a consistent size, consistent foot position, and consistent
    background across every frame regardless of source quirks.
    """
    key = (filename, target_height)
    if key in _character_frame_cache:
        return _character_frame_cache[key]

    try:
        path = find_asset(filename)
    except FileNotFoundError:
        print(f"[scene1] WARNING: '{filename}' is missing from the asset "
              f"folder - using a placeholder image instead.")
        surf = _placeholder_image((target_height, target_height))
        _character_frame_cache[key] = surf
        return surf

    if Image is not None:
        pil_img = Image.open(path).convert("RGBA")
        if np is not None and not _frame_has_real_alpha(pil_img):
            pil_img = _auto_key_out_background(pil_img)
        alpha_bbox = pil_img.split()[-1].getbbox()
        if alpha_bbox is not None:
            pil_img = pil_img.crop(alpha_bbox)
        scale = target_height / pil_img.height
        target_w = max(1, round(pil_img.width * scale))
        pil_img = pil_img.resize((target_w, target_height), Image.LANCZOS)
        surf = pygame.image.fromstring(pil_img.tobytes(), pil_img.size, "RGBA").convert_alpha()
    else:
        # Fallback without Pillow: no content-cropping available, so just
        # scale the raw canvas to a square of the target height.
        surf = pygame.image.load(path).convert_alpha()
        surf = pygame.transform.smoothscale(surf, (target_height, target_height))

    _character_frame_cache[key] = surf
    return surf


def petal_image(size=PETAL_SPRITE_SIZE):
    """The single clean petal sprite (Sakura Petal Single.png), scaled to a
    size x size box. Every petal effect (pickups, heal burst, level-complete
    drift) reuses this one asset and gets its variety from random rotation
    and scale at draw time instead of from the source art."""
    return load_image("Sakura Petal Single.png", (size, size))


_gif_cache = {}


def _placeholder_gif_frames(size):
    """A simple animated stand-in (a bud growing into a bloom) used when a
    gif asset can't be loaded at all - either Pillow isn't installed, or the
    file is missing from disk - so a missing asset degrades gracefully
    instead of crashing the whole scene."""
    w, h = size or (100, 100)
    frames = []
    steps = 12
    for i in range(steps):
        t = i / (steps - 1)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        radius = int(min(w, h) * (0.15 + 0.35 * t))
        color = (int(150 + 90 * t), int(150 + 60 * t), int(160 + 60 * t))
        pygame.draw.circle(surf, color, (w // 2, int(h * 0.75)), radius)
        frames.append((surf, 120))
    return frames


def load_gif_frames(filename, size=None):
    """Return a list of (pygame.Surface, duration_ms) for an animated GIF."""
    key = (filename, size)
    if key in _gif_cache:
        return _gif_cache[key]

    if Image is None:
        # Pillow isn't installed - fall back to a placeholder animation so
        # the scene still runs (pip install pillow to get the real one).
        frames = _placeholder_gif_frames(size)
        _gif_cache[key] = frames
        return frames

    try:
        path = find_asset(filename)
    except FileNotFoundError:
        print(f"[scene1] WARNING: '{filename}' is missing from the asset "
              f"folder - using a placeholder animation instead.")
        frames = _placeholder_gif_frames(size)
        _gif_cache[key] = frames
        return frames

    frames = []
    pil_img = Image.open(path)
    try:
        while True:
            frame = pil_img.convert("RGBA")
            duration = pil_img.info.get("duration", 80)
            data = frame.tobytes()
            surf = pygame.image.fromstring(data, frame.size, "RGBA")
            if size is not None:
                surf = pygame.transform.smoothscale(surf, size)
            frames.append((surf, max(duration, 20)))
            pil_img.seek(pil_img.tell() + 1)
    except EOFError:
        pass

    _gif_cache[key] = frames
    return frames


def load_sound(filename):
    try:
        return pygame.mixer.Sound(find_asset(filename))
    except (pygame.error, FileNotFoundError):
        return None


def play_sound(sound, volume=1.0):
    if sound is not None:
        sound.set_volume(volume)
        sound.play()


# ---------------------------------------------------------------------------
# Generic animator, following the same pattern as bloomie_animations.py /
# wilt_animations.py, extended with looping control and an on-finish callback
# so one-shot animations (heal, evil reaction) can hand control back.
# ---------------------------------------------------------------------------

class Animator:
    def __init__(self, animations, target_height, start="idle"):
        self.animations = animations
        self.target_height = target_height
        self.current_anim = start
        self.frame_index = 0
        self.last_update = pygame.time.get_ticks()
        self.finished = False
        self._on_finish = None
        self._cache = {}
        for data in animations.values():
            for fname in data["frames"]:
                if fname not in self._cache:
                    self._cache[fname] = load_character_frame(fname, target_height)

    def set_animation(self, name, restart_if_same=False, on_finish=None):
        if name not in self.animations:
            return
        if name == self.current_anim and not restart_if_same:
            return
        self.current_anim = name
        self.frame_index = 0
        self.finished = False
        self.last_update = pygame.time.get_ticks()
        self._on_finish = on_finish

    def _delay(self):
        delay = self.animations[self.current_anim]["delay"]
        return delay[self.frame_index] if isinstance(delay, list) else delay

    def update(self):
        data = self.animations[self.current_anim]
        frames = data["frames"]
        loop = data.get("loop", True)
        now = pygame.time.get_ticks()
        if self.finished or now - self.last_update < self._delay():
            return
        self.last_update = now
        if self.frame_index + 1 < len(frames):
            self.frame_index += 1
        else:
            if loop:
                self.frame_index = 0
            else:
                self.finished = True
                if self._on_finish:
                    cb, self._on_finish = self._on_finish, None
                    cb()

    def frame(self, flip=False):
        fname = self.animations[self.current_anim]["frames"][self.frame_index]
        img = self._cache[fname]
        return pygame.transform.flip(img, True, False) if flip else img


BLOOMIE_ANIMATIONS = {
    "idle": {"frames": ["Bloomie BG REMOVED.png"], "delay": 1000, "loop": True},
    "walk": {
        # walk3/walk4 are the matched pair: same linework/proportions as
        # each other. The auto-key-out-background step above also strips
        # any baked-in solid background these frames might still carry, so
        # they don't flash a colored box against walk1/walk2's real
        # transparent edges when the animation loops.
        "frames": ["bloomie_walk3.png", "bloomie_walk4.png"],
        "delay": 220, "loop": True,
    },
    "jump": {
        "frames": ["bloomie_jump1.png", "bloomie_jump2.png", "bloomie_jump3.png"],
        "delay": 130, "loop": False,
    },
    "heal": {
        "frames": ["bloomie_heal1.png", "bloomie_heal2.png", "bloomie_heal3.png", "bloomie_heal4.png"],
        "delay": 220, "loop": False,
    },
}

WILT_ANIMATIONS = {
    "default": {"frames": ["Wilt BG REMOVED.png"], "delay": 1000, "loop": True},
    "evil": {
        "frames": ["wilt_evil1.png", "wilt_evil2.png", "wilt_evil3.png", "wilt_evil4.png"],
        "delay": [220, 220, 220, 420], "loop": False,
    },
}


# ---------------------------------------------------------------------------
# World entities
# ---------------------------------------------------------------------------

class Camera:
    def __init__(self, level_width, screen_width):
        self.offset_x = 0
        self.level_width = level_width
        self.screen_width = screen_width

    def update(self, target_x):
        self.offset_x = max(0, min(target_x - self.screen_width // 2,
                                    self.level_width - self.screen_width))

    def apply(self, x):
        return x - self.offset_x


class Petal(pygame.sprite.Sprite):
    """A small floating petal the player collects to charge the Healing
    Bloom meter, gently spinning in place so it reads as a collectible
    rather than a static sticker."""

    def __init__(self, x, y):
        super().__init__()
        self.image = petal_image(24)
        self.base_y = y
        self.x = x
        self.t = random.uniform(0, 6.28)
        self.angle = random.uniform(0, 360)
        self.spin_speed = random.uniform(25, 55) * random.choice((-1, 1))
        self.scale = random.uniform(0.85, 1.2)
        self.collected = False

    def update(self, dt):
        self.t += dt * 2.2
        self.angle += self.spin_speed * dt

    def draw(self, screen, cam):
        y = self.base_y + int(7 * math.sin(self.t))
        img = pygame.transform.rotozoom(self.image, self.angle, self.scale)
        rect = img.get_rect(center=(cam.apply(self.x), y))
        screen.blit(img, rect)


class PetalBurst:
    """Short-lived decorative petal shower spawned when a flower is healed.
    Each particle tumbles outward at its own size/rotation/speed so a shared
    single-petal sprite still reads as a natural little shower."""

    def __init__(self, x, y):
        sprite = petal_image(20)
        self.particles = []
        for _ in range(14):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(1.2, 3.4)
            self.particles.append({
                "x": x, "y": y,
                "vx": speed * pygame.math.Vector2(1, 0).rotate_rad(angle).x,
                "vy": speed * pygame.math.Vector2(1, 0).rotate_rad(angle).y - 2,
                "life": random.uniform(50, 90),
                "spin": random.uniform(-6, 6),
                "angle": random.uniform(0, 360),
                "scale": random.uniform(0.7, 1.3),
                "image": sprite,
            })

    def update(self):
        for p in self.particles:
            p["vy"] += 0.08
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["angle"] += p["spin"]
            p["life"] -= 1
        self.particles = [p for p in self.particles if p["life"] > 0]

    @property
    def alive(self):
        return len(self.particles) > 0

    def draw(self, screen, cam):
        for p in self.particles:
            img = pygame.transform.rotozoom(p["image"], p["angle"], p["scale"])
            alpha = max(0, min(255, int(255 * (p["life"] / 70))))
            img.set_alpha(alpha)
            rect = img.get_rect(center=(cam.apply(p["x"]), p["y"]))
            screen.blit(img, rect)


class Butterfly:
    """Spawns near a healed flower and flutters nearby indefinitely."""

    def __init__(self, x, y):
        self.image = load_image("Butterfly Sprite .png", BUTTERFLY_SIZE)
        self.origin_x = x
        self.origin_y = y
        self.t = random.uniform(0, 6.28)

    def update(self, dt):
        self.t += dt * 1.6

    def draw(self, screen, cam):
        x = self.origin_x + 40 * math.sin(self.t)
        y = self.origin_y - 30 + 16 * math.sin(self.t * 2.3)
        wobble = pygame.transform.rotozoom(self.image, 10 * math.sin(self.t * 4), 1.0)
        rect = wobble.get_rect(center=(cam.apply(x), y))
        screen.blit(wobble, rect)


class Flower:
    """
    A wilted flower that Bloomie can heal, using the real Sakura Flower.png
    illustration (previously this relied on Blloming Flower Animation.gif,
    which is missing from the asset folder and fell back to a plain gray
    placeholder circle). The same image is used for both states: small and
    desaturated while wilted/healing, growing to full size and full color
    over HEAL_DURATION_MS once Bloomie casts Healing Bloom on it - a
    procedural "bloom" tween standing in for the missing frame-by-frame
    animation. Healing an "unlocks_platform" flower creates a magical
    platform.
    """

    HEAL_RANGE = 90
    HEAL_DURATION_MS = 900
    WILTED_SCALE = 0.45

    def __init__(self, x, y, unlocks_platform=False, platform_rect=None):
        self.x = x
        self.y = y
        self.bloom_image = load_character_frame("Sakura Flower.png", 90)
        self.state = "wilted"  # wilted -> healing -> healed
        self.heal_start_ms = 0
        self.unlocks_platform = unlocks_platform
        self.platform_rect = platform_rect

    @property
    def rect(self):
        w, h = self.bloom_image.get_size()
        return pygame.Rect(self.x - w // 2, self.y - h, w, h)

    def start_heal(self):
        if self.state == "wilted":
            self.state = "healing"
            self.heal_start_ms = pygame.time.get_ticks()

    def update(self, on_healed):
        if self.state != "healing":
            return
        elapsed = pygame.time.get_ticks() - self.heal_start_ms
        if elapsed >= self.HEAL_DURATION_MS:
            self.state = "healed"
            on_healed(self)

    def _bloom_progress(self):
        """0.0 = fully wilted, 1.0 = fully healed. Eased so growth starts
        fast and settles gently instead of animating linearly."""
        if self.state == "healed":
            return 1.0
        if self.state != "healing":
            return 0.0
        elapsed = pygame.time.get_ticks() - self.heal_start_ms
        t = max(0.0, min(1.0, elapsed / self.HEAL_DURATION_MS))
        return 1 - (1 - t) ** 3  # ease-out cubic

    def draw(self, screen, cam):
        progress = self._bloom_progress()
        scale = self.WILTED_SCALE + (1.0 - self.WILTED_SCALE) * progress
        img = pygame.transform.rotozoom(self.bloom_image, 0, scale)
        rect = img.get_rect(midbottom=(cam.apply(self.x), self.y))
        if progress >= 1.0:
            screen.blit(img, rect)
            return
        # Fade from a dull, desaturated tone up to the flower's real colors
        # as it blooms. Alpha channel must stay 255 here - multiplying it
        # by anything less zeroes out the sprite's own transparency and
        # makes the whole image vanish instead of just darkening it.
        tinted = img.copy()
        mult = (int(120 + 135 * progress), int(110 + 145 * progress), int(115 + 140 * progress), 255)
        tinted.fill(mult, special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(tinted, rect)


class WiltFigure:
    """Ambient corrupted-flora hazard. Reacts with its 'evil' animation when
    Bloomie wanders too close, then settles back to its default brooding pose."""

    TRIGGER_RANGE = 210
    COOLDOWN_MS = 4000

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.animator = Animator(WILT_ANIMATIONS, WILT_HEIGHT, start="default")
        self.last_trigger = -99999

    def update(self, player_x):
        now = pygame.time.get_ticks()
        if (self.animator.current_anim == "default"
                and abs(player_x - self.x) < self.TRIGGER_RANGE
                and now - self.last_trigger > self.COOLDOWN_MS):
            self.last_trigger = now
            self.animator.set_animation("evil", restart_if_same=True,
                                         on_finish=lambda: self.animator.set_animation("default"))
        self.animator.update()

    def draw(self, screen, cam):
        img = self.animator.frame()
        rect = img.get_rect(midbottom=(cam.apply(self.x), self.y))
        screen.blit(img, rect)


class GrassPatch:
    def __init__(self, x, y):
        self.image = load_image("Grass Texture .png", GRASS_SIZE)
        self.x = x
        self.y = y

    def draw(self, screen, cam):
        rect = self.image.get_rect(midbottom=(cam.apply(self.x), self.y + 6))
        screen.blit(self.image, rect)


class FloatingPetals:
    """Ambient sakura petals that drift around the screen on the level-
    complete card, once all obstacles have been cleared. A slow side-to-side
    sway plus a faster, smaller wobble layered on top makes each one tumble
    unevenly on the way down, the way real falling petals do."""

    def __init__(self, width, height, count=22):
        self.width = width
        self.height = height
        self.sprite = petal_image(30)
        self.particles = [self._new_particle(random.uniform(0, height)) for _ in range(count)]

    def _new_particle(self, y):
        return {
            "image": self.sprite,
            "scale": random.uniform(0.7, 1.4),
            "x": random.uniform(0, self.width),
            "y": y,
            "vy": random.uniform(14, 32),
            "sway": random.uniform(18, 50),
            "sway_speed": random.uniform(0.4, 1.1),
            "wobble": random.uniform(4, 12),
            "wobble_speed": random.uniform(2.2, 3.6),
            "t": random.uniform(0, 6.28),
            "spin": random.uniform(-35, 35),
            "angle": random.uniform(0, 360),
        }

    def update(self, dt):
        for p in self.particles:
            p["t"] += dt * p["sway_speed"]
            p["y"] += p["vy"] * dt
            p["angle"] += p["spin"] * dt
            if p["y"] > self.height + 20:
                p.update(self._new_particle(-20))

    def draw(self, screen):
        for p in self.particles:
            drift = math.sin(p["t"]) * p["sway"] + math.sin(p["t"] * p["wobble_speed"]) * p["wobble"]
            x = p["x"] + drift
            img = pygame.transform.rotozoom(p["image"], p["angle"], p["scale"])
            rect = img.get_rect(center=(x, p["y"]))
            screen.blit(img, rect)


class Bloomie:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.on_ground = False
        self.facing_left = False
        self.healing = False
        self.animator = Animator(BLOOMIE_ANIMATIONS, BLOOMIE_HEIGHT, start="idle")
        self.petals_collected = 0
        self.flowers_healed = 0
        self.heal_meter = 0  # fuelled by petals; Healing Bloom needs HEAL_METER_FULL

    @property
    def rect(self):
        w, h = BLOOMIE_SIZE
        return pygame.Rect(int(self.x - w * 0.28), int(self.y - h * 0.92), int(w * 0.56), int(h * 0.9))

    def add_petal(self):
        self.petals_collected += 1
        self.heal_meter = min(HEAL_METER_FULL, self.heal_meter + 1)

    def try_jump(self):
        if self.on_ground and not self.healing:
            self.vy = JUMP_SPEED
            self.on_ground = False
            self.animator.set_animation("jump", restart_if_same=True)

    def nearby_wilted_flower(self, flowers):
        for flower in flowers:
            if flower.state == "wilted" and abs(flower.x - self.x) < Flower.HEAL_RANGE:
                return flower
        return None

    def try_heal(self, flowers):
        if self.healing:
            return None
        flower = self.nearby_wilted_flower(flowers)
        if flower is None or self.heal_meter < HEAL_METER_FULL:
            return None

        self.heal_meter = 0  # Healing Bloom spends the whole charge
        self.healing = True
        flower.start_heal()

        def finish_heal():
            self.healing = False

        self.animator.set_animation("heal", restart_if_same=True, on_finish=finish_heal)
        return flower

    def update(self, keys, platforms):
        if not self.healing:
            move = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                move -= 1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                move += 1
            self.vx = move * MOVE_SPEED
            if move != 0:
                self.facing_left = move < 0
        else:
            self.vx = 0

        self.vy += GRAVITY
        self.vy = min(self.vy, 22)

        self.x += self.vx
        self.x = max(40, min(self.x, LEVEL_WIDTH - 40))
        self.y += self.vy

        self.on_ground = False
        foot_rect = self.rect
        for plat in platforms:
            plat_rect = plat if isinstance(plat, pygame.Rect) else plat.rect
            # Vertical check uses self.y directly (the same coordinate the
            # sprite is drawn/anchored at) rather than foot_rect.bottom.
            # foot_rect's 0.92/0.9 height coefficients put its bottom edge
            # about 2.4px above self.y, so using foot_rect.bottom here could
            # miss landing by a couple of pixels on some frames - just
            # enough for on_ground to flicker False for a tick right after
            # touching down, which flashes the jump animation back on even
            # while standing still.
            if (foot_rect.right > plat_rect.left and foot_rect.left < plat_rect.right
                    and self.vy >= 0
                    and self.y >= plat_rect.top - 1
                    and self.y - self.vy <= plat_rect.top + 1):
                self.y = plat_rect.top
                self.vy = 0
                self.on_ground = True

        if self.y > SCREEN_HEIGHT + 400:
            # fell into a gap - respawn at the nearest platform to the left
            self.x = max(80, self.x - 250)
            self.y = GROUND_Y - 260

        if not self.healing:
            if not self.on_ground:
                if self.animator.current_anim != "jump":
                    self.animator.set_animation("jump", restart_if_same=False)
            elif self.vx != 0:
                self.animator.set_animation("walk")
            else:
                self.animator.set_animation("idle")

        self.animator.update()

    def draw(self, screen, cam):
        img = self.animator.frame(flip=self.facing_left)
        rect = img.get_rect(midbottom=(cam.apply(self.x), self.y))
        screen.blit(img, rect)


class RisingPlatform:
    """A glowing blue platform that appears once every flower in the scene
    has been healed. It only rises while Bloomie is actually standing on
    it, carrying them up to the gem's ledge on "the opposite side" - it
    does NOT climb on its own timer. Rising unconditionally the instant it
    activates was the original bug: the platform could finish its whole
    climb (and end up sitting far out of jump range, near the gem ledge's
    height) before the player had even walked over to it, making it look
    like you could never actually jump onto it. Once it reaches the top it
    locks in place permanently as a normal platform.

    self.y is the walkable *surface* height (matching how ground/flower
    platform rects use .top), so it lines up exactly with GROUND_Y and with
    the gem ledge's rect.top - not the center of the drawn circle."""

    RADIUS = 46
    RISE_SPEED = 70  # px/sec, while boarded

    def __init__(self, x, y_ground, y_top):
        self.x = x
        self.y = y_ground
        self.y_top = y_top
        self.active = False
        self.boarded = False  # set every frame from the outside (is Bloomie standing on it?)
        self.t = 0.0

    def activate(self):
        self.active = True

    @property
    def risen(self):
        return self.y <= self.y_top + 0.5

    def update(self, dt):
        self.t += dt
        if self.active and self.boarded and self.y > self.y_top:
            self.y = max(self.y_top, self.y - self.RISE_SPEED * dt)

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.RADIUS), int(self.y), self.RADIUS * 2, 20)

    def player_is_boarding(self, player):
        """True if the player is currently standing on this platform's
        surface (used to decide whether it should rise this frame)."""
        return (player.on_ground
                and abs(player.x - self.x) <= self.RADIUS
                and abs(player.y - self.y) < 2)

    def draw(self, screen, cam):
        if not self.active:
            return
        sx = cam.apply(self.x)
        cy = self.y + self.RADIUS - 12  # circle bulges below the walkable surface line
        pulse = 4 * math.sin(self.t * 3)
        layers = (
            (self.RADIUS + 10 + pulse, (120, 180, 255), 70),
            (self.RADIUS, (90, 150, 240), 225),
            (self.RADIUS - 16, (190, 225, 255), 255),
        )
        for radius, color, alpha in layers:
            radius = max(1, int(radius))
            surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, alpha), (radius, radius), radius)
            screen.blit(surf, (sx - radius, cy - radius))


class Gem:
    """The end-of-level gem, perched on a ledge reachable only via the
    rising platform. Uses the Crystal Activation Animation gif: it sits on
    the first frame until Bloomie reaches it, then plays the activation
    burst once before handing off to the memory-playback cutscene."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.frames = load_gif_frames("Crystal Activation Animation .gif", GEM_SIZE)
        self.frame_index = 0
        self.last_update = pygame.time.get_ticks()
        self.state = "idle"  # idle -> activating -> collected
        self.t = 0.0

    @property
    def rect(self):
        w, h = GEM_SIZE
        return pygame.Rect(self.x - w // 2, self.y - h, w, h)

    def collect(self):
        if self.state == "idle":
            self.state = "activating"
            self.frame_index = 0
            self.last_update = pygame.time.get_ticks()

    def update(self, dt, on_collected):
        self.t += dt
        if self.state != "activating":
            return
        _, duration = self.frames[self.frame_index]
        now = pygame.time.get_ticks()
        if now - self.last_update >= max(70, duration):
            self.last_update = now
            if self.frame_index + 1 < len(self.frames):
                self.frame_index += 1
            else:
                self.state = "collected"
                on_collected()

    def draw(self, screen, cam):
        if self.state == "collected":
            return
        idx = 0 if self.state == "idle" else self.frame_index
        img = self.frames[idx][0]
        bob = 6 * math.sin(self.t * 2) if self.state == "idle" else 0
        rect = img.get_rect(midbottom=(cam.apply(self.x), self.y + bob))
        screen.blit(img, rect)


# ---------------------------------------------------------------------------
# Level layout
# ---------------------------------------------------------------------------

RISING_PLATFORM_X = 2900
GEM_LEDGE_Y = GROUND_Y - 260
GEM_LEDGE_RECT = pygame.Rect(2965, GEM_LEDGE_Y, 150, 20)
GEM_X = GEM_LEDGE_RECT.centerx
GEM_Y = GEM_LEDGE_Y


def build_level():
    """
    Ground segments with gaps that mirror the storyboard: an intro clearing
    to learn moving/jumping/collecting petals, then a corrupted stretch
    guarded by Wilt where the pathway has crumbled away entirely - those
    gaps are wide enough that they are impossible to clear with a jump
    alone, so Bloomie must charge Healing Bloom on the nearby wilted flower
    to grow a magical platform across before continuing (verified against
    the jump physics below). Every petal zone holds more petals than the
    10 needed to fill the Healing Bloom meter once, so a player who
    collects along the way never gets stuck short.
    """
    ground_segments = [
        pygame.Rect(0, GROUND_Y, 860, SCREEN_HEIGHT),      # starting clearing
        pygame.Rect(1000, GROUND_Y, 500, SCREEN_HEIGHT),   # after the first (unaided) jump
        pygame.Rect(1850, GROUND_Y, 450, SCREEN_HEIGHT),   # after healing flower #2
        pygame.Rect(2650, GROUND_Y, 950, SCREEN_HEIGHT),   # after healing flower #3, to the end
    ]
    # gaps: 860->1000 (140px, jumpable unaided) | 1500->1850 (350px, needs a
    # healed-flower platform) | 2300->2650 (350px, needs a healed-flower platform)

    flowers = [
        Flower(780, GROUND_Y, unlocks_platform=False),                       # free practice heal
        Flower(1480, GROUND_Y, unlocks_platform=True,
               platform_rect=pygame.Rect(1590, GROUND_Y - 20, 180, 20)),     # bridges gap 2
        Flower(2280, GROUND_Y, unlocks_platform=True,
               platform_rect=pygame.Rect(2390, GROUND_Y - 20, 180, 20)),     # bridges gap 3
    ]

    wilt_figures = [
        WiltFigure(1420, GROUND_Y),
        WiltFigure(2240, GROUND_Y),
    ]

    # Every zone carries well more than the 10 petals needed to fill the
    # Healing Bloom meter once, with extra density right before each flower's
    # heal range so the meter reliably tops up before Bloomie walks out of
    # range again - even a player who doesn't catch every single petal.
    petal_xs = (
        list(range(80, 800, 40))       # zone A: on the way to flower #1 (18 petals)
        + list(range(1010, 1470, 30))  # zone B: on the way to flower #2 (15 petals)
        + list(range(1850, 2270, 30))  # zone C: on the way to flower #3 (14 petals)
        + list(range(2700, 3400, 90))  # finale bonus petals (8 petals)
    )
    petals = [Petal(x, GROUND_Y - 150) for x in petal_xs]

    return ground_segments, flowers, wilt_figures, petals


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def draw_sky(screen):
    for i in range(SCREEN_HEIGHT):
        t = i / SCREEN_HEIGHT
        color = [int(SKY_TOP[c] * (1 - t) + SKY_BOTTOM[c] * t) for c in range(3)]
        pygame.draw.line(screen, color, (0, i), (SCREEN_WIDTH, i))


def draw_background(screen, cam, bg_image, corrupted_zone):
    bg_w = bg_image.get_width()
    parallax = cam.offset_x * 0.35
    start = -(int(parallax) % bg_w)
    x = start
    while x < SCREEN_WIDTH:
        screen.blit(bg_image, (x, SCREEN_HEIGHT - bg_image.get_height()))
        x += bg_w

    # A darker corrupted tint over The Wilt's stretch of the garden.
    zone_left, zone_right = corrupted_zone
    left = cam.apply(zone_left)
    right = cam.apply(zone_right)
    if right > 0 and left < SCREEN_WIDTH:
        overlay = pygame.Surface((max(1, right - left), SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*CORRUPT_PURPLE, 55))
        screen.blit(overlay, (left, 0))


def draw_ground(screen, cam, ground_segments):
    """No-op by design (matches the fix in the uploaded reference file): the
    ground_segments rects still exist and still drive collision in
    Bloomie.update(), but we no longer paint a brown/green box over the
    background art for them. Bloomie just stands directly on the
    illustrated ground in Spring Sanctuary Background .png instead of
    appearing to stand on a solid-color block."""
    pass


def draw_platform(screen, cam, plat, glow_t):
    left = cam.apply(plat.left)
    rect = pygame.Rect(left, plat.top, plat.width, plat.height)
    glow = 0.5 + 0.5 * math.sin(glow_t)
    color = (int(255 - 40 * glow), int(200 + 30 * glow), int(230))
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, WHITE, rect, 2, border_radius=8)


def draw_heal_meter(screen, x, y, meter):
    """The Healing Bloom meter: 10 pips that fill in as petals are
    collected. Pips past HEAL_METER_BOOST light up gold instead of pink,
    and the whole bar announces itself as ready once full."""
    pip_w, pip_h, gap = 20, 14, 4
    for i in range(HEAL_METER_FULL):
        rect = pygame.Rect(x + i * (pip_w + gap), y, pip_w, pip_h)
        if i >= meter:
            color = (75, 65, 80)
        elif i < HEAL_METER_BOOST:
            color = (255, 175, 205)
        else:
            color = (255, 205, 90)
        pygame.draw.rect(screen, color, rect, border_radius=4)
        pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
    bar_end_x = x + HEAL_METER_FULL * (pip_w + gap) + 10
    if meter >= HEAL_METER_FULL:
        draw_text(screen, "READY!", bar_end_x, y + pip_h // 2, (255, 225, 140), 18)
    else:
        draw_text(screen, f"{meter}/{HEAL_METER_FULL}", bar_end_x, y + pip_h // 2, CREAM, 16)


def draw_text(screen, text, x, y, color=WHITE, size=24, center=False, shadow=True, font_name=None):
    font = pygame.font.SysFont(font_name or "arial", size, bold=True)
    surf = font.render(text, True, color)
    if shadow:
        shadow_surf = font.render(text, True, (0, 0, 0))
        pos = surf.get_rect(center=(x, y)) if center else (x, y)
        if center:
            screen.blit(shadow_surf, (pos.x + 2, pos.y + 2))
        else:
            screen.blit(shadow_surf, (x + 2, y + 2))
    rect = surf.get_rect(center=(x, y)) if center else (x, y)
    screen.blit(surf, rect)
    return surf.get_rect(center=(x, y)) if center else pygame.Rect(x, y, *surf.get_size())


def wrap_text(text, font, max_width):
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------

NARRATIVE = ("In the Spring Sanctuary, Bloomie wakes up in a beautiful cherry blossom "
             "garden. It is partially corrupted by The Wilt, causing some flowers to "
             "wilt and parts of the pathways to disappear. Move, jump, and collect "
             "petals to charge Healing Bloom - once the meter is full, heal a flower "
             "to bring the garden back to life. Heal every flower to reveal a path to "
             "a hidden gem.")

MEMORY_TEXT = ("As the gem awakens, a memory flickers through Bloomie's mind: The Wilt "
               "was never acting alone. Somewhere beyond the sanctuary, an older, "
               "greater corruption stirs - the true source of the blight is watching.")


def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Scene 1 - Spring Sanctuary")
    clock = pygame.time.Clock()

    bg_image = load_image("Spring Sanctuary Background .png",
                           (int(1344 * (SCREEN_HEIGHT / 768)), SCREEN_HEIGHT))

    bgm = None
    try:
        bgm_path = find_asset("Spring Garden Theme Scene 1.mp3")
        pygame.mixer.music.load(bgm_path)
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)
        bgm = True
    except (pygame.error, FileNotFoundError):
        pass

    greeting_sfx = load_sound("Bloomie Greeting Scene 1.mp3")
    butterfly_sfx = load_sound("Butterfly Spawn Sound  Scene 1.mp3")
    bloom_sfx = load_sound("Flower Bloom Sound Scene 1, 4 .mp3")
    crystal_sfx = load_sound("Crystal Activation Sound Scene 2.mp3")
    boss_tease_img = load_character_frame("wilt_ult_attack1.png", 380)

    ground_segments, flowers, wilt_figures, petals = build_level()
    platforms = list(ground_segments)  # active collidable surfaces (grows as flowers heal)
    platforms.append(GEM_LEDGE_RECT)   # always present, just unreachable without the rising platform

    player = Bloomie(120, GROUND_Y - 260)
    camera = Camera(LEVEL_WIDTH, SCREEN_WIDTH)
    rising_platform = RisingPlatform(RISING_PLATFORM_X, GROUND_Y, GEM_LEDGE_Y)
    gem = Gem(GEM_X, GEM_Y)
    platform_activated = False

    butterflies = []
    grass_patches = []
    petal_bursts = []
    win_petals = None  # sakura petals drifting on the level-complete card

    corrupted_zone = (1420, 2650)

    STATE_INTRO, STATE_PLAY, STATE_MEMORY, STATE_WIN = "intro", "play", "memory", "win"
    state = STATE_INTRO
    intro_played_sound = False
    glow_t = 0.0
    memory_timer = 0.0
    MEMORY_AUTO_ADVANCE = 7.0  # seconds before the memory cutscene advances on its own

    heal_prompt_flower = None
    max_frames = os.environ.get("SCENE1_MAX_FRAMES")
    max_frames = int(max_frames) if max_frames else None
    frame_count = 0

    def on_flower_healed(flower):
        play_sound(bloom_sfx, 0.8)
        grass_patches.append(GrassPatch(flower.x, flower.y))
        petal_bursts.append(PetalBurst(flower.x, flower.y - 60))
        butterflies.append(Butterfly(flower.x, flower.y - 90))
        play_sound(butterfly_sfx, 0.7)
        player.flowers_healed += 1
        if flower.unlocks_platform and flower.platform_rect is not None:
            platforms.append(flower.platform_rect)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        frame_count += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == STATE_INTRO and event.key not in (pygame.K_ESCAPE,):
                    state = STATE_PLAY
                elif state == STATE_PLAY:
                    if event.key == pygame.K_SPACE:
                        player.try_jump()
                    elif event.key in (pygame.K_e, pygame.K_f):
                        player.try_heal(flowers)
                elif state == STATE_MEMORY:
                    state = STATE_WIN
                    win_petals = FloatingPetals(SCREEN_WIDTH, SCREEN_HEIGHT)
                elif state == STATE_WIN and event.key == pygame.K_r:
                    return "restart"

        if state == STATE_INTRO:
            if not intro_played_sound:
                play_sound(greeting_sfx, 0.9)
                intro_played_sound = True

        elif state == STATE_PLAY:
            keys = pygame.key.get_pressed()
            player.update(keys, platforms)
            camera.update(player.x)

            for flower in flowers:
                flower.update(on_flower_healed)

            for wilt in wilt_figures:
                wilt.update(player.x)

            for petal in list(petals):
                if not petal.collected:
                    dx = petal.x - player.x
                    dy = petal.base_y - player.y
                    if dx * dx + dy * dy < 45 * 45:
                        petal.collected = True
                        player.add_petal()
                petal.update(dt)
            petals[:] = [p for p in petals if not p.collected]

            for b in butterflies:
                b.update(dt)

            for burst in list(petal_bursts):
                burst.update()
                if not burst.alive:
                    petal_bursts.remove(burst)

            heal_prompt_flower = player.nearby_wilted_flower(flowers)

            # Once every flower has been healed, the rising platform appears
            # and lifts Bloomie up to the gem on the opposite side.
            if not platform_activated and player.flowers_healed >= len(flowers):
                platform_activated = True
                rising_platform.activate()
                platforms.append(rising_platform)

            rising_platform.boarded = rising_platform.player_is_boarding(player)
            rising_platform.update(dt)
            if rising_platform.boarded and not rising_platform.risen:
                # The ground segment Bloomie is already standing on runs the
                # full width of this part of the level (the platform is an
                # "elevator" rising out of solid ground, not out of a pit),
                # so the generic per-frame gravity/landing check above keeps
                # re-catching Bloomie at the fixed ground height every frame
                # - it's built to catch a player falling onto a surface, not
                # to be pushed upward by one. Left alone, that fight caps the
                # platform's climb at a couple of pixels before the boarding-
                # proximity check (player_is_boarding) trips false and it
                # stalls for good. Explicitly gluing Bloomie to the platform
                # while it's actively rising sidesteps that fight entirely.
                player.y = rising_platform.y
                player.vy = 0
                player.on_ground = True

            if gem.state == "idle":
                dx = gem.x - player.x
                dy = gem.y - player.y
                if dx * dx + dy * dy < 55 * 55:
                    gem.collect()
                    play_sound(crystal_sfx, 0.8)

            def on_gem_collected():
                pass  # state transition is driven by gem.state below

            gem.update(dt, on_gem_collected)
            if gem.state == "collected" and state == STATE_PLAY:
                state = STATE_MEMORY
                memory_timer = 0.0

        elif state == STATE_MEMORY:
            memory_timer += dt
            if memory_timer >= MEMORY_AUTO_ADVANCE:
                state = STATE_WIN
                win_petals = FloatingPetals(SCREEN_WIDTH, SCREEN_HEIGHT)

        glow_t += dt * 3

        # --- draw ---
        draw_sky(screen)
        draw_background(screen, camera, bg_image, corrupted_zone)
        draw_ground(screen, camera, ground_segments)
        for plat in platforms:
            if isinstance(plat, pygame.Rect) and plat not in ground_segments:
                draw_platform(screen, camera, plat, glow_t)
        rising_platform.draw(screen, camera)
        gem.draw(screen, camera)
        for gp in grass_patches:
            gp.draw(screen, camera)
        for flower in flowers:
            flower.draw(screen, camera)
        for wilt in wilt_figures:
            wilt.draw(screen, camera)
        for petal in petals:
            petal.draw(screen, camera)
        for b in butterflies:
            b.draw(screen, camera)
        player.draw(screen, camera)
        for burst in petal_bursts:
            burst.draw(screen, camera)

        # HUD
        draw_text(screen, f"Petals: {player.petals_collected}", 20, 24, CREAM, 22)
        draw_text(screen, f"Flowers Healed: {player.flowers_healed}/{len(flowers)}", 20, 52, CREAM, 22)
        draw_heal_meter(screen, 20, 78, player.heal_meter)
        draw_text(screen, "A/D or Arrows: Move   Space: Jump   Petals charge Healing Bloom   E: Heal",
                  20, SCREEN_HEIGHT - 26, (255, 255, 255), 16)

        if state == STATE_PLAY and not player.healing and heal_prompt_flower is not None:
            if player.heal_meter >= HEAL_METER_FULL:
                draw_text(screen, "Press E to heal this flower!",
                          SCREEN_WIDTH // 2, SCREEN_HEIGHT - 66, (255, 240, 200), 22, center=True)
            else:
                draw_text(screen, f"Collect petals to charge Healing Bloom ({player.heal_meter}/{HEAL_METER_FULL})",
                          SCREEN_WIDTH // 2, SCREEN_HEIGHT - 66, (255, 210, 210), 20, center=True)
        elif state == STATE_PLAY and platform_activated and gem.state == "idle":
            if rising_platform.risen:
                draw_text(screen, "Cross to the gem!",
                          SCREEN_WIDTH // 2, SCREEN_HEIGHT - 66, (200, 230, 255), 22, center=True)
            elif rising_platform.boarded:
                draw_text(screen, "Rising... stay on the platform!",
                          SCREEN_WIDTH // 2, SCREEN_HEIGHT - 66, (200, 230, 255), 22, center=True)
            else:
                draw_text(screen, "Step onto the glowing platform to ride it up!",
                          SCREEN_WIDTH // 2, SCREEN_HEIGHT - 66, (200, 230, 255), 22, center=True)

        if state == STATE_INTRO:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((20, 10, 25, 165))
            screen.blit(overlay, (0, 0))
            draw_text(screen, "Scene 1 - Spring Sanctuary", SCREEN_WIDTH // 2, 190,
                      (255, 225, 240), 40, center=True)
            font = pygame.font.SysFont("arial", 20)
            lines = wrap_text(NARRATIVE, font, SCREEN_WIDTH - 220)
            for i, line in enumerate(lines):
                draw_text(screen, line, SCREEN_WIDTH // 2, 250 + i * 28, CREAM, 20, center=True)
            draw_text(screen, "Press any key to begin", SCREEN_WIDTH // 2, SCREEN_HEIGHT - 90,
                      (255, 210, 120), 24, center=True)

        elif state == STATE_MEMORY:
            fade = min(1.0, memory_timer / 1.2)
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 5, 15, int(210 * fade)))
            screen.blit(overlay, (0, 0))

            tinted = boss_tease_img.copy()
            tinted.fill((255, 80, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
            tinted.set_alpha(int(255 * fade))
            rect = tinted.get_rect(midbottom=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40))
            screen.blit(tinted, rect)

            draw_text(screen, "A Memory Stirs...", SCREEN_WIDTH // 2, 90,
                      (255, 190, 190), 34, center=True)
            font = pygame.font.SysFont("arial", 20)
            lines = wrap_text(MEMORY_TEXT, font, SCREEN_WIDTH - 260)
            for i, line in enumerate(lines):
                draw_text(screen, line, SCREEN_WIDTH // 2, 150 + i * 28, CREAM, 20, center=True)
            draw_text(screen, "Press any key to continue", SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30,
                      (255, 210, 120), 20, center=True)

        elif state == STATE_WIN:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((20, 10, 25, 175))
            screen.blit(overlay, (0, 0))
            if win_petals is not None:
                win_petals.update(dt)
                win_petals.draw(screen)
            draw_text(screen, "Spring Sanctuary Cleansed", SCREEN_WIDTH // 2, 200,
                      (255, 225, 240), 38, center=True)
            draw_text(screen, f"Petals collected: {player.petals_collected}",
                      SCREEN_WIDTH // 2, 268, CREAM, 24, center=True)
            draw_text(screen, f"Flowers healed: {player.flowers_healed}/{len(flowers)}",
                      SCREEN_WIDTH // 2, 304, CREAM, 24, center=True)
            draw_text(screen, f"Gem recovered: {'yes' if gem.state == 'collected' else 'no'}",
                      SCREEN_WIDTH // 2, 340, CREAM, 24, center=True)
            draw_text(screen, "Press R to replay or ESC to quit", SCREEN_WIDTH // 2, 410,
                      (255, 210, 120), 22, center=True)

        pygame.display.flip()

        if max_frames is not None and frame_count >= max_frames:
            running = False

    return "quit"


if __name__ == "__main__":
    result = main()
    while result == "restart":
        result = main()
    pygame.quit()
    sys.exit()
