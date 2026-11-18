"""Shared fixtures for Heizwerk tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.heizwerk.const import DOMAIN, SUBENTRY_ROOM

TRV = "climate.trv_bad"
ROOM_SENSOR = "sensor.bad_temperature"
HUMIDITY = "sensor.bad_humidity"
WALL = "sensor.bad_wall"
WINDOW = "binary_sensor.window_bad"
TARGET = "input_number.temperaturspeicher_bad"
OUTDOOR = "sensor.outdoor"
OUTDOOR_H = "sensor.outdoor_humidity"
SEASON = "input_boolean.heizperiode"
LOCK = "input_boolean.lock_bad"
CLIMATE = "climate.heizwerk_bad"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components in every test."""


def trv_state(
    hass: HomeAssistant,
    mode: str = "off",
    setpoint: float = 7,
    *,
    current: float = 20.0,
    action: str = "idle",
    entity_id: str = TRV,
) -> None:
    """Set a fake thermostat state (TRVZB-like)."""
    hass.states.async_set(
        entity_id,
        mode,
        {
            "hvac_modes": ["off", "auto", "heat"],
            "temperature": setpoint,
            "current_temperature": current,
            "hvac_action": action,
            "min_temp": 4,
            "max_temp": 35,
            "target_temp_step": 0.5,
        },
    )


@pytest.fixture
def house(hass: HomeAssistant) -> None:
    """Base states of the test house."""
    trv_state(hass)
    hass.states.async_set(ROOM_SENSOR, "18.5")
    hass.states.async_set(HUMIDITY, "60")
    hass.states.async_set(WALL, "15.6")
    hass.states.async_set(WINDOW, "off")
    hass.states.async_set(TARGET, "22.0")
    hass.states.async_set(OUTDOOR, "8.9")
    hass.states.async_set(OUTDOOR_H, "80")
    hass.states.async_set(SEASON, "on")
    hass.states.async_set(LOCK, "off")


def room_data(**overrides: Any) -> dict[str, Any]:
    """Room subentry data for the bathroom."""
    data: dict[str, Any] = {
        "name": "Bad",
        "trvs": [TRV],
        "temperature_sensor": ROOM_SENSOR,
        "humidity_sensor": HUMIDITY,
        "wall_temperature_sensor": WALL,
        "windows": [WINDOW],
        "window_open_delay": 30,
        "window_close_delay": 10,
        "target_entity": TARGET,
        "lock_entities": [LOCK],
        "lock_mode": "off",
        "frost_temperature": 7.0,
        "correction": -0.5,
        "regulation": "setpoint",
        "default_target": 20.0,
        "min_temp": 5.0,
        "max_temp": 30.0,
        "humidity_threshold": 60,
        "observe_only": False,
    }
    data.update(overrides)
    return data


@pytest.fixture
def setup_room(hass: HomeAssistant, house: None) -> Callable[..., Any]:
    """Create and set up a Heizwerk entry with one room."""

    async def _setup(**overrides: Any) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Heizwerk",
            data={},
            options={
                "outdoor_temperature": OUTDOOR,
                "outdoor_humidity": OUTDOOR_H,
                "season_entity": SEASON,
                "summer_lock_temperature": 16.0,
                "summer_lock_minutes": 10,
            },
            subentries_data=[
                ConfigSubentryData(
                    data=room_data(**overrides),
                    subentry_type=SUBENTRY_ROOM,
                    title="Bad",
                    unique_id=None,
                )
            ],
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup
