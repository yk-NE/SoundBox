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


logger = logging.getLogger(__name__)


KONASHI_UUID_CONFIG_CMD = "064d0201-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_CFG_CMD_GPIO = 0x01
KONASHI_UUID_GPIO_CONFIG_GET = "064d0202-8251-49d9-b6f3-f7ba35e5d0a1"

KONASHI_UUID_CONTROL_CMD = "064d0301-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_CTL_CMD_GPIO= 0x01
KONASHI_UUID_GPIO_OUTPUT_GET = "064d0302-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_UUID_GPIO_INPUT = "064d0303-8251-49d9-b6f3-f7ba35e5d0a1"


KONASHI_GPIO_COUNT = 8
_KONASHI_GPIO_FUNCTION_STR = ["DISABLED", "GPIO", "PWM", "I2C", "SPI"]
class PinFunction(IntEnum):
    DISABLED = 0
    GPIO = 1
    PWM = 2
    I2C = 3
    SPI = 4
class PinDirection(IntEnum):
    DISABLED = 0
    INPUT = 1
    OUTPUT = 2
    OPEN_DRAIN = 3
    OPEN_SOURCE = 4
class PinPull(IntEnum):
    NONE = 0
    UP = 1
    DOWN = 2
class PinConfig(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('function', c_uint8, 4),
        ('', c_uint8, 4),
        ('pull_down', c_uint8, 1),
        ('pull_up', c_uint8, 1),
        ('wired_fct', c_uint8, 2),
        ('direction', c_uint8, 1),
        ('send_on_change', c_uint8, 1),
        ('', c_uint8, 2)
    ]
    def __init__(self, direction: PinDirection, pull: PinPull, send_on_change: bool):
        if direction == PinDirection.INPUT:
            self.function = 1
            self.direction = 0
            self.wired_fct = 0
        elif direction == PinDirection.OUTPUT:
            self.function = 1
            self.direction = 1
            self.wired_fct = 0
        elif direction == PinDirection.OPEN_DRAIN:
            self.function = 1
            self.direction = 0
            self.wired_fct = 1
        elif direction == PinDirection.OPEN_SOURCE:
            self.function = 1
            self.direction = 0
            self.wired_fct = 2
        else:
            self.function = 0
            self.direction = 0
            self.wired_fct = 0
        if pull == PinPull.UP:
            self.pull_down = 0
            self.pull_up = 1
        elif pull == PinPull.DOWN:
            self.pull_down = 1
            self.pull_up = 0
        else:
            self.pull_down = 0
            self.pull_up = 0
        self.send_on_change = send_on_change
    def __str__(self):
        s = "KonashiGpioPinConfig("
        try:
            s += _KONASHI_GPIO_FUNCTION_STR[self.function]
            if self.function == PinFunction.GPIO:
                s += ", "
                s += "OD" if self.wired_fct==1 else "OS" if self.wired_fct==2 else "OUT" if 1 else "IN"
                if self.pull_down:
                    s += ", PDOWN"
                if self.pull_up:
                    s += ", PUP"
                if self.send_on_change:
                    s += ", NTFY"
        except:
            s += ", Unknown"
        s += ")"
        return s
_PinsConfig = PinConfig*KONASHI_GPIO_COUNT

class PinControl(IntEnum):
    LOW = 0
    HIGH = 1
    TOGGLE = 2
class PinLevel(IntEnum):
    LOW = 0
    HIGH = 1
    INVALID = 2
class _PinIO(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('level', c_uint8, 1),
        ('', c_uint8, 3),
        ('valid', c_uint8, 1),
        ('', c_uint8, 3)
    ]
_PinsIO = _PinIO*KONASHI_GPIO_COUNT


