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
KONASHI_CFG_CMD_ANALOG = 0x04
KONASHI_UUID_ANALOG_CONFIG_GET = "064d0205-8251-49d9-b6f3-f7ba35e5d0a1"

KONASHI_UUID_CONTROL_CMD = "064d0301-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_CTL_CMD_ANALOG = 0x04
KONASHI_UUID_ANALOG_OUTPUT_GET = "064d0306-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_UUID_ANALOG_INPUT = "064d0307-8251-49d9-b6f3-f7ba35e5d0a1"


KONASHI_AIO_COUNT = 3
class AdcRef(IntEnum):
    DISABLE = 0
    REF_1V25 = 0x0+1
    REF_2V5 = 0x1+1
    REF_VDD = 0x2+1
class VdacRef(IntEnum):
    DISABLE = 0
    REF_1V25LN = 0x0+1
    REF_2V5LN = 0x1+1
    REF_1V25 = 0x2+1
    REF_2V5 = 0x3+1
    REF_VDD = 0x4+1
class IdacRange(IntEnum):
    DISABLE = 0
    RANGE0 = 0x0+1  # 0.05~1.6uA range, 50nA step
    RANGE1 = 0x1+1  # 1.6~4.7uA range, 100nA step
    RANGE2 = 0x2+1  # 0.5~16uA range, 500nA step
    RANGE3 = 0x3+1  # 2~64uA range, 2000nA step
class PinDirection(IntEnum):
    INPUT = 0
    OUTPUT = 1
class PinConfig(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('direction', c_uint8, 1),
        ('send_on_change', c_uint8, 1),
        ('', c_uint8, 1),
        ('enabled', c_uint8, 1),
        ('', c_uint8, 4)
    ]
    def __init__(self, enabled: bool, direction: PinDirection=PinDirection.INPUT, send_on_change: bool=True):
        """
        Parameters
        ----------
        enable : bool
            Enable or disable the pin.
        direction : PinDirection
            The pin direction.
        send_on_change : bool
            Send latest data notification for this pin.
        """
        self.enabled = enabled
        self.send_on_change = send_on_change
        self.direction = direction
class AnalogConfig(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('adc_update_period', c_uint8),
        ('adc_voltage_reference', c_uint8, 4),
        ('', c_uint8, 4),
        ('vdac_voltage_reference', c_uint8, 4),
        ('', c_uint8, 4),
        ('idac_current_step', c_uint8, 4),
        ('', c_uint8, 4)
    ]
