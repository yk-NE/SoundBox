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
KONASHI_CFG_CMD_HARDPWM = 0x03
KONASHI_UUID_HARDPWM_CONFIG_GET = "064d0204-8251-49d9-b6f3-f7ba35e5d0a1"

KONASHI_UUID_CONTROL_CMD = "064d0301-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_CTL_CMD_HARDPWM = 0x03
KONASHI_UUID_HARDPWM_OUTPUT_GET = "064d0305-8251-49d9-b6f3-f7ba35e5d0a1"


KONASHI_HARDPWM_COUNT = 4
KONASHI_HARDPWM_PIN_TO_GPIO_NUM = [0, 1, 2, 3]
class Clock(IntEnum):
    HFCLK = 0
    CASCADE = 1
KONASHI_HARDPWM_CLOCK_FREQ = {Clock.HFCLK: 38400000, Clock.CASCADE: 20000}
class Prescale(IntEnum):
    DIV1 = 0x0
    DIV2 = 0x1
    DIV4 = 0x2
    DIV8 = 0x3
    DIV16 = 0x4
    DIV32 = 0x5
    DIV64 = 0x6
    DIV128 = 0x7
    DIV256 = 0x8
    DIV512 = 0x9
    DIV1024 = 0xA
class PinConfig(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('enabled', c_uint8, 1),
        ('', c_uint8, 7)
    ]
    def __init__(self, enable: bool) -> None:
        self.enabled = enable
    def __str__(self):
        s = "KonashiHardPWMPinConfig("
        if self.enabled:
            s += "enabled"
        else:
            s += "disabled"
        s += ")"
        return s
class PwmConfig(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('prescale', c_uint8, 4),
        ('clock', c_uint8, 4),
        ('top', c_uint16)
    ]
    def __init__(self, clock: Clock, prescale: Prescale, top: int) -> None:
        """
        Parameters
        ----------
        clock : Clock)
            The used clock.
        prescale : Prescale
            The clock prescaling.
        top : int
            The value written to the TOP register of the timer (valid range: [0,65535]).

        Raises
        ------
        ValueError
            If the top value is out of range.
        """
        self.clock = clock
        self.prescale = prescale
        if top < 0 or top > 65535:
            raise ValueError("The valid range for top is [0,65535]")
        self.top = top
    def __str__(self):
        s = "KonashiHardPWMConfig("
        if self.clock == Clock.HFCLK:
            s += "Clock=HF"
        elif self.clock == Clock.CASCADE:
            s += "Clock=CASCADE"
        else:
            s += "Clock=unknown"
        s += ", Prescale={}".format(1<<self.prescale)
        s += ", Top={}".format(self.top)
        s += ", Period={}s".format((self.top/(KONASHI_HARDPWM_CLOCK_FREQ[self.clock]/(1<<self.prescale))))
        s += ")"
        return s
class _Config(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('pin', PinConfig*KONASHI_HARDPWM_COUNT),
        ('pwm', PwmConfig)
    ]

class PinControl(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('control_value', c_uint16),
        ('transition_duration', c_uint32)
    ]
    def __init__(self, control_value: int, transition_duration: int=0):
        """
        Parameters
        ----------
        control_value : int
            The control value written directly to the timer capture/compare register (valid range: [0,65535]).
        transition_duration : int, optional
            Duration to reach the target value in untis of 1ms (valid range: [0,4294967295]).

        Raises
        ------
        ValueError
            If the control value or the duration is out of range.
        """
        if control_value < 0 or control_value > 65535:
            raise ValueError("The valid range for the control value is [0,65535]")
        if transition_duration < 0 or transition_duration > 4294967295:
            raise ValueError("The valid range for the transition duration is [0,4294967295] (unit: 1ms)")
        self.control_value = control_value
        self.transition_duration = transition_duration
    def __str__(self):
        s = "KonashiHardPWMPinControl("
        s += "Control value "+str(self.control_value)+", Transition duration "+str(self.transition_duration)+"ms"
        s += ")"
        return s
_PinsControl = PinControl*KONASHI_HARDPWM_COUNT


