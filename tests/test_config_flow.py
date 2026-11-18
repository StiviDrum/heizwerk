"""Config flow, options flow and room subentries."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.heizwerk.const import DOMAIN, SUBENTRY_ROOM

from .conftest import TRV, room_data


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"summer_lock_temperature": 16, "summer_lock_minutes": 10},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["summer_lock_temperature"] == 16


async def test_single_instance(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT


async def test_options_flow(hass: HomeAssistant, house) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={"summer_lock_temperature": 16, "summer_lock_minutes": 10},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"summer_lock_temperature": 15, "summer_lock_minutes": 20}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["summer_lock_minutes"] == 20


async def test_room_subentry_create_and_reconfigure(hass: HomeAssistant, house) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={"summer_lock_temperature": 16, "summer_lock_minutes": 10},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    data = room_data(observe_only=True)
    del data["target_entity"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("climate.heizwerk_bad") is not None

    # Duplicate name rejected
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], data
    )
    assert result["errors"] == {"name": "name_exists"}

    subentry_id = next(iter(entry.subentries))
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**data, "correction": -1.0}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[subentry_id].data["correction"] == -1.0


async def test_room_validation(hass: HomeAssistant, house) -> None:
    entry = MockConfigEntry(domain=DOMAIN, options={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**room_data(), "min_temp": 25, "max_temp": 20, "trvs": [TRV]},
    )
    assert result["errors"] == {"max_temp": "min_max"}


async def test_zeitwerk_plans_offered(hass: HomeAssistant, house) -> None:
    from custom_components.heizwerk.config_flow import zeitwerk_plans

    hass.states.async_set(
        "sensor.zeitwerk_heizung_bad_profile", "Komfort", {"plan_id": "heizung_bad"}
    )
    hass.states.async_set("sensor.other", "1", {"plan_id": "nope"})
    assert zeitwerk_plans(hass) == ["heizung_bad"]


def _entity_selectors(schema) -> list[dict]:
    from homeassistant.helpers.selector import EntitySelector

    return [
        value.serialize()["selector"]["entity"]
        for value in schema.schema.values()
        if isinstance(value, EntitySelector)
    ]


async def test_entity_selectors_do_not_filter_everything(hass: HomeAssistant) -> None:
    """Regression: device_class=None serialised to [] hid every entity."""
    from custom_components.heizwerk.config_flow import _hub_schema, _room_schema

    selectors = _entity_selectors(_hub_schema()) + _entity_selectors(_room_schema(hass))
    assert len(selectors) == 11
    for sel in selectors:
        assert sel.get("device_class") != [], sel
