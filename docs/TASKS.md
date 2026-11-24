# Heizwerk – Aufgaben

Stand nach jeder Aufgabe aktualisieren. Aktuelle Version: **0.5.2**. Arbeits-Branch: `claude/heizwerk-0.1` (Name historisch), Standard-Branch `main`.
Die Abschnitte unten sind die Historie je Version; maßgeblich für den Ist-Stand sind README und SPEC.

## M0 – Gerüst
- [x] HACS (`hacs.json`), `manifest.json`, Lizenz, Skripte (`setup`, `develop`, `lint`, `check`, `test`)
- [x] CI: hassfest, HACS, ruff, pytest, eslint, prettier, tsc, vitest, Build; Release-ZIP bei Tag
- [x] Dev-Instanz `config/` (Port 8125) mit simulierten TRVs, Fühlern, Fenstern, Zeitwerk-Kopie
- [x] Schnittstellen Zeitwerk/Läutwerk festgehalten (`docs/SPEC.md` §2)

## M1 – Config-Flow und Regelung
- [x] Hauptsatz mit Hausoptionen + Optionen-Flow
- [x] Räume als Subentries (anlegen, ändern, Validierung)
- [x] `climate.heizwerk_<raum>` mit Zeitwerk-Ziel, Korrektur, Offset, Entprellung
- [x] Sperren: Fenster, Heizperiode, Sommer, Sperr-Entitäten; Modus aus/Frostschutz
- [x] Manuelle Übersteuerung (bis nächster Block / Dauer), Fortsetzen, Wiederherstellung
- [x] Nur beobachten (Standard), Schalter pro Raum
- [x] Raumklima: Taupunkt, Wandfeuchte, Lüften, Ereignisse
- [x] Tests (pytest)

## M2 – Karte
- [x] Standardvariante nach Mockup (Dial, Chip, Hinweis, Raumklima, Tagesband, Fußzeile)
- [x] Kompaktvariante: Kachel + Hausliste mit Dauer-Pillen
- [x] Hell/Dunkel, de/en, visueller Editor
- [x] Tests (vitest)

## M3 – Doku
- [x] README (en + de), CHANGELOG

## 0.2 – Übersteuerung in Zeitwerk sichtbar (Wunsch Steven 2026-11-18)
- [x] Manueller Wert ins Zeitwerk-Ziel, Ende über Zeitwerk (Block, `zeitwerk.resume`)
- [x] Übersteuerung aus Zeitwerk in Heizwerk anzeigen
- [x] Nur beobachten schreibt nie ins Ziel
- [x] Tests + Dev-Test gegen echtes Zeitwerk (Zeitwerk-Karte zeigt „Manuell … von Heizwerk-Wert“)

## 0.3 – Backlog umgesetzt („go“ Steven 2026-11-18, Subagents Backend + Frontend)
Künftige Wünsche wieder hier sammeln und erst nach „go“ umsetzen.

### B1 – Raum-Dialog: Erklärung zu jeder Einstellung
- [x] Jede Einstellung (Raum **und** Hausoptionen) bekommt einen Erklärtext (de/en):
      wozu, Standardwert, Empfehlung (z. B. „TRVZB: externer Eingang statt Offset“).
- Hinweis: Der HA-Konfigurationsdialog kennt kein „?“-Symbol mit Tooltip. HA zeigt
  Erklärungen als kurzen Hilfetext direkt unter dem Feld (`data_description`) –
  das ist der native Weg und wird genutzt. Längere Erklärungen gehen in die
  Abschnittsbeschreibung (B3) und in die Doku (Link im Dialog).

### B2 – Pflichtfelder oben, optionale darunter
- [x] Reihenfolge: Raumname, Thermostate, Raumfühler, Zeitwerk-Ziel (empfohlen)
      oben; alles Optionale darunter in Abschnitten (B3).
- [x] Gleiches Prinzip für die Hausoptionen.

### B3 – Einklappbare Abschnitte im Dialog
- [x] Abschnitte (HA `section`, standardmäßig zugeklappt): „Zeitwerk“, „Raumklima“,
      „Fenster & Sperren“, „Regelung (erweitert)“, „Grenzen“.
- [x] Datenmigration: Abschnitte verschachteln die gespeicherten Werte; bestehende
      Räume müssen beim Update ohne Neuanlage weiterlaufen (Migration + Test).

### B4 – Große Karte: Zieltemperatur am Kreis ziehen
- [x] Ziel-Punkt auf dem Dial mit Finger/Maus ziehbar (Pointer-Events, Raster =
      Schrittweite 0,5 K, Skala `dial_min`–`dial_max`), Wert während des Ziehens
      groß anzeigen, beim Loslassen einmal `heizwerk.set_manual` (Dauer wie ±).
- [x] Bedienbar ohne Ziehen: Tastatur (Pfeiltasten) und ± bleiben; Touch-Ziel
      ≥ 44 px; kein Scrollen der Seite während des Ziehens.
