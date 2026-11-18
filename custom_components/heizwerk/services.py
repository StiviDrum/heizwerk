"""Services heizwerk.set_manual / resume / sync."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN
from .room import RoomController

ATTR_DURATION = "duration"

_ENTITY_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})
_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
        vol.Optional(ATTR_DURATION): cv.positive_time_period,
    }
)


def _rooms(hass: HomeAssistant, call: ServiceCall) -> list[RoomController]:
    rooms: list[RoomController] = []
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    for entity_id in call.data[ATTR_ENTITY_ID]:
        room = next(
            (
                r
                for e in entries
                if (r := e.runtime_data.room_by_entity(entity_id)) is not None
            ),
            None,
        )
        if room is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_room",
                translation_placeholders={"entity_id": entity_id},
            )
        rooms.append(room)
    return rooms


async def _user_name(hass: HomeAssistant, call: ServiceCall) -> str | None:
    if call.context.user_id is None:
        return None
    user = await hass.auth.async_get_user(call.context.user_id)
    return user.name if user else None


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services (once, in async_setup)."""

    async def set_manual(call: ServiceCall) -> None:
        duration: timedelta | None = call.data.get(ATTR_DURATION)
        if duration is not None and duration <= timedelta(0):
            duration = None
        user = await _user_name(hass, call)
        for room in _rooms(hass, call):
            await room.async_set_manual(
                call.data[ATTR_TEMPERATURE], duration, user, call.context
            )

    async def resume(call: ServiceCall) -> None:
        for room in _rooms(hass, call):
            await room.async_resume()

    async def sync(call: ServiceCall) -> None:
        for room in _rooms(hass, call):
            await room.async_sync()

    hass.services.async_register(DOMAIN, "set_manual", set_manual, _MANUAL_SCHEMA)
    hass.services.async_register(DOMAIN, "resume", resume, _ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "sync", sync, _ENTITY_SCHEMA)
