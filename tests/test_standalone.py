"""The offline entry point must contain every runtime asset."""

import base64
import json
from html.parser import HTMLParser

from healthvalue.config import ROOT, WEB
from healthvalue.standalone import main


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external = []
        self.payloads = {}
        self.active = None
        self.csv = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            if "src" in attrs:
                self.external.append(attrs["src"])
            self.active = attrs.get("id")
        if tag == "link" and not attrs.get("href", "").startswith("data:"):
            self.external.append(attrs.get("href"))
        if tag == "a" and attrs.get("download") == "panel.csv":
            self.csv = attrs["href"]

    def handle_data(self, data):
        if self.active:
            self.payloads[self.active] = self.payloads.get(self.active, "") + data

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = None


def test_offline_bundle_contains_current_data_and_assets():
    main()
    parser = Assets()
    parser.feed((ROOT / "HealthValue Atlas.html").read_text(encoding="utf-8"))
    assert not parser.external
    for name in ("atlas", "world"):
        assert json.loads(parser.payloads[f"embedded-{name}"]) == json.loads(
            (WEB / f"data/{name}.json").read_text(encoding="utf-8")
        )
    assert base64.b64decode(parser.csv.split(",", 1)[1]) == (WEB / "data/panel.csv").read_bytes()