class _Gpio(KonashiElementBase._KonashiElementBase):
    def __init__(self, konashi) -> None:
        super().__init__(konashi)
        self._config = _PinsConfig()
        self._output = _PinsIO()
        self._input = _PinsIO()
        self._input_cb = None

    def __str__(self):
        return f'KonashiGpio'

    def __repr__(self):
        return f'KonashiGpio()'


    async def _on_connect(self) -> None:
        await self._enable_notify(KONASHI_UUID_GPIO_CONFIG_GET, self._ntf_cb_config)
        await self._read(KONASHI_UUID_GPIO_CONFIG_GET)
        await self._enable_notify(KONASHI_UUID_GPIO_OUTPUT_GET, self._ntf_cb_output)
        await self._read(KONASHI_UUID_GPIO_OUTPUT_GET)
        await self._enable_notify(KONASHI_UUID_GPIO_INPUT, self._ntf_cb_input)
        await self._read(KONASHI_UUID_GPIO_INPUT)
        

    def _ntf_cb_config(self, sender, data):
        logger.debug("Received config data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._config = _PinsConfig.from_buffer_copy(data)

    def _ntf_cb_output(self, sender, data):
        logger.debug("Received output data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._output = _PinsIO.from_buffer_copy(data)

    def _ntf_cb_input(self, sender, data):
        logger.debug("Received input data: {}".format("".join("{:02x}".format(x) for x in data)))
        for i in range(KONASHI_GPIO_COUNT):
            if data[i]&0x10:
                val = data[i]&0x01
                if self._input[i].level != val:
                    if self._input_cb is not None:
                        self._input_cb(i, val)
        self._input = _PinsIO.from_buffer_copy(data)


    async def config_pins(self, configs: Sequence(Tuple[int, PinConfig])) -> None:
        """
        Configure pins.

        Parameters
        ----------
        configs : list of tuples of int, bool, PinConfig
            The list of configurations to set. For each tuple:
            int: pin bitmask. A bitmask of the pins to apply this configuration to (range 0x00 to 0xFF).
            PinConfig: config. The configuration for the pins specified in the bitmask.

        Raises
        ------
        PinUnavailableError
            If a pin is already configured with a function other than GPIO.
        """
        b = bytearray([KONASHI_CFG_CMD_GPIO])
        for config in configs:
            for i in range(KONASHI_GPIO_COUNT):
                if (config[0]&(1<<i)) > 0:
                    if PinFunction(self._config[i].function) != PinFunction.DISABLED and PinFunction(self._config[i].function) != PinFunction.GPIO:
                        raise PinUnavailableError(f'Pin {i} is already configured as {_KONASHI_GPIO_FUNCTION_STR[self._config[i].function]}')
                    b.extend(bytearray([(i<<4)|(bytes(config[1])[0]), bytes(config[1])[1]]))
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def get_pins_config(self, pin_bitmask: int) -> List[PinConfig]:
        """Returns a list of configurations for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_GPIO_CONFIG_GET)
        l = []
        for i in range(KONASHI_GPIO_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                l.append(self._config[i])
        return l

    def set_input_cb(self, notify_callback: Callable[[int, int], None]) -> None:
        """
        Set a GPIO input callback function.
        The function will be called when GPIO input is changed.

        Parameters
        ----------
        notify_callback : callable
            The input callback function.
            The function takes 2 parameters and returns nothing:
                pin: int. The pin number.
                value: int. The pin value.
        """
        self._input_cb = notify_callback

    async def control_pins(self, controls: Sequence(Tuple[int, PinControl])) -> None:
        """
        Control pins.

        Parameters
        ----------
        controls : list of tuples of int, PinControl
            The list of controls to set. For each tuple:
            int: pin bitmask. A bitmask of the pins to apply this control to.
            PinControl: control. The control for the pins specified in the bitmask.

        Raises
        ------
        PinUnavailableError
            If a pin is not configured with the GPIO function.
        """
        b = bytearray([KONASHI_CTL_CMD_GPIO])
        for control in controls:
            for i in range(KONASHI_GPIO_COUNT):
                if (control[0]&(1<<i)) > 0:
                    if PinFunction(self._config[i].function) != PinFunction.GPIO:
                        raise PinUnavailableError(f'Pin {i} is not configured as GPIO (configured as {_KONASHI_GPIO_FUNCTION_STR[self._config[i].function]})')
                    b.extend(bytearray([(i<<4)|(control[1])]))
        await self._write(KONASHI_UUID_CONTROL_CMD, b)

    async def get_pins_control(self, pin_bitmask: int) -> List[PinLevel]:
        """Returns a list of output levels for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_GPIO_OUTPUT_GET)
        l = []
        for i in range(KONASHI_GPIO_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                if not self._output[i].valid:
                    l.append(PinLevel.INVALID)
                else:
                    l.append(PinLevel(self._output[i].level))
        return l

    async def read_pins(self, pin_bitmask: int) -> List[PinLevel]:
        """Returns a list of input levels for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_GPIO_INPUT)
        l = []
        for i in range(KONASHI_GPIO_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                if not self._input[i].valid:
                    l.append(PinLevel.INVALID)
                else:
                    l.append(PinLevel(self._input[i].level))
        return l
