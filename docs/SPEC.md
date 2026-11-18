# Heizwerk – Spezifikation

> Sprache: Deutsch. Code, Kommentare, Bezeichner, Commits: Englisch.
> Stand: Version 0.5.1 (2026-11-18) · Mindestversion Home Assistant **2026.11**

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
| `sensor.zeitwerk_<plan>_profile` (`profile_id`, `manual_override`, `manual_until`), `sensor.zeitwerk_<plan>_next_change` | Nur Anzeige: Profil, „bis …“, und „manuell“, wenn Zeitwerk eine Änderung außerhalb der Karte erkannt hat. |
| WebSocket `zeitwerk/plans/get`, `zeitwerk/preview` → `{plans: {plan_id: [...]}}` | Karte: Profilwerte (Aktionen auf `climate.heizwerk_<raum>`) und Tagesband. |
| Dienst `zeitwerk.get_plan` | Automatische Plan-Erkennung: der Plan, dessen Profilaktionen `climate.heizwerk_<raum>` setzen. |

Zeitwerk erkennt Änderungen der Heizwerk-Karte selbst als manuelle Übersteuerung
(fremder Context am beobachteten Attribut `temperature`) und beendet sie beim
nächsten Block. Sperren (Fenster usw.) ändern den Sollwert nicht – kein
Fehlalarm in Zeitwerk. Bis 0.3 gab es ein „Zeitwerk-Ziel“ (Helfer); ein alter
Wert wird ignoriert und als Reparaturhinweis gemeldet.

### 2.2 Heizwerk → Läutwerk (lose gekoppelt)

Heizwerk ruft Läutwerk nicht auf. Läutwerk-Regeln bzw. Automationen reagieren auf
Heizwerk-Zustände und -Ereignisse:

| Heizwerk liefert | Beispiel in Läutwerk |
|---|---|
| Ereignis `heizwerk_event` mit `type: ventilation_done`, `room`, `entity_id` | Automation → `laeutwerk.trigger` (Regel „Fenster schließen“) |
| Ereignis `heizwerk_event` mit `type: trv_unavailable` (nach 5 min) | Erinnerung „TRV prüfen“ |
| `binary_sensor.heizwerk_<raum>_ventilation` (Lüften empfohlen) | Gelegenheit/Quittierung über Fensterkontakt |

Läutwerk-Dienste zur Referenz: `laeutwerk.trigger` {rule}, `acknowledge`,
`snooze`, `get_rules`.

## 3. Datenmodell

### 3.1 Integrations-Eintrag (einmalig, Optionen änderbar)

| Option | Bedeutung | Standard |
|---|---|---|
| `outdoor_temperature` | Außentemperatur-Sensor | – |
| `outdoor_humidity` | Außenfeuchte (für Taupunkt außen) | – |
| `season_entity` | Heizperiode (`on` = Heizperiode aktiv) | – |
| `summer_lock_temperature` | Sommerabschaltung ab … °C (0 = aus) | 16 |
| `summer_lock_minutes` | … wenn so lange überschritten | 10 |

### 3.2 Raum (Config-Subentry `room`, über „Raum hinzufügen“)

Dialog: oben Name, Thermostate, Raumfühler, Nur beobachten; darunter zugeklappte
Abschnitte. Auswahlfelder als Klappliste (HA 2026.11 zeichnet Radio-Punkte
versetzt). Felder erscheinen nur, wenn sie wirken (HA-Sichtbarkeitsbedingungen).
Gespeichert wird flach (Schlüssel wie unten).

