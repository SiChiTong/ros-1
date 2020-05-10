#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot OS project and is released under the "Apache Licence, Version 2.0".
# Please see the LICENSE file included as part of this package.
#
# author:   altheim
# created:  2020-03-31
# modified: 2020-03-31

# Import library functions we need
import time
from colorama import init, Fore, Style
init()

try:
    import numpy
except ImportError:
    exit("This script requires the numpy module\nInstall with: sudo pip3 install numpy")

from lib.tof import TimeOfFlight, Range
from lib.servo import Servo
from lib.logger import Logger, Level
from lib.player import Sound, Player

# ..............................................................................
class Scanner():

    def __init__(self, config, player, level):
        self._log = Logger('scanner', Level.INFO)
        self._config = config
        if self._config:
            self._log.info('configuration provided.')
            _config = self._config['ros'].get('scanner')
            self._play_sound = _config.get('play_sound')
            self._log.info('enable play sound: {}'.format(self._play_sound))
            self._min_angle = _config.get('min_angle')
            self._max_angle = _config.get('max_angle')
            self._degree_step = _config.get('degree_step')  
            _range_value = _config.get('tof_range')  
            _range = Range.from_str(_range_value)
        else:
            self._log.warning('no configuration provided.')
            self._play_sound = False
            self._log.info('play sound disabled.')
            self._min_angle = -60.0
            self._max_angle =  60.0
            self._degree_step = 3.0
#           _range = Range.PERFORMANCE
#           _range = Range.LONG
#           _range = Range.MEDIUM
            _range = Range.SHORT

        self._log.info('scan range of {} from {:>5.2f} to {:>5.2f} with step of {:>4.1f}°'.format(_range, self._min_angle, self._max_angle, self._degree_step))
        self._player = player
        _servo_number = 1
        self._servo = Servo(self._config, _servo_number, level)
        self._tof = TimeOfFlight(_range, Level.WARN)
        self._error_range = 0.067
        self._enabled = False
        self._closed = False
        self._log.info('ready.')


    # ..........................................................................
    def _in_range(self, p, q):
        return p >= ( q - self._error_range ) and p <= ( q + self._error_range )


    # ..........................................................................
    def scan(self):
        if not self._enabled:
            self._log.warning('cannot scan: disabled.')
            return
        try:
    
            start = time.time()
            _min_mm = 9999.0
            _angle_at_min = 0.0
            _max_mm = 0
            _angle_at_max = 0.0
            if self._play_sound:
                self._player.repeat(Sound.PING, 3, 0.1)

            self._servo.set_position(self._min_angle)
            time.sleep(0.3)
#           wait_count = 0
#           while ( not self._in_range(self._servo.get_position(self._min_angle), self._min_angle) ) and ( wait_count < 20 ):
#               wait_count += 1
#               self._servo.set_position(self._min_angle)
#               self._log.info(Fore.MAGENTA + Style.BRIGHT + 'waiting for match at degrees: {:>5.2f}°: waited: {:d}'.format(self._servo.get_position(-1), wait_count))
#               time.sleep(1.0)
#           time.sleep(0.05)
#           self._log.info(Fore.YELLOW + Style.BRIGHT + 'starting scan from degrees: {:>5.2f}°: waited: {:d}'.format(self._servo.get_position(-1), wait_count))

            for degrees in numpy.arange(self._min_angle, self._max_angle + 0.1, self._degree_step):
                self._servo.set_position(degrees)
                wait_count = 0
                while not self._in_range(self._servo.get_position(degrees), degrees) and wait_count < 10:
                    time.sleep(0.0025)
                    wait_count += 1
                self._log.debug(Fore.GREEN + Style.BRIGHT + 'measured degrees: {:>5.2f}°: \ttarget: {:>5.2f}°; waited: {:d}'.format(\
                        self._servo.get_position(degrees), degrees, wait_count))
                mm = self._tof.read_distance()
                self._log.info('distance at {:>5.2f}°: \t{}mm'.format(degrees, mm))
                # capture min and max at angles
                _min_mm = min(_min_mm, mm)
                if mm == _min_mm:
                    _angle_at_min = degrees
                _max_mm = max(_max_mm, mm)
                if mm == _max_mm:
                    _angle_at_max = degrees
#               time.sleep(0.001)

            if self._play_sound:
                self._player.stop()
            time.sleep(0.1)
#           self._log.info('complete.')
            elapsed = time.time() - start
            self._log.info('scan complete: {:>5.2f}sec elapsed.'.format(elapsed))

            self._log.info(Fore.CYAN + Style.BRIGHT + 'mix. distance at {:>5.2f}°:\t{}mm'.format(_angle_at_min, _min_mm))
            self._log.info(Fore.CYAN + Style.BRIGHT + 'max. distance at {:>5.2f}°:\t{}mm'.format(_angle_at_max, _max_mm))
            self._servo.set_position(0.0)
#           self._servo.set_position(_angle_at_max)
#           self.close()
            return [ _angle_at_min, _min_mm, _angle_at_max, _max_mm ]
    
        except KeyboardInterrupt:
            self._log.info('caught Ctrl-C.')
            self.close()
            self._log.info('interrupted: incomplete.')
    

    # ..........................................................................
    def enable(self):
        if self._closed:
            self._log.warning('cannot enable: closed.')
            return
        self._tof.enable()
        self._enabled = True


    # ..........................................................................
    def disable(self):
        self._enabled = False
        self._servo.disable()
        self._tof.disable()


    # ..........................................................................
    def close(self):
        self.disable()
        self._servo.close()
        self._closed = True


#EOF
