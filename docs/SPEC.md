# Heizwerk – Spezifikation

> Sprache: Deutsch. Code, Kommentare, Bezeichner, Commits: Englisch.
> Stand: 2026-11-18 · Mindestversion Home Assistant **2026.11**

## 1. Idee

**Zeitwerk plant, Heizwerk regelt.** Zeitwerk entscheidet, *welche* Solltemperatur
gerade gilt (Profile, Wochenplan, Vorrang-Regeln). Heizwerk setzt diese Sollwerte
pro Raum an den Heizkörperthermostaten (TRV) um und kümmert sich um alles, was
zwischen „Sollwert steht fest“ und „Ventil macht auf“ passiert:

- externer Raumfühler statt TRV-Eigenmessung, Korrektur (z. B. −0,5 K)
- **Sperren**: Fenster offen, Heizperiode aus, Sommerabschaltung (außen ≥ 16 °C
  für 10 min), frei wählbare Sperr-Entitäten
- manuelle Übersteuerung mit Dauer (bis nächster Block / 1 h / 3 h)
- Raumklima: Feuchte, Taupunkt, Wandfeuchte (Schimmelrisiko), Lüftungsempfehlung
- **Nur beobachten**: Heizwerk rechnet alles, schickt aber nichts an die TRVs

Abgrenzung: Heizwerk plant nicht (kein Wochenplan, keine Profile) – das bleibt
Zeitwerk. Heizwerk erinnert nicht (keine Push-Ketten) – das bleibt Läutwerk.

## 2. Schnittstellen zu Zeitwerk und Läutwerk (gelesen am 2026-11-18)

Quelle: Repos `~/zeitwerk` (1.0.0-rc.11) und `~/laeutwerk` (0.11.4), abgeglichen
mit der installierten Zeitwerk-Instanz (nur lesend). Heizwerk nutzt **nur
öffentliche Schnittstellen** (Zustände, Attribute, WebSocket, Dienste), keine
Interna.

### 2.1 Zeitwerk → Heizwerk

| Schnittstelle | Nutzung in Heizwerk |
|---|---|
| Ziel-Entität eines Plans (z. B. `input_number.temperaturspeicher_bad`), gesetzt von Profil-Aktionen (`input_number.set_value`, `data.value`) | **Zeitwerk-Ziel** = geplanter Sollwert des Raums (`target_entity`). Numerischer Zustand; bei `climate` das Attribut `temperature`. |
| `sensor.zeitwerk_<plan>_profile` – Zustand = Profilname; Attribute `plan_id`, `profile_id`, `source` (`schedule` / `override:<id>` / `default` / `inactive`), `day_type`, `is_holiday`, `profiles` {id: name}, `overrides` [{id, name, profile, active}], `forced_until`, `manual_override`, `manual_since`, `manual_until` | Profilanzeige („Profil Komfort“), Grund bei Vorrang-Regel |
| `sensor.zeitwerk_<plan>_next_change` – Zeitstempel; Attribute `next_profile`, `next_profile_name` | „Komfort bis 07:30“, Ende der manuellen Übersteuerung „bis nächster Block“ |
| WebSocket `zeitwerk/plans/get` {plan_id} (kein Admin nötig) → Plan inkl. `profiles[].actions` und `status` | Karte: Profile mit Name, Farbe, Aktionen → Wert pro Profil für die Ziel-Entität |
| WebSocket `zeitwerk/preview` {plan_ids, start?, end?} (kein Admin) → `{plans: {plan_id: [{start, end, profile}]}}` | Karte: Tagesband „Heute“ |
| Zeitwerk erkennt manuelle Änderungen an der Ziel-Entität über einen fremden `context` (Attribute `manual_override`, `manual_since`, `manual_until` am Profilsensor) | **Übersteuerung über Zeitwerk** (ab 0.2, Wunsch Steven 2026-11-18): Heizwerk schreibt den manuellen Wert in die Ziel-Entität, Zeitwerk zeigt ihn als manuelle Übersteuerung und beendet sie beim nächsten Block. Gilt nur mit Zeitwerk-Ziel **und** Plan **und** ohne „Nur beobachten“ – sonst bleibt die Übersteuerung intern (das Ziel kann in der Parallelphase noch die alte Heizungssteuerung speisen). |
| Dienst `zeitwerk.resume` {plan} | Ende einer Übersteuerung mit Dauer (1 h / 3 h), „Fortsetzen“ in Heizwerk, Rückkehr auf den Planwert |

