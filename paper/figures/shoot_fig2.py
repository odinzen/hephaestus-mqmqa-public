"""Capture Figure 2 (the live ternary solver card, light theme) at high resolution
via headless-Chrome CDP, then greyscale it.

Flow matches the caption: load the shipped slag database, compute the live
FeO-MgO-SiO2 section at 1600 degC, tap a composition so the pinned comparison
list is visible, and shoot from the controls through the list.

Run with the web app already served at http://localhost:8781. Prints the solver
readout line so the caption's sample/facet numbers can be checked against it.
"""
import base64
import json
import subprocess
import time
from pathlib import Path

import requests
import websocket
from PIL import Image

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://localhost:8781/"
PORT = 9456
HERE = Path(__file__).resolve().parent

SETUP = r"""
(async () => {
  try { document.documentElement.setAttribute('data-theme','light'); } catch(e){}
  document.getElementById('example').click();
  await new Promise(r=>setTimeout(r,4500));
  document.getElementById('live-go').click();
  let t=0; while(t++<60 && !/Solved/.test(document.getElementById('liveread').textContent)){ await new Promise(r=>setTimeout(r,1000)); }
  const cv=document.getElementById('livecanvas'), r=cv.getBoundingClientRect();
  const clk=(fx,fy)=>cv.dispatchEvent(new MouseEvent('click',{clientX:r.left+fx*r.width,clientY:r.top+fy*r.height,bubbles:true}));
  clk(0.48,0.62); await new Promise(r=>setTimeout(r,400));
  return document.getElementById('liveread').textContent;
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


def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         "--remote-allow-origins=*", "--hide-scrollbars",
         "--window-size=1800,2600", "--force-device-scale-factor=1", URL],
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
            {"width": 1800, "height": 2600, "deviceScaleFactor": 3, "mobile": False})
        res = cdp(ws, 10, "Runtime.evaluate",
                  {"expression": SETUP, "awaitPromise": True, "returnByValue": True})
        readout = str(res.get("result", {}).get("value", "?"))
        print("readout:", readout.encode("ascii", "replace").decode())
        time.sleep(1.0)
        ctl = rect_of(ws, 20, "#livecard .tern-ctl")
        hist = rect_of(ws, 21, "#livehist")
        clip = {"x": ctl["x"] - 8, "y": ctl["y"] - 8,
                "width": ctl["w"] + 16,
                "height": (hist["y"] + hist["h"]) - ctl["y"] + 16}
        # clip scale stays 1: the dsf=3 metrics override already renders at 3x,
        # a clip scale on top of that resamples and bands the flat fills
        r = cdp(ws, 30, "Page.captureScreenshot",
                {"format": "png", "clip": {**clip, "scale": 1},
                 "captureBeyondViewport": True})
        ws.close()
    finally:
        proc.terminate()

    raw = HERE / "_fig2.png"
    raw.write_bytes(base64.b64decode(r["data"]))
    Image.open(raw).convert("L").save(HERE / "fig2_browser_app.png")
    raw.unlink(missing_ok=True)
    im = Image.open(HERE / "fig2_browser_app.png")
    print("fig2_browser_app.png written", im.size)


if __name__ == "__main__":
    main()
