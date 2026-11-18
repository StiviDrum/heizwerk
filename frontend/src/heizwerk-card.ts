/**
 * custom:heizwerk-card – room card for Heizwerk (variants standard / compact).
 * Data: climate.heizwerk_<room> attributes; day band from Zeitwerk's public
 * websocket API (zeitwerk/plans/get, zeitwerk/preview – no admin needed).
 */
import { LitElement, html, nothing, svg, type PropertyValues, type TemplateResult } from "lit";
import { strings, type Strings } from "./localize";
import {
  DIAL,
  arcPath,
  dayBand,
  dialPoint,
  fmtTarget,
  fmtTemp,
  fmtTime,
  fraction,
  fractionToValue,
  keyDelta,
  nextValue,
  parseRoom,
  pointToFraction,
  roomNote,
  statusView,
  stepTarget,
  trvText,
  type Fmt,
  type HassEntityLike,
  type Room,
  type Segment,
  type StatusView,
  type Tone,
  type ZeitwerkPlan,
} from "./model";
import { compactStyles, standardStyles, tokens } from "./styles";
import "./editor";

declare const __VERSION__: string;

interface Hass {
  states: Record<string, HassEntityLike>;
  locale?: { language?: string };
  language?: string;
  themes?: { darkMode?: boolean };
  user?: { is_admin?: boolean };
  callService(domain: string, service: string, data: Record<string, unknown>): Promise<unknown>;
  callWS<T>(msg: Record<string, unknown>): Promise<T>;
}

export interface CardConfig {
  type: string;
  variant?: "standard" | "compact";
  entity?: string;
  entities?: string[];
  title?: string;
  dial_min?: number;
  dial_max?: number;
  manual_duration?: "next" | number;
}

type Duration = "next" | 60 | 180;

interface DragState {
  pointerId: number;
  el: Element;
  room: Room;
  value: number | null;
}

interface PlanData {
  plan: ZeitwerkPlan | null;
  segments: Segment[];
  fetched: number;
  day: string;
  key: string;
}

const PLAN_TTL = 10 * 60 * 1000;
const CLICK_DELAY = 700;

const icon = (d: string, size = 17): TemplateResult =>
  html`<svg class="i" width=${size} height=${size} viewBox="0 0 24 24" aria-hidden="true">
    ${svg`<path d=${d} />`}
  </svg>`;

const P = {
  plus: "M5 12h14M12 5v14",
  minus: "M5 12h14",
  chev: "M6 9l6 6 6-6",
  flame:
    "M12 3c1 3 4.5 4.8 4.5 9a4.5 4.5 0 0 1-9 0c0-2 1-3.4 2.2-4.4 0 1.6 1 2.7 2.1 2.7 0-2.7-1-4.6.2-7.3z",
  window:
    "M5.5 3h13A1.5 1.5 0 0 1 20 4.5v15a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19.5v-15A1.5 1.5 0 0 1 5.5 3zM12 3v18M4 12h16",
  check: "M5 12l4 4 10-10",
  moon: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z",
  warn: "M12 4l9 16H3zM12 10v4M12 17.5v.01",
  person: "M12 4a4 4 0 1 0 0 8a4 4 0 1 0 0-8zM4 21c1-4 4-6 8-6s7 2 8 6",
  clock: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM12 7v5l3 2",
  drop: "M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5z",
};

function statusIcon(room: Room, sv: StatusView): string {
  if (sv.tone === "red") return P.warn;
  if (room.status === "window") return P.window;
  if (sv.locked) return P.lock;
  switch (sv.tone as Tone) {
    case "heat":
      return P.flame;
    case "green":
      return P.check;
    case "violet":
      return P.person;
    default:
      return P.moon;
  }
}

