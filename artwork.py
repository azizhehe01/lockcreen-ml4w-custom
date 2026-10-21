"""Antialiased transparent native-image assets; no font glyph dependencies."""
import hashlib
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw

CACHE = Path.home()/'.cache/ml4w/lockscreen-art'
S = 4

def canvas(size):
    im=Image.new('RGBA',(size[0]*S,size[1]*S))
    return im,ImageDraw.Draw(im)

def finish(im,size):
    return im.resize(size,Image.Resampling.LANCZOS)

def panel(size,radius,accent):
    im,d=canvas(size)
    d.rounded_rectangle((0,0,size[0]*S-1,size[1]*S-1),radius*S,fill=(29,33,38,255),outline=accent,width=2*S)
    return finish(im,size)

def progress(size,fraction,accent):
    im,d=canvas(size); w,h=im.size
    d.rounded_rectangle((0,0,w-1,h-1),h/2,fill=(230,230,230,60))
    if fraction is not None and fraction>0:
        end=max(h,min(w,round(w*max(0,min(1,fraction)))))
        d.rounded_rectangle((0,0,end-1,h-1),h/2,fill=accent)
    return finish(im,size)

def icon(kind,size=(64,64),color='#f7f3ee'):
    im,d=canvas((64,64))
    def line(points,fill=color,width=3): d.line([(x*S,y*S) for x,y in points],fill=fill,width=width*S,joint='curve')
    def ellipse(box,fill=None,width=3): d.ellipse(tuple(v*S for v in box),fill=fill,outline=color if fill is None else None,width=width*S)
    def poly(points,fill=color): d.polygon([(x*S,y*S) for x,y in points],fill=fill)
    if kind in ('play','pause'):
        ellipse((7,7,57,57),width=2)
        if kind=='play': poly([(26,20),(26,44),(44,32)])
        else:
            for x in (24,36): d.rounded_rectangle((x*S,21*S,(x+5)*S,43*S),S,fill=color)
    elif kind in ('previous','next'):
        pts=[(23,22),(38,32),(23,42)]
        if kind=='previous': pts=[(64-x,y) for x,y in pts]
        poly(pts); x=20 if kind=='previous' else 43
        line([(x,22),(x,42)],width=4)
    elif kind in ('battery','charging'):
        d.rounded_rectangle((17*S,7*S,47*S,58*S),5*S,outline=color,width=3*S)
        line([(27,3),(37,3)],width=3)
        if kind=='charging': poly([(33,18),(24,34),(31,34),(28,47),(40,29),(33,29)],'#cdebb5')
    elif kind=='sun':
        ellipse((20,20,44,44))
        for a in range(0,360,45):
            t=math.radians(a); line([(32+math.cos(t)*20,32+math.sin(t)*20),(32+math.cos(t)*27,32+math.sin(t)*27)])
    elif kind=='offline':
        ellipse((13,13,51,51)); line([(20,44),(44,20)])
    else:
        # One continuous cloud silhouette avoids seams from overlapping circles.
        points=[(15,45),(10,43),(7,38),(7,33),(10,28),(16,26),(18,19),(23,15),(30,14),(37,17),(41,24),(48,25),(54,29),(57,35),(56,40),(52,44),(46,45),(15,45)]
        line(points,width=3)
        if kind=='rain':
            for x in (20,32,44): line([(x,50),(x-3,57)],width=2)
        elif kind=='storm': poly([(34,47),(27,55),(32,55),(29,63),(40,51),(34,51)],'#cdebb5')
        elif kind=='fog':
            line([(13,51),(51,51)],width=2); line([(18,57),(46,57)],width=2)
    return im.resize(size,Image.Resampling.LANCZOS)

def save(im,name):
    """Content-addressed paths make hyprlock reload actual changed pixels."""
    CACHE.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(im.tobytes()).hexdigest()[:16]
    target=CACHE/f'{name}-{digest}.png'
    if not target.exists():
        temp=CACHE/f'.{name}-{os.getpid()}.png'; im.save(temp); temp.replace(target)
    return target