| Abschnitt | Option | Bedeutung | Standard |
|---|---|---|---|
| oben | `name` | Raumname → `climate.heizwerk_<slug>` | – |
| oben | `trvs` | Thermostate (`climate`, mehrere; Heizwerk-Entitäten nicht wählbar) | – |
| oben | `temperature_sensor` | Raumfühler; ohne: Mittel der TRV-Messungen | – |
| oben | `observe_only` | **Nur beobachten** | **an** |
| Plan & Fortsetzen | `zeitwerk_plan` | Plan für Anzeige; automatisch erkannt (Plan, der `climate.heizwerk_<raum>` setzt) | – |
| Plan & Fortsetzen | `resume_action` | HA-Aktionen für „Fortsetzen“ und Dauer-Ende; leer + Plan → `zeitwerk.resume` | – |
| Raumklima | `humidity_sensor` | Feuchte (Taupunkt, Lüften) | – |
| Raumklima | `mold_sensor` | Schimmel-Indikator: Wandfeuchte in % direkt | – |
| Raumklima | `wall_temperature_sensor` | Wandoberfläche °C/°F (nur ohne `mold_sensor`) | – |
| Raumklima | `humidity_threshold` | Lüften empfohlen ab % | 60 |
| Fenster & Sperren | `windows`, `window_open_delay`, `window_close_delay` | Fenster, Sekunden bis Sperre / Freigabe | – / 30 / 10 |
| Fenster & Sperren | `lock_entities` | weitere Sperren (`on`/`true`/`open` sperrt) | – |
| Fenster & Sperren | `lock_mode`, `frost_temperature` | Sperre = TRV `off` oder heat auf Frostschutz | `off` / 7 |
| Fenster & Sperren | `outdoor_limit` | Sommerabschaltung ab … °C für diesen Raum (0 = keine) | Hauswert |
| Regelung | `regulation` | `setpoint`, `two_point` oder `offset` | `setpoint` |
| Regelung | `send_temperature` | Raumtemperatur an die TRVs senden (nur mit Raumfühler) | an (neue Räume) |
| Regelung | `correction` | Korrektur in K auf den TRV-Sollwert | 0 |
| Regelung | `hysteresis_low`, `hysteresis_high`, `heat_setpoint` | nur Zweipunkt | 0,5 / 0 / 24 |
| Regelung | `trv_manual` | Drehen am Thermostat: `adopt` (übernehmen) oder `reset` | `adopt` |
| Sollwerte & Grenzen | `default_target` | Start-Sollwert bis zum ersten Wert | 20 |
| Sollwerte & Grenzen | `min_temp` / `max_temp` | Bereich | 5 / 30 |

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
manuell  = über Heizwerk-Karte/heizwerk.set_manual gesetzt, bis zum nächsten Wert
           von außen, „Fortsetzen“ oder Ablauf der Dauer (dann resume_action);
           zusätzlich „manuell“, wenn Zeitwerk eine Übersteuerung meldet
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

### 4.3 Befehle

- `setpoint`/`offset`: TRV-Soll = wirksam + `correction` (+ TRV-Ist − Raum-Ist,
  ±5 K, bei `offset`), auf Schrittweite des TRV gerundet und begrenzt.
- `two_point`: siehe 4.5.
- Entprellung 10 s: Änderungen werden gesammelt, dann einmal ausgewertet.
- Gesendet wird nur, was vom TRV-Zustand abweicht (kein Dauerfeuer).
- Abgleich alle 5 min, solange Befehle ausstehen; Neubewertung nach HA-Start.
- Externe Temperatur: siehe 4.5 (`send_temperature`).
- **Nur beobachten**: Befehle werden berechnet und als `planned_commands`
  angezeigt, aber nicht gesendet.
- `last_sync` = Zeit der letzten (gesendeten bzw. geplanten) Befehlsrunde.

### 4.4 Raumklima

- Taupunkt (Magnus, a = 17,62, b = 243,12 °C) aus Raum-Ist und Feuchte; außen analog.
- Wandfeuchte = relative Feuchte an der Wand: 100 · E(Taupunkt) / E(Wand).
  Stufe `ok` < 70 %, `warning` ≥ 70 %, `alarm` ≥ 80 %.
- Lüftungsdauer nach Außentemperatur: < 0 °C 5 min, < 10 °C 10 min,
  < 15 °C 15 min, < 20 °C 20 min, sonst 25 min.
- Fenster offen ≥ empfohlene Dauer → `ventilation_done` (Ereignis einmal pro Öffnung).
- Lüften empfohlen: Feuchte ≥ `humidity_threshold` und (Taupunkt außen unbekannt
  oder ≥ 1 K unter Taupunkt innen) und Fenster zu.

### 4.5 Thermostat-Funktionen (ab 0.5)

