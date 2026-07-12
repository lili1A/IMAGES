"""
Scene 3 - Dream Realm
======================
Bloomie enters the Dream Realm: a sky full of drifting clouds under a
dazzling moon, holding the Sanctuary's memories from before The Wilt.
There is no ground here - only four floating crystal islands, spaced too
far apart to simply jump between. Crossing them means using Bloomie's
Light Dash: a fast, low-gravity swoop through the sky, using her dash
frames, that covers the distance a normal jump can't. Shift+D dashes
right, Shift+A dashes left.

Bloomie starts already standing on the first island - no memory fragment
there, it's just solid ground to begin on - and the second island is
visible and reachable right away too. Each of the remaining three islands
holds one memory fragment; collecting it plays a shine burst, and then the
NEXT island rises up out of the clouds (it isn't just faded in) and
becomes solid ground to dash to. The fourth and final island - visibly
the biggest of the four - holds both the last memory fragment and the
crystal that closes out the level. Collecting that last fragment is also
the only point in the scene where the flower/Wilt flashback cutscene
plays.

Run with:
    pip install pygame pillow
    python3 "scene3_dream_realm.py"

This file must stay in the same folder as the "ISE " and "Imaging Movements"
asset folders (same place as scene1_spring_sanctuary.py) - assets are
located automatically by filename, so no paths need to be edited.

Asset -> usage map
--------------------------------------------------------
ISE /Scene 3/Scene 3 bg.png                     -> scrolling night-sky background
ISE /Scene 3/Side Platform.png                  -> island 0 (start, no pickup)
ISE /Scene 3/Middle platform.png                -> islands 1 and 2
ISE /Scene 3/Final platform.png                 -> island 3 (bigger, crystal + last memory)
ISE /Scene 3/Cloud Texture.png                  -> drifting ambient cloud layers
ISE /Scene 3/Star Particles .png                -> twinkling sky accents + part of
                                                    the "unlock" shine effect + landing sparkle
ISE /Scene 1/Sakura Petal Single.png            -> memory-fragment pickups
ISE /Scene 2/Rainbow Sparkles .png              -> the "unlock" shine burst
ISE /Scene 2/Crystal Activation Animation .gif  -> the end-of-level crystal
ISE /Scene 1/Sakura Flower.png                  -> flashback "restored garden" image
Imaging Movements/Wilt/Evil Appearance/wilt_evil2.png -> flashback "corruption" image
Imaging Movements/Bloomie/Bloomie LightDash/*   -> the Shift+D / Shift+A Light Dash animation
Imaging Movements/Bloomie/*                     -> Bloomie idle/walk/jump frames
ISE /Sounds/Dream Realm Theme Scene 3.mp3       -> scene BGM (kept low so it sits behind sfx)
ISE /Sounds/Memory Collection Sound Scene 3.mp3 -> plays when a fragment is collected
ISE /Sounds/Floating Island Movement  Scene 3.mp3 -> plays while an island rises up
ISE /Sounds/Flower Bloom Sound Scene 1, 4 .mp3  -> flashback "restored garden" beat
ISE /Sounds/Spore Explosion Sound Scene 4.mp3   -> flashback "corruption" beat (soft)
ISE /Sounds/Crystal Activation Sound Scene 2.mp3-> plays when the crystal is collected
ISE /Sounds/Bloomie Greeting Scene 1.mp3        -> plays on the title/intro card
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
    pass

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 576
FPS = 60

GRAVITY = 0.75
MOVE_SPEED = 4.5
JUMP_SPEED = -14.5

# Light Dash (Shift+F): a fast, mostly-horizontal swoop that covers far more
# ground than a normal jump, using much-reduced gravity while it's active.
# This is the intended way to cross the (deliberately too-wide-to-jump) gaps
# between islands - a normal jump only clears ~200px; the gaps here don't.
DASH_SPEED = 12.5
DASH_DURATION = 0.46
DASH_GRAVITY_MULT = 0.22
DASH_KICK = -3.5
DASH_COOLDOWN = 0.9

LEVEL_WIDTH = 1750

BLOOMIE_SIZE = (120, 120)
BLOOMIE_HEIGHT = 140

FALL_LIMIT = SCREEN_HEIGHT + 400

WHITE = (255, 255, 255)
CREAM = (255, 248, 235)
GOLD = (255, 210, 130)
SKY_TOP = (30, 25, 70)
SKY_BOTTOM = (70, 55, 120)

FRAGMENT_MEMORY_LINES = [
    "A memory of laughter drifts back to the garden...",
    "The scent of cherry blossoms returns on the wind...",
    "The last light of a peaceful evening glows once more...",
]


# ---------------------------------------------------------------------------
# Asset loading (same conventions as scene1_spring_sanctuary.py)
# ---------------------------------------------------------------------------
ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
_FILE_INDEX = {}
for _root, _dirs, _files in os.walk(ASSET_DIR):
    for _f in _files:
        _FILE_INDEX.setdefault(_f, os.path.join(_root, _f))


def find_asset(filename):
    if filename in _FILE_INDEX:
        return _FILE_INDEX[filename]
    raise FileNotFoundError(f"Could not locate '{filename}' under {ASSET_DIR}")


def _placeholder_image(size):
    w, h = size if size else (80, 80)
    surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    surf.fill((255, 0, 220, 255))
    pygame.draw.rect(surf, (0, 0, 0, 255), surf.get_rect(), 2)
    return surf


def load_image(filename, size=None):
    try:
        path = find_asset(filename)
    except FileNotFoundError as e:
        print(f"[scene3] WARNING: {e}. Using a placeholder image instead.")
        return _placeholder_image(size)
    img = pygame.image.load(path).convert_alpha()
    if size:
        img = pygame.transform.smoothscale(img, size)
    return img


def _frame_has_real_alpha(pil_img, threshold=0.6):
    """True if enough of the image's border pixels are actually transparent.
    Some source frames carry a baked-in solid background instead of real
    transparency; mixing those with properly-transparent frames in the same
    animation makes a colored box flash on screen as frames alternate."""
    if pil_img.mode != "RGBA":
        return False
    alpha = pil_img.split()[-1]
    w, h = pil_img.size
    xs = sorted({0, w // 4, w // 2, (3 * w) // 4, w - 1})
    ys = sorted({0, h // 4, h // 2, (3 * h) // 4, h - 1})
    points = set()
    for x in xs:
        points.add((x, 0))
        points.add((x, h - 1))
    for y in ys:
        points.add((0, y))
        points.add((w - 1, y))
    if not points:
        return False
    transparent = sum(1 for p in points if alpha.getpixel(p) < 250)
    return (transparent / len(points)) >= threshold


def _auto_key_out_background(pil_img, tolerance=34, feather=40):
    """Chroma-keys out a baked-in solid border color, feathering the cut
    edge so it doesn't look hard-edged, and returns an RGBA image."""
    if np is None:
        return pil_img
    img = pil_img.convert("RGBA")
    arr = np.array(img).astype(np.int16)
    h, w = arr.shape[:2]
    border_pts = (
        [(0, x) for x in range(0, w, max(1, w // 20))]
        + [(h - 1, x) for x in range(0, w, max(1, w // 20))]
        + [(y, 0) for y in range(0, h, max(1, h // 20))]
        + [(y, w - 1) for y in range(0, h, max(1, h // 20))]
    )
    samples = np.array([arr[y, x, :3] for y, x in border_pts])
    bg_color = np.median(samples, axis=0)
    diff = np.sqrt(((arr[:, :, :3] - bg_color) ** 2).sum(axis=2))
    alpha = arr[:, :, 3].astype(np.float32)
    key_mask = diff <= tolerance
    fade_mask = (diff > tolerance) & (diff <= tolerance + feather)
    fade_frac = np.clip((diff - tolerance) / max(1, feather), 0, 1)
    alpha = np.where(key_mask, 0, alpha)
    alpha = np.where(fade_mask, alpha * fade_frac, alpha)
    arr[:, :, 3] = np.clip(alpha, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def load_character_frame(filename, target_height):
    """Loads a sprite frame, crops it to its real alpha-channel content (so
    inconsistent source canvas sizes don't throw off scaling), keys out any
    baked-in solid background if the frame lacks real transparency, then
    scales to a consistent target height while preserving aspect ratio."""
    try:
        path = find_asset(filename)
    except FileNotFoundError as e:
        print(f"[scene3] WARNING: {e}. Using a placeholder image instead.")
        return _placeholder_image((target_height, target_height))

    if Image is None:
        img = pygame.image.load(path).convert_alpha()
        w, h = img.get_size()
        scale = target_height / h
        return pygame.transform.smoothscale(img, (max(1, int(w * scale)), target_height))

    pil_img = Image.open(path).convert("RGBA")
    if np is not None and not _frame_has_real_alpha(pil_img):
        pil_img = _auto_key_out_background(pil_img)

    bbox = pil_img.getbbox()
    if bbox:
        pil_img = pil_img.crop(bbox)
    w, h = pil_img.size
    scale = target_height / h
    new_w = max(1, int(w * scale))
    pil_img = pil_img.resize((new_w, target_height), Image.LANCZOS)

    mode = pil_img.mode
    data = pil_img.tobytes()
    surf = pygame.image.fromstring(data, pil_img.size, mode).convert_alpha()
    return surf


def load_sound(filename):
    try:
        path = find_asset(filename)
        return pygame.mixer.Sound(path)
    except (FileNotFoundError, pygame.error):
        return None


def play_sound(sound, volume=0.1):
    if sound is not None:
        sound.set_volume(volume)
        sound.play()


# ---------------------------------------------------------------------------
# Animator + Bloomie animations
# ---------------------------------------------------------------------------
class Animator:
    def __init__(self, anim_dict, target_height, start="idle"):
        self.anim_dict = anim_dict
        self.target_height = target_height
        self._cache = {}
        self.current_anim = start
        self.index = 0
        self.last_update = pygame.time.get_ticks()
        self.on_finish = None
        self.finished_once = False

    def _frames(self, name):
        if name not in self._cache:
            spec = self.anim_dict[name]
            self._cache[name] = [load_character_frame(f, self.target_height) for f in spec["frames"]]
        return self._cache[name]

    def set_animation(self, name, restart_if_same=False, on_finish=None):
        if name == self.current_anim and not restart_if_same:
            return
        self.current_anim = name
        self.index = 0
        self.last_update = pygame.time.get_ticks()
        self.on_finish = on_finish
        self.finished_once = False

    def update(self):
        spec = self.anim_dict[self.current_anim]
        frames = self._frames(self.current_anim)
        delay = spec.get("delay", 150)
        now = pygame.time.get_ticks()
        if now - self.last_update >= delay:
            self.last_update = now
            if self.index + 1 < len(frames):
                self.index += 1
            elif spec.get("loop", True):
                self.index = 0
            elif not self.finished_once:
                self.finished_once = True
                if self.on_finish:
                    self.on_finish()

    def frame(self, flip=False):
        frames = self._frames(self.current_anim)
        idx = min(self.index, len(frames) - 1)
        img = frames[idx]
        if flip:
            img = pygame.transform.flip(img, True, False)
        return img


BLOOMIE_ANIMATIONS = {
    "idle": {"frames": ["Bloomie BG REMOVED.png"], "delay": 1000, "loop": True},
    "walk": {
        "frames": ["bloomie_walk3.png", "bloomie_walk4.png"],
        "delay": 220, "loop": True,
    },
    "jump": {
        "frames": ["bloomie_jump1.png", "bloomie_jump2.png", "bloomie_jump3.png"],
        "delay": 130, "loop": False,
    },
    "dash": {
        "frames": ["bloomie_dash1.png", "bloomie_dash2.png", "bloomie_dash3.png", "bloomie_dash4.png"],
        "delay": 80, "loop": True,
    },
}


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
class Camera:
    def __init__(self, level_width, screen_width):
        self.offset_x = 0
        self.level_width = level_width
        self.screen_width = screen_width

    def update(self, target_x):
        self.offset_x = max(0, min(target_x - self.screen_width // 2,
                                    max(0, self.level_width - self.screen_width)))

    def apply(self, x):
        return x - self.offset_x


# ---------------------------------------------------------------------------
# Ambient sky: drifting clouds + twinkling stars
# ---------------------------------------------------------------------------
class Cloud:
    def __init__(self, image, x, y, speed, alpha, scale):
        self.x = x
        self.y = y
        self.speed = speed
        base = pygame.transform.smoothscale(
            image, (int(image.get_width() * scale), int(image.get_height() * scale)))
        base.set_alpha(alpha)
        self.surf = base

    def update(self, dt, level_width):
        self.x += self.speed * dt
        if self.speed >= 0 and self.x - self.surf.get_width() > level_width + 200:
            self.x = -200
        elif self.speed < 0 and self.x + self.surf.get_width() < -200:
            self.x = level_width + 200

    def draw(self, screen, cam, parallax):
        sx = self.x - cam.offset_x * parallax
        screen.blit(self.surf, (sx, self.y))


def make_cloud_layer(cloud_image, count, level_width, y_range, speed_range, alpha_range, scale_range):
    clouds = []
    for _ in range(count):
        x = random.uniform(-200, level_width + 200)
        y = random.uniform(*y_range)
        speed = random.uniform(*speed_range) * random.choice((-1, 1))
        alpha = random.randint(*alpha_range)
        scale = random.uniform(*scale_range)
        clouds.append(Cloud(cloud_image, x, y, speed, alpha, scale))
    return clouds


class TwinkleStars:
    """Small procedural dots (cheap, no asset needed) plus a few larger
    Star Particles accents, all pulsing gently for ambience."""

    def __init__(self, star_image, width, height, count=80, accents=6):
        self.width = width
        self.height = height
        self.dots = [
            {
                "x": random.uniform(0, width),
                "y": random.uniform(0, height * 0.55),
                "r": random.uniform(1, 2.4),
                "t": random.uniform(0, 6.28),
                "speed": random.uniform(1.2, 2.6),
            }
            for _ in range(count)
        ]
        small = pygame.transform.smoothscale(star_image, (70, 72))
        self.accents = []
        for _ in range(accents):
            self.accents.append({
                "img": small,
                "x": random.uniform(0, width),
                "y": random.uniform(0, height * 0.45),
                "t": random.uniform(0, 6.28),
                "speed": random.uniform(0.5, 1.0),
            })

    def update(self, dt):
        for d in self.dots:
            d["t"] += dt * d["speed"]
        for a in self.accents:
            a["t"] += dt * a["speed"]

    def draw(self, screen):
        for d in self.dots:
            alpha = int(120 + 100 * math.sin(d["t"]))
            alpha = max(30, min(255, alpha))
            surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 255, alpha), (2, 2), max(1, int(d["r"])))
            screen.blit(surf, (d["x"], d["y"]))
        for a in self.accents:
            alpha = int(70 + 60 * math.sin(a["t"]))
            alpha = max(0, min(140, alpha))
            img = a["img"].copy()
            img.set_alpha(alpha)
            rect = img.get_rect(center=(a["x"], a["y"]))
            screen.blit(img, rect)


# ---------------------------------------------------------------------------
# Unlock shine effect (rainbow/star burst - fragment pickups, island rises,
# and now landings too)
# ---------------------------------------------------------------------------
class ShineBurst:
    def __init__(self, sprite, x, y, max_scale=1.6, duration=0.7):
        self.sprite = sprite
        self.x = x
        self.y = y
        self.t = 0.0
        self.max_scale = max_scale
        self.duration = duration

    def update(self, dt):
        self.t += dt

    @property
    def alive(self):
        return self.t < self.duration

    def draw(self, screen, cam):
        p = min(1.0, self.t / self.duration)
        scale = 0.3 + self.max_scale * p
        alpha = int(255 * (1 - p) ** 1.5)
        if alpha <= 0:
            return
        img = pygame.transform.rotozoom(self.sprite, 0, scale)
        img = img.copy()
        img.set_alpha(alpha)
        rect = img.get_rect(center=(cam.apply(self.x), self.y))
        screen.blit(img, rect)


class LandingPuff:
    """A quick, cheap dust/sparkle puff spawned under Bloomie's feet the
    instant she touches down - a few expanding, fading rings, no art asset
    needed. Purely cosmetic (doesn't touch collision)."""
    DURATION = 0.35

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    @property
    def alive(self):
        return self.t < self.DURATION

    def draw(self, screen, cam):
        p = min(1.0, self.t / self.DURATION)
        cx = cam.apply(self.x)
        for i in range(3):
            ring_p = max(0.0, min(1.0, p - i * 0.12))
            if ring_p <= 0:
                continue
            r = int(6 + 26 * ring_p)
            alpha = int(150 * (1 - ring_p))
            if alpha <= 0:
                continue
            surf = pygame.Surface((r * 2 + 4, r + 4), pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (235, 230, 255, alpha), (2, 2, r * 2, r))
            screen.blit(surf, (cx - r - 2, self.y - r // 2 - 2))


# ---------------------------------------------------------------------------
# Memory fragment (collectible)
# ---------------------------------------------------------------------------
class MemoryFragment:
    BOB_RANGE = 8

    def __init__(self, x, y, image):
        self.x = x
        self.base_y = y
        self.image = image
        self.t = random.uniform(0, 6.28)
        self.collected = False
        self.available = False  # only collectible once its island is revealed

    def update(self, dt):
        self.t += dt * 1.8

    @property
    def y(self):
        return self.base_y + math.sin(self.t) * self.BOB_RANGE

    def draw(self, screen, cam):
        if self.collected or not self.available:
            return
        glow = 0.6 + 0.4 * math.sin(self.t * 1.6)
        img = pygame.transform.rotozoom(self.image, 0, 1.0 + 0.05 * glow)
        rect = img.get_rect(center=(cam.apply(self.x), self.y))
        screen.blit(img, rect)


# ---------------------------------------------------------------------------
# Floating island - starts completely absent, then RISES UP out of the
# clouds (from well below its resting height, fading in as it climbs) once
# unlocked, settling into a solid platform.
# ---------------------------------------------------------------------------
class FloatingIsland:
    RISE_DISTANCE = 260   # how far below its resting spot it starts from
    RISE_DURATION = 1.6
    TOP_FRAC = {
        # Side Platform bumped up from 0.20 -> 0.30 so Bloomie's feet (which
        # always sit exactly on the collision line) land visually embedded
        # in the platform art instead of hovering just above it.
        "Side Platform.png": 0.30,
        "Middle platform.png": 0.38,
        "Final platform.png": 0.48,
    }

    def __init__(self, asset, x, surface_y, target_height, revealed=False):
        self.asset = asset
        self.x = x
        self.surface_y = surface_y
        self.image = load_character_frame(asset, target_height)
        self.w, self.h = self.image.get_size()
        self.revealed = revealed
        self.reveal_t = 1.0 if revealed else 0.0
        self.bob_t = random.uniform(0, 6.28)

    def start_reveal(self):
        if not self.revealed:
            self.revealed = True
            self.reveal_t = 0.0

    def update(self, dt):
        self.bob_t += dt * 0.9
        if self.revealed and self.reveal_t < 1.0:
            self.reveal_t = min(1.0, self.reveal_t + dt / self.RISE_DURATION)

    @property
    def solid(self):
        return self.revealed and self.reveal_t >= 1.0

    @property
    def current_y(self):
        """Current surface height mid-rise (only meaningful for drawing -
        collision stays gated on .solid, i.e. only once the rise finishes,
        so there's no risk of Bloomie trying to land on a still-moving
        surface)."""
        if not self.revealed:
            return self.surface_y + self.RISE_DISTANCE
        ease = 1 - (1 - self.reveal_t) ** 3
        return self.surface_y + self.RISE_DISTANCE * (1 - ease)

    @property
    def rect(self):
        band_w = self.w * 0.62
        return pygame.Rect(int(self.x - band_w / 2), int(self.surface_y), int(band_w), 14)

    def draw(self, screen, cam):
        if not self.revealed:
            return
        ease = 1 - (1 - self.reveal_t) ** 3
        alpha = int(90 + 165 * ease)
        top_frac = self.TOP_FRAC.get(self.asset, 0.25)
        bob = math.sin(self.bob_t) * 3 if self.solid else 0
        img = self.image.copy()
        img.set_alpha(alpha)
        y_now = self.current_y + bob
        img_top_y = y_now - top_frac * img.get_height()
        rect = img.get_rect(midtop=(cam.apply(self.x), img_top_y))
        screen.blit(img, rect)
        if not self.solid:
            # rising sparkle trail beneath it while it's still climbing
            glow = pygame.Surface((self.w, 30), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (200, 220, 255, int(70 * ease)), glow.get_rect())
            screen.blit(glow, (rect.centerx - self.w // 2, y_now + 6))


# ---------------------------------------------------------------------------
# Bloomie
# ---------------------------------------------------------------------------
class Bloomie:
    LAND_SQUASH_DURATION = 0.16

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.on_ground = False
        self.facing_left = False
        self.animator = Animator(BLOOMIE_ANIMATIONS, BLOOMIE_HEIGHT, start="idle")
        self.fragments_collected = 0
        self.last_safe_x = x
        self.last_safe_y = y

        self.dashing = False
        self.dash_t = 0.0
        self.dash_dir = 1
        self.dash_cooldown = 0.0

        self.land_squash_t = 0.0
        self._was_on_ground = True

    @property
    def rect(self):
        w, h = BLOOMIE_SIZE
        return pygame.Rect(int(self.x - w * 0.28), int(self.y - h * 0.92), int(w * 0.56), int(h * 0.9))

    def try_jump(self):
        if self.on_ground and not self.dashing:
            self.vy = JUMP_SPEED
            self.on_ground = False
            self.animator.set_animation("jump", restart_if_same=True)

    def try_dash(self, direction=None):
        """Shift+D: Light Dash right. Shift+A: Light Dash left. A fast,
        low-gravity swoop in the given direction - the only way to cross
        the gaps between islands in this scene, since they're deliberately
        wider than a normal jump can clear. If no direction is passed,
        falls back to whichever way Bloomie is currently facing."""
        if self.dashing or self.dash_cooldown > 0:
            return False
        self.dashing = True
        self.dash_t = 0.0
        if direction is not None:
            self.dash_dir = direction
            self.facing_left = direction < 0
        else:
            self.dash_dir = -1 if self.facing_left else 1
        self.vy = DASH_KICK
        self.on_ground = False
        self.animator.set_animation("dash", restart_if_same=True)
        return True

    def update(self, keys, platforms, dt):
        landing_puff_pos = None

        if self.dashing:
            self.dash_t += dt
            self.vx = self.dash_dir * DASH_SPEED
            self.vy += GRAVITY * DASH_GRAVITY_MULT
            if self.dash_t >= DASH_DURATION:
                self.dashing = False
                self.dash_cooldown = DASH_COOLDOWN
        else:
            move = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                move -= 1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                move += 1
            self.vx = move * MOVE_SPEED
            if move != 0:
                self.facing_left = move < 0
            self.vy += GRAVITY
            self.vy = min(self.vy, 22)
            if self.dash_cooldown > 0:
                self.dash_cooldown = max(0.0, self.dash_cooldown - dt)

        self.x += self.vx
        self.x = max(40, min(self.x, LEVEL_WIDTH - 40))
        self.y += self.vy

        self.on_ground = False
        foot_rect = self.rect
        for plat in platforms:
            plat_rect = plat if isinstance(plat, pygame.Rect) else plat.rect
            # Landing check keyed off self.y (the render anchor) rather than
            # foot_rect.bottom - see scene1_spring_sanctuary.py's Bloomie for
            # why: foot_rect's height coefficients put its bottom a couple
            # of px above self.y, which caused on_ground to flicker False
            # for a frame right after landing there.
            if (foot_rect.right > plat_rect.left and foot_rect.left < plat_rect.right
                    and self.vy >= 0
                    and self.y >= plat_rect.top - 1
                    and self.y - self.vy <= plat_rect.top + 1):
                self.y = plat_rect.top
                self.vy = 0
                self.on_ground = True
                if self.dashing:
                    self.dashing = False
                    self.dash_cooldown = DASH_COOLDOWN

        if self.on_ground:
            self.last_safe_x = self.x
            self.last_safe_y = self.y

        respawned = False
        if self.y > FALL_LIMIT:
            self.x = self.last_safe_x
            self.y = self.last_safe_y - 40
            self.vy = 0
            self.dashing = False
            respawned = True

        if self.on_ground and not self._was_on_ground:
            self.land_squash_t = self.LAND_SQUASH_DURATION
            landing_puff_pos = (self.x, self.y)
        self._was_on_ground = self.on_ground
        if self.land_squash_t > 0:
            self.land_squash_t = max(0.0, self.land_squash_t - dt)

        if self.dashing:
            pass  # animator already locked to "dash"
        elif not self.on_ground:
            if self.animator.current_anim != "jump":
                self.animator.set_animation("jump", restart_if_same=False)
        elif self.vx != 0:
            self.animator.set_animation("walk")
        else:
            self.animator.set_animation("idle")

        self.animator.update()
        return respawned, landing_puff_pos

    def draw(self, screen, cam):
        img = self.animator.frame(flip=self.facing_left)
        if self.land_squash_t > 0:
            p = self.land_squash_t / self.LAND_SQUASH_DURATION
            sx = 1.0 + 0.24 * p
            sy = 1.0 - 0.20 * p
            w, h = img.get_size()
            img = pygame.transform.smoothscale(img, (max(1, int(w * sx)), max(1, int(h * sy))))
        rect = img.get_rect(midbottom=(int(cam.apply(self.x)), int(self.y)))
        screen.blit(img, rect)


# ---------------------------------------------------------------------------
# Crystal (finale collectible)
# ---------------------------------------------------------------------------
def load_gif_frames(filename, size=None):
    try:
        path = find_asset(filename)
    except FileNotFoundError as e:
        print(f"[scene3] WARNING: {e}. Using a placeholder animation instead.")
        return _placeholder_gif_frames(size)
    if Image is None:
        print(f"[scene3] WARNING: Pillow not installed, cannot read '{filename}'. Using a placeholder instead.")
        return _placeholder_gif_frames(size)
    pil_gif = Image.open(path)
    frames = []
    try:
        while True:
            frame = pil_gif.convert("RGBA")
            if size:
                frame = frame.resize(size, Image.LANCZOS)
            duration = pil_gif.info.get("duration", 80)
            data = frame.tobytes()
            surf = pygame.image.fromstring(data, frame.size, "RGBA").convert_alpha()
            frames.append((surf, duration))
            pil_gif.seek(pil_gif.tell() + 1)
    except EOFError:
        pass
    if not frames:
        return _placeholder_gif_frames(size)
    return frames


def _placeholder_gif_frames(size):
    w, h = size if size else (80, 80)
    frames = []
    for i in range(8):
        surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
        r = int(min(w, h) * 0.15 * (i + 1))
        pygame.draw.circle(surf, (150, 220, 255, 220), (w // 2, h // 2), max(2, r))
        frames.append((surf, 90))
    return frames


CRYSTAL_SIZE = (70, 90)


class Crystal:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.frames = load_gif_frames("Crystal Activation Animation .gif", CRYSTAL_SIZE)
        self.idle_frame = self.frames[0][0]
        self.state = "idle"  # idle -> activating -> collected
        self.frame_index = 0
        self.last_update = pygame.time.get_ticks()
        self.t = random.uniform(0, 6.28)

    def collect(self):
        if self.state == "idle":
            self.state = "activating"
            self.frame_index = 0
            self.last_update = pygame.time.get_ticks()

    def update(self, dt, on_collected):
        self.t += dt * 1.5
        if self.state != "activating":
            return
        img, duration = self.frames[self.frame_index]
        now = pygame.time.get_ticks()
        if now - self.last_update >= duration:
            self.last_update = now
            if self.frame_index + 1 < len(self.frames):
                self.frame_index += 1
            else:
                self.state = "collected"
                on_collected()

    def draw(self, screen, cam):
        if self.state == "collected":
            return
        bob = math.sin(self.t) * 6
        if self.state == "idle":
            img = self.idle_frame
        else:
            img = self.frames[min(self.frame_index, len(self.frames) - 1)][0]
        glow_r = 46
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pulse = 0.6 + 0.4 * math.sin(self.t * 1.3)
        pygame.draw.circle(glow, (190, 220, 255, int(90 * pulse)), (glow_r, glow_r), glow_r)
        gx = cam.apply(self.x)
        screen.blit(glow, (gx - glow_r, self.y - glow_r + bob))
        rect = img.get_rect(center=(gx, self.y + bob))
        screen.blit(img, rect)


# ---------------------------------------------------------------------------
# Flashback - a brief modal cutscene played when a memory fragment is
# collected: The Wilt's corruption first, then the flower restored, with
# sound and the memory caption. Freezes gameplay (no player/camera/island
# updates) for its short duration.
# ---------------------------------------------------------------------------
class Flashback:
    WILT_OUT = 1.0     # 0 -> WILT_OUT: wilt image visible
    FLOWER_IN = 1.25   # WILT_OUT -> FLOWER_IN: crossfade
    HOLD_END = 2.6      # FLOWER_IN -> HOLD_END: flower + caption held
    FADE_END = 3.0      # HOLD_END -> FADE_END: fade back to gameplay

    def __init__(self, wilt_img, flower_img, caption):
        self.wilt_img = wilt_img
        self.flower_img = flower_img
        self.caption = caption
        self.t = 0.0
        self.done = False
        self.played_flower_sfx = False

    def update(self, dt):
        self.t += dt
        if self.t >= self.FADE_END:
            self.done = True

    def skip(self):
        self.t = self.FADE_END

    def draw(self, screen):
        t = self.t
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        if t < self.FADE_END:
            dark = 210 if t < self.HOLD_END else int(210 * max(0.0, (self.FADE_END - t) / (self.FADE_END - self.HOLD_END)))
            overlay.fill((8, 6, 20, dark))
        screen.blit(overlay, (0, 0))

        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30
        if t < self.FLOWER_IN:
            p = min(1.0, t / self.WILT_OUT) if t < self.WILT_OUT else 1.0
            fade_out = 1.0
            if t >= self.WILT_OUT:
                fade_out = max(0.0, 1 - (t - self.WILT_OUT) / (self.FLOWER_IN - self.WILT_OUT))
            img = self.wilt_img.copy()
            tinted = img.copy()
            tinted.fill((80, 60, 110, 255), special_flags=pygame.BLEND_RGBA_MULT)
            tinted.set_alpha(int(255 * p * fade_out))
            rect = tinted.get_rect(center=(cx, cy))
            screen.blit(tinted, rect)
        if t >= self.WILT_OUT:
            p = min(1.0, (t - self.WILT_OUT) / (self.FLOWER_IN - self.WILT_OUT))
            img = self.flower_img.copy()
            img.set_alpha(int(255 * p))
            rect = img.get_rect(center=(cx, cy))
            screen.blit(img, rect)

        if t >= self.FLOWER_IN - 0.15:
            cap_p = min(1.0, (t - (self.FLOWER_IN - 0.15)) / 0.5)
            font = pygame.font.SysFont("arial", 22, bold=True, italic=True)
            surf = font.render(self.caption, True, CREAM)
            surf.set_alpha(int(255 * cap_p))
            screen.blit(surf, surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 130)))
        if t >= self.FLOWER_IN:
            hint_font = pygame.font.SysFont("arial", 15)
            hint = hint_font.render("press any key to skip", True, (200, 195, 220))
            screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40)))


# ---------------------------------------------------------------------------
# Level layout - 4 islands, deliberately spaced beyond normal jump range
# (see the dash-distance calibration note in build_level's docstring).
# ---------------------------------------------------------------------------
ISLAND_DEFS = [
    # asset, x, surface_y, target_height
    ("Side Platform.png", 180, 400, 210),
    ("Middle platform.png", 564, 380, 200),
    ("Middle platform.png", 972, 400, 200),
    ("Final platform.png", 1400, 380, 320),
]


def build_level(fragment_image):
    """
    Four floating islands. Bloomie starts already standing on the first
    (no memory fragment needed there - it's simply solid ground to begin
    on), and the second island is visible and reachable right away too.
    From there, each of the remaining three islands holds one memory
    fragment; collecting it is what calls the *next* island up out of the
    clouds. The fourth (final, and now visibly larger) island holds both
    the last memory fragment and the crystal that closes out the level -
    it's also the only island whose fragment triggers the flower/Wilt
    flashback cutscene.

    Gaps were sized against Light-Dash range, empirically bisected the
    same way jump range was measured in scene1_spring_sanctuary.py:
    DASH_SPEED/DASH_DURATION/DASH_GRAVITY_MULT fixed, then binary-search
    the farthest gap Bloomie can actually cross for a given height change,
    *while holding the travel direction key through and after the dash*
    (the intended technique - Light Dash covers the first ~340px on its own
    low-gravity swoop, and simply continuing to hold the direction key lets
    normal movement carry her the rest of the way down onto the target
    while she falls). Height deltas were kept modest (+/-20px) because the
    dash's own lift is small (~30px max) - it's built for distance, not
    altitude. Gaps here (~250-290px) are well beyond a normal jump's
    ~200px reach on purpose, so Light Dash (Shift+D / Shift+A) is required,
    not just an option.

    Islands 0 and 1 are solid from the start; islands 2-3 are simply not
    drawn/collidable at all until their unlocking fragment is collected, at
    which point they rise up out of the clouds into place (FloatingIsland.
    start_reveal). Each fragment floats just above its own island.
    """
    islands = []
    for i, (asset, x, surface_y, h) in enumerate(ISLAND_DEFS):
        islands.append(FloatingIsland(asset, x, surface_y, h, revealed=(i <= 1)))

    # Fragments map 1:1 to islands[1:] - the starting island has no pickup,
    # since Bloomie is simply already standing there when the scene begins.
    fragments = []
    for island_index in range(1, len(islands)):
        asset, x, surface_y, _h = ISLAND_DEFS[island_index]
        fx = x + 25
        fy = surface_y - 60
        frag = MemoryFragment(fx, fy, fragment_image)
        if island_index == 1:
            frag.available = True
        fragments.append(frag)

    return islands, fragments


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_sky(screen):
    for i in range(SCREEN_HEIGHT):
        t = i / SCREEN_HEIGHT
        color = [int(SKY_TOP[c] * (1 - t) + SKY_BOTTOM[c] * t) for c in range(3)]
        pygame.draw.line(screen, color, (0, i), (SCREEN_WIDTH, i))


def draw_background(screen, cam, bg_image):
    bg_w = bg_image.get_width()
    parallax = cam.offset_x * 0.4
    start = -(int(parallax) % bg_w)
    x = start
    while x < SCREEN_WIDTH:
        screen.blit(bg_image, (x, SCREEN_HEIGHT - bg_image.get_height()))
        x += bg_w


def draw_text(screen, text, x, y, color=WHITE, size=24, center=False, shadow=True):
    font = pygame.font.SysFont("arial", size, bold=True)
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(x, y)) if center else (x, y)
    if shadow:
        shadow_surf = font.render(text, True, (0, 0, 0))
        if center:
            screen.blit(shadow_surf, (rect.x + 2, rect.y + 2))
        else:
            screen.blit(shadow_surf, (x + 2, y + 2))
    screen.blit(surf, rect)
    return rect


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


def draw_fragment_counter(screen, x, y, collected, total):
    for i in range(total):
        cx = x + i * 26
        color = GOLD if i < collected else (90, 85, 120)
        pygame.draw.circle(screen, color, (cx, y), 9)
        pygame.draw.circle(screen, WHITE, (cx, y), 9, 1)


def draw_dash_meter(screen, x, y, cooldown, on_cooldown_max):
    ready = cooldown <= 0
    label = "Light Dash: READY (Shift+D / Shift+A)" if ready else "Light Dash: recharging..."
    color = (170, 230, 255) if ready else (120, 120, 150)
    draw_text(screen, label, x, y, color, 16)
    if not ready:
        bar_w = 120
        pygame.draw.rect(screen, (60, 60, 90), (x, y + 14, bar_w, 6), border_radius=3)
        frac = 1 - (cooldown / on_cooldown_max)
        pygame.draw.rect(screen, (170, 230, 255), (x, y + 14, int(bar_w * frac), 6), border_radius=3)


NARRATIVE = ("Bloomie enters the Dream Realm - a magical place where drifting clouds "
             "float under the dazzling light of the moon. The islands here are too far "
             "apart to jump between - hold Shift+D to Light Dash right, or Shift+A to "
             "Light Dash left, across the gaps. Collect the memory fragments to call "
             "each next island up out of the clouds.")
OUTRO_TEXT = ("The Dream Realm's memories are safe once more. But somewhere beyond "
              "the clouds, The Wilt is still waiting...")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Scene 3 - Dream Realm")
    clock = pygame.time.Clock()

    bg_image = load_image("Scene 3 bg.png",
                           (int(2732 * (SCREEN_HEIGHT / 1536)), SCREEN_HEIGHT))
    cloud_image = load_image("Cloud Texture.png")
    star_image = load_image("Star Particles .png")
    # load_character_frame (content-crop + scale-by-height) rather than
    # load_image, so the single petal's real aspect ratio is preserved
    # instead of getting squashed by a fixed-size load_image call.
    fragment_image = load_character_frame("Sakura Petal Single.png", 30)
    shine_image = load_image("Rainbow Sparkles .png", (140, 168))
    flashback_wilt_img = load_character_frame("wilt_evil2.png", 300)
    flashback_flower_img = load_character_frame("Sakura Flower.png", 220)

    bgm = None
    try:
        bgm_path = find_asset("Dream Realm Theme Scene 3.mp3")
        pygame.mixer.music.load(bgm_path)
        pygame.mixer.music.set_volume(0.16)
        pygame.mixer.music.play(-1)
        bgm = True
    except (pygame.error, FileNotFoundError):
        pass

    greeting_sfx = load_sound("Bloomie Greeting Scene 1.mp3")
    memory_sfx = load_sound("Memory Collection Sound Scene 3.mp3")
    island_sfx = load_sound("Floating Island Movement  Scene 3.mp3")
    crystal_sfx = load_sound("Crystal Activation Sound Scene 2.mp3")
    flower_sfx = load_sound("Flower Bloom Sound Scene 1, 4 .mp3")
    wilt_sfx = load_sound("Spore Explosion Sound Scene 4.mp3")

    islands, fragments = build_level(fragment_image)
    platforms = []

    far_clouds = make_cloud_layer(cloud_image, 6, LEVEL_WIDTH, (30, 140), (4, 10), (60, 110), (0.8, 1.3))
    near_clouds = make_cloud_layer(cloud_image, 5, LEVEL_WIDTH, (380, 520), (14, 26), (140, 200), (1.1, 1.8))
    stars = TwinkleStars(star_image, LEVEL_WIDTH, SCREEN_HEIGHT)

    player = Bloomie(islands[0].x, islands[0].surface_y)
    camera = Camera(LEVEL_WIDTH, SCREEN_WIDTH)

    crystal = Crystal(islands[-1].x, islands[-1].surface_y - 150)

    bursts = []
    puffs = []
    caption_text = ""
    caption_timer = 0.0
    flashback = None

    STATE_INTRO, STATE_PLAY, STATE_FLASHBACK, STATE_OUTRO, STATE_WIN = "intro", "play", "flashback", "outro", "win"
    state = STATE_INTRO
    intro_played_sound = False
    outro_timer = 0.0

    def on_fragment_collected(index, frag):
        nonlocal caption_text, caption_timer, flashback
        play_sound(memory_sfx, 0.85)
        player.fragments_collected += 1
        bursts.append(ShineBurst(shine_image, frag.x, frag.y))
        caption = FRAGMENT_MEMORY_LINES[index] if index < len(FRAGMENT_MEMORY_LINES) else ""
        caption_text = caption
        caption_timer = 3.0
        # fragments[i] lives on islands[i + 1] (island 0 has no pickup), so
        # the next island to call up out of the clouds is islands[i + 2].
        is_last = (index == len(fragments) - 1)
        if not is_last:
            next_island = islands[index + 2]
            next_island.start_reveal()
            play_sound(island_sfx, 0.8)
            fragments[index + 1].available = True
        else:
            # Only the final platform's memory triggers the flashback.
            flashback = Flashback(flashback_wilt_img, flashback_flower_img, caption)

    running = True
    max_frames = os.environ.get("SCENE3_MAX_FRAMES")
    max_frames = int(max_frames) if max_frames else None
    frame_count = 0

    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)
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
                    if event.key in (pygame.K_SPACE, pygame.K_UP):
                        player.try_jump()
                    elif event.key == pygame.K_d and (event.mod & pygame.KMOD_SHIFT):
                        player.try_dash(1)
                    elif event.key == pygame.K_a and (event.mod & pygame.KMOD_SHIFT):
                        player.try_dash(-1)
                elif state == STATE_FLASHBACK:
                    if flashback is not None:
                        flashback.skip()
                elif state == STATE_OUTRO:
                    state = STATE_WIN
                elif state == STATE_WIN and event.key == pygame.K_r:
                    return "restart"

        if state == STATE_INTRO:
            if not intro_played_sound:
                play_sound(greeting_sfx, 0.9)
                intro_played_sound = True

        elif state == STATE_PLAY:
            keys = pygame.key.get_pressed()

            for isl in islands:
                isl.update(dt)
            platforms = [isl for isl in islands if isl.solid]

            respawned, landing_puff_pos = player.update(keys, platforms, dt)
            if respawned:
                play_sound(island_sfx, 0.5)
            if landing_puff_pos is not None:
                puffs.append(LandingPuff(*landing_puff_pos))
            camera.update(player.x)

            for frag in fragments:
                frag.update(dt)
            for i, frag in enumerate(fragments):
                if frag.available and not frag.collected:
                    dx = frag.x - player.x
                    dy = frag.y - player.y
                    if dx * dx + dy * dy < 42 * 42:
                        frag.collected = True
                        on_fragment_collected(i, frag)

            for cl in far_clouds:
                cl.update(dt, LEVEL_WIDTH)
            for cl in near_clouds:
                cl.update(dt, LEVEL_WIDTH)
            stars.update(dt)

            for b in list(bursts):
                b.update(dt)
                if not b.alive:
                    bursts.remove(b)
            for p in list(puffs):
                p.update(dt)
                if not p.alive:
                    puffs.remove(p)

            if caption_timer > 0:
                caption_timer -= dt

            if crystal.state == "idle" and player.fragments_collected >= len(fragments):
                dx = crystal.x - player.x
                dy = crystal.y - player.y
                if dx * dx + dy * dy < 60 * 60:
                    crystal.collect()
                    play_sound(crystal_sfx, 0.9)

            def _on_crystal_collected():
                nonlocal state, outro_timer
                state = STATE_OUTRO
                outro_timer = 0.0

            crystal.update(dt, _on_crystal_collected)

            if flashback is not None:
                state = STATE_FLASHBACK

        elif state == STATE_FLASHBACK:
            if flashback is not None:
                flashback.update(dt)
                # played_flower_sfx doubles as a 3-value progress marker:
                # False -> "wilt" (corruption beat played) -> True (flower
                # beat played) - each sfx fires exactly once, in order.
                if flashback.played_flower_sfx is False and flashback.t >= flashback.WILT_OUT - 0.05:
                    play_sound(wilt_sfx, 0.35)
                    flashback.played_flower_sfx = "wilt"
                elif flashback.played_flower_sfx == "wilt" and flashback.t >= flashback.FLOWER_IN:
                    play_sound(flower_sfx, 0.7)
                    flashback.played_flower_sfx = True
                if flashback.done:
                    flashback = None
                    state = STATE_PLAY

        elif state == STATE_OUTRO:
            outro_timer += dt

        # --- draw ---
        draw_sky(screen)
        draw_background(screen, camera, bg_image)
        stars.draw(screen)
        for cl in far_clouds:
            cl.draw(screen, camera, parallax=0.25)

        for isl in islands:
            isl.draw(screen, camera)
        for frag in fragments:
            frag.draw(screen, camera)
        crystal.draw(screen, camera)
        for p in puffs:
            p.draw(screen, camera)
        if state in (STATE_PLAY, STATE_FLASHBACK, STATE_OUTRO):
            player.draw(screen, camera)
        for b in bursts:
            b.draw(screen, camera)

        for cl in near_clouds:
            cl.draw(screen, camera, parallax=0.7)

        if state in (STATE_PLAY, STATE_FLASHBACK):
            draw_text(screen, "Memories:", 20, 30, CREAM, 20)
            draw_fragment_counter(screen, 130, 30, player.fragments_collected, len(fragments))
            draw_dash_meter(screen, 20, 54, player.dash_cooldown, DASH_COOLDOWN)
            draw_text(screen, "Move: A/D or Arrows   Jump: Space/Up   Light Dash: Shift+D (right) / Shift+A (left)",
                      SCREEN_WIDTH // 2, SCREEN_HEIGHT - 24, (230, 230, 255), 16, center=True)
            if caption_timer > 0 and state == STATE_PLAY:
                alpha = min(255, int(255 * min(1.0, caption_timer)))
                cap_surf = pygame.font.SysFont("arial", 20, bold=True, italic=True).render(caption_text, True, CREAM)
                cap_surf.set_alpha(alpha)
                screen.blit(cap_surf, cap_surf.get_rect(center=(SCREEN_WIDTH // 2, 90)))
            elif player.fragments_collected >= len(fragments) and crystal.state == "idle":
                draw_text(screen, "The crystal awaits at the final island...",
                          SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50, (200, 220, 255), 20, center=True)

        if state == STATE_FLASHBACK and flashback is not None:
            flashback.draw(screen)

        if state == STATE_INTRO:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 8, 30, 170))
            screen.blit(overlay, (0, 0))
            draw_text(screen, "Scene 3 - Dream Realm", SCREEN_WIDTH // 2, 180, (225, 220, 255), 40, center=True)
            font = pygame.font.SysFont("arial", 20)
            lines = wrap_text(NARRATIVE, font, SCREEN_WIDTH - 220)
            for i, line in enumerate(lines):
                draw_text(screen, line, SCREEN_WIDTH // 2, 245 + i * 28, CREAM, 20, center=True)
            draw_text(screen, "Press any key to begin", SCREEN_WIDTH // 2, SCREEN_HEIGHT - 90, GOLD, 24, center=True)

        elif state == STATE_OUTRO:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 8, 30, min(200, int(outro_timer * 160))))
            screen.blit(overlay, (0, 0))
            font = pygame.font.SysFont("arial", 22)
            lines = wrap_text(OUTRO_TEXT, font, SCREEN_WIDTH - 260)
            for i, line in enumerate(lines):
                draw_text(screen, line, SCREEN_WIDTH // 2, 250 + i * 30, CREAM, 22, center=True)
            if outro_timer > 1.0:
                draw_text(screen, "Press any key to continue", SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60, GOLD, 20, center=True)
            if outro_timer > 7.0:
                state = STATE_WIN

        elif state == STATE_WIN:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 8, 30, 185))
            screen.blit(overlay, (0, 0))
            draw_text(screen, "The Dream Realm Remembers", SCREEN_WIDTH // 2, 220, (225, 220, 255), 38, center=True)
            draw_text(screen, f"Memory fragments recovered: {player.fragments_collected}/{len(fragments)}",
                      SCREEN_WIDTH // 2, 300, CREAM, 24, center=True)
            draw_text(screen, "Press R to replay or ESC to quit", SCREEN_WIDTH // 2, 400, GOLD, 22, center=True)

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
