# A Python-based Robot Operating System (ROS)

This provides a _Robot Operating System_ (ROS) for a Raspberry Pi based robot written in Python 3, whose prototype hardware implementation is the KR01 robot.  Main communication between sensors and motor controller is performed over I²C, using lever switch bumpers, Sharp/Pololu infrared distance sensors as well as a variety of Pimoroni sensors from the Breakout Garden series. 


![The KRO1 Robot](https://service.robots.org.nz/wiki/attach/KR01/KR01-0533-1280x584.jpg)


The KR01 robot uses the PiBorg ThunderBorg motor controller and UltraBorg ultrasonic sensor and servo controller board. 

More information can be found on the New Zealand Personal Robotic Group (NZPRG) Blog at:

* [The KR01 Robot Project](https://robots.org.nz/2019/12/08/kr01/)
* [Facilius Est Multa Facere Quam Diu](https://robots.org.nz/2020/04/24/facilius-est/)
 
and the NZPRG wiki at:

* [KR01 Robot](https://service.robots.org.nz/wiki/Wiki.jsp?page=KR01)


## Features

* written in Python 3
* Behaviour-Based System (BBS)
* subsumption architecture (uses message queue, arbitrator and controller for task prioritisation)
* auto-configures by scanning I²C bus for available devices on startup
* configuration via YAML file
* motor control via PID controller with odometry support using encoders
* complex composite sensors include mini-LIDAR, scanning ultrasonic distance sensor and PIR-based cat scanner
* supports analog and digital IR bumper sensors
* output via 11x7 white matrix LED and 5x5 RGB matrix LED displays
* supports Pimoroni Breakout Garden, Adafruit and other I²C sensors, and can be extended for others
* supports PiBorg ThunderBorg motor controller, UltraBorg servo and ultrasonic controller board


## Status

This project should currently be considered a "**Technology Preview**".

The files that have been copied into the repository are from the initial local project. These function largely as advertised but the overall state of the ROS is not yet complete — there are still some pieces missing that are not quite "ready for prime time."

The project is being exposed publicly so that those interested can follow its progress. At such a time when the ROS is generally useable this status section will be updated accordingly.


## Installation

The ROS requires installation of a number of support libraries. In order to begin you'll need Python3 and pip3, as well as the pigpio library.


## Support & Liability

This project comes with no promise of support or liability. Use at your own risk.


## Further Information

This project is part of the _New Zealand Personal Robotics (NZPRG)_ "Robot Operating System", not to be confused with other "ROS" projects. For more information check out the [NZPRG Blog](https://robots.org.nz/) and [NZPRG Wiki](https://service.robots.org.nz/wiki/).

Please note that the documentation in the code will likely be more current than this README file, so please consult it for the "canonical" information.


## Copyright & License

This software is Copyright 2020 by Murray Altheim, All Rights Reserved.

Distributed under the MIT License, see LICENSE file included with project.

