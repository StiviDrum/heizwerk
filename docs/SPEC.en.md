# Heizwerk – Specification

> English (translation) · [Deutsch](SPEC.md) – the German version is the source
> of truth; if the two differ, the German version applies.
>
> Language of the project: German. Code, comments, identifiers, commits: English.
> As of: version 0.5.2 (2026-11-24) · Minimum Home Assistant version **2026.11**

## 1. Idea

**Zeitwerk plans, Heizwerk controls.** A scheduler (Zeitwerk, Scheduler,
automation) decides *which* set-point applies right now and sets it via
`climate.set_temperature`. Heizwerk applies it per room to the radiator
thermostats (TRVs) and takes care of everything between "the set-point is
decided" and "the valve opens":

- external room sensor instead of the TRV's own reading, room temperature sent
  to the TRVs
- regulation mode set-point (TRV regulates itself), two-point (valve open/closed)
  or offset
- **locks**: window open, heating period off, summer lock (house value,
  overridable per room), freely chosen lock entities
- manual override (card, service, knob at the thermostat) with a duration,
  "Resume" via a freely chosen action
- protection against wrong thermostat reports (stale values, jumps, commands a
  thermostat does not take over)
- room climate: humidity, dew point, wall humidity or mold indicator, airing
- **observe-only**: Heizwerk computes everything but sends nothing to the TRVs

Goal from 0.5 on: being able to fully replace the previous heating automations.

Scope: Heizwerk does not plan (no weekly schedule, no profiles) – that stays
Zeitwerk. Heizwerk does not remind (no push chains) – that stays Läutwerk.

## 2. Interfaces to Zeitwerk and Läutwerk (read on 2026-11-18)

Source: repositories `~/zeitwerk` (1.0.0-rc.11) and `~/laeutwerk` (0.11.4),
checked against the installed Zeitwerk instance (read-only). Heizwerk uses
**only public interfaces** (states, attributes, WebSocket, services), no
internals.

### 2.1 Scheduler → Heizwerk (from 0.4, decision Steven 2026-11-18)

**Heizwerk is a plain thermostat, the scheduler is only the remote control.**

| Interface | Meaning |
|---|---|
| `climate.set_temperature` on `climate.heizwerk_<room>` | The only input: new set-point. From a Zeitwerk profile action, Scheduler, automation or by hand. Ends an override from the Heizwerk card. |
| Room option `resume_action` (HA actions) | Runs on "Resume" and at the end of an override with a duration. Empty + Zeitwerk plan known → `zeitwerk.resume {plan}`. Empty without plan → Resume/durations hidden. Scheduler: e.g. `scheduler.run_action`. |
| `sensor.zeitwerk_<plan>_profile` (`profile_id`, `source`, `manual_override`, `manual_until`), `sensor.zeitwerk_<plan>_next_change` (`next_profile_name`) | Display only: profile, "until …", and "manual" when Zeitwerk detected a change outside the card. |
| WebSocket `zeitwerk/plans/get`, `zeitwerk/preview` → `{plans: {plan_id: [...]}}` | Card: profile values (actions on `climate.heizwerk_<room>`) and day band. |
| Service `zeitwerk.get_plan` | Automatic plan detection: the plan whose profile actions set `climate.heizwerk_<room>`. From 0.5.2 also: lowest profile value of this room as the automatic lower bound for knob turns at the thermostat (4.5). |

Zeitwerk itself detects changes made with the Heizwerk card as a manual
override (foreign context on the watched attribute `temperature`) and ends it
with the next block. Locks (window etc.) do not change the set-point – no false
alarm in Zeitwerk. Up to 0.3 there was a "Zeitwerk target" (helper); an old
value is ignored and reported as a repair issue.

### 2.2 Heizwerk → Läutwerk and automations (loosely coupled)

Heizwerk does not call Läutwerk. Läutwerk rules or automations react to
Heizwerk states and events. Every `heizwerk_event` event contains `type`,
`room` (room name) and `entity_id` (`climate.heizwerk_<room>`):

| `type` | further fields | When | Example |
|---|---|---|---|
| `ventilation_done` | `minutes` | window open ≥ recommended airing time (once per opening) | automation → `laeutwerk.trigger` (rule "close window") |
| `trv_unavailable` | `trvs` (list) | a TRV unavailable for 5 min | reminder "check TRV" |
| `knob_adopted` (from 0.5.2) | `result`, `reason`, `trv`, `value`, `before`, `delta`, `target`, `seconds_since_command` | knob turn at the thermostat adopted as manual override | log, traceability |
| `knob_rejected` (from 0.5.2) | as above; `reason` = `after_own_command`, `stale_value`, `two_point`, `reset_mode`, `jump` or `below_minimum`; `target` empty | set-point change at the thermostat rejected, Heizwerk sends its own value again | troubleshooting thermostats |

