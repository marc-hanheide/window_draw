import sys
import os
abspath = os.path.dirname(__file__)
print abspath

if len(abspath) > 0:
    sys.path.append(abspath)
    os.chdir(abspath)

import web
import signal
from json import dumps
from json import loads
import sys
from threading import Condition
from os import _exit, getenv, environ
from datetime import datetime
from twython import Twython, TwythonError
from StringIO import StringIO
from PIL import Image

import config

from geopy.geocoders import Nominatim
from geopy.distance import vincenty




urls = (
    '/', 'index',
    '/simple', 'index_simple',
    '/image_store', 'image_store',
    '/tweet', 'tweet',
    '/sse', 'SSEServer',
    '/view', 'view',
    '/acc', 'Acc',
    '/about', 'about'
)

print(os.environ)

renderer = web.template.render('templates', base="base", globals=globals())

is_running = True


class Geofence():

    def __init__(self):
        self.location = config.location
        self.max_distance = config.max_distance

    def distance(self, location):
        if location is None:
            return float('inf')
        else:
            return vincenty(self.location, location).km

    def valid_position(self, location):
        d = self.distance(location)
        print "distance: %f" % d
        return d < self.max_distance


current_energy = 0.0
gravities = []

class Acc():

    def __init__(self):
        self.up_rate = .4
        self.down_rate = .3

    def response(self, data):
        response = "data: " + data + "\n\n"
        return response

    def POST(self):
        global current_energy, gravities
        i = web.input()
        acc = float(loads(i['acc_abs']))
        acc_time = float(loads(i['acc_time']))
        current_gravity_angle = float(loads(i['gravity_angle']))
        # gravity_angle = gravity_angle * .5 + current_gravity_angle * .5
        current_energy = current_energy + self.up_rate * acc
        print "last energy: %f, acc_time: %f, current_gravity_angle: %f" % (acc, acc_time, current_gravity_angle)

        new_acc_cond.acquire()
        gravities.append(current_gravity_angle)
        try:
            new_acc_cond.notifyAll()
        finally:
            new_acc_cond.release()

    def GET(self):
        global current_energy, gravities
        block = False
        web.header("Content-Type", "text/event-stream")
        web.header('Cache-Control', 'no-cache')
        web.header('Content-length:', 0)
        while is_running:
            new_acc_cond.acquire()
            try:
                if block:
                    new_acc_cond.wait(timeout=2)
                gravity_angle = 0.0
                if len(gravities) > 0:
                    for a in gravities:
                        gravity_angle += a
                    gravity_angle /= len(gravities)
                    del gravities[:]
                current_energy = (1.0 - self.down_rate) * current_energy
                e = dumps({
                    'energy': current_energy / 4.0,
                    'gravity_angle': gravity_angle
                })
                print e
            finally:
                new_acc_cond.release()
            block = True
            if e is not None:
                r = self.response(str(e))
                yield r

class PhotoServer():

    def POST(self):

        return web.ok()

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

    def tweet_photo_url(self, text, photo_path):
        if self._twitter is None:
            return

        nchar = len(text)

        print "Tweeting %s with photo ... (%d)" % (text, nchar)
        if nchar < 140:
            try:
                photo = open(photo_path, 'rb')
                self._twitter.update_status_with_media(status=text,
                                                       media=photo)
            except TwythonError as e:
                print e
        else:
            print "tweet of more than 140 chars not allowed"

    def tweet_photo(self, text, blob):
        if self._twitter is None:
            return

        nchar = len(text)

        print "Tweeting %s with photo ... (%d)" % (text, nchar)
        if nchar < 140:
            image_io = StringIO()
            image_io.write(blob)
            image_io.seek(0)

            try:
                print type(blob)
                response = self._twitter.upload_media(media=image_io)
                print response
                response = self._twitter.update_status(
                    status=text,
                    media_ids=[response['media_id']])
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
    web.config.debug = False
    app = web.application(urls, globals(), autoreload=False)

