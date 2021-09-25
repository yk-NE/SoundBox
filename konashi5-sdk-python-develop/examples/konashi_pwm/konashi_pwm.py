#!/usr/bin/env python3

try:
    from asyncio.exceptions import CancelledError
except ModuleNotFoundError:
    from asyncio import CancelledError
from konashi import *
import konashi
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
        def hpwm_trans_end_cb(pin, duty):
            if 0 < pin <= 3:
                logging.info("HardPWM transition end on pin {}: current duty {}%".format(pin, duty))
                if duty == 100 and pin == 3:
                    new_pin = 3
                    new_duty = 0
                elif duty == 0 and pin == 1:
                    new_pin = 1
                    new_duty = 100
                else:
                    if duty == 100:
                        new_pin = pin+1
                    else:
                        new_pin = pin-1
                    new_duty = duty
                asyncio.create_task(device.io.hardpwm.control_pins([(0x1<<new_pin, KonashiHPWM.PinControl(device.io.hardpwm.calc_control_value_for_duty(new_duty), 2000))]))
        def spwm_trans_end_cb(pin, control_type, control):
            if pin == 0:
                logging.info("SoftPWM transition end on pin {}: current {} {}{}".format(
                    pin,
                    "duty" if control_type == KonashiSPWM.ControlType.DUTY else "period",
                    control/10 if control_type == KonashiSPWM.ControlType.DUTY else control,
                    "%" if control_type == KonashiSPWM.ControlType.DUTY else "ms"
                ))
                new_period = 2000 if control == 0 else 0
                asyncio.create_task(device.io.softpwm.control_pins([(0x1, KonashiSPWM.PinControl(new_period, 6000))]))
        # Transition end callback functions set
        device.io.hardpwm.set_transition_end_cb(hpwm_trans_end_cb)
        device.io.softpwm.set_transition_end_cb(spwm_trans_end_cb)
        # HardPWM clock settings: 10ms period
        await device.io.hardpwm.config_pwm(0.01)
        # HardPWM1~3: enable
        await device.io.hardpwm.config_pins([(0xe, True)])
        # SoftPWM0: period control, fixed duty 50%
        await device.io.softpwm.config_pins([(0x1, KonashiSPWM.PinConfig(KonashiSPWM.ControlType.PERIOD, 500))])

        await device.io.hardpwm.control_pins([(0x2, KonashiHPWM.PinControl(device.io.hardpwm.calc_control_value_for_duty(100), 2000))])
        await device.io.softpwm.control_pins([(0x1, KonashiSPWM.PinControl(0, 6000))])

        while True:
            await asyncio.sleep(60)
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


parser = argparse.ArgumentParser(description="Connect to a konashi device, setup the PWMs and control them.")
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