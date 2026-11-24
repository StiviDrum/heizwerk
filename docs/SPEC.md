# Heizwerk – Spezifikation

> Deutsch (maßgebliche Fassung) · [English](SPEC.en.md)
>
> Sprache: Deutsch. Code, Kommentare, Bezeichner, Commits: Englisch.
> Stand: Version 0.5.2 (2026-11-24) · Mindestversion Home Assistant **2026.11**

## 1. Idee

**Zeitwerk plant, Heizwerk regelt.** Ein Zeitplan (Zeitwerk, Scheduler,
Automation) entscheidet, *welche* Solltemperatur gerade gilt, und setzt sie per
`climate.set_temperature`. Heizwerk setzt sie pro Raum an den
Heizkörperthermostaten (TRV) um und kümmert sich um alles, was zwischen „Sollwert
steht fest“ und „Ventil macht auf“ passiert:

- externer Raumfühler statt TRV-Eigenmessung, Raumtemperatur an die TRVs senden
- Regelart Sollwert (TRV regelt selbst), Zweipunkt (Ventil auf/zu) oder Offset
- **Sperren**: Fenster offen, Heizperiode aus, Sommerabschaltung (Hauswert, pro
  Raum überschreibbar), frei wählbare Sperr-Entitäten
- manuelle Übersteuerung (Karte, Dienst, Drehen am Thermostat) mit Dauer,
  „Fortsetzen“ über eine frei wählbare Aktion
- Schutz vor falschen Thermostat-Meldungen (veraltete Werte, Sprünge,
  Befehle, die ein Thermostat nicht übernimmt)
- Raumklima: Feuchte, Taupunkt, Wandfeuchte bzw. Schimmel-Indikator, Lüften
- **Nur beobachten**: Heizwerk rechnet alles, schickt aber nichts an die TRVs

Ziel ab 0.5: die bisherigen Heizungs-Automationen vollständig ablösen können.

Abgrenzung: Heizwerk plant nicht (kein Wochenplan, keine Profile) – das bleibt
Zeitwerk. Heizwerk erinnert nicht (keine Push-Ketten) – das bleibt Läutwerk.

## 2. Schnittstellen zu Zeitwerk und Läutwerk (gelesen am 2026-11-18)

Quelle: Repos `~/zeitwerk` (1.0.0-rc.11) und `~/laeutwerk` (0.11.4), abgeglichen
mit der installierten Zeitwerk-Instanz (nur lesend). Heizwerk nutzt **nur
öffentliche Schnittstellen** (Zustände, Attribute, WebSocket, Dienste), keine
Interna.

### 2.1 Zeitplan → Heizwerk (ab 0.4, Entscheidung Steven 2026-11-18)

**Heizwerk ist ein normales Thermostat, der Zeitplan nur die Fernbedienung.**

| Schnittstelle | Bedeutung |
|---|---|
| `climate.set_temperature` auf `climate.heizwerk_<raum>` | Einzige Eingabe: neuer Sollwert. Von Zeitwerk-Profilaktion, Scheduler, Automation oder Hand. Beendet eine Übersteuerung aus der Heizwerk-Karte. |
| Raumoption `resume_action` (HA-Aktionen) | Läuft bei „Fortsetzen“ und am Ende einer Übersteuerung mit Dauer. Leer + Zeitwerk-Plan bekannt → `zeitwerk.resume {plan}`. Leer ohne Plan → Fortsetzen/Dauer ausgeblendet. Scheduler: z. B. `scheduler.run_action`. |
| `sensor.zeitwerk_<plan>_profile` (`profile_id`, `source`, `manual_override`, `manual_until`), `sensor.zeitwerk_<plan>_next_change` (`next_profile_name`) | Nur Anzeige: Profil, „bis …“, und „manuell“, wenn Zeitwerk eine Änderung außerhalb der Karte erkannt hat. |
| WebSocket `zeitwerk/plans/get`, `zeitwerk/preview` → `{plans: {plan_id: [...]}}` | Karte: Profilwerte (Aktionen auf `climate.heizwerk_<raum>`) und Tagesband. |
| Dienst `zeitwerk.get_plan` | Automatische Plan-Erkennung: der Plan, dessen Profilaktionen `climate.heizwerk_<raum>` setzen. Ab 0.5.2 zusätzlich: niedrigster Profilwert dieses Raums als automatische Untergrenze für Drehen am Thermostat (4.5). |