Field meaning for `knob_*`: `trv` = thermostat, `value` = reported set-point,
`before` = set-point before, `delta` = `value − before` (K), `target` = adopted
room set-point, `seconds_since_command` = seconds since the last own command to
this thermostat (empty if none is known), `result` = `adopted`/`rejected`.

Also: `binary_sensor.heizwerk_<room>_ventilation` (airing recommended) –
opportunity/acknowledgement via the window contact.

Läutwerk services for reference: `laeutwerk.trigger` {rule}, `acknowledge`,
`snooze`, `get_rules`.

## 3. Data model

### 3.1 Integration entry (single, options changeable)

| Option | Meaning | Default | Range |
|---|---|---|---|
| `outdoor_temperature` | outdoor temperature sensor (`sensor`, `input_number`; no `weather` entities) | – | – |
| `outdoor_humidity` | outdoor humidity (for the outdoor dew point) | – | – |
| `season_entity` | heating period (`off` = locked; `input_boolean`, `binary_sensor`, `switch`, `schedule`) | – | – |
| `summer_lock_temperature` | summer lock from … °C (0 = off) | 16 | 0–30 |
| `summer_lock_minutes` | … when exceeded for this long (min) | 10 | 0–240 |

### 3.2 Room (config subentry `room`, via "Add room")

Dialog: name, thermostats, room sensor, observe-only on top; collapsed sections
below. Choice fields are dropdowns (HA 2026.11 draws radio dots off-centre).
Fields appear only when they have an effect (HA visibility conditions); a hidden
field keeps its stored value or the default on save. Data is stored flat (keys
as below).

| Section | Option | Meaning | Default | Range |
|---|---|---|---|---|
| top | `name` | room name → `climate.heizwerk_<slug>` | – | – |
| top | `trvs` | thermostats (`climate`, several; Heizwerk entities cannot be selected) | – | – |
| top | `temperature_sensor` | room sensor; without: mean of the TRV readings | – | – |
| top | `observe_only` | **observe-only** | **on** | – |
| Schedule & resume | `zeitwerk_plan` | plan for display; detected automatically (plan that sets `climate.heizwerk_<room>`) | – | – |
| Schedule & resume | `resume_action` | HA actions for "Resume" and end of a duration; empty + plan → `zeitwerk.resume` | – | – |
| Room climate | `humidity_sensor` | humidity (dew point, airing) | – | – |
| Room climate | `mold_sensor` | mold indicator: wall humidity in % directly | – | – |
| Room climate | `wall_temperature_sensor` | wall surface °C/°F (only without `mold_sensor`) | – | – |
| Room climate | `humidity_threshold` | airing recommended from % | 60 | 30–95 |
| Windows & locks | `windows`, `window_open_delay`, `window_close_delay` | windows, seconds until lock / release | – / 30 / 10 | 0–900 s |
| Windows & locks | `lock_entities` | further locks (`on`/`true`/`open` locks) | – | – |
| Windows & locks | `lock_mode`, `frost_temperature` | lock = TRV `off` or heat to frost protection (frost field only with `frost`) | `off` / 7 | 4–12 °C |
| Windows & locks | `outdoor_limit` | summer lock from … °C for this room (0 = none) | house value | 0–30 |
| Regulation | `regulation` | `setpoint`, `two_point` or `offset` | `setpoint` | – |
| Regulation | `send_temperature` | send room temperature to the TRVs (only with a room sensor) | on (new rooms) | – |
| Regulation | `correction` | correction in K on the TRV set-point | 0 | −5…5 K |
| Regulation | `hysteresis_low` | two-point only: on below target − value | 0.5 | 0…3 K |
| Regulation | `hysteresis_high` | two-point only: off from target + value; negative = off already before the target | 0 | −2…3 K |
| Regulation | `heat_setpoint` | two-point only: TRV set-point while heating | 24 | 5–35 °C |
| Regulation | `min_on_minutes` (from 0.5.2) | two-point only: minimum valve run time, 0 = off | 0 | 0–60 min |
| Regulation | `min_off_minutes` (from 0.5.2) | two-point only: minimum valve pause, 0 = off | 0 | 0–60 min |
| Regulation | `trv_manual` | knob at the thermostat: `adopt` or `reset`; hidden for two-point (always reset) | `adopt` | – |
| Regulation | `knob_min_temperature` (from 0.5.2) | accept knob values from … °C; empty = automatic (lowest Zeitwerk profile value of the room, else `min_temp`); only with `adopt` and not two-point | empty | 5–25 °C |
| Set-points & limits | `default_target` | initial set-point until the first value | 20 | 5–30 °C |
| Set-points & limits | `min_temp` / `max_temp` | range | 5 / 30 | 4–30 / 5–35 °C |

