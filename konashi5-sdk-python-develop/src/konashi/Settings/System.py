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


KONASHI_UUID_SETTINGS_CMD = "064d0101-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_SET_CMD_SYSTEM = 0x01
KONASHI_UUID_SYSTEM_SETTINGS_GET = "064d0102-8251-49d9-b6f3-f7ba35e5d0a1"


class _Command(IntEnum):
    NVM_USE_SET = 1
    NVM_SAVE_TRIGGER_SET = 2
    NVM_SAVE_NOW = 3
    NVM_ERASE_NOW = 4
    FCT_BTN_EMULATE_PRESS = 5
    FCT_BTN_EMULATE_LONG_PRESS = 6
    FCT_BTN_EMULATE_VERY_LONG_PRESS = 7
class NvmUse(IntEnum):
    DISABLED = 0  ## Disable NVM use.
    ENABLED = 1  ## Enable NVM use.
class NvmSaveTrigger(IntEnum):
    AUTO = 0  ## Automatically save to NVM on config change.
    MANUAL = 1  ## Manually save to NVM.
class Settings(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('nvm_use', c_uint8),
        ('nvm_save_trigger', c_uint8)
    ]
    def __str__(self):
        s = "KonashiSettingsSystemSettings("
        if self.nvm_use == NvmUse.ENABLED:
            s += "NVM enabled"
            s += ", NVM save " + ("auto" if self.nvm_save_trigger==NvmSaveTrigger.AUTO else "manual")
        else:
            s += "NVM disabled"
        s += ")"
        return s


class _System(KonashiElementBase._KonashiElementBase):
    def __init__(self, konashi) -> None:
        super().__init__(konashi)
        self._settings: Settings = Settings()

    def __str__(self):
        s = "KonashiSettingsSystem("
        if self.nvm_use == NvmUse.ENABLED:
            s += "NVM enabled"
            s += ", NVM save " + ("auto" if self.nvm_save_trigger==NvmSaveTrigger.AUTO else "manual")
        else:
            s += "NVM disabled"
        s += ")"
        return s

    def __repr__(self):
        return "KonashiSettingsSystem(0x{:02x}, 0x{:02x})".format(self._settings.nvm_use, self._settings.nvm_save_trigger)


    async def _on_connect(self) -> None:
        await self._enable_notify(KONASHI_UUID_SYSTEM_SETTINGS_GET, self._ntf_cb_settings)
        await self._read(KONASHI_UUID_SYSTEM_SETTINGS_GET)


    def _ntf_cb_settings(self, sender, data):
        logger.debug("Received settings data: {}".format("".join("{:02x}".format(x) for x in data)))
        self._settings = Settings.from_buffer_copy(data)


    async def get_settings(self) -> Settings:
        """Get current system settings."""
        await self._read(KONASHI_UUID_SYSTEM_SETTINGS_GET)
        return self._settings

    async def set_nvm_use(self, enable: bool) -> None:
        """Enable or disable NVM usage."""
        b = bytearray([KONASHI_SET_CMD_SYSTEM, _Command.NVM_USE_SET, enable])
        await self._write(KONASHI_UUID_SETTINGS_CMD, b)

    async def set_nvm_save_trigger(self, trigger: NvmSaveTrigger) -> None:
        """Set NVM save trigger."""
        b = bytearray([KONASHI_SET_CMD_SYSTEM, _Command.NVM_SAVE_TRIGGER_SET, trigger])
        await self._write(KONASHI_UUID_SETTINGS_CMD, b)

    async def nvm_save_now(self) -> None:
        """Save all to NVM now."""
        b = bytearray([KONASHI_SET_CMD_SYSTEM, _Command.NVM_SAVE_NOW])
        await self._write(KONASHI_UUID_SETTINGS_CMD, b)

    async def nvm_erase_now(self) -> None:
        """Erase all from NVM now."""
        b = bytearray([KONASHI_SET_CMD_SYSTEM, _Command.NVM_ERASE_NOW])
        await self._write(KONASHI_UUID_SETTINGS_CMD, b)

    async def emul_press(self) -> None:
        """Emulate a function button simple press."""
        b = bytearray([KONASHI_SET_CMD_SYSTEM, _Command.FCT_BTN_EMULATE_PRESS])
        await self._write(KONASHI_UUID_SETTINGS_CMD, b)

    async def emul_long_press(self) -> None:
        """Emulate a function button long press."""
        b = bytearray([KONASHI_SET_CMD_SYSTEM, _Command.FCT_BTN_EMULATE_LONG_PRESS])
        await self._write(KONASHI_UUID_SETTINGS_CMD, b)

    async def emul_very_long_press(self) -> None:
        """Emulate a function button very long press."""
        b = bytearray([KONASHI_SET_CMD_SYSTEM, _Command.FCT_BTN_EMULATE_VERY_LONG_PRESS])
        await self._write(KONASHI_UUID_SETTINGS_CMD, b)