Zeitwerk erkennt Änderungen der Heizwerk-Karte selbst als manuelle Übersteuerung
(fremder Context am beobachteten Attribut `temperature`) und beendet sie beim
nächsten Block. Sperren (Fenster usw.) ändern den Sollwert nicht – kein
Fehlalarm in Zeitwerk. Bis 0.3 gab es ein „Zeitwerk-Ziel“ (Helfer); ein alter
Wert wird ignoriert und als Reparaturhinweis gemeldet.

### 2.2 Heizwerk → Läutwerk und Automationen (lose gekoppelt)

Heizwerk ruft Läutwerk nicht auf. Läutwerk-Regeln bzw. Automationen reagieren auf
Heizwerk-Zustände und -Ereignisse. Jedes Ereignis `heizwerk_event` enthält
`type`, `room` (Raumname) und `entity_id` (`climate.heizwerk_<raum>`):

| `type` | weitere Felder | Wann | Beispiel |
|---|---|---|---|
| `ventilation_done` | `minutes` | Fenster offen ≥ empfohlene Lüftungsdauer (einmal pro Öffnung) | Automation → `laeutwerk.trigger` (Regel „Fenster schließen“) |
| `trv_unavailable` | `trvs` (Liste) | ein TRV seit 5 min nicht verfügbar | Erinnerung „TRV prüfen“ |
| `knob_adopted` (ab 0.5.2) | `result`, `reason`, `trv`, `value`, `before`, `delta`, `target`, `seconds_since_command` | Drehen am Thermostat als manuelle Übersteuerung übernommen | Protokoll, Nachverfolgung |
| `knob_rejected` (ab 0.5.2) | wie oben; `reason` = `after_own_command`, `stale_value`, `two_point`, `reset_mode`, `jump` oder `below_minimum`; `target` leer | Sollwertänderung am Thermostat verworfen, Heizwerk sendet seinen Wert erneut | Fehlersuche bei Thermostaten |

Feldbedeutung bei `knob_*`: `trv` = Thermostat, `value` = gemeldeter Sollwert,
`before` = Sollwert davor, `delta` = `value − before` (K), `target` =
übernommener Raum-Sollwert, `seconds_since_command` = Sekunden seit dem letzten
eigenen Befehl an dieses Thermostat (leer, wenn keiner bekannt), `result` =
`adopted`/`rejected`.

Außerdem: `binary_sensor.heizwerk_<raum>_ventilation` (Lüften empfohlen) –
Gelegenheit/Quittierung über Fensterkontakt.

Läutwerk-Dienste zur Referenz: `laeutwerk.trigger` {rule}, `acknowledge`,
`snooze`, `get_rules`.

## 3. Datenmodell

### 3.1 Integrations-Eintrag (einmalig, Optionen änderbar)

| Option | Bedeutung | Standard | Bereich |
|---|---|---|---|
| `outdoor_temperature` | Außentemperatur-Sensor (`sensor`, `input_number`; keine `weather`-Entitäten) | – | – |
| `outdoor_humidity` | Außenfeuchte (für Taupunkt außen) | – | – |
| `season_entity` | Heizperiode (`off` = gesperrt; `input_boolean`, `binary_sensor`, `switch`, `schedule`) | – | – |
| `summer_lock_temperature` | Sommerabschaltung ab … °C (0 = aus) | 16 | 0–30 |
| `summer_lock_minutes` | … wenn so lange überschritten (min) | 10 | 0–240 |

### 3.2 Raum (Config-Subentry `room`, über „Raum hinzufügen“)

Dialog: oben Name, Thermostate, Raumfühler, Nur beobachten; darunter zugeklappte
Abschnitte. Auswahlfelder als Klappliste (HA 2026.11 zeichnet Radio-Punkte
versetzt). Felder erscheinen nur, wenn sie wirken (HA-Sichtbarkeitsbedingungen);
ein ausgeblendetes Feld behält beim Speichern seinen gespeicherten Wert bzw. den
Standard. Gespeichert wird flach (Schlüssel wie unten).

