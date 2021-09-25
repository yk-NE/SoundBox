#!/usr/bin/env python3

import asyncio

from . import Temperature
from . import Humidity
from . import Pressure
from . import Presence
from . import AccelGyro
from . import RGBLed


class Builtin:
    def __init__(self, konashi):
        self._temperature = Temperature.Temperature(konashi)
        self._humidity = Humidity.Humidity(konashi)
        self._pressure = Pressure.Pressure(konashi)
        self._presence = Presence.Presence(konashi)
        self._accelgyro = AccelGyro.AccelGyro(konashi)
        self._rgbled = RGBLed.RGBLed(konashi)

    @property
    def temperature(self) -> Temperature.Temperature:
        return self._temperature

    @property
    def humidity(self) -> Humidity.Humidity:
        return self._humidity

    @property
    def pressure(self) -> Pressure.Pressure:
        return self._pressure

    @property
    def presence(self) -> Presence.Presence:
        return self._presence

    @property
    def accelgyro(self) -> AccelGyro.AccelGyro:
        return self._accelgyro

    @property
    def rgbled(self) -> RGBLed.RGBLed:
        return self._rgbled

    async def _on_connect(self):
        await self._temperature._on_connect()
        await self._humidity._on_connect()
        await self._pressure._on_connect()
        await self._presence._on_connect()
        await self._accelgyro._on_connect()
        await self._rgbled._on_connect()
