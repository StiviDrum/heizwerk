"""Hub: one room controller per room subentry."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, SUBENTRY_ROOM
from .room import RoomController


class HeizwerkHub:
    """Runtime data of the Heizwerk config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create controllers for all rooms."""
        self.hass = hass
        self.entry = entry
        hub_config = {**entry.data, **entry.options}
        self.rooms: dict[str, RoomController] = {
            subentry.subentry_id: RoomController(
                hass, subentry.subentry_id, subentry.data, hub_config
            )
            for subentry in entry.get_subentries_of_type(SUBENTRY_ROOM)
        }

    async def async_setup(self) -> None:
        """Raise / clear the repair issue for rooms with a 0.3 Zeitwerk target."""
        for subentry_id, room in self.rooms.items():
            issue_id = f"target_entity_{subentry_id}"
            if room.legacy_target:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="target_entity_removed",
                    translation_placeholders={
                        "room": room.name,
                        "entity": room.legacy_target,
                        "climate": room.climate_entity_id,
                    },
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    @callback
    def async_start(self) -> None:
        """Start all rooms once the platforms (and restore) are set up."""
        for room in self.rooms.values():
            room.async_start()
        # Issues of thermostats that are no longer part of any room.
        known = {
            f"sensor_select_{sel}"
            for r in self.rooms.values()
            for sel in r.sensor_selects
        }
        # trv_rejects_* are cleared by the rooms on start anyway; any left
        # over belongs to a thermostat that is no longer part of a room.
        for domain, issue_id in list(ir.async_get(self.hass).issues):
            if domain != DOMAIN:
                continue
            if (
                issue_id.startswith("sensor_select_") and issue_id not in known
            ) or issue_id.startswith("trv_rejects_"):
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    @callback
    def async_stop(self) -> None:
        """Stop all rooms."""
        for room in self.rooms.values():
            room.async_stop()

    def room_by_entity(self, entity_id: str) -> RoomController | None:
        """Room whose climate entity is entity_id."""
        return next(
            (r for r in self.rooms.values() if r.climate_entity_id == entity_id), None
        )
