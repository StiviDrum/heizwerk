"""Config flow: one Heizwerk entry (house options) + one subentry per room.

The forms group optional settings in collapsible sections. Sections nest the
submitted data, but entry options and room subentry data are stored flat (same
keys as before sections existed), so the runtime and older entries need no
migration: ``_flatten`` on save, ``_nest`` when showing stored values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import (
    Optional as VisibleOptional,
    Required as VisibleRequired,
    section,
)
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    selector,
)
from homeassistant.util import slugify
import probatio

from .const import (
    CONF_CORRECTION,
    CONF_DEFAULT_TARGET,
    CONF_EXTERNAL_TEMPERATURE_ENTITIES,
    CONF_FROST_TEMPERATURE,
    CONF_HEAT_SETPOINT,
    CONF_HUMIDITY_SENSOR,
    CONF_HUMIDITY_THRESHOLD,
    CONF_HYSTERESIS_HIGH,
    CONF_HYSTERESIS_LOW,
    CONF_LOCK_ENTITIES,
    CONF_LOCK_MODE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_MOLD_SENSOR,
    CONF_NAME,
    CONF_OBSERVE_ONLY,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_LIMIT,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_REGULATION,
    CONF_RESUME_ACTION,
    CONF_SEASON_ENTITY,
    CONF_SEND_TEMPERATURE,
    CONF_SUMMER_LOCK_MINUTES,
    CONF_SUMMER_LOCK_TEMPERATURE,
    CONF_TARGET_ENTITY,
    CONF_TEMPERATURE_SENSOR,
    CONF_TRV_MANUAL,
    CONF_TRVS,
    CONF_WALL_TEMPERATURE_SENSOR,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOWS,
    CONF_ZEITWERK_PLAN,
    DEFAULT_FROST_TEMPERATURE,
    DEFAULT_HEAT_SETPOINT,
    DEFAULT_HUMIDITY_THRESHOLD,
    DEFAULT_HYSTERESIS_HIGH,
    DEFAULT_HYSTERESIS_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_SUMMER_LOCK_MINUTES,
    DEFAULT_SUMMER_LOCK_TEMPERATURE,
    DEFAULT_TARGET,
    DEFAULT_WINDOW_CLOSE_DELAY,
    DEFAULT_WINDOW_OPEN_DELAY,
    DOMAIN,
    LOCK_MODE_FROST,
    LOCK_MODE_OFF,
    NAME,
    REGULATION_OFFSET,
    REGULATION_SETPOINT,
    REGULATION_TWO_POINT,
    SUBENTRY_ROOM,
    TRV_MANUAL_ADOPT,
    TRV_MANUAL_RESET,
)
from .helpers import heizwerk_entities, is_heizwerk_entity

_LOGGER = logging.getLogger(__name__)


def _entity(
    domain: list[str],
    multiple: bool = False,
    device_class: list[str] | None = None,
    exclude: list[str] | None = None,
) -> selector.EntitySelector:
    """Entity selector; device_class / exclude_entities only when given.

    An explicit ``device_class=None`` serialises to ``[]``, which makes the
    frontend filter out every entity ("no entities available").
    """
    options: dict[str, Any] = {"domain": domain, "multiple": multiple}
    if device_class:
        options["device_class"] = device_class
    if exclude:
        options["exclude_entities"] = exclude
    return selector.EntitySelector(selector.EntitySelectorConfig(**options))


_SENSOR_TEMP = _entity(["sensor", "input_number", "number"])


def _number(
    minimum: float, maximum: float, step: float, unit: str | None = None
) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


# --- Form layout -----------------------------------------------------------
# Section keys and the (flat, stored) fields each section holds. The order of
# the fields here is the order in the form.

SECTION_SUMMER_LOCK = "summer_lock"
SECTION_CLIMATE = "climate"

HUB_SECTIONS: dict[str, tuple[str, ...]] = {
    SECTION_SUMMER_LOCK: (CONF_SUMMER_LOCK_TEMPERATURE, CONF_SUMMER_LOCK_MINUTES),
    SECTION_CLIMATE: (CONF_OUTDOOR_HUMIDITY,),
}

SECTION_SCHEDULE = "schedule"
SECTION_ROOM_CLIMATE = "room_climate"
SECTION_WINDOWS_LOCKS = "windows_locks"
SECTION_REGULATION = "regulation"
SECTION_LIMITS = "limits"

ROOM_SECTIONS: dict[str, tuple[str, ...]] = {
    SECTION_SCHEDULE: (CONF_ZEITWERK_PLAN, CONF_RESUME_ACTION),
    SECTION_ROOM_CLIMATE: (
        CONF_HUMIDITY_SENSOR,
        CONF_MOLD_SENSOR,
        CONF_WALL_TEMPERATURE_SENSOR,
        CONF_HUMIDITY_THRESHOLD,
    ),
    SECTION_WINDOWS_LOCKS: (
        CONF_WINDOWS,
        CONF_WINDOW_OPEN_DELAY,
        CONF_WINDOW_CLOSE_DELAY,
        CONF_LOCK_ENTITIES,
        CONF_LOCK_MODE,
        CONF_FROST_TEMPERATURE,
        CONF_OUTDOOR_LIMIT,
    ),
    SECTION_REGULATION: (
        CONF_REGULATION,
        CONF_SEND_TEMPERATURE,
        CONF_CORRECTION,
        CONF_HYSTERESIS_LOW,
        CONF_HYSTERESIS_HIGH,
        CONF_HEAT_SETPOINT,
        CONF_TRV_MANUAL,
    ),
    SECTION_LIMITS: (CONF_DEFAULT_TARGET, CONF_MIN_TEMP, CONF_MAX_TEMP),
}

_TWO_POINT: Any = {"field": CONF_REGULATION, "value": REGULATION_TWO_POINT}


def _is_two_point(data: Mapping[str, Any]) -> bool:
    return data.get(CONF_REGULATION) == REGULATION_TWO_POINT


# Fields with a visibility condition: (default, hidden(flat data)). A hidden
# field is omitted from the submitted data; on save it keeps the stored
# value, else the default (None = leave it out).
ROOM_HIDEABLE: dict[str, tuple[Any, Callable[[Mapping[str, Any]], bool]]] = {
    CONF_FROST_TEMPERATURE: (
        DEFAULT_FROST_TEMPERATURE,
        lambda d: d.get(CONF_LOCK_MODE) != LOCK_MODE_FROST,
    ),
    CONF_HYSTERESIS_LOW: (DEFAULT_HYSTERESIS_LOW, lambda d: not _is_two_point(d)),
    CONF_HYSTERESIS_HIGH: (DEFAULT_HYSTERESIS_HIGH, lambda d: not _is_two_point(d)),
    CONF_HEAT_SETPOINT: (DEFAULT_HEAT_SETPOINT, lambda d: not _is_two_point(d)),
    CONF_WALL_TEMPERATURE_SENSOR: (None, lambda d: bool(d.get(CONF_MOLD_SENSOR))),
}

# Two-point regulation: smaller total hysteresis makes the valve chatter.
MIN_HYSTERESIS = 0.2

_TEMPERATURE_UNITS = {UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT}

_COLLAPSED: Any = {"collapsed": True}


def _flatten(
    data: Mapping[str, Any], sections: Mapping[str, tuple[str, ...]]
) -> dict[str, Any]:
    """Merge the section dicts of submitted form data into one flat dict."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if key in sections and isinstance(value, Mapping):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def _nest(
    flat: Mapping[str, Any], sections: Mapping[str, tuple[str, ...]]
) -> dict[str, Any]:
    """Group flat stored data into the form's sections (for suggested values)."""
    in_section = {key for keys in sections.values() for key in keys}
    nested: dict[str, Any] = {
        key: value for key, value in flat.items() if key not in in_section
    }
    for name, keys in sections.items():
        nested[name] = {key: flat[key] for key in keys if key in flat}
    return nested


