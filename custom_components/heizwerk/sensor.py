"""Room climate sensors: dew point and wall humidity."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeizwerkConfigEntry
from .const import CONF_HUMIDITY_SENSOR, CONF_WALL_TEMPERATURE_SENSOR
from .entity import HeizwerkEntity
from .room import RoomController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizwerkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Dew point with a humidity sensor, wall humidity with a wall sensor too."""
    for subentry_id, room in entry.runtime_data.rooms.items():
        entities: list[SensorEntity] = []
        if room.config.get(CONF_HUMIDITY_SENSOR):
            entities.append(DewPointSensor(room))
            if room.config.get(CONF_WALL_TEMPERATURE_SENSOR):
                entities.append(WallHumiditySensor(room))
        if entities:
            async_add_entities(entities, config_subentry_id=subentry_id)


class DewPointSensor(HeizwerkEntity, SensorEntity):
    """Dew point of the room air."""

    _attr_translation_key = "dew_point"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, room: RoomController) -> None:
        """Bind to the room."""
        super().__init__(room, "dew_point")
        self.entity_id = f"sensor.{self._object_id}"

    @property
    def native_value(self) -> float | None:
        """Dew point in °C."""
        return self.room.values.get("dew_point")


class WallHumiditySensor(HeizwerkEntity, SensorEntity):
    """Relative humidity at the (cold) wall surface – mold risk indicator."""

    _attr_translation_key = "wall_humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, room: RoomController) -> None:
        """Bind to the room."""
        super().__init__(room, "wall_humidity")
        self.entity_id = f"sensor.{self._object_id}"

    @property
    def native_value(self) -> float | None:
        """Wall humidity in %."""
        return self.room.values.get("wall_humidity")

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Mold level ok / warning / alarm."""
        return {"mold_level": self.room.attributes.get("mold_level")}
