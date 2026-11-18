"""binary_sensor.heizwerk_<room>_ventilation: airing recommended."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeizwerkConfigEntry
from .const import CONF_HUMIDITY_SENSOR
from .entity import HeizwerkEntity
from .room import RoomController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizwerkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Only rooms with a humidity sensor."""
    for subentry_id, room in entry.runtime_data.rooms.items():
        if room.config.get(CONF_HUMIDITY_SENSOR):
            async_add_entities(
                [VentilationSensor(room)], config_subentry_id=subentry_id
            )


class VentilationSensor(HeizwerkEntity, BinarySensorEntity):
    """On when airing would lower the humidity and the window is closed."""

    _attr_translation_key = "ventilation"

    def __init__(self, room: RoomController) -> None:
        """Bind to the room."""
        super().__init__(room, "ventilation")
        self.entity_id = f"binary_sensor.{self._object_id}"

    @property
    def is_on(self) -> bool:
        """Airing recommended."""
        return bool(self.room.values.get("ventilation_recommended"))