def _hub_schema() -> probatio.Schema:
    # No weather entities: their state is a condition, not a number.
    outdoor = _entity(["sensor", "input_number"])
    return probatio.Schema(
        {
            probatio.Optional(CONF_OUTDOOR_TEMPERATURE): outdoor,
            probatio.Optional(CONF_SEASON_ENTITY): _entity(
                ["input_boolean", "binary_sensor", "switch", "schedule"]
            ),
            probatio.Required(SECTION_SUMMER_LOCK): section(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_SUMMER_LOCK_TEMPERATURE,
                            default=DEFAULT_SUMMER_LOCK_TEMPERATURE,
                        ): _number(0, 30, 0.5, "°C"),
                        probatio.Required(
                            CONF_SUMMER_LOCK_MINUTES,
                            default=DEFAULT_SUMMER_LOCK_MINUTES,
                        ): _number(0, 240, 1, "min"),
                    }
                ),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_CLIMATE): section(
                probatio.Schema({probatio.Optional(CONF_OUTDOOR_HUMIDITY): outdoor}),
                _COLLAPSED,
            ),
        }
    )


def zeitwerk_plans(hass: HomeAssistant) -> list[str]:
    """Plan ids announced by Zeitwerk profile sensors."""
    return sorted(
        {
            str(plan)
            for state in hass.states.async_all("sensor")
            if state.entity_id.startswith("sensor.zeitwerk_")
            and (plan := state.attributes.get("plan_id"))
        }
    )


