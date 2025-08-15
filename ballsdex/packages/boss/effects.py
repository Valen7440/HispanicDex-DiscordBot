from ballsdex.core.models import BallInstance
from .utils import AUTONOMOUS_COMMUNITY, LATAM, SUMMER_BALLS

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

def chile_leviatan_effect(instance: BallInstance) -> tuple[int, int]:
    if instance.countryball.country in LATAM or instance.countryball.country in AUTONOMOUS_COMMUNITY or instance.countryball.country == "Spain":
        attack = instance.attack * (1 - (25 / 100))
        health = instance.health * (1 - (10 / 100))

        return int(attack), int(health)
    elif instance.countryball.country in SUMMER_BALLS:
        attack = instance.attack * (1 + (25 / 100))
        health = instance.health * (1 + (5 / 100))

        return int(attack), int(health)
    else:
        return instance.attack, instance.health