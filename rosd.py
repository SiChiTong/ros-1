#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   Robot Operating System Daemon (rosd)
#
# This also uses the rosd.service.

# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot Operating System project and is released under the "Apache Licence,
# Version 2.0". Please see the LICENSE file included as part of this package.
#
# author:   Murray Altheim
# created:  2020-08-01
# modified: 2020-08-01
#
# see: https://dpbl.wordpress.com/2017/02/12/a-tutorial-on-python-daemon/
# ..............................................................................

try:
    import daemon
    from daemon import pidfile
except Exception:
    sys.exit("This script requires the python-daemon module.\nInstall with: sudo pip3 install python-daemon")

import os, signal, sys, time, threading, traceback, itertools
from datetime import datetime
import RPi.GPIO as GPIO
from colorama import init, Fore, Style
init()

from lib.logger import Level, Logger
from lib.config_loader import ConfigLoader
from ros import ROS
from lib.gamepad_demo import GamepadDemo

PIDFILE = '/home/pi/ros/.rosd.pid'

# ..............................................................................

def shutdown(signum, frame):  # signum and frame are mandatory
    sys.exit(0)

# ..............................................................................
class RosDaemon():
    '''
        Monitors a toggle switch connected to a GPIO pin, mirroring its state
        on an LED (likewise connected to a GPIO pin).

        This state is used to enable or disable the ROS. This replaces rather
        than reuses the Status class (as a reliable simplification).
    '''
    def __init__(self, config, gpio, level):
        self._log = Logger("rosd", level)
        self._log.warning('initialising rosd...')
        self._gpio = gpio
        self._gpio.setmode(GPIO.BCM)
        self._gpio.setwarnings(False)
        if config is None:
            raise ValueError('no configuration provided.')
        self._log.info('configuration provided.')
        self._config = config['rosd']
        self._switch_pin  = self._config.get('switch_pin') # default 14
        self._led_pin     = self._config.get('led_pin')    # default 27
        self._application = self._config.get('application') # 'ros' | 'gamepad'
        self._log.info('initialising with switch on pin {} and LED on pin {}.'.format(self._switch_pin, self._led_pin))
        self._gpio.setup(self._switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self._gpio.setup(self._led_pin, GPIO.OUT, initial=GPIO.LOW)
        self._counter = itertools.count()
        self._old_state  = False
        self._ros        = None
        self._gamepad    = None
        self._loop_count = 0
        self._thread_timeout_delay_sec = 1
        _rosd_mask = os.umask(0)
        os.umask(_rosd_mask)
        self._log.info('mask: {}'.format(_rosd_mask))
        self._log.info('uid:  {}'.format(os.getuid()))
        self._log.info('gid:  {}'.format(os.getgid()))
        self._log.info('cwd:  {}'.format(os.getcwd()))
        self._log.info('pid file: {}'.format(PIDFILE))
        self._log.info('rosd ready.')

    # ..........................................................................
    def _get_timestamp(self):
        return datetime.utcfromtimestamp(datetime.utcnow().timestamp()).isoformat()

    # ..........................................................................
    def read_state(self):
        '''
            Reads the state of the toggle switch, sets the LED accordingly,
            then returns the value. This only calls enable() or disable()
            if the value has changed since last reading.
        '''
        self._state = not GPIO.input(self._switch_pin)
        self._loop_count = next(self._counter)
        if self._loop_count % 10 == 0:
            self._log.info('[{}] ros daemon waiting...'.format(self._loop_count))
        if self._state is not self._old_state: # if low
            if self._state:
                self._log.info('enabling from state: {}'.format(self._state))
                self.enable()
            else:
                self._log.info('disabling from state: {}'.format(self._state))
                self.disable()
        self._old_state = self._state
        return self._state

    # ..........................................................................
    def enable(self):
        if self._application == 'ros':
            self._enable_ros()
        elif self._application == 'gamepad':
            self._enable_gamepad()
        else:
            raise Exception('unrecognised application: "{}"'.format(self._application))

    # ..........................................................................
    def disable(self):
        if self._application == 'ros':
            self._disable_ros()
        elif self._application == 'gamepad':
            self._disable_gamepad()
        else:
            raise Exception('unrecognised application: "{}"'.format(self._application))

    def _set_status_led(self, enable):
        if enable:
            self._gpio.output(self._led_pin, True)
        else:
            self._gpio.output(self._led_pin, False)

    # ..........................................................................
    def _enable_ros(self):
        self._log.info('ros state enabled at: {}'.format(self._get_timestamp()))
        if self._ros is None:
            self._log.info('starting ros thread...')
            self._ros = ROS()
            self._ros._log.set_mutex(self._log.get_mutex())
            self._ros.start()
            self._log.info('ros started.')
            time.sleep(1.0)
            if self._ros.has_connected_gamepad():
                self._log.info('gamepad is available and connected.')
            else:
                self._log.warning('no connected gamepad.')
        else:
            self._log.info('enabling ros arbitrator...')
            _arbitrator = self._ros.get_arbitrator()
            _arbitrator.set_suppressed(False)
        self._set_status_led(True)

    # ..........................................................................
    def _disable_ros(self):
        self._log.info('ros state disabled at: {}'.format(self._get_timestamp()))
        if self._ros is not None:
            self._log.info('suppressing ros arbitrator... ')
            _arbitrator = self._ros.get_arbitrator()
            _arbitrator.set_suppressed(True)
            self._log.info('ros arbitrator suppressed.')
        self._set_status_led(False)
        # TODO make it flash instead

    # ..........................................................................
    def _enable_gamepad(self):
        if self._gamepad is None:
            self._log.info('instantiating gamepad...')
            self._gamepad = GamepadDemo(Level.INFO)
        self._gamepad.enable()
        self._set_status_led(True)
        self._log.info('gamepad enabled at: {}'.format(self._get_timestamp()))

    # ..........................................................................
    def _disable_gamepad(self):
        if self._gamepad is not None:
            self._gamepad.disable()
        self._set_status_led(False)
        self._log.info('gamepad disabled at: {}'.format(self._get_timestamp()))

    # ..........................................................................
    def close(self):
        self._log.info('closing rosd...')
        if self._ros is not None:
            self._log.info('closing ros...')
            self._ros.close()
            self._log.info('ros closed.')
        else:
            self._log.warning('ros thread was null.')
        self._set_status_led(False)
        self._log.info('rosd closed.')


# main .........................................................................

_daemon = None

def main():
    try:
        _loader = ConfigLoader(Level.INFO)
        filename = 'config.yaml'
        _config = _loader.configure(filename)
        _daemon = RosDaemon(_config, GPIO, Level.INFO)
        while True:
            _daemon.read_state()
            time.sleep(2.0)

    except Exception:
        print('error starting ros daemon: {}'.format(traceback.format_exc()))
    finally:
        if _daemon is not None:
            try:
                _daemon.close()
            except Exception:
                print('error closing ros daemon.')
        print('rosd complete.')

# ..............................................................................

with daemon.DaemonContext(
    stdout=sys.stdout,
    stderr=sys.stderr,
#   chroot_directory=None,
    working_directory='/home/pi/ros',
    umask=0o002,
    pidfile=pidfile.TimeoutPIDLockFile(PIDFILE), ) as context:
#   signal_map={
#       signal.SIGTERM: shutdown,
#       signal.SIGTSTP: shutdown
#   }) as context:
    main()

# call main ....................................................................
#if __name__== "__main__":
#    main()

#EOF