def _room_schema(hass: HomeAssistant) -> probatio.Schema:
    plans = zeitwerk_plans(hass)
    own = heizwerk_entities(hass)
    plan_selector: Any = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=plans,
                custom_value=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        if plans
        else selector.TextSelector()
    )
    return probatio.Schema(
        {
            probatio.Required(CONF_NAME): selector.TextSelector(),
            # Heizwerk's own entities are never offered: they would make
            # Heizwerk control / follow itself in an endless loop.
            probatio.Required(CONF_TRVS): _entity(
                ["climate"], multiple=True, exclude=own
            ),
            probatio.Optional(CONF_TEMPERATURE_SENSOR): _SENSOR_TEMP,
            probatio.Required(
                CONF_OBSERVE_ONLY, default=True
            ): selector.BooleanSelector(),
            probatio.Required(SECTION_SCHEDULE): section(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_ZEITWERK_PLAN): plan_selector,
                        probatio.Optional(
                            CONF_RESUME_ACTION
                        ): selector.ActionSelector(),
                    }
                ),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_ROOM_CLIMATE): section(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_HUMIDITY_SENSOR): _entity(
                            ["sensor", "input_number"]
                        ),
                        probatio.Optional(CONF_MOLD_SENSOR): _entity(
                            ["sensor"], device_class=["humidity"]
                        ),
                        VisibleOptional(
                            CONF_WALL_TEMPERATURE_SENSOR,
                            visible={
                                "field": CONF_MOLD_SENSOR,
                                "operator": "not_exists",
                            },
                        ): _SENSOR_TEMP,
                        probatio.Required(
                            CONF_HUMIDITY_THRESHOLD,
                            default=DEFAULT_HUMIDITY_THRESHOLD,
                        ): _number(30, 95, 1, "%"),
                    }
                ),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_WINDOWS_LOCKS): section(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_WINDOWS): _entity(
                            ["binary_sensor", "input_boolean"], multiple=True
                        ),
                        probatio.Required(
                            CONF_WINDOW_OPEN_DELAY, default=DEFAULT_WINDOW_OPEN_DELAY
                        ): _number(0, 900, 1, "s"),
                        probatio.Required(
                            CONF_WINDOW_CLOSE_DELAY,
                            default=DEFAULT_WINDOW_CLOSE_DELAY,
                        ): _number(0, 900, 1, "s"),
                        probatio.Optional(CONF_LOCK_ENTITIES): _entity(
                            ["input_boolean", "binary_sensor", "switch"], multiple=True
                        ),
                        probatio.Required(
                            CONF_LOCK_MODE, default=LOCK_MODE_OFF
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[LOCK_MODE_OFF, LOCK_MODE_FROST],
                                translation_key=CONF_LOCK_MODE,
                                # Dropdown: HA 2026.11 draws the radio dot off-centre
                                # (ha-radio-option squeezes its 16x16 SVG to 11.2x14).
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        VisibleRequired(
                            CONF_FROST_TEMPERATURE,
                            default=DEFAULT_FROST_TEMPERATURE,
                            visible={"field": CONF_LOCK_MODE, "value": LOCK_MODE_FROST},
                        ): _number(4, 12, 0.5, "°C"),
                        probatio.Optional(CONF_OUTDOOR_LIMIT): _number(
                            0, 30, 0.5, "°C"
                        ),
                    }
                ),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_REGULATION): section(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_REGULATION, default=REGULATION_SETPOINT
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    REGULATION_SETPOINT,
                                    REGULATION_OFFSET,
                                    REGULATION_TWO_POINT,
                                ],
                                translation_key=CONF_REGULATION,
                                # Dropdown: HA 2026.11 draws the radio dot off-centre
                                # (ha-radio-option squeezes its 16x16 SVG to 11.2x14).
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        # No schema default: an omitted value must not switch
                        # sending on for 0.4 rooms (see send_temperature_default).
                        probatio.Optional(
                            CONF_SEND_TEMPERATURE
                        ): selector.BooleanSelector(),
                        probatio.Required(CONF_CORRECTION, default=0.0): _number(
                            -5, 5, 0.1, "K"
                        ),
                        VisibleRequired(
                            CONF_HYSTERESIS_LOW,
                            default=DEFAULT_HYSTERESIS_LOW,
                            visible=_TWO_POINT,
                        ): _number(0, 3, 0.1, "K"),
                        VisibleRequired(
                            CONF_HYSTERESIS_HIGH,
                            default=DEFAULT_HYSTERESIS_HIGH,
                            visible=_TWO_POINT,
                        ): _number(0, 3, 0.1, "K"),
                        VisibleRequired(
                            CONF_HEAT_SETPOINT,
                            default=DEFAULT_HEAT_SETPOINT,
                            visible=_TWO_POINT,
                        ): _number(5, 35, 0.5, "°C"),
                        probatio.Required(
                            CONF_TRV_MANUAL, default=TRV_MANUAL_ADOPT
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[TRV_MANUAL_ADOPT, TRV_MANUAL_RESET],
                                translation_key=CONF_TRV_MANUAL,
                                # Dropdown: HA 2026.11 draws the radio dot off-centre
                                # (ha-radio-option squeezes its 16x16 SVG to 11.2x14).
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_LIMITS): section(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_DEFAULT_TARGET, default=DEFAULT_TARGET
                        ): _number(5, 30, 0.5, "°C"),
                        probatio.Required(
                            CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP
                        ): _number(4, 30, 0.5, "°C"),
                        probatio.Required(
                            CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP
                        ): _number(5, 35, 0.5, "°C"),
                    }
                ),
                _COLLAPSED,
            ),
        }
    )