- [x] Tests: Winkel → Temperatur (vitest), im echten Frontend per Screenshot.

### Vorschläge aus der Raum-Erklärung (2026-11-18) – nur bei „go“
- [x] Zeitwerk-Plan automatisch aus dem Zeitwerk-Ziel ermitteln (Feld entfällt).
- [x] „Sollwert ohne Zeitwerk-Ziel“ und „Frostschutztemperatur“ nur zeigen, wenn sie
      wirken – umgesetzt mit HA-2026.11-Sichtbarkeitsbedingungen (`visible`), ohne zweiten Schritt.
- [x] Warnung, wenn Offset-Regelung und externer Temperatureingang zugleich gesetzt sind.

## 0.4 – Einfache Schnittstelle („go“ Steven 2026-11-18)
- [x] Zeitplan schreibt `climate.set_temperature` auf den Raum; Feld „Zeitwerk-Ziel“ entfernt (Reparaturhinweis für Altdaten)
- [x] Fix: Zeitwerk-Ziel = eigene Klima-Entität → RecursionError (0.3.0); eigene Entitäten nicht wählbar
- [x] Frei wählbare Fortsetzen-Aktion (Standard `zeitwerk.resume`, z. B. `scheduler.run_action`), auch für Dauer-Ende
- [x] Manuell-Erkennung ohne Zeitwerk; Zeitwerk-Meldung wird angezeigt
- [x] Plan-Erkennung über die Klima-Entität (Dialog + Start)
- [x] Karte: Fortsetzen/Dauer nur mit Fortsetzen-Aktion
- [x] Tests + Dev-Test gegen echtes Zeitwerk (Fall Steven: Plan 16 °C, manuell, Fortsetzen → Planwert)

## 0.5 – Ablösung der Heizungs-Automationen („go“ Steven 2026-11-18)
Ziel: die Heizungs-Automationen (`claude_Heizungssteuerung_*`,
`claude_Thermostat_Raumtemperatur`) langfristig deaktivieren können.

- [x] **B5 Raumtemperatur an die Thermostate senden** – ein Schalter statt des Felds
      „Externe Temperatureingänge“. Heizwerk findet den Eingang
      `number.…_external_temperature_input` am selben Gerät wie jeden TRV des Raums
      selbst und schickt den Wert des Raumfühlers (≥ 0,1 K Änderung, sonst alle 30 min).
      Bestehende Einträge im alten Feld werden übernommen.
- [x] **B6 Regelart „Zweipunkt“** (Option, Standard bleibt „Sollwert“ = TRVZB regelt
      selbst nach dem externen Wert): Hysterese negativ/positiv (Standard −0,5 / +0 K),
      Heizwert am TRV (Standard 24 °C), TRV nur heizen/aus – wie Blueprint
      `claude_Heizungssteuerung_V2`.
- [x] **B7 Außentemperatur-Grenze pro Raum** (optional, überschreibt den Hauswert).
- [x] **B8 Hinweis Messquelle** – Reparaturhinweis, wenn die Messquellen-Auswahl eines
      TRV länger als 5 min nicht auf `remote_temperature` steht (nicht verfügbar /
      unbekannt zählen nicht). Heizwerk stellt nicht selbst um.
- [x] **B9 Drehen am Thermostat erkennen** – als manuelle Übersteuerung übernehmen
      (Standard) oder zurücksetzen (Raum-Option); Echo eigener Befehle ausfiltern.
- [x] **B10 Wandfeuchte**: Feld Wandtemperatur nur für Temperatursensoren (°C);
      neues Feld „Schimmel-Indikator (Wandfeuchte in %)“ übernimmt z. B.
      `sensor.claude_schimmel_<raum>` direkt (inkl. kritischer Wandtemperatur).

Danach Umstieg je Raum: Heizwerk-Raum mit gleichen Werten in „Nur beobachten“,
vergleichen, dann mit Freigabe Automation deaktivieren (nicht löschen).

Arbeitsteilung: Dialog-Agent, Karten-Agent (beide wiederverwendet), Laufzeit +
Tests + Dev-Test Orchestrator, **unabhängiger Prüf-Agent** (neu, Nr. 3 von 4):
14 Befunde + 1 Nachbefund (mehrere Rasten am TRV) behoben, je mit Regressionstest.
Dev-Test: Drehen am TRV, Zweipunkt, Schimmel-Indikator in der Dev-Instanz OK;
Erkennung von Eingang/Messquelle am TRVZB-Gerät nur per Test (Dev-TRVs haben
kein Gerät).

