#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot OS project and is released under the "Apache Licence, Version 2.0".
# Please see the LICENSE file included as part of this package.
#
# author:   Murray Altheim
# created:  2020-01-18
# modified: 2020-08-30
#

import time
from colorama import init, Fore, Style
init()

try:
    import numpy
except ImportError:
    exit("This script requires the numpy module\nInstall with: sudo pip install numpy")

from lib.logger import Level, Logger
from lib.devnull import DevNull
from lib.enums import Direction, Orientation, Speed
from lib.slew import SlewRate
from lib.rotary_encoder import Decoder

# ..............................................................................
class Motor():
    '''
        Establishes power control over a motor using an encoder to determine
        the velocity and distance traveled.

        This uses the ros:motors: section of the configuration.
    '''
    def __init__(self, config, tb, pi, orientation, level):
        global TB
        super(Motor, self).__init__()
        if config is None:
            raise ValueError('null configuration argument.')
        if tb is None:
            raise ValueError('null thunderborg argument.')
        self._tb = tb
        TB = tb
        if pi is None:
            raise ValueError('null pi argument.')
        self._pi = pi

        # configuration ....................................
        # get motors configuration section
        cfg = config['ros'].get('motors')
        # in case you wire something up backwards (we need this prior to the logger)
        self._reverse_motor_orientation = cfg.get('reverse_motor_orientation')
        # establish orientation
        if self._reverse_motor_orientation:
            self._orientation = Orientation.STBD if orientation is Orientation.PORT else Orientation.PORT
        else:
            self._orientation = orientation
        # NOW we can create the logger
        self._log = Logger('motor:{}'.format(orientation.label), level)
        self._log.info('initialising {} motor...'.format(orientation))
        self._log.debug('_reverse_motor_orientation: {}'.format(self._reverse_motor_orientation))
        self._reverse_encoder_orientation = cfg.get('reverse_encoder_orientation')
        self._log.debug('_reverse_encoder_orientation: {}'.format(self._reverse_encoder_orientation))
        # GPIO pins configured for A1, B1, A2 and B2
        self._rotary_encoder_a1_port = cfg.get('rotary_encoder_a1_port') # default: 22
        self._log.debug('rotary_encoder_a1_port: {:d}'.format(self._rotary_encoder_a1_port))
        self._rotary_encoder_b1_port = cfg.get('rotary_encoder_b1_port') # default: 17
        self._log.debug('rotary_encoder_b1_port: {:d}'.format(self._rotary_encoder_b1_port))
        self._rotary_encoder_a2_stbd = cfg.get('rotary_encoder_a2_stbd') # default: 27
        self._log.debug('rotary_encoder_a2_stbd: {:d}'.format(self._rotary_encoder_a2_stbd))
        self._rotary_encoder_b2_stbd = cfg.get('rotary_encoder_b2_stbd') # default: 18
        self._log.debug('rotary_encoder_b2_stbd: {:d}'.format(self._rotary_encoder_b2_stbd))
        # how many pulses per encoder measurement?
        self._sample_rate = cfg.get('sample_rate') # default: 10
        self._log.debug('sample_rate: {:d}'.format(self._sample_rate))
        # convert raw velocity to approximate a percentage
        self._velocity_fudge_factor = cfg.get('velocity_fudge_factor') # default: 14.0
        self._log.debug('velocity fudge factor: {:>5.2f}'.format(self._velocity_fudge_factor))
        # limit set on power sent to motors
        self._max_power_limit = cfg.get('max_power_limit') # default: 1.2
        self._log.debug('maximum power limit: {:>5.2f}'.format(self._max_power_limit))
        # acceleration loop delay
        self._accel_loop_delay_sec = cfg.get('accel_loop_delay_sec') # default: 0.10
        self._log.debug('acceleration loop delay: {:>5.2f} sec'.format(self._accel_loop_delay_sec))
        # end configuration ................................

        self._motor_power_limit = 0.99       # power limit to motor
        self._steps = 0                      # step counter
        self._steps_begin = 0                # step count at beginning of velocity measurement
        self._velocity = 0.0                 # current velocity
        self._max_velocity = 0.0             # capture maximum velocity attained
        self._max_power = 0.0                # capture maximum power applied
        self._max_driving_power = 0.0        # capture maximum adjusted power applied
        self._interrupt = False              # used to interrupt loops
        self._stepcount_timestamp = time.time()  # timestamp at beginning of velocity measurement
        self._start_timestamp = time.time()  # timestamp at beginning of velocity measurement

        # configure encoder ................................
        self._log.info('configuring rotary encoders...')
        if self._reverse_encoder_orientation:
            if orientation is Orientation.PORT:
                self.configure_encoder(Orientation.STBD)
            else:
                self.configure_encoder(Orientation.PORT)
        else:
            self.configure_encoder(self._orientation)

        self._log.info('ready.')

    # ..............................................................................
    @property
    def velocity(self):
        return self._velocity

    # ..............................................................................
    @property
    def steps(self):
        return self._steps

    # ..............................................................................
    def reset_steps(self):
        self._steps = 0

    # ..............................................................................
    def set_max_power_ratio(self, max_power_ratio):
        self._max_power_ratio = max_power_ratio

    # ..............................................................................
    def get_max_power_ratio(self):
        return self._max_power_ratio

    # ..............................................................................
    def configure_encoder(self, orientation):
        if self._orientation is Orientation.PORT:
            ROTARY_ENCODER_A = self._rotary_encoder_a1_port
            ROTARY_ENCODER_B = self._rotary_encoder_b1_port
        elif self._orientation is Orientation.STBD:
            ROTARY_ENCODER_A = self._rotary_encoder_a2_stbd
            ROTARY_ENCODER_B = self._rotary_encoder_b2_stbd
        else:
            raise ValueError("unrecognised value for orientation.")
        self._decoder = Decoder(self._pi, ROTARY_ENCODER_A, ROTARY_ENCODER_B, self.callback_step_count)
        self._log.info('configured {} rotary encoder on pin {} and {}.'.format(orientation.name, ROTARY_ENCODER_A, ROTARY_ENCODER_B))

    # ..............................................................................
    def callback_step_count(self, pulse):
        '''
            This callback is used to capture encoder steps.
        '''
        if not self._reverse_encoder_orientation:
            if self._orientation is Orientation.PORT:
                self._steps = self._steps + pulse
            else:
                self._steps = self._steps - pulse
        else:
            if self._orientation is Orientation.PORT:
                self._steps = self._steps - pulse
            else:
                self._steps = self._steps + pulse
        if self._steps % self._sample_rate == 0:
            if self._steps_begin != 0:
                self._velocity = ( (self._steps - self._steps_begin) / (time.time() - self._stepcount_timestamp) / self._velocity_fudge_factor ) # steps / duration
                self._max_velocity = max(self._velocity, self._max_velocity)
                self._stepcount_timestamp = time.time()
            self._stepcount_timestamp = time.time()
            self._steps_begin = self._steps
        self._log.debug(Fore.BLACK + '{}: {:+d} steps'.format(self._orientation.label, self._steps))

    # ..............................................................................
    def cruise():
        '''
            Cruise at the current speed.
        '''
        pass # TODO

    # ..........................................................................
    def enable(self):
        self._log.info('enabled.')
        pass

    # ..........................................................................
    def disable(self):
        self._log.info('disabled.')
        pass

    # ..........................................................................
    def close(self):
        self._log.info('max velocity: {:>5.2f}; max power: {:>5.2f}; max adjusted power: {:>5.2f}.'.format(self._max_velocity, self._max_power, self._max_driving_power))
        self._log.info('closed.')

    # ..........................................................................
    def interrupt(self):
        '''
            Interrupt any loops by setting the _interrupt flag.
        '''
        self._interrupt = True

    # ..........................................................................
    def reset_interrupt(self):
        '''
            Reset the value of the _interrupt flag to False.
        '''
        self._interrupt = False

    # ..........................................................................
    def is_interrupted(self):
        '''
            Return the value of the _interrupt flag.
        '''
        return self._interrupt

    # ..........................................................................
    @staticmethod
    def cancel():
        '''
            Stop both motors immediately. This can be called from either motor.
        '''
        try: TB
        except NameError: TB = None

        if TB:
            TB.SetMotor1(0.0)
            TB.SetMotor2(0.0)
        else:
            print('motor             :' + Fore.YELLOW + ' WARN  : cannot cancel motors: no thunderborg available.' + Style.RESET_ALL)

