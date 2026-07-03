"""
Scene 1 - Spring Sanctuary
===========================
Bloomie wakes up in a cherry blossom garden partially corrupted by The Wilt.
This scene is the game's tutorial: move, jump, collect petals, and learn the
Healing Bloom ability. Healing a wilted flower brings the garden back to life
and creates a magical platform that lets Bloomie keep advancing.

Run with:
    pip install pygame pillow
    python3 "scene1_spring_sanctuary.py"

This file must stay in the same folder as the "ISE " and "Imaging Movements"
asset folders (same place as bloomie_animations.py / wilt_animations.py) -
assets are located automatically by filename, so no paths need to be edited.

Asset -> usage map (from the storyboard / asset notes)
--------------------------------------------------------
ISE /Scene 1/Spring Sanctuary Background .png   -> scrolling level background
ISE /Scene 1/Blloming Flower Animation.gif      -> wilted flower -> full bloom
                                                    (frame 0 = wilted/closed,
                                                    last frame = fully healed)
ISE /Scene 1/Grass Texture .png                 -> appears once a flower heals
ISE /Scene 1/Sakura Petals.png                  -> tutorial petal pickups AND
                                                    the petal-burst effect that
                                                    plays when a flower heals
ISE /Scene 1/Butterfly Sprite .png              -> spawns after a flower heals
ISE /Sounds/Spring Garden Theme Scene 1.mp3     -> scene BGM
ISE /Sounds/Bloomie Greeting Scene 1.mp3        -> plays on the title/intro card
ISE /Sounds/Butterfly Spawn Sound  Scene 1.mp3  -> plays when a butterfly spawns
ISE /Sounds/Flower Bloom Sound Scene 1, 4 .mp3  -> plays when a flower finishes healing
Imaging Movements/Bloomie/*                     -> Bloomie idle/walk/jump/heal frames
Imaging Movements/Wilt/Wilt BG REMOVED.png      -> Wilt's corrupted idle pose
Imaging Movements/Wilt/Evil Appearance/*        -> Wilt's corruption reaction
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


_image_cache = {}


def load_image(filename, size=None):
    key = (filename, size)
    if key in _image_cache:
        return _image_cache[key]
    img = pygame.image.load(find_asset(filename)).convert_alpha()
    if size is not None:
        img = pygame.transform.smoothscale(img, size)
    _image_cache[key] = img
    return img


_character_frame_cache = {}


def load_character_frame(filename, target_height):
    """
    Load a single character-animation frame, cropped to its actual (non-
    transparent) content and scaled by height, preserving aspect ratio.

    The Bloomie/Wilt frame PNGs were exported at inconsistent canvas sizes
    (some 2048x2048, some ~300x400) with very different amounts of empty
    transparent padding around the character. Naively stretching every
    frame to one fixed WxH box - which is what a plain load_image() does -
    makes the character visibly pop/resize/shift every time the animation
    lands on one of the odd-sized frames (this is what caused the walking
    animation to look like it was "twitching" no matter what delay was
    used - it was never a timing problem). Cropping to content first and
    scaling only by height keeps the character a consistent size and
    consistent foot position across every frame, regardless of source
    canvas size, and still anchors correctly since sprites are drawn with
    a midbottom anchor.
    """
    key = (filename, target_height)
    if key in _character_frame_cache:
        return _character_frame_cache[key]

    path = find_asset(filename)

    if Image is not None:
        pil_img = Image.open(path).convert("RGBA")
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


# "Sakura Petals.png" is a single 1280x603 illustration containing 13
# individual scattered petal shapes, not one petal. These are their
# pixel bounding boxes (pre-computed once with connected-component
# analysis) so we can slice out real, individually-shaped petals instead
# of squashing the whole scattered illustration into one tiny icon.
_PETAL_SPRITE_BOXES = [
    (138, 185, 285, 265), (933, 431, 1085, 508), (790, 248, 934, 324),
    (1086, 216, 1184, 310), (617, 253, 743, 322), (1180, 420, 1279, 483),
    (273, 234, 391, 310), (294, 372, 400, 440), (810, 534, 902, 603),
    (58, 39, 179, 90), (474, 382, 543, 448), (547, 456, 620, 506),
    (1, 0, 63, 43),
]

_petal_sprite_cache = {}


def load_petal_sprites(target_size):
    """Return a list of individual petal pygame.Surfaces (one per real petal
    shape found in Sakura Petals.png), each scaled so its longer edge is
    target_size px, preserving its own aspect ratio."""
    if target_size in _petal_sprite_cache:
        return _petal_sprite_cache[target_size]

    sprites = []
    path = find_asset("Sakura Petals.png")
    if Image is not None:
        full = Image.open(path).convert("RGBA")
        for box in _PETAL_SPRITE_BOXES:
            piece = full.crop(box)
            scale = target_size / max(piece.size)
            new_w = max(1, round(piece.width * scale))
            new_h = max(1, round(piece.height * scale))
            piece = piece.resize((new_w, new_h), Image.LANCZOS)
            sprites.append(pygame.image.fromstring(piece.tobytes(), piece.size, "RGBA").convert_alpha())
    else:
        # Fallback without Pillow: use the whole illustration as one sprite.
        sprites = [load_image("Sakura Petals.png", (target_size, target_size))]

    _petal_sprite_cache[target_size] = sprites
    return sprites


_gif_cache = {}


def load_gif_frames(filename, size=None):
    """Return a list of (pygame.Surface, duration_ms) for an animated GIF."""
    key = (filename, size)
    if key in _gif_cache:
        return _gif_cache[key]

    frames = []
    if Image is None:
        # Pillow isn't installed - fall back to a single static frame so the
        # scene still runs (pip install pillow to get the full animation).
        placeholder = pygame.Surface(size or (100, 100), pygame.SRCALPHA)
        pygame.draw.circle(placeholder, PINK, (placeholder.get_width() // 2,
                                                 placeholder.get_height() // 2),
                            min(placeholder.get_size()) // 2)
        frames = [(placeholder, 100)]
        _gif_cache[key] = frames
        return frames

    path = find_asset(filename)
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
    "idle": {"frames": ["Bloomie BG REMOVED.png"], "delay": 50, "loop": True},
    "walk": {
        "frames": ["bloomie_walk1.png", "bloomie_walk2.png", "bloomie_walk3.png", "bloomie_walk4.png"],
        "delay": 150, "loop": True,  
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
    """A small floating petal the player collects while learning to move/jump.
    Each one is a real individual petal shape (sliced from the multi-petal
    Sakura Petals.png illustration) rather than the whole scattered image
    squashed into an icon, and gently spins in place so it reads as a
    collectible rather than a static sticker."""

    def __init__(self, x, y):
        super().__init__()
        self.image = random.choice(load_petal_sprites(24))
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
    Each particle is its own individually-shaped petal (randomly chosen and
    sized) tumbling outward, instead of copies of one flat icon."""

    def __init__(self, x, y):
        sprites = load_petal_sprites(20)
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
                "image": random.choice(sprites),
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
    A wilted flower that Bloomie can heal. Uses the 65-frame bloom GIF:
    frame 0 doubles as the "wilted" pose, playing through it is the heal
    transformation, and the final frame is the permanent "healed" pose.
    Healing an "unlocks_platform" flower creates a magical platform.
    """

    HEAL_RANGE = 90
    # The source GIF plays back slowly (~9s for all 65 frames). Speed it up
    # for gameplay pacing while keeping the same "growing" look.
    BLOOM_SPEED = 0.45

    def __init__(self, x, y, unlocks_platform=False, platform_rect=None):
        self.x = x
        self.y = y
        raw_frames = load_gif_frames("Blloming Flower Animation.gif", FLOWER_SIZE)
        self.frames = [(img, max(15, int(dur * self.BLOOM_SPEED))) for img, dur in raw_frames]
        self.frame_index = 0
        self.last_update = pygame.time.get_ticks()
        self.state = "wilted"  # wilted -> healing -> healed
        self.unlocks_platform = unlocks_platform
        self.platform_rect = platform_rect
        self.grass_drawn = False

    @property
    def rect(self):
        w, h = FLOWER_SIZE
        return pygame.Rect(self.x - w // 2, self.y - h, w, h)

    def start_heal(self):
        if self.state == "wilted":
            self.state = "healing"
            self.frame_index = 0
            self.last_update = pygame.time.get_ticks()

    def update(self, on_healed):
        if self.state != "healing":
            return
        img, duration = self.frames[self.frame_index]
        now = pygame.time.get_ticks()
        if now - self.last_update >= duration:
            self.last_update = now
            if self.frame_index + 1 < len(self.frames):
                self.frame_index += 1
            else:
                self.state = "healed"
                on_healed(self)

    def current_image(self):
        if self.state == "wilted":
            return self.frames[0][0]
        idx = min(self.frame_index, len(self.frames) - 1)
        return self.frames[idx][0]

    def draw(self, screen, cam):
        img = self.current_image()
        rect = img.get_rect(midbottom=(cam.apply(self.x), self.y))
        if self.state == "wilted":
            tinted = img.copy()
            tinted.fill((150, 150, 150, 0), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(tinted, rect)
        else:
            screen.blit(img, rect)


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
    complete card, once all obstacles have been cleared. Uses individually
    shaped petals (not one flat icon repeated) with a slow side-to-side
    sway plus a faster, smaller wobble layered on top so each one tumbles
    unevenly on the way down, the way real falling petals do."""

    def __init__(self, width, height, count=22):
        self.width = width
        self.height = height
        self.sprites = load_petal_sprites(30)
        self.particles = [self._new_particle(random.uniform(0, height)) for _ in range(count)]

    def _new_particle(self, y):
        return {
            "image": random.choice(self.sprites),
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

    @property
    def rect(self):
        w, h = BLOOMIE_SIZE
        return pygame.Rect(int(self.x - w * 0.28), int(self.y - h * 0.92), int(w * 0.56), int(h * 0.9))

    def try_jump(self):
        if self.on_ground and not self.healing:
            self.vy = JUMP_SPEED
            self.on_ground = False
            self.animator.set_animation("jump", restart_if_same=True)

    def try_heal(self, flowers):
        if self.healing:
            return
        for flower in flowers:
            if flower.state == "wilted" and abs(flower.x - self.x) < Flower.HEAL_RANGE:
                self.healing = True
                flower.start_heal()

                def finish_heal():
                    self.healing = False

                self.animator.set_animation("heal", restart_if_same=True, on_finish=finish_heal)
                return flower
        return None

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
            if (foot_rect.right > plat.left and foot_rect.left < plat.right
                    and self.vy >= 0
                    and foot_rect.bottom - self.vy <= plat.top + 2
                    and foot_rect.bottom >= plat.top):
                self.y = plat.top
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


# ---------------------------------------------------------------------------
# Level layout
# ---------------------------------------------------------------------------

def build_level():
    """
    Ground segments with gaps that mirror the storyboard: an intro clearing
    to learn moving/jumping, then a corrupted stretch guarded by Wilt where
    the pathway has crumbled away entirely - those gaps are wide enough that
    they are impossible to clear with a jump alone, so Bloomie must use
    Healing Bloom on the nearby wilted flower to grow a magical platform
    across before continuing (verified against the jump physics below).
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
        Flower(400, GROUND_Y, unlocks_platform=False),                       # free practice heal
        Flower(1480, GROUND_Y, unlocks_platform=True,
               platform_rect=pygame.Rect(1590, GROUND_Y - 20, 180, 20)),     # bridges gap 2
        Flower(2280, GROUND_Y, unlocks_platform=True,
               platform_rect=pygame.Rect(2390, GROUND_Y - 20, 180, 20)),     # bridges gap 3
    ]

    wilt_figures = [
        WiltFigure(1420, GROUND_Y),
        WiltFigure(2240, GROUND_Y),
    ]

    petals = [Petal(x, GROUND_Y - 150) for x in
              (300, 480, 650, 900, 1120, 1260, 1400, 1970, 2120, 2750, 2900, 3050, 3200)]

    return ground_segments, flowers, wilt_figures, petals


LEVEL_END_X = 3450


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
    for seg in ground_segments:
        left = cam.apply(seg.left)
        right = cam.apply(seg.right)
        if right < 0 or left > SCREEN_WIDTH:
            continue
        rect = pygame.Rect(left, seg.top, seg.width, seg.height)
        pygame.draw.rect(screen, (150, 110, 90), rect)
        pygame.draw.rect(screen, (120, 190, 110), (rect.left, rect.top, rect.width, 14))


def draw_platform(screen, cam, plat, glow_t):
    left = cam.apply(plat.left)
    rect = pygame.Rect(left, plat.top, plat.width, plat.height)
    glow = 0.5 + 0.5 * math.sin(glow_t)
    color = (int(255 - 40 * glow), int(200 + 30 * glow), int(230))
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, WHITE, rect, 2, border_radius=8)


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
             "wilt and parts of the pathways to disappear. Move, jump, collect petals, "
             "and use Healing Bloom to bring the garden back to life.")


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

    ground_segments, flowers, wilt_figures, petals = build_level()
    platforms = list(ground_segments)  # active collidable surfaces (grows as flowers heal)

    player = Bloomie(120, GROUND_Y - 260)
    camera = Camera(LEVEL_WIDTH, SCREEN_WIDTH)

    butterflies = []
    grass_patches = []
    petal_bursts = []
    win_petals = None  # sakura petals drifting on the level-complete card

    corrupted_zone = (1420, 2650)

    STATE_INTRO, STATE_PLAY, STATE_WIN = "intro", "play", "win"
    state = STATE_INTRO
    intro_played_sound = False
    glow_t = 0.0

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
                        player.petals_collected += 1
                petal.update(dt)
            petals[:] = [p for p in petals if not p.collected]

            for b in butterflies:
                b.update(dt)

            for burst in list(petal_bursts):
                burst.update()
                if not burst.alive:
                    petal_bursts.remove(burst)

            heal_prompt_flower = None
            for flower in flowers:
                if flower.state == "wilted" and abs(flower.x - player.x) < Flower.HEAL_RANGE:
                    heal_prompt_flower = flower
                    break

            if player.x >= LEVEL_END_X:
                state = STATE_WIN
                win_petals = FloatingPetals(SCREEN_WIDTH, SCREEN_HEIGHT)

        glow_t += dt * 3

        # --- draw ---
        draw_sky(screen)
        draw_background(screen, camera, bg_image, corrupted_zone)
        draw_ground(screen, camera, ground_segments)
        for plat in platforms:
            if plat not in ground_segments:
                draw_platform(screen, camera, plat, glow_t)
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
        draw_text(screen, "Move: A/D or Arrows   Jump: Space   Heal: E", 20, SCREEN_HEIGHT - 26,
                  (255, 255, 255), 16)
        if state == STATE_PLAY and heal_prompt_flower is not None and not player.healing:
            draw_text(screen, "Press E to heal this flower",
                      SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60, (255, 240, 200), 22, center=True)

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

        elif state == STATE_WIN:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((20, 10, 25, 175))
            screen.blit(overlay, (0, 0))
            if win_petals is not None:
                win_petals.update(dt)
                win_petals.draw(screen)
            draw_text(screen, "Spring Sanctuary Cleansed", SCREEN_WIDTH // 2, 220,
                      (255, 225, 240), 38, center=True)
            draw_text(screen, f"Petals collected: {player.petals_collected}",
                      SCREEN_WIDTH // 2, 290, CREAM, 24, center=True)
            draw_text(screen, f"Flowers healed: {player.flowers_healed}/{len(flowers)}",
                      SCREEN_WIDTH // 2, 326, CREAM, 24, center=True)
            draw_text(screen, "Press R to replay or ESC to quit", SCREEN_WIDTH // 2, 400,
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
