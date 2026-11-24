import sys, json, base64, os, pathlib
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
data = json.loads(pathlib.Path(sys.argv[1]).read_text()); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.path.expanduser("~/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
    pg = b.new_page(viewport={"width": 540, "height": 960}); pg.on("pageerror", lambda e: print("ERR", e)); pg.goto("file://" + str(ROOT / "gen/reel_t.html")); pg.evaluate("d=>setData(d)", data)
    for t in sys.argv[3:]:
        u = pg.evaluate(f'render({t});document.getElementById("c").toDataURL("image/png")'); (out / f"t{t}.png").write_bytes(base64.b64decode(u.split(",")[1]))
    b.close()
