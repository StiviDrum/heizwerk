"""Base entity for all room entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME
from .room import RoomController


class HeizwerkEntity(Entity):
    """Entity bound to a room controller; no polling."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, room: RoomController, key: str | None) -> None:
        """Set ids and device; entity_id follows heizwerk_<room>[_<key>]."""
        self.room = room
        suffix = f"_{key}" if key else ""
        self._attr_unique_id = f"{room.subentry_id}{suffix}"
        self._object_id = f"heizwerk_{room.slug}{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room.subentry_id)},
            name=f"{NAME} {room.name}",
            manufacturer=NAME,
            model="Room",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Follow the room's updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.room.async_add_listener(self.async_write_ha_state))
