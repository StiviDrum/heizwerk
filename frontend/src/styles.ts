import { css } from "lit";

/**
 * Tokens follow mockups/heizwerk-karte-*.html. Surfaces and text come from the
 * HA theme; accents use the mockup values (light/dark via the [dark] host
 * attribute, set from hass.themes.darkMode) and can be overridden with
 * --heizwerk-<token>.
 */
export const tokens = css`
  :host {
    --hw-card: var(--ha-card-background, var(--card-background-color, #fff));
    --hw-tx: var(--primary-text-color, #15171a);
    --hw-tx2: var(--secondary-text-color, #5a616b);
    --hw-line: var(--divider-color, #e2e5ea);
    --hw-track: var(--heizwerk-track, #e6e9ee);
    --hw-heat: var(--heizwerk-heat, #b85500);
    --hw-heatf: var(--heizwerk-heat-fill, #f08a24);
    --hw-blue: var(--heizwerk-blue, #1f5fc4);
    --hw-teal: var(--heizwerk-teal, #0b7a70);
    --hw-amber: var(--heizwerk-amber, #8a5300);
    --hw-red: var(--heizwerk-red, #b42318);
    --hw-green: var(--heizwerk-green, #2e7d32);
    --hw-violet: var(--heizwerk-violet, #5b3fc4);
    --hw-eco: var(--heizwerk-eco, #4d6a86);
    display: block;
  }
  :host([dark]) {
    --hw-track: var(--heizwerk-track, #2c313a);
    --hw-heat: var(--heizwerk-heat, #ff9f4a);
    --hw-heatf: var(--heizwerk-heat-fill, #ff9f4a);
    --hw-blue: var(--heizwerk-blue, #7aa8ff);
    --hw-teal: var(--heizwerk-teal, #45c9ba);
    --hw-amber: var(--heizwerk-amber, #f2b84b);
    --hw-red: var(--heizwerk-red, #ff7a70);
    --hw-green: var(--heizwerk-green, #6bcb77);
    --hw-violet: var(--heizwerk-violet, #b3a1ff);
    --hw-eco: var(--heizwerk-eco, #9db4cc);
  }
  .t-heat {
    --c: var(--hw-heat);
  }
  .t-green {
    --c: var(--hw-green);
  }
  .t-blue {
    --c: var(--hw-blue);
  }
  .t-violet {
    --c: var(--hw-violet);
  }
  .t-red {
    --c: var(--hw-red);
  }
  .t-eco {
    --c: var(--hw-eco);
  }
  .t-muted {
    --c: var(--hw-tx2);
  }
  .t-amber {
    --c: var(--hw-amber);
  }
  .t-teal {
    --c: var(--hw-teal);
  }
  svg.i {
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  button {
    font: inherit;
    color: inherit;
    -webkit-tap-highlight-color: transparent;
  }
  button:focus-visible,
  .sum:focus-visible {
    outline: 2px solid var(--primary-color, var(--hw-blue));
    outline-offset: 2px;
  }
  .num {
    font-variant-numeric: tabular-nums;
  }
  .err {
    padding: 16px;
    color: var(--hw-tx2);
  }
`;

