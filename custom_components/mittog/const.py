"""Constants for the MitTog integration."""

from datetime import timedelta

DOMAIN = "mittog"

WS_URL = "wss://api.mittog.dk/api/ws/departure/{station}/dinstation/"
WS_ORIGIN = "https://mittog.dk"

# The server pushes a full board every ~5 s. If nothing arrives for this long
# the connection is considered dead and is re-established.
WS_IDLE_TIMEOUT = timedelta(seconds=60)
WS_RECONNECT_MIN = 5
WS_RECONNECT_MAX = 120

CONF_STATION = "station"
CONF_STATION_NAME = "station_name"
CONF_TIME = "time"
CONF_DIRECTION = "direction"

SUBENTRY_DEPARTURE = "departure"

DIRECTION_UP = "UP"
DIRECTION_DOWN = "DOWN"
DIRECTIONS = [DIRECTION_UP, DIRECTION_DOWN]

# A train counts as delayed from this many minutes (DSB's own threshold is 3).
DELAY_THRESHOLD_MIN = 3

# Keep showing a departed train for this long before looking for the next one.
DEPARTED_GRACE = timedelta(minutes=60)

# Banedanmark station codes seen in the feed. Only used for display.
STATION_NAMES: dict[str, str] = {
    "VO": "Vordingborg St.",
    "NEL": "København Syd St.",
    "KH": "København H",
    "KK": "Østerport St.",
    "CPH": "Københavns Lufthavn",
    "NÆ": "Næstved St.",
    "NF": "Nykøbing F St.",
    "EK": "Eskilstrup St.",
    "NV": "Nørre Alslev St.",
    "RG": "Ringsted St.",
    "SG": "Slagelse St.",
    "HGL": "Helsingør St.",
    "ES": "Esbjerg St.",
    "RO": "Roskilde St.",
    "OD": "Odense St.",
    "AR": "Aarhus H",
    "AB": "Aalborg St.",
    "FA": "Fredericia St.",
    "KJ": "Køge St.",
    "HTÅ": "Høje Taastrup St.",
    "GL": "Glumsø St.",
    "LU": "Lundby St.",
    "HZ": "Haslev St.",
}

# Rolling-stock codes from the feed's UnitType, for a friendlier label.
UNIT_TYPES: dict[str, str] = {
    "MFA": "IC3",
    "MFB": "IC3",
    "ER": "IR4",
    "MG": "IC4",
    "MQ": "Desiro",
    "MP": "IC2",
    "ET": "Øresundstog",
    "EB": "Lokomotiv",
    "ME": "Lokomotiv",
    "B": "Dobbeltdækker",
    "BK": "Dobbeltdækker",
    "ABS": "Dobbeltdækker",
}
