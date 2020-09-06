#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot Operating System project and is released under the "Apache Licence, 
# Version 2.0". Please see the LICENSE file included as part of this package.
#
# author:   Murray Altheim
# created:  2020-08-23
# modified: 2020-08-31
#
#  Beginnings of a possible replacement for the BNO055 as the source of 
#  heading information for the Compass class, instead using the Adafruit 
#  Precision NXP 9-DOF Breakout Board - FXOS8700 + FXAS21002, see:
#
#      https://www.adafruit.com/product/3463
#
#  This is very preliminary work and currently non-functional.
#

#from __future__ import division, print_function
import sys, time, math
from colorama import init, Fore, Style
init()

from lib.config_loader import ConfigLoader
from lib.logger import Level, Logger
from lib.queue import MessageQueue
from lib.indicator import Indicator
from lib.nxp9dof import NXP9DoF
from lib.rate import Rate

class NXP():

    def __init__(self, nxp, level):
        self._log = Logger('nxp-test', level)
        self._imu  = nxp.get_imu()
        self._fxos = nxp.get_fxos()
        self._fxas = nxp.get_fxas()
        self._log.info('ready.')

    # ..........................................................................
    @staticmethod
    def to_degrees(radians):
        return math.degrees(radians)

    # ..........................................................................
    def imu(self, count):
        header = 67
        self._log.info('-'*header)
        self._log.info("| {:17} | {:20} | {:20} |".format("Accels [g's]", " Magnet [uT]", "Gyros [dps]"))
        self._log.info('-'*header)
        for _ in range(count):
            a, m, g = self._imu.get()
            self._log.info('| {:>5.2f} {:>5.2f} {:>5.2f} | {:>6.1f} {:>6.1f} {:>6.1f} | {:>6.1f} {:>6.1f} {:>6.1f} |'.format(
                a[0], a[1], a[2],
                m[0], m[1], m[2],
                g[0], g[1], g[2])
            )
            time.sleep(0.50)
        self._log.info('-'*header)
        self._log.info(' uT: micro Tesla')
        self._log.info('  g: gravity')
        self._log.info('dps: degrees per second')
        self._log.info('')
    
    # ..........................................................................
    def ahrs(self, count):
        self._log.info('')
        header = 47
        self._log.info('-'*header)
        self._log.info("| {:20} | {:20} |".format("Accels [g's]", "Orient(r,p,h) [deg]"))
        self._log.info('-'*header)
        for _ in range(count):
            a, m, g = self._imu.get()
            m = mag_x, mag_y, mag_z
            r, p, h = self._imu.getOrientation(a, m)
            self._log.info(Fore.GREEN + '| {:>6.1f} {:>6.1f} {:>6.1f} | {:>6.1f} {:>6.1f} {:>6.1f} |'.format(a[0], a[1], a[2], r, p, h) + Style.RESET_ALL)
            time.sleep(0.50)
        self._log.info('-'*header)
        self._log.info('  r: roll')
        self._log.info('  p: pitch')
        self._log.info('  h: heading')
        self._log.info('  g: gravity')
        self._log.info('deg: degree')
        self._log.info('')
    
    # ..........................................................................
    def ahrs2(self, print_info):
        if print_info:
            header = 87 #47
            self._log.info('-'*header)
            self._log.info(Fore.CYAN + "| {:20} | {:20} | {:20} | {:14} |".format("Accels [g's]", "Magnet [uT]", "Gyros [dps]", "Orient [deg]") + Style.RESET_ALL)
#           self._log.info(Fore.MAGENTA + "| {:20} | {:20} |".format("Accels [g's]", "Orient(r,p,h) [deg]") + Style.RESET_ALL)
#           self._log.info(Fore.CYAN    + "| {:20} | {:20} |".format("Magnet [uT]", "Gyros [dps]") + Style.RESET_ALL)
            self._log.info('-'*header)
#       for _ in range(count):
#       a, m, g = self._imu.get()

        accel_x, accel_y, accel_z = self._fxos.accelerometer

        a = accel_x, accel_y, accel_z

