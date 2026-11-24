# Heizwerk – Identity

> English (translation) · [Deutsch](BRANDING.md) – the German version is the
> source of truth.

**Claim:** *Zeitwerk plans, Heizwerk controls.* (German: *Zeitwerk plant, Heizwerk regelt.*)

## Family principle (taken over from the sister projects)
All three logos are **the same gear** (12 teeth, identical path, hole radius 138) with a **dark disc** (`#141417`, r 139) and a **white symbol** (`#f5f5f7`) inside. The word mark is **Inter Bold 190 px, tracking −4**, in one colour, position x 540 / y 318 on a canvas of 1440 × 512.

| Project | Gear | Symbol |
|---|---|---|
| Zeitwerk | blue `#6fa8ff`, two orange sectors | clock with hands |
| Läutwerk | orange `#ff8b4a` | bell with blue sound arcs |
| **Heizwerk** | **orange `#ff8b4a`, two blue sectors** (Zeitwerk mirrored: Zeitwerk plans, Heizwerk controls) | **flame** with a small dark core |

The blue sectors stand for cold or the actual-value side, the orange for warmth. Compared with Zeitwerk the sectors are mirrored horizontally (300°–30° and 143°–180°), so the gear does not look like a plain colour inversion.

## Files
Structure as in the sister projects, for copying into the Heizwerk repository:

| Folder / file | Target in the repo | Content |
|---|---|---|
| `brand/heizwerk-icon.svg` | `docs/brand/` | app icon with dark tile (rx 112) |
| `brand/heizwerk-icon-transparent.svg` | `docs/brand/` | gear with disc, transparent |
| `brand/heizwerk-logo-light.svg` / `-dark.svg` | `docs/brand/` | logo + word mark, dark or light text (font as paths) |
| `brand/readme-logo-light.png` / `-dark.png` | `docs/brand/` | README logo (1440 × 512) |
| `brand/social-preview.png` | `docs/brand/` | GitHub preview image (1280 × 640) |
| `custom_components-brand/` | `custom_components/heizwerk/brand/` | `icon`, `logo`, `dark_logo`, each also `@2x` (icon 256/512 px, logo 360 × 128 / 720 × 256, transparent) |
| `vorschau.html` | – | overview next to Zeitwerk and Läutwerk |

The brand folder inside the integration matches the one of Zeitwerk and Läutwerk.

## Colours
| Role | Value |
|---|---|
| Gear, warmth | `#ff8b4a` |
| Sectors, cold | `#6fa8ff` |
| Disc, tile, light-theme text | `#141417` |
| Symbol, text on dark | `#f5f5f7` |
| Tagline | `#a9acb5` |

The card uses its own contrast-checked theme colours (light/dark, e.g. `#B85500` / `#FF9F4A` for warmth). The logo keeps the family colours of the sister projects; the card may align with them in the dark theme.

## Font and tagline
**Inter Bold**, word mark without colour change. Tagline in the social preview in Inter Regular, 34 px.
Proposal (English as in the sister projects): *Room heating control with climate protection for Home Assistant.* German: *Raumweise Heizungsregelung mit Raumklima-Schutz für Home Assistant.* Please check whether this matches the feature set.

## Usage
- On a light background `logo-light`, on a dark one `logo-dark`; the disc always stays dark.
- At least 24 px gear diameter; below that the teeth and the flame disappear.
- Do not recolour, do not stretch, do not move the sectors.

## Tone
As in the sister projects: factual, calm, technically precise, informal "you" (German "Du"), short sentences, technical terms (target, current, lead time, lock) without explanation, no marketing language.
Examples (German UI): "Küche heizt auf 21,0 °C, Fenster offen – Heizung gesperrt." ("Kitchen heating to 21.0 °C, window open – heating locked.") · "Lüften empfohlen: Wandfeuchte 0,74." ("Airing recommended: wall humidity 0.74.")

## State in the repository (0.5.2)
- Present: `docs/brand/heizwerk-icon.svg`, `heizwerk-logo-light.svg`, `social-preview.png`.
- `custom_components/heizwerk/brand/`: `icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png` – rendered from the SVGs (Chromium, transparent).
- Not yet added: `heizwerk-icon-transparent.svg`, `heizwerk-logo-dark.svg`, `readme-logo-*.png`; therefore no `dark_logo.png` (HA uses `logo.png` in the dark theme).
- The social preview has to be uploaded in GitHub under Settings → General → Social preview (no API for it).
