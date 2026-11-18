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

## Offen / später
- [ ] Vorheizen („Vorlauf ab …“ im Mockup) – braucht Lernlogik, bewusst nicht in 0.1
- [ ] Brand-Icons (`custom_components/heizwerk/brand/`)
- [ ] Release 0.1.0 taggen – erst nach Stevens Freigabe
- [ ] Produktiv-Einsatz: nur nach Freigabe (Hausregeln 1.4), zuerst „Nur beobachten“ parallel zu den bestehenden Automationen

## Erkenntnisse
- HA 2026.11: `ClimateEntity.temperature_unit/current_temperature/target_temperature`
  sind veraltet → `native_*` (Entfall 2027.11).
- Zeitwerk erkennt manuelle Änderungen am Ziel über den Context. Heizwerk schreibt
  deshalb nie in die Zeitwerk-Ziel-Entität; Übersteuerung lebt nur in Heizwerk.
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