| Abschnitt | Option | Bedeutung | Standard | Bereich |
|---|---|---|---|---|
| oben | `name` | Raumname → `climate.heizwerk_<slug>` | – | – |
| oben | `trvs` | Thermostate (`climate`, mehrere; Heizwerk-Entitäten nicht wählbar) | – | – |
| oben | `temperature_sensor` | Raumfühler; ohne: Mittel der TRV-Messungen | – | – |
| oben | `observe_only` | **Nur beobachten** | **an** | – |
| Plan & Fortsetzen | `zeitwerk_plan` | Plan für Anzeige; automatisch erkannt (Plan, der `climate.heizwerk_<raum>` setzt) | – | – |
| Plan & Fortsetzen | `resume_action` | HA-Aktionen für „Fortsetzen“ und Dauer-Ende; leer + Plan → `zeitwerk.resume` | – | – |
| Raumklima | `humidity_sensor` | Feuchte (Taupunkt, Lüften) | – | – |
| Raumklima | `mold_sensor` | Schimmel-Indikator: Wandfeuchte in % direkt | – | – |
| Raumklima | `wall_temperature_sensor` | Wandoberfläche °C/°F (nur ohne `mold_sensor`) | – | – |
| Raumklima | `humidity_threshold` | Lüften empfohlen ab % | 60 | 30–95 |
| Fenster & Sperren | `windows`, `window_open_delay`, `window_close_delay` | Fenster, Sekunden bis Sperre / Freigabe | – / 30 / 10 | 0–900 s |
| Fenster & Sperren | `lock_entities` | weitere Sperren (`on`/`true`/`open` sperrt) | – | – |
| Fenster & Sperren | `lock_mode`, `frost_temperature` | Sperre = TRV `off` oder heat auf Frostschutz (Frostschutz-Feld nur bei `frost`) | `off` / 7 | 4–12 °C |
| Fenster & Sperren | `outdoor_limit` | Sommerabschaltung ab … °C für diesen Raum (0 = keine) | Hauswert | 0–30 |
| Regelung | `regulation` | `setpoint`, `two_point` oder `offset` | `setpoint` | – |
| Regelung | `send_temperature` | Raumtemperatur an die TRVs senden (nur mit Raumfühler) | an (neue Räume) | – |
| Regelung | `correction` | Korrektur in K auf den TRV-Sollwert | 0 | −5…5 K |
| Regelung | `hysteresis_low` | nur Zweipunkt: an unter Soll − Wert | 0,5 | 0…3 K |
| Regelung | `hysteresis_high` | nur Zweipunkt: aus ab Soll + Wert; negativ = schon vor dem Soll aus | 0 | −2…3 K |
| Regelung | `heat_setpoint` | nur Zweipunkt: TRV-Sollwert beim Heizen | 24 | 5–35 °C |
| Regelung | `min_on_minutes` (ab 0.5.2) | nur Zweipunkt: Mindestlaufzeit Ventil, 0 = aus | 0 | 0–60 min |
| Regelung | `min_off_minutes` (ab 0.5.2) | nur Zweipunkt: Mindestpause Ventil, 0 = aus | 0 | 0–60 min |
| Regelung | `trv_manual` | Drehen am Thermostat: `adopt` (übernehmen) oder `reset`; bei Zweipunkt ausgeblendet (immer zurücksetzen) | `adopt` | – |
| Regelung | `knob_min_temperature` (ab 0.5.2) | Handwerte am Thermostat ab … °C; leer = automatisch (niedrigster Zeitwerk-Profilwert des Raums, sonst `min_temp`); nur bei `adopt` und nicht Zweipunkt | leer | 5–25 °C |
| Sollwerte & Grenzen | `default_target` | Start-Sollwert bis zum ersten Wert | 20 | 5–30 °C |
| Sollwerte & Grenzen | `min_temp` / `max_temp` | Bereich | 5 / 30 | 4–30 / 5–35 °C |

