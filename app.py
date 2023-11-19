import sys
import os
from glob import glob
abspath = os.path.dirname(__file__)
print(abspath)
import cv2
from math import inf
import numpy as np
from base64 import b64decode

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
from io import BytesIO
from PIL import Image

import config

from geopy.geocoders import Nominatim
from geopy.distance import Geodesic




urls = (
    '/graphotti', 'index',
    '/graphotti/', 'index',
    '/graphotti/simple', 'index_simple',
    '/graphotti/history(.*)', 'history',
    '/graphotti/image_store', 'image_store',
    '/graphotti/tweet', 'tweet',
    '/graphotti/sse', 'SSEServer',
    '/graphotti/view', 'view',
    '/graphotti/acc', 'Acc',
    '/graphotti/about', 'about',
    '/graphotti/photo', 'PhotoServer',
    '/graphotti/log', 'LogServer'
)

#print(os.environ)

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
            return Geodesic(self.location, location).km

    def valid_position(self, location):
        d = self.distance(location)
        #print "distance: %f" % d
        return d < self.max_distance


current_energy = 0.0
gravities = []
last_photo_base64 = None

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
        #print "last energy: %f, acc_time: %f, current_gravity_angle: %f" % (acc, acc_time, current_gravity_angle)

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
        #web.header('Content-length:', 0)
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
                #print e
            finally:
                new_acc_cond.release()
            block = True
            if e is not None:
                r = self.response(str(e))
                yield r

class LogServer():
    def POST(self):
        d = web.input()
        ctx = web.ctx
        env = ctx['environ']
        print("*** LOG: %s\n      [%s: %s]\n      %s" % (
            d['logger'],
            ctx['ip'],
            env['HTTP_USER_AGENT'],
            d['msg']
        ))
        return web.ok()


class PhotoServer():
    def response(self, data):
        response = "data: " + data + "\n\n"
        return response

    def POST(self):
        global last_photo_base64
        i = web.input()
        b64str = i['img']
        from_hist = (i['from_hist'] == "true")
        #print('photopost ' + str(from_hist))
        new_photo_cond.acquire()
        last_photo_base64 = b64str
        if not from_hist:
            history.store(b64str)

        # image = np.asarray(bytearray(png_data), dtype="uint8")
        # cv_image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        # cv2.imwrite('out.png', cv_image)
        try:
            new_photo_cond.notifyAll()
        finally:
            new_photo_cond.release()
        return web.ok()

    def GET(self):
        global last_photo_base64
        web.header("Content-Type", "text/event-stream")
        web.header('Cache-Control', 'no-cache')
        #web.header('Content-length:', 0)
        block = False

        while is_running:
            try:
                new_photo_cond.acquire()
                if block:
                    new_photo_cond.wait()
                if last_photo_base64:
                    e = dumps({
                        'img': last_photo_base64
                    })
                else:
                    e = None
            finally:
                new_photo_cond.release()
            block = True
            if e is not None:
                r = self.response(str(e))
                yield r


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
            print (e)
        except Exception as e:
            print ("tweeting disabled as no valid credentials found: %s" \
                % e)
            self._twitter = None

    def tweet(self, text):
        if self._twitter is None:
            return

        nchar = len(text)
        print("Tweeting %s ... (%d)" % (text, nchar))
        if nchar < 140:
            try:
                self._twitter.update_status(status=text)
            except TwythonError as e:
                print(e)
        else:
            print ("tweet of more than 140 chars not allowed")

    def tweet_photo_url(self, text, photo_path):
        if self._twitter is None:
            return

        nchar = len(text)

        print("Tweeting %s with photo ... (%d)" % (text, nchar))
        if nchar < 140:
            try:
                photo = open(photo_path, 'rb')
                self._twitter.update_status_with_media(status=text,
                                                       media=photo)
            except TwythonError as e:
                print(e)
        else:
            print("tweet of more than 140 chars not allowed")

    def tweet_photo(self, text, blob):
        if self._twitter is None:
            return

        nchar = len(text)

        print("Tweeting %s with photo ... (%d)" % (text, nchar))
        if nchar < 140:
            image_io = BytesIO()
            image_io.write(blob)
            image_io.seek(0)

            try:
                #print type(blob)
                response = self._twitter.upload_media(media=image_io)
                #print response
                response = self._twitter.update_status(
                    status=text,
                    media_ids=[response['media_id']])
            except TwythonError as e:
                print(e)
        else:
            print("tweet of more than 140 chars not allowed")


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
new_photo_cond = Condition()
current_path = dumps({'path': [],
                     'dummy': list(range(1, 2048)),  # data to stop proxy buffering
                      })

