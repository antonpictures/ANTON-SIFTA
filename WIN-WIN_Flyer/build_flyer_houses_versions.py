import os, base64, io
from PIL import Image
OUT="/sessions/loving-blissful-maxwell/mnt/ANTON_SIFTA/WIN-WIN_Flyer"
PEEK="/sessions/loving-blissful-maxwell/mnt/outputs"
os.makedirs(OUT, exist_ok=True)

SRC = {
    "A": "/tmp/h/a.jpg",
    "B": "/tmp/h/b.jpg",
}

def band_b64(path, top, bot, w=1500, q=90):
    im=Image.open(path).convert("RGB")
    H=im.height
    im=im.crop((0, int(H*top), im.width, int(H*bot)))   # keep the project band, drop sky/houses + foreground parking
    h=int(im.height*w/im.width)
    im=im.resize((w,h),Image.LANCZOS)
    buf=io.BytesIO(); im.save(buf,"JPEG",quality=q,optimize=True)
    return "data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()

TEMPLATE=r"""<!doctype html><html><head><meta charset="utf-8"><style>
@page{size:10in 10in;margin:0}
*{margin:0;padding:0;box-sizing:border-box}
html,body{font-family:'Carlito','DejaVu Sans',sans-serif;color:#16242e}
.page{width:960px;height:960px;position:relative;overflow:hidden;background:#fff}
.hdr{background:#0a3a63;color:#fff;padding:16px 30px 15px;position:relative}
.hdr:after{content:"";position:absolute;left:0;bottom:0;height:5px;width:100%;background:linear-gradient(90deg,#2e8b57 0%,#2e8b57 55%,#e0a92e 55%,#e0a92e 100%)}
.kick{letter-spacing:2.6px;font-size:11px;color:#bcd6ea;font-weight:700;text-transform:uppercase}
.h1{font-size:38px;font-weight:800;line-height:1.0;margin-top:4px}
.loc{font-size:17px;font-weight:700;color:#ffd34d;letter-spacing:1px;margin-top:1px}
.sub{font-size:13px;color:#dbe8f2;margin-top:7px;font-weight:600}
.hero{position:relative;height:230px}
.hero img{width:100%;height:100%;object-fit:cover;object-position:center 42%;display:block}
.hero .cap{position:absolute;left:0;bottom:0;width:100%;padding:20px 30px 9px;color:#fff;font-weight:700;font-size:13.5px;background:linear-gradient(0deg,rgba(7,26,44,.9),rgba(7,26,44,0))}
.pillars{padding:11px 18px 0;font-size:0}
.card{display:inline-block;vertical-align:top;width:50%;padding:7px 11px}
.inner{position:relative;border:1px solid #e3e9ef;border-radius:10px;padding:11px 13px 11px 54px;min-height:120px;background:#fff}
.badge{position:absolute;left:11px;top:12px;width:32px;height:32px;border-radius:50%}
.b-blue{background:#0a3a63}.b-gold{background:#c9881a}.b-green{background:#2e7d4f}.b-white{background:#fff;border:1px solid #e3e9ef}
.card h3{font-size:14px;font-weight:800;color:#0a3a63;text-transform:uppercase;letter-spacing:.3px;line-height:1.1;padding-top:1px;margin:0}
.card p{font-size:11.8px;line-height:1.42;margin:6px 0 0;color:#34434e}
.card p b{color:#0a3a63}
.deliver{margin:7px 30px 0;background:#0a3a63;border-radius:11px;padding:11px 15px 5px;color:#fff}
.deliver h2{font-size:13px;letter-spacing:1.4px;text-transform:uppercase;text-align:center;color:#ffd34d;margin:0 0 7px;font-weight:800}
.dgrid{font-size:0}
.ditem{display:inline-block;vertical-align:top;width:50%;font-size:12px;padding:4px 9px 4px 0;line-height:1.28;color:#fff}
.ditem svg{vertical-align:-3px;margin-right:7px}
.cta{text-align:center;padding:12px 30px 6px}
.cta .big{font-size:25px;font-weight:800;color:#2e8b57;letter-spacing:.4px}
.cta .l2{font-size:12.5px;color:#34434e;margin-top:4px;font-weight:600}
.cta .l3{font-size:13px;color:#0a3a63;margin-top:5px;font-weight:800}
.foot{position:absolute;bottom:0;left:0;width:100%;background:#eef3f8;color:#62717e;font-size:9.5px;text-align:center;padding:6px 10px}
</style></head><body>
<div class="page">
  <div class="hdr">
    <div class="kick">A Better Way Forward &mdash; Cooperation Beats Litigation</div>
    <div class="h1">WIN&#8209;WIN SOLUTION</div>
    <div class="loc">FOR IMPERIAL COUNTY</div>
    <div class="sub">A better site &middot; A public benefit &middot; Shared tax revenue &middot; Jobs and growth.</div>
  </div>
  <div class="hero">
    <img src="__HERO__">
    <div class="cap">__CAP__</div>
  </div>
  <div class="pillars">
    <div class="card"><div class="inner">
      <span class="badge b-blue"><svg width="32" height="32" viewBox="0 0 36 36"><g stroke="#fff" stroke-width="2.1" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 H25"/><path d="M22 11 L25 14 L22 17"/><path d="M27 22 H11"/><path d="M14 19 L11 22 L14 25"/></g></svg></span>
      <h3>Smart Land Swap</h3>
      <p>Relocates to the <b>95-acre industrial site</b> at Imperial Ave &amp; Clark Rd &mdash; over <b>&frac12; mile from homes</b>, <b>zero direct impact</b>. The City annexes the 75-acre Aten &amp; Clark site.</p>
    </div></div>
    <div class="card"><div class="inner">
      <span class="badge b-gold"><svg width="32" height="32" viewBox="0 0 36 36"><g stroke="#fff" stroke-width="2" fill="none" stroke-linejoin="round"><rect x="10" y="17" width="16" height="9"/><rect x="8.5" y="13" width="19" height="4"/><path d="M18 13 V26"/><path d="M18 13 c-1-4-7-3-5 0 z"/><path d="M18 13 c1-4 7-3 5 0 z"/></g></svg></span>
      <h3>$7 Million Community Gift</h3>
      <p>On permit approval, the full <b>75 acres is deeded FREE to the City</b> &mdash; park, soccer fields, playgrounds. A <b>$7 million gift</b> to the community.</p>
    </div></div>
    <div class="card"><div class="inner">
      <span class="badge b-white"><svg width="32" height="32" viewBox="0 0 36 36"><path d="M18 18 L18 5 A13 13 0 1 1 5.6 14.3 Z" fill="#0a3a63"/><path d="M18 18 L5.6 14.3 A13 13 0 0 1 18 5 Z" fill="#e0a92e"/></svg></span>
      <h3>Fair Tax Sharing</h3>
      <p>The <b>County receives 80%</b> and the <b>City 20%</b> of the millions in tax revenue the data center generates.</p>
    </div></div>
    <div class="card"><div class="inner">
      <span class="badge b-green"><svg width="32" height="32" viewBox="0 0 36 36"><path d="M13 9 C13 9 8 15.5 8 19.5 a5 5 0 0 0 10 0 C18 15.5 13 9 13 9 Z" fill="#fff"/><path d="M24 9 L18.5 19.5 H22.5 L20.5 27 L28 16 H23.5 Z" fill="#fff"/></svg></span>
      <h3>Responsible Water &amp; Power</h3>
      <p>Three zero-impact solutions for just <b>880 acre-feet</b> of water &mdash; while IID exports ~20% of supply and <b>61% of its electricity</b> out of the Valley. Ample capacity here; non-firm power.</p>
    </div></div>
  </div>
  <div class="deliver">
    <h2>The Win-Win Delivers For Everyone</h2>
    <div class="dgrid">
      <div class="ditem"><svg width="15" height="15" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>Homes &amp; neighborhoods fully protected</div>
      <div class="ditem"><svg width="15" height="15" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>City gains control + a $7M park gift</div>
      <div class="ditem"><svg width="15" height="15" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>County &amp; City both share the tax dollars</div>
      <div class="ditem"><svg width="15" height="15" viewBox="0 0 16 16"><path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="#ffd34d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>Largest economic opportunity in county history moves forward</div>
    </div>
  </div>
  <div class="cta">
    <div class="big">SUPPORT THE WIN-WIN SOLUTION</div>
    <div class="l2">Choose cooperation over conflict. Progress, parks, and prosperity together.</div>
    <div class="l3">Imperial County is strongest when we work together.</div>
  </div>
  <div class="foot">A better industrial site &bull; A new public park &bull; Shared prosperity &bull; Jobs &amp; growth for our families</div>
</div>
</body></html>"""

CAP="Imperial Avenue &mdash; new retail, jobs, and the relocated data center, set well beyond the homes on the horizon."

from weasyprint import HTML as WP
import fitz
for key, path in SRC.items():
    if not os.path.exists(path):
        print("MISSING", key, path); continue
    w,h = Image.open(path).size
    hero = band_b64(path, 0.12, 0.60)   # keep project band; drop sky/houses + most parking
    html = TEMPLATE.replace("__HERO__", hero).replace("__CAP__", CAP)
    base = f"WIN-WIN_10x10_src{key}"
    pdf = os.path.join(OUT, base+".pdf")
    WP(string=html).write_pdf(pdf)
    doc = fitz.open(pdf)
    doc[0].get_pixmap(dpi=150).save(os.path.join(OUT, base+".png"))
    doc[0].get_pixmap(dpi=96).save(os.path.join(PEEK, base+"_peek.png"))
    print(f"{key} src={w}x{h} -> {base}.pdf + .png + peek")
print("DONE")
