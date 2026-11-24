# Changelog

Each entry in English, followed by the German version.
Jeder Eintrag auf Englisch, darunter auf Deutsch.

## 0.5.2 – 2026-11-24

Fix for a production incident: a Zigbee2MQTT thermostat that Heizwerk switched
to heat (two-point, heat set-point 30 °C) reported its previously stored
set-point (e.g. 18 °C) in a separate message 0.15–0.25 s later. 0.5.1 treated
that as a knob turn and kept a 6 °C manual value until the next schedule change.

- **Knob detection**: set-point reports within 30 s after an own command are no
  longer taken as a knob turn; a report equal to the thermostat's set-point
  before Heizwerk's last command is rejected within 5 minutes after that
  command (stale value). Heizwerk then sends its own value again. A report
  equal to the set-point Heizwerk currently wants for that thermostat is never
  a knob turn (the thermostat agrees; no event).
- **Two-point regulation**: turning the knob at the thermostat is always reset
  (the knob shows the heat set-point, not the room temperature); the room dialog
  hides "Turning the thermostat knob" for two-point.
- **Plausibility**: a single report changing the set-point by more than 5 K is
  rejected; a knob value below a lower bound is rejected – new room option
  `knob_min_temperature` (5–25 °C), empty = automatic: lowest Zeitwerk profile
  value for this room, else the room's minimum set-point. The unclamped value is
  compared, so the minimum set-point works as a bound even without plan and
  option.