Checks on save: name not empty and unique, at least one thermostat, no Heizwerk
entity as thermostat, `min_temp` < `max_temp`, `offset` not together with
`send_temperature`, two-point only with a room sensor and with
`hysteresis_low` + `hysteresis_high` ≥ 0.2 K, wall temperature sensor only in
°C/°F (no unit is accepted), valid resume action.

Legacy data: `target_entity` (up to 0.3) is ignored and reported as a repair
issue; `external_temperature_entities` (up to 0.4) stays effective as long as
`send_temperature` is on.

New rooms **always** start in observe-only mode (section 1.4 of the house rules:
heating control only with approval).

## 4. Regulation

### 4.1 Set-point

```
set-point = last received value (climate.set_temperature / heizwerk.set_manual),
            on the very first start the initial set-point (default_target)
manual    = set via the Heizwerk card / heizwerk.set_manual or the knob at the
            thermostat, until the next value from outside, "Resume" or the end
            of the duration (then resume_action); also "manual" when Zeitwerk
            reports an override
```

### 4.2 Status (priority from the top)

| Status | Condition | TRV command |
|---|---|---|
| `off` | room switched off via `hvac_mode: off` | `off` |
| `unavailable` | all TRVs `unavailable`/`unknown` | – (send nothing) |
| `window` | window open longer than `window_open_delay` | lock |
| `season` | heating period off | lock |
| `summer` | outdoor ≥ threshold for `summer_lock_minutes` | lock |
| `locked` | a lock entity is active | lock |
| `manual` | manual override active | as per regulation mode |
| `heating` | set-point: current < target − 0.2 K or TRV reports `heating`; two-point: on | set-point: heat, target · two-point: heat, `heat_setpoint` |
| `reached` | otherwise | set-point: heat, target · two-point: off |

Lock = `hvac_mode: off` (`lock_mode: off`) or heat to `frost_temperature`.
Locks and "room off" always act immediately, also during a minimum run or pause
time of two-point regulation; afterwards no hold time from before applies (after
airing the valve opens immediately).

### 4.3 Commands

- `setpoint`/`offset`: TRV set-point = effective + `correction` (+ TRV current −
  room current, ±5 K, with `offset`), rounded to the TRV's step and clamped.
- `two_point`: see 4.5.
- Debounce 10 s: changes are collected, then evaluated once.
- Only what differs from the TRV state is sent (no command flood).
- Re-check every 5 min while commands are pending; re-evaluation after HA start.
- **No sending during HA start-up (from 0.5.2)**: commands reach the thermostats
  only once Home Assistant has fully started (thermostats often restore their
  state late); the room is re-evaluated right after.
- **Retry cap (from 0.5.2)**: the same command (mode + temperature) is sent to a
  thermostat at most 3 times within 10 minutes (counted from the first send).
  After that Heizwerk pauses for this thermostat until the 10-minute window
  ends, logs a warning and raises the repair issue `trv_rejects_command`
  ("thermostat does not take over the command"). Counter and issue are cleared
  once the thermostat keeps the value for 2 minutes (a thermostat that takes the
  value briefly and jumps back right away does not reset the counter). Only
  device-side reports count (`after_own_command`, `stale_value`, `jump` – a change over 5 K is a device
  resetting itself); when Heizwerk
  rejects a knob turn by a person (`two_point`, `reset_mode`, `below_minimum`), the counter is reset and a notice removed. All
  `trv_rejects_command` notices are removed when the integration starts or
  reloads.
- External temperature: see 4.5 (`send_temperature`).
- **Observe-only**: commands are computed and shown as `planned_commands`, but
  not sent.
- `last_sync` = time of the last (sent or planned) command round.

### 4.4 Room climate

- Dew point (Magnus, a = 17.62, b = 243.12 °C) from room temperature and
  humidity; outdoor likewise.
- Wall humidity = relative humidity at the wall: 100 · E(dew point) / E(wall),
  at most 100 %. Level `ok` < 70 %, `warning` ≥ 70 %, `alarm` ≥ 80 %.