## 0.5.1 – Karte und Dialog (Feedback Steven 2026-11-18)
- [x] Kompaktkarte volle Breite, übersichtliches Layout (Karten-Agent)
- [x] Standardkarte: Profil/Plan aus dem Kopf, Plan über dem Tagesband, Fußzeile ohne TRV/Fühler
- [x] Auswahlfelder als Klappliste (Radio-Punkt in HA 2026.11 versetzt – gemessen: SVG 11,2 × 14 px statt quadratisch)
- [x] Brand: HA-Icons aus den SVGs gerendert, `docs/brand` ins Repo
- [ ] Brand-Dateien laut BRANDING.md noch nicht vorhanden: transparentes Icon, dunkles Logo, README-PNGs
- [ ] Social Preview in GitHub hochladen (Settings → General, keine API)

## 0.5.2 – Störfall Handwert 6 °C (Steven 2026-11-24)
- [x] Echo-Fix: Meldungen innerhalb 30 s nach eigenem Befehl kein Drehen; Wert von vor dem Befehl 5 min lang veraltet; Wunschwert = Zustimmung
- [x] Zweipunkt: Drehen am Thermostat immer zurückgesetzt (Feld im Dialog ausgeblendet)
- [x] Plausibilität: Sprung > 5 K verworfen; Untergrenze `knob_min_temperature` (automatisch: niedrigster Zeitwerk-Profilwert, sonst min_temp)
- [x] Wiederholungsgrenze 3 × / 10 min + Reparaturhinweis (Gerätefehler zählen, Nutzereingriffe nicht)
- [x] Zweipunkt: obere Hysterese negativ erlaubt, Mindestlauf/-pause (Opt-in), keine Haltezeit nach Sperre
- [x] Keine Befehle vor HA-Start; Zweipunkt-Zustand aus erster TRV-Meldung
- [x] Logging + Ereignisse knob_adopted/knob_rejected + Attribut last_knob
- [x] Doku vollständig zweisprachig (README, CHANGELOG, SPEC.md/SPEC.en.md, BRANDING)
- Punkt 4 (TRV-Soll 30/7 nicht anzeigen) gestrichen: keine Karte liest den TRV-Wert.
Arbeitsteilung: Dialog-Agent, Prüf-Agent (3 Runden, 8 Befunde behoben), neuer Doku-Agent (Nr. 4 von 4);
Laufzeit, Tests, Dev-Test (Störfall per REST-Zustand nachgestellt) Orchestrator. 141 + 42 Tests.

## Offen / später
- [ ] Vorheizen („Vorlauf ab …“ im Mockup) – braucht Lernlogik, bisher bewusst nicht umgesetzt
- [x] Release 0.1.0 getaggt (Freigabe Steven 2026-11-18)
- [ ] Produktiv-Einsatz: nur nach Freigabe (Hausregeln 1.4), Raum für Raum zuerst „Nur beobachten“ parallel zu den bestehenden Automationen

## Erkenntnisse
- HA 2026.11: Formulare können Felder abhängig von anderen Feldern zeigen
  (`data_entry_flow.Optional(..., visible=...)`); Bedingungen wirken nur innerhalb
  derselben Ebene/desselben Abschnitts. Fehler in Abschnitten werden über den
  Abschnittsschlüssel gemeldet.
- HA 2026.11 ersetzt voluptuous durch probatio (Alias in `homeassistant/__init__`).
- HA 2026.11: `ClimateEntity.temperature_unit/current_temperature/target_temperature`
  sind veraltet → `native_*` (Entfall 2027.11).
- Zeitwerk erkennt manuelle Änderungen an seinen Zielen über den Context. Seit
  0.4 ist das Ziel die Heizwerk-Klima-Entität selbst – Übersteuerungen aus der
  Heizwerk-Karte sind dadurch ohne Zusatzlogik in Zeitwerk sichtbar.
- Der HA-Aktionseditor im Dialog zeigt keinen Hilfetext (`data_description`) –
  Erklärung steht deshalb in der Abschnittsbeschreibung.
- Zeitwerk `zeitwerk/preview` antwortet mit `{plans: {plan_id: [...]}}` (im Dev-Test gefunden, Karte angepasst).
- HA 2026.11 übernimmt `http:` aus YAML einmalig als *ausstehende* Konfiguration; ohne
  `http/config/promote` wird sie nach 5 min zurückgesetzt und HA startet neu.
  `scripts/dev_check.py` bestätigt sie für die Dev-Instanz (Port 8125).
- Startrennen mit dem Wiederherstellen der TRV-Zustände: Neubewertung nach
  `homeassistant_started` und 5-min-Abgleich bei ausstehenden Befehlen.

## Dev-Test (Stand 0.1, Dev-Instanz :8125) – spätere Dev-Tests je Version oben
`scripts/dev_check.py screenshots --shots` – alle Szenarien OK: TRV-Steuerung mit
Korrektur, externe Temperatur, Nur beobachten, Fenstersperre mit Verzögerungen,
Sperr-Entität mit Frostschutz, manuelle Übersteuerung inkl. Benutzer und Ende durch
neuen Zeitwerk-Wert, Zeitwerk-Schnittstellen, keine Heizwerk-Warnungen im Log;
Karte Standard/Kompakt in hell und dunkel gerendert.
