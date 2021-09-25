#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import struct
from ctypes import *
from typing import *
from enum import *

from bleak import *

from .. import KonashiElementBase
from ..Errors import *


KONASHI_UUID_BUILTIN_RGB_SET = "064d0402-8251-49d9-b6f3-f7ba35e5d0a1"
KONASHI_UUID_BUILTIN_RGB_GET = "064d0403-8251-49d9-b6f3-f7ba35e5d0a1"


class RGBLed(KonashiElementBase._KonashiElementBase):
    def __init__(self, konashi) -> None:
        super().__init__(konashi)
        self._cb = None

    def __str__(self):
        return f'KonashiRGBLed'

    def __repr__(self):
        return f'KonashiRGBLed()'


    async def _on_connect(self) -> None:
        await self._enable_notify(KONASHI_UUID_BUILTIN_RGB_GET, self._ntf_cb)


    def _ntf_cb(self, sender, data):
        d = struct.unpack("<ccccH", data)
        color = (d[0],d[1],d[2],d[3])
        if self._cb is not None:
            self._cb(color)
            self._cb = None


    async def set(self, r: int, g: int, b: int, a: int, duration: int, callback: Callable[[(int,int,int,int)], None] = None) -> None:
        """
        Set the RGB LED color.
        r (int): Red (0~255)
        g (int): Green (0~255)
        b (int): Blue (0~255)
        a (int): Alpha (0~255)
        duration (int): duration to new color in milliseconds (0~65535)
        """
        b = bytearray([r&0xFF, g&0xFF, b&0xFF, a&0xFF, (duration&0x00FF), ((duration&0xFF00)>>8)])
        await self._write(KONASHI_UUID_BUILTIN_RGB_SET, b)
        if callback is not None:
            self._cb = callback
