#!/usr/bin/env python3

import asyncio

from . import Gpio
from . import SoftPWM
from . import HardPWM
from . import Analog
from . import I2C
from . import UART
from . import SPI


class Io:
    def __init__(self, konashi):
        self._gpio = Gpio._Gpio(konashi)
        self._softpwm = SoftPWM._SoftPWM(konashi, self._gpio)
        self._hardpwm = HardPWM._HardPWM(konashi, self._gpio)
        self._analog = Analog._Analog(konashi)
        self._i2c = I2C._I2C(konashi, self._gpio)
        self._uart = UART._UART(konashi)
        self._spi = SPI._SPI(konashi, self._gpio)

    @property
    def gpio(self) -> Gpio._Gpio:
        return self._gpio

    @property
    def softpwm(self) -> SoftPWM._SoftPWM:
        return self._softpwm

    @property
    def hardpwm(self) -> HardPWM._HardPWM:
        return self._hardpwm

    @property
    def analog(self) -> Analog._Analog:
        return self._analog

    @property
    def i2c(self) -> I2C._I2C:
        return self._i2c

    @property
    def uart(self) -> UART._UART:
        return self._uart

    @property
    def spi(self) -> SPI._SPI:
        return self._spi

    async def _on_connect(self):
        await self._gpio._on_connect()
        await self._softpwm._on_connect()
        await self._hardpwm._on_connect()
        await self._analog._on_connect()
        await self._i2c._on_connect()
        await self._uart._on_connect()
        await self._spi._on_connect()
