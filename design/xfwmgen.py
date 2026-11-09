from PIL import Image, ImageDraw, ImageFilter
import os, sys
S=4; TH=34; R=12
def theme(path, bg, edge, text, itext, inactive_dot, dark):
    os.makedirs(path, exist_ok=True)
    def solid(n,w,h,c): Image.new("RGBA",(w,h),c+(255,)).save(f"{path}/{n}")
    for st in ("active","inactive"):
        for i in range(1,6): solid(f"title-{i}-{st}.png",4,TH,bg)
        for n in ("left","right"): solid(f"{n}-{st}.png",1,4,edge)
        solid(f"bottom-{st}.png",4,1,edge); solid(f"bottom-left-{st}.png",1,1,edge); solid(f"bottom-right-{st}.png",1,1,edge)
        for side in ("left","right"):
            big=Image.new("RGBA",(R*S,TH*S),(0,0,0,0)); d=ImageDraw.Draw(big)
            x0=0 if side=="left" else -R*S
            # square corners: the compositor rounds the whole window (radius 14)
            d.rectangle((0,0,R*S,TH*S),fill=bg+(255,))
            d.line((0,0,R*S,0),fill=((255,255,255,255) if not dark else tuple(min(255,c+22) for c in bg)+(255,)),width=S)
            big.resize((R,TH),Image.LANCZOS).save(f"{path}/top-{side}-{st}.png")
        # top highlight on title pieces
        for i in range(1,6):
            im=Image.open(f"{path}/title-{i}-{st}.png"); px=im.load()
            for x in range(im.width): px[x,0]=(255,255,255,255) if not dark else tuple(min(255,c+22) for c in bg)+(255,)
            im.save(f"{path}/title-{i}-{st}.png")
    cols={"close":((255,95,87),(229,62,52)),"hide":((254,190,47),(229,160,20)),"maximize":((43,201,64),(24,168,40))}
    W=24
    def button(name,state):
        big=Image.new("RGBA",(W*S,TH*S),bg+(255,)); d=ImageDraw.Draw(big)
        cx,cy,r=W*S//2,TH*S//2,int(6.5*S)
        if state=="inactive": top,bot=inactive_dot
        else: top,bot=cols[name]
        if state=="pressed": top=tuple(int(c*.8) for c in top); bot=tuple(int(c*.8) for c in bot)
        # vertical gradient sphere
        for k in range(2*r):
            t=k/(2*r); c=tuple(int(top[j]*(1-t)+bot[j]*t) for j in range(3))
            y=cy-r+k; half=int((r*r-(y-cy)**2)**0.5) if abs(y-cy)<=r else 0
            d.line((cx-half,y,cx+half,y),fill=c+(255,))
        rim=tuple(int(c*0.82) for c in bot)
        d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=rim+(255,),width=S)
        # specular highlight
        if state!="inactive":
            hl=Image.new("RGBA",big.size,(0,0,0,0)); hd=ImageDraw.Draw(hl)
            hd.ellipse((cx-int(r*.62),cy-int(r*.86),cx+int(r*.62),cy-int(r*.08)),fill=(255,255,255,120))
            hl=hl.filter(ImageFilter.GaussianBlur(S*0.8)); big.alpha_composite(hl)
        if state in ("prelight","pressed"):
            g=(110,25,20) if name=="close" else ((120,70,0) if name=="hide" else (0,90,15)); w=int(1.4*S); k=int(2.8*S)
            if name=="close": d.line((cx-k,cy-k,cx+k,cy+k),fill=g,width=w); d.line((cx-k,cy+k,cx+k,cy-k),fill=g,width=w)
            elif name=="hide": d.line((cx-k-S//2,cy,cx+k+S//2,cy),fill=g,width=w)
            else:
                d.polygon([(cx-k,cy-k+S),(cx-k,cy+S//2),(cx-S//2,cy-k+S)],fill=g); d.polygon([(cx+k,cy+k-S),(cx+k,cy-S//2),(cx+S//2,cy+k-S)],fill=g)
        # titlebar top highlight row
        img=big.resize((W,TH),Image.LANCZOS); px=img.load()
        for x in range(W): px[x,0]=(255,255,255,255) if not dark else tuple(min(255,c+22) for c in bg)+(255,)
        img.save(f"{path}/{name}-{state}.png")
    for n in cols:
        for st in ("active","inactive","prelight","pressed"): button(n,st)
    for st in ("active","inactive","prelight","pressed"):
        Image.open(f"{path}/maximize-{st}.png").save(f"{path}/maximize-toggled-{st}.png")
    for st in ("active","inactive","prelight","pressed"):
        for n in ("menu","shade","stick","shade-toggled","stick-toggled"):
            Image.new("RGBA",(1,TH),bg+(255,)).save(f"{path}/{n}-{st}.png")
    open(f"{path}/themerc","w").write(f"""button_offset=8
button_spacing=0
full_width_title=true
title_vertical_offset_active=1
title_vertical_offset_inactive=1
title_shadow_active=false
title_shadow_inactive=false
active_text_color={text}
inactive_text_color={itext}
show_app_icon=false
""")
root=sys.argv[1]
theme(f"{root}/Summit/xfwm4",(255,255,255),(214,214,220),"#1d1d1f","#9a9aa0",((222,222,226),(200,200,206)),False)
theme(f"{root}/Summit-Dark/xfwm4",(44,44,46),(22,22,24),"#f2f2f7","#8e8e93",((88,88,92),(70,70,74)),True)
print("ok")
