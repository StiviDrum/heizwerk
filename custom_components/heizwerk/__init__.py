"""Heizwerk – room heating control for Home Assistant.

Zeitwerk plans the set-points, Heizwerk controls the radiator thermostats.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CARD_FILENAME, CARD_URL_BASE, DATA_CARD_REGISTERED, DOMAIN
from .hub import HeizwerkHub
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]
CARD_PATH = Path(__file__).parent / "frontend" / CARD_FILENAME
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HeizwerkConfigEntry = ConfigEntry[HeizwerkHub]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services and the card once."""
    async_setup_services(hass)
    await _async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeizwerkConfigEntry) -> bool:
    """Set up Heizwerk from a config entry (rooms are subentries)."""
    hub = HeizwerkHub(hass, entry)
    entry.runtime_data = hub
    await hub.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hub.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeizwerkConfigEntry) -> bool:
    """Unload a config entry and clean up all listeners."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.async_stop()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: HeizwerkConfigEntry) -> None:
    """Reload after options or rooms changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the card JS and add it to the frontend (no manual resource needed)."""
    if hass.data.get(DATA_CARD_REGISTERED):
        return
    card_path = CARD_PATH
    if not await hass.async_add_executor_job(card_path.is_file):
        _LOGGER.warning(
            "Card bundle %s not found – build the frontend (npm run build)", card_path
        )
        return
    content = await hass.async_add_executor_job(card_path.read_bytes)
    digest = hashlib.sha256(content).hexdigest()[:8]
    url = f"{CARD_URL_BASE}/{CARD_FILENAME}"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url, str(card_path), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{url}?v={digest}")
    hass.data[DATA_CARD_REGISTERED] = True