def validate_room(
    entry: ConfigEntry,
    data: Mapping[str, Any],
    subentry_id: str | None = None,
    hass: HomeAssistant | None = None,
) -> dict[str, str]:
    """Return form errors for a room (flat data).

    Errors of fields inside a section are keyed by the section key; the
    frontend shows them at that section (same as core integrations do).
    """
    errors: dict[str, str] = {}
    slug = slugify(data.get(CONF_NAME, ""))
    if not slug:
        errors[CONF_NAME] = "invalid_name"
    for sub in entry.get_subentries_of_type(SUBENTRY_ROOM):
        if (
            sub.subentry_id != subentry_id
            and slugify(sub.data.get(CONF_NAME, "")) == slug
        ):
            errors[CONF_NAME] = "name_exists"
    if not data.get(CONF_TRVS):
        errors[CONF_TRVS] = "no_trvs"
    if hass is not None and any(
        is_heizwerk_entity(hass, e) for e in data.get(CONF_TRVS) or []
    ):
        errors[CONF_TRVS] = "heizwerk_entity"
    if float(data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)) >= float(
        data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)
    ):
        errors[SECTION_LIMITS] = "min_max"
    if data.get(CONF_REGULATION) == REGULATION_OFFSET and data.get(
        CONF_SEND_TEMPERATURE, True
    ):
        errors[SECTION_REGULATION] = "offset_with_external"
    if data.get(CONF_REGULATION) == REGULATION_TWO_POINT:
        if not data.get(CONF_TEMPERATURE_SENSOR):
            errors[SECTION_REGULATION] = "two_point_needs_sensor"
        elif (
            float(data.get(CONF_HYSTERESIS_LOW, DEFAULT_HYSTERESIS_LOW))
            + float(data.get(CONF_HYSTERESIS_HIGH, DEFAULT_HYSTERESIS_HIGH))
            < MIN_HYSTERESIS
        ):
            errors[SECTION_REGULATION] = "hysteresis_too_small"
    if (
        hass is not None
        and (wall := data.get(CONF_WALL_TEMPERATURE_SENSOR))
        and (state := hass.states.get(wall)) is not None
        # No unit (old helpers / templates) is accepted; a wrong one, e.g. % of
        # a mold indicator, is not.
        and (unit := state.attributes.get("unit_of_measurement")) is not None
        and unit not in _TEMPERATURE_UNITS
    ):
        errors[SECTION_ROOM_CLIMATE] = "not_temperature"
    if actions := data.get(CONF_RESUME_ACTION):
        try:
            cv.SCRIPT_SCHEMA(actions)
        except probatio.Invalid:
            errors[SECTION_SCHEDULE] = "invalid_action"
    return errors