class _HardPWM(KonashiElementBase._KonashiElementBase):
    def __init__(self, konashi, gpio) -> None:
        super().__init__(konashi)
        self._gpio = gpio
        self._config = _Config()
        self._output = _PinsControl()
        self._trans_end_cb = None
        self._ongoing_control = []

    def __str__(self):
        return f'KonashiHardPWM'

    def __repr__(self):
        return f'KonashiHardPWM()'


    async def _on_connect(self) -> None:
        await self._enable_notify(KONASHI_UUID_HARDPWM_CONFIG_GET, self._ntf_cb_config)
        await self._read(KONASHI_UUID_HARDPWM_CONFIG_GET)
        await self._enable_notify(KONASHI_UUID_HARDPWM_OUTPUT_GET, self._ntf_cb_output)
        await self._read(KONASHI_UUID_HARDPWM_OUTPUT_GET)


    def _ntf_cb_config(self, sender, data):
        logger.debug("Received config data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._config = _Config.from_buffer_copy(data)

    def _ntf_cb_output(self, sender, data):
        logger.debug("Received output data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._output = _PinsControl.from_buffer_copy(data)
        for i in range(KONASHI_HARDPWM_COUNT):
            if i in self._ongoing_control and self._output[i].transition_duration == 0:
                self._ongoing_control.remove(i)
                if self._trans_end_cb is not None:
                    self._trans_end_cb(i, self._calc_duty_for_control_value(self._output[i].control_value))


    def _calc_pwm_config_for_period(self, period: float) -> PwmConfig:
        freq = KONASHI_HARDPWM_CLOCK_FREQ[Clock.HFCLK]
        presc = None
        top = None
        for div in Prescale:
            f = freq/(1<<div.value)
            top = round(period*f)
            if top <= 65535:
                presc = div
                break
        if presc is not None:
            return PwmConfig(Clock.HFCLK, presc, top)
        freq = KONASHI_HARDPWM_CLOCK_FREQ[Clock.CASCADE]
        presc = Prescale.DIV1
        top = round(period*freq)
        if top <= 65535:
            return PwmConfig(Clock.CASCADE, presc, top)
        raise ValueError("A suitable configuration cannot be calculated for this period value")

    def _calc_duty_for_control_value(self, value: int) -> float:
        return value * 100.0 / self._config.pwm.top


    async def config_pwm(self, period: float) -> None:
        """Configure the period for PWM output."""
        config = self._calc_pwm_config_for_period(period)
        b = bytearray([KONASHI_CFG_CMD_HARDPWM, 0xFF]) + bytearray(config)
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def get_pwm_config(self) -> PwmConfig:
        """Returns the current PWM configuration."""
        await self._read(KONASHI_UUID_HARDPWM_CONFIG_GET)
        return self._config.pwm

    async def config_pins(self, configs: Sequence(Tuple[int, bool])) -> None:
        """
        Configure pins.

        Parameters
        ----------
        configs : list of tuples of int, PinConfig
            The list of configurations to set. For each tuple:
            int: pin bitmask. A bitmask of the pins to apply this configuration to (range 0x00 to 0x0F).
            bool: config. Enable or disable the pins specified in the bitmask.

        Raises
        ------
        PinUnavailableError
            If a pin is already configured with a function other than HardPWM.
        """
        b = bytearray([KONASHI_CFG_CMD_HARDPWM])
        for config in configs:
            for i in range(KONASHI_HARDPWM_COUNT):
                if (config[0]&(1<<i)) > 0:
                    if self._gpio._config[KONASHI_HARDPWM_PIN_TO_GPIO_NUM[i]].function != int(Gpio.PinFunction.DISABLED) and self._gpio._config[KONASHI_HARDPWM_PIN_TO_GPIO_NUM[i]].function != int(Gpio.PinFunction.PWM):
                        raise PinUnavailableError(f'Pin {KONASHI_HARDPWM_PIN_TO_GPIO_NUM[i]} is already configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_HARDPWM_PIN_TO_GPIO_NUM[i]].function]}')
                    b.extend(bytearray([(i<<4)|int(config[1])]))
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def get_pins_config(self, pin_bitmask: int) -> List[PinConfig]:
        """Returns a list of configurations for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_HARDPWM_CONFIG_GET)
        l = []
        for i in range(KONASHI_HARDPWM_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                l.append(self._config.pin[i])
        return l

    def set_transition_end_cb(self, notify_callback: Callable[[int, float], None]) -> None:
        """
        Set a transition end callback function.
        The function will be called when HardPWM value transition is completed.

        Parameters
        ----------
        notify_callback : callable
            The input callback function.
            The function takes 1 parameter and returns nothing:
                pin: int. The pin number.
        """
        self._trans_end_cb = notify_callback

    async def control_pins(self, controls: Sequence(Tuple[int, PinControl])) -> None:
        """
        Control pins.

        Parameters
        ----------
        controls : list of tuples of int, PinControl
            The list of controls to set. For each tuple:
            int: pin bitmask. A bitmask of the pins to apply this control to (range 0x00 to 0x0F).
            PinControl: control. The control for the pins specified in the bitmask.

        Raises
        ------
        PinUnavailableError
            If a pin is not configured with the HardPWM function.
        """
        ongoing_control = []
        b = bytearray([KONASHI_CTL_CMD_HARDPWM])
        for control in controls:
            for i in range(KONASHI_HARDPWM_COUNT):
                if (control[0]&(1<<i)) > 0:
                    if self._gpio._config[KONASHI_HARDPWM_PIN_TO_GPIO_NUM[i]].function != int(Gpio.PinFunction.PWM):
                        raise PinUnavailableError(f'Pin {KONASHI_HARDPWM_PIN_TO_GPIO_NUM[i]} is not configured as PWM (configured as {Gpio._KONASHI_GPIO_FUNCTION_STR[self._gpio._config[KONASHI_HARDPWM_PIN_TO_GPIO_NUM[i]].function]})')
                    b.extend(bytearray([i])+bytearray(control[1]))
                    ongoing_control.append(i)
        await self._write(KONASHI_UUID_CONTROL_CMD, b)
        for i in ongoing_control:
            if i not in self._ongoing_control:
                self._ongoing_control.append(i)

    def calc_control_value_for_duty(self, duty: float) -> int:
        """Return the control value for a specified duty."""
        return round(duty * self._config.pwm.top / 100.0)

    async def get_pins_control(self, pin_bitmask: int) -> List[PinControl]:
        """Returns a list of output controls for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_HARDPWM_OUTPUT_GET)
        l = []
        for i in range(KONASHI_HARDPWM_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                l.append(self._output[i])
        return l
