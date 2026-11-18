"""Room controller in a running Home Assistant (SPEC sections 4 and 5)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant.common import async_fire_time_changed, async_mock_service

from .conftest import (
    CLIMATE,
    LOCK,
    OUTDOOR,
    ROOM_SENSOR,
    SEASON,
    TRV,
    WINDOW,
    trv_state,
)


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_entities_and_attributes(hass: HomeAssistant, setup_room, calls) -> None:
    await setup_room()
    state = hass.states.get(CLIMATE)
    assert state is not None
    assert state.state == "heat"
    assert state.attributes["temperature"] == 22.0
    assert state.attributes["current_temperature"] == 18.5
    assert state.attributes["current_humidity"] == 60
    assert state.attributes["status"] == "heating"
    assert state.attributes["room_name"] == "Bad"
    assert state.attributes["temperature_source"] == "sensor"
    assert state.attributes["ventilation_minutes"] == 10
    assert state.attributes["mold_level"] == "warning"
    assert state.attributes["planned_commands"] == [
        {"entity_id": TRV, "hvac_mode": "heat", "temperature": 21.5}
    ]
    assert hass.states.get("sensor.heizwerk_bad_dew_point").state == "10.6"
    assert float(hass.states.get("sensor.heizwerk_bad_wall_humidity").state) == 72
    assert hass.states.get("binary_sensor.heizwerk_bad_ventilation").state == "on"
    assert hass.states.get("switch.heizwerk_bad_observe_only").state == "off"
    ent = er.async_get(hass).async_get(CLIMATE)
    assert ent is not None and ent.config_subentry_id is not None


async def test_commands_debounced_and_sent_once(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room()
    assert not calls["mode"] and not calls["temp"]
    await _tick(hass, freezer, 11)
    assert [c.data for c in calls["mode"]] == [{"entity_id": TRV, "hvac_mode": "heat"}]
    assert [c.data for c in calls["temp"]] == [{"entity_id": TRV, "temperature": 21.5}]
    # Thermostat follows -> nothing more to send
    trv_state(hass, "heat", 21.5)
    await _tick(hass, freezer, 11)
    assert len(calls["temp"]) == 1


async def test_observe_only_sends_nothing(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room(observe_only=True)
    await _tick(hass, freezer, 30)
    assert not calls["mode"] and not calls["temp"]
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["observe_only"] is True
    assert attrs["planned_commands"][0]["temperature"] == 21.5
    assert attrs["last_sync"] is not None


async def test_window_lock_with_delays(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room()
    trv_state(hass, "heat", 21.5)
    await hass.async_block_till_done()
    hass.states.async_set(WINDOW, "on")
    await _tick(hass, freezer, 20)
    assert hass.states.get(CLIMATE).attributes["status"] == "heating"
    await _tick(hass, freezer, 11)
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "window"
    assert attrs["locks"][0]["type"] == "window"
    await _tick(hass, freezer, 11)
    assert calls["mode"][-1].data == {"entity_id": TRV, "hvac_mode": "off"}
    # Close: released only after the close delay
    hass.states.async_set(WINDOW, "off")
    await _tick(hass, freezer, 5)
    assert hass.states.get(CLIMATE).attributes["status"] == "window"
    await _tick(hass, freezer, 6)
    assert hass.states.get(CLIMATE).attributes["status"] == "heating"


async def test_short_window_opening_does_not_lock(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room()
    hass.states.async_set(WINDOW, "on")
    await _tick(hass, freezer, 10)
    hass.states.async_set(WINDOW, "off")
    await _tick(hass, freezer, 40)
    assert hass.states.get(CLIMATE).attributes["status"] == "heating"


async def test_ventilation_done_event(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    events = []
    hass.bus.async_listen("heizwerk_event", events.append)
    await setup_room()
    hass.states.async_set(WINDOW, "on")
    await _tick(hass, freezer, 9 * 60)
    assert not events
    await _tick(hass, freezer, 61)
    assert [e.data["type"] for e in events] == ["ventilation_done"]
    assert hass.states.get(CLIMATE).attributes["ventilation_done"] is True
    await _tick(hass, freezer, 120)
    assert len(events) == 1


async def test_summer_season_and_entity_locks(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room()
    hass.states.async_set(OUTDOOR, "17")
    await _tick(hass, freezer, 5 * 60)
    assert hass.states.get(CLIMATE).attributes["status"] == "heating"
    await _tick(hass, freezer, 5 * 60 + 1)
    assert hass.states.get(CLIMATE).attributes["status"] == "summer"
    hass.states.async_set(OUTDOOR, "10")
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["status"] == "heating"
    hass.states.async_set(SEASON, "off")
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "season"
    assert attrs["season_active"] is False
    hass.states.async_set(SEASON, "on")
    hass.states.async_set(LOCK, "on")
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "locked"
    assert attrs["locks"][0]["entity_ids"] == [LOCK]


async def test_frost_lock_mode(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room(lock_mode="frost")
    hass.states.async_set(LOCK, "on")
    await _tick(hass, freezer, 11)
    assert calls["temp"][-1].data == {"entity_id": TRV, "temperature": 7.0}


async def test_room_off(hass: HomeAssistant, setup_room, calls, freezer) -> None:
    await setup_room()
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": CLIMATE, "hvac_mode": "off"},
        blocking=True,
    )
    state = hass.states.get(CLIMATE)
    assert state.state == "off"
    assert state.attributes["status"] == "off"
    assert state.attributes["hvac_action"] == "off"


async def test_trv_fallback_temperature_and_unavailable_event(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    events = []
    hass.bus.async_listen("heizwerk_event", events.append)
    await setup_room(temperature_sensor=None)
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["current_temperature"] == 20.0
    assert attrs["temperature_source"] == "trv"
    hass.states.async_set(TRV, "unavailable")
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "unavailable"
    assert attrs["trv_unavailable_since"] is not None
    await _tick(hass, freezer, 5 * 60 + 1)
    assert [e.data["type"] for e in events] == ["trv_unavailable"]


async def test_external_temperature_push(
    hass: HomeAssistant, setup_room, calls
) -> None:
    pushes = async_mock_service(hass, "number", "set_value")
    await setup_room(external_temperature_entities=["number.trv_bad_external"])
    await hass.async_block_till_done()
    assert pushes[-1].data == {"entity_id": "number.trv_bad_external", "value": 18.5}
    hass.states.async_set(ROOM_SENSOR, "18.55")
    await hass.async_block_till_done()
    assert len(pushes) == 1  # below 0.1 K
    hass.states.async_set(ROOM_SENSOR, "18.7")
    await hass.async_block_till_done()
    assert pushes[-1].data["value"] == 18.7


async def test_observe_switch_updates_subentry(
    hass: HomeAssistant, setup_room, calls
) -> None:
    entry = await setup_room()
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.heizwerk_bad_observe_only"},
        blocking=True,
    )
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    assert sub.data["observe_only"] is True
    assert hass.states.get(CLIMATE).attributes["observe_only"] is True


async def test_unload_removes_listeners(hass: HomeAssistant, setup_room, calls) -> None:
    entry = await setup_room()
    room = next(iter(entry.runtime_data.rooms.values()))
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert room._unsubs == []
    assert room._wakeup is None
    hass.states.async_set(ROOM_SENSOR, "25")
    await hass.async_block_till_done()  # no errors, nothing tracked


async def test_unknown_room_service_error(
    hass: HomeAssistant, setup_room, calls
) -> None:
    from homeassistant.exceptions import ServiceValidationError

    await setup_room()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "heizwerk", "resume", {"entity_id": "climate.other"}, blocking=True
        )


async def test_lost_command_is_resent(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """A thermostat that ignores a command gets it again within 5 minutes."""
    calls["deaf"] = True
    await setup_room()
    await _tick(hass, freezer, 11)
    assert len(calls["temp"]) == 1
    calls["deaf"] = False
    await _tick(hass, freezer, 5 * 60)
    await _tick(hass, freezer, 11)
    assert len(calls["temp"]) == 2
    assert hass.states.get(TRV).attributes["temperature"] == 21.5
    # In sync now: no further commands
    await _tick(hass, freezer, 10 * 60)
    assert len(calls["temp"]) == 2


async def test_own_climate_as_thermostat_is_ignored(
    hass: HomeAssistant, setup_room, calls
) -> None:
    await setup_room(trvs=[TRV, CLIMATE])
    attrs = hass.states.get(CLIMATE).attributes
    assert [t["entity_id"] for t in attrs["trvs"]] == [TRV]
    assert CLIMATE in attrs["ignored_entities"]
