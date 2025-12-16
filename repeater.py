from settings import *

class UIRepeater:
    def __init__(self, delay=200):
        self.delay = delay
        self.last = {}

    def allow(self, action):
        now = pygame.time.get_ticks()
        if action not in self.last or now - self.last[action] > self.delay:
            self.last[action] = now
            return True
        return False