- Airing time by outdoor temperature: < 0 °C 5 min, < 10 °C 10 min,
  < 15 °C 15 min, < 20 °C 20 min, otherwise 25 min; without outdoor value 10 min.
- Window open ≥ recommended time → `ventilation_done` (event once per opening).
- Airing recommended: humidity ≥ `humidity_threshold` and (outdoor or indoor dew
  point unknown or outdoor ≥ 1 K below indoor) and window closed.

### 4.5 Thermostat functions (from 0.5)

| Function | Behaviour |
|---|---|
| Send room temperature (`send_temperature`) | Inputs `number.…_external_temperature_input` on each TRV's device (entity_id/unique_id), room sensor value on a change of ≥ 0.1 K, otherwise every 30 min. Only with a room sensor, not in observe-only. Old explicit inputs stay as long as sending is on. Without a stored key: on if old inputs exist. |
| Measuring source (`…_temperature_sensor_select`) | Repair issue `sensor_select_not_remote` after 5 min ≠ `remote_temperature` (unavailable/unknown do not count). No automatic switching. |
| Two-point (`regulation: two_point`) | on at current < target − `hysteresis_low`, off from current ≥ target + `hysteresis_high`, in between unchanged; on = heat to `heat_setpoint` (24 °C), off = off. `hysteresis_high` may be negative (−2…3 K, off already before the target, against overshoot); `hysteresis_low` + `hysteresis_high` ≥ 0.2 K. Optional minimum run/pause time (`min_on_minutes`/`min_off_minutes`, 0 = off): after a switch the valve stays on or off for that long; window, locks and room off still act immediately, and after a forced state (lock, room off, missing room temperature) no hold applies – after airing the valve opens immediately. Only with a room sensor. Valve state after a restart taken from the first available thermostat report (also during HA start-up): an available TRV that is not `off` and less than 0.6 K away from `heat_setpoint` means the valve is on. Without a room temperature the TRV gets the room target as a fallback (it regulates itself) until the sensor reports again. |
| Outdoor limit per room (`outdoor_limit`) | replaces the house value; 0 = no summer lock for the room. |
| Knob at the thermostat (`trv_manual`, `knob_min_temperature`) | A set-point change reported by a TRV is checked in this order. **Silently ignored** (no event): observe-only, Heizwerk is sending, room off, lock active, TRV just came back or unavailable before/after, TRV reports `off`, context with a parent (automation/script), set-point unchanged, value equal to the set-point Heizwerk currently wants for this thermostat (the thermostat agrees), echo of the own command (same value within 30 s). **Rejected** (`knob_rejected`, Heizwerk sends its own value again): `after_own_command` – any other report within 30 s after an own command (mode or set-point); `stale_value` – value equals the TRV's set-point before Heizwerk's last command, within 5 minutes after that command; `two_point` – always with two-point (the knob shows the heat set-point, not the room temperature); `reset_mode` – `trv_manual: reset`; `jump` – change of more than 5 K in one report; `below_minimum` – derived room set-point (before clamping to `min_temp`…`max_temp`) below the lower bound (`knob_min_temperature`, empty = lowest Zeitwerk profile value of this room, else `min_temp`). **Adopted** (`knob_adopted`): room set-point = value − `correction` (with `offset` also − (TRV current − room current), ±5 K), rounded to 0.5 K, clamped to `min_temp`…`max_temp`; if it equals the current set-point nothing happens, otherwise manual override (source `thermostat`) until the next value. Every adopted/rejected decision is logged (info), fired as `heizwerk_event` (2.2) and stored in the attribute `last_knob`. |
| Mold indicator (`mold_sensor`) | value = wall humidity (%), `estimated_critical_temp` = critical wall temperature; takes precedence over the wall temperature sensor (which only accepts °C/°F). |

Background of 0.5.2: a Zigbee2MQTT thermostat that Heizwerk switched to heat
(two-point, 30 °C) reported its previously stored set-point (e.g. 18 °C) in a
separate message 0.15–0.25 s later. 0.5.1 took that as a knob turn and kept a
manual value of 6 °C until the next schedule change. Default behaviour is
otherwise unchanged; the new options are opt-in.

## 5. Entities per room (device "Heizwerk <Room>")

| Entity | Content |
|---|---|
| `climate.heizwerk_<room>` | modes `heat`/`off`, current = room sensor, target = effective (step 0.5 K), `current_humidity`, `hvac_action` |
| `sensor.heizwerk_<room>_dew_point` | dew point (°C), only with a humidity sensor |
| `sensor.heizwerk_<room>_wall_humidity` | wall humidity (%), with mold indicator or humidity + wall sensor |
| `binary_sensor.heizwerk_<room>_ventilation` | airing recommended |
| `switch.heizwerk_<room>_observe_only` | observe-only (configuration) |