Prüfungen beim Speichern: Name nicht leer und eindeutig, mindestens ein
Thermostat, keine Heizwerk-Entität als Thermostat, `min_temp` < `max_temp`,
`offset` nicht zusammen mit `send_temperature`, Zweipunkt nur mit Raumfühler und
mit `hysteresis_low` + `hysteresis_high` ≥ 0,2 K, Wandtemperatur-Sensor nur mit
°C/°F (ohne Einheit erlaubt), gültige Fortsetzen-Aktion.

Altdaten: `target_entity` (bis 0.3) wird ignoriert und als Reparaturhinweis
gemeldet; `external_temperature_entities` (bis 0.4) bleibt wirksam, solange
`send_temperature` an ist.

Neue Räume starten **immer** im Modus „Nur beobachten“ (Abschnitt 1.4 der
Hausregeln: Heizungssteuerung nur mit Freigabe).

## 4. Regelung

### 4.1 Sollwert

```
Sollwert = zuletzt empfangener Wert (climate.set_temperature / heizwerk.set_manual),
           beim allerersten Start der Start-Sollwert (default_target)
manuell  = über Heizwerk-Karte/heizwerk.set_manual oder Drehen am Thermostat gesetzt,
           bis zum nächsten Wert von außen, „Fortsetzen“ oder Ablauf der Dauer
           (dann resume_action); zusätzlich „manuell“, wenn Zeitwerk eine
           Übersteuerung meldet
```

### 4.2 Status (Priorität von oben)

| Status | Bedingung | TRV-Befehl |
|---|---|---|
| `off` | Raum per `hvac_mode: off` ausgeschaltet | `off` |
| `unavailable` | alle TRVs `unavailable`/`unknown` | – (nichts senden) |
| `window` | Fenster länger als `window_open_delay` offen | Sperre |
| `season` | Heizperiode aus | Sperre |
| `summer` | außen ≥ Schwelle seit `summer_lock_minutes` | Sperre |
| `locked` | eine Sperr-Entität aktiv | Sperre |
| `manual` | manuelle Übersteuerung aktiv | wie Regelart |
| `heating` | Sollwert: Ist < Soll − 0,2 K oder TRV meldet `heating`; Zweipunkt: an | Sollwert: heat, Soll · Zweipunkt: heat, `heat_setpoint` |
| `reached` | sonst | Sollwert: heat, Soll · Zweipunkt: off |

Sperre = `hvac_mode: off` (`lock_mode: off`) bzw. heat auf `frost_temperature`.
Sperren und „Raum aus“ wirken immer sofort, auch während einer Mindestlaufzeit
oder -pause der Zweipunkt-Regelung; danach gilt keine Haltezeit aus der Zeit
davor (nach dem Lüften öffnet das Ventil sofort).

### 4.3 Befehle

- `setpoint`/`offset`: TRV-Soll = wirksam + `correction` (+ TRV-Ist − Raum-Ist,
  ±5 K, bei `offset`), auf Schrittweite des TRV gerundet und begrenzt.
- `two_point`: siehe 4.5.
- Entprellung 10 s: Änderungen werden gesammelt, dann einmal ausgewertet.
- Gesendet wird nur, was vom TRV-Zustand abweicht (kein Dauerfeuer).
- Abgleich alle 5 min, solange Befehle ausstehen; Neubewertung nach HA-Start.
- **Kein Senden während des HA-Starts (ab 0.5.2)**: Befehle gehen erst an die
  Thermostate, wenn Home Assistant vollständig gestartet ist (Thermostate stellen
  ihren Zustand oft erst spät wieder her); danach wird sofort neu bewertet.
- **Wiederholungsgrenze (ab 0.5.2)**: derselbe Befehl (Modus + Temperatur) geht
  an ein Thermostat höchstens 3-mal innerhalb von 10 Minuten (gerechnet ab dem
  ersten Senden). Danach pausiert Heizwerk für dieses Thermostat bis zum Ende
  des 10-Minuten-Fensters, schreibt eine Warnung ins Log und meldet den
  Reparaturhinweis `trv_rejects_command` („Thermostat übernimmt den Befehl
  nicht“). Zähler und Hinweis verschwinden, sobald das Thermostat den Wert
  2 Minuten lang hält (ein Thermostat, das den Wert kurz übernimmt und sofort
  zurückspringt, setzt den Zähler nicht zurück). Es zählen nur Meldungen des
  Geräts selbst (`after_own_command`, `stale_value`, `jump` – ein Sprung über 5 K ist ein
  Gerät, das sich zurücksetzt); verwirft Heizwerk ein
  Drehen durch eine Person (`two_point`, `reset_mode`, `below_minimum`), wird der Zähler zurückgesetzt und ein Hinweis entfernt.
  Beim Start bzw. Neuladen der Integration werden alle Hinweise
  `trv_rejects_command` entfernt.
