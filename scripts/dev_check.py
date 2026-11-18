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
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.temperaturspeicher_bad"},
                    "data": {"value": 22},
                }
            ],
        },
        {
            "id": "eco",
            "name": "Absenkung",
            "color": "#42a5f5",
            "actions": [
                {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.temperaturspeicher_bad"},
                    "data": {"value": 18},
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
        "target_entity": "input_number.temperaturspeicher_bad",
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
        "target_entity": "input_number.temperaturspeicher_kueche",
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
            f"/api/config/config_entries/subentries/flow/{flow['flow_id']}", room
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

    # Baseline
    await api.call(
        "input_boolean", "turn_off", entity_id="input_boolean.sim_fenster_bad"
    )
    await api.call(
        "input_boolean", "turn_off", entity_id="input_boolean.sim_sperre_kueche"
    )
    await api.call(
        "input_number",
        "set_value",
        entity_id="input_number.temperaturspeicher_bad",
        value=22,
    )
    await api.call("heizwerk", "resume", entity_id=[bad, kue])
    await asyncio.sleep(12)
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
        trv["state"] == "heat" and trv["attributes"]["temperature"] == 21.5,
        "TRV Bad auf heat 21,5 (22 − 0,5 K)",
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

    # Manual override, then Zeitwerk target change ends it
    await api.call("heizwerk", "set_manual", entity_id=bad, temperature=23.5)
    await asyncio.sleep(1)
    st = await api.state(bad)
    show("Bad manuell", st, "status", "temperature", "manual_until", "manual_by")
    check(st["attributes"]["status"] == "manual", "Manuell 23,5 aktiv")
    check(st["attributes"]["manual_by"] == "Dev", "Manuell: Benutzer erkannt")
    await api.call(
        "input_number",
        "set_value",
        entity_id="input_number.temperaturspeicher_bad",
        value=18,
    )
    await asyncio.sleep(1)
    st = await api.state(bad)
    check(st["attributes"]["status"] != "manual", "Neuer Zeitwerk-Wert beendet manuell")
    await api.call(
        "input_number",
        "set_value",
        entity_id="input_number.temperaturspeicher_bad",
        value=22,
    )

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
                        "cards": [{"type": "custom:heizwerk-card", "entity": rooms[0]}],
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


async def screenshots(
    api: Api, session: aiohttp.ClientSession, tok: dict[str, Any]
) -> list[str]:
    fails: list[str] = []
    await dashboard(api)
    # A lively state for the pictures: window open in the bath, manual in the kitchen.
    await api.call(
        "input_boolean", "turn_on", entity_id="input_boolean.sim_fenster_bad"
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
    finally:
        proc.terminate()
        await api.call(
            "input_boolean", "turn_off", entity_id="input_boolean.sim_fenster_bad"
        )
        await api.call("heizwerk", "resume", entity_id="climate.heizwerk_kuche")
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
        print("Scenarios:")
        fails = await scenarios(api)
        if SHOTS:
            print("Screenshots:")
            fails += await screenshots(api, session, tok)
    print("RESULT:", "OK" if not fails else f"{len(fails)} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
