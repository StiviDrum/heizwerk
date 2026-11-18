"""Config flow: one Heizwerk entry (house options) + one subentry per room."""

from __future__ import annotations

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
from homeassistant.helpers import selector
from homeassistant.util import slugify
import voluptuous as vol

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


def _hub_schema() -> vol.Schema:
    return vol.Schema(
        {
            # No weather entities: their state is a condition, not a number.
            vol.Optional(CONF_OUTDOOR_TEMPERATURE): _entity(["sensor", "input_number"]),
            vol.Optional(CONF_OUTDOOR_HUMIDITY): _entity(["sensor", "input_number"]),
            vol.Optional(CONF_SEASON_ENTITY): _entity(
                ["input_boolean", "binary_sensor", "switch", "schedule"]
            ),
            vol.Required(
                CONF_SUMMER_LOCK_TEMPERATURE, default=DEFAULT_SUMMER_LOCK_TEMPERATURE
            ): _number(0, 30, 0.5, "°C"),
            vol.Required(
                CONF_SUMMER_LOCK_MINUTES, default=DEFAULT_SUMMER_LOCK_MINUTES
            ): _number(0, 240, 1, "min"),
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


def _room_schema(hass: HomeAssistant) -> vol.Schema:
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
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_TRVS): _entity(["climate"], multiple=True),
            vol.Optional(CONF_TEMPERATURE_SENSOR): _SENSOR_TEMP,
            vol.Optional(CONF_HUMIDITY_SENSOR): _entity(["sensor", "input_number"]),
            vol.Optional(CONF_WALL_TEMPERATURE_SENSOR): _SENSOR_TEMP,
            vol.Optional(CONF_WINDOWS): _entity(
                ["binary_sensor", "input_boolean"], multiple=True
            ),
            vol.Required(
                CONF_WINDOW_OPEN_DELAY, default=DEFAULT_WINDOW_OPEN_DELAY
            ): _number(0, 900, 1, "s"),
            vol.Required(
                CONF_WINDOW_CLOSE_DELAY, default=DEFAULT_WINDOW_CLOSE_DELAY
            ): _number(0, 900, 1, "s"),
            vol.Optional(CONF_TARGET_ENTITY): _entity(
                ["input_number", "number", "sensor", "climate"]
            ),
            vol.Optional(CONF_ZEITWERK_PLAN): plan_selector,
            vol.Optional(CONF_LOCK_ENTITIES): _entity(
                ["input_boolean", "binary_sensor", "switch"], multiple=True
            ),
            vol.Required(
                CONF_LOCK_MODE, default=LOCK_MODE_OFF
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[LOCK_MODE_OFF, LOCK_MODE_FROST],
                    translation_key=CONF_LOCK_MODE,
                )
            ),
            vol.Required(
                CONF_FROST_TEMPERATURE, default=DEFAULT_FROST_TEMPERATURE
            ): _number(4, 12, 0.5, "°C"),
            vol.Required(CONF_CORRECTION, default=0.0): _number(-5, 5, 0.1, "K"),
            vol.Required(
                CONF_REGULATION, default=REGULATION_SETPOINT
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[REGULATION_SETPOINT, REGULATION_OFFSET],
                    translation_key=CONF_REGULATION,
                )
            ),
            vol.Optional(CONF_EXTERNAL_TEMPERATURE_ENTITIES): _entity(
                ["number", "input_number"], multiple=True
            ),
            vol.Required(CONF_DEFAULT_TARGET, default=DEFAULT_TARGET): _number(
                5, 30, 0.5, "°C"
            ),
            vol.Required(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): _number(
                4, 30, 0.5, "°C"
            ),
            vol.Required(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): _number(
                5, 35, 0.5, "°C"
            ),
            vol.Required(
                CONF_HUMIDITY_THRESHOLD, default=DEFAULT_HUMIDITY_THRESHOLD
            ): _number(30, 95, 1, "%"),
            vol.Required(CONF_OBSERVE_ONLY, default=True): selector.BooleanSelector(),
        }
    )


def validate_room(
    entry: ConfigEntry, data: dict[str, Any], subentry_id: str | None = None
) -> dict[str, str]:
    """Return form errors for a room."""
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
    if float(data.get(CONF_MIN_TEMP, 0)) >= float(data.get(CONF_MAX_TEMP, 0)):
        errors[CONF_MAX_TEMP] = "min_max"
    return errors


class HeizwerkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single Heizwerk entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """House-wide sensors and summer lock."""
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={}, options=user_input)
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
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _hub_schema(), self.config_entry.options
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
            errors = validate_room(self._get_entry(), user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
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
            errors = validate_room(entry, user_input, subentry.subentry_id)
            if not errors:
                return self.async_update_and_abort(
                    entry, subentry, title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _room_schema(self.hass), user_input or dict(subentry.data)
            ),
            errors=errors,
        )