class _Config(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('pin', PinConfig*KONASHI_AIO_COUNT),
        ('analog', AnalogConfig),
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
            The control value (valid range: [0,65535]).
        transition_duration : int, optional
            Duration to reach the target value in untis of 1ms (valid range: [0,4294967295])

        Raises
        ------
        ValueError
            If the control value or duration is out of range.
        """
        if control_value < 0 or control_value > 65535:
            raise ValueError("The valid range for the control value is [0,65535]")
        if transition_duration < 0 or transition_duration > 4294967295:
            raise ValueError("The valid range for the transition duration is [0,4294967295] (unit: 1ms)")
        self.control_value = control_value
        self.transition_duration = transition_duration
    def __str__(self):
        s = "KonashiAnalogPinControl("
        if self.control_type is None:
            s += "Control value "+str(self.control_value)+", Transition duration "+str(self.transition_duration)+"ms"
        s += ")"
        return s
class _PinOut(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('valid', c_uint8),
        ('control', PinControl)
    ]
class _PinsOut(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('idac_current_step', c_uint8, 4),
        ('vdac_voltage_reference', c_uint8, 4),
        ('pin', _PinOut*KONASHI_AIO_COUNT)
    ]
class _PinIn(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('valid', c_uint8),
        ('value', c_uint16)
    ]
class _PinsIn(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('adc_voltage_reference', c_uint8, 4),
        ('', c_uint8, 4),
        ('pin', _PinIn*KONASHI_AIO_COUNT)
    ]


class _Analog(KonashiElementBase._KonashiElementBase):
    def __init__(self, konashi) -> None:
        super().__init__(konashi)
        self._config = _Config()
        self._output = _PinsOut()
        self._input = _PinsIn()
        self._input_cb = None

    def __str__(self):
        return f'KonashiAnalog'

    def __repr__(self):
        return f'KonashiAnalog()'


    async def _on_connect(self) -> None:
        await self._enable_notify(KONASHI_UUID_ANALOG_CONFIG_GET, self._ntf_cb_config)
        await self._read(KONASHI_UUID_ANALOG_CONFIG_GET)
        await self._enable_notify(KONASHI_UUID_ANALOG_OUTPUT_GET, self._ntf_cb_output)
        await self._read(KONASHI_UUID_ANALOG_OUTPUT_GET)
        await self._enable_notify(KONASHI_UUID_ANALOG_INPUT, self._ntf_cb_input)
        await self._read(KONASHI_UUID_ANALOG_INPUT)
        

    def _ntf_cb_config(self, sender, data):
        logger.debug("Received config data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._config = _Config.from_buffer_copy(data)

    def _ntf_cb_output(self, sender, data):
        logger.debug("Received output data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._output = _PinsOut.from_buffer_copy(data)

    def _ntf_cb_input(self, sender, data):
        logger.debug("Received input data: {}".format("".join("{:02x}".format(x) for x in data)))
        _new_input = _PinsIn.from_buffer_copy(data)
        for i in range(KONASHI_AIO_COUNT):
            if _new_input.pin[i].valid:
                if _new_input.pin[i].value != self._input.pin[i].value:
                    if self._input_cb is not None:
                        self._input_cb(i, _new_input.pin[i].value)
        self._input = _new_input


    def _calc_voltage_for_value(self, value: int) -> float:
        max_ref = None
        if self._config.analog.adc_voltage_reference == AdcRef.DISABLE:
            return None
        elif self._config.analog.adc_voltage_reference == AdcRef.REF_1V25:
            max_ref = 1.25
        elif self._config.analog.adc_voltage_reference == AdcRef.REF_2V5:
            max_ref = 2.5
        elif self._config.analog.adc_voltage_reference == AdcRef.REF_VDD:
            max_ref = 3.3
        else:
            return None
        return value*max_ref/65535

    async def config_adc_period(self, period: float) -> None:
        """
        Configure the ADC update period.
        
        Parameters
        ----------
        period : float
            The read period is seconds (valid range: [0.1,25.6])

        Raises
        ------
        ValueError
            If the period value is out of range.
        """
        if period < 0.1 or period > 25.6:
            raise ValueError("Period should be in range [0.1,25.6] seconds")
        val = round(period*10)-1  # period = 100 * (val+1) in ms
        b = bytearray([KONASHI_CFG_CMD_ANALOG, 0xF0, int(val)&0xFF])
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def config_adc_ref(self, ref: AdcRef) -> None:
        """Configure the ADC voltage reference."""
        b = bytearray([KONASHI_CFG_CMD_ANALOG, 0xE0|(ref&0x0F)])
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def config_vdac_ref(self, ref: VdacRef) -> None:
        """Configure the VDAC voltage reference."""
        b = bytearray([KONASHI_CFG_CMD_ANALOG, 0xD0|(ref&0x0F)])
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def config_idac_range(self, range: IdacRange) -> None:
        """Configure the IDAC currant range."""
        b = bytearray([KONASHI_CFG_CMD_ANALOG, 0xC0|(range&0x0F)])
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    async def get_analog_config(self) -> AnalogConfig:
        """Returns the current analog configuration."""
        await self._read(KONASHI_UUID_ANALOG_CONFIG_GET)
        return self._config.analog

    async def config_pins(self, configs: Sequence(Tuple[int, PinConfig])) -> None:
        """
        Configure pins.

        Parameters
        ----------
        configs : list of tuples of int, PinConfig
            The list of configurations to set. For each tuple:
            int: pin bitmask. A bitmask of the pins to apply this control to (range 0x00 to 0x07).
            PinConfig: config. The configuration for the pins specified in the bitmask.
        """
        b = bytearray([KONASHI_CFG_CMD_ANALOG])
        for config in configs:
            for i in range(KONASHI_AIO_COUNT):
                if (config[0]&(1<<i)) > 0:
                    b.extend(bytearray([(i<<4)|(bytes(config[1])[0]&0x0F)]))
        await self._write(KONASHI_UUID_CONFIG_CMD, b)

    def set_input_cb(self, notify_callback: Callable[[int, float], None]) -> None:
        """
        """
        self._input_cb = notify_callback


    async def get_pins_config(self, pin_bitmask: int) -> List[PinConfig]:
        """Returns a list of configurations for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_ANALOG_CONFIG_GET)
        l = []
        for i in range(KONASHI_AIO_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                l.append(self._config.pin[i])
        return l

    async def control_pins(self, controls: Sequence(Tuple[int, PinControl])) -> None:
        """
        Control pins.

        Parameters
        ----------
        controls : list of tuples of int, PinControl
            The list of controls to set. For each tuple:
            int: pin bitmask. A bitmask of the pins to apply this control to (range 0x00 to 0x07).
            PinControl: control. The control for the pins specified in the bitmask.
        """
        b = bytearray([KONASHI_CTL_CMD_ANALOG])
        for control in controls:
            for i in range(KONASHI_AIO_COUNT):
                if (control[0]&(1<<i)) > 0:
                    b.extend(bytearray([i])+bytearray(control[1]))
        await self._write(KONASHI_UUID_CONTROL_CMD, b)

    def calc_control_value_for_voltage(self, voltage: float) -> int:
        """
        Returns a control value for the given voltage.

        Parameters
        ----------
        voltage : float
            The target voltage in V.

        Raises
        ------
        KonashiDisabledError
            If the VDAC is disabled.
        KonashiInvalidError
            If the VDAC configuration is invalid.
        ValueError
            If the target voltage value is not within range for the configuration.
        """
        max_ref = None
        if self._config.analog.vdac_voltage_reference == VdacRef.DISABLE:
            raise KonashiDisabledError("The VDAC is not enabled")
        elif self._config.analog.vdac_voltage_reference == VdacRef.REF_1V25LN or self._config.analog.vdac_voltage_reference == VdacRef.REF_1V25:
            max_ref = 1.25
        elif self._config.analog.vdac_voltage_reference == VdacRef.REF_2V5LN or self._config.analog.vdac_voltage_reference == VdacRef.REF_2V5:
            max_ref = 2.5
        elif self._config.analog.vdac_voltage_reference == VdacRef.REF_VDD:
            max_ref = 3.3
        else:
            raise KonashiInvalidError("The VDAC configuration is not valid")
        if voltage > max_ref:
            raise ValueError(f"The target voltage needs to be in the range [0,{max_ref}]")
        return round(voltage*4095/max_ref)

    def calc_control_value_for_current(self, current: float) -> int:
        """
        Returns a control value for the given current.

        Parameters
        ----------
        current : float
            The target current in uA.

        Raises
        ------
        KonashiDisabledError
            If the IDAC is disabled.
        KonashiInvalidError
            If the IDAC configuration is invalid.
        ValueError
            If the target current value is not within range for the configuration.
        """
        first = None
        last = None
        if self._config.analog.idac_current_step == IdacRange.DISABLE:
            raise KonashiDisabledError("The IDAC is not enabled")
        elif self._config.analog.idac_current_step == IdacRange.RANGE0:
            first = 0.05
            last = 1.6
        elif self._config.analog.idac_current_step == IdacRange.RANGE1:
            first = 1.6
            last = 4.7
        elif self._config.analog.idac_current_step == IdacRange.RANGE2:
            first = 0.5
            last = 16
        elif self._config.analog.idac_current_step == IdacRange.RANGE3:
            first = 2
            last = 64
        else:
            raise KonashiInvalidError("The IDAC configuration is not valid")
        if not first <= current <= last:
            raise ValueError(f"The target current needs to be in the range [{first},{last}]")
        return round((current-first)*31/(last-first))

    async def get_pins_control(self, pin_bitmask: int) -> List[PinControl]:
        """Returns a list of output controls for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_ANALOG_OUTPUT_GET)
        l = []
        for i in range(KONASHI_AIO_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                if not self._output.pin[i].valid:
                    l.append(None)
                else:
                    l.append(self._output.pin[i].control)
        return l

    async def read_pins(self, pin_bitmask: int) -> List[int]:
        """Returns a list of input values converted to V for the pins specified in the bitmask."""
        await self._read(KONASHI_UUID_ANALOG_INPUT)
        l = []
        for i in range(KONASHI_AIO_COUNT):
            if (pin_bitmask&(1<<i)) > 0:
                if not self._input.pin[i].valid:
                    l.append(None)
                else:
                    l.append(self._calc_voltage_for_value(self._input.pin[i].value))
        return l
