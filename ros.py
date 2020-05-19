#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot Operating System project and is released under the "Apache Licence, 
# Version 2.0". Please see the LICENSE file included as part of this package.
#
# author:   Murray Altheim
# created:  2019-12-23
# modified: 2020-03-12
#
#        1         2         3         4         5         6         7         8         9         C
#234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890

# ..............................................................................
import os, sys, signal, time, logging, yaml, threading, traceback
from colorama import init, Fore, Style
init()

#import RPi.GPIO as GPIO
from lib.import_gpio import *

from lib.logger import Level, Logger
from lib.devnull import DevNull
from lib.event import Event
from lib.message import Message
from lib.player import Player
from lib.queue import MessageQueue
from lib.abstract_task import AbstractTask 
from lib.fsm import FiniteStateMachine
from lib.config_loader import ConfigLoader
from lib.configurer import Configurer

# TODO move to feature importer
from lib.lidar import Lidar

from lib.arbitrator import Arbitrator
from lib.controller import Controller

from lib.rgbmatrix import RgbMatrix

# GPIO Setup .....................................
#GPIO.setwarnings(False)
#GPIO.setmode(GPIO.BCM)

led_0_path = '/sys/class/leds/led0/brightness'
led_1_path = '/sys/class/leds/led1/brightness'

_level = Level.INFO

# import RESTful Flask Service
from flask_wrapper import FlaskWrapperService

# ==============================================================================

# ROS ..........................................................................
class ROS(AbstractTask):
    '''
        Extends AbstractTask as a Finite State Machine (FSM) basis of a Robot Operating System 
        or behaviour-based system (BBS), including spawning the various tasks and an arbitrator 
        as separate threads, inter-communicating over a common message queue.
    
        This establishes a RESTful flask service, a message queue, an arbitrator and a 
        controller. 
    
        The message queue receives Event-containing messages, which are passed on to the 
        arbitrator, whose job it is to determine the highest priority action to execute for 
        that task cycle.

        Example usage:

            try:
                _ros = ROS()
                _ros.start()
            except Exception:
                _ros.close()
    '''

    # ..........................................................................
    def __init__(self):
        '''
            This initialises the ROS and calls the YAML configurer.
        '''
        self._queue = MessageQueue(Level.INFO)
        self._mutex = threading.Lock()
        super().__init__("os", self._queue, None, None, self._mutex)
        self._log.info('initialising...')
        self._active        = False
        self._closing       = False
        self._disable_leds  = False
        self._switch        = None
        self._motors        = None
        self._arbitrator    = None
        self._controller    = None
        # read YAML configuration
        _loader = ConfigLoader(Level.INFO)
        filename = 'config.yaml'
        self._config = _loader.configure(filename)
        # import available features
        self._features = []
        _configurer = Configurer(self, Level.INFO)
        _configurer.scan()
        self._log.info('initialised.')