- Externe Temperatur: siehe 4.5 (`send_temperature`).
- **Nur beobachten**: Befehle werden berechnet und als `planned_commands`
  angezeigt, aber nicht gesendet.
- `last_sync` = Zeit der letzten (gesendeten bzw. geplanten) Befehlsrunde.

### 4.4 Raumklima

- Taupunkt (Magnus, a = 17,62, b = 243,12 °C) aus Raum-Ist und Feuchte; außen analog.
- Wandfeuchte = relative Feuchte an der Wand: 100 · E(Taupunkt) / E(Wand),
  höchstens 100 %. Stufe `ok` < 70 %, `warning` ≥ 70 %, `alarm` ≥ 80 %.
- Lüftungsdauer nach Außentemperatur: < 0 °C 5 min, < 10 °C 10 min,
  < 15 °C 15 min, < 20 °C 20 min, sonst 25 min; ohne Außenwert 10 min.
- Fenster offen ≥ empfohlene Dauer → `ventilation_done` (Ereignis einmal pro Öffnung).
- Lüften empfohlen: Feuchte ≥ `humidity_threshold` und (Taupunkt außen oder
  innen unbekannt oder außen ≥ 1 K unter innen) und Fenster zu.

### 4.5 Thermostat-Funktionen (ab 0.5)

| Funktion | Verhalten |
|---|---|
| Raumtemperatur senden (`send_temperature`) | Eingänge `number.…_external_temperature_input` am Gerät jedes TRV (entity_id/unique_id), Wert des Raumfühlers bei ≥ 0,1 K Änderung, sonst alle 30 min. Nur mit Raumfühler, nicht bei „Nur beobachten“. Alte explizite Eingänge bleiben, solange Senden an ist. Ohne gespeicherten Schlüssel: an, wenn alte Eingänge existieren. |
| Messquelle (`…_temperature_sensor_select`) | Reparaturhinweis `sensor_select_not_remote` nach 5 min ≠ `remote_temperature` (nicht verfügbar/unbekannt zählen nicht). Kein automatisches Umstellen. |
| Zweipunkt (`regulation: two_point`) | an bei Ist < Soll − `hysteresis_low`, aus ab Ist ≥ Soll + `hysteresis_high`, dazwischen wie zuvor; an = heat auf `heat_setpoint` (24 °C), aus = off. `hysteresis_high` darf negativ sein (−2…3 K, aus schon vor dem Soll, gegen Überschwingen); `hysteresis_low` + `hysteresis_high` ≥ 0,2 K. Optional Mindestlaufzeit/-pause (`min_on_minutes`/`min_off_minutes`, 0 = aus): nach einem Wechsel bleibt das Ventil so lange an bzw. aus; Fenster, Sperren und Raum aus wirken trotzdem sofort, und nach einem erzwungenen Zustand (Sperre, Raum aus, fehlende Raumtemperatur) gilt keine Haltezeit – nach dem Lüften öffnet das Ventil sofort. Nur mit Raumfühler. Ventilzustand nach Neustart aus der ersten verfügbaren Thermostat-Meldung (auch schon während des HA-Starts): steht ein verfügbares TRV nicht auf `off` und weniger als 0,6 K von `heat_setpoint` entfernt, gilt das Ventil als an. Fehlt die Raumtemperatur, bekommt der TRV ersatzweise das Raum-Soll (er regelt dann selbst), bis der Fühler wieder liefert. |
| Außengrenze pro Raum (`outdoor_limit`) | ersetzt den Hauswert; 0 = keine Sommerabschaltung für den Raum. |
| Drehen am Thermostat (`trv_manual`, `knob_min_temperature`) | Eine Sollwertänderung, die ein TRV meldet, wird in dieser Reihenfolge geprüft. **Still ignoriert** (kein Ereignis): „Nur beobachten“, Heizwerk sendet gerade, Raum aus, Sperre aktiv, TRV gerade wieder verfügbar bzw. vorher/nachher nicht verfügbar, TRV meldet `off`, Kontext mit Elternteil (Automation/Skript), Sollwert unverändert, Wert gleich dem Sollwert, den Heizwerk gerade für dieses Thermostat will (das Thermostat stimmt zu), Echo des eigenen Befehls (gleicher Wert innerhalb 30 s). **Verworfen** (`knob_rejected`, Heizwerk sendet seinen Wert erneut): `after_own_command` – jede andere Meldung innerhalb von 30 s nach einem eigenen Befehl (Modus oder Sollwert); `stale_value` – Wert gleich dem Sollwert des TRV vor Heizwerks letztem Befehl, innerhalb von 5 Minuten nach diesem Befehl; `two_point` – bei Zweipunkt immer (der Drehknopf zeigt den Heiz-Sollwert, nicht die Raumtemperatur); `reset_mode` – `trv_manual: reset`; `jump` – Änderung um mehr als 5 K in einer Meldung; `below_minimum` – zurückgerechneter Raum-Sollwert (vor dem Begrenzen auf `min_temp`…`max_temp`) unter der Untergrenze (`knob_min_temperature`, leer = niedrigster Zeitwerk-Profilwert dieses Raums, sonst `min_temp`). **Übernommen** (`knob_adopted`): Raum-Sollwert = Wert − `correction` (bei `offset` zusätzlich − (TRV-Ist − Raum-Ist), ±5 K), auf 0,5 K gerundet, auf `min_temp`…`max_temp` begrenzt; ist er gleich dem aktuellen Sollwert, passiert nichts, sonst manuelle Übersteuerung (Quelle `thermostat`) bis zum nächsten Wert. Jede Entscheidung „übernommen/verworfen“ wird im Log (Info) protokolliert, als `heizwerk_event` gemeldet (2.2) und im Attribut `last_knob` abgelegt. |
| Schimmel-Indikator (`mold_sensor`) | Wert = Wandfeuchte (%), `estimated_critical_temp` = kritische Wandtemperatur; hat Vorrang vor dem Wandtemperatur-Sensor (der nur °C/°F akzeptiert). |

