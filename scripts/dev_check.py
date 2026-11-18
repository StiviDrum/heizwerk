"""Set up and check the local Heizwerk dev instance (http://localhost:8125).

Usage (dev instance running via scripts/develop):
    python scripts/dev_check.py <output dir> [--shots]

1. Onboard the dev instance (first run only), get tokens.
2. Create the Zeitwerk entry + plan ``heizung_bad`` (if Zeitwerk is present).
3. Create the Heizwerk entry and two rooms through the real config flows.
4. Play through scenarios (window, lock, manual override) and print results.
5. ``--shots``: put the card on a dashboard and screenshot standard/compact in
   light and dark with headless Chromium (Playwright's headless shell).

Only talks to localhost:8125 – never to a production Home Assistant.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import aiohttp

HA = "http://localhost:8125"
CLIENT_ID = f"{HA}/"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots")
SHOTS = "--shots" in sys.argv
TOKENS = OUT / "ha_tokens.json"
SHELL = Path(
    os.environ.get(
        "HEIZWERK_CHROME",
        Path.home()
        / ".cache/ms-playwright/chromium_headless_shell-1194/chrome-linux/headless_shell",
    )
)
# Missing system libs (libnss3, libnspr4)? Extract them without root
# (apt-get download + dpkg -x) and point HEIZWERK_CHROME_LIBS at the .so dir.
LIBS = os.environ.get("HEIZWERK_CHROME_LIBS", "")
PROFILE_BAD = "sensor.zeitwerk_heizung_bad_profile"
DEV_USER = {"username": "dev", "password": "dev-dev-dev"}

PLAN = {
    "id": "heizung_bad",
    "name": "Heizung Bad",
    "profiles": [
        {
            "id": "comfort",
            "name": "Komfort",
            "color": "#ff7043",
            "actions": [
                {
                    "action": "climate.set_temperature",
                    "target": {"entity_id": "climate.heizwerk_bad"},
                    "data": {"temperature": 22},
                }
            ],
        },
        {
            "id": "eco",
            "name": "Absenkung",
            "color": "#42a5f5",
            "actions": [
                {
                    "action": "climate.set_temperature",
                    "target": {"entity_id": "climate.heizwerk_bad"},
                    "data": {"temperature": 18},
                }
            ],
        },
    ],
    "default_profile": "eco",
    "week": {
        "day_types": [
            {
                "id": "all",
                "name": "Täglich",
                "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "blocks": [
                    {"start": "05:30", "end": "07:30", "profile": "comfort"},
                    {"start": "18:00", "end": "21:00", "profile": "comfort"},
                ],
            }
        ]
    },
}

HUB = {
    "outdoor_temperature": "sensor.aussentemperatur",
    "outdoor_humidity": "sensor.aussenfeuchte",
    "season_entity": "input_boolean.heizperiode",
    "summer_lock_temperature": 16,
    "summer_lock_minutes": 10,
}

ROOMS = [
    {
        "name": "Bad",
        "trvs": ["climate.trv_bad"],
        "temperature_sensor": "sensor.bad_temperatur",
        "humidity_sensor": "sensor.bad_feuchte",
        "wall_temperature_sensor": "sensor.bad_wandtemperatur",
        "windows": ["binary_sensor.fenster_bad"],
        "window_open_delay": 5,
        "window_close_delay": 5,
        "zeitwerk_plan": "heizung_bad",
        "lock_mode": "off",
        "frost_temperature": 7,
        "correction": -0.5,
        "regulation": "setpoint",
        "external_temperature_entities": ["input_number.sim_trv_bad_external"],
        "default_target": 20,
        "min_temp": 5,
        "max_temp": 30,
        "humidity_threshold": 60,
        # Dev instance only: the TRVs are simulated, so real control is tested.
        "observe_only": False,
    },
    {
        "name": "Küche",
        "trvs": ["climate.trv_kueche"],
        "temperature_sensor": "sensor.kueche_temperatur",
        "humidity_sensor": "sensor.kueche_feuchte",
        "windows": ["binary_sensor.fenster_kueche"],
        "window_open_delay": 5,
        "window_close_delay": 5,
        "lock_entities": ["input_boolean.sim_sperre_kueche"],
        "lock_mode": "frost",
        "frost_temperature": 7,
        "correction": 0,
        "regulation": "offset",
        "default_target": 20,
        "min_temp": 5,
        "max_temp": 30,
        "humidity_threshold": 60,
        "observe_only": True,
    },
]


class Api:
    """Tiny REST/WS client for the dev instance."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self.s = session
        self.h = {"Authorization": f"Bearer {token}"}
        self.token = token

    async def get(self, path: str) -> Any:
        async with self.s.get(f"{HA}{path}", headers=self.h) as r:
            return await r.json()

    async def post(self, path: str, data: Any = None) -> Any:
        async with self.s.post(f"{HA}{path}", headers=self.h, json=data or {}) as r:
            text = await r.text()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"status": r.status, "text": text}

    async def state(self, entity_id: str) -> dict[str, Any]:
        return await self.get(f"/api/states/{entity_id}")

    async def call(self, domain: str, service: str, **data: Any) -> Any:
        return await self.post(f"/api/services/{domain}/{service}", data)

    async def ws(self, *msgs: dict[str, Any]) -> list[Any]:
        out = []
        async with self.s.ws_connect(f"{HA}/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": self.token})
            assert (await ws.receive_json())["type"] == "auth_ok"
            for i, msg in enumerate(msgs, start=1):
                await ws.send_json({"id": i, **msg})
                while True:
                    res = await ws.receive_json()
                    if res.get("id") == i and res.get("type") == "result":
                        out.append(res)
                        break
        return out


