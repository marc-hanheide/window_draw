#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from json import dumps
import time
import sys
from Queue import Queue, Empty

import config

urls = (
    '/', 'index',
    '/sse', 'SSEServer'
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
        event_queue.put(i['path'])
        return web.ok()


class SSEServer:

    def response(self, data):
        response = "data: " + data + "\n\n"
        return response

    def GET(self):
        block = False
        web.header("Content-Type", "text/event-stream")
        web.header('Cache-Control', 'no-cache')
        web.header('Content-length:', 1000)
        while is_running:
            print "await response"
            try:
                e = event_queue.get(block=block)
            except Empty as e:
                e = None
            block = True
            if e is not None:
                r = self.response(str(e))
            else:
                r = self.response('{}')
            yield r


def signal_handler(signum, frame):
    print "stopped."
    sys.exit(0)
    #app.stop()
    #is_running = False


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
