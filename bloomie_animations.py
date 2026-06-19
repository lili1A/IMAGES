import os
import pygame
import sys


pygame.init()

# CHANGE TO LOCAL PATH 
ASSET_DIR = "/Users/liliiagubaeva/IMAGES-2/Imaging Movements"

# Screen settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Target size for the character (adjust these values)
CHARACTER_WIDTH = 150
CHARACTER_HEIGHT = 200

def load_image(fname):
    """Load an image by searching through all subdirectories."""
    for root, dirs, files in os.walk(ASSET_DIR):
        if fname in files:
            full_path = os.path.join(root, fname)
            img = pygame.image.load(full_path).convert_alpha()
            # Scale the image to fit the screen
            return pygame.transform.scale(img, (CHARACTER_WIDTH, CHARACTER_HEIGHT))
    
    raise FileNotFoundError(f"Could not find '{fname}' in {ASSET_DIR}")

# animations with their frame delays (in milliseconds)
ANIMATIONS = {
    "walk": {
        "frames": ["bloomie_walk1.png", "bloomie_walk2.png", "bloomie_walk3.png", "bloomie_walk4.png"],
        "delay": 150
    },
    "dash": {
        "frames": ["bloomie_dash1.png", "bloomie_dash2.png", "bloomie_dash3.png", "bloomie_dash4.png"],
        "delay": 80
    },
    "jump": {
        "frames": ["bloomie_jump1.png", "bloomie_jump2.png", "bloomie_jump3.png"],
        "delay": 200
    },
    "heal": {
        "frames": ["bloomie_heal1.png", "bloomie_heal2.png", "bloomie_heal3.png", "bloomie_heal4.png"],
        "delay": 250
    },
    "victory": {
        "frames": ["bloomie_vic1.png", "bloomie_vic2.png", "bloomie_vic3.png"],
        "delay": 300
    }
}

class Animator:
    def __init__(self, animations):
        self.animations = animations
        self.current_anim = "walk"
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
    
    def update(self):
        """Update animation based on time."""
        current_time = pygame.time.get_ticks()
        anim_data = self.animations[self.current_anim]
        
        # Check if it's time to advance
        if current_time - self.last_update >= anim_data["delay"]:
            self.frame_index = (self.frame_index + 1) % len(anim_data["frames"])
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

def draw_rounded_rect(screen, color, rect, radius=10):
    """Draw a rounded rectangle."""
    pygame.draw.rect(screen, color, rect, border_radius=radius)

def run_demo():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Bloomie Animations")
    
    # Create animator
    animator = Animator(ANIMATIONS)
    
    # Colors
    bg_color = (20, 20, 40)
    panel_color = (40, 40, 70, 180)
    
    running = True
    clock = pygame.time.Clock()
    
    # Animation state tracking
    current_anim_name = "Walk"
    
    print("\n=== Bloomie Animation Demo ===")
    print("Controls:")
    print("  1 - Walk")
    print("  2 - Dash")
    print("  3 - Jump")
    print("  4 - Heal")
    print("  5 - Victory")
    print("  ESC - Quit")
    print("===============================\n")
    
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    animator.set_animation("walk")
                    current_anim_name = "Walk"
                    print("Switched to: Walk")
                elif event.key == pygame.K_2:
                    animator.set_animation("dash")
                    current_anim_name = "Dash"
                    print("Switched to: Dash")
                elif event.key == pygame.K_3:
                    animator.set_animation("jump")
                    current_anim_name = "Jump"
                    print("Switched to: Jump")
                elif event.key == pygame.K_4:
                    animator.set_animation("heal")
                    current_anim_name = "Heal"
                    print("Switched to: Heal")
                elif event.key == pygame.K_5:
                    animator.set_animation("victory")
                    current_anim_name = "Victory"
                    print("Switched to: Victory")
        
        # Update animation
        animator.update()
        
        # Draw everything
        screen.fill(bg_color)
        
        # Draw a subtle background pattern (optional)
        for i in range(0, SCREEN_WIDTH, 40):
            for j in range(0, SCREEN_HEIGHT, 40):
                if (i + j) % 80 == 0:
                    pygame.draw.rect(screen, (30, 30, 60), (i, j, 40, 40))
        
        # Draw character panel background
        panel_rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 150, 300, 300)
        s = pygame.Surface((300, 300), pygame.SRCALPHA)
        s.fill((40, 40, 70, 180))
        screen.blit(s, (SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 150))
        pygame.draw.rect(screen, (100, 100, 150), panel_rect, 2, border_radius=15)
        
        # Get and draw current frame (centered in panel)
        frame = animator.get_current_frame()
        if frame:
            frame_rect = frame.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(frame, frame_rect)
        
        # Draw UI overlay
        
        # Title
        draw_text(screen, "✨ Bloomie Animations ✨", SCREEN_WIDTH // 2 - 120, 30, (255, 200, 100), 32)
        
        # Current animation with colored indicator
        colors = {
            "Walk": (100, 255, 100),
            "Dash": (255, 200, 50),
            "Jump": (100, 200, 255),
            "Heal": (255, 100, 255),
            "Victory": (255, 215, 0)
        }
        color = colors.get(current_anim_name, (255, 255, 255))
        draw_text(screen, f"▶ {current_anim_name}", 30, 90, color, 30)
        
        # Frame info
        anim_data = ANIMATIONS[animator.current_anim]
        draw_text(screen, f"Frame {animator.frame_index + 1}/{len(anim_data['frames'])}", 30, 130, (200, 200, 255), 24)
        
        # Controls at bottom
        controls_bg = pygame.Rect(20, SCREEN_HEIGHT - 80, SCREEN_WIDTH - 40, 60)
        s = pygame.Surface((SCREEN_WIDTH - 40, 60), pygame.SRCALPHA)
        s.fill((0, 0, 0, 150))
        screen.blit(s, (20, SCREEN_HEIGHT - 80))
        pygame.draw.rect(screen, (100, 100, 150), controls_bg, 1, border_radius=10)
        
        draw_text(screen, "1:Walk  2:Dash  3:Jump  4:Heal  5:Victory  ESC:Quit", 
                  SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT - 55, (200, 200, 200), 20)
        
        # Update display
        pygame.display.flip()
        
        # Control game speed
        clock.tick(FPS)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    run_demo()