async def tokens(session: aiohttp.ClientSession) -> dict[str, Any]:
    """Onboard (first run) or log in as the dev user."""
    async with session.get(f"{HA}/api/onboarding") as resp:
        steps = await resp.json() if resp.status == 200 else []
    user_done = next((s["done"] for s in steps if s["step"] == "user"), True)
    if not user_done:
        async with session.post(
            f"{HA}/api/onboarding/users",
            json={"client_id": CLIENT_ID, "name": "Dev", "language": "de", **DEV_USER},
        ) as resp:
            code = (await resp.json())["auth_code"]
    else:
        async with session.post(
            f"{HA}/auth/login_flow",
            json={
                "client_id": CLIENT_ID,
                "handler": ["homeassistant", None],
                "redirect_uri": CLIENT_ID,
            },
        ) as resp:
            flow_id = (await resp.json())["flow_id"]
        async with session.post(
            f"{HA}/auth/login_flow/{flow_id}",
            json={"client_id": CLIENT_ID, **DEV_USER},
        ) as resp:
            code = (await resp.json())["result"]
    async with session.post(
        f"{HA}/auth/token",
        data={"grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID},
    ) as resp:
        tok = await resp.json()
    TOKENS.write_text(json.dumps(tok))
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    for step, body in (
        ("core_config", {}),
        ("analytics", {}),
        (
            "integration",
            {"client_id": CLIENT_ID, "redirect_uri": f"{HA}/?auth_callback=1"},
        ),
    ):
        if not next((s["done"] for s in steps if s["step"] == step), True):
            await session.post(
                f"{HA}/api/onboarding/{step}", json=body, headers=headers
            )
    return tok


async def entries(api: Api, domain: str) -> list[dict[str, Any]]:
    return [
        e
        for e in await api.get("/api/config/config_entries/entry")
        if e["domain"] == domain
    ]


def nest_room(flat: dict[str, Any]) -> dict[str, Any]:
    """Room data in the dialog's section layout (0.3+)."""
    # Lazy: importing Home Assistant is slow and only needed for new rooms.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from custom_components.heizwerk.config_flow import (  # noqa: PLC0415
        ROOM_SECTIONS,
        _nest,
    )

    return _nest(flat, ROOM_SECTIONS)


