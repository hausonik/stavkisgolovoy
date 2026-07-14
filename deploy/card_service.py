#!/usr/bin/env python3
# SSG card-render microservice. Standalone. Listens on :8788.
#   GET  /health -> {"ok": true}
#   POST /card   (header X-Render-Key) -> image/png 1080x1350
import io, os, requests
from flask import Flask, request, Response, abort
from PIL import Image, ImageDraw, ImageFont

RENDER_KEY = os.environ.get("RENDER_KEY", "674ebd8d6e69bfca62f209c3f890101ae7b86c2a00cc2462")
PORT = int(os.environ.get("CARD_PORT", "8788"))

W, H = 1080, 1350
BG = (13, 17, 23); GREEN = (61, 220, 132); WHITE = (240, 246, 252); GREY = (139, 148, 158)
MARGIN = 90

def _find_font(bold):
    cands = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]

FONT_REG = _find_font(False)
FONT_BOLD = _find_font(True)

def _hex(c, default):
    try:
        c = (c or "").lstrip("#")
        return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return default

def _font(path, size):
    return ImageFont.truetype(path, size)

def _wrap(draw, text, font, max_w):
    words = str(text).split(); lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [""]

def render_card(spec):
    accent = _hex(spec.get("accent"), GREEN)
    photo_url = spec.get("photo_url")
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)

    if photo_url:
        try:
            r = requests.get(photo_url, timeout=8); r.raise_for_status()
            p = Image.open(io.BytesIO(r.content)).convert("RGB")
            sc = max(W / p.width, H / p.height)
            p = p.resize((int(p.width * sc) + 1, int(p.height * sc) + 1))
            l = (p.width - W) // 2; t = (p.height - H) // 2
            img.paste(p.crop((l, t, l + W, t + H)), (0, 0)); d = ImageDraw.Draw(img)
            d.rectangle([0, H - 150, W, H], fill=(0, 0, 0))
            d.text((MARGIN, H - 105), spec.get("footer") or "СТАВКИ С ГОЛОВОЙ", font=_font(FONT_BOLD, 40), fill=WHITE)
            out = io.BytesIO(); img.save(out, "PNG", optimize=True); return out.getvalue()
        except Exception:
            img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)

    y = MARGIN
    kicker = (spec.get("kicker") or "").strip()
    if kicker:
        d.rectangle([MARGIN, y, MARGIN + 12, y + 40], fill=accent)
        d.text((MARGIN + 30, y + 2), kicker.upper(), font=_font(FONT_BOLD, 34), fill=accent); y += 90

    title = (spec.get("title") or "").strip()
    if title:
        ft = _font(FONT_BOLD, 74)
        col = accent if not spec.get("lines") else WHITE
        for ln in _wrap(d, title, ft, W - 2 * MARGIN):
            d.text((MARGIN, y), ln, font=ft, fill=col); y += 88
        y += 30; d.rectangle([MARGIN, y, MARGIN + 220, y + 8], fill=accent); y += 50

    fb = _font(FONT_REG, 46)
    for para in (spec.get("lines") or []):
        for ln in _wrap(d, para, fb, W - 2 * MARGIN):
            if y > H - 220: break
            d.text((MARGIN, y), ln, font=fb, fill=WHITE); y += 62
        y += 24

    d.text((MARGIN, H - 110), (spec.get("footer") or "СТАВКИ С ГОЛОВОЙ").strip(), font=_font(FONT_BOLD, 38), fill=GREY)
    out = io.BytesIO(); img.save(out, "PNG", optimize=True); return out.getvalue()

app = Flask(__name__)

@app.get("/health")
def health():
    return {"ok": True, "service": "ssg-card"}

@app.post("/card")
def card():
    if request.headers.get("X-Render-Key") != RENDER_KEY:
        abort(401)
    return Response(render_card(request.get_json(force=True) or {}), mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
