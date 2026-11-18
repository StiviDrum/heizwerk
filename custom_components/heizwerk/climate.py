"""climate.heizwerk_<room>: the room as a thermostat."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, ClassVar

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import HeizwerkConfigEntry
from .const import STATUS_HEATING, STATUS_MANUAL, STATUS_OFF
from .entity import HeizwerkEntity
from .room import RoomController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizwerkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One climate entity per room (added to the room's subentry)."""
    for subentry_id, room in entry.runtime_data.rooms.items():
        async_add_entities([HeizwerkClimate(room)], config_subentry_id=subentry_id)


class _RestoreData(ExtraStoredData):
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def as_dict(self) -> dict[str, Any]:
        return self.data


class HeizwerkClimate(HeizwerkEntity, ClimateEntity, RestoreEntity):
    """Thermostat of a room: target from Zeitwerk, control by Heizwerk."""

    _attr_name = None
    _attr_translation_key = "room"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [HVACMode.HEAT, HVACMode.OFF]
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, room: RoomController) -> None:
        """Bind to the room."""
        super().__init__(room, None)
        self.entity_id = f"climate.{self._object_id}"
        self._attr_min_temp = room.min_temp
        self._attr_max_temp = room.max_temp

    async def async_added_to_hass(self) -> None:
        """Restore runtime state before the room starts."""
        await super().async_added_to_hass()
        self.room.climate_entity_id = self.entity_id
        if (extra := await self.async_get_last_extra_data()) is not None:
            self.room.async_restore(extra.as_dict())

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Persist manual override, base target and on/off."""
        return _RestoreData(self.room.restore_data())

    @property
    def hvac_mode(self) -> HVACMode:
        """Heat unless the room is switched off."""
        return HVACMode.HEAT if self.room.enabled else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Heating / idle / off."""
        decision = self.room.decision
        if decision is None:
            return None
        if decision.status == STATUS_OFF:
            return HVACAction.OFF
        if decision.heating and decision.status in (STATUS_HEATING, STATUS_MANUAL):
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def native_current_temperature(self) -> float | None:
        """Room temperature (external sensor, else TRV mean)."""
        return self.room.values.get("current")

    @property
    def current_humidity(self) -> float | None:
        """Room humidity."""
        return self.room.values.get("humidity")

    @property
    def native_target_temperature(self) -> float | None:
        """Effective target (manual or planned)."""
        return self.room.decision.target if self.room.decision else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Interface for the card (SPEC section 5)."""
        return self.room.attributes

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Manual override (with Zeitwerk target) or new base target."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        if (mode := kwargs.get("hvac_mode")) is not None:
            self.room.set_enabled(mode != HVACMode.OFF)
        await self.room.async_set_target(
            float(temperature), await self._user_name(), self._context
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch the room on/off."""
        self.room.set_enabled(hvac_mode != HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Switch on."""
        self.room.set_enabled(True)

    async def async_turn_off(self) -> None:
        """Switch off."""
        self.room.set_enabled(False)

    async def async_set_manual(
        self, temperature: float, duration: timedelta | None
    ) -> None:
        """Service heizwerk.set_manual."""
        await self.room.async_set_manual(
            temperature, duration, await self._user_name(), self._context
        )

    async def _user_name(self) -> str | None:
        if self._context is None or self._context.user_id is None:
            return None
        user = await self.hass.auth.async_get_user(self._context.user_id)
        return user.name if user else None
