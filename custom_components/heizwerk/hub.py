"""Hub: one room controller per room subentry."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import SUBENTRY_ROOM
from .room import RoomController


class HeizwerkHub:
    """Runtime data of the Heizwerk config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create controllers for all rooms."""
        self.hass = hass
        self.entry = entry
        hub_config = {**entry.data, **entry.options}
        self.rooms: dict[str, RoomController] = {
            subentry.subentry_id: RoomController(
                hass, subentry.subentry_id, subentry.data, hub_config
            )
            for subentry in entry.get_subentries_of_type(SUBENTRY_ROOM)
        }

    async def async_setup(self) -> None:
        """Nothing to load yet (state is restored by the climate entities)."""

    @callback
    def async_start(self) -> None:
        """Start all rooms once the platforms (and restore) are set up."""
        for room in self.rooms.values():
            room.async_start()

    @callback
    def async_stop(self) -> None:
        """Stop all rooms."""
        for room in self.rooms.values():
            room.async_stop()

    def room_by_entity(self, entity_id: str) -> RoomController | None:
        """Room whose climate entity is entity_id."""
        return next(
            (r for r in self.rooms.values() if r.climate_entity_id == entity_id), None
        )
