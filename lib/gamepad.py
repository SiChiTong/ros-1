#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot Operating System project and is released under the "Apache Licence,
# Version 2.0". Please see the LICENSE file included as part of this package.
#
# author:   Murray Altheim
# created:  2020-08-05
# modified: 2020-08-06
#
# This class interprets the signals arriving from the 8BitDo N30 Pro gamepad,
# a paired Bluetooth device. 
#

import sys, itertools, time, threading, traceback
from enum import Enum
from evdev import InputDevice, categorize, ecodes
from colorama import init, Fore, Style
init()

from lib.config_loader import ConfigLoader
from lib.logger import Logger, Level
from lib.enums import Orientation
from lib.event import Event
from lib.message import Message

'''
    Pairing and using a bluetooth gamepad device:

    1. prior to pairing your gamepad, list the current devices using:

       % ls /dev/input

    2. connect and pair the gamepad, then repeat the previous command. You'll
       notice a new device, e.g., "/dev/input/event6". This is your gamepad.
    3. set the value of gamepad:device_path in the config.yaml file to the 
       value of your gamepad device.
    4. be sure your gamepad is paired prior to starting ros.

    This class based on information found at:

      https://core-electronics.com.au/tutorials/using-usb-and-bluetooth-controllers-with-python.html
'''

# ..............................................................................
class GamepadControl(Enum):
    '''
        An enumeration of the controls available on the 8BitDo N30 Pro Gamepad,
        or any similar/compatible model. The numeric values for 'code' may need
        to be modified for different devices, but the basic functionality of this
        Enum should hold.

        This also includes an Event variable, which provides the mapping between
        a specific gamepad control and its corresponding action.

        The @property annotations make sure the respective variable is read-only.

    control            num  code  id          control descripton     event
    '''
    A_BUTTON        = ( 1,  304,  'cross',    'A (Cross) Button',    Event.SNIFF)
    B_BUTTON        = ( 2,  305,  'circle',   'B (Circle) Button',   Event.STOP)
    X_BUTTON        = ( 3,  307,  'triangle', 'X (Triangle) Button', Event.ROAM)
    Y_BUTTON        = ( 4,  308,  'square',   'Y ((Square) Button',  Event.BRAKE)

    L1_BUTTON       = ( 5,  310,  'l1',       'L1 Start Video',      Event.START_VIDEO)
    L2_BUTTON       = ( 6,  312,  'l2',       'L2 Stop Video',       Event.STOP_VIDEO)
    R1_BUTTON       = ( 8,  311,  'r1',       'R1 Lights On',        Event.LIGHTS_ON)
    R2_BUTTON       = ( 7,  313,  'r2',       'R2 Lights Off',       Event.LIGHTS_OFF)
#   L1_BUTTON       = ( 5,  310,  'l1',       'L1 Button',           Event.BUMPER_PORT)
#   L2_BUTTON       = ( 6,  312,  'l2',       'L2 Button',           Event.BUMPER_CNTR)
#   R2_BUTTON       = ( 7,  313,  'r2',       'R2 Button',           Event.BUMPER_CNTR)
#   R1_BUTTON       = ( 8,  311,  'r1',       'R1 Button',           Event.BUMPER_STBD)

    START_BUTTON    = ( 9,  315,  'start',    'Start Button',        Event.NO_ACTION)
    SELECT_BUTTON   = ( 10, 314,  'select',   'Select Button',       Event.STANDBY)
    HOME_BUTTON     = ( 11, 306,  'home',     'Home Button',         Event.SHUTDOWN)
    DPAD_HORIZONTAL = ( 12, 16,   'dph',      'D-PAD Horizontal',    Event.THETA)
    DPAD_VERTICAL   = ( 13, 17,   'dpv',      'D-PAD Vertical',      Event.FORWARD_VELOCITY)

    L3_VERTICAL     = ( 14, 1,    'l3v',      'L3 Vertical',         Event.PORT_VELOCITY)
    L3_HORIZONTAL   = ( 15, 0,    'l3h',      'L3 Horizontal',       Event.PORT_THETA)
    R3_VERTICAL     = ( 16, 5,    'r3v',      'R3 Vertical',         Event.STBD_VELOCITY)
    R3_HORIZONTAL   = ( 17, 2,    'r3h',      'R3 Horizontal',       Event.STBD_THETA)

    # ignore the first param since it's already set by __new__
    def __init__(self, num, code, name, label, event):
        self._code = code
        self._name = name
        self._label = label
        self._event = event

    @property
    def code(self):
        return self._code

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def event(self):
        return self._event

    # ..........................................................................
    @staticmethod
    def get_by_code(self, code):
        for ctrl in GamepadControl:
            if ctrl.code == code:
#               print(Fore.WHITE + Style.BRIGHT + 'ctrl code: {}'.format(code) + Style.RESET_ALL)
                return ctrl
        return None