- **Retry cap**: the same command is sent at most 3 times within 10 minutes;
  then Heizwerk pauses and raises a repair issue ("thermostat does not take
  over the command"). Counter and issue reset when the thermostat keeps the
  value for 2 minutes. Only device-side reports count (`after_own_command`,
  `stale_value`, `jump` – a change over 5 K is a device resetting itself); knob turns by a person that Heizwerk rejects (`two_point`,
  `reset_mode`, `below_minimum`) reset the counter and remove the
  notice. These notices are removed on start/reload.
- **Start-up**: no commands are sent to thermostats before Home Assistant has
  fully started; the two-point valve state is taken over from the first
  available thermostat report (also during start-up).
- **Two-point**: upper hysteresis may be negative (−2 … 3 K; off already before
  the target, against overshoot); low + high must be ≥ 0.2 K. Optional minimum
  run / pause time of the valve (`min_on_minutes` / `min_off_minutes`, 0–60 min,
  0 = off); window, locks and room off still act immediately, and there is no
  hold after a forced state (lock, room off, missing room temperature) – after
  airing the valve opens immediately.
- **Traceability**: every knob decision is logged (info) and fired as
  `heizwerk_event` type `knob_adopted` / `knob_rejected` (`trv`, `value`,
  `before`, `delta`, `target`, `seconds_since_command`, `reason`:
  `after_own_command`, `stale_value`, `two_point`, `reset_mode`, `jump`,
  `below_minimum`); new attribute `last_knob` on `climate.heizwerk_<room>`.
- Default behaviour otherwise unchanged; the new options are opt-in.
- Documentation fully bilingual (README, CHANGELOG, SPEC, branding).

Deutsch:

Behebt einen Vorfall im Produktivbetrieb: Ein Zigbee2MQTT-Thermostat, das
Heizwerk auf heat schaltete (Zweipunkt, Heiz-Sollwert 30 °C), meldete
0,15–0,25 s später in einer eigenen Nachricht seinen vorher gespeicherten
Sollwert (z. B. 18 °C). 0.5.1 hielt das für Drehen am Thermostat und behielt bis
zum nächsten Zeitplanwechsel einen manuellen Wert von 6 °C.

- **Erkennung Drehen am Thermostat**: Sollwert-Meldungen innerhalb von 30 s nach
  einem eigenen Befehl gelten nicht mehr als Drehen; eine Meldung gleich dem
  Thermostat-Sollwert vor Heizwerks letztem Befehl wird innerhalb von
  5 Minuten nach diesem Befehl verworfen (veralteter Wert). Heizwerk sendet dann
  seinen eigenen Wert erneut. Eine Meldung gleich dem Sollwert, den Heizwerk
  gerade für dieses Thermostat will, ist nie Drehen am Thermostat (das
  Thermostat stimmt zu; kein Ereignis).
- **Zweipunkt-Regelung**: Drehen am Thermostat wird immer zurückgesetzt (der
  Drehknopf zeigt den Heiz-Sollwert, nicht die Raumtemperatur); der Raumdialog
  blendet „Drehen am Thermostat“ bei Zweipunkt aus.
- **Plausibilität**: Eine einzelne Meldung, die den Sollwert um mehr als 5 K
  ändert, wird verworfen; ein Handwert unter einer Untergrenze wird verworfen –
  neue Raumoption `knob_min_temperature` (5–25 °C), leer = automatisch:
  niedrigster Zeitwerk-Profilwert dieses Raums, sonst der minimale Sollwert des
  Raums. Verglichen wird der unbegrenzte Wert, daher wirkt der minimale Sollwert
  auch ohne Plan und Option als Grenze.
- **Wiederholungsgrenze**: Derselbe Befehl wird höchstens 3-mal innerhalb von
  10 Minuten gesendet; danach pausiert Heizwerk und meldet einen
  Reparaturhinweis („Thermostat übernimmt den Befehl nicht“). Zähler und Hinweis
  werden zurückgesetzt, wenn das Thermostat den Wert 2 Minuten lang hält. Es
  zählen nur Meldungen des Geräts (`after_own_command`, `stale_value`, `jump` – ein Sprung
  über 5 K ist ein Gerät, das sich zurücksetzt); von Heizwerk verworfenes Drehen durch eine Person (`two_point`, `reset_mode`,
  `below_minimum`) setzt den Zähler zurück und entfernt den Hinweis.
  Beim Start/Neuladen werden diese Hinweise entfernt.
- **Start**: Vor dem vollständigen Start von Home Assistant werden keine Befehle
  an Thermostate gesendet; der Ventilzustand bei Zweipunkt wird aus der ersten
  verfügbaren Thermostat-Meldung übernommen (auch schon während des Starts).
- **Zweipunkt**: Die obere Hysterese darf negativ sein (−2 … 3 K; aus schon vor
  dem Soll, gegen Überschwingen); unten + oben muss ≥ 0,2 K sein. Optionale
  Mindestlaufzeit / Mindestpause des Ventils (`min_on_minutes` /
  `min_off_minutes`, 0–60 min, 0 = aus); Fenster, Sperren und Raum aus wirken
  trotzdem sofort, und nach einem erzwungenen Zustand (Sperre, Raum aus,
  fehlende Raumtemperatur) gilt keine Haltezeit – nach dem Lüften öffnet das
  Ventil sofort.
- **Nachvollziehbarkeit**: Jede Entscheidung zum Drehen am Thermostat wird
  protokolliert (Info) und als `heizwerk_event` mit `type` `knob_adopted` /
  `knob_rejected` gemeldet (`trv`, `value`, `before`, `delta`, `target`,
  `seconds_since_command`, `reason`: `after_own_command`, `stale_value`,
  `two_point`, `reset_mode`, `jump`, `below_minimum`); neues Attribut
  `last_knob` an `climate.heizwerk_<raum>`.
- Standardverhalten sonst unverändert; die neuen Optionen sind freiwillig.
- Dokumentation vollständig zweisprachig (README, CHANGELOG, SPEC, Branding).

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

Deutsch:

- Kompaktkarte für volle Breite neu gestaltet: Status-Symbol, Name mit Status,
  Ist- und Zieltemperatur, − / + nebeneinander, Infozeile (Fenster / Ende der
  Übersteuerung, Feuchte, nächster Wechsel) und ein Fortschrittsbalken; gleiches
  Layout in der Hausliste.
- Standardkarte entrümpelt: Kopf zeigt nur den Raumnamen; der Planname steht
  über dem Tagesband; Fußzeile nur bei Bedarf (Abgleichzeit, Zweipunkt, Nur
  beobachten, fehlender Raumfühler) – kein „TRV heizt auf“ / „Fühler“ mehr.
- Raumdialog: Auswahlfelder sind Klapplisten. HA 2026.11 staucht das
  16×16-SVG des Radio-Punkts auf 11,2×14 px, dadurch saß der Punkt versetzt.
- Brand: Icon und Logo für Home Assistant (`custom_components/heizwerk/brand`),
  SVG-Quellen und Social Preview in `docs/brand`, Icon im README.

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
  ignored; with several quick clicks the last click wins.
- **Mold indicator** (e.g. HA's mold indicator) as wall-humidity source with its
  critical wall temperature; the wall temperature field only accepts °C/°F.
- Card: "critical below …", "at the thermostat", "two-point", warning when the
  room sensor is missing while thermostats use its value.
- Independent review (separate review agent): 14 findings + 1 follow-up fixed
  before release, each with a regression test.

Deutsch:

Alles, was nötig ist, um die alten Heizungs-Automationen abzulösen.

- **Raumtemperatur an die Thermostate senden** (ein Schalter): Heizwerk findet
  den externen Temperatureingang (`number.…_external_temperature_input`, Sonoff
  TRVZB) am Gerät jedes Thermostats selbst; nur mit Raumfühler. Räume mit
  expliziten Eingängen aus älteren Versionen behalten diese.
- **Zweipunkt-Regelung** (Option; Standard bleibt „Sollwert“, der TRVZB regelt
  selbst mit dem externen Wert): Ventil heizt mit festem Wert (Standard 24 °C)
  oder ist aus, Hysterese unten/oben; braucht einen Raumfühler; Zustand
  übersteht Neustarts.
- **Außengrenze pro Raum** (optional, überschreibt den Hauswert; 0 = keine
  Sommerabschaltung für diesen Raum).
- **Hinweis zur Messquelle**: Reparaturhinweis, wenn der
  `…_temperature_sensor_select` eines Thermostats 5 Minuten lang nicht
  `remote_temperature` ist (Neustarts ignoriert). Heizwerk stellt ihn nie selbst
  um.
- **Drehen am Thermostat** = manuelle Übersteuerung (oder „zurücksetzen“ pro
  Raum). Echos eigener Befehle, Schreibvorgänge von Automationen, Sperren und
  wieder verfügbare Geräte werden ignoriert; bei mehreren schnellen Klicks
  gilt der letzte.
- **Schimmel-Indikator** (z. B. der Schimmel-Indikator von HA) als Quelle der
  Wandfeuchte mit seiner kritischen Wandtemperatur; das Wandtemperatur-Feld
  akzeptiert nur °C/°F.
- Karte: „kritisch unter …“, „am Thermostat“, „Zweipunkt“, Warnung, wenn der
  Raumfühler fehlt, während Thermostate seinen Wert nutzen.
- Unabhängiges Review (eigener Review-Agent): 14 Befunde + 1 Nachtrag vor dem
  Release behoben, jeweils mit Regressionstest.

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

Deutsch:

**Inkompatibel – einfachere Schnittstelle.** Ein Zeitplan (Zeitwerk, Scheduler,
Automation) ruft jetzt `climate.set_temperature` auf `climate.heizwerk_<raum>`
auf; Heizwerk ist ein normales Thermostat und funktioniert ganz ohne Zeitplan.

- Feld „Zeitwerk-Ziel“ und das Schreiben manueller Werte in Helfer entfernt.
  Ein alter Wert wird ignoriert und als Reparaturhinweis gemeldet (Raum erneut
  speichern, nachdem der Plan auf `climate.set_temperature` umgestellt ist).
- Behoben: Ein Zeitwerk-Ziel auf die eigene Klima-Entität des Raums endete in
  einem `RecursionError` (0.3.0). Heizwerks eigene Entitäten sind nicht mehr
  wählbar.
- Neue Raumoption „Fortsetzen-Aktion“ (beliebige HA-Aktion, z. B.
  `scheduler.run_action`); leer mit erkanntem Zeitwerk-Plan = `zeitwerk.resume`.
  Läuft bei „Fortsetzen“ und wenn eine Übersteuerung von 1 Std. / 3 Std. endet.
  Ohne sie sind Fortsetzen und Dauern ausgeblendet.
- Manuelle Übersteuerungen: Heizwerk-Karte / `heizwerk.set_manual` markieren
  den Sollwert als manuell; der nächste Wert des Zeitplans beendet das. Zeitwerk
  erkennt die Änderung selbst und zeigt sie an; von Zeitwerk gemeldete
  Änderungen werden auch in Heizwerk angezeigt.
- Zeitwerk-Plan wird automatisch erkannt: der Plan, der die Klima-Entität des
  Raums schreibt (im Dialog und beim Start). Neues Attribut `resume_available`;
  entfernt: `scheduled_target`, `target_entity`, `manual_source`.
- Karte: Fortsetzen- und Dauer-Pillen nur mit Fortsetzen-Aktion;
  „Start-Sollwert“ nach „Sollwerte & Grenzen“ verschoben.

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

Deutsch:

- Raumdialog: Pflicht- und wichtige Felder zuerst (Name, Thermostate,
  Raumfühler, Zeitwerk-Ziel, Nur beobachten), alles Weitere in aufklappbaren
  Abschnitten (Zeitwerk, Raumklima, Fenster & Sperren, Regelung, Grenzen); die
  Hausoptionen ebenso. Gespeichert wird weiterhin flach – bestehende Räume
  funktionieren weiter.
- Hilfetext zu jeder Einstellung (de/en) mit Standardwerten und Empfehlungen.
- Felder erscheinen nur, wenn sie wirken: Frostschutztemperatur nur bei
  Sperrmodus „Frostschutz“, Sollwert ohne Zeitwerk-Ziel nur ohne Ziel.
- Zeitwerk-Plan wird aus dem Zeitwerk-Ziel automatisch erkannt
  (`zeitwerk.get_plan`); das Feld bleibt zum Überschreiben.
- Fehler, wenn die Regelung „Offset“ mit einem externen Temperatureingang
  kombiniert wird.
- Karte: Ziel am Kreis ziehen (Touch und Maus, 0,5-K-Schritte, übernommen beim
  Loslassen); Tastatursteuerung (Pfeile, Bild auf/ab) und ARIA-Slider.

## 0.2.0 – 2026-11-18

- Manual overrides are visible in Zeitwerk: with a Zeitwerk target and plan
  (observe-only off) Heizwerk writes the manual value to the Zeitwerk target;
  Zeitwerk shows it as a manual change and ends it with the next block.
  Durations end via `zeitwerk.resume`, "Resume" in either card ends both.
- Overrides started in Zeitwerk are shown in Heizwerk (`manual_source`).
- Observe-only rooms never write to the Zeitwerk target.

Deutsch:

- Manuelle Übersteuerungen sind in Zeitwerk sichtbar: Mit Zeitwerk-Ziel und
  Plan (Nur beobachten aus) schreibt Heizwerk den manuellen Wert ins
  Zeitwerk-Ziel; Zeitwerk zeigt ihn als manuelle Änderung und beendet sie mit
  dem nächsten Block. Dauern enden über `zeitwerk.resume`, „Fortsetzen“ in einer
  der beiden Karten beendet beide.
- In Zeitwerk gestartete Übersteuerungen werden in Heizwerk angezeigt
  (`manual_source`).
- Räume im Modus „Nur beobachten“ schreiben nie ins Zeitwerk-Ziel.

## 0.1.1 – 2026-11-18

- Fix: entity pickers in the Heizwerk options and the room dialog showed
  "no entities available" (an empty `device_class` filter hid every entity).
- Outdoor temperature no longer offers `weather` entities (their state is not a
  number).

Deutsch:

- Behoben: Die Entitätsauswahl in den Heizwerk-Optionen und im Raumdialog
  zeigte „keine Entitäten verfügbar“ (ein leerer `device_class`-Filter blendete
  jede Entität aus).
- Außentemperatur bietet keine `weather`-Entitäten mehr an (ihr Zustand ist
  keine Zahl).

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

Deutsch:

- Integration `heizwerk` (HA ≥ 2026.11): ein Eintrag mit Hausoptionen, Räume als
  Config-Subentries („Raum hinzufügen“).
- `climate.heizwerk_<raum>`: Ziel aus einer Zeitwerk-Ziel-Entität, externer
  Raumfühler, Korrektur, Regelung Sollwert oder Offset, 10 s Entprellung, nur
  abweichende Befehle werden gesendet.
- Sperren: Fenster (Verzögerungen beim Öffnen/Schließen), Heizperiode,
  Sommerabschaltung (außen ≥ 16 °C für 10 min), weitere Sperr-Entitäten;
  Sperrmodus Thermostat aus oder Frostschutz.
- Manuelle Übersteuerung bis zum nächsten Zeitwerk-Wechsel oder für eine Dauer
  (`heizwerk.set_manual`, `heizwerk.resume`, `heizwerk.sync`).
- Modus „Nur beobachten“ (Standard für neue Räume) mit geplanten Befehlen als
  Attribut.
- Raumklima: Taupunkt, Wandfeuchte / Schimmelstufe, Lüftungsempfehlung,
  Ereignisse `heizwerk_event` (`ventilation_done`, `trv_unavailable`).
- Karte `custom:heizwerk-card`: Varianten Standard (Kreisanzeige, Raumklima,
  Zeitwerk-Tagesband) und Kompakt (Kachel, Hausliste), hell/dunkel, de/en,
  visueller Editor.
