/**
 * Pure view logic of the Heizwerk card (no DOM, no Lit) – unit tested.
 * Input is the climate.heizwerk_<room> state (attributes per docs/SPEC.md §5)
 * plus optional Zeitwerk data (plan + today's preview segments).
 */
import { Strings } from "./localize";

export interface HassEntityLike {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

export interface TrvAttr {
  entity_id: string;
  available: boolean;
  hvac_mode: string | null;
  setpoint: number | null;
  current: number | null;
  hvac_action: string | null;
}

export interface LockAttr {
  type: string;
  since: string | null;
  entity_ids?: string[];
}

export interface ZeitwerkAction {
  action?: string;
  service?: string;
  target?: { entity_id?: string | string[] };
  entity_id?: string | string[];
  data?: Record<string, unknown>;
}

export interface ZeitwerkProfile {
  id: string;
  name: string;
  color?: string;
  actions?: ZeitwerkAction[];
}

export interface ZeitwerkPlan {
  id: string;
  name?: string;
  default_profile?: string;
  profiles: ZeitwerkProfile[];
}

export interface Segment {
  start: string;
  end: string;
  profile: string;
}

export type Tone = "heat" | "green" | "blue" | "violet" | "red" | "eco" | "muted";

export interface Room {
  entityId: string;
  name: string;
  status: string;
  current: number | null;
  target: number | null;
  scheduled: number | null;
  humidity: number | null;
  dewPoint: number | null;
  outdoorDewPoint: number | null;
  outdoor: number | null;
  wallTemperature: number | null;
  wallHumidity: number | null;
  moldLevel: string | null;
  humidityThreshold: number;
  windowOpen: boolean;
  windowOpenSince: Date | null;
  ventilationMinutes: number;
  ventilationDone: boolean;
  ventilationRecommended: boolean;
  manualTarget: number | null;
  manualUntil: Date | null;
  manualMode: string | null;
  manualBy: string | null;
  plan: string | null;
  profile: string | null;
  profileId: string | null;
  nextChange: Date | null;
  nextProfile: string | null;
  targetEntity: string | null;
  trvs: TrvAttr[];
  trvUnavailableSince: Date | null;
  locks: LockAttr[];
  observeOnly: boolean;
  lastSync: Date | null;
  temperatureSource: string;
  seasonActive: boolean | null;
  minTemp: number;
  maxTemp: number;
  step: number;
}

const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v)
    ? v
    : typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))
      ? Number(v)
      : null;

const date = (v: unknown): Date | null => {
  if (typeof v !== "string" || !v) return null;
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
};

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

/** Parse the climate entity into a typed room. */
export function parseRoom(state: HassEntityLike): Room {
  const a = state.attributes;
  return {
    entityId: state.entity_id,
    name: str(a.room_name) ?? str(a.friendly_name) ?? state.entity_id,
    status: str(a.status) ?? (state.state === "off" ? "off" : "reached"),
    current: num(a.current_temperature),
    target: num(a.temperature),
    scheduled: num(a.scheduled_target),
    humidity: num(a.current_humidity),
    dewPoint: num(a.dew_point),
    outdoorDewPoint: num(a.outdoor_dew_point),
    outdoor: num(a.outdoor_temperature),
    wallTemperature: num(a.wall_temperature),
    wallHumidity: num(a.wall_humidity),
    moldLevel: str(a.mold_level),
    humidityThreshold: num(a.humidity_threshold) ?? 60,
    windowOpen: a.window_open === true,
    windowOpenSince: date(a.window_open_since),
    ventilationMinutes: num(a.ventilation_minutes) ?? 10,
    ventilationDone: a.ventilation_done === true,
    ventilationRecommended: a.ventilation_recommended === true,
    manualTarget: num(a.manual_target),
    manualUntil: date(a.manual_until),
    manualMode: str(a.manual_mode),
    manualBy: str(a.manual_by),
    plan: str(a.zeitwerk_plan),
    profile: str(a.zeitwerk_profile),
    profileId: str(a.zeitwerk_profile_id),
    nextChange: date(a.next_change),
    nextProfile: str(a.next_profile),
    targetEntity: str(a.target_entity),
    trvs: Array.isArray(a.trvs) ? (a.trvs as TrvAttr[]) : [],
    trvUnavailableSince: date(a.trv_unavailable_since),
    locks: Array.isArray(a.locks) ? (a.locks as LockAttr[]) : [],
    observeOnly: a.observe_only === true,
    lastSync: date(a.last_sync),
    temperatureSource: str(a.temperature_source) ?? "sensor",
    seasonActive: typeof a.season_active === "boolean" ? a.season_active : null,
    minTemp: num(a.min_temp) ?? 5,
    maxTemp: num(a.max_temp) ?? 30,
    step: num(a.target_temp_step) ?? 0.5,
  };
}

// --- Formatting -------------------------------------------------------------

export interface Fmt {
  lang: string;
  now: Date;
}

