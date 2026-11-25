"""Pixel metrics on chapter screenshots (1440x900). Same boxes before/after.
Usage: python3 audit/metrics.py <shots_dir> [label]"""
import sys, json, numpy as np
from PIL import Image
from scipy.ndimage import median_filter
D = sys.argv[1]; label = sys.argv[2] if len(sys.argv) > 2 else D
def img(ch): return np.asarray(Image.open(f"{D}/ch{ch:02d}.png").convert('RGB')).astype(float)
def L(a): return a.mean(2)
def box(ch, b): x0,y0,x1,y1=b; return img(ch)[y0:y1, x0:x1]
R = {}
# aperture / emitter peaks (max channel value, 0-255)
for k,(ch,b) in {'ap_eye':(5,(820,560,960,640)),'ap_atosL':(4,(810,470,880,540)),'ap_atosR':(4,(1130,470,1200,540)),
                 'ap_biba':(2,(960,780,1060,820)),'em_rylo':(6,(760,380,1340,560)),'em_kalis':(3,(850,380,1340,570)),'em_indirect':(7,(770,350,1300,580))}.items():
    a=box(ch,b); R[k]=int(a.max())
# profile face brightness range (p95-p5 of luminance) on the white side face
for k,(ch,b) in {'prof_atos':(4,(500,280,1400,370)),'prof_eye':(5,(560,230,760,300))}.items():
    l=L(box(ch,b)); R[k+'_range']=int(np.percentile(l,95)-np.percentile(l,5)); R[k+'_mean']=int(l.mean())
# black body means
for k,(ch,b) in {'blk_eye1':(5,(860,330,1000,580)),'blk_eye2':(5,(1050,300,1300,600)),'blk_biba':(2,(980,700,1040,780))}.items():
    R[k+'_mean']=int(L(box(ch,b)).mean())
# dashed line: along the profile's lower lip (ch04 rows 392-412) count on/off transitions of the brightest pixel per column
l=L(box(4,(420,394,1440,410))); col=l.max(0); on=col>60
R['dash_transitions']=int(np.abs(np.diff(on.astype(int))).sum())
# speckle: isolated bright pixels on white head bodies (lum - 3x3 median > 30)
sp=0
from scipy.ndimage import maximum_filter
for ch,b in [(4,(840,420,930,500)),(4,(1100,400,1190,470)),(5,(440,370,650,510))]:
    l=L(box(ch,b)); fp=np.ones((3,3),bool); fp[1,1]=False
    sp+=int(((l-maximum_filter(l,footprint=fp))>12).sum())
R['speckle_px']=sp
print(json.dumps({label:R}))
