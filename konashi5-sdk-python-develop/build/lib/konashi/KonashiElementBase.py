#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import struct
import logging
from ctypes import *
from typing import *
from enum import *
import abc

from bleak import *
from bleak.exc import BleakDBusError

from .Errors import *


logger = logging.getLogger(__name__)


class _KonashiElementBase:
    def __init__(self, konashi):
        self._konashi = konashi

    async def _read(self, uuid: str) -> None:
        if self._konashi._ble_client is None:
            raise KonashiConnectionError(f'Connection is not established')
        try:
            logger.debug("Read from {}".format(uuid))
            while True:
                try:
                    await self._konashi._ble_client.read_gatt_char(uuid)
                    break
                except BleakDBusError as e:
                    if e.dbus_error == "org.bluez.Error.InProgress":
                        continue
                    else:
                        raise e
        except BleakError as e:
            raise KonashiError(f'Error occured during BLE read: "{str(e)}"')

    async def _write(self, uuid: str, data: bytes) -> None:
        if self._konashi._ble_client is None:
            raise KonashiConnectionError(f'Connection is not established')
        try:
            logger.debug("Write to {}: {}".format(uuid, "".join("{:02x}".format(x) for x in data)))
            while True:
                try:
                    await self._konashi._ble_client.write_gatt_char(uuid, data)
                    break
                except BleakDBusError as e:
                    if e.dbus_error == "org.bluez.Error.InProgress":
                        continue
                    else:
                        raise e
        except BleakError as e:
            raise KonashiError(f'Error occured during BLE write: "{str(e)}"')

    async def _enable_notify(self, uuid: str, cb: Callable[[int, bytearray], None]) -> None:
        if self._konashi._ble_client is None:
            raise KonashiConnectionError(f'Connection is not established')
        try:
            logger.debug("Enable notify for {}".format(uuid))
            while True:
                try:
                    await self._konashi._ble_client.start_notify(uuid, cb)
                    break
                except BleakDBusError as e:
                    if e.dbus_error == "org.bluez.Error.InProgress":
                        continue
                    else:
                        raise e
        except BleakError as e:
            raise KonashiError(f'Error occured during BLE notify start: "{str(e)}"')

    async def _disable_notify(self, uuid: str) -> None:
        if self._konashi._ble_client is None:
            raise KonashiConnectionError(f'Connection is not established')
        try:
            logger.debug("Disable notify for {}".format(uuid))
            while True:
                try:
                    await self._konashi._ble_client.stop_notify(uuid)
                    break
                except BleakDBusError as e:
                    if e.dbus_error == "org.bluez.Error.InProgress":
                        continue
                    else:
                        raise e
        except BleakError as e:
            raise KonashiError(f'Error occured during BLE notify stop: "{str(e)}"')

    @abc.abstractmethod
    async def _on_connect(self) -> None:
        pass
