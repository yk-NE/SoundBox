#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import struct
import logging
from ctypes import *
from typing import *
from enum import *

from bleak import *

from .. import KonashiElementBase
from ..Errors import *
from . import Gpio


logger = logging.getLogger(__name__)


KONASHI_UUID_CONFIG_CMD = "064d0201-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_CFG_CMD_SPI = 0x07
KONASHI_UUID_SPI_CONFIG_GET = "064d0208-8251-49d9-b6f3-f7ba35e5d0a1"

KONASHI_UUID_CONTROL_CMD = "064d0301-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_CTL_CMD_SPI_DATA = 0x07
KONASHI_UUID_SPI_DATA_IN = "064d030b-8251-49d9-b6f3-f7ba35e5d0a1"


KONASHI_SPI_CS_PINNB = 2
KONASHI_SPI_CLK_PINNB = 5
KONASHI_SPI_MISO_PINNB = 3
KONASHI_SPI_MOSI_PINNB = 4
class Mode(IntEnum):
    MODE0 = 0  # SPI mode 0: CLKPOL=0, CLKPHA=0.
    MODE1 = 1  # SPI mode 1: CLKPOL=0, CLKPHA=1.
    MODE2 = 2  # SPI mode 2: CLKPOL=1, CLKPHA=0.
    MODE3 = 3  # SPI mode 3: CLKPOL=1, CLKPHA=1.
class Endian(IntEnum):
    LSB_FIRST = 0  # LSB bit is transmitted first.
    MSB_FIRST = 1  # MSB bit is transmitted first.
class Config(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('mode', c_uint8, 2),
        ('', c_uint8, 1),
        ('endian', c_uint8, 1),
        ('', c_uint8, 3),
        ('enabled', c_uint8, 1),
        ('bitrate', c_uint32)
    ]
    def __init__(self, enable: bool, mode: Mode, endian: Endian, bitrate: int) -> None:
        self.enabled = enable
        self.mode = mode
        self.endian = endian
        self.bitrate = bitrate
    def __str__(self):
        s = "KonashiSPIConfig("
        if self.enabled:
            s += "enabled"
        else:
            s += "disabled"
        if self.mode == Mode.MODE0:
            s += ", CLKPOL=0/CLKPHA=0"
        elif self.mode == Mode.MODE1:
            s += ", CLKPOL=0/CLKPHA=1"
        elif self.mode == Mode.MODE2:
            s += ", CLKPOL=1/CLKPHA=0"
        elif self.mode == Mode.MODE3:
            s += ", CLKPOL=1/CLKPHA=1"
        if self.endian == Endian.LSB_FIRST:
            s += ", LSB"
        elif self.endian == Endian.MSB_FIRST:
            s += ", MSB"
        s += ", "+str(self.bitrate)
        s += ")"
        return s


class _SPI(KonashiElementBase._KonashiElementBase):
    def __init__(self, konashi, gpio) -> None:
        super().__init__(konashi)
        self._gpio = gpio
        self._config = Config(False, Mode.MODE0, Endian.LSB_FIRST, 0)
        self._async_loop = None
        self._data_in_future = None

    def __str__(self):
        return f'KonashiSpi'

    def __repr__(self):
        return f'KonashiSpi()'


    async def _on_connect(self) -> None:
        await self._enable_notify(KONASHI_UUID_SPI_CONFIG_GET, self._ntf_cb_config)
        await self._read(KONASHI_UUID_SPI_CONFIG_GET)
        await self._enable_notify(KONASHI_UUID_SPI_DATA_IN, self._ntf_cb_data_in)


    def _ntf_cb_config(self, sender, data):
        logger.debug("Received config data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._config = Config.from_buffer_copy(data)

    def _ntf_cb_data_in(self, sender, data):
        logger.debug("Received input data: {}".format("".join("{:02x}".format(x) for x in data)))
        if self._async_loop is not None and self._data_in_future is not None:
            self._async_loop.call_soon_threadsafe(self._data_in_future.set_result, data)


    async def config(self, config: Config) -> None:
        """
        Configure the I2C peripheral.

        Parameters
        ----------
        config : Config
            The configuration.

        Raises
        ------
        PinUnavailableError
            If a pin is already configured with a function other than SPI.
        """
        if config.enabled:
            if self._gpio._config[KONASHI_SPI_CS_PINNB].function != int(Gpio.PinFunction.DISABLED) and self._gpio._config[KONASHI_SPI_CS_PINNB].function != int(Gpio.PinFunction.SPI):
                raise PinUnavailableError(f'Pin {KONASHI_SPI_CS_PINNB} is already configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_SPI_CS_PINNB].function]}')
            if self._gpio._config[KONASHI_SPI_CLK_PINNB].function != int(Gpio.PinFunction.DISABLED) and self._gpio._config[KONASHI_SPI_CLK_PINNB].function != int(Gpio.PinFunction.SPI):
                raise PinUnavailableError(f'Pin {KONASHI_SPI_CLK_PINNB} is already configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_SPI_CLK_PINNB].function]}')
            if self._gpio._config[KONASHI_SPI_MISO_PINNB].function != int(Gpio.PinFunction.DISABLED) and self._gpio._config[KONASHI_SPI_MISO_PINNB].function != int(Gpio.PinFunction.SPI):
                raise PinUnavailableError(f'Pin {KONASHI_SPI_MISO_PINNB} is already configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_SPI_MISO_PINNB].function]}')
            if self._gpio._config[KONASHI_SPI_MOSI_PINNB].function != int(Gpio.PinFunction.DISABLED) and self._gpio._config[KONASHI_SPI_MOSI_PINNB].function != int(Gpio.PinFunction.SPI):
                raise PinUnavailableError(f'Pin {KONASHI_SPI_MOSI_PINNB} is already configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_SPI_MOSI_PINNB].function]}')
        b = bytearray([KONASHI_CFG_CMD_SPI]) + bytearray(config)
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def get_config(self) -> Config:
        """Returns the current configuration."""
        await self._read(KONASHI_UUID_SPI_CONFIG_GET)
        return self._config

    async def transaction(self, write_data: bytes) -> bytes:
        """
        Run a transaction.

        Parameters
        ----------
        write_data : bytes
            The data to send (length range: 1 ~ 127)

        Returns
        -------
        bytes
            The read data.

        Raises
        ------
        ValueError
            If the write data is empty or too long.
        """
        if len(write_data) == 0:
            ValueError("Write data buffer cannot be empty")
        if len(write_data) > 127:
            ValueError("Maximum write data length is 127 bytes")
        b = bytearray([KONASHI_CTL_CMD_SPI_DATA]) + bytearray(write_data)
        self._async_loop = asyncio.get_event_loop()
        self._data_in_future = self._async_loop.create_future()
        await self._write(KONASHI_UUID_CONTROL_CMD, b)
        res = await self._data_in_future
        self._async_loop = None
        self._data_in_future = None
        return res