# session = web.session.Session(app,
#                               web.session.DiskStore('sessions'),
#                               initializer={'count': 0})

# web.config.session_parameters['timeout'] = 3600

new_path_cond = Condition()
new_acc_cond = Condition()
current_path = dumps({'path': [],
                     'dummy': range(1, 2048),  # data to stop proxy buffering
                      })

last_snapshot = None


# Renderers for actual interface:

class DrawPage:
    def POST(self):
        global current_path
        i = web.input()
        p = loads(i['path'])
        zoom = float(i['zoom'])
        if 'latitude' in i:
            latitude = float(i['latitude'])
        else:
            latitude = -1.0
        if 'longitude' in i:
            longitude = float(i['longitude'])
        else:
            longitude = -1.0

        geo_location = (latitude, longitude)

        #print latitude
        #if not latitude < 0.0:
        #    if not geo_fence.valid_position(geo_location):
        #        return web.notacceptable()

        #pixel_ratio = float(i['pixel_ratio'])
        for s in p[1]['segments']:
            s[0] /= (zoom)
            s[1] /= (zoom)
        new_path_cond.acquire()
        try:
            env = {}
            for (k, v) in web.ctx.env.items():
                if type(v) is str:
                    env[k] = v
            d = {
                'path': p,
                'env': env,
                'dummy': range(1, 2048),  # dummy data to stop proxy buffering
            }
            current_path = dumps(d)
            new_path_cond.notifyAll()
            # store relevant logs:
            fname = abspath + '/logs/graphotti_%s.json' % str(datetime.now())
            with open(fname, 'w') as f:
                log_data = {
                    'path': p,
                    'env': env,
                    'longitude': longitude,
                    'latitude': latitude,
                    'timestamp': str(datetime.now())
                }
                f.write(dumps(log_data))
        finally:
            new_path_cond.release()
        return web.ok()


class index_simple(DrawPage):
    def GET(self):
        # session.count += 1
        # session.env = {}
        # for (k, v) in web.ctx.env.items():
        #     if type(v) is str:
        #         session.env[k] = v
        return renderer.index_simple(config.config)


class index(DrawPage):
    def GET(self):
        # session.count += 1
        # session.env = {}
        # for (k, v) in web.ctx.env.items():
        #     if type(v) is str:
        #         session.env[k] = v
        return renderer.index(config.config)



class view:
    def GET(self):
        master_key = web.ctx.env.get('GRAPHOTTI_MASTER','')
        i = web.input(key='')
        print('running as master? %s' % (i.key == master_key))
        return renderer.view(config.config, (i.key == master_key))


class about:
    def GET(self):
        return renderer.about(config.config)


class tweet:
    def POST(self):
        global last_snapshot
        i = web.input()
        if last_snapshot is not None:
            #tweeter.tweet_photo(str(datetime.now()), last_snapshot['blob'])
            tweeter.tweet_photo(
                "This doodle has been shared by @graph0tti for @WestEndLights", last_snapshot['blob']
            )
            # tweeter.tweet('test')
        print i
        return web.ok()


class image_store:

    def GET(self):
        if last_snapshot is None:
            return web.ok()
        else:
            web.header('Content-Type', 'image/png')  # file type
            # web.header('Content-disposition',
            #            'attachment; filename=graphotti.png')
            return last_snapshot['blob']

    def POST(self):
        global last_snapshot
        i = web.input()
        image_in = StringIO()
        image_in.write(i['data'])
        image_in.seek(0)

        img = Image.open(image_in)
        if config.config['mirror']:
            img_flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            img_flipped = img

        image_out = StringIO()
        img_flipped.save(image_out, 'jpeg')
        i['data'] = image_out.getvalue()

        fname = abspath + '/images/graphotti_%s.jpg' % str(datetime.now())
        with open(fname, 'w') as f:
            f.write(i['data'])
        last_snapshot = {
            'fname': fname,
            'blob': i['data']
        }
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

geo_fence = Geofence()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
else:
    application = app.wsgifunc()
