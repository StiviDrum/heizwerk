<p align="center"><img src="docs/brand/heizwerk-icon.svg" width="128" alt="Heizwerk"></p>

# Heizwerk

**Zeitwerk plans, Heizwerk controls.** Room heating control for Home Assistant
(≥ 2026.11) with its own Lovelace card.

A scheduler – [Zeitwerk](https://github.com/StiviDrum/zeitwerk), the Scheduler
component or a plain automation – decides *which* set-point applies. Heizwerk
turns it into commands for the radiator thermostats (TRVs) of a room: external
room sensor, locks, manual override, knob at the thermostat and room-climate
hints. Without a scheduler Heizwerk is simply a thermostat per room.

> **Version 0.5.1.** New rooms start in **observe-only** mode: Heizwerk computes
> everything and shows what it would send, but does not touch the thermostats
> until you switch that off per room. See [CHANGELOG](CHANGELOG.md).

## Features

- **`climate.heizwerk_<room>`** per room – current temperature from an external
  room sensor (fallback: mean of the TRV readings); the set-point comes from
  `climate.set_temperature` (scheduler, automation, card, voice).
- **Regulation** per room:
  - *set-point* (default) – the TRV regulates itself; with Sonoff TRVZB on the
    room temperature Heizwerk sends to its external input,
  - *two-point* – valve fully open at a fixed value (default 24 °C) or off, with
    hysteresis, like a classic heating automation,
  - *offset* – for thermostats without an external input.
  10 s debounce, only differing commands are sent, re-check every 5 min.
- **Room temperature to the thermostats** – one switch: Heizwerk finds each
  TRVZB's `…_external_temperature_input` itself and raises a repair issue if a
  thermostat no longer measures with `remote_temperature`.
- **Locks** – window open (delays), heating period off, summer lock (house value,
  per room overridable), extra lock entities. Locked = TRV off (frost protection
  in the device) or heat to a frost temperature.
- **Manual override** – card (±, drag on the dial), service or **knob at the
  thermostat**; ends with the scheduler's next value, after 1 h / 3 h, or with
  **Resume**, which runs a configurable action (default with a Zeitwerk plan:
  `zeitwerk.resume`; Scheduler: e.g. `scheduler.run_action`). Zeitwerk shows
  Heizwerk overrides as manual changes.
- **Room climate** – dew point, wall humidity with mold level (from a wall
  temperature sensor or directly from a mold indicator), airing recommendation,
  "aired enough" event.
- **Card** `custom:heizwerk-card`, registered automatically – standard room card
  (dial, room climate, day band with the plan name) and a full-width compact
  card / house list (status, temperatures, ±, info line, progress bar), light
  and dark, German and English.

## Installation

1. HACS → Integrations → ⋮ → *Custom repositories* →
   `https://github.com/StiviDrum/heizwerk` (category *Integration*).
2. Install *Heizwerk*, restart Home Assistant.
3. Settings → Devices & services → *Add integration* → **Heizwerk**: outdoor
   temperature/humidity, heating-period entity, summer lock.
4. On the Heizwerk entry: **Add room** – name, thermostats, room sensor and
   observe-only on top; everything else in collapsible sections (schedule &
   resume, room climate, windows & locks, regulation, set-points & limits), each
   setting with a help text. The Zeitwerk plan is detected automatically.

## Connecting a scheduler

```yaml
# Zeitwerk profile action (or Scheduler / automation action)
action: climate.set_temperature
target:
  entity_id: climate.heizwerk_bad
data:
  temperature: 21
```

That is the whole interface. Leave the room's resume action empty to use
`zeitwerk.resume` for the detected plan, or set your own (e.g.
`scheduler.run_action` with the schedule switch). Without any resume action the
card hides "Resume" and the duration buttons.

## Card

```yaml
type: custom:heizwerk-card
entity: climate.heizwerk_bad          # standard room card
```

```yaml
type: custom:heizwerk-card
variant: compact
entity: climate.heizwerk_kueche       # full-width tile: status, temperatures, ±, info line
```

```yaml
type: custom:heizwerk-card
variant: compact                      # house list with expandable rows
title: Heizung
entities:
  - climate.heizwerk_bad
  - climate.heizwerk_kueche
```

On the standard card the target can be dragged on the dial (touch or mouse,
0.5 K steps, sent on release) or changed with ± and the arrow keys.
Options: `dial_min` / `dial_max` (scale, default 12–26 °C), `manual_duration`
(`next`, `60`, `180` – duration for ± on the standard card).

## Services and events

| Service | Fields |
|---|---|
| `heizwerk.set_manual` | `entity_id`, `temperature`, `duration` (empty = until the next value) |
| `heizwerk.resume` | `entity_id` – runs the room's resume action |
| `heizwerk.sync` | `entity_id` – evaluate and send pending commands now |

Events: `heizwerk_event` with `type` `ventilation_done` or `trv_unavailable`
(after 5 min) – e.g. to start a [Läutwerk](https://github.com/StiviDrum/laeutwerk)
reminder via `laeutwerk.trigger`.

Full specification: [docs/SPEC.md](docs/SPEC.md) (German).

## Development

```bash
scripts/setup      # .venv (Python ≥ 3.14) + npm ci
scripts/develop    # local dev instance on http://localhost:8125 (helpers only)
scripts/check      # read-only: ruff, prettier, eslint, tsc, pytest, vitest
scripts/lint       # format + autofix
python scripts/dev_check.py screenshots [--shots]   # scenarios + screenshots
```

The dev instance in `config/` simulates two rooms (TRVs as generic thermostats,
sensors, windows and a mold indicator as helpers) and copies Zeitwerk from
`../zeitwerk` if present.

---

## Deutsch

**Zeitwerk plant, Heizwerk regelt.** Ein Zeitplan (Zeitwerk, Scheduler oder eine
Automation) legt fest, welcher Sollwert gilt; Heizwerk setzt ihn pro Raum an den
Thermostaten um – mit externem Raumfühler, Sperren (Fenster, Heizperiode,
Sommerabschaltung, eigene Sperren), manueller Übersteuerung (Karte, Drehen am
Thermostat; auch in Zeitwerk sichtbar) und Raumklima (Taupunkt, Wandfeuchte bzw.
Schimmel-Indikator, Lüftungsempfehlung). Ohne Zeitplan ist Heizwerk ein normales
Thermostat pro Raum.

**Anbindung:** Der Zeitplan setzt den Raum mit `climate.set_temperature` auf
`climate.heizwerk_<raum>` – mehr Schnittstelle gibt es nicht. „Fortsetzen“ führt
eine frei wählbare Aktion aus (Standard mit Zeitwerk-Plan: `zeitwerk.resume`, für
Scheduler z. B. `scheduler.run_action`).

**Regelung:** *Sollwert* (Standard – der TRVZB regelt selbst nach der
Raumtemperatur, die Heizwerk an seinen externen Eingang schickt), *Zweipunkt*
(Ventil auf 24 °C oder aus, mit Hysterese – wie die bisherigen Automationen) oder
*Offset* (für Thermostate ohne externen Eingang).

**Neue Räume starten im Modus „Nur beobachten“**: Heizwerk rechnet alles und
zeigt in der Karte bzw. im Attribut `planned_commands`, was es senden würde, fasst
die Thermostate aber nicht an. Erst wenn `switch.heizwerk_<raum>_observe_only` aus
ist, regelt Heizwerk wirklich.

Einrichtung: Integration hinzufügen (Außenfühler, Heizperiode, Sommerabschaltung),
dann am Eintrag **„Raum hinzufügen“** – oben Name, Thermostate, Raumfühler, Nur
beobachten; alles Weitere in aufklappbaren Abschnitten mit Hilfetext. Die Karte
(`custom:heizwerk-card`) wird automatisch registriert: **Standard** (Raumkarte,
Ziel am Kreis ziehbar) und **Kompakt** (Kachel bzw. Hausliste).
Details: [docs/SPEC.md](docs/SPEC.md).
