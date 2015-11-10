#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from json import dumps
from json import loads
import sys
from threading import Condition
from os import _exit

from twython import Twython, TwythonError

import config


web.config.debug = False


urls = (
    '/wel/', 'index',
    '/wel/tweet', 'tweet',
    '/wel/sse', 'SSEServer',
    '/wel/view', 'view',
)

renderer = web.template.render('templates', base="base", globals=globals())

is_running = True


class Tweeter():

    TWITTER_CONFIG_FILE = 'twitter_config.json'

    def __init__(self):
        try:
            with file(self.TWITTER_CONFIG_FILE) as f:
                self._twitter_config = loads(f.read())['twitter']
                self._twitter = Twython(
                    self._twitter_config['consumer_key'],
                    self._twitter_config['consumer_secret'],
                    self._twitter_config['access_token'],
                    self._twitter_config['access_token_secret'])
        except TwythonError as e:
            print e
        except Exception as e:
            print "tweeting disabled as no valid credentials found: %s" \
                % e.message
            self._twitter = None

    def tweet(self, text):
        if self._twitter is None:
            return

        nchar = len(text)
        print "Tweeting %s ... (%d)" % (text, nchar)
        if nchar < 140:
            try:
                self._twitter.update_status(status=text)
            except TwythonError as e:
                print e
        else:
            print "tweet of more than 140 chars not allowed"

    def tweet_photo(self, text, photo_path):
        if self._twitter is None:
            return

        nchar = len(text)

        print "Tweeting %s with photo ... (%d)" % (text, nchar)
        if nchar < 140:
            try:
                photo = open(photo_path, 'rb')
                self._twitter.update_status_with_media(status=text, media=photo)
            except TwythonError as e:
                print e
        else:
            print "tweet of more than 140 chars not allowed"


tweeter = Tweeter()


class WindowDrawApp(web.application):
    def run(self, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', config.listen_port))


if __name__ == '__main__':
    app = WindowDrawApp(urls, globals())
else:
    app = web.application(urls, globals(), autoreload=False)

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
        return renderer.index(config.config)

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
        return renderer.view(config.config)


### Renderers for actual interface:
class tweet:
    def POST(self):
        i = web.input()
        with open(i['fname'], 'w') as f:
            f.write(i['data'])
        return web.ok()


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
            r = self.response(str(e))
            yield r


def signal_handler(signum, frame):
    _exit(signal.SIGTERM)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
else:
    application = app.wsgifunc()
