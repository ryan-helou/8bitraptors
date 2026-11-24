"""Measure the real drawn bounds of each scene (ignoring oversized background fills). usage: measure.py out/<team>_<kind>.data.json ..."""
import sys, json, os
from playwright.sync_api import sync_playwright
HOOK = """
window.__B=null;
const C=CanvasRenderingContext2D.prototype, add=(x0,y0,x1,y1)=>{const m=g.getTransform(),pts=[[x0,y0],[x1,y0],[x0,y1],[x1,y1]].map(([x,y])=>[(m.a*x+m.c*y+m.e)/2,(m.b*x+m.d*y+m.f)/2]);
 const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const b=window.__B;if(!b)return;if(Math.min(...xs)<-10||Math.max(...xs)>W+10)return;b.x0=Math.min(b.x0,...xs);b.x1=Math.max(b.x1,...xs);b.y0=Math.min(b.y0,...ys);b.y1=Math.max(b.y1,...ys)};
const big=(w,h)=>Math.abs(w)>W*1.5||Math.abs(h)>H*1.2;
const fr=C.fillRect;C.fillRect=function(x,y,w,h){if(this!==g)return fr.call(this,x,y,w,h);if(!((w===32||w===40)&&(h===32||h===40))&&!big(w,h)&&!(w>=W*0.99&&this.getTransform().a>0))add(x,y,x+w,y+h);return fr.call(this,x,y,w,h)};
const rrr=C.roundRect;C.roundRect=function(x,y,w,h,r){if(this!==g)return rrr.call(this,x,y,w,h,r);add(x,y,x+w,y+h);return rrr.call(this,x,y,w,h,r)};
const di=C.drawImage;C.drawImage=function(i,x,y,w,h){if(this!==g)return di.apply(this,arguments);if(w===undefined){w=i.width;h=i.height}add(x,y,x+w,y+h);return di.apply(this,arguments)};
const el=C.ellipse;C.ellipse=function(x,y,rx,ry){if(this!==g)return el.apply(this,arguments);if(rx*2<W*1.2)add(x-rx,y-ry,x+rx,y+ry);return el.apply(this,arguments)};
const ft=C.fillText;C.fillText=function(s,x,y){if(this!==g)return ft.apply(this,arguments);const w=this.measureText(s).width;const al=this.textAlign;const x0=al==='center'?x-w/2:al==='right'?x-w:x;const h=parseInt(this.font)||12;add(x0,y,x0+w,y+h);return ft.apply(this,arguments)};0;
"""
out = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.path.expanduser('~/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell'))
    for f in sys.argv[1:]:
        d = json.load(open(f)); pg = b.new_page(viewport={'width': 540, 'height': 960}); pg.goto('file://' + os.path.abspath('gen/reel_t.html')); pg.evaluate('d=>setData(d)', d); pg.evaluate(HOOK)
        print('==', os.path.basename(f))
        for sp in d['spans']:
            t = sp['end'] - 0.25
            r = pg.evaluate(f'(()=>{{window.__B={{x0:1e9,x1:-1e9,y0:1e9,y1:-1e9}};render({t});return window.__B}})()')
            cx = (r['x0'] + r['x1']) / 2; cy = (r['y0'] + r['y1']) / 2
            print(f"  {sp['scene']:7s} x {r['x0']:6.1f}..{r['x1']:6.1f}  centreX {cx:6.1f} (want 270, off {cx-270:+5.1f})   y {r['y0']:6.1f}..{r['y1']:6.1f} centreY {cy:6.1f}")
        pg.close()
    b.close()