def _action_targets(action: Any) -> set[str]:
    """Entity ids an action (HA script action dict) writes to."""
    if not isinstance(action, Mapping):
        return set()
    found: set[str] = set()
    for container in (action, action.get("target"), action.get("data")):
        if not isinstance(container, Mapping):
            continue
        ids = container.get("entity_id")
        if isinstance(ids, str):
            found.add(ids)
        elif isinstance(ids, list):
            found.update(str(i) for i in ids)
    return found


async def async_detect_plan(hass: HomeAssistant, entity_id: str) -> str | None:
    """Id of the one Zeitwerk plan whose profile actions target entity_id.

    Uses the public ``zeitwerk.get_plan`` service. None when Zeitwerk is
    missing, the call fails, or no / several plans match.
    """
    if not hass.services.has_service("zeitwerk", "get_plan"):
        return None
    try:
        response = await hass.services.async_call(
            "zeitwerk", "get_plan", {}, blocking=True, return_response=True
        )
    except Exception as err:  # foreign integration: never block saving a room
        _LOGGER.debug("Zeitwerk plan detection failed: %s", err)
        return None
    plans = response.get("plans") if isinstance(response, Mapping) else None
    if not isinstance(plans, list):
        return None
    matches = {
        str(plan["id"])
        for plan in plans
        if isinstance(plan, Mapping)
        and plan.get("id")
        and any(
            entity_id in _action_targets(action)
            for profile in plan.get("profiles") or []
            if isinstance(profile, Mapping)
            for action in profile.get("actions") or []
        )
    }
    return matches.pop() if len(matches) == 1 else None


def room_climate_entity_id(
    hass: HomeAssistant, name: str, subentry_id: str | None = None
) -> str:
    """Climate entity id of a room: registry for existing rooms, else predicted."""
    if subentry_id and (
        entity_id := er.async_get(hass).async_get_entity_id(
            "climate", DOMAIN, subentry_id
        )
    ):
        return entity_id
    return f"climate.{DOMAIN}_{slugify(name)}"


def send_temperature_default(stored: Mapping[str, Any]) -> bool:
    """send_temperature of a room that has no stored value.

    New rooms: on. Rooms from before 0.5: on only if they had explicit
    external temperature inputs, so an unrelated edit never switches it on.
    """
    if not stored:
        return True
    return bool(stored.get(CONF_EXTERNAL_TEMPERATURE_ENTITIES))


