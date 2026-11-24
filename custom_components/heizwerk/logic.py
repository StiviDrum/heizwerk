"""Pure control logic of Heizwerk (no Home Assistant objects, easy to test).

The room controller collects inputs into :class:`RoomInputs`; :func:`decide`
turns them into a :class:`Decision` (status, effective target, TRV commands).
See docs/SPEC.md section 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from .const import (
    HEATING_HYSTERESIS,
    LOCK_MODE_FROST,
    OFFSET_LIMIT,
    REGULATION_OFFSET,
    REGULATION_TWO_POINT,
    STATUS_HEATING,
    STATUS_LOCKED,
    STATUS_MANUAL,
    STATUS_OFF,
    STATUS_REACHED,
    STATUS_SEASON,
    STATUS_SUMMER,
    STATUS_UNAVAILABLE,
    STATUS_WINDOW,
)

HVAC_OFF = "off"
HVAC_HEAT = "heat"

# Lock types in priority order (first wins for the status).
LOCK_WINDOW = "window"
LOCK_SEASON = "season"
LOCK_SUMMER = "summer"
LOCK_ENTITY = "entity"
_LOCK_STATUS = {
    LOCK_WINDOW: STATUS_WINDOW,
    LOCK_SEASON: STATUS_SEASON,
    LOCK_SUMMER: STATUS_SUMMER,
    LOCK_ENTITY: STATUS_LOCKED,
}
_LOCK_ORDER = list(_LOCK_STATUS)

MOLD_OK = "ok"
MOLD_WARNING = "warning"
MOLD_ALARM = "alarm"
MOLD_WARNING_PCT = 70.0
MOLD_ALARM_PCT = 80.0

# Magnus formula constants over water (Sonntag 1990).
_MAGNUS_A = 17.62
_MAGNUS_B = 243.12


# --- Room climate ----------------------------------------------------------


def saturation_pressure(temperature: float) -> float:
    """Saturation vapour pressure in hPa (Magnus)."""
    return 6.112 * math.exp(_MAGNUS_A * temperature / (_MAGNUS_B + temperature))


def dew_point(temperature: float | None, humidity: float | None) -> float | None:
    """Dew point in °C, or None if an input is missing/invalid."""
    if temperature is None or humidity is None or not 0 < humidity <= 100:
        return None
    gamma = math.log(humidity / 100) + _MAGNUS_A * temperature / (
        _MAGNUS_B + temperature
    )
    return round(_MAGNUS_B * gamma / (_MAGNUS_A - gamma), 1)


def surface_humidity(dew: float | None, surface: float | None) -> float | None:
    """Relative humidity at a (colder) surface, in %, capped at 100."""
    if dew is None or surface is None:
        return None
    value = 100 * saturation_pressure(dew) / saturation_pressure(surface)
    return round(min(value, 100.0), 0)


def mold_level(wall_humidity: float | None) -> str | None:
    """Mold risk level from the relative humidity at the wall."""
    if wall_humidity is None:
        return None
    if wall_humidity >= MOLD_ALARM_PCT:
        return MOLD_ALARM
    if wall_humidity >= MOLD_WARNING_PCT:
        return MOLD_WARNING
    return MOLD_OK


def ventilation_minutes(outdoor: float | None) -> int:
    """Recommended airing time by outdoor temperature."""
    if outdoor is None:
        return 10
    for limit, minutes in ((0, 5), (10, 10), (15, 15), (20, 20)):
        if outdoor < limit:
            return minutes
    return 25


def ventilation_recommended(
    humidity: float | None,
    threshold: float,
    indoor_dew: float | None,
    outdoor_dew: float | None,
    window_open: bool,
) -> bool:
    """Whether airing would lower the humidity (and the window is closed)."""
    if window_open or humidity is None or humidity < threshold:
        return False
    if outdoor_dew is None or indoor_dew is None:
        return True
    return outdoor_dew <= indoor_dew - 1.0


# --- Control ---------------------------------------------------------------


@dataclass(slots=True)
class TrvInfo:
    """Current state of one thermostat."""

    entity_id: str
    available: bool = True
    hvac_mode: str | None = None
    hvac_modes: list[str] = field(default_factory=list)
    setpoint: float | None = None
    current: float | None = None
    hvac_action: str | None = None
    min_temp: float = 4.0
    max_temp: float = 35.0
    step: float = 0.5


@dataclass(slots=True)
class RoomInputs:
    """Everything the decision needs, already parsed."""

    enabled: bool
    target: float
    room_temperature: float | None
    trvs: list[TrvInfo]
    locks: list[str]
    manual: bool = False
    correction: float = 0.0
    regulation: str = "setpoint"
    lock_mode: str = "off"
    frost_temperature: float = 7.0
    # Two-point regulation (valve fully open at heat_setpoint, or off).
    hysteresis_low: float = 0.5
    hysteresis_high: float = 0.0
    heat_setpoint: float = 24.0
    two_point_on: bool = False
    # Minimum run / pause of the valve (seconds, 0 = off) and time since the
    # last two-point switch (None = unknown, e.g. right after start).
    min_on_seconds: float = 0.0
    min_off_seconds: float = 0.0
    two_point_elapsed: float | None = None


@dataclass(slots=True)
class Command:
    """Target state for one thermostat."""

    entity_id: str
    hvac_mode: str
    temperature: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialise for attributes/diagnostics."""
        data: dict[str, Any] = {
            "entity_id": self.entity_id,
            "hvac_mode": self.hvac_mode,
        }
        if self.temperature is not None:
            data["temperature"] = self.temperature
        return data


