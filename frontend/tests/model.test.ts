import { describe, expect, it } from "vitest";
import { strings } from "../src/localize";
import {
  arcPath,
  dayBand,
  dialPoint,
  fmtTarget,
  fmtTemp,
  fmtTime,
  parseRoom,
  profileValue,
  roomNote,
  statusView,
  stepTarget,
  trvText,
  type HassEntityLike,
  type ZeitwerkPlan,
} from "../src/model";

const de = strings("de");
const now = new Date(2026, 10, 18, 7, 14);
const fmt = { lang: "de", now };

function entity(attrs: Record<string, unknown>, state = "heat"): HassEntityLike {
  return {
    entity_id: "climate.heizwerk_bad",
    state,
    attributes: {
      room_name: "Bad",
      status: "heating",
      current_temperature: 18.5,
      temperature: 22,
      min_temp: 5,
      max_temp: 30,
      target_temp_step: 0.5,
      target_entity: "input_number.temperaturspeicher_bad",
      ...attrs,
    },
  };
}

const plan: ZeitwerkPlan = {
  id: "heizung_bad",
  default_profile: "eco",
  profiles: [
    {
      id: "comfort",
      name: "Komfort",
      actions: [
        {
          action: "input_number.set_value",
          target: { entity_id: "input_number.temperaturspeicher_bad" },
          data: { value: 22 },
        },
      ],
    },
    {
      id: "eco",
      name: "Absenkung",
      actions: [
        {
          action: "input_number.set_value",
          target: { entity_id: "input_number.temperaturspeicher_bad" },
          data: { value: 18 },
        },
      ],
    },
  ],
};

describe("formatting", () => {
  it("formats like the mockup", () => {
    expect(fmtTemp(18.5, fmt)).toBe("18,5");
    expect(fmtTarget(22, fmt)).toBe("22");
    expect(fmtTarget(22.5, fmt)).toBe("22,5");
    expect(fmtTemp(null, fmt)).toBe("–");
  });
  it("adds the weekday when not today", () => {
    expect(fmtTime(new Date(2026, 10, 18, 7, 30), fmt)).toBe("07:30");
    expect(fmtTime(new Date(2026, 10, 19, 5, 15), fmt)).toMatch(/^Do 05:15$/);
  });
});

describe("dial", () => {
  it("matches the mockup geometry", () => {
    // 18.5 °C on a 12..26 scale -> point from the mockup (114.6, 21.3)
    const p = dialPoint((18.5 - 12) / 14);
    expect(p.x).toBeCloseTo(114.6, 0);
    expect(p.y).toBeCloseTo(21.3, 0);
    expect(dialPoint(0)).toEqual({ x: 64.9, y: 177.1 });
    expect(dialPoint(1)).toEqual({ x: 195.1, y: 177.1 });
  });
  it("uses the large-arc flag for long arcs", () => {
    expect(arcPath(0, 1)).toContain(" 0 1 1 ");
    expect(arcPath(0.4, 0.6)).toContain(" 0 0 1 ");
    expect(arcPath(0.6, 0.4)).toBe(arcPath(0.4, 0.6));
  });
});

describe("status", () => {
  it("heating", () => {
    const sv = statusView(parseRoom(entity({})), de, fmt);
    expect(sv).toMatchObject({ tone: "heat", text: "Heizt", chip: null });
  });
  it("window with chip", () => {
    const room = parseRoom(
      entity({
        status: "window",
        window_open: true,
        window_open_since: new Date(now.getTime() - 14 * 60000).toISOString(),
      }),
    );
    const sv = statusView(room, de, fmt);
    expect(sv.text).toBe("Fenster offen · pausiert");
    expect(sv.chip).toBe("Fenster offen seit 14 min · Heizung pausiert");
    expect(sv.tone).toBe("blue");
    expect(sv.locked).toBe(true);
  });
  it("manual with user and time", () => {
    const room = parseRoom(
      entity({
        status: "manual",
        manual_target: 23,
        manual_by: "Steven",
        manual_until: new Date(2026, 10, 18, 11, 0).toISOString(),
      }),
    );
    expect(statusView(room, de, fmt).text).toBe("Manuell 23° von Steven · bis 11:00");
  });
  it("manual until next block", () => {
    const room = parseRoom(entity({ status: "manual", manual_target: 23 }));
    expect(statusView(room, de, fmt).text).toBe("Manuell 23° · bis nächster Block");
  });
  it("unreachable TRV wins", () => {
    const room = parseRoom(
      entity({ trv_unavailable_since: new Date(now.getTime() - 6 * 60000).toISOString() }),
    );
    expect(statusView(room, de, fmt)).toMatchObject({
      tone: "red",
      text: "TRV seit 6 min nicht erreichbar",
    });
  });
  it("reached with next profile, lowered on the lowest profile", () => {
    const next = new Date(2026, 10, 18, 11, 45).toISOString();
    const room = parseRoom(
      entity({ status: "reached", temperature: 18, next_change: next, next_profile: "Komfort" }),
    );
    expect(statusView(room, de, fmt).text).toBe("Erreicht · Komfort ab 11:45");
    expect(statusView(room, de, fmt, plan)).toMatchObject({
      tone: "eco",
      text: "Abgesenkt bis 11:45",
    });
  });
  it("summer lock", () => {
    const room = parseRoom(entity({ status: "summer", outdoor_temperature: 17 }));
    expect(statusView(room, de, fmt).text).toBe("Sommerabschaltung · außen 17°");
  });
  it("english", () => {
    expect(statusView(parseRoom(entity({})), strings("en-GB"), fmt).text).toBe("Heating");
  });
});

