# Heizwerk – Aufgaben

Stand nach jeder Aufgabe aktualisieren. Branch: `claude/heizwerk-0.1`.

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

## Backlog – wartet auf „go“ von Steven
Nichts davon wird umgesetzt, bevor Steven „go“ gibt (ganz oder für einzelne Punkte).
Danach je Punkt: umsetzen → Tests → Dev-Test → Push → CI grün → Tag (automatisch).

### B1 – Raum-Dialog: Erklärung zu jeder Einstellung
- [ ] Jede Einstellung (Raum **und** Hausoptionen) bekommt einen Erklärtext (de/en):
      wozu, Standardwert, Empfehlung (z. B. „TRVZB: externer Eingang statt Offset“).
- Hinweis: Der HA-Konfigurationsdialog kennt kein „?“-Symbol mit Tooltip. HA zeigt
  Erklärungen als kurzen Hilfetext direkt unter dem Feld (`data_description`) –
  das ist der native Weg und wird genutzt. Längere Erklärungen gehen in die
  Abschnittsbeschreibung (B3) und in die Doku (Link im Dialog).

### B2 – Pflichtfelder oben, optionale darunter
- [ ] Reihenfolge: Raumname, Thermostate, Raumfühler, Zeitwerk-Ziel (empfohlen)
      oben; alles Optionale darunter in Abschnitten (B3).
- [ ] Gleiches Prinzip für die Hausoptionen.

### B3 – Einklappbare Abschnitte im Dialog
- [ ] Abschnitte (HA `section`, standardmäßig zugeklappt): „Zeitwerk“, „Raumklima“,
      „Fenster & Sperren“, „Regelung (erweitert)“, „Grenzen“.
- [ ] Datenmigration: Abschnitte verschachteln die gespeicherten Werte; bestehende
      Räume müssen beim Update ohne Neuanlage weiterlaufen (Migration + Test).

### B4 – Große Karte: Zieltemperatur am Kreis ziehen
- [ ] Ziel-Punkt auf dem Dial mit Finger/Maus ziehbar (Pointer-Events, Raster =
      Schrittweite 0,5 K, Skala `dial_min`–`dial_max`), Wert während des Ziehens
      groß anzeigen, beim Loslassen einmal `heizwerk.set_manual` (Dauer wie ±).
- [ ] Bedienbar ohne Ziehen: Tastatur (Pfeiltasten) und ± bleiben; Touch-Ziel
      ≥ 44 px; kein Scrollen der Seite während des Ziehens.
- [ ] Tests: Winkel → Temperatur (vitest), im echten Frontend per Screenshot.

### Vorschläge aus der Raum-Erklärung (2026-11-18) – nur bei „go“
- [ ] Zeitwerk-Plan automatisch aus dem Zeitwerk-Ziel ermitteln (Feld entfällt).
- [ ] „Sollwert ohne Zeitwerk-Ziel“ und „Frostschutztemperatur“ nur zeigen, wenn sie
      wirken (braucht zweiten Dialogschritt – HA blendet Felder nicht dynamisch aus).
- [ ] Warnung, wenn Offset-Regelung und externer Temperatureingang zugleich gesetzt sind.

## Offen / später
- [ ] Vorheizen („Vorlauf ab …“ im Mockup) – braucht Lernlogik, bewusst nicht in 0.1
- [ ] Brand-Icons (`custom_components/heizwerk/brand/`)
- [x] Release 0.1.0 getaggt (Freigabe Steven 2026-11-18)
- [ ] Produktiv-Einsatz: nur nach Freigabe (Hausregeln 1.4), zuerst „Nur beobachten“ parallel zu den bestehenden Automationen

## Erkenntnisse
- HA 2026.11: `ClimateEntity.temperature_unit/current_temperature/target_temperature`
  sind veraltet → `native_*` (Entfall 2027.11).
- Zeitwerk erkennt manuelle Änderungen am Ziel über den Context. Seit 0.2 nutzt
  Heizwerk genau das: Übersteuerungen werden ins Ziel geschrieben und sind in
  Zeitwerk sichtbar (nicht bei „Nur beobachten“).
- Zeitwerk `zeitwerk/preview` antwortet mit `{plans: {plan_id: [...]}}` (im Dev-Test gefunden, Karte angepasst).
- HA 2026.11 übernimmt `http:` aus YAML einmalig als *ausstehende* Konfiguration; ohne
  `http/config/promote` wird sie nach 5 min zurückgesetzt und HA startet neu.
  `scripts/dev_check.py` bestätigt sie für die Dev-Instanz (Port 8125).
- Startrennen mit dem Wiederherstellen der TRV-Zustände: Neubewertung nach
  `homeassistant_started` und 5-min-Abgleich bei ausstehenden Befehlen.

## Dev-Test (2026-11-18, Dev-Instanz :8125)
`scripts/dev_check.py screenshots --shots` – alle Szenarien OK: TRV-Steuerung mit
Korrektur, externe Temperatur, Nur beobachten, Fenstersperre mit Verzögerungen,
Sperr-Entität mit Frostschutz, manuelle Übersteuerung inkl. Benutzer und Ende durch
neuen Zeitwerk-Wert, Zeitwerk-Schnittstellen, keine Heizwerk-Warnungen im Log;
Karte Standard/Kompakt in hell und dunkel gerendert.