@dataclass(slots=True)
class Decision:
    """Result of one evaluation."""

    status: str
    target: float
    heating: bool
    commands: list[Command]
    two_point_on: bool = False


def round_to_step(value: float, step: float) -> float:
    """Round to the thermostat's step (half up)."""
    if step <= 0:
        return round(value, 1)
    return round(math.floor(value / step + 0.5) * step, 2)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def heat_mode(trv: TrvInfo) -> str:
    """Mode used to heat: 'heat' if offered, else the first non-off mode."""
    if not trv.hvac_modes or HVAC_HEAT in trv.hvac_modes:
        return HVAC_HEAT
    return next((m for m in trv.hvac_modes if m != HVAC_OFF), HVAC_HEAT)


def trv_setpoint(inputs: RoomInputs, trv: TrvInfo) -> float:
    """Set-point to send to one thermostat for the effective target."""
    value = inputs.target + inputs.correction
    if (
        inputs.regulation == REGULATION_OFFSET
        and trv.current is not None
        and inputs.room_temperature is not None
    ):
        value += _clamp(
            trv.current - inputs.room_temperature, -OFFSET_LIMIT, OFFSET_LIMIT
        )
    return _clamp(round_to_step(value, trv.step), trv.min_temp, trv.max_temp)


def lock_status(locks: list[str]) -> str | None:
    """Status of the highest-priority active lock."""
    for lock in _LOCK_ORDER:
        if lock in locks:
            return _LOCK_STATUS[lock]
    return None