export const standardStyles = css`
  ha-card.std {
    border-radius: var(--ha-card-border-radius, 20px);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    color: var(--hw-tx);
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }
  h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }
  .sub {
    font-size: 13px;
    color: var(--hw-tx2);
  }
  .iconbtn {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    border: none;
    background: transparent;
    color: var(--hw-tx2);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex: none;
  }
  .chip {
    align-self: flex-start;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    min-height: 36px;
    border-radius: 999px;
    border: none;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    background: color-mix(in srgb, var(--c) 14%, transparent);
    color: var(--c);
    text-align: left;
  }
  .dial {
    position: relative;
    width: 260px;
    height: 214px;
    align-self: center;
  }
  .dial svg {
    display: block;
    /* Only the arc/knob hit areas take pointers – the rest of the dial scrolls normally. */
    pointer-events: none;
    touch-action: none;
    -webkit-tap-highlight-color: transparent;
    border-radius: 16px;
  }
  .dial svg:focus {
    outline: none;
  }
  .dial svg:focus-visible {
    outline: 2px solid var(--c);
    outline-offset: 2px;
  }
  .dial .hit {
    pointer-events: all;
    cursor: grab;
  }
  .dial path.hit {
    pointer-events: stroke;
  }
  .dial.dragging .hit {
    cursor: grabbing;
  }
  .dial .halo {
    opacity: 0;
    pointer-events: none;
  }
  .dial .knob {
    pointer-events: none;
  }
  .dial.dragging .halo {
    opacity: 0.2;
  }
  .dial.dragging .knob {
    r: 13px;
  }
  @media (prefers-reduced-motion: no-preference) {
    .dial .knob {
      transition: r 0.12s ease-out;
    }
    .dial .halo {
      transition: opacity 0.12s ease-out;
    }
  }
  .dial .mid,
  .dial .end {
    pointer-events: none;
  }
  .dial .mid {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding-top: 6px;
  }
  .dial .big {
    font-size: 54px;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.05;
  }
  .dial .s {
    font-size: 13px;
    color: var(--hw-tx2);
  }
  .dial .end {
    position: absolute;
    top: 190px;
    font-size: 11.5px;
    color: var(--hw-tx2);
  }
  .ctrl {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 22px;
  }
  .round {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 1px solid var(--hw-line);
    background: var(--hw-card);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
  .round:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .ziel {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 110px;
  }
  .ziel b {
    font-size: 26px;
    font-weight: 600;
    color: var(--hw-heat);
  }
  .ziel span {
    font-size: 12px;
    color: var(--hw-tx2);
  }
  .next {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 13px;
    color: var(--hw-tx2);
    text-align: center;
  }
  .link {
    border: none;
    background: none;
    color: var(--hw-violet);
    font-weight: 600;
    cursor: pointer;
    padding: 6px 4px;
    min-height: 32px;
  }
  .note {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding: 12px 14px;
    border-radius: 14px;
    background: color-mix(in srgb, var(--c) 13%, transparent);
  }
  .note strong {
    font-size: 14px;
    color: var(--c);
    display: block;
  }
  .note span {
    font-size: 13px;
    color: var(--hw-tx2);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr));
    gap: 10px;
  }
  .m {
    border: 1px solid var(--hw-line);
    border-radius: 14px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }
  .m .k {
    font-size: 12px;
    color: var(--hw-tx2);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .m .v {
    font-size: 20px;
    font-weight: 600;
  }
  .m .n {
    font-size: 12px;
    color: var(--hw-tx2);
  }
  .m .n.warn {
    font-weight: 600;
    color: var(--c);
  }
  .bar {
    position: relative;
    height: 6px;
    border-radius: 3px;
    background: var(--hw-track);
  }
  .bar i {
    position: absolute;
    top: 0;
    bottom: 0;
    border-radius: 3px;
  }
  .day {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .day .row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: 12px;
    color: var(--hw-tx2);
  }
  .track {
    position: relative;
    height: 12px;
    border-radius: 6px;
    background: color-mix(in srgb, var(--hw-eco) 30%, transparent);
  }
  .track i {
    position: absolute;
    top: 0;
    bottom: 0;
    border-radius: 3px;
    background: var(--hw-heatf);
  }
  .track em {
    position: absolute;
    top: -5px;
    width: 2px;
    height: 22px;
    border-radius: 1px;
    background: var(--hw-tx);
  }
  .foot {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 14px;
    font-size: 12px;
    color: var(--hw-tx2);
    border-top: 1px solid var(--hw-line);
    padding-top: 12px;
  }
  .foot .fwarn {
    color: var(--hw-amber);
    font-weight: 600;
  }
  .foot .obs {
    color: var(--hw-violet);
    font-weight: 600;
  }
`;

export const compactStyles = css`
  .tile {
    border-radius: var(--ha-card-border-radius, 16px);
    color: var(--hw-tx);
  }
  .row1 {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    min-height: 64px;
    cursor: pointer;
  }
  .ic {
    flex: none;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--c) 15%, transparent);
    color: var(--c);
  }
  .nm {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .nm b {
    font-size: 14px;
    font-weight: 600;
  }
  .nm span {
    font-size: 12.5px;
    color: var(--hw-tx2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tp {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    flex: none;
  }
  .tp b {
    font-size: 18px;
    font-weight: 600;
  }
  .tp span {
    font-size: 12px;
    color: var(--hw-tx2);
  }
  .step {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: none;
  }
  .step button {
    width: 44px;
    height: 24px;
    border: 1px solid var(--hw-line);
    background: var(--hw-card);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    padding: 0;
  }
  .act .step {
    flex-direction: row;
    gap: 6px;
  }
  .act .step button {
    width: 44px;
    height: 36px;
  }
  .card {
    border-radius: var(--ha-card-border-radius, 20px);
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    color: var(--hw-tx);
  }
  .hd {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
    margin: 2px 4px 8px;
  }
  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }
  .sub {
    font-size: 12px;
    color: var(--hw-tx2);
  }
  .badges {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .bd {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    color: var(--c);
    background: color-mix(in srgb, var(--c) 14%, transparent);
  }
  .rw {
    border-top: 1px solid var(--hw-line);
  }
  .sum {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 4px;
    min-height: 52px;
    cursor: pointer;
    width: 100%;
    border: none;
    background: none;
    text-align: left;
  }
  .chev {
    color: var(--hw-tx2);
    transition: transform 0.15s;
    flex: none;
  }
  .open .chev {
    transform: rotate(180deg);
  }
  .det {
    padding: 2px 4px 12px 52px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .tile .det {
    padding: 0 12px 12px 60px;
  }
  .mini {
    position: relative;
    height: 6px;
    border-radius: 3px;
    background: var(--hw-track);
  }
  .mini i {
    position: absolute;
    top: 0;
    bottom: 0;
    border-radius: 3px;
    background: color-mix(in srgb, var(--c) 55%, transparent);
  }
  .mini em {
    position: absolute;
    top: -3px;
    width: 3px;
    height: 12px;
    border-radius: 2px;
    background: var(--hw-tx);
  }
  .kv {
    font-size: 12.5px;
    color: var(--hw-tx2);
  }
  .act {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .pillrow {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .pill {
    min-height: 36px;
    padding: 5px 12px;
    border-radius: 999px;
    border: 1px solid var(--hw-line);
    background: transparent;
    font-size: 12.5px;
    cursor: pointer;
  }
  .pill.on {
    border-color: var(--hw-violet);
    background: color-mix(in srgb, var(--hw-violet) 14%, transparent);
    color: var(--hw-violet);
    font-weight: 600;
  }
  .obs {
    color: var(--hw-violet);
    font-weight: 600;
  }
`;
