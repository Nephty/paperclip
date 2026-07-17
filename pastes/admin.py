from django.contrib import admin

from .models import Paste


@admin.register(Paste)
class PasteAdmin(admin.ModelAdmin):
    list_display = ("slug", "owner", "created_at", "burn_after_read", "private")
    list_filter = ("burn_after_read", "private")
    readonly_fields = ("slug", "created_at")
    search_fields = ("slug", "owner__username")
