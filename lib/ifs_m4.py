#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot OS project and is released under the "Apache Licence, Version 2.0".
# Please see the LICENSE file included as part of this package.
#
# author:   altheim
# created:  2020-01-18
# modified: 2020-02-06
# 
# An Integrated Front Sensor implemented using an Itsy Bitsy M4 Express (an
# Arduino compatible) in an I²C slave configuration.
#

import sys, time, threading, itertools
import datetime as dt
from colorama import init, Fore, Style
init()

try:
    from smbus2 import SMBus
except Exception:
    sys.exit("This script requires the smbus2 module.\nInstall with: sudo pip3 install smbus2")

from lib.pintype import PinType
from lib.logger import Logger, Level
from lib.event import Event
from lib.message import Message

CLEAR_SCREEN = '\n'  # no clear screen

# ..............................................................................
class IntegratedFrontSensor():
    '''
        IntegratedFrontSensor: communicates with the integrated front bumpers 
        and infrared sensors, receiving messages from the I²C Arduino slave,
        sending the messages with its events onto the message bus.
        
        Parameters:
    
           config: the YAML based application configuration
           queue:  the message queue receiving activation notifications
           level:  the logging Level
    
        Usage:
    
           _ifs = IntegratedFrontSensor(_config, _queue, Level.INFO)
           _ifs.enable()
    '''

    # ..........................................................................
    def __init__(self, config, queue, level):
        if config is None:
            raise ValueError('no configuration provided.')
        self._config = config['ros'].get('integrated_front_sensor')
        self._queue = queue
        self._log = Logger("ifs", level)
        self._device_id                  = self._config.get('device_id') # i2c hex address of slave device, must match Arduino's SLAVE_I2C_ADDRESS
        self._channel                    = self._config.get('channel')
        # short distance:
        self._port_side_trigger_distance = self._config.get('port_side_trigger_distance')
        self._port_trigger_distance      = self._config.get('port_trigger_distance')
        self._center_trigger_distance    = self._config.get('center_trigger_distance')
        self._stbd_trigger_distance      = self._config.get('stbd_trigger_distance')
        self._stbd_side_trigger_distance = self._config.get('stbd_side_trigger_distance')
        self._log.info('event thresholds:' \
                + Fore.RED + ' port side={:>5.2f}; port={:>5.2f};'.format(self._port_side_trigger_distance, self._port_trigger_distance) \
                + Fore.BLUE + ' center={:>5.2f};'.format(self._center_trigger_distance) \
                + Fore.GREEN + ' stbd={:>5.2f}; stbd side={:>5.2f}'.format(self._stbd_trigger_distance, self._stbd_side_trigger_distance ))
        self._loop_delay_sec = self._config.get('loop_delay_sec')
        self._log.debug('initialising integrated front sensor...')
        self._counter = itertools.count()
        self._thread  = None
        self._enabled = False
        self._suppressed = False
        self._closing = False
        self._closed  = False
        self._log.info('ready.')

    # ..........................................................................
    def _callback(self, pin, pin_type, value):
        '''
            This is the callback method from the I²C Master, whose events are
            being returned from the Arduino.

            The pin designations for each sensor are hard-coded to match the 
            robot's hardware as well as the Arduino. There's little point in 
            configuring this in the YAML since it's hard-coded in both hardware
            and software. The default pins A1-A5 are defined as IR analog 
            sensors, 9-11 are digital bumper sensors.
        '''
        if not self._enabled or self._suppressed:
            self._log.debug(Fore.BLACK + Style.DIM + 'SUPPRESSED callback: pin {:d}; type: {}; value: {:d}'.format(pin, pin_type, value))
            return
