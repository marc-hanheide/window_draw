#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from json import dumps,loads
import time
import sys
from threading import Condition
from os import _exit

import config

web.config.debug = False

urls = (
    '/wel/', 'index',
    '/wel/sse', 'SSEServer',
    '/wel/view', 'view',
)

renderer = web.template.render('templates', base="base", globals=globals())

is_running = True


class WindowDrawApp(web.application):
    def run(self, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', config.listen_port))


app = WindowDrawApp(urls, globals())

session = web.session.Session(app,
                              web.session.DiskStore('sessions'),
                              initializer={'count': 0})

web.config.session_parameters['timeout'] = 3600

new_path_cond = Condition()
current_path = dumps({'path': [],
                     'dummy': range(1, 2048),  # data to stop proxy buffering
                      })



### Renderers for actual interface:
class index:
    def GET(self):
        session.count += 1
        session.env = {}
        for (k, v) in web.ctx.env.items():
            if type(v) is str:
                session.env[k] = v
        print session.env
        data = {}
        return renderer.index(data)

    def POST(self):
        global current_path
        i = web.input()
        p = loads(i['path'])
        zoom = float(i['zoom'])
        pixel_ratio = float(i['pixel_ratio'])
        for s in p[1]['segments']:
            s[0] /= (zoom / pixel_ratio)
            s[1] /= (zoom / pixel_ratio)
        new_path_cond.acquire()
        try:
            d = {
                'path': p,
                'dummy': range(1, 2048),  # dummy data to stop proxy buffering
            }
            current_path = dumps(d)
            new_path_cond.notifyAll()
        finally:
            new_path_cond.release()
        return web.ok()


### Renderers for actual interface:
class view:
    def GET(self):
        data = {}
        return renderer.view(data)


class SSEServer:

    def response(self, data):
        response = "data: " + data + "\n\n"
        return response

    def GET(self):
        block = False
        web.header("Content-Type", "text/event-stream")
        web.header('Cache-Control', 'no-cache')
        web.header('Content-length:', 0)
        while is_running:
            new_path_cond.acquire()
            try:
                if block:
                    new_path_cond.wait(timeout=sys.maxint)
                e = current_path
            finally:
                new_path_cond.release()
            block = True
            if e is not None:
                r = self.response(str(e))
            else:
                r = self.response(str(e))
            yield r


def signal_handler(signum, frame):
    _exit(signal.SIGTERM)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
