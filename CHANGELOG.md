# Changelog

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
