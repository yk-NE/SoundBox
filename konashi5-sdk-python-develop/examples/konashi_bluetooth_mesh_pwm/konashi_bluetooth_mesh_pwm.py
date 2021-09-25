#!/usr/bin/env python3

try:
    from asyncio.exceptions import CancelledError
except ModuleNotFoundError:
    from asyncio import CancelledError
from konashi import *
import konashi
from konashi.Settings import System as KonashiSystem
from konashi.Settings import Bluetooth as KonashiBluetooth
from konashi.Io import SoftPWM as KonashiSPWM
from konashi.Io import HardPWM as KonashiHPWM
import logging
import asyncio
import argparse


async def main(device):
    try:
        if device is None:
            logging.info("Scan for konashi devices for 5 seconds")
            ks = await Konashi.search(5)
            if len(ks) > 0:
                device = ks[0]
                logging.info("Use konashi device: {}".format(device.name))
            else:
                logging.error("Could no find a konashi device")
                return
        try:
            await device.connect(5)
        except Exception as e:
            logging.error("Could not connect to konashi device '{}': {}".format(device.name, e))
            return
        logging.info("Connected to device")
        await device.settings.system.set_nvm_use(True)
        await device.settings.system.set_nvm_save_trigger(KonashiSystem.NvmSaveTrigger.AUTO)
        await device.settings.bluetooth.enable_function(KonashiBluetooth.Function.MESH, True)
        # HardPWM clock settings: 10ms period
        await device.io.hardpwm.config_pwm(0.01)
        # HardPWM1~3: enable
        await device.io.hardpwm.config_pins([(0xe, True)])
        # SoftPWM0: period control, fixed duty 50%
        await device.io.softpwm.config_pins([(0x1, KonashiSPWM.PinConfig(KonashiSPWM.ControlType.PERIOD, 500))])
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("Stop loop")
    finally:
        try:
            if device is not None:
                await device.disconnect()
                logging.info("Disconnected")
        except konashi.Errors.KonashiConnectionError:
            pass
    logging.info("Exit")


parser = argparse.ArgumentParser(description="Connect to a konashi device, enable NVM save and mesh, setup the PWMs, and exit.")
parser.add_argument("--device", "-d", type=Konashi, help="The konashi device name to use. Ommit to scan and use first discovered device.")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
main_task = None
try:
    main_task = loop.create_task(main(args.device))
    loop.run_until_complete(main_task)
except KeyboardInterrupt:
    if main_task is not None:
        main_task.cancel()
        loop.run_until_complete(main_task)
        main_task.exception()
finally:
    loop.close()