Attributes of `climate.heizwerk_<room>` (interface to the card):

`room_name`, `status`, `locks` [{type (`window`/`season`/`summer`/`entity`),
since, entity_ids (only for `entity`)}], `manual_target`, `manual_mode`
(`until_next`/`duration`), `manual_until`, `manual_by`, `manual_source`
(`heizwerk`/`thermostat`/`zeitwerk`), `resume_available`, `ignored_entities`,
`zeitwerk_plan`, `zeitwerk_profile`, `zeitwerk_profile_id`, `zeitwerk_source`,
`next_change`, `next_profile`, `temperature_source` (`sensor`/`trv`),
`trvs` [{entity_id, available, hvac_mode, setpoint, current, hvac_action}],
`trv_unavailable_since`, `planned_commands` [{entity_id, hvac_mode,
temperature?}], `last_sync`, `observe_only`, `window_open`,
`window_open_since`, `ventilation_minutes`, `ventilation_done`,
`ventilation_recommended`, `dew_point`, `wall_temperature`, `wall_source`
(`indicator`/`sensor`), `wall_critical_temperature`, `regulation`,
`last_knob` (from 0.5.2: {time, result, reason, trv, value, before, delta,
target, seconds_since_command} of the last knob decision, otherwise empty),
`external_inputs`, `wall_humidity`, `mold_level`, `outdoor_temperature`,
`outdoor_dew_point`, `season_active`, `humidity_threshold`.

## 6. Services, events, repair issues

| Service | Fields |
|---|---|
| `heizwerk.set_manual` | `entity_id`, `temperature`, `duration` (optional, only with a resume action; without = until the next value) |
| `heizwerk.resume` | `entity_id` – ends the override and runs the resume action |
| `heizwerk.sync` | `entity_id` – re-evaluate now and send pending commands (in observe-only only recompute) |

Event `heizwerk_event` with `type` `ventilation_done`, `trv_unavailable`,
`knob_adopted` or `knob_rejected` – fields see 2.2.

| Repair issue | When | Disappears |
|---|---|---|
| `target_entity_removed` | room still has a Zeitwerk target from 0.3 | after switching over and saving the room again |
| `sensor_select_not_remote` | a TRV's measuring source ≠ `remote_temperature` for 5 min | as soon as the measuring source is correct again |
| `trv_rejects_command` (from 0.5.2) | same command not taken over 3 times in 10 min | as soon as the TRV keeps the value for 2 min, when Heizwerk rejects a knob turn by a person, or when the integration starts/reloads |

## 7. Card `custom:heizwerk-card`

```yaml
type: custom:heizwerk-card
variant: standard        # standard | compact
entity: climate.heizwerk_bad
# compact with house list:
# entities: [climate.heizwerk_bad, climate.heizwerk_kueche]
title: Heizung           # house list
dial_min: 12
dial_max: 26
manual_duration: next    # next | 60 | 180 (minutes) – default for ± on the standard card
```

- **Standard** (mockup `mockups/heizwerk-karte-standard.html`, simplified in
  0.5.1): header only room name + ⋯ (more-info), state chip, dial current/target,
  ± target, next change, hint (airing/mold), room climate (humidity, dew point,
  wall humidity), day band titled "Today · Plan <name>", footer only when needed
  (sync, two-point, observe-only, warning "room sensor missing").
- **Compact** (from 0.5.1, full width): per room status icon, name with status,
  large current + target, − / + side by side (44 px), below an info line (window
  or "Manual until …", humidity, next change, airing) and a bar current →
  target. `entity` → single card, `entities` → house list with header (heating
  period, outdoor, open windows). Tapping expands duration pills "Until next
  block / 1 h / 3 h" and Resume (only with a resume action), otherwise it opens
  the more-info dialog.
- Standard: target draggable on the dial (touch/mouse, 0.5 K, sent on release),
  keyboard (arrows, Page Up/Down), ARIA slider.
- Uses HA theme variables, light/dark, touch targets ≥ 44 px, no hover needed,
  translations de/en, friendly error state without `hass`/entity.
- The card is registered by the integration itself (static path +
  `add_extra_js_url`), no manual resource.

## 8. Non-goals

- No own schedule, no profiles (Zeitwerk).
- No pre-heating/learning ("lead time from …" in the mockup) – noted for later.
- No push notifications (Läutwerk).
