"""Room controller: collects inputs, decides, talks to the thermostats."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from statistics import mean
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.script import Script
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util, slugify
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
    CONF_RESUME_ACTION,
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
    DEBOUNCE_SECONDS,
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
    EVENT,
    EVENT_TRV_UNAVAILABLE,
    EVENT_VENTILATION_DONE,
    EXTERNAL_TEMPERATURE_INTERVAL_MIN,
    EXTERNAL_TEMPERATURE_MIN_DELTA,
    LOCK_MODE_OFF,
    MANUAL_DURATION,
    MANUAL_UNTIL_NEXT,
    REGULATION_SETPOINT,
    RESYNC_MINUTES,
    TRV_UNAVAILABLE_EVENT_MINUTES,
)
from .helpers import is_heizwerk_entity
from .logic import (
    HVAC_OFF,
    LOCK_ENTITY,
    LOCK_SEASON,
    LOCK_SUMMER,
    LOCK_WINDOW,
    Command,
    Decision,
    RoomInputs,
    TrvInfo,
    decide,
    dew_point,
    mold_level,
    pending_commands,
    surface_humidity,
    ventilation_minutes,
    ventilation_recommended,
)

_LOGGER = logging.getLogger(__name__)

_ACTIVE_STATES = {"on", "true", "open"}
_INVALID = {STATE_UNAVAILABLE, STATE_UNKNOWN, "", None}


def _float(value: Any) -> float | None:
    if value in _INVALID:
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass(slots=True)
class ManualOverride:
    """A set-point changed by hand (Heizwerk card / heizwerk.set_manual).

    The value itself is the room's set-point; this only remembers that it is
    manual, who set it and until when. It ends with the next value from the
    scheduler (climate.set_temperature), with "resume" or after its duration.
    """

    target: float
    mode: str
    until: datetime | None
    by: str | None = None
    resume_sent: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialise for restore data."""
        return {
            "target": self.target,
            "mode": self.mode,
            "until": _iso(self.until),
            "by": self.by,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ManualOverride | None:
        """Restore; None if the data is incomplete or from the 0.2/0.3 model."""
        if data.get("zeitwerk"):
            return None
        try:
            until = data.get("until")
            return cls(
                target=float(data["target"]),
                mode=str(data["mode"]),
                until=dt_util.parse_datetime(until) if until else None,
                by=data.get("by"),
            )
        except KeyError, TypeError, ValueError:
            return None


class RoomController:
    """Runtime state and control loop of one room (one config subentry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        subentry_id: str,
        room: Mapping[str, Any],
        hub: Mapping[str, Any],
    ) -> None:
        """Store configuration; nothing is tracked until async_start."""
        self.hass = hass
        self.subentry_id = subentry_id
        self.config = dict(room)
        self.hub_config = dict(hub)
        self.name: str = room[CONF_NAME]
        self.slug = slugify(self.name)
        # Never follow / control Heizwerk's own entities (endless loop).
        self.ignored_entities: list[str] = [
            e
            for e in room.get(CONF_TRVS, [])
            if is_heizwerk_entity(hass, e)
            or e == f"climate.heizwerk_{slugify(room[CONF_NAME])}"
        ]
        self.trv_ids: list[str] = [
            e for e in room.get(CONF_TRVS, []) if e not in self.ignored_entities
        ]
        self.window_ids: list[str] = list(room.get(CONF_WINDOWS, []))
        self.lock_ids: list[str] = list(room.get(CONF_LOCK_ENTITIES, []))
        self.external_ids: list[str] = list(
            room.get(CONF_EXTERNAL_TEMPERATURE_ENTITIES, [])
        )
        if self.ignored_entities:
            _LOGGER.warning(
                "%s: ignoring Heizwerk's own entities %s as thermostats "
                "(Heizwerk would control itself)",
                room.get(CONF_NAME),
                self.ignored_entities,
            )
        # Up to 0.3 a room could follow a "Zeitwerk target" entity. Since 0.4
        # the scheduler writes climate.set_temperature to the room directly;
        # an old value is ignored (repair issue, see __init__.py).
        self.legacy_target: str | None = room.get(CONF_TARGET_ENTITY) or None
        self.plan: str | None = room.get(CONF_ZEITWERK_PLAN) or None
        self.resume_action: list[dict[str, Any]] = list(
            room.get(CONF_RESUME_ACTION) or []
        )
        self.min_temp = float(room.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
        self.max_temp = float(room.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))
        self.observe_only: bool = bool(room.get(CONF_OBSERVE_ONLY, True))
        # Updated by the climate entity once added (may differ after a rename).
        self.climate_entity_id = f"climate.heizwerk_{self.slug}"

        # Runtime state (restored by the climate entity).
        self.enabled = True
        self.base_target = float(room.get(CONF_DEFAULT_TARGET, DEFAULT_TARGET))
        self.manual: ManualOverride | None = None

        # Derived state.
        self.decision: Decision | None = None
        self.planned: list[Command] = []
        self.last_sync: datetime | None = None
        self.window_open_since: datetime | None = None
        self.window_closed_since: datetime | None = None
        self.summer_since: datetime | None = None
        self.trv_unavailable_since: datetime | None = None
        self.trv_event_sent = False
        self.ventilation_event_sent = False
        self.external_last_value: float | None = None
        self.external_last_time: datetime | None = None
        self.attributes: dict[str, Any] = {}
        self.values: dict[str, Any] = {}

        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._wakeup: CALLBACK_TYPE | None = None
        self._debounce: CALLBACK_TYPE | None = None
        self._started = False
        self._sending = False
        self._tracker: CALLBACK_TYPE | None = None

    # --- Configuration helpers --------------------------------------------

    @property
    def zeitwerk_profile_entity(self) -> str | None:
        """Entity id of the Zeitwerk profile sensor of the plan."""
        return f"sensor.zeitwerk_{self.plan}_profile" if self.plan else None

    @property
    def zeitwerk_next_entity(self) -> str | None:
        """Entity id of the Zeitwerk next-change sensor of the plan."""
        return f"sensor.zeitwerk_{self.plan}_next_change" if self.plan else None

    def tracked_entities(self) -> list[str]:
        """All entities whose changes trigger a re-evaluation."""
        ids = [
            *self.trv_ids,
            *self.window_ids,
            *self.lock_ids,
            self.config.get(CONF_TEMPERATURE_SENSOR),
            self.config.get(CONF_HUMIDITY_SENSOR),
            self.config.get(CONF_WALL_TEMPERATURE_SENSOR),
            self.hub_config.get(CONF_OUTDOOR_TEMPERATURE),
            self.hub_config.get(CONF_OUTDOOR_HUMIDITY),
            self.hub_config.get(CONF_SEASON_ENTITY),
            self.zeitwerk_profile_entity,
            self.zeitwerk_next_entity,
        ]
        return sorted({i for i in ids if i})

    # --- Lifecycle ----------------------------------------------------------

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Register an entity update callback."""
        self._listeners.append(update)

        @callback
        def remove() -> None:
            self._listeners.remove(update)

        return remove

    @callback
    def async_restore(self, data: Mapping[str, Any]) -> None:
        """Restore runtime state saved by the climate entity."""
        self.enabled = bool(data.get("enabled", True))
        if (base := _float(data.get("base_target"))) is not None:
            self.base_target = base
        if manual := data.get("manual"):
            self.manual = ManualOverride.from_dict(manual)

    def restore_data(self) -> dict[str, Any]:
        """Runtime state to persist across restarts."""
        return {
            "enabled": self.enabled,
            "base_target": self.base_target,
            "manual": self.manual.as_dict() if self.manual else None,
        }

    @callback
    def async_start(self) -> None:
        """Start tracking (after the entities restored their state)."""
        if self._started:
            return
        self._started = True
        self._subscribe()
        now = dt_util.utcnow()
        if self._is_window_open():
            # Open since before the start: count from now, lock immediately.
            self.window_open_since = now - timedelta(seconds=self._window_open_delay)
        self.async_update()
        # Thermostats may restore their own state late during start-up.
        self._unsubs.append(async_at_started(self.hass, self._async_hass_started))

    @callback
    def _async_hass_started(self, _hass: HomeAssistant) -> None:
        self.async_update()
        if not self.plan:
            self.hass.async_create_task(
                self._async_detect_plan(), f"heizwerk detect plan {self.name}"
            )

    def _subscribe(self) -> None:
        if self._tracker:
            self._tracker()
        self._tracker = async_track_state_change_event(
            self.hass, self.tracked_entities(), self._async_state_changed
        )

    async def _async_detect_plan(self) -> None:
        """Find the Zeitwerk plan that writes this room (for display only)."""
        from .config_flow import async_detect_plan  # noqa: PLC0415

        plan = await async_detect_plan(self.hass, self.climate_entity_id)
        if plan and self._started:
            _LOGGER.debug("%s: Zeitwerk plan %s detected", self.name, plan)
            self.plan = plan
            self._subscribe()
            self.async_update()

    @callback
    def async_stop(self) -> None:
        """Remove all listeners and timers."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._tracker:
            self._tracker()
            self._tracker = None
        self._cancel_wakeup()
        if self._debounce:
            self._debounce()
            self._debounce = None
        self._started = False

    # --- Inputs ---------------------------------------------------------------

    def _state(self, entity_id: str | None) -> State | None:
        return self.hass.states.get(entity_id) if entity_id else None

    def _number(self, entity_id: str | None) -> float | None:
        state = self._state(entity_id)
        return _float(state.state) if state else None

    def _active(self, entity_id: str) -> bool:
        state = self._state(entity_id)
        return state is not None and str(state.state).lower() in _ACTIVE_STATES

    def _is_window_open(self) -> bool:
        return any(self._active(w) for w in self.window_ids)

    @property
    def _window_open_delay(self) -> float:
        return float(self.config.get(CONF_WINDOW_OPEN_DELAY, DEFAULT_WINDOW_OPEN_DELAY))

    @property
    def _window_close_delay(self) -> float:
        return float(
            self.config.get(CONF_WINDOW_CLOSE_DELAY, DEFAULT_WINDOW_CLOSE_DELAY)
        )

    def _trv_infos(self) -> list[TrvInfo]:
        infos = []
        for entity_id in self.trv_ids:
            state = self._state(entity_id)
            if state is None or state.state in _INVALID:
                infos.append(TrvInfo(entity_id, available=False))
                continue
            attrs = state.attributes
            infos.append(
                TrvInfo(
                    entity_id,
                    available=True,
                    hvac_mode=state.state,
                    hvac_modes=list(attrs.get(ATTR_HVAC_MODES) or []),
                    setpoint=_float(attrs.get(ATTR_TEMPERATURE)),
                    current=_float(attrs.get(ATTR_CURRENT_TEMPERATURE)),
                    hvac_action=attrs.get(ATTR_HVAC_ACTION),
                    min_temp=_float(attrs.get(ATTR_MIN_TEMP)) or 4.0,
                    max_temp=_float(attrs.get(ATTR_MAX_TEMP)) or 35.0,
                    step=_float(attrs.get(ATTR_TARGET_TEMP_STEP)) or 0.5,
                )
            )
        return infos

    def _clamp(self, value: float) -> float:
        return max(self.min_temp, min(self.max_temp, value))

    # --- Set-point, manual override, resume -----------------------------------

    def zeitwerk_manual(self) -> tuple[bool, datetime | None]:
        """Whether Zeitwerk reports a manual override of the plan, and its end."""
        state = self._state(self.zeitwerk_profile_entity)
        if state is None or not state.attributes.get("manual_override"):
            return False, None
        until = state.attributes.get("manual_until")
        return True, dt_util.parse_datetime(until) if until else None

    @property
    def resume_actions(self) -> list[dict[str, Any]]:
        """Configured resume action, else zeitwerk.resume for the known plan."""
        if self.resume_action:
            return self.resume_action
        if self.plan:
            return [{"action": "zeitwerk.resume", "data": {"plan": [self.plan]}}]
        return []

    @property
    def resume_available(self) -> bool:
        """Whether "resume" can reload a plan."""
        return bool(self.resume_actions)

    def set_target(self, temperature: float) -> None:
        """climate.set_temperature: the new set-point (scheduler, automation …).

        Ends a manual override: the scheduler delivered its next value.
        """
        self.base_target = self._clamp(temperature)
        self.manual = None
        self.async_update()

    def set_manual(
        self,
        temperature: float,
        duration: timedelta | None,
        user_name: str | None = None,
    ) -> None:
        """Set the set-point by hand (Heizwerk card, heizwerk.set_manual)."""
        now = dt_util.utcnow()
        self.base_target = self._clamp(temperature)
        if duration is not None and self.resume_available:
            mode, until = MANUAL_DURATION, now + duration
        else:
            # Without a resume action a duration could not restore anything.
            mode, until = MANUAL_UNTIL_NEXT, None
        self.manual = ManualOverride(self.base_target, mode, until, user_name)
        self.enabled = True
        self.async_update()

    async def async_resume(self) -> None:
        """End a manual override and reload the plan (resume action)."""
        self.manual = None
        self.async_update()
        await self._async_run_resume()

    async def _async_run_resume(self) -> None:
        actions = self.resume_actions
        if not actions:
            return
        try:
            script = Script(
                self.hass,
                cv.SCRIPT_SCHEMA(actions),
                f"Heizwerk {self.name} resume",
                DOMAIN,
            )
            await script.async_run(context=Context())
        except (HomeAssistantError, vol.Invalid) as err:
            _LOGGER.warning("%s: resume action failed: %s", self.name, err)

    def set_enabled(self, enabled: bool) -> None:
        """hvac_mode heat/off of the room."""
        self.enabled = enabled
        self.async_update()

    async def async_sync(self) -> None:
        """Re-evaluate and send pending commands immediately."""
        self.async_update(debounce=False)
        await self._async_send()

    # --- Evaluation -------------------------------------------------------

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        now = dt_util.utcnow()
        if entity_id in self.window_ids:
            if self._is_window_open():
                if self.window_open_since is None:
                    self.window_open_since = now
                    self.ventilation_event_sent = False
                self.window_closed_since = None
            elif (
                self.window_open_since is not None and self.window_closed_since is None
            ):
                self.window_closed_since = now
        self.async_update()

    def _locks(self, now: datetime) -> list[str]:
        locks: list[str] = []
        # Window: locked after the open delay, released after the close delay.
        if self.window_open_since is not None:
            opened = (now - self.window_open_since).total_seconds()
            if self.window_closed_since is not None:
                closed = (now - self.window_closed_since).total_seconds()
                if closed >= self._window_close_delay:
                    self.window_open_since = None
                    self.window_closed_since = None
                elif opened - closed >= self._window_open_delay:
                    locks.append(LOCK_WINDOW)
                else:
                    # Closed again before the lock engaged.
                    self.window_open_since = None
                    self.window_closed_since = None
            elif opened >= self._window_open_delay:
                locks.append(LOCK_WINDOW)
        season = self._state(self.hub_config.get(CONF_SEASON_ENTITY))
        if season is not None and season.state == "off":
            locks.append(LOCK_SEASON)
        if self._summer_locked(now):
            locks.append(LOCK_SUMMER)
        if any(self._active(e) for e in self.lock_ids):
            locks.append(LOCK_ENTITY)
        return locks

    def _summer_locked(self, now: datetime) -> bool:
        threshold = float(
            self.hub_config.get(
                CONF_SUMMER_LOCK_TEMPERATURE, DEFAULT_SUMMER_LOCK_TEMPERATURE
            )
        )
        outdoor = self._number(self.hub_config.get(CONF_OUTDOOR_TEMPERATURE))
        if threshold <= 0 or outdoor is None or outdoor < threshold:
            self.summer_since = None
            return False
        if self.summer_since is None:
            self.summer_since = now
        minutes = float(
            self.hub_config.get(CONF_SUMMER_LOCK_MINUTES, DEFAULT_SUMMER_LOCK_MINUTES)
        )
        return now - self.summer_since >= timedelta(minutes=minutes)

    def _expire_manual(self, now: datetime) -> None:
        manual = self.manual
        if manual is None or manual.until is None or now < manual.until:
            return
        if manual.resume_sent:
            return
        manual.resume_sent = True
        self.manual = None
        self.hass.async_create_task(
            self._async_run_resume(), f"heizwerk resume {self.name}"
        )

    def _room_temperature(self, trvs: list[TrvInfo]) -> tuple[float | None, str]:
        sensor = self._number(self.config.get(CONF_TEMPERATURE_SENSOR))
        if sensor is not None:
            return sensor, "sensor"
        values = [t.current for t in trvs if t.available and t.current is not None]
        return (round(mean(values), 1), "trv") if values else (None, "trv")

    @callback
    def async_update(self, debounce: bool = True) -> None:
        """Recompute everything, notify entities, schedule commands/timers."""
        now = dt_util.utcnow()
        trvs = self._trv_infos()
        self._expire_manual(now)
        target = self.base_target
        zeitwerk_manual, _ = self.zeitwerk_manual()
        manual_active = self.manual is not None or zeitwerk_manual
        current, source = self._room_temperature(trvs)
        locks = self._locks(now)

        decision = decide(
            RoomInputs(
                enabled=self.enabled,
                target=self._clamp(target),
                room_temperature=current,
                trvs=trvs,
                locks=locks,
                manual=manual_active,
                correction=float(self.config.get(CONF_CORRECTION, 0.0)),
                regulation=self.config.get(CONF_REGULATION, REGULATION_SETPOINT),
                lock_mode=self.config.get(CONF_LOCK_MODE, LOCK_MODE_OFF),
                frost_temperature=float(
                    self.config.get(CONF_FROST_TEMPERATURE, DEFAULT_FROST_TEMPERATURE)
                ),
            )
        )
        changed = [c.as_dict() for c in decision.commands] != [
            c.as_dict() for c in self.planned
        ]
        if self.observe_only and (self.decision is None or changed):
            self.last_sync = now
        self.decision = decision
        self.planned = decision.commands

        self._update_trv_availability(now, trvs)
        self._update_climate(now, current, source, trvs, locks)
        self._push_external(now, current, source)

        pending = pending_commands(decision.commands, trvs)
        _LOGGER.debug(
            "%s: status=%s pending=%s debounce=%s trvs=%s",
            self.name,
            decision.status,
            [c.as_dict() for c in pending],
            self._debounce is not None,
            [(t.entity_id, t.available, t.hvac_mode, t.setpoint) for t in trvs],
        )
        if (
            debounce
            and self._debounce is None
            and not self._sending
            and not self.observe_only
            and pending
        ):
            self._debounce = async_call_later(
                self.hass, DEBOUNCE_SECONDS, self._async_debounced
            )
        self._schedule_wakeup(now)
        for update in list(self._listeners):
            update()

    async def _async_debounced(self, _now: datetime) -> None:
        self._debounce = None
        self.async_update(debounce=False)
        await self._async_send()

    async def _async_send(self) -> None:
        """Send commands that differ from the thermostats' state."""
        if self.observe_only or self.decision is None:
            return
        pending = pending_commands(self.decision.commands, self._trv_infos())
        if not pending:
            return
        context = Context()
        trvs = {t.entity_id: t for t in self._trv_infos()}
        self._sending = True
        try:
            await self._async_send_commands(pending, trvs, context)
        finally:
            self._sending = False
        _LOGGER.debug("%s: sent %s", self.name, [c.as_dict() for c in pending])
        self.last_sync = dt_util.utcnow()
        self.async_update(debounce=False)

    async def _async_send_commands(
        self, pending: list[Command], trvs: dict[str, TrvInfo], context: Context
    ) -> None:
        for cmd in pending:
            trv = trvs[cmd.entity_id]
            try:
                if trv.hvac_mode != cmd.hvac_mode:
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {ATTR_ENTITY_ID: cmd.entity_id, "hvac_mode": cmd.hvac_mode},
                        blocking=True,
                        context=context,
                    )
                if cmd.hvac_mode != HVAC_OFF and cmd.temperature is not None:
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {
                            ATTR_ENTITY_ID: cmd.entity_id,
                            ATTR_TEMPERATURE: cmd.temperature,
                        },
                        blocking=True,
                        context=context,
                    )
            except HomeAssistantError as err:
                _LOGGER.warning(
                    "%s: command to %s failed: %s", self.name, cmd.entity_id, err
                )

    def _push_external(self, now: datetime, current: float | None, source: str) -> None:
        """Send the room temperature to the thermostats' external input."""
        if (
            self.observe_only
            or not self.external_ids
            or current is None
            or source != "sensor"
        ):
            return
        due = (
            self.external_last_time is None
            or now - self.external_last_time
            >= timedelta(minutes=EXTERNAL_TEMPERATURE_INTERVAL_MIN)
        )
        changed = (
            self.external_last_value is None
            or abs(current - self.external_last_value) >= EXTERNAL_TEMPERATURE_MIN_DELTA
        )
        if not (due or changed):
            return
        self.external_last_value = current
        self.external_last_time = now
        for entity_id in self.external_ids:
            domain = entity_id.split(".", 1)[0]
            self.hass.async_create_task(
                self.hass.services.async_call(
                    domain,
                    "set_value",
                    {ATTR_ENTITY_ID: entity_id, "value": current},
                    blocking=False,
                ),
                f"heizwerk external temperature {entity_id}",
            )
        self.last_sync = now

    def _update_trv_availability(self, now: datetime, trvs: list[TrvInfo]) -> None:
        if any(not t.available for t in trvs):
            if self.trv_unavailable_since is None:
                self.trv_unavailable_since = now
                self.trv_event_sent = False
            if (
                not self.trv_event_sent
                and now - self.trv_unavailable_since
                >= timedelta(minutes=TRV_UNAVAILABLE_EVENT_MINUTES)
            ):
                self.trv_event_sent = True
                self._fire(
                    EVENT_TRV_UNAVAILABLE,
                    trvs=[t.entity_id for t in trvs if not t.available],
                )
        else:
            self.trv_unavailable_since = None
            self.trv_event_sent = False

    def _fire(self, event_type: str, **data: Any) -> None:
        self.hass.bus.async_fire(
            EVENT,
            {
                "type": event_type,
                "room": self.name,
                "entity_id": self.climate_entity_id,
                **data,
            },
        )

    def _update_climate(
        self,
        now: datetime,
        current: float | None,
        source: str,
        trvs: list[TrvInfo],
        locks: list[str],
    ) -> None:
        humidity = self._number(self.config.get(CONF_HUMIDITY_SENSOR))
        wall = self._number(self.config.get(CONF_WALL_TEMPERATURE_SENSOR))
        outdoor = self._number(self.hub_config.get(CONF_OUTDOOR_TEMPERATURE))
        outdoor_humidity = self._number(self.hub_config.get(CONF_OUTDOOR_HUMIDITY))
        dew = dew_point(current, humidity)
        outdoor_dew = dew_point(outdoor, outdoor_humidity)
        wall_humidity = surface_humidity(dew, wall)
        window_open = self._is_window_open()
        minutes = ventilation_minutes(outdoor)
        open_for = (
            now - self.window_open_since
            if window_open and self.window_open_since
            else None
        )
        done = open_for is not None and open_for >= timedelta(minutes=minutes)
        if done and not self.ventilation_event_sent:
            self.ventilation_event_sent = True
            self._fire(EVENT_VENTILATION_DONE, minutes=minutes)
        threshold = float(
            self.config.get(CONF_HUMIDITY_THRESHOLD, DEFAULT_HUMIDITY_THRESHOLD)
        )
        season = self._state(self.hub_config.get(CONF_SEASON_ENTITY))
        profile = self._state(self.zeitwerk_profile_entity)
        next_state = self._state(self.zeitwerk_next_entity)
        decision = self.decision
        assert decision is not None
        lock_since = {
            LOCK_WINDOW: self.window_open_since,
            LOCK_SUMMER: self.summer_since,
        }
        self.values = {
            "current": current,
            "humidity": humidity,
            "dew_point": dew,
            "wall_humidity": wall_humidity,
            "ventilation_recommended": ventilation_recommended(
                humidity, threshold, dew, outdoor_dew, window_open
            ),
        }
        self.attributes = {
            "room_name": self.name,
            "status": decision.status,
            "locks": [
                {"type": lock, "since": _iso(lock_since.get(lock))}
                | (
                    {"entity_ids": [e for e in self.lock_ids if self._active(e)]}
                    if lock == LOCK_ENTITY
                    else {}
                )
                for lock in locks
            ],
            **self._manual_attributes(),
            "resume_available": self.resume_available,
            "ignored_entities": self.ignored_entities,
            "zeitwerk_plan": self.plan,
            "zeitwerk_profile": profile.state
            if profile and profile.state not in _INVALID
            else None,
            "zeitwerk_profile_id": profile.attributes.get("profile_id")
            if profile
            else None,
            "zeitwerk_source": profile.attributes.get("source") if profile else None,
            "next_change": next_state.state
            if next_state and next_state.state not in _INVALID
            else None,
            "next_profile": next_state.attributes.get("next_profile_name")
            if next_state
            else None,
            "temperature_source": source,
            "trvs": [
                {
                    "entity_id": t.entity_id,
                    "available": t.available,
                    "hvac_mode": t.hvac_mode,
                    "setpoint": t.setpoint,
                    "current": t.current,
                    "hvac_action": t.hvac_action,
                }
                for t in trvs
            ],
            "trv_unavailable_since": _iso(self.trv_unavailable_since),
            "planned_commands": [c.as_dict() for c in decision.commands],
            "last_sync": _iso(self.last_sync),
            "observe_only": self.observe_only,
            "window_open": window_open,
            "window_open_since": _iso(self.window_open_since) if window_open else None,
            "ventilation_minutes": minutes,
            "ventilation_done": done,
            "ventilation_recommended": self.values["ventilation_recommended"],
            "dew_point": dew,
            "wall_temperature": wall,
            "wall_humidity": wall_humidity,
            "mold_level": mold_level(wall_humidity),
            "outdoor_temperature": outdoor,
            "outdoor_dew_point": outdoor_dew,
            "season_active": None if season is None else season.state != "off",
            "humidity_threshold": threshold,
        }

    def _manual_attributes(self) -> dict[str, Any]:
        """manual_* attributes, also for overrides Zeitwerk detected itself."""
        zeitwerk_active, zeitwerk_until = self.zeitwerk_manual()
        manual = self.manual
        if manual is not None:
            until = manual.until
            if until is None and zeitwerk_active:
                until = zeitwerk_until
            return {
                "manual_target": manual.target,
                "manual_mode": manual.mode,
                "manual_until": _iso(until),
                "manual_by": manual.by,
            }
        if zeitwerk_active:
            # Changed outside the Heizwerk card (more-info dialog, voice …).
            return {
                "manual_target": self.base_target,
                "manual_mode": MANUAL_UNTIL_NEXT,
                "manual_until": _iso(zeitwerk_until),
                "manual_by": None,
            }
        return {
            "manual_target": None,
            "manual_mode": None,
            "manual_until": None,
            "manual_by": None,
        }

    # --- Timers ---------------------------------------------------------------

    def _cancel_wakeup(self) -> None:
        if self._wakeup:
            self._wakeup()
            self._wakeup = None

    def _schedule_wakeup(self, now: datetime) -> None:
        """One timer on the earliest time-based change (delays, expiry, events)."""
        self._cancel_wakeup()
        if not self._started:
            return
        candidates: list[datetime] = []
        if self.window_open_since is not None:
            candidates.append(
                self.window_open_since + timedelta(seconds=self._window_open_delay)
            )
            if self._is_window_open() and not self.ventilation_event_sent:
                outdoor = self._number(self.hub_config.get(CONF_OUTDOOR_TEMPERATURE))
                candidates.append(
                    self.window_open_since
                    + timedelta(minutes=ventilation_minutes(outdoor))
                )
        if self.window_closed_since is not None:
            candidates.append(
                self.window_closed_since + timedelta(seconds=self._window_close_delay)
            )
        if self.summer_since is not None:
            minutes = float(
                self.hub_config.get(
                    CONF_SUMMER_LOCK_MINUTES, DEFAULT_SUMMER_LOCK_MINUTES
                )
            )
            candidates.append(self.summer_since + timedelta(minutes=minutes))
        if self.manual is not None and self.manual.until is not None:
            candidates.append(self.manual.until)
        if self.trv_unavailable_since is not None and not self.trv_event_sent:
            candidates.append(
                self.trv_unavailable_since
                + timedelta(minutes=TRV_UNAVAILABLE_EVENT_MINUTES)
            )
        if self.external_ids and self.external_last_time is not None:
            candidates.append(
                self.external_last_time
                + timedelta(minutes=EXTERNAL_TEMPERATURE_INTERVAL_MIN)
            )
        if (
            not self.observe_only
            and self.decision is not None
            and pending_commands(self.decision.commands, self._trv_infos())
        ):
            candidates.append(now + timedelta(minutes=RESYNC_MINUTES))
        future = [c for c in candidates if c > now]
        if not future:
            return
        self._wakeup = async_track_point_in_utc_time(
            self.hass, self._async_wakeup, min(future) + timedelta(milliseconds=50)
        )

    @callback
    def _async_wakeup(self, _now: datetime) -> None:
        self._wakeup = None
        self.async_update()

    def diagnostics(self) -> dict[str, Any]:
        """Snapshot for the diagnostics download."""
        return {
            "name": self.name,
            "config": self.config,
            "runtime": self.restore_data(),
            "attributes": self.attributes,
        }
