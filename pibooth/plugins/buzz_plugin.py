# -*- coding: utf-8 -*-
import threading
from typing import List, Dict

import pibooth
import logging

import usb.core
import usb.util
import traceback, sys, os
import time

LOGGER = logging.getLogger(__name__)


class Buzz:
    def __init__(self):
        # ID 054c:1000 Sony Corp. Wireless Buzz! Receiver
        self.device = usb.core.find(idVendor=0x054c, idProduct=0x1000)
        self.interface = 0
        self.lights = [0, 0, 0, 0]
        self.buttons = [{'red': 0, 'yellow': 0, 'green': 0, 'orange': 0, 'blue': 0},
                        {'red': 0, 'yellow': 0, 'green': 0, 'orange': 0, 'blue': 0},
                        {'red': 0, 'yellow': 0, 'green': 0, 'orange': 0, 'blue': 0},
                        {'red': 0, 'yellow': 0, 'green': 0, 'orange': 0, 'blue': 0}]
        self.event_handler = None
        self.bits = 0
        if self.device is None:
            LOGGER.error("No device found")
            raise ValueError('Device not found')

        if self.device.is_kernel_driver_active(self.interface) is True:
            self.kerneldriver = True
            self.device.detach_kernel_driver(self.interface)
        else:
            self.kerneldriver = False

        self.device.set_configuration()
        usb.util.claim_interface(self.device, self.interface)
        cfg = self.device.get_active_configuration()
        self.endpoint = cfg[(0, 0)][0]
        self.is_running = False

    # TODO: Should figure out how to re-attach the kernel driver
    # But this doesn't seem to work
    #    def __del__(self):
    # print "release claimed interface"
    # usb.util.release_interface(self.device, self.interface)
    # if self.kerneldriver == True:
    #    print "now attaching the kernel driver again"
    #    dev.attach_kernel_driver(self.interface)

    def set_lights(self, control: int):
        # Sets lights based on binaray
        # 1 = Controller 1
        # 2 = Controller 2
        # 4 = Controller 3
        # 8 = Controller 4

        self.lights[0] = 0xFF if control & 1 else 0x00
        self.lights[1] = 0xFF if control & 2 else 0x00
        self.lights[2] = 0xFF if control & 4 else 0x00
        self.lights[3] = 0xFF if control & 8 else 0x00
        self.device.ctrl_transfer(0x21, 0x09, 0x0200, 0,
                                  [0x0, self.lights[0], self.lights[1], self.lights[2], self.lights[3], 0x0, 0x0])

    def set_light(self, controller: int, state=False) -> None:
        # Sets a light on or off for a single controller
        self.lights[controller] = 0xFF if state else 0x00
        self.device.ctrl_transfer(0x21, 0x09, 0x0200, 0,
                                  [0x0, self.lights[0], self.lights[1], self.lights[2], self.lights[3], 0x0, 0x0])

    def is_light_on(self, controller: int) -> bool:
        return self.lights[controller] == 0xFF

    def read_controller(self, raw=False, timeout=None):
        # Reads the controller
        # Returns the result of Parsecontroller (the changed bit) or raw
        try:
            cfg = self.device.get_active_configuration()
            self.endpoint = cfg[(0, 0)][0]
            data = self.device.read(self.endpoint.bEndpointAddress, self.endpoint.wMaxPacketSize, timeout=timeout)
            parsed = self.parse_controller(data)
        except usb.core.USBTimeoutError:
            data = None
        except usb.core.USBError as e:
            traceback.print_exc(file=sys.stdout)
            LOGGER.exception("Something unexpected happened here, so I log it?")
            # TODO: Should probably raise an error here, as it's something unexpected.
            data = None
        if data is not None and raw is False:
            data = parsed
        return data

    def set_current_state(self, controller, button, state):
        if self.buttons[controller][button] != state:
            self.buttons[controller][button] = state
            self.event_handler(controller, button, state)
        return

    def parse_controller(self, data) -> int:
        # Function to parse the results of readcontroller
        # We break this out incase someone else wants todo something different
        # Returns the changed bits

        # Controller 1
        self.set_current_state(0, "red", True if data[2] & 1 else False)
        self.set_current_state(0, "yellow", True if data[2] & 2 else False)
        self.set_current_state(0, "green", True if data[2] & 4 else False)
        self.set_current_state(0, "orange", True if data[2] & 8 else False)
        self.set_current_state(0, "blue", True if data[2] & 16 else False)

        # Controller 2
        self.set_current_state(1, "red", True if data[2] & 32 else False)
        self.set_current_state(1, "yellow", True if data[2] & 64 else False)
        self.set_current_state(1, "green", True if data[2] & 128 else False)
        self.set_current_state(1, "orange", True if data[3] & 1 else False)
        self.set_current_state(1, "blue", True if data[3] & 2 else False)

        # Controller 3

        self.set_current_state(2, "red", True if data[3] & 4 else False)
        self.set_current_state(2, "yellow", True if data[3] & 8 else False)
        self.set_current_state(2, "green", True if data[3] & 16 else False)
        self.set_current_state(2, "orange", True if data[3] & 32 else False)
        self.set_current_state(2, "blue", True if data[3] & 64 else False)

        # Controller 4
        self.set_current_state(3, "red", True if data[3] & 128 else False)
        self.set_current_state(3, "yellow", True if data[4] & 1 else False)
        self.set_current_state(3, "green", True if data[4] & 2 else False)
        self.set_current_state(3, "orange", True if data[4] & 4 else False)
        self.set_current_state(3, "blue", True if data[4] & 8 else False)

        oldbits = self.bits
        self.bits = (data[4] << 16) + (data[3] << 8) + data[2]

        changed = oldbits | self.bits

        return changed

    def get_buttons(self) ->  List[Dict[str, int]]:
        # Returns current state of buttons
        return self.buttons

    def get_lights(self) -> List[int]:
        # Returns the current state of the lights
        return self.lights

    def run_thread(self):
        LOGGER.info("Thread is started")
        self.is_running = True
        while self.is_running:
            self.read_controller(timeout=500)


