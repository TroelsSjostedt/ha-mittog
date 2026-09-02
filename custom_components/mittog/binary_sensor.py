"""Binary sensors: connection state + delayed/cancelled flags per departure."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SUBENTRY_DEPARTURE
from .coordinator import MitTogConfigEntry
from .entity import MitTogDepartureEntity, MitTogStationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitTogConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([ConnectionSensor(coordinator)])
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_DEPARTURE:
            continue
        async_add_entities(
            [DelayedSensor(coordinator, subentry), CancelledSensor(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class ConnectionSensor(MitTogStationEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "forbindelse")

    @property
    def available(self) -> bool:
        # This one must keep reporting while the feed is down.
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected


class DelayedSensor(MitTogDepartureEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, subentry) -> None:
        super().__init__(coordinator, subentry, "forsinket")

    @property
    def is_on(self) -> bool | None:
        train = self.train
        if train is None:
            return None
        return train.is_delayed and not train.cancelled


class CancelledSensor(MitTogDepartureEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, subentry) -> None:
        super().__init__(coordinator, subentry, "aflyst")

    @property
    def is_on(self) -> bool | None:
        train = self.train
        return train.cancelled if train else None