#       self._log.debug(Fore.BLACK + Style.BRIGHT + 'callback: pin {:d}; type: {}; value: {:d}'.format(pin, pin_type, value))
        _message = None
       
        # NOTE: the shorter range infrared triggers preclude the longer range triggers 
        if pin == 1:
            if value > self._port_side_trigger_distance:
                _message = Message(Event.INFRARED_PORT_SIDE)
        elif pin == 2:
            if value > self._port_trigger_distance:
                _message = Message(Event.INFRARED_PORT)
        elif pin == 3:
            if value > self._center_trigger_distance:
                _message = Message(Event.INFRARED_CNTR)
        elif pin == 4:
            if value > self._stbd_trigger_distance:
                _message = Message(Event.INFRARED_STBD)
        elif pin == 5:
            if value > self._stbd_side_trigger_distance:
                _message = Message(Event.INFRARED_STBD_SIDE)
        elif pin == 9:
            if value == 1:
                _message = Message(Event.BUMPER_PORT)
        elif pin == 10:
            if value == 1:
                _message = Message(Event.BUMPER_CNTR)
        elif pin == 11:
            if value == 1:
                _message = Message(Event.BUMPER_STBD)
        if _message is not None:
            _message.set_value(value)
            self._queue.add(_message)

    # ..........................................................................
    def suppress(self, state):
        self._log.info('suppress {}.'.format(state))
        self._suppressed = state

    # ..........................................................................
    def enable(self):
        if not self._closed:
            self._log.info('enabled integrated front sensor.')
            self._enabled = True
            if not self.in_loop():
                self.start_front_sensor_loop()
            else:
                self._log.error('cannot start integrated front sensor.')
        else:
            self._log.warning('cannot enable integrated front sensor: already closed.')

    # ..........................................................................
    def in_loop(self):
        '''
            Returns true if the main loop is active (the thread is alive).
        '''
        return self._thread != None and self._thread.is_alive()

    # ..........................................................................
    def _front_sensor_loop(self):
        self._log.info('starting event loop...\n')

        while self._enabled:
            _count = next(self._counter)
