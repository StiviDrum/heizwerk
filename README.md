<p align="center"><img src="docs/brand/heizwerk-icon.svg" width="128" alt="Heizwerk"></p>

# Heizwerk

English | [Deutsch](#deutsch)

**Zeitwerk plans, Heizwerk controls.** Room heating control for Home Assistant
(≥ 2026.11) with its own Lovelace card.

A scheduler – [Zeitwerk](https://github.com/StiviDrum/zeitwerk), the Scheduler
component or a plain automation – decides *which* set-point applies. Heizwerk
turns it into commands for the radiator thermostats (TRVs) of a room: external
room sensor, locks, manual override, knob at the thermostat and room-climate
hints. Without a scheduler Heizwerk is simply a thermostat per room.

> **Version 0.5.2.** New rooms start in **observe-only** mode: Heizwerk computes
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
    hysteresis (the upper one may be negative to switch off before the target)
    and an optional minimum run / pause time of the valve (not after a lock:
    after airing the valve opens immediately), like a classic heating
    automation,
  - *offset* – for thermostats without an external input.
  10 s debounce, only differing commands are sent, re-check every 5 min. The
  same command is sent at most 3 times within 10 minutes; a thermostat that
  does not take it over raises a repair issue. Nothing is sent before Home
  Assistant has fully started.
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
- **Knob protection** – set-point reports within 30 s after Heizwerk's own
  command, the thermostat's old value within 5 minutes after a command, jumps
  of more than 5 K and values below a lower bound (default: lowest Zeitwerk
  profile value, else the room's minimum set-point) are not taken as a knob
  turn; a report matching Heizwerk's own value is simply accepted. With
  two-point regulation the knob is always reset. Every decision is logged, fired as an event and shown in the attribute
  `last_knob`.
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
| `heizwerk.resume` | `entity_id` – ends the override and runs the room's resume action |
| `heizwerk.sync` | `entity_id` – evaluate and send pending commands now |

Event `heizwerk_event` (always with `room` and `entity_id`), `type`:

| `type` | When |
|---|---|
| `ventilation_done` | window open for the recommended airing time (`minutes`) |
| `trv_unavailable` | a thermostat unavailable for 5 min (`trvs`) |
| `knob_adopted` | knob turn at the thermostat adopted as manual override |
| `knob_rejected` | knob report rejected; `reason`: `after_own_command`, `stale_value`, `two_point`, `reset_mode`, `jump`, `below_minimum` |

`knob_*` events carry `trv`, `value`, `before`, `delta`, `target`,
`seconds_since_command`, `result` and `reason`. Use e.g. `ventilation_done` to
start a [Läutwerk](https://github.com/StiviDrum/laeutwerk) reminder via
`laeutwerk.trigger`.

Full specification: [docs/SPEC.en.md](docs/SPEC.en.md) (English) ·
[docs/SPEC.md](docs/SPEC.md) (German, source of truth).

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

[English](#heizwerk) | Deutsch

**Zeitwerk plant, Heizwerk regelt.** Raumweise Heizungsregelung für Home
Assistant (≥ 2026.11) mit eigener Lovelace-Karte.

Ein Zeitplan – [Zeitwerk](https://github.com/StiviDrum/zeitwerk), die
Scheduler-Komponente oder eine einfache Automation – entscheidet, *welcher*
Sollwert gilt. Heizwerk macht daraus Befehle für die Heizkörperthermostate (TRV)
eines Raums: externer Raumfühler, Sperren, manuelle Übersteuerung, Drehen am
Thermostat und Raumklima-Hinweise. Ohne Zeitplan ist Heizwerk einfach ein
Thermostat pro Raum.

> **Version 0.5.2.** Neue Räume starten im Modus **„Nur beobachten“**: Heizwerk
> rechnet alles und zeigt, was es senden würde, fasst die Thermostate aber nicht
> an, bis du das pro Raum ausschaltest. Siehe [CHANGELOG](CHANGELOG.md).

### Funktionen

- **`climate.heizwerk_<raum>`** pro Raum – Ist-Temperatur vom externen
  Raumfühler (ersatzweise Mittel der TRV-Messungen); der Sollwert kommt über
  `climate.set_temperature` (Zeitplan, Automation, Karte, Sprache).
- **Regelung** pro Raum:
  - *Sollwert* (Standard) – das TRV regelt selbst; beim Sonoff TRVZB nach der
    Raumtemperatur, die Heizwerk an seinen externen Eingang schickt,
  - *Zweipunkt* – Ventil ganz auf mit festem Wert (Standard 24 °C) oder aus, mit
    Hysterese (die obere darf negativ sein, um schon vor dem Ziel abzuschalten)
    und optionaler Mindestlaufzeit / Mindestpause des Ventils (nicht nach einer
    Sperre: nach dem Lüften öffnet das Ventil sofort) – wie eine klassische
    Heizungs-Automation,
  - *Offset* – für Thermostate ohne externen Eingang.
  10 s Entprellung, nur abweichende Befehle werden gesendet, Abgleich alle
  5 min. Derselbe Befehl geht höchstens 3-mal innerhalb von 10 Minuten raus; ein
  Thermostat, das ihn nicht übernimmt, erzeugt einen Reparaturhinweis. Vor dem
  vollständigen Start von Home Assistant wird nichts gesendet.
- **Raumtemperatur an die Thermostate** – ein Schalter: Heizwerk findet den
  `…_external_temperature_input` jedes TRVZB selbst und meldet einen
  Reparaturhinweis, wenn ein Thermostat nicht mehr mit `remote_temperature` misst.
- **Sperren** – Fenster offen (mit Verzögerungen), Heizperiode aus,
  Sommerabschaltung (Hauswert, pro Raum überschreibbar), eigene
  Sperr-Entitäten. Gesperrt = TRV aus (Frostschutz im Gerät) oder heizen auf eine
  Frostschutztemperatur.
- **Manuelle Übersteuerung** – Karte (±, Ziehen am Kreis), Dienst oder **Drehen
  am Thermostat**; endet mit dem nächsten Wert des Zeitplans, nach 1 Std. /
  3 Std. oder mit **Fortsetzen**, das eine einstellbare Aktion ausführt
  (Standard mit Zeitwerk-Plan: `zeitwerk.resume`; Scheduler: z. B.
  `scheduler.run_action`). Zeitwerk zeigt Heizwerk-Übersteuerungen als manuelle
  Änderungen.
- **Schutz beim Drehen am Thermostat** – Sollwert-Meldungen innerhalb von 30 s
  nach einem eigenen Befehl, der alte Wert des Thermostats innerhalb von
  5 Minuten nach einem Befehl, Sprünge um mehr als 5 K und Werte unter einer
  Untergrenze (Standard: niedrigster Zeitwerk-Profilwert, sonst der minimale
  Sollwert des Raums) gelten nicht als Drehen; eine Meldung, die Heizwerks
  eigenem Wert entspricht, wird einfach akzeptiert. Bei Zweipunkt-Regelung wird
  der Drehknopf immer zurückgesetzt. Jede Entscheidung wird protokolliert, als
  Ereignis gemeldet und im Attribut `last_knob` angezeigt.
- **Raumklima** – Taupunkt, Wandfeuchte mit Schimmelstufe (aus einem
  Wandtemperatur-Sensor oder direkt aus einem Schimmel-Indikator),
  Lüftungsempfehlung, Ereignis „genug gelüftet“.
- **Karte** `custom:heizwerk-card`, automatisch registriert – Standard-Raumkarte
  (Kreisanzeige, Raumklima, Tagesband mit Planname) und eine Kompaktkarte bzw.
  Hausliste in voller Breite (Status, Temperaturen, ±, Infozeile,
  Fortschrittsbalken), hell und dunkel, Deutsch und Englisch.

### Installation

1. HACS → Integrationen → ⋮ → *Benutzerdefinierte Repositories* →
   `https://github.com/StiviDrum/heizwerk` (Kategorie *Integration*).
2. *Heizwerk* installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → *Integration hinzufügen* → **Heizwerk**:
   Außentemperatur/-feuchte, Heizperioden-Entität, Sommerabschaltung.
4. Am Heizwerk-Eintrag: **Raum hinzufügen** – oben Name, Thermostate, Raumfühler
   und Nur beobachten; alles Weitere in aufklappbaren Abschnitten (Zeitplan &
   Fortsetzen, Raumklima, Fenster & Sperren, Regelung, Sollwerte & Grenzen),
   jede Einstellung mit Hilfetext. Der Zeitwerk-Plan wird automatisch erkannt.

### Zeitplan anbinden

```yaml
# Zeitwerk-Profilaktion (oder Scheduler-/Automations-Aktion)
action: climate.set_temperature
target:
  entity_id: climate.heizwerk_bad
data:
  temperature: 21
```

Mehr Schnittstelle gibt es nicht. Lass die Fortsetzen-Aktion des Raums leer, um
`zeitwerk.resume` für den erkannten Plan zu nutzen, oder trag eine eigene ein
(z. B. `scheduler.run_action` mit dem Zeitplan-Schalter). Ohne Fortsetzen-Aktion
blendet die Karte „Fortsetzen“ und die Dauer-Schaltflächen aus.

### Karte

```yaml
type: custom:heizwerk-card
entity: climate.heizwerk_bad          # Standard-Raumkarte
```

```yaml
type: custom:heizwerk-card
variant: compact
entity: climate.heizwerk_kueche       # Kachel volle Breite: Status, Temperaturen, ±, Infozeile
```

```yaml
type: custom:heizwerk-card
variant: compact                      # Hausliste mit aufklappbaren Zeilen
title: Heizung
entities:
  - climate.heizwerk_bad
  - climate.heizwerk_kueche
```

In der Standardkarte lässt sich das Ziel am Kreis ziehen (Touch oder Maus,
0,5-K-Schritte, gesendet beim Loslassen) oder mit ± und den Pfeiltasten ändern.
Optionen: `dial_min` / `dial_max` (Skala, Standard 12–26 °C), `manual_duration`
(`next`, `60`, `180` – Dauer für ± in der Standardkarte).

### Dienste und Ereignisse

| Dienst | Felder |
|---|---|
| `heizwerk.set_manual` | `entity_id`, `temperature`, `duration` (leer = bis zum nächsten Wert) |
| `heizwerk.resume` | `entity_id` – beendet die Übersteuerung und führt die Fortsetzen-Aktion des Raums aus |
| `heizwerk.sync` | `entity_id` – sofort auswerten und ausstehende Befehle senden |

Ereignis `heizwerk_event` (immer mit `room` und `entity_id`), `type`:

| `type` | Wann |
|---|---|
| `ventilation_done` | Fenster so lange offen wie die empfohlene Lüftungsdauer (`minutes`) |
| `trv_unavailable` | ein Thermostat seit 5 min nicht verfügbar (`trvs`) |
| `knob_adopted` | Drehen am Thermostat als manuelle Übersteuerung übernommen |
| `knob_rejected` | Meldung vom Thermostat verworfen; `reason`: `after_own_command`, `stale_value`, `two_point`, `reset_mode`, `jump`, `below_minimum` |

`knob_*`-Ereignisse enthalten `trv`, `value`, `before`, `delta`, `target`,
`seconds_since_command`, `result` und `reason`. Mit `ventilation_done` lässt
sich z. B. eine [Läutwerk](https://github.com/StiviDrum/laeutwerk)-Erinnerung
über `laeutwerk.trigger` starten.

Vollständige Spezifikation: [docs/SPEC.md](docs/SPEC.md) (Deutsch, maßgeblich) ·
[docs/SPEC.en.md](docs/SPEC.en.md) (Englisch).

### Entwicklung

```bash
scripts/setup      # .venv (Python ≥ 3.14) + npm ci
scripts/develop    # lokale Dev-Instanz auf http://localhost:8125 (nur Helfer)
scripts/check      # nur lesend: ruff, prettier, eslint, tsc, pytest, vitest
scripts/lint       # formatieren + automatisch korrigieren
python scripts/dev_check.py screenshots [--shots]   # Szenarien + Screenshots
```

Die Dev-Instanz in `config/` simuliert zwei Räume (TRVs als generische
Thermostate, Sensoren, Fenster und ein Schimmel-Indikator als Helfer) und
kopiert Zeitwerk aus `../zeitwerk`, falls vorhanden.