| Funktion | Verhalten |
|---|---|
| Raumtemperatur senden (`send_temperature`) | Eingänge `number.…_external_temperature_input` am Gerät jedes TRV (entity_id/unique_id), Wert des Raumfühlers bei ≥ 0,1 K Änderung, sonst alle 30 min. Nur mit Raumfühler, nicht bei „Nur beobachten“. Alte explizite Eingänge bleiben, solange Senden an ist. Ohne gespeicherten Schlüssel: an, wenn alte Eingänge existieren. |
| Messquelle (`…_temperature_sensor_select`) | Reparaturhinweis `sensor_select_not_remote` nach 5 min ≠ `remote_temperature` (nicht verfügbar/unbekannt zählen nicht). Kein automatisches Umstellen. |
| Zweipunkt (`regulation: two_point`) | an bei Ist < Soll − `hysteresis_low`, aus ab Ist ≥ Soll + `hysteresis_high`, dazwischen wie zuvor; an = heat auf `heat_setpoint` (24 °C), aus = off. Nur mit Raumfühler, Summe Hysterese ≥ 0,2 K. Zustand nach Neustart aus den TRVs. |
| Außengrenze pro Raum (`outdoor_limit`) | ersetzt den Hauswert; 0 = keine Sommerabschaltung für den Raum. |
| Drehen am Thermostat (`trv_manual`) | `adopt`: Sollwertänderung am TRV = manuelle Übersteuerung (Rückrechnung Korrektur/Offset; bei Zweipunkt als Differenz). Kein Drehen: Echo eigener Befehle (gleicher Wert innerhalb 30 s), Moduswechsel durch eigenen Befehl, Kontext mit Elternteil (Automation/Skript), Sperre aktiv, Raum aus, TRV gerade wieder verfügbar, „Nur beobachten“. `reset`: Heizwerk stellt zurück. |
| Schimmel-Indikator (`mold_sensor`) | Wert = Wandfeuchte (%), `estimated_critical_temp` = kritische Wandtemperatur; hat Vorrang vor dem Wandtemperatur-Sensor (der nur °C/°F akzeptiert). |

## 5. Entitäten pro Raum (Gerät „Heizwerk <Raum>“)

| Entität | Inhalt |
|---|---|
| `climate.heizwerk_<raum>` | Modi `heat`/`off`, Ist = Raumfühler, Soll = wirksam, `current_humidity`, `hvac_action` |
| `sensor.heizwerk_<raum>_dew_point` | Taupunkt (°C), nur mit Feuchtesensor |
| `sensor.heizwerk_<raum>_wall_humidity` | Wandfeuchte (%), mit Schimmel-Indikator oder Feuchte- + Wandsensor |
| `binary_sensor.heizwerk_<raum>_ventilation` | Lüften empfohlen |
| `switch.heizwerk_<raum>_observe_only` | Nur beobachten (Konfiguration) |

Attribute von `climate.heizwerk_<raum>` (Schnittstelle zur Karte):

`room_name`, `status`, `locks` [{type, entity_id?, since}], `resume_available`,
`regulation`, `external_inputs`, `wall_source`, `wall_critical_temperature`,
`manual_source` (`heizwerk`/`thermostat`/`zeitwerk`),
`ignored_entities`, `manual_target`, `manual_until`, `manual_mode` (`until_next`/`duration`),
`manual_by`, `zeitwerk_plan`, `zeitwerk_profile`,
`next_change`, `next_profile`, `temperature_source` (`sensor`/`trv`),
`trvs` [{entity_id, state, available, setpoint, current}], `trv_unavailable_since`,
`planned_commands` [{entity_id, hvac_mode, temperature?}], `last_sync`,
`observe_only`, `window_open`, `window_open_since`, `ventilation_minutes`,
`ventilation_done`, `ventilation_recommended`, `dew_point`, `wall_temperature`,
`wall_humidity`, `mold_level`, `outdoor_temperature`, `outdoor_dew_point`,
`season_active`, `humidity_threshold`.

## 6. Dienste

| Dienst | Felder |
|---|---|
| `heizwerk.set_manual` | `entity_id`, `temperature`, `duration` (optional, nur mit Fortsetzen-Aktion; ohne = bis zum nächsten Wert) |
| `heizwerk.resume` | `entity_id` – führt die Fortsetzen-Aktion aus |
| `heizwerk.sync` | `entity_id` – Befehle sofort neu senden (bzw. neu berechnen) |

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
