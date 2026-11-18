/** Card strings (de / en). Language from hass.locale.language. */
export interface Strings {
  actual: string;
  target: string;
  roomSensor: string;
  trvSensor: string;
  lower: string;
  raise: string;
  more: string;
  profile: string;
  plan: string;
  noPlan: string;
  off: string;
  heating: string;
  reached: string;
  fromTime: string;
  lowered: string;
  windowPaused: string;
  windowChip: string;
  seasonOff: string;
  summer: string;
  locked: string;
  manual: string;
  by: string;
  until: string;
  untilNext: string;
  trvUnavailable: string;
  nextLine: string;
  nextLineNoValue: string;
  resume: string;
  ventDone: string;
  ventDoneText: string;
  ventRecommended: string;
  ventRecommendedText: string;
  moldWarning: string;
  moldAlarm: string;
  moldText: string;
  humidity: string;
  dewPoint: string;
  outside: string;
  wallHumidity: string;
  wallAttention: string;
  wallOk: string;
  today: string;
  trv: string;
  trvNone: string;
  trvOff: string;
  trvOffFrost: string;
  trvOffline: string;
  trvHeatTo: string;
  sensor: string;
  sensorRoom: string;
  sensorTrv: string;
  sync: string;
  observeOnly: string;
  heatingTitle: string;
  seasonActive: string;
  seasonInactive: string;
  outdoorShort: string;
  windows: string;
  untilNextBlock: string;
  hour1: string;
  hours3: string;
  missing: string;
  notHeizwerk: string;
}

const de: Strings = {
  actual: "Ist",
  target: "Ziel",
  roomSensor: "Raumfühler",
  trvSensor: "TRV-Messung",
  lower: "Ziel senken",
  raise: "Ziel erhöhen",
  more: "Weitere Optionen",
  profile: "Profil",
  plan: "Plan",
  noPlan: "ohne Zeitwerk-Plan",
  off: "Aus",
  heating: "Heizt",
  reached: "Erreicht",
  fromTime: "{p} ab {time}",
  lowered: "Abgesenkt bis {time}",
  windowPaused: "Fenster offen · pausiert",
  windowChip: "Fenster offen seit {min} min · Heizung pausiert",
  seasonOff: "Heizperiode aus",
  summer: "Sommerabschaltung · außen {t}°",
  locked: "Gesperrt",
  manual: "Manuell {t}°",
  by: "von",
  until: "bis",
  untilNext: "bis nächster Block",
  trvUnavailable: "TRV seit {min} min nicht erreichbar",
  nextLine: "{p} bis {time}, dann {n} {v}°",
  nextLineNoValue: "{p} bis {time}, dann {n}",
  resume: "Fortsetzen",
  ventDone: "Genug gelüftet, Fenster kann zu",
  ventDoneText: "Außen {out}, empfohlen {rec} min. Offen seit {min} min.",
  ventRecommended: "Lüften empfohlen",
  ventRecommendedText: "Feuchte {h} %, außen trockener. Empfohlen {rec} min.",
  moldWarning: "Wand feucht",
  moldAlarm: "Schimmelgefahr an der Wand",
  moldText: "Wand {wall} °C, dort {rh} % Feuchte. Lüften und gleichmäßig heizen.",
  humidity: "Feuchte",
  dewPoint: "Taupunkt",
  outside: "außen",
  wallHumidity: "Wandfeuchte",
  wallAttention: "Achtung · Wand {t}°",
  wallOk: "Wand {t}°",
  today: "Heute",
  trv: "TRV",
  trvNone: "kein TRV",
  trvOff: "aus",
  trvOffFrost: "aus, Frostschutz im Gerät",
  trvOffline: "nicht erreichbar",
  trvHeatTo: "heizt auf {t}°",
  sensor: "Fühler",
  sensorRoom: "Raum",
  sensorTrv: "TRV",
  sync: "Abgleich",
  observeOnly: "Nur beobachten",
  heatingTitle: "Heizung",
  seasonActive: "Heizperiode aktiv",
  seasonInactive: "Heizperiode aus",
  outdoorShort: "Außen",
  windows: "Fenster",
  untilNextBlock: "Bis nächster Block",
  hour1: "1 Std.",
  hours3: "3 Std.",
  missing: "Entität nicht gefunden",
  notHeizwerk: "Keine Heizwerk-Entität",
};

const en: Strings = {
  actual: "Current",
  target: "Target",
  roomSensor: "Room sensor",
  trvSensor: "TRV reading",
  lower: "Lower target",
  raise: "Raise target",
  more: "More options",
  profile: "Profile",
  plan: "Plan",
  noPlan: "no Zeitwerk plan",
  off: "Off",
  heating: "Heating",
  reached: "Reached",
  fromTime: "{p} from {time}",
  lowered: "Lowered until {time}",
  windowPaused: "Window open · paused",
  windowChip: "Window open for {min} min · heating paused",
  seasonOff: "Heating period off",
  summer: "Summer lock · outside {t}°",
  locked: "Locked",
  manual: "Manual {t}°",
  by: "by",
  until: "until",
  untilNext: "until next block",
  trvUnavailable: "TRV unreachable for {min} min",
  nextLine: "{p} until {time}, then {n} {v}°",
  nextLineNoValue: "{p} until {time}, then {n}",
  resume: "Resume",
  ventDone: "Aired enough, window can close",
  ventDoneText: "Outside {out}, recommended {rec} min. Open for {min} min.",
  ventRecommended: "Airing recommended",
  ventRecommendedText: "Humidity {h} %, drier outside. Recommended {rec} min.",
  moldWarning: "Damp wall",
  moldAlarm: "Mold risk at the wall",
  moldText: "Wall {wall} °C, {rh} % humidity there. Air and heat evenly.",
  humidity: "Humidity",
  dewPoint: "Dew point",
  outside: "outside",
  wallHumidity: "Wall humidity",
  wallAttention: "Attention · wall {t}°",
  wallOk: "Wall {t}°",
  today: "Today",
  trv: "TRV",
  trvNone: "no TRV",
  trvOff: "off",
  trvOffFrost: "off, frost protection in device",
  trvOffline: "unreachable",
  trvHeatTo: "heats to {t}°",
  sensor: "Sensor",
  sensorRoom: "room",
  sensorTrv: "TRV",
  sync: "Sync",
  observeOnly: "Observe only",
  heatingTitle: "Heating",
  seasonActive: "Heating period active",
  seasonInactive: "Heating period off",
  outdoorShort: "Outside",
  windows: "windows",
  untilNextBlock: "Until next block",
  hour1: "1 h",
  hours3: "3 h",
  missing: "Entity not found",
  notHeizwerk: "Not a Heizwerk entity",
};

export function strings(lang: string | undefined): Strings {
  return (lang ?? "en").toLowerCase().startsWith("de") ? de : en;
}
