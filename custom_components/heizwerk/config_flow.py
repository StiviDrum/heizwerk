"""Config flow: one Heizwerk entry (house options) + one subentry per room.

The forms group optional settings in collapsible sections. Sections nest the
submitted data, but entry options and room subentry data are stored flat (same
keys as before sections existed), so the runtime and older entries need no
migration: ``_flatten`` on save, ``_nest`` when showing stored values.
"""

from __future__ import annotations

from collections.abc import Mapping
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import (
    Required as VisibleRequired,
    section,
)
from homeassistant.helpers import selector
from homeassistant.util import slugify
import probatio

from .const import (
    CONF_CORRECTION,
    CONF_DEFAULT_TARGET,
    CONF_EXTERNAL_TEMPERATURE_ENTITIES,
    CONF_FROST_TEMPERATURE,
    CONF_HUMIDITY_SENSOR,
    CONF_HUMIDITY_THRESHOLD,
    CONF_LOCK_ENTITIES,
    CONF_LOCK_MODE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_OBSERVE_ONLY,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_REGULATION,
    CONF_SEASON_ENTITY,
    CONF_SUMMER_LOCK_MINUTES,
    CONF_SUMMER_LOCK_TEMPERATURE,
    CONF_TARGET_ENTITY,
    CONF_TEMPERATURE_SENSOR,
    CONF_TRVS,
    CONF_WALL_TEMPERATURE_SENSOR,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOWS,
    CONF_ZEITWERK_PLAN,
    DEFAULT_FROST_TEMPERATURE,
    DEFAULT_HUMIDITY_THRESHOLD,
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
    SUBENTRY_ROOM,
)

_LOGGER = logging.getLogger(__name__)


def _entity(
    domain: list[str], multiple: bool = False, device_class: list[str] | None = None
) -> selector.EntitySelector:
    """Entity selector; device_class only when given.

    An explicit ``device_class=None`` serialises to ``[]``, which makes the
    frontend filter out every entity ("no entities available").
    """
    config = selector.EntitySelectorConfig(domain=domain, multiple=multiple)
    if device_class:
        config = selector.EntitySelectorConfig(
            domain=domain, multiple=multiple, device_class=device_class
        )
    return selector.EntitySelector(config)


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

SECTION_ZEITWERK = "zeitwerk"
SECTION_ROOM_CLIMATE = "room_climate"
SECTION_WINDOWS_LOCKS = "windows_locks"
SECTION_REGULATION = "regulation"
SECTION_LIMITS = "limits"

ROOM_SECTIONS: dict[str, tuple[str, ...]] = {
    SECTION_ZEITWERK: (CONF_ZEITWERK_PLAN,),
    SECTION_ROOM_CLIMATE: (
        CONF_HUMIDITY_SENSOR,
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
    ),
    SECTION_REGULATION: (
        CONF_CORRECTION,
        CONF_REGULATION,
        CONF_EXTERNAL_TEMPERATURE_ENTITIES,
    ),
    SECTION_LIMITS: (CONF_MIN_TEMP, CONF_MAX_TEMP),
}

