"""Pure control logic (SPEC section 4)."""

from __future__ import annotations

import pytest

from custom_components.heizwerk.logic import (
    Command,
    RoomInputs,
    TrvInfo,
    decide,
    dew_point,
    mold_level,
    pending_commands,
    round_to_step,
    surface_humidity,
    ventilation_minutes,
    ventilation_recommended,
)


def _trv(**kw) -> TrvInfo:
    base = {
        "entity_id": "climate.trv",
        "hvac_mode": "off",
        "hvac_modes": ["off", "heat"],
    }
    base.update(kw)
    return TrvInfo(**base)


def _inputs(**kw) -> RoomInputs:
    base = {
        "enabled": True,
        "target": 22.0,
        "room_temperature": 18.5,
        "trvs": [_trv(current=20.5)],
        "locks": [],
    }
    base.update(kw)
    return RoomInputs(**base)


def test_dew_point_matches_reference() -> None:
    # 18.5 °C / 60 % -> ~10.6 °C (value from the mockup)
    assert dew_point(18.5, 60) == pytest.approx(10.6, abs=0.1)
    assert dew_point(None, 60) is None
    assert dew_point(20, 0) is None


def test_wall_humidity_and_mold_level() -> None:
    wall = surface_humidity(10.6, 15.6)
    assert wall == pytest.approx(72, abs=1)
    assert mold_level(wall) == "warning"
    assert mold_level(65) == "ok"
    assert mold_level(85) == "alarm"
    assert surface_humidity(12, 10) == 100  # condensation is capped
    assert mold_level(None) is None


@pytest.mark.parametrize(
    ("outdoor", "minutes"),
    [(-5, 5), (0, 10), (8.9, 10), (12, 15), (18, 20), (25, 25), (None, 10)],
)
def test_ventilation_minutes(outdoor: float | None, minutes: int) -> None:
    assert ventilation_minutes(outdoor) == minutes


def test_ventilation_recommended() -> None:
    assert ventilation_recommended(65, 60, 12.0, 5.0, False)
    assert not ventilation_recommended(65, 60, 12.0, 11.5, False)  # outside as humid
    assert not ventilation_recommended(55, 60, 12.0, 5.0, False)
    assert not ventilation_recommended(65, 60, 12.0, 5.0, True)  # already open
    assert ventilation_recommended(65, 60, None, None, False)


def test_round_to_step() -> None:
    assert round_to_step(21.26, 0.5) == 21.5
    assert round_to_step(21.24, 0.5) == 21.0
    assert round_to_step(21.25, 0.5) == 21.5


def test_heating_with_correction() -> None:
    d = decide(_inputs(correction=-0.5))
    assert d.status == "heating"
    assert d.heating
    assert d.commands == [Command("climate.trv", "heat", 21.5)]


def test_reached() -> None:
    d = decide(_inputs(room_temperature=22.0))
    assert d.status == "reached"
    assert not d.heating


def test_trv_reports_heating_counts() -> None:
    d = decide(_inputs(room_temperature=22.0, trvs=[_trv(hvac_action="heating")]))
    assert d.status == "heating"


def test_offset_regulation_compensates_trv_reading() -> None:
    # TRV reads 20.5, room 18.5 -> +2 K
    d = decide(_inputs(regulation="offset"))
    assert d.commands[0].temperature == 24.0
    # Limited to +5 K
    d = decide(_inputs(regulation="offset", trvs=[_trv(current=30.0)]))
    assert d.commands[0].temperature == 27.0


def test_setpoint_clamped_to_trv_range() -> None:
    d = decide(_inputs(target=40.0, trvs=[_trv(max_temp=30.0)]))
    assert d.commands[0].temperature == 30.0


@pytest.mark.parametrize(
    ("locks", "status"),
    [
        (["window"], "window"),
        (["season", "window"], "window"),
        (["summer", "season"], "season"),
        (["entity", "summer"], "summer"),
        (["entity"], "locked"),
    ],
)
def test_lock_priority(locks: list[str], status: str) -> None:
    d = decide(_inputs(locks=locks))
    assert d.status == status
    assert d.commands == [Command("climate.trv", "off")]


def test_lock_frost_mode() -> None:
    d = decide(_inputs(locks=["window"], lock_mode="frost", frost_temperature=7.0))
    assert d.commands == [Command("climate.trv", "heat", 7.0)]


def test_lock_beats_manual_and_off_beats_lock() -> None:
    assert decide(_inputs(locks=["window"], manual=True)).status == "window"
    d = decide(_inputs(locks=["window"], enabled=False))
    assert d.status == "off"
    assert d.commands == [Command("climate.trv", "off")]


def test_manual_status() -> None:
    assert decide(_inputs(manual=True)).status == "manual"


def test_all_unavailable_sends_nothing() -> None:
    d = decide(_inputs(trvs=[_trv(available=False)]))
    assert d.status == "unavailable"
    assert d.commands == []


def test_partially_unavailable_controls_the_rest() -> None:
    trvs = [_trv(entity_id="climate.a", available=False), _trv(entity_id="climate.b")]
    d = decide(_inputs(trvs=trvs))
    assert d.status == "heating"
    assert [c.entity_id for c in d.commands] == ["climate.b"]


def test_heat_mode_fallback() -> None:
    d = decide(_inputs(trvs=[_trv(hvac_modes=["off", "auto"])]))
    assert d.commands[0].hvac_mode == "auto"


def test_pending_commands_only_differences() -> None:
    trvs = [_trv(hvac_mode="heat", setpoint=21.5)]
    assert pending_commands([Command("climate.trv", "heat", 21.5)], trvs) == []
    assert pending_commands([Command("climate.trv", "heat", 22.0)], trvs)
    assert pending_commands([Command("climate.trv", "off")], trvs)
    off = [_trv(hvac_mode="off", setpoint=21.5)]
    assert pending_commands([Command("climate.trv", "off")], off) == []
