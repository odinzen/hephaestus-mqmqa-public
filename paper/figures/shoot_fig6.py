"""Capture the two panels of Figure 6 (uTDB steelmaking: Fe-C diagram + Scheil) at
high resolution via headless-Chrome CDP, then greyscale-compose them.

Panel (a): the steelmaking .utdb loaded, Melt/Alloy toggle on Alloy, the Fe-C phase
diagram calculated in the browser with two pinned readouts.
Panel (b): the Scheil solidification panel for the same join.

Run with the web app already served at http://localhost:8781.
"""
import base64
import json
import subprocess
import time
from pathlib import Path

import requests
import websocket
from PIL import Image, ImageDraw, ImageFont

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://localhost:8781/"
PORT = 9455
HERE = Path(__file__).resolve().parent

SETUP = r"""
(async () => {
  try { document.documentElement.setAttribute('data-theme','light'); } catch(e){}
  document.getElementById('example-steel').click();
  await new Promise(r=>setTimeout(r,4500));
  document.querySelector('#pdmode .seg-btn[data-m="alloy"]').click();
  await new Promise(r=>setTimeout(r,1500));
  document.getElementById('pdTmin').value=800;
  document.getElementById('pdTmax').value=1900;
  document.getElementById('pdgen').click();
  let t=0; while(t++<60 && document.getElementById('pdout').classList.contains('hidden')){ await new Promise(r=>setTimeout(r,1000)); }
  const cv=document.getElementById('pdcanvas'), r=cv.getBoundingClientRect();
  const W=cv.clientWidth,H=420,mL=54,mT=34,PW=W-16-mL,PH=H-48-mT;
  const clk=(f,T)=>cv.dispatchEvent(new MouseEvent('click',{clientX:r.left+(mL+f*PW)*r.width/W,clientY:r.top+(mT+PH*(1-(T-800)/(1900-800)))*r.height/H,bubbles:true}));
  clk(0.05,1400); await new Promise(r=>setTimeout(r,300));
  clk(0.17,1500); await new Promise(r=>setTimeout(r,300));
  document.getElementById('scheil-x').value=4;
  document.getElementById('scheil-go').click();
  t=0; while(t++<40 && !document.getElementById('scheil-read').textContent.trim()){ await new Promise(r=>setTimeout(r,1000)); }
  return 'ready';
})()
"""


def cdp(ws, mid, method, params=None):
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            return msg.get("result", {})


def rect_of(ws, mid, selector):
    js = ("(() => { const e=document.querySelector(%r); const r=e.getBoundingClientRect();"
          "return JSON.stringify({x:r.left+window.scrollX,y:r.top+window.scrollY,"
          "w:r.width,h:r.height}); })()" % selector)
    r = cdp(ws, mid, "Runtime.evaluate", {"expression": js, "returnByValue": True})
    return json.loads(r["result"]["value"])


def shoot(ws, mid, clip):
    # clip scale MUST be 1: the deviceScaleFactor=2 metrics override already renders
    # the canvas at 2x native pixels. A clip scale > 1 resamples on top of that and
    # bands the flat fills. dsf=2 + clip scale=1 = one clean 2x capture.
    r = cdp(ws, mid, "Page.captureScreenshot",
            {"format": "png", "clip": {**clip, "scale": 1}, "captureBeyondViewport": True})
    return base64.b64decode(r["data"])


def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         "--remote-allow-origins=*", "--hide-scrollbars",
         "--window-size=1800,2200", "--force-device-scale-factor=1", URL],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        for _ in range(20):
            try:
                tabs = requests.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json()
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.5)
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], max_size=None)
        cdp(ws, 1, "Page.enable")
        cdp(ws, 2, "Runtime.enable")
        cdp(ws, 3, "Emulation.setDeviceMetricsOverride",
            {"width": 1800, "height": 2200, "deviceScaleFactor": 3, "mobile": False})
        # run the setup and wait for 'ready'
        cdp(ws, 10, "Runtime.evaluate",
            {"expression": SETUP, "awaitPromise": True, "returnByValue": True})
        time.sleep(1.0)
        pd = rect_of(ws, 20, "#pdcanvas")
        sc = rect_of(ws, 21, "#scheilcanvas")
        tog = rect_of(ws, 22, "#pdmode-row")
        # panel (a): from the mode toggle down through the diagram
        a_clip = {"x": tog["x"] - 8, "y": tog["y"] - 8,
                  "width": max(pd["w"], tog["w"]) + 16,
                  "height": (pd["y"] + pd["h"]) - tog["y"] + 16}
        b_clip = {"x": sc["x"] - 8, "y": sc["y"] - 8, "width": sc["w"] + 16, "height": sc["h"] + 16}
        Path(HERE / "_fig6a.png").write_bytes(shoot(ws, 30, a_clip))
        Path(HERE / "_fig6b.png").write_bytes(shoot(ws, 31, b_clip))
        ws.close()
        print("panels captured")
    finally:
        proc.terminate()

    # greyscale + compose stacked, with (a)/(b) labels
    a = Image.open(HERE / "_fig6a.png").convert("L")
    b = Image.open(HERE / "_fig6b.png").convert("L")
    W = max(a.width, b.width)
    def pad(im):
        if im.width == W:
            return im
        c = Image.new("L", (W, im.height), 255)
        c.paste(im, ((W - im.width) // 2, 0))
        return c
    a, b = pad(a), pad(b)
    lab_h = 60
    gap = 40
    canvas = Image.new("L", (W, lab_h + a.height + gap + lab_h + b.height), 255)
    try:
        font = ImageFont.truetype("times.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(canvas)
    y = 0
    d.text((0, y + 8), "(a)", fill=0, font=font)
    y += lab_h
    canvas.paste(a, (0, y)); y += a.height + gap
    d.text((0, y + 8), "(b)", fill=0, font=font)
    y += lab_h
    canvas.paste(b, (0, y))
    canvas.save(HERE / "fig6_utdb_steel.png")
    for tmp in ("_fig6a.png", "_fig6b.png"):
        (HERE / tmp).unlink(missing_ok=True)
    print("fig6_utdb_steel.png written", canvas.size)


if __name__ == "__main__":
    main()
