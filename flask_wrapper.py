#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 by Murray Altheim. All rights reserved. This file is part of
# the Robot Operating System project and is released under the "Apache Licence, 
# Version 2.0". Please see the LICENSE file included as part of this package.
#
# author:   Murray Altheim
# created:  2019-12-23
# modified: 2020-04-09
#

import logging, threading
from colorama import init, Fore, Style
init()

from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_restful import Api
#from flask_socketio import SocketIO, emit

from lib.logger import Level, Logger
from lib.event import Event

# RESTful Flask Service  .......................................................

app = Flask(__name__)
api = Api(app)
#socketio = SocketIO(app)

# endpoints ...............................................

@app.route('/')
def home():
    return render_template('index.html')  # render a template

@app.route('/cancel')
def cancel():
    global loop
    if ( loop is True ):
        loop = False
        return jsonify(state='loop cancelled.')
    else:
        return jsonify(state='no active loop.')

@app.route('/speed')
def setSpeed():
    port = request.args.get('port', type=int)
    starboard  = request.args.get('starboard', type=int)
    port_speed = float( port )
    starboard_speed = float( starboard )
    print(Fore.GREEN + 'setSpeed: port: {:>5.2f}, starboard: {:>5.2f}'.format(port_speed, starboard_speed) + Style.RESET_ALL)
    return jsonify([ { 'port_speed': port_speed }, { 'starboard_speed': starboard_speed } ])

@app.route('/event')
def setEvent():
    global g_controller, g_queue
    event_label = request.args.get('id', type=str)
    event = Event.from_str(event_label)
    print( Fore.MAGENTA + Style.BRIGHT + 'ACTION: {}'.format(event.name) + Style.RESET_ALL)
    response = g_queue.respond(event)
    print( Fore.MAGENTA + Style.BRIGHT + 'RESPONSE mimetype: {}; json: {}'.format(response.mimetype, response.json) + Style.RESET_ALL)
    return response
#   return jsonify([ event_label ])

@app.route('/style/<path:path>')
def send_style(path):
    return send_from_directory('style', path)

@app.route('/script/<path:path>')
def send_script(path):
    return send_from_directory('script', path)

#@app.route('/doc')
#def doc_home():
#    return render_template('apidocs/index.html')  # render a template

@app.route('/apidocs/<path:path>')
def send_api_docs(path):
    return send_from_directory('apidocs', path)

# see: https://stackoverflow.com/questions/31264826/start-a-flask-application-in-separate-thread
def shutdown_server(environ):
    if not 'werkzeug.server.shutdown' in environ:
        raise RuntimeError('Not running the development server')
    environ['werkzeug.server.shutdown']()


class FlaskWrapperService(threading.Thread):

    def __init__(self, queue, controller):
        global g_queue, g_controller
        super().__init__()
        g_queue = queue
        g_controller = controller
        threading.Thread.__init__(self)
        self._thread = None
        self._log = Logger('flask.wrapper', Level.INFO)
        self._log.debug('ready')

    # ..........................................................................
    def run(self):
        global app
        self._log.info('starting flask wrapper...')
        # suppress console log messages (this doesn't actually work)
        _flask_log = logging.getLogger('werkzeug')
        _flask_log.setLevel(logging.ERROR)
        _flask_log.disabled = True
#       socketio.run(app)
        self._thread = threading.Thread(target=app.run(host='0.0.0.0', port=8085, debug=False, use_reloader=False))
        self._thread.start()
#       app.run(host='0.0.0.0', port=8085, debug=False, use_reloader=False)
        self._log.info('ended flask thread.')


    # ..........................................................................
    def close(self):
        self._log.info('closing flask.')
        if self._thread != None:
            self._thread.join(timeout=1.0)
            self._log.info('flask app thread joined.')
        self._log.info('closed flask.')


#EOF
