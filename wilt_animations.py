import os
import pygame
import sys

pygame.init()

# CHANGE TO LOCAL PATH 
ASSET_DIR = "/Users/liliiagubaeva/IMAGES/Imaging Movements"

# Screen settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Target size for the Wilt
CHARACTER_WIDTH = 150
CHARACTER_HEIGHT = 200


def load_image(fname):
    """Load an image by searching through all subdirectories."""
    for root, dirs, files in os.walk(ASSET_DIR):
        if fname in files:
            full_path = os.path.join(root, fname)
            img = pygame.image.load(full_path).convert_alpha()
            return pygame.transform.scale(img, (CHARACTER_WIDTH, CHARACTER_HEIGHT))

    raise FileNotFoundError(f"Could not find '{fname}' in {ASSET_DIR}")


# Animations with their frame delays (in milliseconds).
ANIMATIONS = {
    "default": {
        # idle / default appearance, single static frame
        "frames": ["Wilt BG REMOVED.png"],
        "delay": 1000
    },
    "evil": {
        # frames 1-3: eyes slowly turning evil, frame 4: sudden lightning strike
        "frames": ["wilt_evil1.png", "wilt_evil2.png", "wilt_evil3.png", "wilt_evil4.png"],
        "delay": [250, 250, 250, 450]
    },
    "attack": {
        # 1: gets ready, 2: splits spores, 3: covered in spore particles
        "frames": ["wilt_norm_attack1.png", "wilt_norm_attack2.png", "wilt_norm_attack3.png"],
        "delay": [200, 180, 320]
    },
    "ultimate": {
        # 1: gets ready, 2: splits dark vines, 3: closes eyes
        "frames": ["wilt_ult_attack1.png", "wilt_ult_attack2.png", "wilt_ult_attack3.png"],
        "delay": [250, 250, 450]
    },
    "defeated": {
        # constantly lying down defeated, slow idle loop
        "frames": ["wilt_defeated1.png", "wilt_defeated23.png", "wilt_defeated32.png", "wilt_defeated4.png"],
        "delay": 400
    }
}


class Animator:
    def __init__(self, animations):
        self.animations = animations
        self.current_anim = "default"
        self.frame_index = 0
        self.last_update = pygame.time.get_ticks()
        self._image_cache = {}

        # Pre-load all images
        for anim_name, anim_data in animations.items():
            for fname in anim_data["frames"]:
                if fname not in self._image_cache:
                    self._image_cache[fname] = load_image(fname)

        # Get initial frame
        self.current_frame = self._get_frame()

    def _get_frame(self):
        """Get the current frame image."""
        frames = self.animations[self.current_anim]["frames"]
        return self._image_cache[frames[self.frame_index]]

    def _current_delay(self):
        """Resolve the delay for the current frame (supports per-frame delays)."""
        delay = self.animations[self.current_anim]["delay"]
        if isinstance(delay, list):
            return delay[self.frame_index]
        return delay

    def update(self):
        """Update animation based on time. Always loops."""
        current_time = pygame.time.get_ticks()

        if current_time - self.last_update >= self._current_delay():
            num_frames = len(self.animations[self.current_anim]["frames"])
            self.frame_index = (self.frame_index + 1) % num_frames
            self.current_frame = self._get_frame()
            self.last_update = current_time

    def set_animation(self, name):
        """Switch to a different animation."""
        if name in self.animations:
            self.current_anim = name
            self.frame_index = 0
            self.current_frame = self._get_frame()
            self.last_update = pygame.time.get_ticks()

    def get_current_frame(self):
        """Get the current frame to display."""
        return self.current_frame


def draw_text(screen, text, x, y, color=(255, 255, 255), size=24):
    """Helper to draw text on screen."""
    font = pygame.font.Font(None, size)
    text_surface = font.render(text, True, color)
    screen.blit(text_surface, (x, y))


def run_demo():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Wilt Animations")

    animator = Animator(ANIMATIONS)

    bg_color = (15, 25, 15)

    running = True
    clock = pygame.time.Clock()

    current_anim_name = "Default"

    print("\n=== Wilt Animation Demo ===")
    print("Controls:")
    print("  1 - Default")
    print("  2 - Evil Appearance")
    print("  3 - Normal Attack")
    print("  4 - Ultimate Attack")
    print("  5 - Defeated")
    print("  ESC - Quit")
    print("============================\n")

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    animator.set_animation("default")
                    current_anim_name = "Default"
                    print("Switched to: Default")
                elif event.key == pygame.K_2:
                    animator.set_animation("evil")
                    current_anim_name = "Evil Appearance"
                    print("Switched to: Evil Appearance")
                elif event.key == pygame.K_3:
                    animator.set_animation("attack")
                    current_anim_name = "Normal Attack"
                    print("Switched to: Normal Attack")
                elif event.key == pygame.K_4:
                    animator.set_animation("ultimate")
                    current_anim_name = "Ultimate Attack"
                    print("Switched to: Ultimate Attack")
                elif event.key == pygame.K_5:
                    animator.set_animation("defeated")
                    current_anim_name = "Defeated"
                    print("Switched to: Defeated")

        animator.update()

        screen.fill(bg_color)

        # Subtle background pattern
        for i in range(0, SCREEN_WIDTH, 40):
            for j in range(0, SCREEN_HEIGHT, 40):
                if (i + j) % 80 == 0:
                    pygame.draw.rect(screen, (25, 40, 25), (i, j, 40, 40))

        # Character panel background
        panel_rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 150, 300, 300)
        s = pygame.Surface((300, 300), pygame.SRCALPHA)
        s.fill((40, 60, 40, 180))
        screen.blit(s, (SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 150))
        pygame.draw.rect(screen, (90, 130, 90), panel_rect, 2, border_radius=15)

        # Current frame (centered in panel)
        frame = animator.get_current_frame()
        if frame:
            frame_rect = frame.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(frame, frame_rect)

        # Title
        draw_text(screen, "Wilt Animations", SCREEN_WIDTH // 2 - 100, 30, (180, 255, 150), 32)

        # Current animation label
        colors = {
            "Default": (200, 200, 200),
            "Evil Appearance": (180, 60, 220),
            "Normal Attack": (120, 220, 90),
            "Ultimate Attack": (60, 30, 90),
            "Defeated": (150, 150, 150)
        }
        color = colors.get(current_anim_name, (255, 255, 255))
        draw_text(screen, f"> {current_anim_name}", 30, 90, color, 30)

        # Frame info
        anim_data = ANIMATIONS[animator.current_anim]
        draw_text(screen, f"Frame {animator.frame_index + 1}/{len(anim_data['frames'])}", 30, 130, (200, 220, 200), 24)

        # Controls bar
        controls_bg = pygame.Rect(20, SCREEN_HEIGHT - 80, SCREEN_WIDTH - 40, 60)
        s = pygame.Surface((SCREEN_WIDTH - 40, 60), pygame.SRCALPHA)
        s.fill((0, 0, 0, 150))
        screen.blit(s, (20, SCREEN_HEIGHT - 80))
        pygame.draw.rect(screen, (90, 130, 90), controls_bg, 1, border_radius=10)

        draw_text(screen, "1:Default  2:Evil  3:Attack  4:Ultimate  5:Defeated  ESC:Quit",
                  SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT - 55, (200, 200, 200), 20)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    run_demo()