#       a = accel_z, accel_x, accel_y
#       a = accel_y, accel_z, accel_x
#       a = accel_x, accel_y, accel_z
#       a = accel_z, accel_y, accel_x
#       a = accel_x, accel_z, accel_y
#       a = accel_y, accel_x, accel_z

        mag_x, mag_y, mag_z       = self._fxos.magnetometer
        m = mag_x, mag_y, mag_z

        gyro_x, gyro_y, gyro_z = self._fxas.gyroscope
        g = gyro_x, gyro_y, gyro_z

        r, p, h = self._imu.getOrientation(a, m)

        _heading = math.degrees(h)

#       _heading_calc = (math.atan2(mag_x, mag_y) * 180.0) / math.pi
        _heading_calc = (math.atan2(mag_z, mag_y) * 180.0) / math.pi
        if _heading_calc < 0:
            _heading_calc += 360

#       _heading_calc = (math.atan2(mag_x, mag_z) * 180.0) / math.pi
#       _heading_calc = (math.atan2(mag_z, mag_x) * 180.0) / math.pi

#       _heading_calc = (math.atan2(mag_z, mag_y) * 180.0) / math.pi
#       _heading_calc = (math.atan2(mag_y, mag_z) * 180.0) / math.pi

        self._log.info(Fore.MAGENTA + '| {:>6.1f} {:>6.1f} {:>6.1f} '.format(a[0], a[1], a[2]) \
                     + Fore.YELLOW  + '| {:>6.1f} {:>6.1f} {:>6.1f} '.format(m[0], m[1], m[2]) \
                     + Fore.CYAN    + '| {:>6.1f} {:>6.1f} {:>6.1f} '.format(g[0], g[1], g[2]) \
                     + Fore.WHITE + '| {:>6.1f}'.format(_heading) + Style.BRIGHT + ' {:>6.1f} '.format(_heading_calc) + Style.NORMAL + ' |' + Style.RESET_ALL)
#       self._log.info(Fore.CYAN    + '| {:>6.1f} {:>6.1f} {:>6.1f} | {:>6.1f} {:>6.1f} {:>6.1f} |'.format(m[0], m[1], m[2], g[0], g[1], g[2]) + Style.RESET_ALL)
        if print_info and False:
            self._log.info('-'*header)
            self._log.info('  r: roll')
            self._log.info('  p: pitch')
            self._log.info('  h: heading')
            self._log.info('  g: gravity')
            self._log.info('deg: degree')
            self._log.info('')
    
    # ..........................................................................
    def heading(self, count):
        self._log.info('')
        for _ in range(count):
            a, m, g = self._imu.get()
            _roll, _pitch, _heading = self._imu.getOrientation(a, m)
            # make easier to read even if completely wrong:
            _roll = _roll * 100.0
            _pitch = _pitch * 100.0
            _heading = _heading * 100.0
            self._log.info(Fore.MAGENTA + 'pitch: {:>6.4f}\troll: {:>6.4f}\theading: {:>6.4f}°'.format(_pitch, _roll, _heading) + Style.RESET_ALL)
            time.sleep(0.50)
    

# ..............................................................................
def main():

    try:

        # read YAML configuration
        _loader = ConfigLoader(Level.INFO)
        filename = 'config.yaml'
        _config = _loader.configure(filename)
        _queue = MessageQueue(Level.INFO)

        _nxp9dof = NXP9DoF(_config, _queue, Level.INFO)
        _nxp = NXP(_nxp9dof, Level.INFO)


#       _nxp.enable()
#       _nxp9dof.enable()

        _rate = Rate(5) # 20Hz

        _nxp.ahrs2(True)
        while True:
#           print(Fore.CYAN + Style.BRIGHT + 'ahrs...' + Style.RESET_ALL)
#           _nxp.heading(20)
            _nxp.ahrs2(False)
#           _nxp.ahrs(10)
#           time.sleep(1.0)
#           print(Fore.CYAN + Style.BRIGHT + 'imu...' + Style.RESET_ALL)
#           _nxp.imu(10)
            _rate.wait()

    except KeyboardInterrupt:
        print(Fore.RED + 'Ctrl-C caught; exiting...' + Style.RESET_ALL)

if __name__== "__main__":
    main()

#EOF
