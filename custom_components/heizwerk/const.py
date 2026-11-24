"""Constants for Heizwerk."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "heizwerk"
NAME: Final = "Heizwerk"

SUBENTRY_ROOM: Final = "room"

CARD_FILENAME: Final = "heizwerk-card.js"
CARD_URL_BASE: Final = "/heizwerk_static"
DATA_CARD_REGISTERED: Final = "heizwerk_card_registered"

EVENT: Final = "heizwerk_event"
EVENT_VENTILATION_DONE: Final = "ventilation_done"
EVENT_TRV_UNAVAILABLE: Final = "trv_unavailable"

SIGNAL_ROOM_UPDATED: Final = "heizwerk_room_updated_{}"

# --- Hub options ---------------------------------------------------------
CONF_OUTDOOR_TEMPERATURE: Final = "outdoor_temperature"
CONF_OUTDOOR_HUMIDITY: Final = "outdoor_humidity"
CONF_SEASON_ENTITY: Final = "season_entity"
CONF_SUMMER_LOCK_TEMPERATURE: Final = "summer_lock_temperature"
CONF_SUMMER_LOCK_MINUTES: Final = "summer_lock_minutes"

DEFAULT_SUMMER_LOCK_TEMPERATURE: Final = 16.0
DEFAULT_SUMMER_LOCK_MINUTES: Final = 10

# --- Room options --------------------------------------------------------
CONF_NAME: Final = "name"
CONF_TRVS: Final = "trvs"
CONF_TEMPERATURE_SENSOR: Final = "temperature_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_WALL_TEMPERATURE_SENSOR: Final = "wall_temperature_sensor"
CONF_WINDOWS: Final = "windows"
CONF_WINDOW_OPEN_DELAY: Final = "window_open_delay"
CONF_WINDOW_CLOSE_DELAY: Final = "window_close_delay"
CONF_TARGET_ENTITY: Final = "target_entity"
CONF_ZEITWERK_PLAN: Final = "zeitwerk_plan"
# Actions (script syntax) run on "resume" and when a timed override ends.
CONF_RESUME_ACTION: Final = "resume_action"
CONF_SEND_TEMPERATURE: Final = "send_temperature"
CONF_HYSTERESIS_LOW: Final = "hysteresis_low"
CONF_HYSTERESIS_HIGH: Final = "hysteresis_high"
CONF_HEAT_SETPOINT: Final = "heat_setpoint"
# Optional per room; absent = hub summer_lock_temperature.
CONF_OUTDOOR_LIMIT: Final = "outdoor_limit"
CONF_TRV_MANUAL: Final = "trv_manual"
# Mold indicator sensor (% relative humidity at the wall).
CONF_MOLD_SENSOR: Final = "mold_sensor"
# Knob values below this are discarded; absent = automatic.
CONF_KNOB_MIN: Final = "knob_min_temperature"
CONF_MIN_ON: Final = "min_on_minutes"
CONF_MIN_OFF: Final = "min_off_minutes"
CONF_LOCK_ENTITIES: Final = "lock_entities"
CONF_LOCK_MODE: Final = "lock_mode"
CONF_FROST_TEMPERATURE: Final = "frost_temperature"
CONF_CORRECTION: Final = "correction"
CONF_REGULATION: Final = "regulation"
CONF_EXTERNAL_TEMPERATURE_ENTITIES: Final = "external_temperature_entities"
CONF_DEFAULT_TARGET: Final = "default_target"
CONF_MIN_TEMP: Final = "min_temp"
CONF_MAX_TEMP: Final = "max_temp"
CONF_HUMIDITY_THRESHOLD: Final = "humidity_threshold"
CONF_OBSERVE_ONLY: Final = "observe_only"

LOCK_MODE_OFF: Final = "off"
LOCK_MODE_FROST: Final = "frost"
REGULATION_SETPOINT: Final = "setpoint"
REGULATION_OFFSET: Final = "offset"
REGULATION_TWO_POINT: Final = "two_point"
TRV_MANUAL_ADOPT: Final = "adopt"
TRV_MANUAL_RESET: Final = "reset"

DEFAULT_WINDOW_OPEN_DELAY: Final = 30
DEFAULT_WINDOW_CLOSE_DELAY: Final = 10
DEFAULT_FROST_TEMPERATURE: Final = 7.0
DEFAULT_TARGET: Final = 20.0
DEFAULT_MIN_TEMP: Final = 5.0
DEFAULT_MAX_TEMP: Final = 30.0
DEFAULT_HUMIDITY_THRESHOLD: Final = 60
DEFAULT_HYSTERESIS_LOW: Final = 0.5
DEFAULT_HYSTERESIS_HIGH: Final = 0.0
DEFAULT_HEAT_SETPOINT: Final = 24.0
DEFAULT_MIN_ON: Final = 0
DEFAULT_MIN_OFF: Final = 0

# --- Control timing ------------------------------------------------------
DEBOUNCE_SECONDS: Final = 10.0
# Safety net: re-check pending commands (lost radio commands, start-up races).
RESYNC_MINUTES: Final = 5
EXTERNAL_TEMPERATURE_INTERVAL_MIN: Final = 30
EXTERNAL_TEMPERATURE_MIN_DELTA: Final = 0.1
TRV_UNAVAILABLE_EVENT_MINUTES: Final = 5
OFFSET_LIMIT: Final = 5.0
HEATING_HYSTERESIS: Final = 0.2

# --- Status values -------------------------------------------------------
STATUS_OFF: Final = "off"
STATUS_UNAVAILABLE: Final = "unavailable"
STATUS_WINDOW: Final = "window"
STATUS_SEASON: Final = "season"
STATUS_SUMMER: Final = "summer"
STATUS_LOCKED: Final = "locked"
STATUS_MANUAL: Final = "manual"
STATUS_HEATING: Final = "heating"
STATUS_REACHED: Final = "reached"

MANUAL_UNTIL_NEXT: Final = "until_next"
MANUAL_DURATION: Final = "duration"