def decide(inputs: RoomInputs) -> Decision:
    """Status and thermostat commands for a room (SPEC 4.2 / 4.3)."""
    trvs = inputs.trvs
    reachable = [t for t in trvs if t.available]
    locked = lock_status(inputs.locks)

    def lock_commands() -> list[Command]:
        if inputs.lock_mode == LOCK_MODE_FROST:
            return [
                Command(
                    t.entity_id,
                    heat_mode(t),
                    _clamp(
                        round_to_step(inputs.frost_temperature, t.step),
                        t.min_temp,
                        t.max_temp,
                    ),
                )
                for t in reachable
            ]
        return [Command(t.entity_id, HVAC_OFF) for t in reachable]

    if not inputs.enabled:
        return Decision(
            STATUS_OFF,
            inputs.target,
            False,
            [Command(t.entity_id, HVAC_OFF) for t in reachable],
        )
    if trvs and not reachable:
        return Decision(STATUS_UNAVAILABLE, inputs.target, False, [])
    if locked is not None:
        return Decision(locked, inputs.target, False, lock_commands())

    current = inputs.room_temperature
    if inputs.regulation == REGULATION_TWO_POINT and current is not None:
        on = two_point_state(
            current,
            inputs.target,
            inputs.hysteresis_low,
            inputs.hysteresis_high,
            inputs.two_point_on,
        )
        on = hold_two_point(
            on,
            inputs.two_point_on,
            inputs.two_point_elapsed,
            inputs.min_on_seconds,
            inputs.min_off_seconds,
        )
        commands = [
            Command(
                t.entity_id,
                heat_mode(t),
                _clamp(
                    round_to_step(inputs.heat_setpoint, t.step), t.min_temp, t.max_temp
                ),
            )
            if on
            else Command(t.entity_id, HVAC_OFF)
            for t in reachable
        ]
        status = (
            STATUS_MANUAL
            if inputs.manual
            else (STATUS_HEATING if on else STATUS_REACHED)
        )
        return Decision(status, inputs.target, on, commands, two_point_on=on)

    commands = [
        Command(t.entity_id, heat_mode(t), trv_setpoint(inputs, t)) for t in reachable
    ]
    heating = any(t.hvac_action == "heating" for t in reachable) or (
        current is not None and current < inputs.target - HEATING_HYSTERESIS
    )
    if inputs.manual:
        status = STATUS_MANUAL
    else:
        status = STATUS_HEATING if heating else STATUS_REACHED
    return Decision(status, inputs.target, heating, commands)


def two_point_state(
    current: float, target: float, low: float, high: float, was_on: bool
) -> bool:
    """Hysteresis switch: on below target - low, off from target + high."""
    if current < target - low:
        return True
    if current >= target + high:
        return False
    return was_on


def hold_two_point(
    on: bool,
    was_on: bool,
    elapsed: float | None,
    min_on: float,
    min_off: float,
) -> bool:
    """Keep the valve state for its minimum run / pause time.

    Locks, "room off" and frost protection are decided before two-point
    regulation, so they always act immediately.
    """
    if on == was_on or elapsed is None:
        return on
    if was_on and elapsed < min_on:
        return True
    if not was_on and elapsed < min_off:
        return False
    return on


def room_target_from_trv(
    trv_setpoint_value: float, inputs: RoomInputs, trv: TrvInfo
) -> float:
    """Room set-point the user meant when turning the knob on a thermostat.

    Inverse of trv_setpoint(): with two-point regulation the knob value is
    taken as room set-point directly.
    """
    if inputs.regulation == REGULATION_TWO_POINT:
        return trv_setpoint_value
    value = trv_setpoint_value - inputs.correction
    if (
        inputs.regulation == REGULATION_OFFSET
        and trv.current is not None
        and inputs.room_temperature is not None
    ):
        value -= _clamp(
            trv.current - inputs.room_temperature, -OFFSET_LIMIT, OFFSET_LIMIT
        )
    return value


def pending_commands(commands: list[Command], trvs: list[TrvInfo]) -> list[Command]:
    """Commands whose target state differs from the thermostat's current state."""
    by_id = {t.entity_id: t for t in trvs}
    result = []
    for cmd in commands:
        trv = by_id.get(cmd.entity_id)
        if trv is None or not trv.available:
            continue
        if trv.hvac_mode != cmd.hvac_mode or (
            cmd.temperature is not None
            and (trv.setpoint is None or abs(trv.setpoint - cmd.temperature) > 1e-6)
        ):
            result.append(cmd)
    return result