#   # ..........................................................................
#   def configure(self):
#       '''
#           Read and return configuration from the YAML file.
#       '''
#       filename = 'config.yaml'
#       self._log.info('reading from yaml configuration file {}...'.format(filename))
#       _config = yaml.safe_load(open(filename, 'r'))
#       for key, value in _config.items():
#           self._log.debug('config key: {}; value: {}'.format(key, str(value)))
#       self._log.info('configuration read.')
#       return _config


    # ..........................................................................
    def get_message_queue(self):
        return self._queue


    # ..........................................................................
    def get_controller(self):
        return self._controller


    # ..........................................................................
    def get_configuration(self):
        return self._config


    # ..........................................................................
    def get_property(self, section, property_name):
        '''
            Return the value of the named property of the application
            configuration, provided its section and property name.
        '''
        return self._config[section].get(property_name)


    # ..........................................................................
    def set_property(self, section, property_name, property_value):
        '''
            Set the value of the named property of the application
            configuration, provided its section, property name and value.
        '''
        self._log.info(Fore.GREEN + 'set config on section \'{}\' for property key: \'{}\' to value: {}.'.format(section, property_name, property_value))
        if section == 'ros':
            self._config[section].update(property_name = property_value)
        else:
            _ros = self._config['ros']
            _ros[section].update(property_name = property_value)


    # ..........................................................................
    def _set_pi_leds(self, enable):
        '''
            Enables or disables the Raspberry Pi's board LEDs.
        '''
        sudo_name = self.get_property('pi', 'sudo_name')
        led_0_path = self._config['pi'].get('led_0_path')
        led_1_path = self._config['pi'].get('led_1_path')
        if enable:
            self._log.info('re-enabling LEDs...')
            os.system('echo 1 | {} tee {}'.format(sudo_name,led_0_path))
            os.system('echo 1 | {} tee {}'.format(sudo_name,led_1_path))
        else:
            self._log.debug('disabling LEDs...')
            os.system('echo 0 | {} tee {}'.format(sudo_name,led_0_path))
            os.system('echo 0 | {} tee {}'.format(sudo_name,led_1_path))


    # ..........................................................................
    def add_feature(self, feature):
        '''
            Add the feature to the list of features. Features must have 
            an enable() method.
        '''
        self._features.append(feature)
        self._log.info('added feature {}.'.format(feature.name()))


    # ..........................................................................
    def _callback_shutdown(self):
        __enable_self_shutdown = self._config['ros'].get('enable_self_shutdown')
        if _enable_self_shutdown:
            self._log.critical('callback: shutting down os...')
            if self._arbitrator:
                self._arbitrator.disable()
            self.close()
        else:
            self._log.critical('self-shutdown disabled.')


    # ..........................................................................
    def run(self):
        '''
            This first disables the Pi's status LEDs, establishes the
            message queue arbitrator, the controller, enables the set
            of features, then starts the main OS loop.
        '''
        super(AbstractTask, self).run()
        loop_count = 0

        self._disable_leds = self._config['pi'].get('disable_leds')
        if self._disable_leds:
            # disable Pi LEDs since they may be distracting
            self._set_pi_leds(False)

        self._log.info('enabling features...')
        for feature in self._features:
            self._log.info('enabling feature {}...'.format(feature.name()))
            feature.enable()

        self._log.info('configuring sound player...')
        self._player = Player(Level.INFO)

        vl53l1x_available = True # self.get_property('features', 'vl53l1x')
        self._log.critical('vl53l1x_available? {}'.format(vl53l1x_available))
        ultraborg_available = True # self.get_property('features', 'ultraborg')
        self._log.critical('ultraborg available? {}'.format(ultraborg_available))
        if vl53l1x_available and ultraborg_available:
            self._log.critical('starting scanner tool...')
            self._lidar = Lidar(self._config, self._player, Level.INFO)
            self._lidar.enable()
        else:
            self._log.critical('scanner tool does not have necessary dependencies.')
        
        # wait to stabilise features?

        # configure the Controller and Arbitrator
        self._log.info('configuring controller...')
        self._controller = Controller(Level.INFO, self._config, self._switch, self._infrareds, self._motors, self._rgbmatrix, self._lidar, self._callback_shutdown)

        self._log.info('configuring arbitrator...')
        self._arbitrator = Arbitrator(_level, self._queue, self._controller, self._mutex)

        flask_enabled = self._config['flask'].get('enabled')
        if flask_enabled:
            self._log.info('starting flask web server...')
            self.configure_web_server()
        else:
            self._log.info('not starting flask web server (suppressed from command line).')


        self._log.warning('Press Ctrl-C to exit.')

        wait_for_button_press = self._config['ros'].get('wait_for_button_press')
        self._controller.set_standby(wait_for_button_press)

        # begin main loop ..............................

#       self._log.info('starting battery check thread...')
#       self._battery_check.enable()

        self._log.info('starting button thread...')
        self._button.start()

#       self._log.info('enabling bno055 sensor...')
#       self._bno055.enable()

        self._log.info('enabling bumpers...')
        self._bumpers.enable()

#       self._log.info('starting info thread...')
#       self._info.start()

#       self._log.info('starting blinky thread...')
#       self._rgbmatrix.enable(DisplayType.RANDOM)

        # enable arbitrator tasks (normal functioning of robot)

        main_loop_delay_ms = self._config['ros'].get('main_loop_delay_ms')
        self._log.info('begin main os loop with {:d}ms delay.'.format(main_loop_delay_ms))
        _loop_delay_sec = main_loop_delay_ms / 1000
        self._arbitrator.start()
        while self._arbitrator.is_alive():
