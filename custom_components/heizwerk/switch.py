"""switch.heizwerk_<room>_observe_only: compute, but do not send commands."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeizwerkConfigEntry
from .const import CONF_OBSERVE_ONLY
from .entity import HeizwerkEntity
from .room import RoomController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizwerkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One switch per room."""
    for subentry_id, room in entry.runtime_data.rooms.items():
        async_add_entities(
            [ObserveOnlySwitch(entry, subentry_id, room)],
            config_subentry_id=subentry_id,
        )


class ObserveOnlySwitch(HeizwerkEntity, SwitchEntity):
    """Stored in the room subentry, so it survives restarts and reloads."""

    _attr_translation_key = "observe_only"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: HeizwerkConfigEntry,
        subentry_id: str,
        room: RoomController,
    ) -> None:
        """Bind to the room."""
        super().__init__(room, "observe_only")
        self.entity_id = f"switch.{self._object_id}"
        self._entry = entry
        self._subentry_id = subentry_id

    @property
    def is_on(self) -> bool:
        """Observe only."""
        return self.room.observe_only

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Stop sending commands."""
        self._store(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Start controlling the thermostats."""
        self._store(False)

    def _store(self, value: bool) -> None:
        # The update listener reloads the entry with the new setting.
        subentry = self._entry.subentries[self._subentry_id]
        self.hass.config_entries.async_update_subentry(
            self._entry, subentry, data={**subentry.data, CONF_OBSERVE_ONLY: value}
        )