Alternative ohne Ziel-Entität: Ein Zeitwerk-Profil kann direkt
`climate.set_temperature` auf `climate.heizwerk_<raum>` ausführen. Dann ist jede
Sollwertänderung der neue Basis-Sollwert; manuelle Übersteuerung übernimmt in
diesem Fall Zeitwerk (`manual_override: until_next`, beobachtetes Attribut
`temperature`).

Plan-Zuordnung: Option `zeitwerk_plan` (Plan-ID). Der Config-Flow bietet alle
Pläne an, die `sensor.zeitwerk_*_profile` mit Attribut `plan_id` melden.

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

| Option | Bedeutung | Standard |
|---|---|---|
| `name` | Raumname → `climate.heizwerk_<slug>` | – |
| `trvs` | Thermostat-Entitäten (`climate`, mehrere) | – |
| `temperature_sensor` | externer Raumfühler; fehlt er, gilt der Mittelwert der TRV-Messungen | – |
| `humidity_sensor`, `wall_temperature_sensor` | Raumklima | – |
| `windows` | Fensterkontakte (`binary_sensor`/`input_boolean`) | – |
| `window_open_delay` / `window_close_delay` | Sekunden bis Sperre greift / endet | 30 / 10 |
| `target_entity` | Zeitwerk-Ziel (siehe 2.1) | – |
| `zeitwerk_plan` | Plan-ID für Anzeige und „bis nächster Block“ | – |
| `lock_entities` | weitere Sperren: Zustand `on`/`true`/`open` sperrt | – |
| `lock_mode` | Sperre schaltet TRV `off` (Frostschutz im Gerät) oder `frost` (heat auf Frostschutztemperatur) | `off` |
| `frost_temperature` | Frostschutz | 7 |
| `correction` | Korrektur in K auf den Sollwert | 0 |
| `regulation` | `setpoint` (TRV-Soll = Ziel + Korrektur) oder `offset` (zusätzlich + TRV-Ist − Raum-Ist, ±5 K) | `setpoint` |
| `external_temperature_entities` | `number`-Entitäten der TRVs für externe Temperatur (z. B. Sonoff TRVZB `external_temperature_input`) | – |
| `default_target` | Sollwert ohne Zeitwerk-Ziel | 20 |
| `min_temp` / `max_temp` | Bereich | 5 / 30 |
| `humidity_threshold` | Lüften empfohlen ab % | 60 |
| `observe_only` | **Nur beobachten** | **an** |

Neue Räume starten **immer** im Modus „Nur beobachten“ (Abschnitt 1.4 der
Hausregeln: Heizungssteuerung nur mit Freigabe).

## 4. Regelung

### 4.1 Sollwert

```
geplant   = Zeitwerk-Ziel (target_entity)  | sonst Basis-Sollwert (set_temperature / default_target)
wirksam   = manuell (falls aktiv)          | sonst geplant
```

Manuelle Übersteuerung (`climate.set_temperature` mit Zeitwerk-Ziel,
`heizwerk.set_manual`), wer übersteuert hat, steht in `manual_by`:

- **Über Zeitwerk** (Ziel + Plan, nicht „Nur beobachten“): Der Wert wird in die
  Ziel-Entität geschrieben; Zeitwerk zeigt „Manuell“ und setzt beim nächsten
  Profilwechsel den Planwert zurück (`until_next`). Dauer (1 h / 3 h): Heizwerk
  ruft nach Ablauf `zeitwerk.resume` auf. „Fortsetzen“ (Heizwerk- oder
  Zeitwerk-Karte) beendet beides. Wird der Planwert eingestellt, ist das ein
  Fortsetzen. Übersteuerungen, die in Zeitwerk entstehen, zeigt Heizwerk ebenfalls
  (`manual_source: zeitwerk`). `scheduled_target` zeigt weiter den Planwert.
  Voraussetzung im Plan: `manual_override` nicht `ignore`.
- **Intern** (sonst): `until_next` endet beim nächsten Zeitwerk-Wechsel
  (`next_change`) oder wenn sich das Ziel ändert; `duration` nach Ablauf.

### 4.2 Status (Priorität von oben)

