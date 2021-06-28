# -*- coding: utf-8 -*-
import logging

from RPi import GPIO

import pibooth
from gpiozero import PWMLED


LOGGER = logging.getLogger(__name__)


class FlashPlugin(object):
    def __init__(self, plugin_manager):
        self._pm = plugin_manager

    @pibooth.hookimpl
    def pibooth_configure(self, cfg):
        """Declare the new configuration options"""
        cfg.add_option(
            'PICTURE', 'flash_brightness', 100, "Brightness of the flash between 0 and 100", "Flash brightness",
            [str(i) for i in range(0, 105, 5)]
        )


    @pibooth.hookimpl
    def pibooth_startup(self, app, cfg):
        """Create the LED instances.

        .. note:: gpiozero is configured as BCM, use a string with "BOARD" to
                   use BOARD pin numbering.
        """
        LOGGER.info("Initializing Flash Plugin")
        self.flash_led = PWMLED(12, frequency=200)
        GPIO.setup(18, GPIO.OUT)
        self.p = GPIO.PWM(18, 200)



    @pibooth.hookimpl
    def state_capture_enter(self, cfg):
        """Ready to take a capture."""
        LOGGER.info("Starting Capture")

        flash_brightness = int(cfg.gettyped('PICTURE', 'flash_brightness'))
        LOGGER.debug(f"Flashing with {flash_brightness} intensity")
        self.p.start(flash_brightness)


    @pibooth.hookimpl
    def state_capture_exit(self, app):
        """A capture has been taken."""
        self.p.stop()