export function fmtTemp(value: number | null, fmt: Fmt, digits = 1): string {
  if (value === null) return "–";
  return new Intl.NumberFormat(fmt.lang, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** Target like the mockup: "22" for whole numbers, "22,5" otherwise. */
export function fmtTarget(value: number | null, fmt: Fmt): string {
  if (value === null) return "–";
  return fmtTemp(value, fmt, Number.isInteger(value) ? 0 : 1);
}

/** "07:30", or "Mi 05:15" when not today. */
export function fmtTime(d: Date, fmt: Fmt): string {
  const time = new Intl.DateTimeFormat(fmt.lang, { hour: "2-digit", minute: "2-digit" }).format(d);
  if (d.toDateString() === fmt.now.toDateString()) return time;
  const day = new Intl.DateTimeFormat(fmt.lang, { weekday: "short" }).format(d).replace(".", "");
  return `${day} ${time}`;
}

export function minutesSince(d: Date | null, now: Date): number {
  return d ? Math.max(0, Math.floor((now.getTime() - d.getTime()) / 60000)) : 0;
}

// --- Zeitwerk ---------------------------------------------------------------

/** Value a profile sets on the target entity (value / temperature). */
export function profileValue(profile: ZeitwerkProfile, entityId: string | null): number | null {
  for (const action of profile.actions ?? []) {
    const ids = action.target?.entity_id ?? action.entity_id;
    const list = Array.isArray(ids) ? ids : ids ? [ids] : [];
    if (entityId && list.length && !list.includes(entityId)) continue;
    const v = num(action.data?.value ?? action.data?.temperature);
    if (v !== null) return v;
  }
  return null;
}

export interface BandPart {
  left: number;
  width: number;
  profile: string;
  warm: boolean;
}

export interface Band {
  parts: BandPart[];
  now: number;
  legend: { name: string; value: number | null }[];
}

/** Today's Zeitwerk segments as percentages; warm = above the lowest value. */
export function dayBand(
  segments: Segment[],
  plan: ZeitwerkPlan | null,
  targetEntity: string | null,
  now: Date,
): Band {
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  const span = end.getTime() - start.getTime();
  const values = new Map<string, number | null>();
  for (const p of plan?.profiles ?? []) values.set(p.id, profileValue(p, targetEntity));
  const used = [...new Set(segments.map((s) => s.profile))];
  const known = used.map((id) => values.get(id)).filter((v): v is number => v != null);
  const low = known.length ? Math.min(...known) : null;
  const parts: BandPart[] = [];
  for (const s of segments) {
    const a = Math.max(new Date(s.start).getTime(), start.getTime());
    const b = Math.min(new Date(s.end).getTime(), end.getTime());
    if (!(b > a)) continue;
    const value = values.get(s.profile) ?? null;
    const warm =
      value !== null && low !== null
        ? value > low
        : plan?.default_profile !== undefined && s.profile !== plan.default_profile;
    parts.push({
      left: ((a - start.getTime()) / span) * 100,
      width: ((b - a) / span) * 100,
      profile: s.profile,
      warm,
    });
  }
  const names = new Map((plan?.profiles ?? []).map((p) => [p.id, p.name]));
  const legend = used
    .map((id) => ({ name: names.get(id) ?? id, value: values.get(id) ?? null }))
    .sort((x, y) => (y.value ?? 0) - (x.value ?? 0));
  return {
    parts: parts.filter((p) => p.warm),
    now: ((now.getTime() - start.getTime()) / span) * 100,
    legend,
  };
}

/** Lowest set-point among the plan's profiles (for "Abgesenkt"). */
export function lowestValue(plan: ZeitwerkPlan | null, targetEntity: string | null): number | null {
  const vals = (plan?.profiles ?? [])
    .map((p) => profileValue(p, targetEntity))
    .filter((v): v is number => v !== null);
  return vals.length ? Math.min(...vals) : null;
}

export function nextValue(plan: ZeitwerkPlan | null, room: Room): number | null {
  const p = plan?.profiles.find((x) => x.name === room.nextProfile || x.id === room.nextProfile);
  return p ? profileValue(p, room.targetEntity) : null;
}

// --- Status -----------------------------------------------------------------

export interface StatusView {
  tone: Tone;
  text: string;
  /** Longer text for the chip of the standard card (null = no chip). */
  chip: string | null;
  locked: boolean;
}

const LOCK_STATUSES = new Set(["window", "season", "summer", "locked"]);

export function statusView(
  room: Room,
  s: Strings,
  fmt: Fmt,
  plan: ZeitwerkPlan | null = null,
): StatusView {
  const t = (v: number | null) => fmtTarget(v, fmt);
  if (room.status === "off") return { tone: "muted", text: s.off, chip: null, locked: false };
  if (room.status === "unavailable" || room.trvUnavailableSince) {
    const min = minutesSince(room.trvUnavailableSince, fmt.now);
    const text = s.trvUnavailable.replace("{min}", String(min));
    return { tone: "red", text, chip: text, locked: LOCK_STATUSES.has(room.status) };
  }
  if (room.status === "window") {
    const min = minutesSince(room.windowOpenSince, fmt.now);
    return {
      tone: "blue",
      text: s.windowPaused,
      chip: s.windowChip.replace("{min}", String(min)),
      locked: true,
    };
  }
  if (room.status === "season")
    return { tone: "blue", text: s.seasonOff, chip: s.seasonOff, locked: true };
  if (room.status === "summer") {
    const text = s.summer.replace("{t}", t(room.outdoor));
    return { tone: "blue", text, chip: text, locked: true };
  }
  if (room.status === "locked")
    return { tone: "blue", text: s.locked, chip: s.locked, locked: true };
  if (room.status === "manual") {
    let text = s.manual.replace("{t}", t(room.manualTarget ?? room.target));
    if (room.manualBy) text += ` ${s.by} ${room.manualBy}`;
    if (room.manualUntil) text += ` · ${s.until} ${fmtTime(room.manualUntil, fmt)}`;
    else text += ` · ${s.untilNext}`;
    return { tone: "violet", text, chip: null, locked: false };
  }
  if (room.status === "heating")
    return { tone: "heat", text: s.heating, chip: null, locked: false };
  // reached
  const low = lowestValue(plan, room.targetEntity);
  if (low !== null && room.target !== null && room.target <= low && room.nextChange) {
    return {
      tone: "eco",
      text: s.lowered.replace("{time}", fmtTime(room.nextChange, fmt)),
      chip: null,
      locked: false,
    };
  }
  let text = s.reached;
  if (room.nextChange && room.nextProfile)
    text += ` · ${s.fromTime.replace("{p}", room.nextProfile).replace("{time}", fmtTime(room.nextChange, fmt))}`;
  return { tone: "green", text, chip: null, locked: false };
}

// --- Dial geometry ------------------------------------------------------------

export const DIAL = { cx: 130, cy: 112.05, r: 92, start: 135, sweep: 270 };

export function dialPoint(fraction: number): { x: number; y: number } {
  const f = Math.max(0, Math.min(1, fraction));
  const a = ((DIAL.start + DIAL.sweep * f) * Math.PI) / 180;
  return {
    x: Math.round((DIAL.cx + DIAL.r * Math.cos(a)) * 10) / 10,
    y: Math.round((DIAL.cy + DIAL.r * Math.sin(a)) * 10) / 10,
  };
}

export function fraction(value: number, min: number, max: number): number {
  return max > min ? Math.max(0, Math.min(1, (value - min) / (max - min))) : 0;
}

/** SVG arc path between two fractions (clockwise). */
export function arcPath(f1: number, f2: number): string {
  const [a, b] = f1 <= f2 ? [f1, f2] : [f2, f1];
  const p1 = dialPoint(a);
  const p2 = dialPoint(b);
  const large = (b - a) * DIAL.sweep > 180 ? 1 : 0;
  return `M ${p1.x} ${p1.y} A ${DIAL.r} ${DIAL.r} 0 ${large} 1 ${p2.x} ${p2.y}`;
}

// --- Notes --------------------------------------------------------------------

export interface Note {
  tone: "amber" | "red" | "teal";
  title: string;
  text: string;
}

export function roomNote(room: Room, s: Strings, fmt: Fmt): Note | null {
  const outdoor = room.outdoor !== null ? `${fmtTemp(room.outdoor, fmt)} °C` : "–";
  if (room.windowOpen && room.ventilationDone) {
    return {
      tone: "amber",
      title: s.ventDone,
      text: s.ventDoneText
        .replace("{out}", outdoor)
        .replace("{rec}", String(room.ventilationMinutes))
        .replace("{min}", String(minutesSince(room.windowOpenSince, fmt.now))),
    };
  }
  if (room.moldLevel === "alarm" || room.moldLevel === "warning") {
    return {
      tone: room.moldLevel === "alarm" ? "red" : "amber",
      title: room.moldLevel === "alarm" ? s.moldAlarm : s.moldWarning,
      text: s.moldText
        .replace("{wall}", fmtTemp(room.wallTemperature, fmt))
        .replace("{rh}", fmtTemp(room.wallHumidity, fmt, 0)),
    };
  }
  if (room.ventilationRecommended) {
    return {
      tone: "teal",
      title: s.ventRecommended,
      text: s.ventRecommendedText
        .replace("{h}", fmtTemp(room.humidity, fmt, 0))
        .replace("{rec}", String(room.ventilationMinutes)),
    };
  }
  return null;
}

/** Footer text for the thermostats. */
export function trvText(room: Room, s: Strings, fmt: Fmt, locked: boolean): string {
  if (!room.trvs.length) return s.trvNone;
  const parts = room.trvs.map((trv) => {
    if (!trv.available) return s.trvOffline;
    if (trv.hvac_mode === "off") return locked ? s.trvOffFrost : s.trvOff;
    return s.trvHeatTo.replace("{t}", fmtTarget(trv.setpoint, fmt));
  });
  const unique = [...new Set(parts)];
  return `${s.trv}: ${unique.join(" / ")}`;
}

/** Clamp and round a target to the step. */
export function stepTarget(value: number, delta: number, room: Room): number {
  const step = room.step || 0.5;
  const v = Math.round((value + delta) / step) * step;
  return Math.max(room.minTemp, Math.min(room.maxTemp, Math.round(v * 100) / 100));
}
