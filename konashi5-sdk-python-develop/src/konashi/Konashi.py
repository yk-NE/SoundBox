#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import struct
import logging
from ctypes import *
from typing import *
from enum import *

from bleak import *

from .Settings import Settings
from .Io import Io
from .Builtin import Builtin
from .Errors import *


logger = logging.getLogger(__name__)


KONASHI_ADV_SERVICE_UUID = "064d0100-8251-49d9-b6f3-f7ba35e5d0a1"

KONASHI_UUID_BUILTIN = "064d0400-8251-49d9-b6f3-f7ba35e5d0a1"


class Konashi:
    def __init__(self, name: str) -> None:
        self._name = name
        self._ble_dev = None
        self._ble_client = None
        self._settings: Settings = Settings(self)
        self._io: Io = Io(self)
        self._builtin: Builtin = Builtin(self)

    def __str__(self):
        return f'Konashi {self._name} ({"Unknown" if self._ble_dev is None else self._ble_dev.address})'

    def __repr__(self):
        return f'Konashi(name="{self._name}")'

    def __eq__(self, other):
        if self._ble_dev is not None and other._ble_dev is not None:
            return self._ble_dev.address == other._ble_dev.address
        return self._name == other._name

    def __ne__(self, other):
        return not self.__eq__(other)
        

    @staticmethod
    async def find(name: str, timeout: float) -> Konashi:
        """
        Find a konashi device.

        Parameters
        ----------
        name : str
            The konashi device name to search for.
        timeout : float or None
            The timeout for the search in seconds (None will search indefinitely).

        Returns
        -------
        Konashi
            An instance representing the found device.

        Raises
        ------
        NotFoundError
            If the device was not found within the timeout time.
        InvalidDeviceError
            If the device was found but was not detected as a konashi device.
        """
        _konashi = None
        _invalid = False
        _scan_task = None
        _scanner = BleakScanner()
        def _scan_cb(dev, adv):
            nonlocal _konashi
            nonlocal _invalid
            if dev.name == name:
                if KONASHI_ADV_SERVICE_UUID in adv.service_uuids:
                    _konashi = Konashi(name)
                    _konashi._ble_dev = dev
                    logger.debug("Found konashi device")
                else:
                    _invalid = True
                _scanner.register_detection_callback(None)
                if _scan_task:
                    _scan_task.cancel()
        _scanner.register_detection_callback(_scan_cb)
        _timedout = False
        async def _scan_coro(t: float) -> None:
            nonlocal _timedout
            try:
                await _scanner.start()
                if t > 0:
                    await asyncio.sleep(t)
                else:
                    while True:
                        await asyncio.sleep(100)
                _timedout = True
            except asyncio.CancelledError:
                _timedout = False
            finally:
                await _scanner.stop()
        logger.debug("Scan for device {} (timeout={}s)".format(name, timeout))
        _scan_task = asyncio.create_task(_scan_coro(timeout))
        await _scan_task
        if _timedout:
            raise NotFoundError(f'Could not find {name}')
        elif _invalid:
            raise InvalidDeviceError(f'{name} is not a Konashi device')
        else:
            return _konashi

    @staticmethod
    async def search(timeout: float) -> List[Konashi]:
        """
        Scan for konashi devices.

        Parameters
        ----------
        timeout : float or None
            The timeout for the scan in seconds (None will scan indefinitely).

        Returns
        -------
        list of Konashi
            A list of scanned konashi devices.

        Raises
        ------
        ValueError
            If the timeout value is invalid.
        """
        if not timeout > 0.0:
            raise ValueError("Timeout should be longer than 0 seconds")
        _konashi = []
        def _scan_cb(dev, adv):
            nonlocal _konashi
            if KONASHI_ADV_SERVICE_UUID in adv.service_uuids:
                k = Konashi(dev.name)
                k._ble_dev = dev
                if k not in _konashi:
                    logger.debug("Discovered new konashi: {}".format(dev.name))
                    _konashi.append(k)
        _scanner = BleakScanner()
        _scanner.register_detection_callback(_scan_cb)
        logger.debug("Start scanning for konashi")
        await _scanner.start()
        await asyncio.sleep(timeout)
        _scanner.register_detection_callback(None)
        await _scanner.stop()
        logger.debug("Finished scanning for konashi")
        return _konashi

    async def connect(self, timeout: float) -> None:
        """
        Establish the connection with this konashi device.

        Parameters
        ----------
        timeout : float or None
            The timeout for the connection in seconds (None will try indefinitely).

        Raises
        ------
        NotFoundError
            If the device was not connected to within the timeout time.
        InvalidDeviceError
            If the device was not detected as a konashi device.
        KonashiConnectionError
            If the connection was attempted but failed.
        """
        if not timeout > 0.0:
            raise ValueError("Timeout should be longer than 0 seconds")
        if self._ble_dev is None:
            try:
                k = await self.find(self._name, timeout)
                self._ble_dev = k._ble_dev
            except NotFoundError:
                raise
            except InvalidDeviceError:
                raise
        if self._ble_client is None:
            self._ble_client = BleakClient(self._ble_dev.address)
        try:
            logger.debug("Connect to device {}".format(self._name))
            _con = await self._ble_client.connect(timeout=timeout)
        except BleakError as e:
            self._ble_client = None
            raise KonashiConnectionError(f'Error occured during BLE connect: "{str(e)}"')
        if _con:
            await self._settings._on_connect()
            await self._io._on_connect()
            srvcs = await self._ble_client.get_services()
            for s in srvcs:
                if s.uuid == KONASHI_UUID_BUILTIN:
                    await self._builtin._on_connect()

    async def disconnect(self) -> None:
        """Disconnect from this konashi device."""
        if self._ble_client is not None:
            await self._ble_client.disconnect()
            self._ble_client = None

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def io(self) -> Io:
        return self._io

    @property
    def builtin(self) -> Builtin:
        return self._builtin

    @property
    def name(self) -> str:
        return self._name