export class HeizwerkCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _plans: { state: true },
    _open: { state: true },
    _duration: { state: true },
    _pending: { state: true },
    _dragging: { state: true },
  };

  static styles = [tokens, standardStyles, compactStyles];

  hass?: Hass;
  private _config?: CardConfig;
  private _plans: Record<string, PlanData> = {};
  private _open: Record<string, boolean> = {};
  private _duration: Record<string, Duration> = {};
  private _pending: Record<string, number> = {};
  private _timers: Record<string, number> = {};
  private _dragging = false;
  private _drag: DragState | null = null;
  private _loading = new Set<string>();

  setConfig(config: CardConfig): void {
    if (!config || (!config.entity && !(config.entities && config.entities.length))) {
      throw new Error("heizwerk-card: 'entity' or 'entities' is required");
    }
    this._config = { variant: "standard", dial_min: 12, dial_max: 26, ...config };
  }

  static getConfigElement(): HTMLElement {
    return document.createElement("heizwerk-card-editor");
  }

  static getStubConfig(hass: Hass): Partial<CardConfig> {
    const entity = Object.keys(hass?.states ?? {}).find((e) => e.startsWith("climate.heizwerk_"));
    return { variant: "standard", entity: entity ?? "climate.heizwerk_bad" };
  }

  getCardSize(): number {
    if (this._config?.variant !== "compact") return 9;
    return this._config.entities ? 1 + this._config.entities.length : 1;
  }

  getGridOptions(): Record<string, number> {
    if (this._config?.variant === "compact" && !this._config.entities)
      return { columns: 6, rows: 1, min_rows: 1 };
    return { columns: 12, min_columns: 6 };
  }

  private get _s(): Strings {
    return strings(this.hass?.locale?.language ?? this.hass?.language);
  }

  private get _fmt(): Fmt {
    return { lang: this.hass?.locale?.language ?? this.hass?.language ?? "en", now: new Date() };
  }

  private get _entities(): string[] {
    const c = this._config;
    if (!c) return [];
    return c.variant === "compact" && c.entities?.length ? c.entities : c.entity ? [c.entity] : [];
  }

  protected updated(changed: PropertyValues): void {
    super.updated(changed);
    if (changed.has("hass") && this.hass) {
      this.toggleAttribute("dark", !!this.hass.themes?.darkMode);
      for (const id of this._entities) {
        const st = this.hass.states[id];
        if (st) this._ensurePlan(parseRoom(st));
      }
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    for (const t of Object.values(this._timers)) window.clearTimeout(t);
    this._timers = {};
    this._endDrag(false);
  }

  // --- Zeitwerk data ----------------------------------------------------------

  private async _ensurePlan(room: Room): Promise<void> {
    const plan = room.plan;
    if (!plan || !this.hass || this._loading.has(plan)) return;
    const now = new Date();
    const day = now.toDateString();
    // Refetch when the profile/next change changed, on a new day or after the TTL.
    const key = `${room.profileId}|${room.nextChange?.toISOString() ?? ""}`;
    const cached = this._plans[plan];
    if (
      cached &&
      cached.day === day &&
      cached.key === key &&
      now.getTime() - cached.fetched < PLAN_TTL
    )
      return;
    this._loading.add(plan);
    try {
      const [planData, preview] = await Promise.all([
        this.hass
          .callWS<ZeitwerkPlan>({ type: "zeitwerk/plans/get", plan_id: plan })
          .catch(() => null),
        this.hass
          .callWS<{ plans?: Record<string, Segment[]> }>({
            type: "zeitwerk/preview",
            plan_ids: [plan],
          })
          .catch(() => ({}) as { plans?: Record<string, Segment[]> }),
      ]);
      this._plans = {
        ...this._plans,
        [plan]: {
          plan: planData,
          segments: preview.plans?.[plan] ?? [],
          fetched: now.getTime(),
          day,
          key,
        },
      };
    } finally {
      this._loading.delete(plan);
    }
  }

  private _planOf(room: Room): PlanData | null {
    return room.plan ? (this._plans[room.plan] ?? null) : null;
  }

  // --- Actions ------------------------------------------------------------------

  private _moreInfo(entityId: string): void {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }),
    );
  }

  /** Duration for set_manual; "next" (= no duration field) without a resume path. */
  private _durationFor(room: Room): Duration {
    if (!room.resumeAvailable) return "next";
    const own = this._duration[room.entityId];
    if (own) return own;
    const cfg = this._config?.manual_duration;
    return cfg === 60 || cfg === 180 ? cfg : "next";
  }

  private _shownTarget(room: Room): number | null {
    return this._pending[room.entityId] ?? room.target;
  }

  private _step(room: Room, delta: number, ev?: Event): void {
    ev?.stopPropagation();
    const base = this._shownTarget(room);
    if (base === null) return;
    this._schedule(room, stepTarget(base, delta, room), CLICK_DELAY);
  }

  /** Show `value` right away and commit it after `delay` ms (debounced per room). */
  private _schedule(room: Room, value: number, delay: number): void {
    this._pending = { ...this._pending, [room.entityId]: value };
    window.clearTimeout(this._timers[room.entityId]);
    this._timers[room.entityId] = window.setTimeout(() => this._commit(room, value), delay);
  }

  // --- Dial dragging / keyboard ---------------------------------------------------

  private _dialRange(): [number, number] {
    return [this._config?.dial_min ?? 12, this._config?.dial_max ?? 26];
  }

  /** Client coordinates → viewBox coordinates (handles CSS scaling). */
  private _toViewBox(svgEl: SVGSVGElement, e: PointerEvent): { x: number; y: number } {
    const ctm = svgEl.getScreenCTM?.();
    if (ctm) {
      const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
      return { x: p.x, y: p.y };
    }
    const r = svgEl.getBoundingClientRect();
    const vb = svgEl.viewBox.baseVal;
    return {
      x: vb.x + ((e.clientX - r.left) * vb.width) / (r.width || 1),
      y: vb.y + ((e.clientY - r.top) * vb.height) / (r.height || 1),
    };
  }

  private _dragValue(room: Room, svgEl: SVGSVGElement, e: PointerEvent): number {
    const { x, y } = this._toViewBox(svgEl, e);
    const [min, max] = this._dialRange();
    return fractionToValue(pointToFraction(x, y), min, max, room.step, room);
  }

  private _dragTo(room: Room, value: number): void {
    if (!this._drag) return;
    this._drag.value = value;
    window.clearTimeout(this._timers[room.entityId]);
    delete this._timers[room.entityId];
    if (this._pending[room.entityId] !== value)
      this._pending = { ...this._pending, [room.entityId]: value };
  }

  private _onDialDown(room: Room, e: PointerEvent): void {
    if (this._drag || (e.pointerType === "mouse" && e.button !== 0)) return;
    if (this._shownTarget(room) === null) return;
    const svgEl = e.currentTarget as SVGSVGElement;
    const el = e.target as Element;
    if (!el.classList?.contains("hit")) return;
    e.preventDefault();
    e.stopPropagation();
    // No programmatic focus: Chrome would draw the keyboard focus ring on touch.
    try {
      el.setPointerCapture(e.pointerId);
    } catch {
      /* capture not supported – moves still arrive while over the dial */
    }
    this._drag = { pointerId: e.pointerId, el, room, value: null };
    this._dragging = true;
    // Tapping the arc jumps there; grabbing the knob keeps the value until moved.
    if (!el.classList.contains("knob-hit")) this._dragTo(room, this._dragValue(room, svgEl, e));
  }

  private _onDialMove(room: Room, e: PointerEvent): void {
    if (!this._drag || e.pointerId !== this._drag.pointerId) return;
    e.preventDefault();
    this._drag.room = room;
    this._dragTo(room, this._dragValue(room, e.currentTarget as SVGSVGElement, e));
  }

  private _onDialUp(e: PointerEvent): void {
    if (!this._drag || e.pointerId !== this._drag.pointerId) return;
    this._endDrag(true);
  }

  /** Finish a drag: release capture and (optionally) commit once. */
  private _endDrag(commit: boolean): void {
    const d = this._drag;
    if (!d) return;
    this._drag = null;
    this._dragging = false;
    try {
      if (d.el.hasPointerCapture?.(d.pointerId)) d.el.releasePointerCapture(d.pointerId);
    } catch {
      /* element already gone */
    }
    if (d.value === null) return;
    if (commit && d.value !== d.room.target) {
      this._schedule(d.room, d.value, 0);
    } else {
      const { [d.room.entityId]: _, ...rest } = this._pending;
      void _;
      this._pending = rest;
    }
  }

  private _onDialKey(room: Room, e: KeyboardEvent): void {
    const delta = keyDelta(e.key, room.step || 0.5);
    if (delta === null) return;
    e.preventDefault();
    e.stopPropagation();
    this._step(room, delta);
  }

  private async _commit(room: Room, value: number): Promise<void> {
    delete this._timers[room.entityId];
    const duration = this._durationFor(room);
    const data: Record<string, unknown> = { entity_id: room.entityId, temperature: value };
    if (duration !== "next") data.duration = { minutes: duration };
    try {
      await this.hass?.callService("heizwerk", "set_manual", data);
    } finally {
      const { [room.entityId]: _, ...rest } = this._pending;
      void _;
      this._pending = rest;
    }
  }

  private _setDuration(room: Room, d: Duration, ev: Event): void {
    ev.stopPropagation();
    this._duration = { ...this._duration, [room.entityId]: d };
    // An active override takes the new duration right away.
    if (room.status === "manual" && room.manualTarget !== null) {
      void this._commitDuration(room, room.manualTarget, d);
    }
  }

  private async _commitDuration(room: Room, value: number, d: Duration): Promise<void> {
    const data: Record<string, unknown> = { entity_id: room.entityId, temperature: value };
    if (d !== "next") data.duration = { minutes: d };
    await this.hass?.callService("heizwerk", "set_manual", data);
  }

  private _resume(room: Room, ev: Event): void {
    ev.stopPropagation();
    void this.hass?.callService("heizwerk", "resume", { entity_id: room.entityId });
  }

  private _toggle(id: string): void {
    this._open = { ...this._open, [id]: !this._open[id] };
  }

  // --- Render ---------------------------------------------------------------------

  protected render(): TemplateResult | typeof nothing {
    if (!this._config || !this.hass) return nothing;
    const c = this._config;
    if (c.variant === "compact") {
      return c.entities?.length ? this._renderHouse(c.entities) : this._renderTileFor(c.entity!);
    }
    const st = this.hass.states[c.entity ?? ""];
    if (!st) return this._error(`${this._s.missing}: ${c.entity}`);
    if (!("room_name" in st.attributes) && !("status" in st.attributes))
      return this._error(`${this._s.notHeizwerk}: ${c.entity}`);
    return this._renderStandard(parseRoom(st));
  }

  private _error(msg: string): TemplateResult {
    return html`<ha-card><div class="err">${msg}</div></ha-card>`;
  }

  private _renderStandard(room: Room): TemplateResult {
    const s = this._s;
    const fmt = this._fmt;
    const pd = this._planOf(room);
    const sv = statusView(room, s, fmt, pd?.plan ?? null);
    const note = roomNote(room, s, fmt);
    const target = this._shownTarget(room);
    const sub = room.plan
      ? `${room.profile ? `${s.profile} ${room.profile} · ` : ""}${s.plan} ${room.plan}`
      : s.noPlan;
    return html`<ha-card class="std t-${sv.tone}">
      <div class="head">
        <div>
          <h2>${room.name}</h2>
          <div class="sub">${sub}</div>
        </div>
        <button class="iconbtn" aria-label=${s.more} @click=${() => this._moreInfo(room.entityId)}>
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            aria-hidden="true"
            style="fill:currentColor"
          >
            <circle cx="5" cy="12" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="19" cy="12" r="2" />
          </svg>
        </button>
      </div>
      ${
        sv.chip
          ? html`<button class="chip t-${sv.tone}" @click=${() => this._moreInfo(room.entityId)}>
              ${icon(statusIcon(room, sv), 18)}${sv.chip}
            </button>`
          : nothing
      }
      ${this._renderDial(room, target, sv)}
      <div class="ctrl">
        <button
          class="round"
          aria-label=${s.lower}
          ?disabled=${target === null || target <= room.minTemp}
          @click=${(e: Event) => this._step(room, -room.step, e)}
        >
          ${icon(P.minus, 20)}
        </button>
        <div class="ziel"><span>${s.target}</span><b class="num">${fmtTemp(target, fmt)}°</b></div>
        <button
          class="round"
          aria-label=${s.raise}
          ?disabled=${target === null || target >= room.maxTemp}
          @click=${(e: Event) => this._step(room, room.step, e)}
        >
          ${icon(P.plus, 20)}
        </button>
      </div>
      ${this._renderNext(room, pd, sv)}
      ${
        note
          ? html`<div class="note t-${note.tone}">
              <svg
                class="i"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                aria-hidden="true"
                style="flex:none;margin-top:1px;stroke:var(--c);stroke-width:2"
              >
                ${svg`<path d=${note.tone === "amber" && room.ventilationDone ? P.check : note.tone === "teal" ? P.window : P.warn} />`}
              </svg>
              <div><strong>${note.title}</strong><span>${note.text}</span></div>
            </div>`
          : nothing
      }
      ${this._renderClimate(room)} ${this._renderBand(room, pd)} ${this._renderFoot(room, sv)}
    </ha-card>`;
  }

  private _renderDial(room: Room, target: number | null, sv: StatusView): TemplateResult {
    const s = this._s;
    const fmt = this._fmt;
    const [min, max] = this._dialRange();
    const fc = room.current !== null ? fraction(room.current, min, max) : null;
    const ft = target !== null ? fraction(target, min, max) : null;
    const pc = fc !== null ? dialPoint(fc) : null;
    const pt = ft !== null ? dialPoint(ft) : null;
    // While a new target is being chosen (drag / ± before commit) colour by
    // direction: warmer than the room = heat, otherwise the manual colour.
    const choosing = this._pending[room.entityId] !== undefined;
    const arcColor =
      choosing && target !== null && room.current !== null
        ? target > room.current
          ? "var(--hw-heatf)"
          : "var(--hw-violet)"
        : sv.tone === "heat"
          ? "var(--hw-heatf)"
          : "var(--c)";
    const label = `${s.actual} ${fmtTemp(room.current, fmt)}°, ${s.target}`;
    const valueText = `${s.target} ${fmtTarget(target, fmt)} °C`;
    const track = arcPath(0, 1);
    return html`<div class="dial ${this._dragging ? "dragging" : ""}">
      <svg
        width="260"
        height="214"
        viewBox="0 0 260 214"
        role="slider"
        tabindex="0"
        aria-label=${label}
        aria-valuemin=${room.minTemp}
        aria-valuemax=${room.maxTemp}
        aria-valuenow=${target ?? nothing}
        aria-valuetext=${valueText}
        aria-disabled=${target === null ? "true" : "false"}
        @pointerdown=${(e: PointerEvent) => this._onDialDown(room, e)}
        @pointermove=${(e: PointerEvent) => this._onDialMove(room, e)}
        @pointerup=${(e: PointerEvent) => this._onDialUp(e)}
        @pointercancel=${(e: PointerEvent) => this._onDialUp(e)}
        @lostpointercapture=${(e: PointerEvent) => this._onDialUp(e)}
        @keydown=${(e: KeyboardEvent) => this._onDialKey(room, e)}
      >
        ${svg`<path d=${track} fill="none" stroke="var(--hw-track)" stroke-width="14" stroke-linecap="round" />`}
        ${
          fc !== null && ft !== null && Math.abs(ft - fc) > 0.001
            ? svg`<path d=${arcPath(fc, ft)} fill="none" stroke=${arcColor} stroke-opacity=".45" stroke-width="14" stroke-linecap="round" />`
            : nothing
        }
        ${
          pc
            ? svg`<circle cx=${pc.x} cy=${pc.y} r="8" fill="var(--hw-card)" stroke="var(--hw-tx)" stroke-width="3" />`
            : nothing
        }
        ${
          target !== null
            ? svg`<path class="hit" d=${track} fill="none" stroke="transparent" stroke-width="44" stroke-linecap="round" />`
            : nothing
        }
        ${
          pt
            ? svg`<circle class="halo" cx=${pt.x} cy=${pt.y} r="18" fill=${arcColor} />
              <circle class="knob" cx=${pt.x} cy=${pt.y} r="11" fill=${arcColor} stroke="var(--hw-card)" stroke-width="3" />
              <circle class="hit knob-hit" cx=${pt.x} cy=${pt.y} r="24" fill="transparent" />`
            : nothing
        }
      </svg>
      <div class="mid">
        <span class="s">${s.actual}</span>
        <span class="big num">${fmtTemp(room.current, fmt)}°</span>
        <span class="s">${room.temperatureSource === "trv" ? s.trvSensor : s.roomSensor}</span>
      </div>
      <span class="end" style="left:${DIAL.cx - 86}px">${fmtTarget(min, fmt)}°</span>
      <span class="end" style="right:${DIAL.cx - 86}px">${fmtTarget(max, fmt)}°</span>
    </div>`;
  }

  private _renderNext(
    room: Room,
    pd: PlanData | null,
    sv: StatusView,
  ): TemplateResult | typeof nothing {
    const s = this._s;
    const fmt = this._fmt;
    if (room.status === "manual") {
      return html`<div class="next">
        ${icon(P.person, 16)}<span>${sv.text}</span>
        ${
          room.resumeAvailable
            ? html`<button class="link" @click=${(e: Event) => this._resume(room, e)}>
                ${s.resume}
              </button>`
            : nothing
        }
      </div>`;
    }
    if (!room.nextChange || !room.nextProfile) return nothing;
    const v = nextValue(pd?.plan ?? null, room);
    const tpl = v !== null ? s.nextLine : s.nextLineNoValue;
    const text = tpl
      .replace("{p}", room.profile ?? "")
      .replace("{time}", fmtTime(room.nextChange, fmt))
      .replace("{n}", room.nextProfile)
      .replace("{v}", fmtTarget(v, fmt));
    return html`<div class="next">${icon(P.clock, 16)}${text}</div>`;
  }

  private _renderClimate(room: Room): TemplateResult | typeof nothing {
    const s = this._s;
    const fmt = this._fmt;
    const cells: TemplateResult[] = [];
    if (room.humidity !== null) {
      const lo = 40;
      const hi = room.humidityThreshold;
      cells.push(
        html`<div class="m t-teal">
          <span class="k">${icon(P.drop, 14)}${s.humidity}</span>
          <span class="v num">${fmtTemp(room.humidity, fmt, 0)} %</span>
          <div class="bar">
            <i
              style="left:${lo}%;width:${Math.max(0, hi - lo)}%;background:color-mix(in srgb,var(--hw-teal) 40%,transparent)"
            ></i>
            <i
              style="left:${Math.min(99, room.humidity)}%;top:-3px;bottom:auto;width:3px;height:12px;background:var(--hw-teal)"
            ></i>
          </div>
        </div>`,
      );
    }
    if (room.dewPoint !== null) {
      cells.push(
        html`<div class="m">
          <span class="k">${s.dewPoint}</span>
          <span class="v num">${fmtTemp(room.dewPoint, fmt)}°</span>
          ${
            room.outdoorDewPoint !== null
              ? html`<span class="n">${s.outside} ${fmtTemp(room.outdoorDewPoint, fmt)}°</span>`
              : nothing
          }
        </div>`,
      );
    }
    if (room.wallHumidity !== null) {
      const warn = room.moldLevel === "warning" || room.moldLevel === "alarm";
      cells.push(
        html`<div class="m ${room.moldLevel === "alarm" ? "t-red" : "t-amber"}">
          <span class="k">${s.wallHumidity}</span>
          <span class="v num">${fmtTemp(room.wallHumidity, fmt, 0)} %</span>
          <span class="n ${warn ? "warn" : ""}"
            >${(warn ? s.wallAttention : s.wallOk).replace("{t}", fmtTemp(room.wallTemperature, fmt))}</span
          >
        </div>`,
      );
    }
    if (!cells.length) return nothing;
    return html`<div class="grid" style="--cols:${cells.length}">${cells}</div>`;
  }

  private _renderBand(room: Room, pd: PlanData | null): TemplateResult | typeof nothing {
    if (!pd || !pd.segments.length) return nothing;
    const s = this._s;
    const fmt = this._fmt;
    const band = dayBand(pd.segments, pd.plan, room.entityId, fmt.now);
    const legend = band.legend
      .map((l) => (l.value !== null ? `${l.name} ${fmtTarget(l.value, fmt)}°` : l.name))
      .join(" · ");
    return html`<div class="day">
      <div class="row"><span>${s.today}</span><span>${legend}</span></div>
      <div class="track">
        ${band.parts.map((p) => html`<i style="left:${p.left}%;width:${p.width}%"></i>`)}
        <em style="left:${band.now}%"></em>
      </div>
      <div class="row" style="font-size:11.5px">
        <span>0</span><span>6</span><span>12</span><span>18</span><span>24</span>
      </div>
    </div>`;
  }

  private _renderFoot(room: Room, sv: StatusView): TemplateResult {
    const s = this._s;
    const fmt = this._fmt;
    return html`<div class="foot">
      <span>${trvText(room, s, fmt, sv.locked)}</span>
      <span>${s.sensor}: ${room.temperatureSource === "trv" ? s.sensorTrv : s.sensorRoom}</span>
      ${room.lastSync ? html`<span>${s.sync} ${fmtTime(room.lastSync, fmt)}</span>` : nothing}
      ${room.observeOnly ? html`<span class="obs">${s.observeOnly}</span>` : nothing}
    </div>`;
  }

  // --- Compact ------------------------------------------------------------------

  private _summary(room: Room, sv: StatusView): TemplateResult {
    const fmt = this._fmt;
    const target = this._shownTarget(room);
    return html`<span class="ic t-${sv.tone}">${icon(statusIcon(room, sv))}</span>
      <span class="nm"><b>${room.name}</b><span>${sv.text}</span></span>
      <span class="tp"
        ><b class="num">${fmtTemp(room.current, fmt)}°</b
        ><span class="num">${this._s.target} ${fmtTarget(target, fmt)}°</span></span
      >`;
  }

  private _stepButtons(room: Room): TemplateResult {
    const s = this._s;
    return html`<span class="step">
      <button
        aria-label="${room.name}: ${s.raise}"
        @click=${(e: Event) => this._step(room, room.step, e)}
      >
        ${icon(P.plus, 16)}
      </button>
      <button
        aria-label="${room.name}: ${s.lower}"
        @click=${(e: Event) => this._step(room, -room.step, e)}
      >
        ${icon(P.minus, 16)}
      </button>
    </span>`;
  }

  private _details(room: Room, sv: StatusView): TemplateResult {
    const s = this._s;
    const fmt = this._fmt;
    const pd = this._planOf(room);
    const target = this._shownTarget(room);
    // Mini bar from 12..26 °C like the dial: fill = current, marker = target.
    const min = this._config?.dial_min ?? 12;
    const max = this._config?.dial_max ?? 26;
    const fill = room.current !== null ? fraction(room.current, min, max) * 100 : 0;
    const mark = target !== null ? fraction(target, min, max) * 100 : null;
    const kv: string[] = [];
    if (room.humidity !== null) kv.push(`${s.humidity} ${fmtTemp(room.humidity, fmt, 0)} %`);
    if (room.wallHumidity !== null)
      kv.push(`${s.wallOk.split(" ")[0]} ${fmtTemp(room.wallHumidity, fmt, 0)} %`);
    if (room.nextChange && room.profile)
      kv.push(`${room.profile} ${s.until} ${fmtTime(room.nextChange, fmt)}`);
    if (room.ventilationRecommended) kv.push(s.ventRecommended);
    if (room.observeOnly) kv.push(s.observeOnly);
    void pd;
    const d = this._durationFor(room);
    const pill = (value: Duration, label: string) =>
      html`<button
        class="pill ${d === value ? "on" : ""}"
        aria-pressed=${d === value}
        @click=${(e: Event) => this._setDuration(room, value, e)}
      >
        ${label}
      </button>`;
    return html`<div class="det t-${sv.tone}">
      <div class="mini">
        <i style="left:0;width:${fill}%"></i>
        ${mark !== null ? html`<em style="left:${mark}%"></em>` : nothing}
      </div>
      <div class="kv">${kv.join(" · ")}</div>
      <div class="act">
        <span class="step">
          <button
            aria-label="${room.name}: ${s.lower}"
            @click=${(e: Event) => this._step(room, -room.step, e)}
          >
            ${icon(P.minus, 16)}
          </button>
          <button
            aria-label="${room.name}: ${s.raise}"
            @click=${(e: Event) => this._step(room, room.step, e)}
          >
            ${icon(P.plus, 16)}
          </button>
        </span>
        ${
          room.resumeAvailable
            ? html`<span class="pillrow">
                ${pill("next", s.untilNextBlock)} ${pill(60, s.hour1)} ${pill(180, s.hours3)}
              </span>`
            : nothing
        }
        ${
          room.status === "manual" && room.resumeAvailable
            ? html`<button class="pill" @click=${(e: Event) => this._resume(room, e)}>
                ${s.resume}
              </button>`
            : nothing
        }
      </div>
    </div>`;
  }

  private _renderTileFor(entityId: string): TemplateResult {
    const st = this.hass!.states[entityId];
    if (!st) return this._error(`${this._s.missing}: ${entityId}`);
    const room = parseRoom(st);
    const sv = statusView(room, this._s, this._fmt, this._planOf(room)?.plan ?? null);
    const open = !!this._open[entityId];
    return html`<ha-card class="tile ${open ? "open" : ""}">
      <div
        class="row1"
        role="button"
        tabindex="0"
        aria-expanded=${open}
        @click=${() => this._toggle(entityId)}
        @keydown=${(e: KeyboardEvent) => (e.key === "Enter" || e.key === " ") && this._toggle(entityId)}
      >
        ${this._summary(room, sv)} ${this._stepButtons(room)}
      </div>
      ${open ? this._details(room, sv) : nothing}
    </ha-card>`;
  }

  private _renderHouse(entities: string[]): TemplateResult {
    const s = this._s;
    const fmt = this._fmt;
    const rooms = entities
      .map((id) => this.hass!.states[id])
      .filter((st): st is HassEntityLike => !!st)
      .map(parseRoom);
    const first = rooms[0];
    const subParts: string[] = [];
    if (first?.seasonActive !== null && first?.seasonActive !== undefined)
      subParts.push(first.seasonActive ? s.seasonActive : s.seasonInactive);
    if (first?.outdoor !== null && first?.outdoor !== undefined)
      subParts.push(`${s.outdoorShort} ${fmtTemp(first.outdoor, fmt)}°`);
    const windows = rooms.filter((r) => r.windowOpen).length;
    return html`<ha-card class="card">
      <div class="hd">
        <div>
          <h2>${this._config?.title ?? s.heatingTitle}</h2>
          <span class="sub">${subParts.join(" · ")}</span>
        </div>
        <span class="badges">
          ${
            windows
              ? html`<span class="bd t-heat">${icon(P.window, 14)}${windows} ${s.windows}</span>`
              : nothing
          }
        </span>
      </div>
      ${entities.map((id) => {
        const st = this.hass!.states[id];
        if (!st) return html`<div class="rw"><div class="sum err">${s.missing}: ${id}</div></div>`;
        const room = parseRoom(st);
        const sv = statusView(room, s, fmt, this._planOf(room)?.plan ?? null);
        const open = !!this._open[id];
        return html`<div class="rw ${open ? "open" : ""}">
          <button class="sum" aria-expanded=${open} @click=${() => this._toggle(id)}>
            ${this._summary(room, sv)}
            <span class="chev" aria-hidden="true">${icon(P.chev, 16)}</span>
          </button>
          ${open ? this._details(room, sv) : nothing}
        </div>`;
      })}
    </ha-card>`;
  }
}

if (!customElements.get("heizwerk-card")) {
  customElements.define("heizwerk-card", HeizwerkCard);
  (window as unknown as { customCards?: unknown[] }).customCards ??= [];
  (window as unknown as { customCards: unknown[] }).customCards.push({
    type: "heizwerk-card",
    name: "Heizwerk",
    description: "Room heating card (standard / compact)",
    preview: true,
    documentationURL: "https://github.com/StiviDrum/heizwerk",
  });
  console.info(`%c HEIZWERK-CARD %c ${__VERSION__} `, "color:#fff;background:#b85500", "");
}