last_snapshot = None


# Renderers for actual interface:

class DrawPage:
    def POST(self):
        global current_path
        i = web.input()
        try:
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
                    'dummy': list(range(1, 2048))  # dummy data to stop proxy buffering
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
        except Exception as e:
            raise
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
        ctx = web.ctx
        env = ctx['environ']
        user_agent = env['HTTP_USER_AGENT']
        phone_type = 'unknown'
        if 'iphone' in user_agent.lower():
            phone_type = 'iphone'
        elif 'android' in user_agent.lower():
            phone_type = 'android'
        else:
            phone_type = 'unknown'
        return renderer.index(config.config, phone_type)



class view:
    def GET(self):
        master_key = web.ctx.env.get('GRAPHOTTI_MASTER',getenv('GRAPHOTTI_MASTER', ''))
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
        #print i
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
        image_in = BytesIO()
        image_in.write(i['data'])
        image_in.seek(0)

        img = Image.open(image_in)
        if config.config['mirror']:
            img_flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            img_flipped = img

        image_out = BytesIO()
        img_flipped.save(image_out, 'jpeg')
        i['data'] = image_out.getvalue()

        fname = abspath + '/images/graphotti_%s.jpg' % str(datetime.now())
        with open(fname, 'wb') as f:
            f.write(i['data'])
        last_snapshot = {
            'fname': fname,
            'blob': i['data']
        }
        return web.ok()

class history:

    @staticmethod
    def store(b64str):
        clean_b64 = b64str.replace('data:image/png;base64,','')
        png_data = b64decode(clean_b64)
        #image_in = BytesIO()
        #image_in.write(png_data)
        #image_in.seek(0)

        #img = Image.open(image_in)
        fname = abspath + '/images/history_%s.png' % str(datetime.now())
        with open(fname, 'wb') as f:
            f.write(png_data)

    def GET(self, fname):
        i = web.input(len='')
        if len(i.len) > 0:
            history_len = int(i.len)
            glob_pat = abspath + '/images/history_*.png'
            hist_files = glob(glob_pat)
            sorted_files = sorted(hist_files, key=os.path.getctime, reverse=True)
            res = {
                'files': [('history/' + os.path.basename(f)) for f in sorted_files[:history_len]]
            }
            web.header('Content-Type', 'application/json')  # file type
            return dumps(res)
        elif fname:
            p = '%s/images/%s' % (abspath, str(fname))
            img = Image.open(p)
            image_out = BytesIO()
            img.thumbnail((600,600), Image.LANCZOS)
            img.save(image_out, format='png')
            web.header('Content-Type', 'image/png')  # file type
            return image_out.getvalue()
        else:
            glob_pat = abspath + '/images/history_*.png'
            hist_files = glob(glob_pat)
            sorted_files = sorted(hist_files, key=os.path.getctime, reverse=True)
            snaps = {
                'files': [('history/' + os.path.basename(f)) for f in sorted_files[:16]]
            }
            glob_pat = abspath + '/images/graphotti_*.jpg'
            hist_files = glob(glob_pat)
            sorted_files = sorted(hist_files, key=os.path.getctime, reverse=True)
            drawings = {
                'files': [('history/' + os.path.basename(f)) for f in sorted_files[:16]]
            }
            return renderer.history(snaps, drawings)
            

    def POST(self):
        global last_snapshot
        i = web.input()
        image_in = BytesIO()
        image_in.write(i['data'])
        image_in.seek(0)

        img = Image.open(image_in)
        if config.config['mirror']:
            img_flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            img_flipped = img

        image_out = BytesIO()
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
        #web.header('Content-length:', 0)
        while is_running:
            new_path_cond.acquire()
            try:
                if block:
                    new_path_cond.wait()
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
