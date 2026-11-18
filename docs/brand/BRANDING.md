<!-- claude: 2026-11-18 – Heizwerk-Identität, angeglichen an Zeitwerk und Läutwerk (Repos StiviDrum/zeitwerk, StiviDrum/laeutwerk, nur gelesen). Nur Dateien im Projektordner, nichts in HA oder im Repo. -->
# Heizwerk – Identität

**Claim:** *Zeitwerk plant, Heizwerk regelt.*

## Familienprinzip (aus den Schwesterprojekten übernommen)
Alle drei Logos sind **dasselbe Zahnrad** (12 Zähne, identischer Pfad, Lochradius 138) mit **dunkler Scheibe** (`#141417`, r 139) und einem **weißen Symbol** (`#f5f5f7`) darin. Die Wortmarke ist **Inter Bold 190 px, Laufweite −4**, in einer Farbe, Position x 540 / y 318 auf einer Fläche von 1440 × 512.

| Projekt | Zahnrad | Symbol |
|---|---|---|
| Zeitwerk | Blau `#6fa8ff`, zwei orange Sektoren | Zeigeruhr |
| Läutwerk | Orange `#ff8b4a` | Glocke mit blauen Klangbögen |
| **Heizwerk** | **Orange `#ff8b4a`, zwei blaue Sektoren** (Zeitwerk spiegelverkehrt: Zeitwerk plant, Heizwerk regelt) | **Flamme** mit kleinem dunklem Kern |

Die blauen Sektoren stehen für Kälte bzw. Ist-Seite, das Orange für Wärme. Die Sektoren sind gegenüber Zeitwerk horizontal gespiegelt (300°–30° und 143°–180°), damit das Rad nicht wie eine reine Farbumkehr wirkt.

## Dateien
Struktur wie bei den Schwesterprojekten, zum Kopieren ins Heizwerk-Repo:

| Ordner / Datei | Ziel im Repo | Inhalt |
|---|---|---|
| `brand/heizwerk-icon.svg` | `docs/brand/` | App-Icon mit dunkler Kachel (rx 112) |
| `brand/heizwerk-icon-transparent.svg` | `docs/brand/` | Zahnrad mit Scheibe, transparent |
| `brand/heizwerk-logo-light.svg` / `-dark.svg` | `docs/brand/` | Logo + Wortmarke, dunkler bzw. heller Text (Schrift als Pfade) |
| `brand/readme-logo-light.png` / `-dark.png` | `docs/brand/` | README-Logo (1440 × 512) |
| `brand/social-preview.png` | `docs/brand/` | GitHub-Vorschaubild (1280 × 640) |
| `custom_components-brand/` | `custom_components/heizwerk/brand/` | `icon`, `logo`, `dark_logo` jeweils auch `@2x` (Icon 256/512 px, Logo 360 × 128 / 720 × 256, transparent) |
| `vorschau.html` | – | Übersicht neben Zeitwerk und Läutwerk |

Die Brand-Ablage im Integrationsordner entspricht der Ablage bei Zeitwerk und Läutwerk.

## Farben
| Rolle | Wert |
|---|---|
| Zahnrad, Wärme | `#ff8b4a` |
| Sektoren, Kälte | `#6fa8ff` |
| Scheibe, Kachel, Text hell | `#141417` |
| Symbol, Text auf dunkel | `#f5f5f7` |
| Tagline | `#a9acb5` |

Die Karte nutzt eigene, kontrastgeprüfte Theme-Farben (hell/dunkel, z. B. `#B85500` / `#FF9F4A` für Wärme). Das Logo bleibt bei den Familienfarben der Schwesterprojekte; die Karte darf sich daran im dunklen Theme angleichen.

## Schrift und Tagline
**Inter Bold**, Wortmarke ohne Farbwechsel. Tagline im Social-Preview in Inter Regular, 34 px.
Vorschlag (Englisch wie bei den Schwesterprojekten): *Room heating control with climate protection for Home Assistant.* Deutsch: *Raumweise Heizungsregelung mit Raumklima-Schutz für Home Assistant.* Bitte prüfen, ob der Funktionsumfang so stimmt.

## Anwendung
- Auf hellem Grund `logo-light`, auf dunklem `logo-dark`; die Scheibe bleibt immer dunkel.
- Mindestens 24 px Zahnrad-Durchmesser; darunter verschwinden Zähne und Flamme.
- Nicht umfärben, nicht strecken, Sektoren nicht verschieben.

## Tonalität
Wie bei den Schwesterprojekten: sachlich, ruhig, technisch genau, Du-Form, kurze Sätze, Fachbegriffe (Soll, Ist, Vorlauf, Sperre) ohne Erklärung, keine Marketingsprache.
Beispiele: „Küche heizt auf 21,0 °C, Fenster offen – Heizung gesperrt.“ · „Lüften empfohlen: Wandfeuchte 0,74.“

## Stand im Repo (0.5.1)
<!-- claude: 2026-11-18 – Ablage im Repo ergänzt -->
- Vorhanden: `docs/brand/heizwerk-icon.svg`, `heizwerk-logo-light.svg`, `social-preview.png`.
- `custom_components/heizwerk/brand/`: `icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png` – aus den SVGs gerendert (Chromium, transparent).
- Noch nicht abgelegt: `heizwerk-icon-transparent.svg`, `heizwerk-logo-dark.svg`, `readme-logo-*.png`; daher kein `dark_logo.png` (HA nutzt im dunklen Theme `logo.png`).
- Social Preview muss in GitHub unter Settings → General → Social preview hochgeladen werden (keine API dafür).
