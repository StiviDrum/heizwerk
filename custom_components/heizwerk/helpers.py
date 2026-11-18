"""Small shared helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def heizwerk_entities(hass: HomeAssistant) -> list[str]:
    """All entity ids created by Heizwerk itself."""
    return sorted(
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == DOMAIN
    )


def is_heizwerk_entity(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Whether entity_id belongs to Heizwerk.

    Heizwerk must never control or follow its own entities: using a room's
    climate entity as Zeitwerk target or thermostat makes Heizwerk call
    itself in an endless loop.
    """
    if not entity_id:
        return False
    entry = er.async_get(hass).async_get(entity_id)
    return entry is not None and entry.platform == DOMAIN