| Status | Bedingung | TRV-Befehl |
|---|---|---|
| `off` | Raum per `hvac_mode: off` ausgeschaltet | `off` |
| `unavailable` | alle TRVs `unavailable`/`unknown` | – (nichts senden) |
| `window` | Fenster länger als `window_open_delay` offen | Sperre |
| `season` | Heizperiode aus | Sperre |
| `summer` | außen ≥ Schwelle seit `summer_lock_minutes` | Sperre |
| `locked` | eine Sperr-Entität aktiv | Sperre |
| `manual` | manuelle Übersteuerung aktiv | heat, Soll |
| `heating` | Ist < wirksam − 0,2 K oder ein TRV meldet `hvac_action: heating` | heat, Soll |
| `reached` | sonst | heat, Soll |

Sperre = `hvac_mode: off` (`lock_mode: off`) bzw. heat auf `frost_temperature`.

### 4.3 Befehle

- TRV-Soll = wirksam + `correction` (+ Offset bei `regulation: offset`), auf
  Schrittweite des TRV gerundet, auf dessen `min_temp`/`max_temp` begrenzt.
- Entprellung 10 s: Änderungen werden gesammelt, dann einmal ausgewertet.
- Gesendet wird nur, was vom TRV-Zustand abweicht (kein Dauerfeuer).
- Externe Temperatur: Raum-Ist an `external_temperature_entities`, wenn sich der
  Wert um ≥ 0,1 K ändert, sonst spätestens alle 30 min.
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

## 5. Entitäten pro Raum (Gerät „Heizwerk <Raum>“)

| Entität | Inhalt |
|---|---|
| `climate.heizwerk_<raum>` | Modi `heat`/`off`, Ist = Raumfühler, Soll = wirksam, `current_humidity`, `hvac_action` |
| `sensor.heizwerk_<raum>_dew_point` | Taupunkt (°C), nur mit Feuchtesensor |
| `sensor.heizwerk_<raum>_wall_humidity` | Wandfeuchte (%), nur mit Wandsensor |
| `binary_sensor.heizwerk_<raum>_ventilation` | Lüften empfohlen |
| `switch.heizwerk_<raum>_observe_only` | Nur beobachten (Konfiguration) |

Attribute von `climate.heizwerk_<raum>` (Schnittstelle zur Karte):

`room_name`, `status`, `locks` [{type, entity_id?, since}], `scheduled_target`,
`manual_target`, `manual_until`, `manual_mode` (`until_next`/`duration`),
`manual_by`, `manual_source` (`zeitwerk`/`heizwerk`), `target_entity`, `zeitwerk_plan`, `zeitwerk_profile`,
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
| `heizwerk.set_manual` | `entity_id`, `temperature`, `duration` (optional; ohne = bis nächster Block) |
| `heizwerk.resume` | `entity_id` |
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

- **Standard** (Mockup `mockups/heizwerk-karte-standard.html`): Kopf (Raum, Profil,
  Plan, ⋯ → Mehr-Info), Zustands-Chip, Dial Ist/Ziel, ± Ziel, nächster Wechsel,
  Hinweis (Lüften/Schimmel), Raumklima (Feuchte, Taupunkt, Wandfeuchte),
  Tagesband aus Zeitwerk, Fußzeile (TRV, Fühler, Abgleich, Nur beobachten).
- **Kompakt** (Mockup `mockups/heizwerk-karte-kompakt.html`): `entity` → Einzelkachel
  (eine Zeile, ± ), `entities` → Hausliste mit aufklappbaren Zeilen (Mini-Balken,
  Kennwerte, ±, Dauer-Pillen „Bis nächster Block / 1 Std. / 3 Std.“).
- Nutzt HA-Theme-Variablen, hell/dunkel, Touch-Ziele ≥ 44 px, kein Hover-Zwang,
  Übersetzungen de/en, freundlicher Fehlerzustand ohne `hass`/Entität.
- Karte wird von der Integration selbst registriert (statischer Pfad +
  `add_extra_js_url`), keine manuelle Ressource.

## 8. Nicht-Ziele (0.x)

- Kein eigener Zeitplan, keine Profile (Zeitwerk).
- Kein Vorheizen/Lernen („Vorlauf ab …“ aus dem Mockup) – vorgemerkt für später.
- Keine Push-Benachrichtigungen (Läutwerk).