class BuzzPlugin(object):
    """Plugin to manage the lights via GPIO.
    """

    def __init__(self, plugin_manager):
        self.effect_running = False
        LOGGER.info("Buzz initializing")
        self._pm = plugin_manager
        self.blink_time = 0.3
        self.buzz = Buzz()
        self.capture_mode = -1
        self.effect_start_time = -1
        self.effect_state = False

    @pibooth.hookimpl
    def pibooth_startup(self, cfg, app):
        LOGGER.info("Buzz starting")
        self.buzz.event_handler = self.event_handler
        x = threading.Thread(target=self.buzz.run_thread, daemon=True)
        x.start()

    @pibooth.hookimpl
    def pibooth_cleanup(self, app):
        LOGGER.info("Buzz cleaning")
        self.buzz.is_running = False

    @pibooth.hookimpl
    def state_wait_do(self, cfg, app, win, events):
        #LOGGER.error("We were successful")
        if self.capture_mode > -1:
            app._machine.set_state("choose")
            app.capture_nbr = app.capture_choices[self.capture_mode]
            self.capture_mode = -1

    @pibooth.hookimpl
    def state_wait_enter(self, cfg, app, win):
        self.capture_mode = -1
        self.buzz.set_lights(3)

    @pibooth.hookimpl
    def state_wait_exit(self, cfg, app, win):
        self.buzz.set_lights(0)

    @pibooth.hookimpl
    def state_preview_enter(self):
        x = threading.Thread(target=self.blink_slow, daemon=True)
        x.start()

    @pibooth.hookimpl
    def state_preview_exit(self):
        self.effect_running = False

    def blink_slow(self):
        self.effect_running = True
        state = True
        while(self.effect_running):
            if state:
                self.buzz.set_lights(3)
            else:
                self.buzz.set_lights(0)
            state = not state
            time.sleep(0.5)

    def event_handler(self, controller, button, state):
        if state:
            LOGGER.info('contr #%s - %s button pressed' % (controller, button))
        else:
            LOGGER.info('contr #%s - %s button released' % (controller, button))

        if button == "red" and controller == 0 and state:
            self.capture_mode = 0

        if button == "red" and controller == 1 and state:
            self.capture_mode = 1
        return

