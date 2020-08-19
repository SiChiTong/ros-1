#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot OS project and is released under the "Apache Licence, Version 2.0".
# Please see the LICENSE file included as part of this package.
#
#    A collection of enums.
#
# author:   Murray Altheim
# created:  2019-12-23
# modified: 2020-03-26

from enum import Enum

# ..............................................................................
class Orientation(Enum):
    PORT  = ( 1, "port", "port")
    CNTR  = ( 2, "center", "cntr")
    STBD  = ( 3, "starboard", "stbd")
    PORT_SIDE = ( 4, "port-side", "psid") # only used with infrareds
    STBD_SIDE = ( 5, "stbd-side", "ssid") # only used with infrareds

    # ignore the first param since it's already set by __new__
    def __init__(self, num, name, label):
        self._name = name
        self._label = label

    # this makes sure the name is read-only
    @property
    def name(self):
        return self._name

    # this makes sure the label is read-only
    @property
    def label(self):
        return self._label


# ..............................................................................
class Direction(Enum):
    FORWARD = 0
    REVERSE = 1


# ..............................................................................
class Color(Enum):
    WHITE         = (  1, 255.0, 255.0, 255.0)
    LIGHT_GREY    = (  2, 192.0, 192.0, 192.0)
    GREY          = (  3, 128.0, 128.0, 128.0)
    DARK_GREY     = (  4, 64.0, 64.0, 64.0)
    BLACK         = (  5, 0.0, 0.0, 0.0)
    LIGHT_RED     = (  6, 255.0, 128.0, 128.0)
    RED           = (  7, 255.0, 0.0, 0.0)
    DARK_RED      = (  8, 128.0, 0.0, 0.0)
    LIGHT_GREEN   = (  9, 128.0, 255.0, 128.0)
    GREEN         = ( 10, 0.0, 255.0, 0.0)
    DARK_GREEN    = ( 11, 0.0, 128.0, 0.0)
    LIGHT_BLUE    = ( 12, 128.0, 128.0, 255.0)
    BLUE          = ( 13, 0.0, 0.0, 255.0)
    DARK_BLUE     = ( 14, 0.0, 0.0, 128.0)
    LIGHT_CYAN    = ( 15, 128.0, 255.0, 255.0)
    CYAN          = ( 16, 0.0, 255.0, 255.0)
    DARK_CYAN     = ( 17, 0.0, 128.0, 128.0)
    LIGHT_MAGENTA = ( 18, 255.0, 128.0, 255.0)
    MAGENTA       = ( 19, 255.0, 0.0, 255.0)
    DARK_MAGENTA  = ( 20, 128.0, 0.0, 128.0)
    LIGHT_YELLOW  = ( 21, 255.0, 255.0, 128.0)
    PURPLE        = ( 22, 77.0, 26.0, 177.0)
    YELLOW        = ( 23, 255.0, 255.0, 0.0)
    DARK_YELLOW   = ( 24, 128.0, 128.0, 0.0)

    # ignore the first param since it's already set by __new__
    def __init__(self, num, red, green, blue):
        self._red = red
        self._green = green
        self._blue = blue

    @property
    def red(self):
        return self._red

    @property
    def green(self):
        return self._green

    @property
    def blue(self):
        return self._blue


# ..............................................................................
class Speed(Enum): # deprecated
    STOPPED       =  0.0
    DEAD_SLOW     = 20.0
    SLOW          = 30.0
    HALF          = 50.0
    THREE_QUARTER = 75.0
    FULL          = 90.0
    EMERGENCY     = 100.0
    MAXIMUM       = 100.000001


# ..............................................................................
class Velocity(Enum):
    STOP          = ( 1,  0.0 )
    DEAD_SLOW     = ( 2, 20.0 )
    SLOW          = ( 3, 30.0 )
    HALF          = ( 4, 50.0 )
    TWO_THIRDS    = ( 5, 66.7 )
    THREE_QUARTER = ( 6, 75.0 )
    FULL          = ( 7, 90.0 )
    EMERGENCY     = ( 8, 100.0 )
    MAXIMUM       = ( 9, 100.000001 )

    # ignore the first param since it's already set by __new__
    def __init__(self, num, value):
        self._value = value

    @property
    def value(self):
        return self._value

    @staticmethod
    def get_slower_than(velocity):
        '''
            Provided a value between 0-100, return the next lower Velocity.
        '''
        if velocity < Velocity.DEAD_SLOW.value:
            return Velocity.STOP
        elif velocity < Velocity.SLOW.value:
            return Velocity.DEAD_SLOW
        elif velocity < Velocity.HALF.value:
            return Velocity.SLOW
        elif velocity < Velocity.TWO_THIRDS.value:
            return Velocity.HALF
        elif velocity < Velocity.THREE_QUARTER.value:
            return Velocity.TWO_THIRDS
        elif velocity < Velocity.FULL.value:
            return Velocity.THREE_QUARTER
        else:
            return Velocity.FULL


# ..............................................................................
class SlewRate(Enum): #       tested to 50.0 velocity:
    EXTREMELY_SLOW   = ( 0.3, 0.0034, 0.16 ) # 5.1 sec
    VERY_SLOW        = ( 1,   0.01,   0.22 ) # 3.1 sec
    SLOWER           = ( 2.5, 0.03,   0.38 ) # 1.7 sec
    SLOW             = ( 2,   0.05,   0.48 ) # 1.3 sec
    NORMAL           = ( 3,   0.08,   0.58 ) # 1.0 sec
    FAST             = ( 4,   0.20,   0.68 ) # 0.6 sec
    VERY_FAST        = ( 5,   0.4,    0.90 ) # 0.5 sec

    def __new__(cls, *args, **kwds):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    # ignore the first param since it's already set by __new__
    def __init__(self, num, ratio, pid):
        self._ratio = ratio
        self._pid = pid

    # this makes sure the ratio is read-only
    @property
    def ratio(self):
        return self._ratio

    # this makes sure the ratio is read-only
    @property
    def pid(self):
        return self._pid


# ..............................................................................
class Heading(Enum):
    NORTH        = 0
    NORTHWEST    = 1
    WEST         = 2
    SOUTHWEST    = 3
    SOUTH        = 4
    SOUTHEAST    = 5
    EAST         = 6
    NORTHEAST    = 7

    @staticmethod
    def get_heading_from_degrees(degrees):
        '''
            Provided a heading in degrees return an enumerated cardinal direction.
        '''
        if degrees > 337.25 or degrees < 22.5:
            return Heading.NORTH
        elif 292.5 <= degrees <= 337.25:
            return Heading.NORTHWEST
        elif 247.5 <- degrees <= 292.5:
            return Heading.WEST
        elif 202.5 <= degrees <= 247.5:
            return Heading.SOUTHWEST
        elif 157.5 <= degrees <= 202.5:
            return Heading.SOUTH
        elif 112.5 <= degrees <= 157.5:
            return Heading.SOUTHEAST
        elif 67.5 <= degrees <= 112.5:
            return Heading.EAST
        elif 0 <= degrees <= 67.5:
            return Heading.NORTHEAST


# ..............................................................................
class ActionState(Enum):
    INIT             = 1
    STARTED          = 2
    COMPLETED        = 3
    CLOSED           = 4