Hintergrund zu 0.5.2: Ein Zigbee2MQTT-Thermostat, das Heizwerk bei Zweipunkt auf
heat (30 °C) schaltete, meldete 0,15–0,25 s später in einer eigenen Nachricht
seinen vorher gespeicherten Sollwert (z. B. 18 °C). 0.5.1 hielt das für Drehen am
Thermostat und behielt bis zum nächsten Zeitplanwechsel einen manuellen Wert von
6 °C. Das Standardverhalten ist sonst unverändert; die neuen Optionen sind
freiwillig.

## 5. Entitäten pro Raum (Gerät „Heizwerk <Raum>“)

| Entität | Inhalt |
|---|---|
| `climate.heizwerk_<raum>` | Modi `heat`/`off`, Ist = Raumfühler, Soll = wirksam (Schritt 0,5 K), `current_humidity`, `hvac_action` |
| `sensor.heizwerk_<raum>_dew_point` | Taupunkt (°C), nur mit Feuchtesensor |
| `sensor.heizwerk_<raum>_wall_humidity` | Wandfeuchte (%), mit Schimmel-Indikator oder Feuchte- + Wandsensor |
| `binary_sensor.heizwerk_<raum>_ventilation` | Lüften empfohlen |
| `switch.heizwerk_<raum>_observe_only` | Nur beobachten (Konfiguration) |

Attribute von `climate.heizwerk_<raum>` (Schnittstelle zur Karte):

`room_name`, `status`, `locks` [{type (`window`/`season`/`summer`/`entity`),
since, entity_ids (nur bei `entity`)}], `manual_target`, `manual_mode`
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
`last_knob` (ab 0.5.2: {time, result, reason, trv, value, before, delta,
target, seconds_since_command} der letzten Entscheidung zu Drehen am
Thermostat, sonst leer), `external_inputs`, `wall_humidity`, `mold_level`,
`outdoor_temperature`, `outdoor_dew_point`, `season_active`,
`humidity_threshold`.

