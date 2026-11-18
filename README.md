# Heizwerk

**Zeitwerk plans, Heizwerk controls.** Room heating control for Home Assistant
(≥ 2026.11) with its own Lovelace card.

[Zeitwerk](https://github.com/StiviDrum/zeitwerk) decides *which* set-point
applies (profiles, weekly plan, overrides). Heizwerk turns that set-point into
commands for the radiator thermostats (TRVs) of a room – with an external room
sensor, locks, manual override and room-climate hints.

> Status: 0.1 (in development). New rooms start in **observe-only** mode: Heizwerk
> computes everything and shows what it would send, but does not touch the
> thermostats until you switch that off per room.

## Features

- `climate.heizwerk_<room>` per room – current temperature from an external
  sensor (fallback: mean of the TRV readings), target from a Zeitwerk target
  entity (e.g. `input_number.temperaturspeicher_bad`).
- Correction (e.g. −0.5 K), *set-point* or *offset* regulation, 10 s debounce,
  only differing commands are sent, optional push of the room temperature to the
  TRV's external-temperature input (e.g. Sonoff TRVZB).
- **Locks**: window open (delays), heating period off, summer lock (outdoor ≥
  16 °C for 10 min), any extra lock entity. Locked = thermostat off (frost
  protection in the device) or heat to a frost temperature.
- **Manual override** until the next Zeitwerk change or for 1 h / 3 h / any
  duration; resume at any time. With a Zeitwerk target and plan (and observe-only
  off) the override is written to the Zeitwerk target, so Zeitwerk shows it as a
  manual change and ends it with the next block; in observe-only mode the target
  is never touched.
- **Room climate**: dew point, wall humidity with mold level, airing
  recommendation and "aired enough" event.
- **Card** `custom:heizwerk-card`, registered automatically – standard room card
  and compact tile / house list, light and dark theme, German and English.

## Installation

1. HACS → Integrations → ⋮ → *Custom repositories* →
   `https://github.com/StiviDrum/heizwerk` (category *Integration*).
2. Install *Heizwerk*, restart Home Assistant.
3. Settings → Devices & services → *Add integration* → Heizwerk: choose outdoor
   temperature/humidity, heating-period entity and summer lock.
4. On the Heizwerk entry: **Add room** – name, thermostats, sensors, windows,
   Zeitwerk target and plan.

## Card

```yaml
type: custom:heizwerk-card
entity: climate.heizwerk_bad          # standard room card
```

```yaml
type: custom:heizwerk-card
variant: compact
entity: climate.heizwerk_kueche       # one-line tile, tap for details
```

```yaml
type: custom:heizwerk-card
variant: compact                      # house list with expandable rows
title: Heizung
entities:
  - climate.heizwerk_bad
  - climate.heizwerk_kueche
```

Options: `dial_min` / `dial_max` (scale, default 12–26 °C), `manual_duration`
(`next`, `60`, `180` – duration for ± on the standard card).

## Services

| Service | Fields |
|---|---|
| `heizwerk.set_manual` | `entity_id`, `temperature`, `duration` (empty = until next block) |
| `heizwerk.resume` | `entity_id` |
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
```

The dev instance in `config/` simulates two rooms (TRVs as generic thermostats,
sensors and windows as helpers) and copies Zeitwerk from `../zeitwerk` if present.

---

## Deutsch

**Zeitwerk plant, Heizwerk regelt.** Zeitwerk legt fest, welcher Sollwert gilt;
Heizwerk setzt ihn pro Raum an den Thermostaten um – mit externem Raumfühler,
Korrektur, Sperren (Fenster, Heizperiode, Sommerabschaltung, eigene Sperren),
manueller Übersteuerung (bis nächster Block / 1 Std. / 3 Std., auch in Zeitwerk
sichtbar) und Raumklima
(Taupunkt, Wandfeuchte, Lüftungsempfehlung).

**Neue Räume starten im Modus „Nur beobachten“**: Heizwerk rechnet alles und
zeigt in der Karte bzw. im Attribut `planned_commands`, was es senden würde, fasst
die Thermostate aber nicht an. Erst wenn der Schalter
`switch.heizwerk_<raum>_observe_only` aus ist, regelt Heizwerk wirklich.

Einrichtung: Integration hinzufügen (Außenfühler, Heizperiode, Sommerabschaltung),
dann am Eintrag **„Raum hinzufügen“**. Die Karte (`custom:heizwerk-card`) wird
automatisch registriert und hat die Varianten **Standard** (Raumkarte) und
**Kompakt** (Kachel bzw. Hausliste). Details: [docs/SPEC.md](docs/SPEC.md).