def form_values(fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Suggested values of a serialized form, nested like the sections."""
    out: dict[str, Any] = {}
    for f in fields:
        if f.get("type") == "expandable":
            out[f["name"]] = form_values(f["schema"])
            continue
        val = (f.get("description") or {}).get("suggested_value", f.get("default"))
        if val is not None:
            out[f["name"]] = val
    return out


async def dialog_checks(api: Api) -> list[str]:
    """Room dialog against the real Zeitwerk: plan auto-detect, offset warning."""
    fails: list[str] = []
    entry = (await entries(api, "heizwerk"))[0]["entry_id"]
    subs = await api.ws({"type": "config_entries/subentries/list", "entry_id": entry})
    bad_id = next(x["subentry_id"] for x in subs[0]["result"] if x["title"] == "Bad")

    async def reconfigure(change) -> dict[str, Any]:
        flow = await api.post(
            "/api/config/config_entries/subentries/flow",
            {"handler": [entry, "room"], "subentry_id": bad_id},
        )
        top = [f["name"] for f in flow["data_schema"]]
        data = form_values(flow["data_schema"])
        change(data)
        res = await api.post(
            f"/api/config/config_entries/subentries/flow/{flow['flow_id']}", data
        )
        if res.get("type") == "form":
            await api.s.delete(
                f"{HA}/api/config/config_entries/subentries/flow/{flow['flow_id']}",
                headers=api.h,
            )
        res["_top"] = top
        return res

    def check(cond: bool, msg: str) -> None:
        print(("  ok  " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    res = await reconfigure(lambda d: d["schedule"].pop("zeitwerk_plan", None))
    print("  Dialog oben:", res["_top"])
    check(
        res["_top"][:4] == ["name", "trvs", "temperature_sensor", "observe_only"],
        "Pflicht/wichtig oben",
    )
    check(res.get("type") == "abort", "Raum ändern ohne Plan gespeichert")
    subs = await api.ws({"type": "config_entries/subentries/list", "entry_id": entry})
    await asyncio.sleep(3)  # reload after the update
    st = await api.state("climate.heizwerk_bad")
    check(
        st["attributes"].get("zeitwerk_plan") == "heizung_bad",
        "Plan automatisch erkannt (heizung_bad)",
    )

    res = await reconfigure(lambda d: d["regulation"].update(regulation="offset"))
    check(
        res.get("errors") == {"regulation": "offset_with_external"},
        f"Warnung Offset + externer Eingang ({res.get('errors')})",
    )
    return fails


async def direct_plan_check(api: Api) -> list[str]:
    """Zeitwerk writes climate.set_temperature to a Heizwerk room directly."""
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("  ok  " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    entry = (await entries(api, "heizwerk"))[0]["entry_id"]
    room = {
        "name": "Direkt",
        "trvs": ["climate.trv_kueche"],
        "temperature_sensor": "sensor.kueche_temperatur",
        "observe_only": True,
    }
    flow = await api.post(
        "/api/config/config_entries/subentries/flow", {"handler": [entry, "room"]}
    )
    res = await api.post(
        f"/api/config/config_entries/subentries/flow/{flow['flow_id']}",
        {**form_values(flow["data_schema"]), **room},
    )
    check(
        res.get("type") == "create_entry",
        f"Testraum ohne Zeitwerk-Ziel angelegt ({res.get('errors')})",
    )
    await asyncio.sleep(4)
    climate = "climate.heizwerk_direkt"
    plan = {
        "id": "heizwerk_direkt_test",
        "name": "Heizwerk Direkt Test",
        "profiles": [
            {
                "id": "warm",
                "name": "Warm",
                "actions": [
                    {
                        "action": "climate.set_temperature",
                        "target": {"entity_id": climate},
                        "data": {"temperature": 21.5},
                    }
                ],
            }
        ],
        "default_profile": "warm",
        "week": {
            "day_types": [
                {
                    "id": "all",
                    "name": "Alle",
                    "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    "blocks": [],
                }
            ]
        },
    }
    created = await api.ws({"type": "zeitwerk/plans/create", "plan": plan})
    check(bool(created[0].get("success")), f"Zeitwerk-Plan auf {climate} angelegt")
    await api.call("zeitwerk", "apply", plan=["heizwerk_direkt_test"])
    await asyncio.sleep(3)
    st = await api.state(climate)
    check(
        st["attributes"].get("temperature") == 21.5,
        "Zeitwerk setzt climate.heizwerk_direkt auf 21,5",
    )
    check(st["attributes"].get("status") != "manual", "kein Fehlalarm 'manuell'")
    logs = await api.ws({"type": "system_log/list"})
    rec = [e for e in logs[0]["result"] if "RecursionError" in json.dumps(e)]
    check(not rec, "keine RecursionError im Log")
    # Clean up the dev-only test objects.
    await api.ws({"type": "zeitwerk/plans/delete", "plan_id": "heizwerk_direkt_test"})
    subs = await api.ws({"type": "config_entries/subentries/list", "entry_id": entry})
    sid = next(
        (x["subentry_id"] for x in subs[0]["result"] if x["title"] == "Direkt"), None
    )
    if sid:
        await api.ws(
            {
                "type": "config_entries/subentries/delete",
                "entry_id": entry,
                "subentry_id": sid,
            }
        )
    return fails


async def migrate_04(api: Api) -> None:
    """Dev instance from 0.3: plan writes the room directly, rooms drop target."""
    plans = await api.ws({"type": "zeitwerk/plans/get", "plan_id": "heizung_bad"})
    plan = plans[0].get("result") or {}
    if "input_number" in json.dumps(plan.get("profiles", [])):
        res = await api.ws(
            {
                "type": "zeitwerk/plans/update",
                "plan_id": "heizung_bad",
                "plan": {**plan, "profiles": PLAN["profiles"]},
            }
        )
        print(
            "plan heizung_bad -> climate.heizwerk_bad:",
            res[0].get("success"),
            res[0].get("error", ""),
        )
    hw = await entries(api, "heizwerk")
    if not hw:
        return
    entry = hw[0]["entry_id"]
    issues = await api.ws({"type": "repairs/list_issues"})
    legacy = {
        i["issue_id"]
        for i in issues[0]["result"]["issues"]
        if i["domain"] == "heizwerk"
    }
    subs = await api.ws({"type": "config_entries/subentries/list", "entry_id": entry})
    for sub in subs[0]["result"]:
        if f"target_entity_{sub['subentry_id']}" not in legacy:
            continue
        flow = await api.post(
            "/api/config/config_entries/subentries/flow",
            {"handler": [entry, "room"], "subentry_id": sub["subentry_id"]},
        )
        res = await api.post(
            f"/api/config/config_entries/subentries/flow/{flow['flow_id']}",
            form_values(flow["data_schema"]),
        )
        print("room", sub["title"], "re-saved:", res.get("type"), res.get("errors", ""))
    await asyncio.sleep(4)


async def setup(api: Api) -> None:
    """Zeitwerk + plan, Heizwerk + rooms (idempotent)."""
    if not await entries(api, "zeitwerk"):
        flow = await api.post(
            "/api/config/config_entries/flow", {"handler": "zeitwerk"}
        )
        res = await api.post(f"/api/config/config_entries/flow/{flow['flow_id']}", {})
        print("zeitwerk entry:", res.get("type"))
        await asyncio.sleep(2)
    plans = await api.ws({"type": "zeitwerk/plans/list"})
    if plans[0].get("success") and not any(
        p["id"] == "heizung_bad" for p in plans[0]["result"]["plans"]
    ):
        res = await api.ws({"type": "zeitwerk/plans/create", "plan": PLAN})
        print("zeitwerk plan:", res[0].get("success"), res[0].get("error"))

    if not (hw := await entries(api, "heizwerk")):
        flow = await api.post(
            "/api/config/config_entries/flow", {"handler": "heizwerk"}
        )
        res = await api.post(f"/api/config/config_entries/flow/{flow['flow_id']}", HUB)
        print("heizwerk entry:", res.get("type"))
        await asyncio.sleep(1)
        hw = await entries(api, "heizwerk")
    entry_id = hw[0]["entry_id"]
    subs = await api.ws(
        {"type": "config_entries/subentries/list", "entry_id": entry_id}
    )
    existing = {s["title"] for s in subs[0]["result"]}
    for room in ROOMS:
        if room["name"] in existing:
            continue
        flow = await api.post(
            "/api/config/config_entries/subentries/flow",
            {"handler": [entry_id, "room"], "show_advanced_options": False},
        )
        res = await api.post(
            f"/api/config/config_entries/subentries/flow/{flow['flow_id']}",
            nest_room(room),
        )
        print("room", room["name"], res.get("type"), res.get("errors"))
        await asyncio.sleep(2)


def show(label: str, st: dict[str, Any], *keys: str) -> None:
    a = st.get("attributes", {})
    print(f"  {label}: state={st.get('state')}", {k: a.get(k) for k in keys})


async def scenarios(api: Api) -> list[str]:
    """Drive the simulated house and check Heizwerk's reaction."""
    fails: list[str] = []
    bad, kue = "climate.heizwerk_bad", "climate.heizwerk_kuche"

    def check(cond: bool, msg: str) -> None:
        print(("  ok  " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    # Baseline: plan value from Zeitwerk itself (setting the target by hand
    # would be a manual override in Zeitwerk's eyes).
    await api.call(
        "input_boolean", "turn_off", entity_id="input_boolean.sim_fenster_bad"
    )
    await api.call(
        "input_boolean", "turn_off", entity_id="input_boolean.sim_sperre_kueche"
    )
    await api.call("zeitwerk", "clear_force", plan="heizung_bad")
    await api.call("zeitwerk", "resume", plan=["heizung_bad"])
    await api.call("heizwerk", "resume", entity_id=[bad, kue])
    await asyncio.sleep(12)
    plan_value = float((await api.state(bad))["attributes"]["temperature"])
    st = await api.state(bad)
    show(
        "Bad",
        st,
        "status",
        "temperature",
        "zeitwerk_profile",
        "planned_commands",
        "last_sync",
    )
    trv = await api.state("climate.trv_bad")
    show("TRV Bad", trv, "temperature")
    check(
        st["attributes"]["status"] in ("heating", "reached"),
        "Bad regelt (heating/reached)",
    )
    check(
        trv["state"] == "heat" and trv["attributes"]["temperature"] == plan_value - 0.5,
        f"TRV Bad auf heat {plan_value - 0.5} (Planwert {plan_value} − 0,5 K)",
    )
    ext = await api.state("input_number.sim_trv_bad_external")
    check(float(ext["state"]) == 18.5, "Externe Temperatur an TRV Bad gesendet (18,5)")

    kst = await api.state(kue)
    ktrv = await api.state("climate.trv_kueche")
    show("Küche", kst, "status", "observe_only", "planned_commands")
    check(kst["attributes"]["observe_only"] is True, "Küche: Nur beobachten aktiv")
    check(
        ktrv["state"] == "off" and ktrv["attributes"]["temperature"] == 7,
        "TRV Küche unverändert (off, 7)",
    )
    check(
        bool(kst["attributes"]["planned_commands"]), "Küche: geplante Befehle sichtbar"
    )

    # Window
    await api.call(
        "input_boolean", "turn_on", entity_id="input_boolean.sim_fenster_bad"
    )
    await asyncio.sleep(7)
    st = await api.state(bad)
    check(
        st["attributes"]["status"] == "window", "Fenster Bad → Status window nach 5 s"
    )
    await asyncio.sleep(11)
    trv = await api.state("climate.trv_bad")
    check(trv["state"] == "off", "TRV Bad aus bei offenem Fenster")
    await api.call(
        "input_boolean", "turn_off", entity_id="input_boolean.sim_fenster_bad"
    )
    await asyncio.sleep(18)
    trv = await api.state("climate.trv_bad")
    check(trv["state"] == "heat", "TRV Bad wieder heat nach Schließen")

    # Lock in observe-only room
    await api.call(
        "input_boolean", "turn_on", entity_id="input_boolean.sim_sperre_kueche"
    )
    await asyncio.sleep(2)
    kst = await api.state(kue)
    check(kst["attributes"]["status"] == "locked", "Sperre Küche → locked")
    check(
        kst["attributes"]["planned_commands"][0].get("temperature") == 7,
        "Küche: geplant Frostschutz 7 °C",
    )
    await api.call(
        "input_boolean", "turn_off", entity_id="input_boolean.sim_sperre_kueche"
    )

    # Manual override: Heizwerk sets its set-point, Zeitwerk notices it.
    async def zw_manual() -> bool:
        attrs = (await api.state(PROFILE_BAD)).get("attributes", {})
        return bool(attrs.get("manual_override"))

    await api.call("heizwerk", "set_manual", entity_id=bad, temperature=23.5)
    await asyncio.sleep(2)
    st = await api.state(bad)
    show(
        "Bad manuell",
        st,
        "status",
        "temperature",
        "manual_until",
        "manual_by",
        "resume_available",
    )
    check(st["attributes"]["temperature"] == 23.5, "Manuell: Sollwert 23,5")
    check(await zw_manual(), "Zeitwerk zeigt manuelle Übersteuerung")
    check(st["attributes"]["status"] == "manual", "Heizwerk: Status manual")
    check(st["attributes"]["manual_by"] == "Dev", "Heizwerk: Benutzer erkannt")
    check(
        st["attributes"]["resume_available"] is True,
        "Fortsetzen verfügbar (Plan erkannt)",
    )
    await asyncio.sleep(11)
    trv = await api.state("climate.trv_bad")
    check(
        trv["attributes"]["temperature"] == 23.0, "TRV Bad folgt Übersteuerung (23,0)"
    )

    # Resume in Heizwerk reloads the plan (Steven: plan 16, manual, resume -> plan)
    await api.call("heizwerk", "resume", entity_id=bad)
    await asyncio.sleep(2)
    st = await api.state(bad)
    check(
        st["attributes"]["temperature"] == plan_value,
        f"Fortsetzen lädt Planwert {plan_value}",
    )
    check(st["attributes"]["status"] != "manual", "Fortsetzen beendet manuell")
    check(not await zw_manual(), "Zeitwerk: Übersteuerung beendet")

    # "Next block": Zeitwerk applies another profile
    await api.call("heizwerk", "set_manual", entity_id=bad, temperature=24)
    await asyncio.sleep(2)
    other = (
        "eco"
        if (await api.state(PROFILE_BAD))["attributes"].get("profile_id") == "comfort"
        else "comfort"
    )
    await api.call(
        "zeitwerk",
        "force_profile",
        plan="heizung_bad",
        profile=other,
        duration="00:05:00",
    )
    await asyncio.sleep(2)
    st = await api.state(bad)
    check(
        st["attributes"]["status"] != "manual",
        "Neuer Zeitwerk-Block beendet Übersteuerung",
    )
    check(st["attributes"]["temperature"] != 24, "Neuer Block setzt seinen Wert")
    await api.call("zeitwerk", "clear_force", plan="heizung_bad")
    await api.call("zeitwerk", "resume", plan=["heizung_bad"])
    await asyncio.sleep(2)

    # Changed outside the card (e.g. more-info dialog): Zeitwerk reports it
    await api.call("climate", "set_temperature", entity_id=bad, temperature=21)
    await asyncio.sleep(2)
    st = await api.state(bad)
    check(
        st["attributes"]["status"] == "manual",
        "Änderung außerhalb der Karte: manuell (von Zeitwerk)",
    )
    await api.call("heizwerk", "resume", entity_id=bad)
    await asyncio.sleep(2)

    # Duration: resume action after 1 min
    await api.call(
        "heizwerk", "set_manual", entity_id=bad, temperature=23, duration={"minutes": 1}
    )
    await asyncio.sleep(2)
    check(
        (await api.state(bad))["attributes"]["manual_mode"] == "duration",
        "Dauer 1 min aktiv",
    )
    await asyncio.sleep(63)
    st = await api.state(bad)
    check(
        st["attributes"]["temperature"] == plan_value,
        "Dauer abgelaufen: Planwert zurück",
    )
    check(not await zw_manual(), "Dauer abgelaufen: Zeitwerk-Übersteuerung beendet")

    # Room without scheduler: plain thermostat, no resume
    kst = await api.state(kue)
    check(
        kst["attributes"]["resume_available"] is False,
        "Küche ohne Plan: kein Fortsetzen",
    )

    # No repair issues left after the migration
    issues = await api.ws({"type": "repairs/list_issues"})
    hw = [i for i in issues[0]["result"]["issues"] if i["domain"] == "heizwerk"]
    check(not hw, f"keine Heizwerk-Reparaturhinweise ({[i['issue_id'] for i in hw]})")

    # Zeitwerk interfaces
    prof = await api.state("sensor.zeitwerk_heizung_bad_profile")
    check(
        prof.get("attributes", {}).get("plan_id") == "heizung_bad",
        "Zeitwerk-Profilsensor vorhanden",
    )
    pre = await api.ws({"type": "zeitwerk/preview", "plan_ids": ["heizung_bad"]})
    check(
        bool(pre[0].get("result", {}).get("plans", {}).get("heizung_bad")),
        "zeitwerk/preview liefert Segmente",
    )

    # Errors in the log from Heizwerk?
    logs = await api.ws({"type": "system_log/list"})
    hw_logs = [
        e
        for e in logs[0]["result"]
        if str(e.get("name", "")).startswith("custom_components.heizwerk")
        and e["level"] in ("ERROR", "WARNING")
    ]
    for e in hw_logs:
        print("  log:", e["level"], e["message"])
    check(not hw_logs, "keine Heizwerk-Warnungen/Fehler im Log")
    return fails


# --- Screenshots ---------------------------------------------------------------

FIND = """
(() => {
  const find = (root, sel, acc) => {
    root.querySelectorAll(sel).forEach((e) => acc.push(e));
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) find(el.shadowRoot, sel, acc);
    return acc;
  };
  window.__findAll = (sel) => find(document, sel, []);
  return true;
})()
"""


class Cdp:
    """Minimal Chrome DevTools Protocol client."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self.ws = ws
        self.n = 0

    async def call(self, method: str, **params: Any) -> dict[str, Any]:
        self.n += 1
        await self.ws.send_json({"id": self.n, "method": method, "params": params})
        while True:
            msg = await self.ws.receive_json()
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    async def js(self, expression: str) -> Any:
        res = await self.call(
            "Runtime.evaluate",
            expression=expression,
            awaitPromise=True,
            returnByValue=True,
        )
        if "exceptionDetails" in res:
            raise RuntimeError(res["exceptionDetails"])
        return res["result"].get("value")

    async def shot(self, name: str) -> None:
        res = await self.call(
            "Page.captureScreenshot", format="png", captureBeyondViewport=True
        )
        (OUT / f"{name}.png").write_bytes(base64.b64decode(res["data"]))
        print("screenshot", OUT / f"{name}.png")


async def dashboard(api: Api) -> None:
    res = await api.ws({"type": "lovelace/dashboards/list"})
    if not any(d["url_path"] == "heizwerk-dev" for d in res[0]["result"]):
        await api.ws(
            {
                "type": "lovelace/dashboards/create",
                "url_path": "heizwerk-dev",
                "title": "Heizwerk",
                "mode": "storage",
            }
        )
    rooms = ["climate.heizwerk_bad", "climate.heizwerk_kuche"]
    await api.ws(
        {
            "type": "lovelace/config/save",
            "url_path": "heizwerk-dev",
            "config": {
                "views": [
                    {
                        "title": "Standard",
                        "path": "standard",
                        "cards": [
                            {"type": "custom:heizwerk-card", "entity": rooms[0]},
                            {
                                "type": "custom:zeitwerk-card",
                                "view": "week",
                                "plan": "heizung_bad",
                            },
                        ],
                    },
                    {
                        "title": "Kompakt",
                        "path": "kompakt",
                        "cards": [
                            {
                                "type": "custom:heizwerk-card",
                                "variant": "compact",
                                "entity": e,
                            }
                            for e in rooms
                        ]
                        + [
                            {
                                "type": "custom:heizwerk-card",
                                "variant": "compact",
                                "title": "Heizung",
                                "entities": rooms,
                            }
                        ],
                    },
                ]
            },
        }
    )


DIAL = {"cx": 130, "cy": 112.05, "r": 92, "start": 135, "sweep": 270, "w": 260}


def dial_xy(
    rect: dict[str, float], value: float, lo: float = 12, hi: float = 26
) -> tuple[float, float]:
    """Screen coordinates of a value on the dial (viewBox 260×214)."""
    f = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    a = math.radians(DIAL["start"] + DIAL["sweep"] * f)
    scale = rect["width"] / DIAL["w"]
    return (
        rect["left"] + (DIAL["cx"] + DIAL["r"] * math.cos(a)) * scale,
        rect["top"] + (DIAL["cy"] + DIAL["r"] * math.sin(a)) * scale,
    )


async def drag_test(api: Api, cdp: Cdp) -> list[str]:
    """Drag the target knob of the standard card with real mouse events."""
    fails: list[str] = []
    bad = "climate.heizwerk_bad"
    await api.call("heizwerk", "resume", entity_id=bad)
    await asyncio.sleep(2)
    await cdp.call("Page.navigate", url=f"{HA}/heizwerk-dev/standard")
    await asyncio.sleep(8)
    await cdp.js(FIND)
    rect = await cdp.js(
        "(() => { const c = window.__findAll('heizwerk-card')[0];"
        " const r = c.shadowRoot.querySelector('.dial svg').getBoundingClientRect();"
        " return {left: r.left, top: r.top, width: r.width, height: r.height} })()"
    )
    start_value = (await api.state(bad))["attributes"]["temperature"]
    goal = 24.5
    x0, y0 = dial_xy(rect, start_value)
    x1, y1 = dial_xy(rect, goal)
    await cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x0, y=y0)
    await cdp.call(
        "Input.dispatchMouseEvent",
        type="mousePressed",
        x=x0,
        y=y0,
        button="left",
        clickCount=1,
    )
    for i in range(1, 11):
        await cdp.call(
            "Input.dispatchMouseEvent",
            type="mouseMoved",
            x=x0 + (x1 - x0) * i / 10,
            y=y0 + (y1 - y0) * i / 10,
            button="left",
            buttons=1,
        )
        await asyncio.sleep(0.03)
    live = await cdp.js(
        "(() => { const c = window.__findAll('heizwerk-card')[0];"
        " return c.shadowRoot.querySelector('.ziel b').textContent.trim() })()"
    )
    await cdp.shot("drag-live")
    await cdp.call(
        "Input.dispatchMouseEvent",
        type="mouseReleased",
        x=x1,
        y=y1,
        button="left",
        clickCount=1,
    )
    await asyncio.sleep(3)
    st = await api.state(bad)
    print(
        f"  drag: start {start_value} → live '{live}' → state {st['attributes']['temperature']}"
    )
    if live != "24,5°":
        fails.append(f"Ziehen: Live-Anzeige '{live}' statt 24,5°")
    if st["attributes"]["temperature"] != goal:
        fails.append(f"Ziehen: Sollwert {st['attributes']['temperature']} statt {goal}")
    if st["attributes"].get("status") != "manual":
        fails.append("Ziehen: keine manuelle Übersteuerung")
    await cdp.shot("drag-done")
    await api.call("heizwerk", "resume", entity_id=bad)
    return fails


CLICK_TEXT = """
(async (text) => {
  const all = window.__findAll('ha-button, mwc-button, button, ha-list-item, ha-md-list-item, a');
  const hit = all.find((e) => (e.textContent || '').trim().includes(text));
  if (!hit) return false;
  hit.click();
  return true;
})
"""


async def dialog_shots(cdp: Cdp) -> list[str]:
    """Open 'Raum hinzufügen' in the real frontend, screenshot collapsed + expanded."""
    fails: list[str] = []
    await cdp.call(
        "Emulation.setDeviceMetricsOverride",
        width=430,
        height=2200,
        deviceScaleFactor=1,
        mobile=True,
    )
    await cdp.call(
        "Page.navigate", url=f"{HA}/config/integrations/integration/heizwerk"
    )
    await asyncio.sleep(8)
    await cdp.js(FIND)
    clicked = await cdp.js(f"({CLICK_TEXT})('Raum hinzufügen')")
    await asyncio.sleep(4)
    await cdp.js(FIND)
    fields = await cdp.js(
        "(() => { const f = window.__findAll('ha-form'); "
        " return f.length ? f[f.length - 1].schema.map(s => s.name + (s.type === 'expandable' ? ':section' : '')) : [] })()"
    )
    print("  dialog clicked:", clicked, "fields:", fields)
    if not clicked or not fields:
        fails.append("Dialog 'Raum hinzufügen' nicht geöffnet")
        return fails
    await cdp.shot("dialog-raum-zu")
    await cdp.js(
        "(() => { window.__findAll('ha-expansion-panel').forEach(p => p.expanded = true); return true })()"
    )
    await asyncio.sleep(1)
    await cdp.shot("dialog-raum-offen")
    await cdp.call(
        "Input.dispatchKeyEvent",
        type="keyDown",
        key="Escape",
        code="Escape",
        windowsVirtualKeyCode=27,
    )
    return fails


async def screenshots(
    api: Api, session: aiohttp.ClientSession, tok: dict[str, Any]
) -> list[str]:
    fails: list[str] = []
    await dashboard(api)
    # A lively state for the pictures: window open in the bath, manual in the kitchen.
    # Bath: manual override (shown in Zeitwerk too); window open in the kitchen.
    await api.call(
        "heizwerk", "set_manual", entity_id="climate.heizwerk_bad", temperature=23.5
    )
    await api.call(
        "input_boolean", "turn_on", entity_id="input_boolean.sim_fenster_kueche"
    )
    await api.call(
        "heizwerk",
        "set_manual",
        entity_id="climate.heizwerk_kuche",
        temperature=21,
        duration={"hours": 1},
    )
    await asyncio.sleep(7)
    hass_tokens = {
        **{k: tok[k] for k in ("access_token", "refresh_token", "expires_in")},
        "token_type": "Bearer",
        "hassUrl": HA,
        "clientId": CLIENT_ID,
        "expires": int(time.time() * 1000) + tok["expires_in"] * 1000,
    }
    proc = subprocess.Popen(
        [
            str(SHELL),
            "--no-sandbox",
            "--remote-debugging-port=9334",
            "--hide-scrollbars",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "LD_LIBRARY_PATH": LIBS} if LIBS else None,
    )
    try:
        pages: list[dict[str, Any]] = []
        for _ in range(50):
            try:
                async with session.get("http://127.0.0.1:9334/json") as resp:
                    pages = await resp.json()
                if pages:
                    break
            except aiohttp.ClientError:
                pass
            await asyncio.sleep(0.2)
        page = next(p for p in pages if p["type"] == "page")
        async with session.ws_connect(
            page["webSocketDebuggerUrl"], max_msg_size=0
        ) as ws:
            cdp = Cdp(ws)
            await cdp.call("Page.enable")
            await cdp.call("Runtime.enable")
            await cdp.call(
                "Emulation.setDeviceMetricsOverride",
                width=430,
                height=1300,
                deviceScaleFactor=1,
                mobile=True,
            )
            for dark in (False, True):
                await cdp.call("Page.navigate", url=f"{HA}/onboarding.html")
                await asyncio.sleep(2)
                theme = json.dumps(json.dumps({"theme": "default", "dark": dark}))
                await cdp.js(
                    f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(hass_tokens))});"
                    "localStorage.setItem('selectedLanguage', '\"de\"');"
                    f"localStorage.setItem('selectedTheme', {theme}); true"
                )
                mode = "dunkel" if dark else "hell"
                for view in ("standard", "kompakt"):
                    await cdp.call("Page.navigate", url=f"{HA}/heizwerk-dev/{view}")
                    await asyncio.sleep(8)
                    await cdp.js(FIND)
                    if view == "kompakt":
                        # Open the bath row in the house list (like the mockup).
                        await cdp.js(
                            "(async () => { const cards = window.__findAll('heizwerk-card');"
                            " const house = cards[cards.length - 1];"
                            " house.shadowRoot.querySelector('.sum').click();"
                            " await house.updateComplete; return true })()"
                        )
                        await asyncio.sleep(1)
                    info = await cdp.js(
                        "window.__findAll('heizwerk-card').map(c => ({dark: c.hasAttribute('dark'),"
                        " html: c.shadowRoot ? c.shadowRoot.innerHTML.length : -1,"
                        " err: !!(c.shadowRoot && c.shadowRoot.querySelector('.err'))}))"
                    )
                    print(f"  {view}/{mode}:", info)
                    if not info or any(c["err"] or c["html"] < 500 for c in info):
                        fails.append(f"Karte {view}/{mode} nicht korrekt gerendert")
                    if any(c["dark"] != dark for c in info):
                        fails.append(f"Karte {view}/{mode}: Dunkelmodus nicht erkannt")
                    await cdp.shot(f"{view}-{mode}")
            fails += await drag_test(api, cdp)
            fails += await dialog_shots(cdp)
    finally:
        proc.terminate()
        await api.call(
            "input_boolean", "turn_off", entity_id="input_boolean.sim_fenster_kueche"
        )
        await api.call(
            "heizwerk",
            "resume",
            entity_id=["climate.heizwerk_kuche", "climate.heizwerk_bad"],
        )
    return fails


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        tok = await tokens(session)
        api = Api(session, tok["access_token"])
        # HA 2026.11 migrates `http:` (port 8125) from YAML as a *pending* config
        # that reverts (with a restart) after 5 min unless it is confirmed.
        res = await api.ws({"type": "http/config/promote"})
        print("http config promoted:", res[0].get("success"), res[0].get("error", ""))
        await setup(api)
        await asyncio.sleep(3)
        await migrate_04(api)
        print("Dialog:")
        fails = await dialog_checks(api)
        print("Zeitwerk direkt auf Heizwerk:")
        fails += await direct_plan_check(api)
        print("Scenarios:")
        fails += await scenarios(api)
        if SHOTS:
            print("Screenshots:")
            fails += await screenshots(api, session, tok)
    print("RESULT:", "OK" if not fails else f"{len(fails)} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