#           print(CLEAR_SCREEN)

            _start_time = dt.datetime.now()

            _port_side_data = self.get_input_for_event_type(Event.INFRARED_PORT_SIDE)
            _port_data      = self.get_input_for_event_type(Event.INFRARED_PORT)
            _cntr_data      = self.get_input_for_event_type(Event.INFRARED_CNTR)
            _stbd_data      = self.get_input_for_event_type(Event.INFRARED_STBD)
            _stbd_side_data = self.get_input_for_event_type(Event.INFRARED_STBD_SIDE)
            _port_bmp_data  = self.get_input_for_event_type(Event.BUMPER_PORT)
            _cntr_bmp_data  = self.get_input_for_event_type(Event.BUMPER_CNTR)
            _stbd_bmp_data  = self.get_input_for_event_type(Event.BUMPER_STBD)

            _delta = dt.datetime.now() - _start_time
            _elapsed_ms = int(_delta.total_seconds() * 1000) 
            # typically 173ms from ItsyBitsy, 85ms from Pimoroni IO Expander

            self._log.info( Fore.WHITE + '[{:04d}] elapsed: {:d}ms'.format(_count, _elapsed_ms))

            # pin 1: analog infrared sensor ................
            self._log.debug('[{:04d}] ANALOG IR ({:d}):       \t'.format(_count, 1) + ( Fore.RED if ( _port_side_data > 100.0 ) else Fore.YELLOW ) \
                    + Style.BRIGHT + '{:d}'.format(_port_side_data) + Style.DIM + '\t(analog value 0-255)')
            self._callback(1, PinType.ANALOG_INPUT, _port_side_data)

            # pin 2: analog infrared sensor ................
            self._log.debug('[{:04d}] ANALOG IR ({:d}):       \t'.format(_count, 2) + ( Fore.RED if ( _port_data > 100.0 ) else Fore.YELLOW ) \
                    + Style.BRIGHT + '{:d}'.format(_port_data) + Style.DIM + '\t(analog value 0-255)')
            self._callback(2, PinType.ANALOG_INPUT, _port_data)

            # pin 3: analog infrared sensor ................
            self._log.debug('[{:04d}] ANALOG IR ({:d}):       \t'.format(_count, 3) + ( Fore.RED if ( _cntr_data > 100.0 ) else Fore.YELLOW ) \
                    + Style.BRIGHT + '{:d}'.format(_cntr_data) + Style.DIM + '\t(analog value 0-255)')
            self._callback(3, PinType.ANALOG_INPUT, _cntr_data)

            # pin 4: analog infrared sensor ................
            self._log.debug('[{:04d}] ANALOG IR ({:d}):       \t'.format(_count, 4) + ( Fore.RED if ( _stbd_data > 100.0 ) else Fore.YELLOW ) \
                    + Style.BRIGHT + '{:d}'.format(_stbd_data) + Style.DIM + '\t(analog value 0-255)')
            self._callback(4, PinType.ANALOG_INPUT, _stbd_data)

            # pin 5: analog infrared sensor ................
            self._log.debug('[{:04d}] ANALOG IR ({:d}):       \t'.format(_count, 5) + ( Fore.RED if ( _stbd_side_data > 100.0 ) else Fore.YELLOW ) \
                    + Style.BRIGHT + '{:d}'.format(_stbd_side_data) + Style.DIM + '\t(analog value 0-255)')
            self._callback(5, PinType.ANALOG_INPUT, _stbd_side_data)

            # pin 9: digital bumper sensor .................
            self._log.debug('[{:04d}] DIGITAL IR ({:d}):      \t'.format(_count, 9) + Fore.GREEN + Style.BRIGHT  + '{:d}'.format(_port_bmp_data) \
                    + Style.DIM + '\t(displays digital pup value 0|1)')
            self._callback(9, PinType.DIGITAL_INPUT_PULLUP, _port_bmp_data)

            # pin 10: digital bumper sensor ................
            self._log.debug('[{:04d}] DIGITAL IR ({:d}):      \t'.format(_count, 10) + Fore.GREEN + Style.BRIGHT  + '{:d}'.format(_cntr_bmp_data) \
                    + Style.DIM + '\t(displays digital pup value 0|1)')
            self._callback(10, PinType.DIGITAL_INPUT_PULLUP, _cntr_bmp_data)

            # pin 11: digital bumper sensor ................
            self._log.debug('[{:04d}] DIGITAL IR ({:d}):      \t'.format(_count, 11) + Fore.GREEN + Style.BRIGHT  + '{:d}'.format(_stbd_bmp_data) \
                    + Style.DIM + '\t(displays digital pup value 0|1)')
            self._callback(11, PinType.DIGITAL_INPUT_PULLUP, _stbd_bmp_data)

            time.sleep(self._loop_delay_sec)

        # we never get here if using 'while True:'
        self._log.info('exited event loop.')

    # ..........................................................................
    def start_front_sensor_loop(self):
        '''
            This is the method to call to actually start the loop.
        '''
        if not self._enabled:
            raise Exception('attempt to start front sensor event loop while disabled.')
        elif not self._closed:
            if self._thread is None:
                enabled = True
                self._thread = threading.Thread(target=IntegratedFrontSensor._front_sensor_loop, args=[self])
                self._thread.start()
                self._log.info('started.')
            else:
                self._log.warning('cannot enable: process already running.')
        else:
            self._log.warning('cannot enable: already closed.')

    # ..............................................................................
    def read_i2c_data(self):
        '''
            Read a byte from the I²C device at the specified handle, returning the value.

            ## Examples:
            int.from_bytes(b'\x00\x01', "big")        # 1
            int.from_bytes(b'\x00\x01', "little")     # 256
        '''
        with SMBus(self._channel) as bus:
            _byte = bus.read_byte_data(self._device_id, 0)
            time.sleep(0.01)
        return _byte

    # ..........................................................................
    def write_i2c_data(self, data):
        '''
            Write a byte to the I²C device at the specified handle.
        '''
        with SMBus(self._channel) as bus:
            bus.write_byte(self._device_id, data)
            time.sleep(0.01)

    # ..........................................................................
    def _get_pin_for_event(self, event):
        '''
            Return the hardwired pin corresponding to the Event type.
        '''
        if event is Event.INFRARED_PORT_SIDE:
            return 1
        elif event is Event.INFRARED_PORT:
            return 2
        elif event is Event.INFRARED_CNTR:
            return 3
        elif event is Event.INFRARED_STBD:
            return 4
        elif event is Event.INFRARED_STBD_SIDE:
            return 5
        elif event is Event.BUMPER_PORT:
            return 9
        elif event is Event.BUMPER_CNTR:
            return 10
        elif event is Event.BUMPER_STBD:
            return 11
        else:
            raise Exception('unexpected event type.')

    # ..........................................................................
    def get_input_for_event_type(self, event):
        '''
            Sends a message to the pin, returning the result as a byte.
        '''
        _pin = self._get_pin_for_event(event)
        self.write_i2c_data(_pin)
        _received_data  = self.read_i2c_data()
        self._log.debug('received response from pin {:d} of {:08b}.'.format(_pin, _received_data))
        return _received_data

    # ..........................................................................
    def disable(self):
        self._log.info('disabled integrated front sensor.')
        self._enabled = False

    # ..........................................................................
    def close(self):
        '''
            Permanently close and disable the integrated front sensor.
        '''
        if self._closing:
            self._log.info('already closing front sensor.')
            return
        if not self._closed:
            self._closing = True
            self._log.info('closing...')
            try:
                self._enabled = False
                if self._thread != None:
                    self._thread.join(timeout=1.0)
                    self._log.debug('front sensor loop thread joined.')
                    self._thread = None
                self._closed = True
#               self._pi.i2c_close(self._handle) # close device
                self._log.info('closed.')
            except Exception as e:
                self._log.error('error closing: {}'.format(e))
        else:
            self._log.debug('already closed.')

#EOF