def room_input(
    user_input: Mapping[str, Any], stored: Mapping[str, Any]
) -> dict[str, Any]:
    """Flat submitted room data with the effective send_temperature."""
    data = _flatten(user_input, ROOM_SECTIONS)
    data.setdefault(
        CONF_SEND_TEMPERATURE,
        stored.get(CONF_SEND_TEMPERATURE, send_temperature_default(stored)),
    )
    return data


async def _async_room_data(
    hass: HomeAssistant,
    user_input: Mapping[str, Any],
    stored: Mapping[str, Any],
    subentry_id: str | None = None,
) -> dict[str, Any]:
    """Flat subentry data from the submitted form.

    Hidden fields keep the stored value (or their default); an empty Zeitwerk
    plan is detected from the room's climate entity; the legacy Zeitwerk
    target (before 0.4) is dropped.
    """
    data = room_input(user_input, stored)
    data.pop(CONF_TARGET_ENTITY, None)
    for key, (default, hidden) in ROOM_HIDEABLE.items():
        if key not in data and hidden(data):
            value = stored.get(key, default)
            if value is not None:
                data[key] = value
    # Legacy (before 0.5): explicit external temperature inputs are kept
    # unchanged (the runtime still honours them), but no longer offered.
    # Dropped when sending is switched off (the runtime ignores it then).
    if data[CONF_SEND_TEMPERATURE] and (
        legacy := stored.get(CONF_EXTERNAL_TEMPERATURE_ENTITIES)
    ):
        data[CONF_EXTERNAL_TEMPERATURE_ENTITIES] = legacy
    if actions := cv.ensure_list(data.pop(CONF_RESUME_ACTION, None)):
        data[CONF_RESUME_ACTION] = actions
    if not data.get(CONF_ZEITWERK_PLAN):
        data.pop(CONF_ZEITWERK_PLAN, None)
        climate = room_climate_entity_id(hass, data[CONF_NAME], subentry_id)
        if plan := await async_detect_plan(hass, climate):
            data[CONF_ZEITWERK_PLAN] = plan
    return data


def _room_suggestions(stored: Mapping[str, Any]) -> dict[str, Any]:
    """Nest stored (flat) room data into the form sections."""
    data = dict(stored)
    data.setdefault(CONF_SEND_TEMPERATURE, send_temperature_default(stored))
    return _nest(data, ROOM_SECTIONS)


class HeizwerkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single Heizwerk entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """House-wide sensors and summer lock."""
        if user_input is not None:
            return self.async_create_entry(
                title=NAME, data={}, options=_flatten(user_input, HUB_SECTIONS)
            )
        return self.async_show_form(step_id="user", data_schema=_hub_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """House options."""
        return HeizwerkOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Rooms are subentries."""
        return {SUBENTRY_ROOM: RoomSubentryFlow}


class HeizwerkOptionsFlow(OptionsFlow):
    """Change the house-wide options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single form."""
        if user_input is not None:
            return self.async_create_entry(data=_flatten(user_input, HUB_SECTIONS))
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _hub_schema(), _nest(self.config_entry.options, HUB_SECTIONS)
            ),
        )


class RoomSubentryFlow(ConfigSubentryFlow):
    """Add or change a room."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new room."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_room(
                self._get_entry(),
                room_input(user_input, {}),
                hass=self.hass,
            )
            if not errors:
                data = await _async_room_data(self.hass, user_input, {})
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _room_schema(self.hass), user_input or _room_suggestions({})
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change a room (the update listener reloads the entry)."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_room(
                entry,
                room_input(user_input, subentry.data),
                subentry.subentry_id,
                hass=self.hass,
            )
            if not errors:
                data = await _async_room_data(
                    self.hass, user_input, subentry.data, subentry.subentry_id
                )
                return self.async_update_and_abort(
                    entry, subentry, title=data[CONF_NAME], data=data
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _room_schema(self.hass),
                user_input or _room_suggestions(subentry.data),
            ),
            errors=errors,
        )
