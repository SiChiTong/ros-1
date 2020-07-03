#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot OS project and is released under the "Apache Licence, Version 2.0".
# Please see the LICENSE file included as part of this package.
#
# author:   Murray Altheim
# created:  2020-02-21
# modified: 2020-03-26
#

from colorama import init, Fore, Style
init()

from .devnull import DevNull
from .logger import Level, Logger
from .enums import Orientation
from .event import Event
from .infrared import Infrared
from .lr_infrared import LongRangeInfrared


# ..............................................................................
class NullInfrared():
    def __init__(self, pin, event, queue, level):
        pass
    def enable(self):
        pass
    def disable(self):
        pass
    def close(self):
        pass

# ..............................................................................
class Infrareds():
    '''
        A convenience class that collectively creates, enables and disables the set of infrared sensors. 
        This includes:

          * a port and starboard short range digital (boolean) sensor
          * either a center short range digital sensor or a long range analog sensor, and 
          * port and starboard digital side sensors
    '''

    def __init__(self, config, queue, level):
        '''
            Initialises the Infrared sensors. The pin numbers for each are provided in the configuration.

            Parameters:
               config:  the YAML-based application configuration
               queue:   the message queue to receive messages from this task
               level:   the logging level
        '''
        super().__init__()
        self._log = Logger('infrareds', level)
        if config is None:
            raise ValueError('no configuration provided.')
        _config = config['ros'].get('infrared')
        _port_pin       = _config.get('port_pin')
        _cntr_pin       = _config.get('center_pin')
        _stbd_pin       = _config.get('stbd_pin')
        _port_side_pin  = _config.get('port_side_pin')
        _stbd_side_pin  = _config.get('stbd_side_pin')
        self._use_lr_ir = _config.get('use_long_range') # if True uses LongRangeInfrared for center sensor
        self._queue = queue

        # these auto-start their threads
        self._infrared_port       = Infrared(self._queue, _port_pin, Orientation.PORT, Event.INFRARED_PORT, level)
        if self._use_lr_ir:
            self._infrared_center = LongRangeInfrared(self._queue, 0, level)
        else:
            self._infrared_center = Infrared(self._queue, _cntr_pin, Orientation.CENTER, Event.INFRARED_CENTER, level)
        self._infrared_stbd       = Infrared(self._queue, _stbd_pin, Orientation.STBD, Event.INFRARED_STBD, level)

        self._infrared_port_side  = Infrared(self._queue, _port_side_pin, Orientation.PORT_SIDE, Event.INFRARED_PORT_SIDE, level)
        self._infrared_stbd_side  = Infrared(self._queue, _stbd_side_pin, Orientation.STBD_SIDE, Event.INFRARED_STBD_SIDE, level)

        if self._use_lr_ir:
            self._log.info('infrared pins: port={:d}; center=[LR_IR]; starboard={:d}; port side={:d}; starboard side={:d}'.format(\
                    _port_pin, _stbd_pin, _port_side_pin, _stbd_side_pin)) 
        else:
            self._log.info('infrared pins: port={:d}; center={:d}; starboard={:d}; port side={:d}; starboard side={:d}'.format(\
                    _port_pin, _cntr_pin, _stbd_pin, _port_side_pin, _stbd_side_pin)) 

        self._enabled = False # default
        if self._use_lr_ir:
            self._log.info('initialised infrared sensors with long-range sensor at center.')
        else:
            self._log.info('initialised infrared sensors.')


    # ..........................................................................
    def enable(self):
        self._log.info('infrared sensors enabled.')
        self._infrared_port.enable()
        self._infrared_center.enable()
        self._infrared_stbd.enable()
        self._infrared_port_side.enable()
        self._infrared_stbd_side.enable()
        self._enabled = True


    # ..........................................................................
    def disable(self):
        self._log.info('infrared sensors disabled.')
        self._infrared_port.disable()
        self._infrared_center.disable()
        self._infrared_stbd.disable()
        self._infrared_port_side.disable()
        self._infrared_stbd_side.disable()
        self._enabled = False


    # ......................................................
    def set_long_range_scan(self, enabled):
        '''
            Enable or disable the long range scan. Disabling it is necessary
            in order to continue past the long range threshold.
        '''
        if self._use_lr_ir:
            self._log.info('setting long-range infrared scanning to {}.'.format(enabled))
            self._infrared_center.set_long_range_scan(enabled)


    # ......................................................
    def get_short_range_hits(self):
        '''
            Returns the number of short range hits on the center long-range sensor. 
            This counter is cleared continuously.
            Returns zero if we're not using the long range sensor.
        '''
        if self._use_lr_ir:
            return self._infrared_center.get_short_range_hits()
        else:
            return 0


    # ......................................................
    def get_long_range_hits(self):
        '''
            Returns the number of long range hits on the center long-range sensor. 
            This counter is cleared continuously.
            Returns zero if we're not using the long range sensor.
        '''
        if self._use_lr_ir:
            return self._infrared_center.get_long_range_hits()
        else:
            return 0


    # ......................................................
    def close(self):
        self._log.info('infrared sensors closed.')
        self._enabled = False
        self._infrared_port.close()
        self._infrared_center.close()
        self._infrared_stbd.close()
        self._infrared_port_side.close()
        self._infrared_stbd_side.close()

#EOF