# ..............................................................................
class Gamepad():

    _NOT_AVAILABLE_ERROR = 'gamepad device not found (not configured, paired, powered or otherwise available)'

    def __init__(self, config, queue, level):
        '''
        Parameters:

           config:          the YAML-based application configuration
           queue:           the message queue to receive messages from this task
           mutex:           vs godzilla
        '''
        if config is None:
            raise ValueError('no configuration provided.')
        self._log = Logger("gamepad", level)
        self._log.info('initialising...')
        self._config = config['ros'].get('gamepad')
        self._queue = queue
        # config
        self._loop_delay_sec = 0.01
        self._device_path = self._config.get('device_path')
#       self._device_path = '/dev/input/event6'
        self._counter = itertools.count()
        self._closing = False
        self._closed  = False
        self._enabled = False
        self._thread  = None
        self._gamepad = None
        self.connect()

    # ..........................................................................
    def has_connection(self):
        return self._gamepad != None

    # ..........................................................................
    def connect(self):
        self._log.info('connecting...')
        try:
            self._gamepad = InputDevice(self._device_path)
            # display device info
            self._log.info(Fore.GREEN + "gamepad: {}".format(self._gamepad))
            self._log.info('connected.')
        except FileNotFoundError:
            self._log.error(Gamepad._NOT_AVAILABLE_ERROR + ' [1]')
            self._gamepad = None
            sys.exit(1)

    # ..........................................................................
    def enable(self):
        if not self._closed:
            self._log.info('enabled gamepad.')
            if not self.in_loop():
                self._enabled = True
                self._start_gamepad_loop()
            else:
                self._log.error('cannot start gamepad.')
                self._enabled = False
        else:
            self._log.warning('cannot enable gamepad: already closed.')
            self._enabled = False

    # ..........................................................................
    def in_loop(self):
        '''
            Returns true if the main loop is active (the thread is alive).
        '''
        return self._thread != None and self._thread.is_alive()

    # ......................................................
    @staticmethod
    def convert_range(value):
        return ( (value - 127.0) / 255.0 ) * -2.0

    # ..........................................................................
    def _gamepad_loop(self, f_is_enabled):
        self._log.info('starting event loop...\n')
        while f_is_enabled():
            if self._gamepad is None:
                self._log.error(Gamepad._NOT_AVAILABLE_ERROR + ' [2]')
                sys.exit(3)
            _count = next(self._counter)
            # loop and filter by event code and print the mapped label
            for event in self._gamepad.read_loop():
                self._handleEvent(event)
                if not f_is_enabled():
                    break
            time.sleep(self._loop_delay_sec)
            self._log.info(Fore.BLACK + 'loop [{}]'.format(_count))
        self._log.info('exited event loop.')

    # ..........................................................................
    def is_enabled(self):
        return self._enabled

    # ..........................................................................
    def _start_gamepad_loop(self):
        '''
            This is the method to call to actually start the loop.
        '''
        if not self._enabled:
            self._log.error('attempt to start gamepad event loop while disabled.')
        elif self._gamepad is None:
            self._log.error(Gamepad._NOT_AVAILABLE_ERROR + ' [3]')
            sys.exit(3)
        elif not self._closed:
            if self._thread is None:
                enabled = True
                self._thread = threading.Thread(target=Gamepad._gamepad_loop, args=[self, lambda: self.is_enabled(), ])
                self._thread.setDaemon(True)
                self._thread.start()
                self._log.info('started.')
            else:
                self._log.warning('cannot enable: process already running.')
        else:
            self._log.warning('cannot enable: already closed.')

    # ..........................................................................
    def disable(self):
        self._log.info('disabled gamepad.')
        self._enabled = False

    # ..........................................................................
    def close(self):
        '''
            Permanently close and disable the gamepad.
        '''
        self._enabled = False
        if self._closing:
            self._log.info('already closing.')
            return
        if self._closed:
            self._log.debug('already closed.')
            return
        self._closing = True
        self._enabled = False # assumed already done
        self._log.info('closing gamepad...')
#       try:
#           if self._thread is not None:
#               self._thread.join(timeout=1.0)
#               self._log.info('gamepad thread joined.')
#           else:
#               self._log.warning('gamepad thread was already joined!')
#           self._thread = None
#       except Exception as e:
#           self._log.error('error closing gamepad: {}/{}'.format(e, traceback.format_exc()))
        # anything?
        self._closed = True
        self._log.info('closed.')

    # ..........................................................................
    def _handleEvent(self, event):
        '''
            Handles the incoming event by filtering on event type and code.
            There's possibly a more elegant way of doing this but for now this 
            works just fine.
        '''
        _message = None
        _control = None
        if event.type == ecodes.EV_KEY:
            _control = GamepadControl.get_by_code(self, event.code)
            if event.value == 1:
                if event.code == GamepadControl.A_BUTTON.code:
                    self._log.info(Fore.RED + "A Button")
#                   _control = GamepadControl.A_BUTTON
                elif event.code == GamepadControl.B_BUTTON.code:
                    self._log.info(Fore.RED + "B Button")
#                   _control = GamepadControl.B_BUTTON
                elif event.code == GamepadControl.X_BUTTON.code:
                    self._log.info(Fore.RED + "X Button")
