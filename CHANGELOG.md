# Changelog

## 0.5.1 – 2026-11-18

- Compact card redesigned for full width: status icon, name with status,
  current and target temperature, − / + side by side, info line (window /
  manual end, humidity, next change) and a progress bar; same layout in the
  house list.
- Standard card decluttered: header shows only the room name; the plan name is
  shown above the day band; footer only when needed (sync time, two-point,
  observe-only, missing room sensor) – no more "TRV heats to" / "sensor".
- Room dialog: option fields are dropdowns. HA 2026.11 squeezes the radio dot's
  16×16 SVG to 11.2×14 px, so the dot sat off-centre.
- Brand: icon and logo for Home Assistant (`custom_components/heizwerk/brand`),
  SVG sources and social preview in `docs/brand`, icon in the README.

## 0.5.0 – 2026-11-18

Everything needed to retire the old heating automations.

- **Send room temperature to the thermostats** (one switch): Heizwerk finds the
  external temperature input (`number.…_external_temperature_input`, Sonoff
  TRVZB) on each thermostat's device itself; only with a room sensor. Rooms with
  explicit inputs from older versions keep them.
- **Two-point regulation** (option; default stays "set-point", the TRVZB
  regulates itself with the external value): valve heats at a fixed value
  (default 24 °C) or is off, hysteresis low/high; needs a room sensor; state
  survives restarts.
- **Outdoor limit per room** (optional, overrides the house value; 0 = no summer
  lock for this room).
- **Measuring-source notice**: repair issue when a thermostat's
  `…_temperature_sensor_select` is not `remote_temperature` for 5 minutes
  (restarts ignored). Heizwerk never switches it itself.
- **Knob at the thermostat** = manual override (or "reset" per room). Echoes of
  Heizwerk's own commands, automation writes, locks and devices coming back are
  ignored; several clicks in a row are adopted as one.
- **Mold indicator** (e.g. HA's mold indicator) as wall-humidity source with its
  critical wall temperature; the wall temperature field only accepts °C/°F.
- Card: "critical below …", "at the thermostat", "two-point", warning when the
  room sensor is missing while thermostats use its value.
- Independent review (separate review agent): 14 findings + 1 follow-up fixed
  before release, each with a regression test.

## 0.4.0 – 2026-11-18

**Breaking – simpler interface.** A scheduler (Zeitwerk, Scheduler, automation)
now calls `climate.set_temperature` on `climate.heizwerk_<room>`; Heizwerk is a
plain thermostat and works without any scheduler.

- Removed the "Zeitwerk target" field and writing manual values to helpers.
  An old value is ignored and reported as a repair issue (re-save the room
  after switching the plan to `climate.set_temperature`).
- Fixed: Zeitwerk target set to the room's own climate entity ended in a
  `RecursionError` (0.3.0). Heizwerk's own entities can no longer be selected.
- New room option "Resume action" (any HA action, e.g. `scheduler.run_action`);
  empty with a detected Zeitwerk plan = `zeitwerk.resume`. Runs on "Resume" and
  when a 1 h / 3 h override ends. Without it, resume and durations are hidden.
- Manual overrides: Heizwerk card / `heizwerk.set_manual` mark the set-point as
  manual; the next value from the scheduler ends it. Zeitwerk detects the change
  itself and shows it; changes Zeitwerk reports are shown in Heizwerk too.
- Zeitwerk plan auto-detected from the plan that writes the room's climate
  entity (dialog and at start). New attribute `resume_available`; removed
  `scheduled_target`, `target_entity`, `manual_source`.
- Card: resume and duration pills only when a resume action exists; "Start
  set-point" moved to "Set-points & limits".

## 0.3.0 – 2026-11-18

- Room dialog: required and important fields first (name, thermostats, room
  sensor, Zeitwerk target, observe-only), everything else in collapsible
  sections (Zeitwerk, room climate, windows & locks, regulation, limits); the
  house options likewise. Stored data stays flat – existing rooms keep working.
- Help text for every setting (de/en) with defaults and recommendations.
- Fields appear only when they matter: frost temperature only with lock mode
  "frost", set-point without Zeitwerk target only without a target.
- Zeitwerk plan is detected automatically from the Zeitwerk target
  (`zeitwerk.get_plan`); the field remains as an override.
- Error when "offset" regulation is combined with an external temperature input.
- Card: drag the target on the dial (touch and mouse, 0.5 K steps, committed
  on release); keyboard control (arrows, Page Up/Down) and ARIA slider.

## 0.2.0 – 2026-11-18

- Manual overrides are visible in Zeitwerk: with a Zeitwerk target and plan
  (observe-only off) Heizwerk writes the manual value to the Zeitwerk target;
  Zeitwerk shows it as a manual change and ends it with the next block.
  Durations end via `zeitwerk.resume`, "Resume" in either card ends both.
- Overrides started in Zeitwerk are shown in Heizwerk (`manual_source`).
- Observe-only rooms never write to the Zeitwerk target.

## 0.1.1 – 2026-11-18

- Fix: entity pickers in the Heizwerk options and the room dialog showed
  "no entities available" (an empty `device_class` filter hid every entity).
- Outdoor temperature no longer offers `weather` entities (their state is not a
  number).

## 0.1.0 – 2026-11-18

- Integration `heizwerk` (HA ≥ 2026.11): one entry with house options, rooms as
  config subentries ("Add room").
- `climate.heizwerk_<room>`: target from a Zeitwerk target entity, external room
  sensor, correction, set-point or offset regulation, 10 s debounce, only
  differing commands are sent.
- Locks: window (open/close delays), heating period, summer lock (outdoor ≥ 16 °C
  for 10 min), extra lock entities; lock mode thermostat off or frost protection.
- Manual override until the next Zeitwerk change or for a duration
  (`heizwerk.set_manual`, `heizwerk.resume`, `heizwerk.sync`).
- Observe-only mode (default for new rooms) with planned commands as attribute.
- Room climate: dew point, wall humidity / mold level, airing recommendation,
  events `heizwerk_event` (`ventilation_done`, `trv_unavailable`).
- Card `custom:heizwerk-card`: standard (dial, room climate, Zeitwerk day band)
  and compact (tile, house list) variants, light/dark, de/en, visual editor.
