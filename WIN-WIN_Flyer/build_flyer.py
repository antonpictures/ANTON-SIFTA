import os, glob, base64, io
from PIL import Image
MUSIC="/sessions/loving-blissful-maxwell/mnt/Music"
OUT="/sessions/loving-blissful-maxwell/mnt/ANTON_SIFTA/WIN-WIN_Flyer"
os.makedirs(OUT, exist_ok=True)
def find(pat):
    g=glob.glob(os.path.join(MUSIC,pat))
    if not g: raise SystemExit("MISSING IMAGE: "+pat)
    return g[0]
south=find("*6.20.32*"); north=find("*6.20.00*"); east=find("*6.19.46*")
def b64(path,w,q=86,croptop=0.0):
    im=Image.open(path)
    if croptop: im=im.crop((0,int(im.height*croptop),im.width,im.height))
    h=int(im.height*w/im.width)
    im=im.resize((w,h),Image.LANCZOS).convert("RGB")
    buf=io.BytesIO(); im.save(buf,"JPEG",quality=q,optimize=True)
    return "data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()
HERO=b64(south,1500,89,0.10); TS=b64(south,860); TN=b64(north,860); TE=b64(east,860)

HTML=r"""<!doctype html><html><head><meta charset="utf-8"><style>
@page{size:Letter;margin:0}
*{margin:0;padding:0;box-sizing:border-box}
html,body{font-family:'Carlito','DejaVu Sans',sans-serif;color:#16242e}
.page{width:816px;height:1056px;position:relative;overflow:hidden;page-break-after:always}
.page.last{page-break-after:auto}
.hdr{background:#0a3a63;color:#fff;padding:20px 40px 20px;position:relative}
.hdr:after{content:"";position:absolute;left:0;bottom:0;height:6px;width:100%;background:linear-gradient(90deg,#2e8b57 0%,#2e8b57 55%,#e0a92e 55%,#e0a92e 100%)}
.kick{letter-spacing:3px;font-size:12px;color:#bcd6ea;font-weight:700;text-transform:uppercase}
.h1{font-size:44px;font-weight:800;line-height:1.0;margin-top:5px}
.h1 b{color:#ffd34d}
.loc{font-size:19px;font-weight:700;color:#ffd34d;letter-spacing:1px;margin-top:2px}
.sub{font-size:14px;color:#dbe8f2;margin-top:9px;font-weight:600;max-width:680px}
.hero{position:relative;height:232px}
.hero img{width:100%;height:100%;object-fit:cover;display:block}
.hero .cap{position:absolute;left:0;bottom:0;width:100%;padding:22px 40px 11px;color:#fff;font-weight:700;font-size:15px;background:linear-gradient(0deg,rgba(7,26,44,.9),rgba(7,26,44,0))}
.pillars{padding:14px 26px 2px;font-size:0}
.card{display:inline-block;vertical-align:top;width:50%;padding:8px 14px;font-size:13px}
.inner{position:relative;border:1px solid #e3e9ef;border-radius:11px;padding:13px 15px 13px 60px;min-height:150px;background:#fff}
.badge{position:absolute;left:13px;top:14px;width:36px;height:36px;border-radius:50%}
.b-blue{background:#0a3a63}.b-gold{background:#c9881a}.b-teal{background:#117a8b}.b-green{background:#2e7d4f}.b-white{background:#fff;border:1px solid #e3e9ef}
.card h3{font-size:15px;font-weight:800;color:#0a3a63;text-transform:uppercase;letter-spacing:.3px;line-height:1.1;padding-top:2px}
.card p{font-size:12.5px;line-height:1.46;margin-top:8px;color:#34434e}
.card p b{color:#0a3a63}
.deliver{margin:8px 40px 0;background:#0a3a63;border-radius:12px;padding:13px 16px 6px;color:#fff}
.deliver h2{font-size:14px;letter-spacing:1.5px;text-transform:uppercase;text-align:center;color:#ffd34d;margin-bottom:9px;font-weight:800}
.dgrid{font-size:0}
.ditem{display:inline-block;vertical-align:top;width:50%;font-size:12.7px;padding:5px 10px 5px 0;line-height:1.3}
.ditem svg{vertical-align:-3px;margin-right:8px}
.cta{text-align:center;padding:15px 40px 8px}
.cta .big{font-size:27px;font-weight:800;color:#2e8b57;letter-spacing:.5px}
.cta .l2{font-size:13.5px;color:#34434e;margin-top:5px;font-weight:600}
.cta .l3{font-size:14px;color:#0a3a63;margin-top:7px;font-weight:800}
.foot{position:absolute;bottom:0;left:0;width:100%;background:#eef3f8;color:#62717e;font-size:10px;text-align:center;padding:7px 10px}
.g-hdr{background:#0a3a63;color:#fff;padding:18px 40px;position:relative}
.g-hdr:after{content:"";position:absolute;left:0;bottom:0;height:5px;width:100%;background:linear-gradient(90deg,#2e8b57 0%,#2e8b57 55%,#e0a92e 55%,#e0a92e 100%)}
.gal{padding:16px 48px}
.gitem{width:442px;margin:0 auto 12px;border:1px solid #e3e9ef;border-radius:10px;overflow:hidden}
.gitem img{width:100%;display:block}
.gcap{padding:6px 14px;font-size:12px;color:#34434e;background:#f6fafc;font-weight:600}
.gintro{font-size:12.5px;color:#34434e;text-align:center;margin-bottom:10px;line-height:1.5}
</style></head><body>

<div class="page">
  <div class="hdr">
    <div class="kick">A Better Way Forward &mdash; Cooperation Beats Litigation</div>
    <div class="h1">WIN&#8209;WIN SOLUTION</div>
    <div class="loc">FOR IMPERIAL COUNTY</div>
    <div class="sub">A better site &middot; A public benefit &middot; Shared tax revenue &middot; Jobs and growth. Real wins for residents, the City, the County, and Imperial County&rsquo;s future.</div>
  </div>

  <div class="hero">
    <img src="__HERO__">
    <div class="cap">The relocated, fully landscaped site &mdash; set back behind a buffer, over half a mile from any homes.</div>
  </div>

  <div class="pillars">
    <div class="card"><div class="inner">
      <span class="badge b-blue"><svg width="36" height="36" viewBox="0 0 36 36"><g stroke="#fff" stroke-width="2.1" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 H25"/><path d="M22 11 L25 14 L22 17"/><path d="M27 22 H11"/><path d="M14 19 L11 22 L14 25"/></g></svg></span>
      <h3>Smart Land Swap</h3>
      <p>The data center relocates to the <b>95-acre industrial site</b> at Imperial Ave &amp; Clark Rd &mdash; over <b>&frac12; mile from homes</b> and surrounded by industrial uses, for <b>zero direct impact</b> on neighbors. In exchange, the City annexes the 75-acre Aten &amp; Clark Rd site, gaining control of the land nearest residences.</p>
    </div></div>
    <div class="card"><div class="inner">
      <span class="badge b-gold"><svg width="36" height="36" viewBox="0 0 36 36"><g stroke="#fff" stroke-width="2" fill="none" stroke-linejoin="round"><rect x="10" y="17" width="16" height="9"/><rect x="8.5" y="13" width="19" height="4"/><path d="M18 13 V26"/><path d="M18 13 c-1-4-7-3-5 0 z"/><path d="M18 13 c1-4 7-3 5 0 z"/></g></svg></span>
      <h3>$7 Million Community Gift</h3>
      <p>Once the building permit is approved on the new site, the full <b>75 acres is deeded FREE to the City</b> &mdash; to become a park, soccer fields, playgrounds, or any public benefit the City chooses. A <b>$7 million gift</b> to the community.</p>
    </div></div>
    <div class="card"><div class="inner">
      <span class="badge b-white"><svg width="36" height="36" viewBox="0 0 36 36"><path d="M18 18 L18 5 A13 13 0 1 1 5.6 14.3 Z" fill="#0a3a63"/><path d="M18 18 L5.6 14.3 A13 13 0 0 1 18 5 Z" fill="#e0a92e"/></svg></span>
      <h3>Fair Tax Sharing</h3>
      <p>The County and City enter a tax-sharing agreement on the millions in tax revenue the data center will generate: the <b>County receives 80%</b> and the <b>City receives 20%</b>.</p>
    </div></div>
    <div class="card"><div class="inner">
      <span class="badge b-green"><svg width="36" height="36" viewBox="0 0 36 36"><path d="M13 9 C13 9 8 15.5 8 19.5 a5 5 0 0 0 10 0 C18 15.5 13 9 13 9 Z" fill="#fff"/><path d="M24 9 L18.5 19.5 H22.5 L20.5 27 L28 16 H23.5 Z" fill="#fff"/></svg></span>
      <h3>Responsible Water &amp; Power</h3>
      <p>The project pursued three zero-impact solutions for just <b>880 acre-feet of water</b> &mdash; while IID sends <b>~600,000 acre-feet</b> (about 20% of supply) out of the Valley each year, and <b>exports 61% of its electricity</b>, fueling Riverside&rsquo;s growth as local ratepayers face rising costs. There is ample capacity to serve a data center here, and it has agreed to non-firm power.</p>
    </div></div>
  </div>

  <div class="deliver">
    <h2>The Win-Win Delivers For Everyone</h2>
    <div class="dgrid">
      <div class="ditem"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>Homes &amp; neighborhoods fully protected</div>
      <div class="ditem"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>City gains control + a $7M park gift</div>
      <div class="ditem"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>County &amp; City both share the tax dollars</div>
      <div class="ditem"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>The largest economic opportunity in county history moves forward</div>
    </div>
  </div>

  <div class="cta">
    <div class="big">SUPPORT THE WIN-WIN SOLUTION</div>
    <div class="l2">Choose cooperation over conflict. Let&rsquo;s unlock progress, parks, and prosperity together.</div>
    <div class="l3">Imperial County is strongest when we work together.</div>
  </div>

  <div class="foot">A better industrial site &bull; A stunning new public park &bull; Shared prosperity for City &amp; County &bull; Jobs &amp; growth for our families</div>
</div>

<div class="page last">
  <div class="g-hdr">
    <div class="kick">Win-Win Solution &mdash; Imperial County</div>
    <div class="h1" style="font-size:28px">Project Renderings</div>
  </div>
  <div class="gal">
    <div class="gintro">Visualizations of the proposed site and the surrounding Imperial Avenue / Aten Road area.</div>
    <div class="gitem"><img src="__TS__"><div class="gcap">View to the South &mdash; landscaped facility, retention pond, and buffer along Aten Road.</div></div>
    <div class="gitem"><img src="__TN__"><div class="gcap">View to the North &mdash; existing substation and infrastructure adjoining the site.</div></div>
    <div class="gitem"><img src="__TE__"><div class="gcap">View to the East &mdash; commercial / retail frontage along Imperial Avenue.</div></div>
  </div>
  <div class="foot">Renderings provided for illustration. Figures and terms per the Win-Win Solution proposal.</div>
</div>
</body></html>"""

HTML=HTML.replace("__HERO__",HERO).replace("__TS__",TS).replace("__TN__",TN).replace("__TE__",TE)
from weasyprint import HTML as WP
pdf=os.path.join(OUT,"WIN-WIN_Solution_Flyer.pdf")
WP(string=HTML).write_pdf(pdf)
with open(os.path.join(OUT,"flyer_source.html"),"w") as f: f.write(HTML)
import fitz, time
doc=fitz.open(pdf)
print("PAGES",doc.page_count,"| PDF_KB",os.path.getsize(pdf)//1024)
tag=str(int(time.time()))
for i,pg in enumerate(doc):
    try:
        out_png=os.path.join(OUT,"_pv_%s_p%d.png"%(tag,i+1))
        pg.get_pixmap(dpi=110).save(out_png)
        print("PREVIEW",out_png)
    except Exception as e:
        print("preview skip",e)
print("DONE",pdf)