#                   _control = GamepadControl.X_BUTTON
                elif event.code == GamepadControl.Y_BUTTON.code:
                    self._log.info(Fore.RED + "Y Button")
#                   _control = GamepadControl.Y_BUTTON
                elif event.code == GamepadControl.L1_BUTTON.code:
                    self._log.info(Fore.YELLOW + "L1 Button")
#                   _control = GamepadControl.L1_BUTTON
                elif event.code == GamepadControl.L2_BUTTON.code:
                    self._log.info(Fore.YELLOW + "L2 Button")
#                   _control = GamepadControl.L2_BUTTON
                elif event.code == GamepadControl.R1_BUTTON.code:
                    self._log.info(Fore.YELLOW + "R1 Button")
#                   _control = GamepadControl.R1_BUTTON
                elif event.code == GamepadControl.R2_BUTTON.code:
                    self._log.info(Fore.YELLOW + "R2 Button")
#                   _control = GamepadControl.R2_BUTTON
                elif event.code == GamepadControl.START_BUTTON.code:
                    self._log.info(Fore.GREEN + "Start Button")
#                   _control = GamepadControl.START_BUTTON
                elif event.code == GamepadControl.SELECT_BUTTON.code:
                    self._log.info(Fore.GREEN + "Select Button")
#                   _control = GamepadControl.SELECT_BUTTON
                elif event.code == GamepadControl.HOME_BUTTON.code:
                    self._log.info(Fore.MAGENTA + "Home Button")
#                   _control = GamepadControl.HOME_BUTTON
                else:
                    self._log.info(Fore.BLACK + "event type: EV_KEY; event: {}; value: {}".format(event.code, event.value))
            else:
    #               self._log.info(Fore.BLACK + Style.DIM + "event type: EV_KEY; value: {}".format(event.value))
                pass
        elif event.type == ecodes.EV_ABS:
            _control = GamepadControl.get_by_code(self, event.code)

            if event.code == GamepadControl.DPAD_HORIZONTAL.code:
                if event.value == 1:
                    self._log.info(Fore.CYAN + Style.BRIGHT + "D-Pad Horizontal(Right) {}".format(event.value))
                elif event.value == -1:
                    self._log.info(Fore.CYAN + Style.NORMAL + "D-Pad Horizontal(Left) {}".format(event.value))
                else:
                    self._log.info(Fore.BLACK + "D-Pad Horizontal(N) {}".format(event.value))
            elif event.code == GamepadControl.DPAD_VERTICAL.code:
                if event.value == -1:
                    self._log.info(Fore.CYAN + Style.NORMAL + "D-Pad Vertical(Up) {}".format(event.value))
                elif event.value == 1:
                    self._log.info(Fore.CYAN + Style.BRIGHT + "D-Pad Vertical(Down) {}".format(event.value))
                else:
                    self._log.info(Fore.BLACK + "D-Pad Vertical(N) {}".format(event.value))

            elif event.code == GamepadControl.L3_VERTICAL.code:
                self._log.debug(Fore.MAGENTA + "L3 Vertical {}".format(event.value))
            elif event.code == GamepadControl.L3_HORIZONTAL.code:
                self._log.debug(Fore.YELLOW + "L3 Horizontal {}".format(event.value))
            elif event.code == GamepadControl.R3_VERTICAL.code:
                self._log.debug(Fore.CYAN + "R3 Vertical {}".format(event.value))
#               _control = GamepadControl.R3_VERTICAL
            elif event.code == GamepadControl.R3_HORIZONTAL.code:
                self._log.debug(Fore.GREEN + "R3 Horizontal {}".format(event.value))
#               _control = GamepadControl.R3_HORIZONTAL
            else:
    #           self._log.info(Fore.BLACK + "type: EV_ABS; event code: {}; value: {}".format(event.code, event.value))
                pass
        else:
    #       self._log.info(Fore.BLACK + Style.DIM + "ZZ. event type: {}; code: {}; value: {}".format(event.type, event.code, event.value))
            pass
        if _control != None:
            _value = event.value
            self._log.debug(Fore.CYAN + Style.BRIGHT + "triggered control: {} with value: {}".format(_control, _value))
            _message = Message(_control.event)
            _message.set_value(_value)
            self._queue.add(_message)


# main .........................................................................

_gamepad = None

def main(argv):

    try:

        _loader  = ConfigLoader(Level.INFO)
        filename = 'config.yaml'
        _config  = _loader.configure(filename)

        _gamepad = Gamepad(_config, _queue, Level.INFO)
        _gamepad.enable()

        while _gamepad.is_enabled():
            time.sleep(1.0)

    except KeyboardInterrupt:
        print(Fore.RED + 'caught Ctrl-C; exiting...' + Style.RESET_ALL)
        if _gamepad:
            _gamepad.disable() 
        sys.exit(0)

    except Exception:
        print(Fore.RED + Style.BRIGHT + 'error processing gamepad events: {}'.format(traceback.format_exc()) + Style.RESET_ALL)
        if _gamepad:
            _gamepad.disable() 
        sys.exit(1)


# call main ....................................................................
if __name__== "__main__":
    main(sys.argv[1:])


# EOF