#   Motor Functions ............................................................

    # ..........................................................................
    def stop(self):
        '''
            Stops the motor immediately.
        '''
        self._log.info('stop.')
        if self._orientation is Orientation.PORT:
            self._tb.SetMotor1(0.0)
        else:
            self._tb.SetMotor2(0.0)
        pass

    # ..........................................................................
    def halt(self):
        '''
            Quickly (but not immediately) stops.
        '''
        self._log.info('halting...')
        # set slew slow, then decelerate to zero
        self.accelerate(0.0, SlewRate.FAST, -1)
        self._log.debug('halted.')

    # ..........................................................................
    def brake(self):
        '''
            Slowly coasts to a stop.
        '''
        self._log.info('braking...')
        # set slew slow, then decelerate to zero
        self.accelerate(0.0, SlewRate.SLOWER, -1)
        self._log.debug('braked.')

    # ..........................................................................
    def ahead(self, speed):
        '''
            Slews the motor to move ahead at speed.
            This is an alias to accelerate(speed).
        '''
        self._log.info('ahead to speed of {}...'.format(speed))
        self.accelerate(speed, SlewRate.NORMAL, -1)
        self._log.debug('ahead complete.')

    # ..........................................................................
    def stepAhead(self, speed, steps):
        '''
            Moves forwards specified number of steps, then stops.
        '''
