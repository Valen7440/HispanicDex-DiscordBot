import math
import random
from ballsdex.core.models import BallInstance, Player

class BattleBall:
    """
    Custom ball only used in battles
    """
    def __init__(self, ball: BallInstance):
        self.id = ball.pk
        self.ball = ball
        self.countryball = ball.countryball
        self.health = ball.health
        self.atk = ball.attack
        self.defense = round(math.sqrt(self.health * self.atk)) # probaremos esta nueva formula vale tio boe xddd

    def heal(self):
        default_min = random.randint(8, 20)
        health_min = random.randint(round(self.ball.health / 10), round(self.ball.health / 7))

        extra = max(default_min, health_min)
        self.health += extra
        return extra

    def attack(self, deal: float | int):

        if self.defense >= deal:
            self.defense -= deal
            text = f":heart: Vida: {self.health}, :shield: Defensa: -${deal} (${self.defense})\n"
        else:
            defense_damage = self.defense
            remaining_damage = deal - self.defense

            self.defense = 0
            self.health -= remaining_damage

            text = f":heart: Vida: -{remaining_damage} ({self.health}), :shield: Defensa: -{defense_damage} (0)\n"
        
        return text