## 6. Dienste, Ereignisse, Reparaturhinweise

| Dienst | Felder |
|---|---|
| `heizwerk.set_manual` | `entity_id`, `temperature`, `duration` (optional, nur mit Fortsetzen-Aktion; ohne = bis zum nächsten Wert) |
| `heizwerk.resume` | `entity_id` – beendet die Übersteuerung und führt die Fortsetzen-Aktion aus |
| `heizwerk.sync` | `entity_id` – sofort neu auswerten und ausstehende Befehle senden (bei „Nur beobachten“ nur neu berechnen) |

Ereignis `heizwerk_event` mit `type` `ventilation_done`, `trv_unavailable`,
`knob_adopted` oder `knob_rejected` – Felder siehe 2.2.

| Reparaturhinweis | Wann | Verschwindet |
|---|---|---|
| `target_entity_removed` | Raum hat noch ein Zeitwerk-Ziel aus 0.3 | nach Umstellen und erneutem Speichern des Raums |
| `sensor_select_not_remote` | Messquelle eines TRV 5 min ≠ `remote_temperature` | sobald die Messquelle wieder stimmt |
| `trv_rejects_command` (ab 0.5.2) | derselbe Befehl 3-mal in 10 min nicht übernommen | sobald das TRV den Wert 2 min hält, wenn Heizwerk ein Drehen durch eine Person verwirft, oder beim Start/Neuladen der Integration |

## 7. Karte `custom:heizwerk-card`

```yaml
type: custom:heizwerk-card
variant: standard        # standard | compact
entity: climate.heizwerk_bad
# compact mit Hausliste:
# entities: [climate.heizwerk_bad, climate.heizwerk_kueche]
title: Heizung           # Hausliste
dial_min: 12
dial_max: 26
manual_duration: next    # next | 60 | 180 (Minuten) – Standard für ± in der Standardkarte
```

- **Standard** (Mockup `mockups/heizwerk-karte-standard.html`, ab 0.5.1 vereinfacht):
  Kopf nur Raumname + ⋯ (Mehr-Info), Zustands-Chip, Dial Ist/Ziel, ± Ziel,
  nächster Wechsel, Hinweis (Lüften/Schimmel), Raumklima (Feuchte, Taupunkt,
  Wandfeuchte), Tagesband mit Titel „Heute · Plan <Name>“, Fußzeile nur bei
  Bedarf (Abgleich, Zweipunkt, Nur beobachten, Warnung „Raumfühler fehlt“).
- **Kompakt** (ab 0.5.1, volle Breite): je Raum Status-Symbol, Name mit Status,
  Ist groß + Ziel, − / + nebeneinander (44 px), darunter eine Infozeile (Fenster
  bzw. „Manuell bis …“, Feuchte, nächster Wechsel, Lüften) und ein Balken
  Ist → Ziel. `entity` → Einzelkarte, `entities` → Hausliste mit Kopf
  (Heizperiode, Außen, offene Fenster). Antippen klappt Dauer-Pillen „Bis
  nächster Block / 1 Std. / 3 Std.“ und Fortsetzen auf (nur mit
  Fortsetzen-Aktion), sonst öffnet es den Mehr-Info-Dialog.
- Standard: Ziel am Kreis ziehbar (Touch/Maus, 0,5 K, Senden beim Loslassen),
  Tastatur (Pfeile, Bild auf/ab), ARIA-Slider.
- Nutzt HA-Theme-Variablen, hell/dunkel, Touch-Ziele ≥ 44 px, kein Hover-Zwang,
  Übersetzungen de/en, freundlicher Fehlerzustand ohne `hass`/Entität.
- Karte wird von der Integration selbst registriert (statischer Pfad +
  `add_extra_js_url`), keine manuelle Ressource.

## 8. Nicht-Ziele

- Kein eigener Zeitplan, keine Profile (Zeitwerk).
- Kein Vorheizen/Lernen („Vorlauf ab …“ aus dem Mockup) – vorgemerkt für später.
- Keine Push-Benachrichtigungen (Läutwerk).