describe("zeitwerk", () => {
  it("reads the profile value of the target entity", () => {
    expect(profileValue(plan.profiles[0], "input_number.temperaturspeicher_bad")).toBe(22);
    expect(profileValue(plan.profiles[0], "input_number.other")).toBeNull();
    expect(
      profileValue({ id: "x", name: "x", actions: [{ data: { temperature: 21 } }] }, null),
    ).toBe(21);
  });
  it("builds the day band", () => {
    const d = (h: number, m = 0) => new Date(2026, 10, 18, h, m).toISOString();
    const band = dayBand(
      [
        { start: d(0), end: d(5, 30), profile: "eco" },
        { start: d(5, 30), end: d(7, 30), profile: "comfort" },
        { start: d(7, 30), end: d(18), profile: "eco" },
        { start: d(18), end: d(21), profile: "comfort" },
        { start: d(21), end: new Date(2026, 10, 19).toISOString(), profile: "eco" },
      ],
      plan,
      "input_number.temperaturspeicher_bad",
      now,
    );
    expect(band.parts).toHaveLength(2);
    expect(band.parts[0].left).toBeCloseTo(22.9, 1);
    expect(band.parts[0].width).toBeCloseTo(8.33, 1);
    expect(band.parts[1].left).toBe(75);
    expect(band.now).toBeCloseTo(30.1, 1);
    expect(band.legend).toEqual([
      { name: "Komfort", value: 22 },
      { name: "Absenkung", value: 18 },
    ]);
  });
});

describe("notes and footer", () => {
  it("ventilation done note", () => {
    const room = parseRoom(
      entity({
        window_open: true,
        ventilation_done: true,
        ventilation_minutes: 10,
        outdoor_temperature: 8.9,
        window_open_since: new Date(now.getTime() - 14 * 60000).toISOString(),
      }),
    );
    expect(roomNote(room, de, fmt)).toEqual({
      tone: "amber",
      title: "Genug gelüftet, Fenster kann zu",
      text: "Außen 8,9 °C, empfohlen 10 min. Offen seit 14 min.",
    });
  });
  it("mold warning", () => {
    const room = parseRoom(
      entity({ mold_level: "warning", wall_humidity: 72, wall_temperature: 15.6 }),
    );
    expect(roomNote(room, de, fmt)?.title).toBe("Wand feucht");
  });
  it("no note", () => {
    expect(roomNote(parseRoom(entity({})), de, fmt)).toBeNull();
  });
  it("TRV footer", () => {
    const off = parseRoom(
      entity({
        trvs: [
          {
            entity_id: "climate.trv",
            available: true,
            hvac_mode: "off",
            setpoint: 7,
            current: 18,
            hvac_action: "idle",
          },
        ],
      }),
    );
    expect(trvText(off, de, fmt, true)).toBe("TRV: aus, Frostschutz im Gerät");
    const heat = parseRoom(
      entity({
        trvs: [
          {
            entity_id: "climate.trv",
            available: true,
            hvac_mode: "heat",
            setpoint: 21.5,
            current: 18,
            hvac_action: "heating",
          },
        ],
      }),
    );
    expect(trvText(heat, de, fmt, false)).toBe("TRV: heizt auf 21,5°");
  });
});

describe("stepTarget", () => {
  it("steps, rounds and clamps", () => {
    const room = parseRoom(entity({}));
    expect(stepTarget(22, 0.5, room)).toBe(22.5);
    expect(stepTarget(21.3, 0.5, room)).toBe(22);
    expect(stepTarget(30, 0.5, room)).toBe(30);
    expect(stepTarget(5, -0.5, room)).toBe(5);
  });
});
