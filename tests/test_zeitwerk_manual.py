"""Manual override written to the Zeitwerk target (visible in Zeitwerk)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from .conftest import CLIMATE, TARGET

PROFILE = "sensor.zeitwerk_heizung_bad_profile"
NEXT = "sensor.zeitwerk_heizung_bad_next_change"


@pytest.fixture
async def zeitwerk(hass: HomeAssistant, house: None) -> dict[str, Any]:
    """Real input_number target + Zeitwerk stand-in (sensors and resume)."""
    hass.states.async_remove(TARGET)
    assert await async_setup_component(
        hass,
        "input_number",
        {
            "input_number": {
                "temperaturspeicher_bad": {
                    "min": 5,
                    "max": 30,
                    "step": 0.5,
                    "initial": 22,
                }
            }
        },
    )
    hass.states.async_set(
        PROFILE,
        "Komfort",
        {"plan_id": "heizung_bad", "profile_id": "comfort", "source": "schedule"},
    )
    hass.states.async_set(
        NEXT, "2099-01-01T00:00:00+00:00", {"next_profile_name": "Absenkung"}
    )
    resumed: list[dict[str, Any]] = []

    async def resume(call: ServiceCall) -> None:
        # Like Zeitwerk: end the manual change and apply the plan value again.
        resumed.append(dict(call.data))
        hass.states.async_set(PROFILE, "Komfort", {"plan_id": "heizung_bad"})
        await hass.services.async_call(
            "input_number",
            "set_value",
            {"entity_id": TARGET, "value": 22},
            blocking=True,
        )

    hass.services.async_register("zeitwerk", "resume", resume)
    return {"resumed": resumed}


def _zeitwerk_registers_manual(hass: HomeAssistant, until: str | None = None) -> None:
    attrs: dict[str, Any] = {
        "plan_id": "heizung_bad",
        "manual_override": True,
        "manual_since": "2026-11-18T08:00:00+00:00",
    }
    if until:
        attrs["manual_until"] = until
    hass.states.async_set(PROFILE, "Komfort", attrs)


async def _manual(hass: HomeAssistant, temperature: float, **extra: Any) -> None:
    await hass.services.async_call(
        "heizwerk",
        "set_manual",
        {"entity_id": CLIMATE, "temperature": temperature, **extra},
        blocking=True,
    )


async def test_override_is_written_to_zeitwerk_target(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    await _manual(hass, 24)
    assert hass.states.get(TARGET).state == "24.0"
    _zeitwerk_registers_manual(hass, "2026-11-18T17:00:00+00:00")
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "manual"
    assert attrs["temperature"] == 24
    assert attrs["scheduled_target"] == 22  # plan value, not the override
    assert attrs["manual_source"] == "zeitwerk"
    assert attrs["manual_until"] == "2026-11-18T17:00:00+00:00"


async def test_next_block_ends_override(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    await _manual(hass, 24)
    # Zeitwerk applies the next profile
    hass.states.async_set(PROFILE, "Absenkung", {"plan_id": "heizung_bad"})
    await hass.services.async_call(
        "input_number", "set_value", {"entity_id": TARGET, "value": 18}, blocking=True
    )
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] != "manual"
    assert attrs["temperature"] == 18
    assert attrs["manual_source"] is None


async def test_duration_ends_with_zeitwerk_resume(
    hass: HomeAssistant, setup_room, zeitwerk, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    await _manual(hass, 24, duration={"hours": 1})
    _zeitwerk_registers_manual(hass)
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert zeitwerk["resumed"] == [{"plan": ["heizung_bad"]}]
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["temperature"] == 22
    assert attrs["status"] != "manual"


async def test_resume_calls_zeitwerk(hass: HomeAssistant, setup_room, zeitwerk) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    await _manual(hass, 24)
    await hass.services.async_call(
        "heizwerk", "resume", {"entity_id": CLIMATE}, blocking=True
    )
    assert zeitwerk["resumed"]
    assert hass.states.get(CLIMATE).attributes["temperature"] == 22


async def test_back_to_plan_value_is_a_resume(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    await _manual(hass, 24)
    await _manual(hass, 22)
    assert zeitwerk["resumed"]
    assert hass.states.get(CLIMATE).attributes["status"] != "manual"


async def test_override_started_in_zeitwerk_is_shown(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    # Someone changes the target in the Zeitwerk card
    await hass.services.async_call(
        "input_number", "set_value", {"entity_id": TARGET, "value": 23}, blocking=True
    )
    _zeitwerk_registers_manual(hass)
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "manual"
    assert attrs["temperature"] == 23
    assert attrs["manual_source"] == "zeitwerk"
    assert attrs["manual_by"] is None


async def test_observe_only_never_writes_the_target(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad", observe_only=True)
    await _manual(hass, 24)
    assert hass.states.get(TARGET).state == "22.0"
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "manual"
    assert attrs["temperature"] == 24
    assert attrs["manual_source"] == "heizwerk"


async def test_restore_keeps_zeitwerk_override(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    entry = await setup_room(zeitwerk_plan="heizung_bad")
    await _manual(hass, 24, duration={"hours": 2})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "manual"
    assert attrs["temperature"] == 24
    assert attrs["scheduled_target"] == 22
