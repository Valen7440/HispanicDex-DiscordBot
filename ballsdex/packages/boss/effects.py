from ballsdex.core.models import BallInstance
from .utils import AUTONOMOUS_COMMUNITY, LATAM

def ceuta_furry_effect(instance: BallInstance) -> tuple[float | int, float | int]:
    if instance.countryball.country in LATAM:
        health = instance.health
        attack = instance.attack * (1 + (25 / 100))

        return int(attack), int(health)
    elif instance.countryball.country in AUTONOMOUS_COMMUNITY:
        health = instance.health * (1 - (35 / 100))
        attack = instance.attack

        return int(attack), int(health)
    else:
        return instance.attack, instance.health

def spain_effect(instance: BallInstance) -> tuple[float | int, float | int]:
    if not instance.countryball.country in AUTONOMOUS_COMMUNITY:
        return instance.attack, instance.health
    
    attack = instance.attack * (1 + (25 / 100))
    health = instance.health * (1 - (25 / 100))

    return int(attack), int(health)

def spanish_empire_effect(instance: BallInstance) -> tuple[float | int, float | int]:
    if not instance.countryball.country in LATAM:
        return instance.attack, instance.health
    
    attack = instance.attack * (1 + (15 / 100))
    health = instance.health * (1 - (20 / 100))

    return int(attack), int(health)