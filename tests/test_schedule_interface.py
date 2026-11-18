"""0.4 interface: a scheduler writes climate.set_temperature, resume runs an action."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.heizwerk.const import DOMAIN

from .conftest import CLIMATE

PROFILE = "sensor.zeitwerk_heizung_bad_profile"
PLAN_VALUE = 16.0


async def _set(hass: HomeAssistant, temperature: float) -> None:
    """What a scheduler does: climate.set_temperature on the room."""
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": CLIMATE, "temperature": temperature},
        blocking=True,
    )


async def _manual(hass: HomeAssistant, temperature: float, **extra: Any) -> None:
    """What the Heizwerk card does."""
    await hass.services.async_call(
        "heizwerk",
        "set_manual",
        {"entity_id": CLIMATE, "temperature": temperature, **extra},
        blocking=True,
    )


@pytest.fixture
def zeitwerk(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Zeitwerk stand-in: profile sensor + resume that re-applies the plan."""
    hass.states.async_set(PROFILE, "Absenkung", {"plan_id": "heizung_bad"})
    calls: list[dict[str, Any]] = []

    async def resume(call: ServiceCall) -> None:
        calls.append(dict(call.data))
        hass.states.async_set(PROFILE, "Absenkung", {"plan_id": "heizung_bad"})
        await _set(hass, PLAN_VALUE)

    hass.services.async_register("zeitwerk", "resume", resume)
    return calls


async def test_scheduler_value_is_the_set_point(
    hass: HomeAssistant, setup_room
) -> None:
    await setup_room()
    await _set(hass, 16)
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["temperature"] == 16
    assert attrs["status"] != "manual"
    assert "scheduled_target" not in attrs
    assert "target_entity" not in attrs


async def test_without_scheduler_no_resume(hass: HomeAssistant, setup_room) -> None:
    """Heizwerk works on its own: plain thermostat, resume hidden."""
    await setup_room()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["resume_available"] is False
    await _manual(hass, 23, duration={"hours": 1})
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["temperature"] == 23
    assert attrs["manual_mode"] == "until_next"  # duration needs a resume action
    assert attrs["manual_until"] is None


async def test_manual_ends_with_next_scheduler_value(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    await _set(hass, PLAN_VALUE)
    await _manual(hass, 20)
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "manual"
    assert attrs["temperature"] == 20
    assert attrs["resume_available"] is True
    await _set(hass, 21)  # next block
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] != "manual"
    assert attrs["temperature"] == 21


async def test_resume_reloads_the_plan(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    """Steven's case: plan 16 °C, manual 17.5 °C, resume -> 16 °C (not 20)."""
    await setup_room(zeitwerk_plan="heizung_bad")
    await _set(hass, PLAN_VALUE)
    await _manual(hass, 17.5)
    await hass.services.async_call(
        "heizwerk", "resume", {"entity_id": CLIMATE}, blocking=True
    )
    await hass.async_block_till_done()
    assert zeitwerk == [{"plan": ["heizung_bad"]}]
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["temperature"] == PLAN_VALUE
    assert attrs["status"] != "manual"


async def test_duration_runs_resume(
    hass: HomeAssistant, setup_room, zeitwerk, freezer: FrozenDateTimeFactory
) -> None:
    await setup_room(zeitwerk_plan="heizung_bad")
    await _set(hass, PLAN_VALUE)
    await _manual(hass, 22, duration={"hours": 1})
    assert hass.states.get(CLIMATE).attributes["manual_mode"] == "duration"
    freezer.tick(timedelta(minutes=59))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not zeitwerk
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert zeitwerk == [{"plan": ["heizung_bad"]}]
    assert hass.states.get(CLIMATE).attributes["temperature"] == PLAN_VALUE


async def test_custom_resume_action(hass: HomeAssistant, setup_room) -> None:
    """E.g. Scheduler: any action can reload the plan."""
    calls: list[ServiceCall] = []
    hass.services.async_register("scheduler", "run_action", calls.append)
    await setup_room(
        resume_action=[
            {
                "action": "scheduler.run_action",
                "data": {"entity_id": "switch.schedule_bad"},
            }
        ]
    )
    assert hass.states.get(CLIMATE).attributes["resume_available"] is True
    await _manual(hass, 23)
    await hass.services.async_call(
        "heizwerk", "resume", {"entity_id": CLIMATE}, blocking=True
    )
    await hass.async_block_till_done()
    assert [c.data for c in calls] == [{"entity_id": "switch.schedule_bad"}]
    assert hass.states.get(CLIMATE).attributes["status"] != "manual"


async def test_manual_detected_by_zeitwerk_is_shown(
    hass: HomeAssistant, setup_room, zeitwerk
) -> None:
    """Changed in the more-info dialog: Zeitwerk reports it, Heizwerk shows it."""
    await setup_room(zeitwerk_plan="heizung_bad")
    await _set(hass, 21)
    hass.states.async_set(
        PROFILE,
        "Absenkung",
        {
            "plan_id": "heizung_bad",
            "manual_override": True,
            "manual_until": "2026-11-18T17:00:00+00:00",
        },
    )
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "manual"
    assert attrs["manual_until"] == "2026-11-18T17:00:00+00:00"
    assert attrs["manual_target"] == 21


async def test_restore_manual(hass: HomeAssistant, setup_room, zeitwerk) -> None:
    entry = await setup_room(zeitwerk_plan="heizung_bad")
    await _manual(hass, 24, duration={"hours": 2})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["status"] == "manual"
    assert attrs["temperature"] == 24
    assert attrs["manual_mode"] == "duration"


async def test_legacy_target_entity_ignored_with_repair(
    hass: HomeAssistant, setup_room
) -> None:
    """Regression 0.3.0: Zeitwerk target = own climate entity looped.

    Since 0.4 the field is gone; an old value is ignored and reported.
    """
    entry = await setup_room(target_entity=CLIMATE, zeitwerk_plan="heizung_bad")
    await _set(hass, 21.5)
    await _manual(hass, 23)
    assert hass.states.get(CLIMATE).attributes["temperature"] == 23
    subentry_id = next(iter(entry.subentries))
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"target_entity_{subentry_id}")
    assert issue is not None
    assert issue.translation_key == "target_entity_removed"


async def test_plan_detected_at_start(hass: HomeAssistant, setup_room) -> None:
    """Without a configured plan, the plan writing this room is found."""
    from homeassistant.core import SupportsResponse

    async def get_plan(call: ServiceCall) -> dict[str, Any]:
        return {
            "plans": [
                {
                    "id": "heizung_bad",
                    "profiles": [
                        {
                            "id": "eco",
                            "actions": [
                                {
                                    "action": "climate.set_temperature",
                                    "target": {"entity_id": CLIMATE},
                                    "data": {"temperature": 16},
                                }
                            ],
                        }
                    ],
                }
            ]
        }

    hass.services.async_register(
        "zeitwerk", "get_plan", get_plan, supports_response=SupportsResponse.ONLY
    )
    await setup_room()
    await hass.async_start()
    await hass.async_block_till_done()
    attrs = hass.states.get(CLIMATE).attributes
    assert attrs["zeitwerk_plan"] == "heizung_bad"
    assert attrs["resume_available"] is True
