"""Assemble standalone test pages (tokens + bundle + preview) for headless rendering."""
import glob
import json
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)
T = json.loads(Path("project/tokens.json").read_text())


def cssv(v, th):
    x = v.get(th) if isinstance(v, dict) else v
    if x is None:
        x = v["light"]
    return f"var(--{x[1:-1]})" if x.startswith("{") else x


out = []
for th, sel in (("light", ':root,[data-theme="light"]'), ("dark", '[data-theme="dark"]')):
    lines = [f"--{t['name']}:{cssv(t['value'], th)};" for t in T["color"]["tokens"]]
    lines += [f"--{t['name']}:{cssv(t['value'], th)};" for t in T["shadow"]["tokens"]]
    out.append(sel + "{" + "".join(lines) + "}")
misc = [f"--{t['name']}:{t['value']};" for f in ("spacing", "radius") for t in T[f]["tokens"]]
misc += [f"--font-{k}:{v};" for k, v in T["type"]["families"].items()]
out.append(":root{" + "".join(misc) + "}")
css = "\n".join(out)

lib = Path("project/components/lib")
libs = (lib / "react.production.min.js").read_text() + "\n"
libs += (lib / "react-dom.production.min.js").read_text()
bundle = Path("project/components/bundle.js").read_text()
bundle_css = Path("project/components/bundle.css").read_text()
head = f"<head><style>{css}</style><style>{bundle_css}</style><script>{libs}</script><script>{bundle}</script>"
Path("test").mkdir(exist_ok=True)
for p in glob.glob("project/components/*/preview.html"):
    name = p.split("/")[-2]
    src = Path(p).read_text()
    for th in ("light", "dark"):
        html = src.replace('<html lang="en">', f'<html lang="en" data-theme="{th}">')
        html = html.replace("<html>", f'<html data-theme="{th}">').replace("<head>", head, 1)
        Path(f"test/{name}-{th}.html").write_text(html)
