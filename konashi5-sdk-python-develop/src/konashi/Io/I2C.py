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
KONASHI_CFG_CMD_I2C = 0x05
KONASHI_UUID_I2C_CONFIG_GET = "064d0206-8251-49d9-b6f3-f7ba35e5d0a1"

KONASHI_UUID_CONTROL_CMD = "064d0301-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_CTL_CMD_I2C_DATA = 0x05
KONASHI_UUID_I2C_DATA_IN = "064d0308-8251-49d9-b6f3-f7ba35e5d0a1"


KONASHI_I2C_SDA_PINNB = 6
KONASHI_I2C_SCL_PINNB = 7
class Mode(IntEnum):
    STANDARD = 0
    FAST = 1
class Config(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('mode', c_uint8, 1),
        ('enabled', c_uint8, 1),
        ('', c_uint8, 6)
    ]
    def __init__(self, enable: bool, mode: Mode) -> None:
        self.enabled = enable
        self.mode = mode
    def __str__(self):
        s = "KonashiI2CConfig("
        if self.enabled:
            s += "enabled"
        else:
            s += "disabled"
        s += ", mode:"
        if self.mode == Mode.STANDARD:
            s += "standard"
        elif self.mode == Mode.FAST:
            s += "fast"
        else:
            s += "unknown"
        s += ")"
        return s

class Operation(IntEnum):
    WRITE = 0
    READ = 1
    WRITE_READ = 2
class Result(IntEnum):
    DONE = 0  # Transfer completed successfully.
    NACK = 1  # NACK received during transfer.
    BUS_ERR = 2  # Bus error during transfer (misplaced START/STOP).
    ARB_LOST = 3  # Arbitration lost during transfer.
    USAGE_FAULT = 4  # Usage fault.
    SW_FAULT = 5  # SW fault.


class _I2C(KonashiElementBase._KonashiElementBase):
    def __init__(self, konashi, gpio) -> None:
        super().__init__(konashi)
        self._gpio = gpio
        self._config = Config(False, Mode.STANDARD)
        self._async_loop = None
        self._data_in_future = None

    def __str__(self):
        return f'KonashiI2C'

    def __repr__(self):
        return f'KonashiI2C()'


    async def _on_connect(self) -> None:
        await self._enable_notify(KONASHI_UUID_I2C_CONFIG_GET, self._ntf_cb_config)
        await self._read(KONASHI_UUID_I2C_CONFIG_GET)
        await self._enable_notify(KONASHI_UUID_I2C_DATA_IN, self._ntf_cb_data_in)


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
            If a pin is already configured with a function other than I2C.
        """
        if config.enabled:
            if self._gpio._config[KONASHI_I2C_SDA_PINNB].function != int(Gpio.PinFunction.DISABLED) and self._gpio._config[KONASHI_I2C_SDA_PINNB].function != int(Gpio.PinFunction.I2C):
                raise PinUnavailableError(f'Pin {KONASHI_I2C_SDA_PINNB} is already configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_I2C_SDA_PINNB].function]}')
            if self._gpio._config[KONASHI_I2C_SCL_PINNB].function != int(Gpio.PinFunction.DISABLED) and self._gpio._config[KONASHI_I2C_SCL_PINNB].function != int(Gpio.PinFunction.I2C):
                raise PinUnavailableError(f'Pin {KONASHI_I2C_SCL_PINNB} is already configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_I2C_SCL_PINNB].function]}')
        b = bytearray([KONASHI_CFG_CMD_I2C]) + bytearray(config)
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def get_config(self) -> Config:
        """Returns the current configuration."""
        await self._read(KONASHI_UUID_I2C_CONFIG_GET)
        return self._config

    async def transaction(self, operation: Operation, address: int, read_len: int, write_data: bytes) -> Tuple[Result, int, bytes]:
        """
        Run an I2C transaction.

        Parameters
        ----------
        operation : Operation
            The transaction operation.
        address : int
            The unshifted I2C slave address (valid range: 0x00 ~ 0x7F).
        read_len : int
            The length of the data to read (valid range: 0 ~ 126).
        write_data : bytes
            The data to write (length range: 0 ~ 124).

        Returns
        -------
        result : Result
            The operation result.
        address : int
            The slave address.
        data : bytes
            The read data.

        Raises
        ------
        ValueError
            If the read length or address is out of range or write data is too long.
        """
        if read_len > 126:
            ValueError("Maximum read length is 126 bytes")
        if address > 0x7F:
            ValueError("The I2C address should be in the range [0x01,0x7F]")
        if len(write_data) > 124:
            ValueError("Maximum write data length is 124 bytes")
        b = bytearray([KONASHI_CTL_CMD_I2C_DATA, operation, read_len, address]) + bytearray(write_data)
        self._async_loop = asyncio.get_event_loop()
        self._data_in_future = self._async_loop.create_future()
        await self._write(KONASHI_UUID_CONTROL_CMD, b)
        res = await self._data_in_future
        self._async_loop = None
        self._data_in_future = None
        ret = (Result(res[0]), res[1], res[2:])
        return ret
