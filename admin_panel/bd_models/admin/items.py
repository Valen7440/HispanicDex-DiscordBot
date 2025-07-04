from typing import TYPE_CHECKING, Any

from django.contrib import admin, messages
from django.db.models import Prefetch, Q
from django.utils.safestring import mark_safe

from ..models import ItemsBD, Ball, Special

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest, HttpResponse

@admin.register(ItemsBD)
class ItemsBDAdmin(admin.ModelAdmin):
    fields = ("name", "ball", "special", "value", "emoji_id", "can_register")
    autocomplete_fields = ("ball", "special")

    list_display = [
        "name",
        "country",
        "special_name",
        "emoji"
    ]
    search_help_text = (
        "Search by name, ball name or "
        "special name."
    )
    search_fields = ("name", "country", "special_name")

    def country(self, obj: ItemsBD) -> str | None:
        if obj.ball:
            return obj.ball.country
    
    def special_name(self, obj: ItemsBD) -> str | None:
        if obj.special:
            return obj.special.name
    
    @admin.display(description="Emoji of this item")
    def emoji(self, obj: ItemsBD) -> str | None:
        if obj.ball:
            return mark_safe(
                f'<img src="https://cdn.discordapp.com/emojis/{obj.ball.emoji_id}.png?size=40" '
                f'title="ID: {obj.ball.emoji_id}" />'
            )
        elif obj.special:
            return obj.special.emoji
        elif obj.emoji_id:
            return mark_safe(
                f'<img src="https://cdn.discordapp.com/emojis/{obj.emoji_id}.png?size=40" '
                f'title="ID: {obj.emoji_id}" />'
            )