#       self._log.info('step ahead {} steps to speed of {}...'.format(steps,speed))
        self.accelerate(speed, SlewRate.NORMAL, steps)
#       self._log.debug('step ahead complete.')
        pass

    # ..........................................................................
    def astern(self, speed):
        '''
            Slews the motor to move astern at speed.
            This is an alias to accelerate(-1 * speed).
        '''
        self._log.info('astern at speed of {}...'.format(speed))
        self.accelerate(-1.0 * speed, SlewRate.NORMAL, -1)
        self._log.debug('astern complete.')

    # ..........................................................................
    def stepAstern(self, speed, steps):
        '''
            Moves backwards specified number of steps, then stops.
        '''
        self._log.info('step astern {} steps to speed of {}...'.format(steps,speed))
        self.accelerate(speed, SlewRate.NORMAL, steps)
        self._log.debug('step astern complete.')
        pass

    # ..........................................................................
    def is_in_motion(self):
        '''
            Returns True if the motor is moving.
        '''
        return self.get_current_power_level() > 0.0

    # ..........................................................................
    def accelerate_to_velocity(self, velocity, slew_rate, steps):
        '''
            Slews the motor to the requested velocity.

            If steps is greater than zero it provides a step limit.
        '''
        if steps > 0:
            _step_limit = self._steps + steps
            self._log.critical('>>>>>>  {} steps, limit: {}.'.format(self._steps, _step_limit))
        else:
            _step_limit = -1

        if self._velocity == velocity: # if current velocity equals requested, no need to accelerate
            self._log.info('NO CHANGE: ALREADY AT velocity {:>5.2f}/{:>5.2f}.'.format(self._velocity, velocity))
            return

        # accelerate to target velocity...
        self._accelerate_to_velocity(velocity, slew_rate, _step_limit)
        self._log.info(Fore.YELLOW + 'REACHED TARGET VELOCITY: {:>5.2f}, now maintaining...'.format(velocity))

        self._log.info(Fore.BLUE + Style.BRIGHT + 'accelerated to velocity {:>5.2f} at power: {:>5.2f}. '.format(velocity, self.get_current_power_level()))

    # ..........................................................................
    def set_motor_power(self, power_level):
        '''
            Sets the power level to a number between 0.0 and 1.0, with the
            actual limits set both by the _max_driving_power limit and by
            the _max_power_ratio, which alters the value to match the
            power/motor voltage ratio.
        '''
        # safety checks ..........................
        if power_level > self._motor_power_limit:
            self._log.error(Style.BRIGHT + 'motor power too high: {:>5.2f}; limit: {:>5.2f}'.format(power_level, self._motor_power_limit))
            return
        elif power_level < ( -1.0 * self._motor_power_limit ):
            self._log.error(Style.BRIGHT + 'motor power too low: {:>5.2f}; limit: {:>5.2f}'.format( power_level,( -1.0 * self._motor_power_limit )))
            return
        _current_power = self.get_current_power_level()
