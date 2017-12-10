from re import compile
from os import listdir, path
from datetime import datetime
from time import mktime
from shutil import copyfile
from PIL import Image, ImageDraw, ImageFont

abspath = path.dirname(__file__)


class Graphotti2Video:

    def __init__(self, basedir=".", outdir="./frames/", framerate=0.1):
        self.basedir = basedir
        self.outdir = outdir
        self.framerate = framerate
        # file format graphotti_2015-12-04 20:30:23.144833

    def get_file_dict(self, dir, re):
        all_files = listdir(dir)
        cre = compile(re)
        res = {}
        for f in all_files:
            n = cre.findall(f)
            if len(n) == 1:
                dt = datetime.strptime(n[0], '%Y-%m-%d %H:%M:%S.%f')
                secs = mktime(dt.timetuple())
                res[secs] = path.join(dir, f)
        return res

    def get_img_dict(self, dir):
        return g2v.get_file_dict('images/', 'graphotti_(.*).jpg')

    def generate_frames_old(self, img_dict):
        ts = img_dict.keys()
        ts.sort()
        start_ts = ts[0]
        last_frame = -(1.0 / self.framerate)
        frame_counter = -1
        last_fn = img_dict[ts[0]]
        for t in ts:
            offset = t - start_ts
            delta = offset - last_frame
            repeat = int(self.framerate * delta)
            print delta, repeat
            last_frame = offset
            last_fn = img_dict[t]
            for i in range(0, repeat):
                frame_counter += 1
                frame_fn = path.join(self.outdir,
                                     'frame_%07d.jpg' % frame_counter)
                print " %s -> %s" % (last_fn, frame_fn)
                copyfile(last_fn, frame_fn)

    def generate_frames(self, img_dict):
        ts = img_dict.keys()
        ts.sort()
        start_ts = ts[0]
        end_ts = ts[-1]
        t = start_ts
        frame_counter = -1
        usr_font = ImageFont.truetype(path.join(abspath, "ubuntu.ttf"), 25)
        while t <= end_ts:
            # find closes frame *before* this time
            c = min(ts, key=lambda x: abs(x-t))
            print c
            frame_counter += 1
            frame_fn = path.join(self.outdir,
                                 'frame_%07d.jpg' % frame_counter)
            print " %s -> %s" % (img_dict[c], frame_fn)
            copyfile(img_dict[c], frame_fn)
            img = Image.open(frame_fn)
            d_usr = ImageDraw.Draw(img)
            d_usr = d_usr.text((0, 0), datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M'),
                               (255, 100, 100), font=usr_font)
            img.save(frame_fn, 'jpeg')
            t += (1.0 / self.framerate)




if __name__ == '__main__':
    g2v = Graphotti2Video()
    img_files = g2v.get_img_dict('images/')
    g2v.generate_frames(img_files)
