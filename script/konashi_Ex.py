#!/usr/bin/env python3

try:
    from asyncio.exceptions import CancelledError
except ModuleNotFoundError:
    from asyncio import CancelledError
from konashi import *
import konashi
from konashi.Io import SoftPWM as KonashiSPWM
from konashi.Io import HardPWM as KonashiHPWM
from konashi.Io import Gpio as KonashiGpio
from konashi.Io import Analog as KonashiAin
from konashi.Builtin import Presence as KonashiPresence
from konashi.Builtin import AccelGyro as KonashiAccelGyro
from konashi.Builtin import Temperature as KonashiTemperature
from konashi.Builtin import Humidity as KonashiHumidity
from konashi.Builtin import Presence as KonashiPresence
import logging
import asyncio
import argparse

import math

global Theta
Theta=[0,0,0]
global button
button=False
global Presence
Presence=False
global Scale
Scale=[220.0, 246.9, 277.2, 293.7, 329.6 ,370.0, 415.3, 440.0]

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

        global button
        global Scale
        global d
        global f
        f=220.0
        d=0

        #function
        def map(x,in_min,in_max,out_min,out_max):
            value=(x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
            if value>out_max:
                value=out_max
            if value<out_min:
                value=out_min
            return value
        #ジャイロ,加速度
        def accelgyro_cb(accel, gyro):
            global Accel
            global Gyro
            global Theta
            Accel=accel
            Gyro=gyro
            Theta[0]=math.atan2(Accel[1],Accel[2])*(180/math.pi)
            Theta[1]=math.atan2(Accel[0],math.sqrt(Accel[1]**2+Accel[2]**2))*(180/math.pi)
            logging.info("A {},G {},({}),{}".format(Accel,Gyro,Theta,int(map(Theta[0],-90,90,0,7))))
        #気温、湿度、気圧
        def temperature_cb(temp):
            global Temp
            Temp=temp

        def humidity_cb(hum):
            global Hum
            Hum=hum

        def pressure_cb(press):
            global Press
            Press=press

        def presence_cb(pres):#人感センサー1
            global Presence
            Presence=pres
            print("Presence1:", pres)
        def input_cb(pin, level):
            global d
            global button
            if level:
                button=True
            else:
                button=False
            logging.info("Pin {}: {},d= {}".format(pin, level,d))
            global Temp
            global Hum
            global Press
            logging.info("T {}[c],H {}[%],P {}[hPa],".format(Temp,Hum,Press))

        #def ainput_cb(pin, level):
        #    logging.info("Ain Pin {}: {},d= {}".format(pin, level,d))
        #アナログ入力設定
        #await device.io.analog.config_adc_period(0.1)
        #device.io.analog.set_input_cb(ainput_cb)
        #await device.io.analog.config_pins([
        #    (0xff, KonashiAin.PinConfig(KonashiAin.PinDirection.INPUT,KonashiAin.AdcRef.REF_VDD,True)),
        #])
        #ジャイロ,加速度
        global Accel
        global Gyro
        await device.builtin.accelgyro.set_callback(accelgyro_cb)
        #気温,湿度,気圧
        global Temp
        global Hum
        global Press
        await device.builtin.temperature.set_callback(temperature_cb)
        await device.builtin.humidity.set_callback(humidity_cb)
        await device.builtin.pressure.set_callback(pressure_cb)
        #人感センサ設定
        await device.builtin.presence.set_callback(presence_cb)
        # Input callback function set
        device.io.gpio.set_input_cb(input_cb)
        # GPIO0: enable, input, notify on change, pull-down off, pull-up off, wired function off
        # GPIO1~4: enable, output, pull-down off, pull-up off, wired function off
        await device.io.gpio.config_pins([
            (0x01, KonashiGpio.PinConfig(KonashiGpio.PinDirection.INPUT, KonashiGpio.PinPull.NONE, True)),
        ])
        def hpwm_trans_end_cb(pin, duty):
            global button
            global Presence
            if 0 < pin <= 3:
                logging.info("HardPWM transition end on pin {}: current duty {}%".format(pin, duty))
                new_pin = 2
                #if Presence:
                #    new_duty = 50
                #else:
                #    new_duty = 0
                new_duty = 50
                asyncio.create_task(device.io.hardpwm.control_pins([(0x1<<new_pin, KonashiHPWM.PinControl(device.io.hardpwm.calc_control_value_for_duty(new_duty), 2000))]))
        # Transition end callback functions set
        device.io.hardpwm.set_transition_end_cb(hpwm_trans_end_cb)
        # HardPWM clock settings: 10ms period
        await device.io.hardpwm.config_pwm(0.01)
        # HardPWM1~3: enable
        await device.io.hardpwm.config_pins([(0xe, True)])

        await device.io.hardpwm.control_pins([(0x2, KonashiHPWM.PinControl(device.io.hardpwm.calc_control_value_for_duty(100), 2000))])

        while True:
            f=Scale[d]
            d=int(map(Theta[0],-90,90,0,7))
            #if button:
            #    f=Scale[d]
            #    d+=1
            #    if d>7:
            #        d=0
            await device.io.hardpwm.config_pwm(1/f)#音を鳴らす
            await asyncio.sleep(1)
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