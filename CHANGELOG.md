# Changelog

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
