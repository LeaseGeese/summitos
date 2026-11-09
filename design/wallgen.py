import numpy as np, sys, math
from PIL import Image, ImageFilter
# name: (base_dark, base_light, blobs [(x,y,r,color)], ribbon tints)
PAL = {
 "blue":   ["#071d55","#2563eb","#38bdf8","#a5f3fc","#7c3aed"],
 "purple": ["#1e0b4d","#7c3aed","#c084fc","#e9d5ff","#ec4899"],
 "pink":   ["#4a0626","#e11d74","#fb7185","#fecdd3","#f97316"],
 "orange": ["#4a1504","#f2611d","#fbbf24","#fde68a","#ef4444"],
 "yellow": ["#4a3200","#eab308","#fde047","#fef9c3","#f97316"],
 "green":  ["#042f22","#059669","#34d399","#bbf7d0","#0ea5e9"],
 "silver": ["#1f2329","#6b7685","#aeb8c5","#e5e9ef","#8b9bb4"],
}
SPECTRUM = ["#2f6df6","#8b5cf6","#ec4899","#f97316","#facc15","#22c55e"]
def hx(c): c=c.lstrip("#"); return np.array([int(c[i:i+2],16) for i in (0,2,4)],float)/255
def smooth(t): return t*t*(3-2*t)

def render(name, dark, W, H, seed=7):
    rng=np.random.default_rng(seed)
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32); u=xx/W; v=yy/H
    if name=="spectrum":
        base = hx("#0d0b2a") if dark else hx("#f4f1ff")
        img=np.ones((H,W,3),np.float32)*base
        cols=[hx(c) for c in SPECTRUM]
        pts=[(0.05,0.15),(0.35,0.05),(0.70,0.12),(0.98,0.35),(0.75,0.95),(0.15,0.85)]
        rad=[0.55,0.5,0.5,0.55,0.6,0.55]
        acc=np.zeros_like(img); wsum=np.zeros((H,W,1),np.float32)
        for (px,py),r,c in zip(pts,rad,cols):
            d=((u-px)**2*(W/H)**2+(v-py)**2)/(r*r)
            w=np.exp(-d*2.2)[...,None]; acc+=w*c; wsum+=w
        mix=acc/np.maximum(wsum,1e-6); strength=np.clip(wsum*1.1,0,1)
        img=img*(1-strength*(0.80 if dark else 0.92))+mix*strength*(0.80 if dark else 0.92)
        ribbon_cols=cols
    else:
        p=[hx(c) for c in PAL[name]]
        if dark: c0,c1,c2=p[0]*0.55,p[0],p[1]*0.55
        else: c0,c1,c2=p[3],p[2],p[1]
        g=np.clip(v*0.75+u*0.35,0,1)[...,None]
        img=np.where(g<0.5, c0+(c1-c0)*smooth(g*2), c1+(c2-c1)*smooth((g-0.5)*2))
        for (px,py,r,c,a) in [(0.92,0.10,0.45,p[4],0.55 if not dark else 0.40),(0.05,0.95,0.50,p[1] if not dark else p[1]*0.6,0.6),(0.30,0.20,0.35,p[2] if not dark else p[2]*0.45,0.35)]:
            d=((u-px)**2*(W/H)**2+(v-py)**2)/(r*r); w=np.exp(-d*2.2)[...,None]*a
            img=img*(1-w)+c*w
        ribbon_cols=[p[2],p[3],p[4],p[1],p[2]] if not dark else [p[1],p[2],p[4],p[2],p[1]]
    # liquid glass: a few large refracting bands
    base=img.copy()
    bands=[(0.30,0.20,0.16,0.55),(0.56,0.26,0.14,0.42),(0.84,0.17,0.07,0.9)]
    for i,(y0,width,amp,freq) in enumerate(bands):
        ph=rng.uniform(0,2*np.pi)
        curve=y0+amp*np.sin(2*np.pi*freq*u+ph)+0.03*np.sin(2*np.pi*1.9*u+ph*1.3)-0.38*(u-0.5)
        w=width*(0.75+0.25*np.sin(2*np.pi*0.6*u+ph*0.7))
        d=(v-curve)/w                      # 0 = top edge, 1 = bottom edge
        inside=(d>0)&(d<1)
        t=np.clip(d,0,1)
        lens=np.sin(np.pi*t)               # thickest in the middle
        # refraction: sample the background shifted, stronger in the middle of the band
        shift=(lens*0.10*H*(1 if i%2==0 else -1)).astype(np.int32)
        yi=np.clip(yy.astype(np.int32)+shift,0,H-1)
        xi=np.clip(xx.astype(np.int32)+(lens*0.03*W).astype(np.int32),0,W-1)
        refr=base[yi,xi]
        m=(inside*1.0)[...,None]
        # soft anti-aliased mask
        aa=np.clip(np.minimum(d,1-d)*w*H/1.5,0,1)[...,None]*m
        c=ribbon_cols[(i*2+1)%len(ribbon_cols)]
        glass=(refr*0.72+np.clip(c*1.25+0.05,0,1)*0.28) if dark else (refr*0.78+np.clip(c*1.1+0.10,0,1)*0.22)
        glass=glass+(1-glass)*(0.16 if not dark else 0.12)*((1-t)**1.5)[...,None]   # brighter towards the top
        img=img*(1-aa)+glass*aa
        # rims: bright specular top rim, softer bottom rim
        rim_top=np.exp(-((d-0.0)/(0.012/width*0.2+0.02))**2)
        rim_bot=np.exp(-((d-1.0)/0.03)**2)*0.45
        hl=(rim_top*0.85+rim_bot)[...,None]*(0.75 if dark else 0.9)
        img=img+(1-img)*hl
        # contact shadow below the band
        sh=np.exp(-((d-1.10)/0.12)**2)*(d>1)*(0.22 if dark else 0.12)
        img=img*(1-sh[...,None])
    # gentle vignette + grain
    vig=1-0.18*((u-0.5)**2+(v-0.5)**2)*(1.6 if dark else 0.8)
    img=img*vig[...,None]
    img+= (rng.standard_normal((H,W,1)).astype(np.float32))*0.006
    return Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8))

if __name__=="__main__":
    out=sys.argv[1]; W=int(sys.argv[2]); H=int(sys.argv[3]); names=sys.argv[4:] or ["spectrum"]+list(PAL)
    for nm in names:
        for dark in (False,True):
            im=render(nm,dark,W,H, seed=11)
            im.save(f"{out}/summit-{nm}-{'dark' if dark else 'light'}.{'jpg' if W>1000 else 'png'}", quality=93)
    print("ok")
