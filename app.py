#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from json import dumps,loads
import time
import sys
from os import _exit
from Queue import Queue, Empty

import config

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


event_queue = Queue()


### Renderers for actual interface:
class index:
    def GET(self):
        data = {}
        return renderer.index(data)

    def POST(self):
        i = web.input()
        p = loads(i['path'])
        zoom = float(i['zoom'])
        pixel_ratio = float(i['pixel_ratio'])
        for s in p[1]['segments']:
            s[0] /= (zoom / pixel_ratio)
            s[1] /= (zoom / pixel_ratio)
        new_path = dumps(p)
        event_queue.put(new_path)
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
            print "await response"
            try:
                e = event_queue.get(block=block, timeout=sys.maxint)
            except Empty as e:
                e = None
            block = True
            if e is not None:
                r = self.response(str(e))
            else:
                r = self.response('')
            yield r


def signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)
    #sys.exit(0)
    #app.stop()
    #is_running = False


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