# Fields with a visibility condition. A hidden field is omitted from the
# submitted data; on save it keeps the stored value, else this default.
ROOM_HIDEABLE_DEFAULTS: dict[str, Any] = {
    CONF_DEFAULT_TARGET: DEFAULT_TARGET,
    CONF_FROST_TEMPERATURE: DEFAULT_FROST_TEMPERATURE,
}

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
            probatio.Required(CONF_TRVS): _entity(["climate"], multiple=True),
            probatio.Optional(CONF_TEMPERATURE_SENSOR): _SENSOR_TEMP,
            probatio.Optional(CONF_TARGET_ENTITY): _entity(
                ["input_number", "number", "sensor", "climate"]
            ),
            # Top level, not in the "zeitwerk" section: a visibility condition
            # can only reference fields of its own section / level.
            VisibleRequired(
                CONF_DEFAULT_TARGET,
                default=DEFAULT_TARGET,
                visible={"field": CONF_TARGET_ENTITY, "operator": "not_exists"},
            ): _number(5, 30, 0.5, "°C"),
            probatio.Required(
                CONF_OBSERVE_ONLY, default=True
            ): selector.BooleanSelector(),
            probatio.Required(SECTION_ZEITWERK): section(
                probatio.Schema({probatio.Optional(CONF_ZEITWERK_PLAN): plan_selector}),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_ROOM_CLIMATE): section(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_HUMIDITY_SENSOR): _entity(
                            ["sensor", "input_number"]
                        ),
                        probatio.Optional(CONF_WALL_TEMPERATURE_SENSOR): _SENSOR_TEMP,
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
                            )
                        ),
                        VisibleRequired(
                            CONF_FROST_TEMPERATURE,
                            default=DEFAULT_FROST_TEMPERATURE,
                            visible={"field": CONF_LOCK_MODE, "value": LOCK_MODE_FROST},
                        ): _number(4, 12, 0.5, "°C"),
                    }
                ),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_REGULATION): section(
                probatio.Schema(
                    {
                        probatio.Required(CONF_CORRECTION, default=0.0): _number(
                            -5, 5, 0.1, "K"
                        ),
                        probatio.Required(
                            CONF_REGULATION, default=REGULATION_SETPOINT
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[REGULATION_SETPOINT, REGULATION_OFFSET],
                                translation_key=CONF_REGULATION,
                            )
                        ),
                        probatio.Optional(CONF_EXTERNAL_TEMPERATURE_ENTITIES): _entity(
                            ["number", "input_number"], multiple=True
                        ),
                    }
                ),
                _COLLAPSED,
            ),
            probatio.Required(SECTION_LIMITS): section(
                probatio.Schema(
                    {
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
    entry: ConfigEntry, data: Mapping[str, Any], subentry_id: str | None = None
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
    if float(data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)) >= float(
        data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)
    ):
        errors[SECTION_LIMITS] = "min_max"
    if data.get(CONF_REGULATION) == REGULATION_OFFSET and data.get(
        CONF_EXTERNAL_TEMPERATURE_ENTITIES
    ):
        errors[SECTION_REGULATION] = "offset_with_external"
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


async def async_detect_plan(hass: HomeAssistant, target_entity: str) -> str | None:
    """Id of the one Zeitwerk plan whose profile actions write target_entity.

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
            target_entity in _action_targets(action)
            for profile in plan.get("profiles") or []
            if isinstance(profile, Mapping)
            for action in profile.get("actions") or []
        )
    }
    return matches.pop() if len(matches) == 1 else None


async def _async_room_data(
    hass: HomeAssistant, user_input: Mapping[str, Any], stored: Mapping[str, Any]
) -> dict[str, Any]:
    """Flat subentry data from the submitted form.

    Hidden fields keep the stored value (or their default); an empty Zeitwerk
    plan is detected from the Zeitwerk target.
    """
    data = _flatten(user_input, ROOM_SECTIONS)
    for key, default in ROOM_HIDEABLE_DEFAULTS.items():
        if key not in data:
            data[key] = stored.get(key, default)
    if (target := data.get(CONF_TARGET_ENTITY)) and not data.get(CONF_ZEITWERK_PLAN):
        data.pop(CONF_ZEITWERK_PLAN, None)
        if plan := await async_detect_plan(hass, target):
            data[CONF_ZEITWERK_PLAN] = plan
    return data


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
                self._get_entry(), _flatten(user_input, ROOM_SECTIONS)
            )
            if not errors:
                data = await _async_room_data(self.hass, user_input, {})
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _room_schema(self.hass), user_input or {}
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
                entry, _flatten(user_input, ROOM_SECTIONS), subentry.subentry_id
            )
            if not errors:
                data = await _async_room_data(self.hass, user_input, subentry.data)
                return self.async_update_and_abort(
                    entry, subentry, title=data[CONF_NAME], data=data
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _room_schema(self.hass),
                user_input or _nest(subentry.data, ROOM_SECTIONS),
            ),
            errors=errors,
        )
