"""0.5: two-point, per-room outdoor limit, TRV inputs, knob, mold indicator."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.heizwerk.const import DOMAIN

from .conftest import CLIMATE, OUTDOOR, ROOM_SENSOR, TRV, trv_state

NUMBER = "number.trv_bad_external_temperature_input"
SELECT = "select.trv_bad_temperature_sensor_select"
MOLD = "sensor.claude_schimmel_bad"


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture
def trv_device(hass: HomeAssistant) -> None:
    """Zigbee2MQTT-like TRVZB device with external input and source select."""
    other = MockConfigEntry(domain="mqtt")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("mqtt", "trvzb_bad")}
    )
    ent_reg = er.async_get(hass)
    for domain, object_id in (
        ("climate", "trv_bad"),
        ("number", "trv_bad_external_temperature_input"),
        ("select", "trv_bad_temperature_sensor_select"),
    ):
        ent_reg.async_get_or_create(
            domain,
            "mqtt",
            object_id,
            suggested_object_id=object_id,
            device_id=device.id,
            config_entry=other,
        )
    hass.states.async_set(NUMBER, "0")
    hass.states.async_set(SELECT, "remote_temperature")


async def test_two_point_regulation(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room(regulation="two_point", hysteresis_low=0.5, hysteresis_high=0.0)
    # 18.5 < 22 - 0.5 -> valve open at 24 °C
    await _tick(hass, freezer, 11)
    assert calls["temp"][-1].data == {"entity_id": TRV, "temperature": 24.0}
    assert hass.states.get(CLIMATE).attributes["regulation"] == "two_point"
    # within the band: keeps heating
    hass.states.async_set(ROOM_SENSOR, "21.8")
    await _tick(hass, freezer, 11)
    assert hass.states.get(TRV).state == "heat"
    # target reached (>= 22 + 0) -> off
    hass.states.async_set(ROOM_SENSOR, "22.0")
    await _tick(hass, freezer, 11)
    assert calls["mode"][-1].data == {"entity_id": TRV, "hvac_mode": "off"}
    assert hass.states.get(CLIMATE).attributes["status"] == "reached"
    # within the band again: stays off
    hass.states.async_set(ROOM_SENSOR, "21.6")
    await _tick(hass, freezer, 11)
    assert hass.states.get(TRV).state == "off"
    hass.states.async_set(ROOM_SENSOR, "21.4")
    await _tick(hass, freezer, 11)
    assert hass.states.get(TRV).state == "heat"


async def test_outdoor_limit_per_room(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room(outdoor_limit=18.0)
    hass.states.async_set(OUTDOOR, "17")  # above house value 16, below room 18
    await _tick(hass, freezer, 11 * 60)
    assert hass.states.get(CLIMATE).attributes["status"] != "summer"
    hass.states.async_set(OUTDOOR, "18.5")
    await _tick(hass, freezer, 11 * 60)
    assert hass.states.get(CLIMATE).attributes["status"] == "summer"


async def test_send_temperature_finds_input_on_trv_device(
    hass: HomeAssistant, trv_device, setup_room, calls
) -> None:
    pushes: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", pushes.append)
    await setup_room(send_temperature=True)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["external_inputs"] == [NUMBER]
    assert pushes[-1].data == {"entity_id": NUMBER, "value": 18.5}


async def test_send_temperature_off_sends_nothing(
    hass: HomeAssistant, trv_device, setup_room, calls
) -> None:
    pushes: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", pushes.append)
    await setup_room(send_temperature=False)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["external_inputs"] == []
    assert not pushes


async def test_measuring_source_issue(
    hass: HomeAssistant, trv_device, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    hass.services.async_register("number", "set_value", lambda call: None)
    await setup_room(send_temperature=True)
    issue_id = f"sensor_select_{SELECT}"
    # restarts (unavailable) do not count
    hass.states.async_set(SELECT, "unavailable")
    await _tick(hass, freezer, 10 * 60)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    hass.states.async_set(SELECT, "internal")
    await _tick(hass, freezer, 4 * 60)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    await _tick(hass, freezer, 61)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "sensor_select_not_remote"
    assert issue.translation_placeholders["state"] == "internal"
    hass.states.async_set(SELECT, "remote_temperature")
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_knob_turn_is_adopted(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room()
    await _tick(hass, freezer, 11)  # Heizwerk sends 21.5 (22 - 0.5)
    assert hass.states.get(TRV).attributes["temperature"] == 21.5
    await _tick(hass, freezer, 30)
    trv_state(hass, "heat", 20.5)  # someone turns the knob
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["temperature"] == 21.0  # 20.5 + 0.5 correction
    assert attrs["status"] == "manual"
    assert attrs["manual_source"] == "thermostat"
    await _tick(hass, freezer, 11)
    assert len(calls["temp"]) == 1  # TRV not reset


async def test_echo_is_not_a_knob_turn(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room()
    await _tick(hass, freezer, 11)
    assert hass.states.get(CLIMATE).attributes["status"] != "manual"


async def test_knob_turn_reset_mode(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room(trv_manual="reset")
    await _tick(hass, freezer, 11)
    await _tick(hass, freezer, 30)
    trv_state(hass, "heat", 25)
    await _tick(hass, freezer, 11)
    assert hass.states.get(CLIMATE).attributes["status"] != "manual"
    assert calls["temp"][-1].data == {"entity_id": TRV, "temperature": 21.5}


async def test_knob_ignored_in_observe_only(
    hass: HomeAssistant, setup_room, calls
) -> None:
    await setup_room(observe_only=True)
    trv_state(hass, "heat", 25)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["status"] != "manual"


async def test_mold_indicator(hass: HomeAssistant, setup_room, calls) -> None:
    hass.states.async_set(
        MOLD, "74", {"unit_of_measurement": "%", "estimated_critical_temp": 16.3}
    )
    await setup_room(mold_sensor=MOLD, wall_temperature_sensor=None)
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["wall_source"] == "indicator"
    assert attrs["wall_humidity"] == 74
    assert attrs["wall_critical_temperature"] == 16.3
    assert attrs["wall_temperature"] is None
    assert attrs["mold_level"] == "warning"
    assert float(hass.states.get("sensor.heizwerk_bad_wall_humidity").state) == 74


async def test_wall_sensor_still_works(hass: HomeAssistant, setup_room, calls) -> None:
    await setup_room()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["wall_source"] == "sensor"
    assert attrs["wall_critical_temperature"] is None


# --- Review findings (0.5) ---------------------------------------------------


async def test_knob_back_to_previous_value_is_adopted(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """Review #3: a value equal to an old command is not an echo after 30 s."""
    await setup_room()
    await _tick(hass, freezer, 11)  # sent 21.5
    await _tick(hass, freezer, 40)
    trv_state(hass, "heat", 19.5)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["temperature"] == 20.0
    await _tick(hass, freezer, 40)
    trv_state(hass, "heat", 21.5)  # back to the value Heizwerk once sent
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["temperature"] == 22.0