#       _current_actual_power = _current_power * ( 1.0 / self._max_power_ratio )
        if abs(_current_power - power_level) > 0.3 and _current_power > 0.0 and power_level < 0:
            self._log.error('cannot perform positive-negative power jump: {:>5.2f} to {:>5.2f}.'.format(_current_power, power_level))
            return
        elif abs(_current_power - power_level) > 0.3 and _current_power < 0.0 and power_level > 0:
            self._log.error('cannot perform negative-positive power jump: {:>5.2f} to {:>5.2f}.'.format(_current_power, power_level))
            return

        # okay, let's go .........................
        _driving_power = float(power_level * self._max_power_ratio)
        self._max_power = max(power_level, self._max_power)
        self._max_driving_power = max(abs(_driving_power), self._max_driving_power)
        self._log.debug(Fore.MAGENTA + Style.BRIGHT + 'power argument: {:>5.2f}'.format(power_level) + Style.NORMAL \
                + '\tcurrent power: {:>5.2f}; driving power: {:>5.2f}.'.format(_current_power, _driving_power))
        if self._orientation is Orientation.PORT:
            self._tb.SetMotor1(_driving_power)
        else:
            self._tb.SetMotor2(_driving_power)

    # ..........................................................................
    @property
    def orientation(self):
        '''
            Returns the orientation of this motor.
        '''
        return self._orientation

    # ..........................................................................
    def is_stopped(self):
        '''
            Returns true if the motor is entirely stopped.
        '''
        return ( self.get_current_power_level() == 0.0 )

    # ................................
    def get_current_power_level(self):
        '''
            Makes a best attempt at getting the power level value from the motors.
        '''
        value = None
        count = 0
        if self._orientation is Orientation.PORT:
            while value == None and count < 20:
                count += 1
                value = self._tb.GetMotor1()
                time.sleep(0.005)
        else:
            while value == None and count < 20:
                count += 1
                value = self._tb.GetMotor2()
                time.sleep(0.005)
        if value == None:
            return 0.0
        else:
            return value

    # ..........................................................................
    def accelerate(self, speed, slew_rate, steps):
        '''
            Slews the motor to the designated speed. -100 <= 0 <= speed <= 100.

            This takes into account the maximum power to be supplied to the
            motor based on the battery and motor voltages.

            If steps > 0 then run until the number of steps has been reached.
        '''
        self._interrupt = False
        _current_power_level = self.get_current_power_level()
        if _current_power_level is None:
            raise RuntimeError('cannot continue: unable to read current power from motor.')
        self._log.info('current power: {:>5.2f} max power ratio: {:>5.2f}...'.format(_current_power_level, self._max_power_ratio))
        _current_power_level = _current_power_level * ( 1.0 / self._max_power_ratio )

        # accelerate to desired speed
        _desired_div_100 = float(speed / 100)
        self._log.info('accelerating from {:>5.2f} to {:>5.2f}...'.format(_current_power_level, _desired_div_100))

        if _current_power_level == _desired_div_100: # no change
            self._log.warning('already at acceleration power of {:>5.2f}, exiting.'.format(_current_power_level) )
            return
        elif _current_power_level < _desired_div_100: # moving ahead
            _slew_rate_ratio = slew_rate.ratio
            overstep = 0.001
        else: # moving astern
            _slew_rate_ratio = -1.0 * slew_rate.ratio
            overstep = -0.001

#       self._log.warning(Style.BRIGHT + 'LOOP from {:>5.2f} to limit: {:>5.2f} with slew: {:>5.2f}'.format(_current_power_level, (_desired_div_100 + overstep), _slew_rate_ratio))

        driving_power_level = 0.0
        for step_power in numpy.arange(_current_power_level, (_desired_div_100 + overstep), _slew_rate_ratio):
            driving_power_level = float( step_power * self._max_power_ratio )
            self.set_motor_power(driving_power_level)
            if self._interrupt:
                break
            time.sleep(self._accel_loop_delay_sec)

        # be sure we're powered off
        if speed == 0.0 and abs(driving_power_level) > 0.00001:
            self._log.warning('non-zero power level: {:7.5f}v; stopping completely...'.format(driving_power_level))
            if self._orientation is Orientation.PORT:
                self._tb.SetMotor1(0.0)
            else:
                self._tb.SetMotor2(0.0)

        self._log.debug('accelerate complete.')

#EOF
