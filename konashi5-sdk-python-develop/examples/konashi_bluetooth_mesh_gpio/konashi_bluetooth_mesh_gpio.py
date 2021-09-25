#!/usr/bin/env python3

try:
    from asyncio.exceptions import CancelledError
except ModuleNotFoundError:
    from asyncio import CancelledError
from konashi import *
import konashi
from konashi.Settings import System as KonashiSystem
from konashi.Settings import Bluetooth as KonashiBluetooth
from konashi.Io import Gpio as KonashiGpio
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
        # GPIO0: enable, input, no notify on change, pull-down off, pull-up off, wired function off
        # GPIO1~4: enable, output, pull-down off, pull-up off, wired function off
        await device.io.gpio.config_pins([
            (0x01, KonashiGpio.PinConfig(KonashiGpio.PinDirection.INPUT, KonashiGpio.PinPull.NONE, False)),
            (0x1e, KonashiGpio.PinConfig(KonashiGpio.PinDirection.OUTPUT, KonashiGpio.PinPull.NONE, False))
        ])
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("Stop loop")
    except Exception as e:
        logging.error("Exception during main loop: {}".format(e))
        raise e
    finally:
        try:
            if device is not None:
                await device.disconnect()
                logging.info("Disconnected")
        except konashi.Errors.KonashiConnectionError:
            pass
    logging.info("Exit")


parser = argparse.ArgumentParser(description="Connect to a konashi device, enable NVM save and mesh, setup the GPIOs, and exit.")
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