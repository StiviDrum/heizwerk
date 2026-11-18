"""Diagnostics download."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import HeizwerkConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HeizwerkConfigEntry
) -> dict[str, Any]:
    """House options and every room's config, runtime state and attributes."""
    return {
        "options": dict(entry.options),
        "rooms": [room.diagnostics() for room in entry.runtime_data.rooms.values()],
    }