#           The sensors and the flask service sends messages to the message queue,
#           which forwards those messages on to the arbitrator, which chooses the
#           highest priority message to send on to the controller. So the timing
#           of this loop is inconsequential; it exists solely as a keep-alive.
            time.sleep(_loop_delay_sec)
            # end application loop .........................
    
        if not self._closing:
            self._log.warning('closing following loop...')
            self.close()
        # end main ...................................


    # ..........................................................................
    def configure_web_server(self):
        '''
            Start flask web server.
        '''
        try:
            self._mutex.acquire()
            self._log.info('starting web service...')
            self._flask_wrapper = FlaskWrapperService(self._queue, self._controller)
            self._flask_wrapper.start()
        except KeyboardInterrupt:
            self._log.error('caught Ctrl-C interrupt.')
        finally:
            self._mutex.release()
            time.sleep(1)
            self._log.info(Fore.BLUE + 'web service started.' + Style.RESET_ALL)


    # ..........................................................................
    def emergency_stop(self):
        '''
            Stop immediately, something has hit the top feelers.
        '''
        self._motors.stop()
        self._log.info(Fore.RED + Style.BRIGHT + 'emergency stop: contact on upper feelers.')


    # ..........................................................................
    def send_message(self, message):
        '''
            Send the Message into the MessageQueue.
        '''
        self._queue.add(message)


    # ..........................................................................
    def enable(self):
        super(AbstractTask, self).enable()


    # ..........................................................................
    def disable(self):
        super(AbstractTask, self).disable()


    # ..........................................................................
    def close(self):
        '''
            This sets the ROS back to normal following a session.
        '''
        if self._closing:
            # this also gets called by the arbitrator so we ignore that
            self._log.info('already closing.')
            return
        else:
            self._active = False
            self._closing = True
            self._log.info(Style.BRIGHT + 'closing...')
            self._flask_wrapper.close()
            if self._arbitrator:
                self._arbitrator.disable()
            super().close()
#           self._arbitrator.join(timeout=1.0)

            # close features
            for feature in self._features:
                self._log.info('closing feature {}...'.format(feature.name()))
                feature.close()
            self._log.info('finished closing features.')

            if self._motors:
                self._motors.close()

#           self._info.close()
#           self._rgbmatrix.close()
            if self._switch:
                self._switch.close()
#           super(AbstractTask, self).close()
            if self._arbitrator:
                self._arbitrator.close()

            if self._disable_leds:
                # restore LEDs
                self._set_pi_leds(True)
         
#           GPIO.cleanup()
#           self._log.info('joining main thread...')
#           self.join(timeout=0.5)
            self._log.info('os closed.')
            sys.stderr = DevNull()
            sys.exit(0)


# ==============================================================================

# exception handler ............................................................

def signal_handler(signal, frame):
    print('\nsignal handler    :' + Fore.MAGENTA + Style.BRIGHT + ' INFO  : Ctrl-C caught: exiting...' + Style.RESET_ALL)
    _ros.close()
    print(Fore.MAGENTA + 'exit.' + Style.RESET_ALL)
    sys.stderr = DevNull()
#   sys.exit()
    sys.exit(0)

def print_help():
    '''
        Displays command line help.
    '''
    print('usage: ros.py [-h (help) | -n (do not start web server)]')


# main .........................................................................

_ros = ROS()

def main(argv):

    signal.signal(signal.SIGINT, signal_handler)

    try:

        _ros.start()

#   except KeyboardInterrupt:
#       print(Fore.CYAN + Style.BRIGHT + 'caught Ctrl-C; exiting...')
#       _ros.close()
    except Exception:
        print(Fore.RED + Style.BRIGHT + 'error starting ros: {}'.format(traceback.format_exc()) + Style.RESET_ALL)
        _ros.close()

# call main ....................................................................
if __name__== "__main__":
    main(sys.argv[1:])

# prevent Python script from exiting abruptly
#signal.pause()

#EOF
