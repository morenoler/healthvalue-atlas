"""Build a self-contained dashboard that also works from a file URL."""

import base64
import json

from .config import ROOT, WEB


def main():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")
    icon = base64.b64encode((WEB / "favicon.svg").read_bytes()).decode("ascii")
    csv = base64.b64encode((WEB / "data/panel.csv").read_bytes()).decode("ascii")
    html = html.replace('href="favicon.svg"', f'href="data:image/svg+xml;base64,{icon}"')
    html = html.replace('<link rel="stylesheet" href="styles.css">', f"<style>{css}</style>")
    html = html.replace('<script defer src="app.js"></script>', "")
    html = html.replace('href="data/panel.csv" download', f'href="data:text/csv;base64,{csv}" download="panel.csv"')
    embedded = []
    for name in ("atlas", "world"):
        data = json.loads((WEB / f"data/{name}.json").read_text(encoding="utf-8"))
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        embedded.append(f'<script type="application/json" id="embedded-{name}">{payload}</script>')
    html = html.replace("</body>", "\n".join(embedded) + f"\n<script>{script}</script>\n</body>")
    destination = ROOT / "HealthValue Atlas.html"
    destination.write_text(html, encoding="utf-8")
    print(f"Standalone dashboard: {destination.name}")


if __name__ == "__main__":
    main()
