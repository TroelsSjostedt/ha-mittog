# MitTog for Home Assistant

Live departure boards from [mittog.dk](https://mittog.dk) (Banedanmark's
passenger-information site) as Home Assistant entities — including what the
Rejseplanen API does not have: **train composition**, car numbers in platform
order, first-class / quiet-zone / bicycle cars, the live track, and
Banedanmark's own delay forecast.

The data is pushed over a websocket; there is no polling and no API key.

> **Status:** personal project, not published. mittog.dk's data is
> "forbeholdt Banedanmark" and the site points developers to Rejseplanen, so
> ask before pointing more than your own household at it.

## Setup

1. Copy `custom_components/mittog` into your HA `config/custom_components/`
   (or add this repository as a custom repository in HACS).
2. Restart Home Assistant.
3. *Settings → Devices & services → Add integration → MitTog*, enter a
   station code (`VO`, `NEL`, `KH`, …).
4. On the station's page, *Add departure*: name, scheduled time, direction.
   The form lists the trains currently on the board with their direction so
   you can tell `UP` from `DOWN` for that station.

## Entities

Per station:

| Entity | |
|---|---|
| `sensor.<station>_naeste_afgang` | Next expected departure (timestamp). Attribute `afgange` = next 10 trains. |
| `binary_sensor.<station>_forbindelse` | Websocket connected (diagnostic). |

Per watched departure (device named as you chose):

| Entity | State | Notes |
|---|---|---|
| `sensor.<name>_afgang` | expected departure (timestamp) | Attributes: `planlagt`, `forventet`, `prognose`, `forsinkelse_min`, `spor`, `spor_aendret`, `vogne`, `togsaet`, `foerste_klasse`, `stillezone`, `cykler`, `destination`, `bemaerkning`, … |
| `sensor.<name>_forsinkelse` | minutes | `None` while there is no forecast or the train is cancelled |
| `sensor.<name>_spor` | track | attributes `spor_oprindeligt`, `spor_aendret` |
| `sensor.<name>_vogne` | number of cars | attributes with the car list |
| `sensor.<name>_status` | enum | `ikke_i_feed` · `planlagt` · `til_tiden` · `forsinket` · `aflyst` · `afgaaet` |
| `binary_sensor.<name>_forsinket` | problem | delay ≥ 3 min |
| `binary_sensor.<name>_aflyst` | problem | |

Trains appear on the board roughly five hours ahead and get a forecast about
an hour before departure. Until then the departure sensors are `unknown` /
`ikke_i_feed`; that is expected, not a fault. A departed train stays visible
for an hour so automations can react to it.

## Development

```
uv venv .venv && uv pip install --python .venv/bin/python aiohttp pytest pyflakes
.venv/bin/python -m pytest tests/
.venv/bin/python tests/live_client.py VO 20   # watch the real feed
```

`model.py` and `client.py` have no Home Assistant dependency and are tested
against recorded boards in `tests/fixtures/`.
