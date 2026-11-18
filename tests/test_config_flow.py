"""Config flow, options flow and room subentries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.data_entry_flow import (
    FlowResultType,
    InvalidData,
    add_visible_conditions_to_serialized_schema,
    section,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import EntitySelector
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.heizwerk.config_flow import (
    HUB_SECTIONS,
    ROOM_SECTIONS,
    _flatten,
    _hub_schema,
    _nest,
    _room_schema,
    zeitwerk_plans,
)
from custom_components.heizwerk.const import DOMAIN, SUBENTRY_ROOM

from .conftest import room_data

CLIMATE = "climate.heizwerk_bad"
RESUME = [
    {
        "action": "scheduler.run_action",
        "target": {"entity_id": "switch.schedule_bad"},
    }
]

TRANSLATIONS = Path(__file__).parents[1] / "custom_components/heizwerk/translations"


def flat_room(**overrides: Any) -> dict[str, Any]:
    """Room data of 0.4 (no Zeitwerk target any more)."""
    data = room_data(**overrides)
    data.pop("target_entity", None)
    return data


def nested_room(**overrides: Any) -> dict[str, Any]:
    """Room data as the sectioned form submits it."""
    return _nest(flat_room(**overrides), ROOM_SECTIONS)


def _without(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in keys}


async def _hub_entry(hass: HomeAssistant, **kwargs: Any) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={"summer_lock_temperature": 16, "summer_lock_minutes": 10},
        **kwargs,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _add_room(hass: HomeAssistant, entry: MockConfigEntry, data: dict) -> Any:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.subentries.async_configure(result["flow_id"], data)


def _suggested(schema: probatio.Schema) -> dict[str, Any]:
    """Suggested values of a shown form, nested like the form."""
    out: dict[str, Any] = {}
    for key, value in schema.schema.items():
        if isinstance(value, section):
            out[key.schema] = _suggested(value.schema)
        elif (key.description or {}).get("suggested_value") is not None:
            out[key.schema] = key.description["suggested_value"]
    return out


# --- flatten / nest ------------------------------------------------------------


def test_flatten_nest_round_trip() -> None:
    flat = flat_room(zeitwerk_plan="heizung_bad", resume_action=RESUME)
    nested = _nest(flat, ROOM_SECTIONS)
    assert nested["regulation"] == {
        "correction": -0.5,
        "regulation": "setpoint",
    }
    assert nested["schedule"] == {
        "zeitwerk_plan": "heizung_bad",
        "resume_action": RESUME,
    }
    assert nested["limits"]["default_target"] == 22.0
    assert "correction" not in nested
    assert nested["name"] == "Bad"
    assert _flatten(nested, ROOM_SECTIONS) == flat
    hub = {"outdoor_temperature": "sensor.o", "summer_lock_minutes": 5}
    assert _flatten(_nest(hub, HUB_SECTIONS), HUB_SECTIONS) == hub


def test_layout_matches_schema(hass: HomeAssistant) -> None:
    """The section layout constants describe the schemas exactly."""
    for schema, sections in (
        (_room_schema(hass), ROOM_SECTIONS),
        (_hub_schema(), HUB_SECTIONS),
    ):
        for key, value in schema.schema.items():
            if isinstance(value, section):
                inner = [k.schema for k in value.schema.schema]
                assert tuple(inner) == sections[key.schema]
                assert value.options["collapsed"] is True


# --- hub ------------------------------------------------------------------


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "outdoor_temperature": "sensor.outdoor",
            "summer_lock": {"summer_lock_temperature": 16, "summer_lock_minutes": 10},
            "climate": {"outdoor_humidity": "sensor.outdoor_humidity"},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "outdoor_temperature": "sensor.outdoor",
        "summer_lock_temperature": 16,
        "summer_lock_minutes": 10,
        "outdoor_humidity": "sensor.outdoor_humidity",
    }


async def test_single_instance(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT


async def test_options_flow(hass: HomeAssistant, house) -> None:
    entry = await _hub_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Stored flat options are shown inside their section.
    assert _suggested(result["data_schema"])["summer_lock"] == {
        "summer_lock_temperature": 16,
        "summer_lock_minutes": 10,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "summer_lock": {"summer_lock_temperature": 15, "summer_lock_minutes": 20},
            "climate": {},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"summer_lock_temperature": 15, "summer_lock_minutes": 20}


# --- room -----------------------------------------------------------------


async def test_room_subentry_create_and_reconfigure(hass: HomeAssistant, house) -> None:
    entry = await _hub_entry(hass)
    data = nested_room(observe_only=True)
    result = await _add_room(hass, entry, data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("climate.heizwerk_bad") is not None
    subentry_id = next(iter(entry.subentries))
    stored = dict(entry.subentries[subentry_id].data)
    # Stored flat, same keys as before sections existed.
    assert stored == flat_room(observe_only=True)

    # Duplicate name rejected
    result = await _add_room(hass, entry, data)
    assert result["errors"] == {"name": "name_exists"}

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["step_id"] == "reconfigure"
    data["regulation"] = {**data["regulation"], "correction": -1.0}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[subentry_id].data["correction"] == -1.0
    assert entry.subentries[subentry_id].data["regulation"] == "setpoint"


async def test_reconfigure_shows_stored_values_in_sections(
    hass: HomeAssistant, house
) -> None:
    """A 0.2-style flat subentry sets up and is shown inside the sections.

    Its legacy Zeitwerk target is not offered any more and dropped on save.
    """
    legacy = room_data(
        zeitwerk_plan="heizung_bad",
        lock_mode="frost",
        target_entity="input_number.temperaturspeicher_bad",
    )
    entry = await _hub_entry(
        hass,
        subentries_data=[
            ConfigSubentryData(
                data=legacy, subentry_type=SUBENTRY_ROOM, title="Bad", unique_id=None
            )
        ],
    )
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert hass.states.get(CLIMATE) is not None
    subentry_id = next(iter(entry.subentries))

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    suggested = _suggested(result["data_schema"])
    assert suggested["name"] == "Bad"
    assert "target_entity" not in suggested
    assert suggested["schedule"] == {"zeitwerk_plan": "heizung_bad"}
    assert suggested["regulation"]["correction"] == -0.5
    assert suggested["windows_locks"]["lock_mode"] == "frost"
    assert suggested["windows_locks"]["frost_temperature"] == 7.0
    assert suggested["limits"] == {
        "default_target": 22.0,
        "min_temp": 5.0,
        "max_temp": 30.0,
    }
    assert "correction" not in suggested

    # Submitting the shown values unchanged keeps everything but the target.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _nest(_without(legacy, "target_entity"), ROOM_SECTIONS)
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    stored = dict(entry.subentries[subentry_id].data)
    assert "target_entity" not in stored
    assert stored == _without(legacy, "target_entity")


async def test_legacy_target_entity_dropped(hass: HomeAssistant, house) -> None:
    """_async_room_data never stores a Zeitwerk target (pre-0.4 key)."""
    from custom_components.heizwerk.config_flow import _async_room_data

    data = await _async_room_data(
        hass, {**nested_room(), "target_entity": "input_number.x"}, {}
    )
    assert "target_entity" not in data


async def test_hidden_fields_keep_values(hass: HomeAssistant, house) -> None:
    """Hidden fields are not submitted; stored values / defaults are kept."""
    entry = await _hub_entry(hass)
    # lock_mode off -> frost_temperature hidden.
    data = nested_room(observe_only=True)
    data["windows_locks"].pop("frost_temperature")
    result = await _add_room(hass, entry, data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    subentry_id = next(iter(entry.subentries))
    assert entry.subentries[subentry_id].data["frost_temperature"] == 7.0

    # A hidden value submitted anyway is dropped by HA; the stored one survives.
    hass.config_entries.async_update_subentry(
        entry,
        entry.subentries[subentry_id],
        data={**entry.subentries[subentry_id].data, "frost_temperature": 9.0},
    )
    await hass.async_block_till_done()
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    data["windows_locks"]["frost_temperature"] = 11.0
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], data
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[subentry_id].data["frost_temperature"] == 9.0


async def test_visible_fields_are_used(hass: HomeAssistant, house) -> None:
    entry = await _hub_entry(hass)
    data = nested_room(lock_mode="frost", default_target=19.0, observe_only=True)
    data["windows_locks"]["frost_temperature"] = 8.0
    result = await _add_room(hass, entry, data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    stored = next(iter(entry.subentries.values())).data
    assert stored["default_target"] == 19.0
    assert stored["frost_temperature"] == 8.0


async def test_resume_action_round_trip(hass: HomeAssistant, house) -> None:
    entry = await _hub_entry(hass)
    data = nested_room(observe_only=True)
    data["schedule"]["resume_action"] = RESUME
    result = await _add_room(hass, entry, data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    subentry_id = next(iter(entry.subentries))
    assert entry.subentries[subentry_id].data["resume_action"] == RESUME

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert _suggested(result["data_schema"])["schedule"]["resume_action"] == RESUME
    # A single action (dict) is stored as a list; clearing removes the key.
    data["schedule"]["resume_action"] = RESUME[0]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], data
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[subentry_id].data["resume_action"] == RESUME

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    data["schedule"]["resume_action"] = []
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], data
    )
    await hass.async_block_till_done()
    assert "resume_action" not in entry.subentries[subentry_id].data


async def test_invalid_resume_action(hass: HomeAssistant, house) -> None:
    entry = await _hub_entry(hass)
    data = nested_room(observe_only=True)
    data["schedule"]["resume_action"] = [{"action": "not a service!"}]
    result = await _add_room(hass, entry, data)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"schedule": "invalid_action"}


async def test_room_validation(hass: HomeAssistant, house) -> None:
    entry = await _hub_entry(
        hass,
    )
    data = nested_room()
    data["limits"] = {"min_temp": 25, "max_temp": 20}
    result = await _add_room(hass, entry, data)
    assert result["errors"] == {"limits": "min_max"}


async def test_offset_with_external_input_rejected(hass: HomeAssistant, house) -> None:
    entry = await _hub_entry(hass)
    data = nested_room(observe_only=True)
    data["regulation"] = {
        "correction": 0.0,
        "regulation": "offset",
        "external_temperature_entities": ["number.trv_bad_external_temperature"],
    }
    result = await _add_room(hass, entry, data)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"regulation": "offset_with_external"}
    # The submitted values are kept in the re-shown form.
    assert _suggested(result["data_schema"])["regulation"]["regulation"] == "offset"

    data["regulation"]["regulation"] = "setpoint"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


# --- Zeitwerk plan detection ---------------------------------------------------


def _plan(plan_id: str, *actions: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": plan_id,
        "name": plan_id,
        "profiles": [
            {"id": "comfort", "name": "Komfort", "actions": list(actions)},
            {"id": "eco", "name": "Eco", "actions": []},
        ],
    }


def _set_value(entity_id: Any, *, in_target: bool = True) -> dict[str, Any]:
    action: dict[str, Any] = {
        "action": "climate.set_temperature",
        "data": {"temperature": 21},
    }
    if in_target:
        action["target"] = {"entity_id": entity_id}
    else:
        action["entity_id"] = entity_id
    return action


def _register_get_plan(hass: HomeAssistant, plans: list[dict[str, Any]]) -> None:
    async def get_plan(call: ServiceCall) -> dict[str, Any]:
        return {"plans": plans}

    hass.services.async_register(
        "zeitwerk", "get_plan", get_plan, supports_response=SupportsResponse.ONLY
    )


@pytest.mark.parametrize(
    ("plans", "expected"),
    [
        (
            [
                _plan("heizung_bad", _set_value(CLIMATE)),
                _plan("heizung_kueche", _set_value("climate.heizwerk_kueche")),
            ],
            "heizung_bad",
        ),
        (
            [_plan("heizung_bad", _set_value([CLIMATE, "x.y"], in_target=False))],
            "heizung_bad",
        ),
        ([_plan("heizung_kueche", _set_value("climate.heizwerk_kueche"))], None),
        (
            [
                _plan("heizung_bad", _set_value(CLIMATE)),
                _plan("heizung_bad_2", _set_value([CLIMATE])),
            ],
            None,
        ),
    ],
    ids=["one", "entity_id_list", "none", "several"],
)
async def test_plan_auto_detect(
    hass: HomeAssistant, house, plans: list, expected: str | None
) -> None:
    _register_get_plan(hass, plans)
    entry = await _hub_entry(hass)
    result = await _add_room(hass, entry, nested_room())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"].get("zeitwerk_plan") == expected


async def test_plan_auto_detect_keeps_manual_plan(hass: HomeAssistant, house) -> None:
    _register_get_plan(hass, [_plan("heizung_bad", _set_value(CLIMATE))])
    entry = await _hub_entry(hass)
    result = await _add_room(hass, entry, nested_room(zeitwerk_plan="anderer_plan"))
    assert result["data"]["zeitwerk_plan"] == "anderer_plan"


async def test_plan_auto_detect_on_reconfigure(hass: HomeAssistant, house) -> None:
    """Existing room: the climate entity id comes from the entity registry."""
    entry = await _hub_entry(hass)
    result = await _add_room(hass, entry, nested_room())
    assert "zeitwerk_plan" not in result["data"]  # no Zeitwerk installed
    await hass.async_block_till_done()
    _register_get_plan(hass, [_plan("heizung_bad", _set_value(CLIMATE))])
    subentry_id = next(iter(entry.subentries))
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    # Renamed room keeps its entity id climate.heizwerk_bad (registry lookup).
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], nested_room(name="Badezimmer")
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data["zeitwerk_plan"] == "heizung_bad"


async def test_plan_auto_detect_service_failure(hass: HomeAssistant, house) -> None:
    async def broken(call: ServiceCall) -> dict[str, Any]:
        raise RuntimeError("boom")

    hass.services.async_register(
        "zeitwerk", "get_plan", broken, supports_response=SupportsResponse.ONLY
    )
    entry = await _hub_entry(hass)
    result = await _add_room(hass, entry, nested_room())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "zeitwerk_plan" not in result["data"]


async def test_zeitwerk_plans_offered(hass: HomeAssistant, house) -> None:
    hass.states.async_set(
        "sensor.zeitwerk_heizung_bad_profile", "Komfort", {"plan_id": "heizung_bad"}
    )
    hass.states.async_set("sensor.other", "1", {"plan_id": "nope"})
    assert zeitwerk_plans(hass) == ["heizung_bad"]


# --- schema checks -------------------------------------------------------------


def _fields(schema: probatio.Schema) -> dict[str | None, dict[str, Any]]:
    """Fields per section (None = top level): name -> selector/validator."""
    out: dict[str | None, dict[str, Any]] = {None: {}}
    for key, value in schema.schema.items():
        if isinstance(value, section):
            out[key.schema] = {k.schema: v for k, v in value.schema.schema.items()}
        else:
            out[None][key.schema] = value
    return out


def _entity_selectors(schema: probatio.Schema) -> list[dict]:
    return [
        value.serialize()["selector"]["entity"]
        for fields in _fields(schema).values()
        for value in fields.values()
        if isinstance(value, EntitySelector)
    ]


async def test_entity_selectors_do_not_filter_everything(hass: HomeAssistant) -> None:
    """Regression: device_class=None serialised to [] hid every entity."""
    selectors = _entity_selectors(_hub_schema()) + _entity_selectors(_room_schema(hass))
    assert len(selectors) == 10
    for sel in selectors:
        assert sel.get("device_class") != [], sel


def test_visibility_conditions_serialized(hass: HomeAssistant) -> None:
    """Layout and visible conditions as the frontend gets them."""
    schema = _room_schema(hass)
    serialized = probatio.to_field_list(schema, custom_serializer=cv.custom_serializer)
    add_visible_conditions_to_serialized_schema(schema, serialized)
    by_name = {field["name"]: field for field in serialized}
    assert [f["name"] for f in serialized] == [
        "name",
        "trvs",
        "temperature_sensor",
        "observe_only",
        "schedule",
        "room_climate",
        "windows_locks",
        "regulation",
        "limits",
    ]
    assert all("visible" not in field for field in serialized)
    inner = {field["name"]: field for field in by_name["windows_locks"]["schema"]}
    assert inner["frost_temperature"]["visible"] == {
        "field": "lock_mode",
        "value": "frost",
    }
    schedule = {field["name"]: field for field in by_name["schedule"]["schema"]}
    assert schedule["resume_action"]["selector"] == {"action": {}}
    limits = [field["name"] for field in by_name["limits"]["schema"]]
    assert limits == ["default_target", "min_temp", "max_temp"]


@pytest.mark.parametrize("lang", ["de", "en"])
async def test_every_field_is_explained(hass: HomeAssistant, lang: str) -> None:
    """Every field (also inside sections) has a label and a description."""
    strings = json.loads((TRANSLATIONS / f"{lang}.json").read_text("utf-8"))
    steps = [
        (strings["config"]["step"]["user"], _hub_schema()),
        (strings["options"]["step"]["init"], _hub_schema()),
        (strings["config_subentries"]["room"]["step"]["user"], _room_schema(hass)),
        (
            strings["config_subentries"]["room"]["step"]["reconfigure"],
            _room_schema(hass),
        ),
    ]
    for step, schema in steps:
        for sec, fields in _fields(schema).items():
            block = step if sec is None else step["sections"][sec]
            if sec is not None:
                assert block["name"], sec
                assert block["description"], sec
            for name in fields:
                assert block["data"][name], (lang, sec, name)
                assert block["data_description"][name], (lang, sec, name)
            assert set(block["data"]) == set(fields), (lang, sec)
            assert set(block["data_description"]) == set(fields), (lang, sec)
        assert set(step.get("sections", {})) == set(_fields(schema)) - {None}
    errors = strings["config_subentries"]["room"]["error"]
    assert errors["offset_with_external"]
    assert "<" not in json.dumps(strings)


async def test_heizwerk_entities_rejected_and_not_offered(
    hass: HomeAssistant, house
) -> None:
    """Own climate entity as thermostat would loop."""
    from homeassistant.config_entries import ConfigSubentryData

    entry = MockConfigEntry(
        domain=DOMAIN,
        options={"summer_lock_temperature": 16, "summer_lock_minutes": 10},
        subentries_data=[
            ConfigSubentryData(
                data=room_data(),
                subentry_type=SUBENTRY_ROOM,
                title="Bad",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    subentry_id = next(iter(entry.subentries))
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    trv_sel = result["data_schema"].schema["trvs"].serialize()["selector"]["entity"]
    assert "climate.heizwerk_bad" in trv_sel["exclude_entities"]
    data = nested_room(trvs=["climate.heizwerk_bad"])
    # The selector already rejects own entities (schema level) ...
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(result["flow_id"], data)
    # ... and validate_room catches them too (e.g. if a client bypasses it).
    from custom_components.heizwerk.config_flow import validate_room

    errors = validate_room(
        entry,
        flat_room(trvs=["climate.heizwerk_bad"]),
        subentry_id,
        hass=hass,
    )
    assert errors["trvs"] == "heizwerk_entity"
