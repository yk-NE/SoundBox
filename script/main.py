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
from konashi.Io import Gpio as KonashiGpio
from konashi.Io import Analog as KonashiAin
from konashi.Builtin import Presence as KonashiPresence
from konashi.Builtin import AccelGyro as KonashiAccelGyro
from konashi.Builtin import Temperature as KonashiTemperature
from konashi.Builtin import Humidity as KonashiHumidity
from konashi.Builtin import Presence as KonashiPresence
from konashi.Builtin import RGBLed as KonashiRGB
import logging
import asyncio
import argparse

import math

global END
END=False
global Theta
Theta=[0,0,0]
global Presence
Presence=False
global Scale
Scale=[220.0, 246.9, 277.2, 293.7, 329.6 ,370.0, 415.3, 440.0]
global RGB
RGB=[
        [255,0,0],
        [255,128,0],
        [255,255,0],
        [255,255,128],
        [255,255,255],
        [255,128,255],
        [255,0,255],
        [255,0,128],
    ]

async def main(device):
    global END
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
        #await device.settings.system.set_nvm_use(True)
        #await device.settings.system.set_nvm_save_trigger(KonashiSystem.NvmSaveTrigger.AUTO)
        #await device.settings.bluetooth.enable_function(KonashiBluetooth.Function.MESH, True)
        global meshdata
        global RGB
        global Scale
        global d
        global f
        f=220.0
        d=0
        meshdata=[0,0,0,0]

        #function
        def map(x,in_min,in_max,out_min,out_max):
            value=(x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
            if value>out_max:
                value=out_max
            if value<out_min:
                value=out_min
            return value
        def i_to_deg(deg):
            i=0
            range=22.5
            if 157.5-range < deg and deg < 157.5+range:
                i=0
            if 113.5-range < deg and deg < 113.5+range:
                i=1
            if 70.1-range < deg and deg < 70.1+range:
                i=2
            if 25.5-range < deg and deg < 25.5+range:
                i=3
            if -19.5-range < deg and deg < -19.5+range:
                i=4
            if -65.7-range < deg and deg < -65.7+range:
                i=5
            if -111.5-range < deg and deg < -111.5+range:
                i=6
            if -157.5-range < deg and deg < -157.5+range:
                i=7
            return i
        #ジャイロ,加速度
        def accelgyro_cb(accel, gyro):
            global Accel
            global Gyro
            global Theta
            Accel=accel
            Gyro=gyro
            Theta[0]=math.atan2(Accel[0],Accel[1])*(180/math.pi)
            Theta[1]=math.atan2(Accel[2],math.sqrt(Accel[1]**2+Accel[0]**2))*(180/math.pi)
            #logging.info("A {},G {},({}),{}".format(Accel,Gyro,Theta,i_to_deg(Theta[0])))

        def presence_cb(pres):#人感センサー1
            global Presence
            Presence=pres
            print("Presence1:", pres)
        def input_cb(pin, level):
            global meshdata
            if level:
                if pin==5:
                    meshdata[0]=1
                elif pin==0:
                    meshdata[1]=1
                elif pin==7:
                    meshdata[2]=1
                elif pin==6:
                    meshdata[3]=1
            else:
                if pin==5:
                    meshdata[0]=0
                elif pin==0:
                    meshdata[1]=0
                elif pin==7:
                    meshdata[2]=0
                elif pin==6:
                    meshdata[3]=0
            logging.info("Pin {}: {},d= {}".format(pin, level,meshdata))

        #ジャイロ,加速度
        global Accel
        global Gyro
        await device.builtin.accelgyro.set_callback(accelgyro_cb)
        #人感センサ設定
        await device.builtin.presence.set_callback(presence_cb)
        # Input callback function set
        device.io.gpio.set_input_cb(input_cb)
        # GPIO0: enable, input, notify on change, pull-down off, pull-up off, wired function off
        # GPIO1~4: enable, output, pull-down off, pull-up off, wired function off
        await device.io.gpio.config_pins([
            (0b11100001, KonashiGpio.PinConfig(KonashiGpio.PinDirection.INPUT, KonashiGpio.PinPull.NONE, True)),
        ])
        def hpwm_trans_end_cb(pin, duty):
            global Presence
            global Theta
            global d
            if 0 < pin <= 3:
                new_pin = 2
                if -10 > Theta[1] or Theta[1] > 10 or END:
                    new_duty = 0
                    alpha=0
                    for i in range(4):
                        if meshdata[i]:
                            d = i
                            new_duty = 50
                            alpha=255
                else:
                    if Presence:
                        new_duty = 50
                        alpha=255
                    else:
                        new_duty = 0
                        alpha=0
                    d=i_to_deg(Theta[0])
                f=Scale[d]
                asyncio.create_task(device.io.hardpwm.config_pwm(1/f))#音階変更
                asyncio.create_task(device.builtin.rgbled.set(RGB[d][0],RGB[d][1],RGB[d][2],alpha,100))#RGBLED
                asyncio.create_task(device.io.hardpwm.control_pins([(0x1<<new_pin, KonashiHPWM.PinControl(device.io.hardpwm.calc_control_value_for_duty(new_duty), 1000))]))
        # Transition end callback functions set
        device.io.hardpwm.set_transition_end_cb(hpwm_trans_end_cb)
        # HardPWM clock settings: 10ms period
        await device.io.hardpwm.config_pwm(0.01)
        # HardPWM1~3: enable
        await device.io.hardpwm.config_pins([(0b00000010, True)])

        await device.io.hardpwm.control_pins([(0x2, KonashiHPWM.PinControl(device.io.hardpwm.calc_control_value_for_duty(100), 2000))])

        while True:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("Stop loop")
        END=True
        await device.builtin.rgbled.set(RGB[d][0],RGB[d][1],RGB[d][2],0,1)
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