async def test_knob_during_lock_is_ignored(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """Review #2: frost/off during a lock is not a new room target."""
    await setup_room(lock_mode="frost")
    hass.states.async_set("input_boolean.lock_bad", "on")
    await _tick(hass, freezer, 11)
    await _tick(hass, freezer, 40)
    trv_state(hass, "heat", 7.5)
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["temperature"] == 22.0
    assert attrs["status"] == "locked"


async def test_knob_two_point_is_a_delta(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """Review #1: the TRV shows 24 °C in two-point; turning down 0.5 = -0.5 K."""
    await setup_room(regulation="two_point")
    await _tick(hass, freezer, 11)
    assert hass.states.get(TRV).attributes["temperature"] == 24.0
    await _tick(hass, freezer, 40)
    trv_state(hass, "heat", 23.5)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["temperature"] == 21.5


async def test_automation_writing_trv_is_not_a_knob(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """Review #8: changes caused by automations (context parent) are ignored."""
    from homeassistant.core import Context

    await setup_room()
    await _tick(hass, freezer, 11)
    await _tick(hass, freezer, 40)
    state = hass.states.get(TRV)
    hass.states.async_set(
        TRV,
        "heat",
        {**state.attributes, "temperature": 19},
        context=Context(parent_id="automation-run"),
    )
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["status"] != "manual"


async def test_two_point_resumes_heating_after_restart(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """Review #9: inside the band after a restart, keep heating if the TRV heats."""
    trv_state(hass, "heat", 24.0)
    hass.states.async_set(ROOM_SENSOR, "21.8")  # inside 21.5 … 22.0
    await setup_room(regulation="two_point")
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["planned_commands"][0]["temperature"] == 24.0
    assert attrs["status"] == "heating"


async def test_no_inputs_without_room_sensor(
    hass: HomeAssistant, trv_device, setup_room, calls
) -> None:
    """Review #7: send_temperature needs a room sensor."""
    await setup_room(send_temperature=True, temperature_sensor=None)
    assert hass.states.get(CLIMATE).attributes["external_inputs"] == []


async def test_legacy_inputs_stop_when_sending_is_off(
    hass: HomeAssistant, setup_room, calls
) -> None:
    """Review #4: switching sending off stops legacy inputs too."""
    pushes: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", pushes.append)
    await setup_room(
        send_temperature=False, external_temperature_entities=["number.legacy"]
    )
    await hass.async_block_till_done()
    assert not pushes
    assert hass.states.get(CLIMATE).attributes["external_inputs"] == []


async def test_legacy_room_without_key_keeps_inputs(
    hass: HomeAssistant, setup_room, calls
) -> None:
    """0.4 room with explicit inputs and no send_temperature key keeps sending."""
    pushes: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", pushes.append)
    await setup_room(external_temperature_entities=["number.legacy"])
    await hass.async_block_till_done()
    assert pushes and pushes[-1].data["entity_id"] == "number.legacy"


async def test_select_issue_kept_on_reload_removed_with_entry(
    hass: HomeAssistant, trv_device, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """Review #6 / re-review nit: reload keeps a real issue, removal drops it."""
    hass.services.async_register("number", "set_value", lambda call: None)
    entry = await setup_room(send_temperature=True)
    hass.states.async_set(SELECT, "internal")
    await _tick(hass, freezer, 6 * 60)
    issue_id = f"sensor_select_{SELECT}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    hass.states.async_set(SELECT, "remote_temperature")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    hass.states.async_set(SELECT, "internal")
    await _tick(hass, freezer, 6 * 60)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_knob_several_clicks_quickly(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """Re-review: 20.5, 21.0, 21.5 reported 1 s apart -> 21.5 adopted, not reset."""
    await setup_room()
    await _tick(hass, freezer, 11)  # Heizwerk sent 21.5
    for value in (22.0, 22.5, 23.0):
        trv_state(hass, "heat", value)
        await _tick(hass, freezer, 1)
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["temperature"] == 23.5  # 23.0 + 0.5 correction
    assert attrs["manual_source"] == "thermostat"
    await _tick(hass, freezer, 11)
    assert hass.states.get(TRV).attributes["temperature"] == 23.0  # not reset


async def test_mode_switch_report_is_not_a_knob(
    hass: HomeAssistant, setup_room, calls, freezer: FrozenDateTimeFactory
) -> None:
    """A TRV switched on by Heizwerk may report its old heat set-point first."""
    await setup_room()
    await _tick(hass, freezer, 11)  # off -> heat 21.5 sent
    trv_state(hass, "off", 21.5)
    await hass.async_block_till_done()
    calls["deaf"] = True
    await _tick(hass, freezer, 11)  # Heizwerk sends heat again
    trv_state(hass, "heat", 19.0)  # device restores its own old value first
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["status"] != "manual"


async def test_two_point_init_after_hass_started(
    hass: HomeAssistant, setup_room, calls
) -> None:
    """Re-review risk 1: TRVs restored only after start (MQTT)."""
    from homeassistant.core import CoreState

    hass.set_state(CoreState.starting)
    hass.states.async_set(TRV, "unavailable")
    hass.states.async_set(ROOM_SENSOR, "21.8")
    await setup_room(regulation="two_point")
    trv_state(hass, "heat", 24.0)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "heating"
    assert attrs["planned_commands"][0]["temperature"] == 24.0
