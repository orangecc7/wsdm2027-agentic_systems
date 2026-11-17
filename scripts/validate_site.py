#!/usr/bin/env python3
"""Check every workshop page, its canonical URL, links, and bundled resources."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re
import sys

SITE_URL = "https://orangecc7.github.io/wsdm2027-agentic_systems/"


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = set()
        self.links = []
        self.resources = []
        self.canonical = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in ("img", "script", "source") and attrs.get("src"):
            self.resources.append(attrs["src"])
        if tag == "link":
            if attrs.get("rel") == "canonical":
                self.canonical = attrs.get("href")
            elif attrs.get("rel") in ("stylesheet", "icon", "preload") and attrs.get("href"):
                self.resources.append(attrs["href"])


root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
pages = {path.resolve(): Page(path.read_text(encoding="utf-8")) for path in root.glob("*.html")}
errors = []
if root / "index.html" not in pages:
    errors.append("Missing workshop index.html")


def check(value, parent, link=False):
    if value.startswith(SITE_URL):
        value = value[len(SITE_URL):]
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return
    if parsed.path.startswith("/"):
        errors.append(f"URL escapes workshop subpath: {value}")
        return
    path = (parent / unquote(parsed.path)).resolve() if parsed.path else parent
    if path.is_dir():
        path /= "index.html"
    if not path.is_relative_to(root) or not path.is_file():
        errors.append(f"Missing local target: {value} (from {parent.relative_to(root)})")
    elif link and parsed.fragment and path in pages and unquote(parsed.fragment) not in pages[path].ids:
        errors.append(f"Broken page anchor: {value}")


for path, page in pages.items():
    expected = SITE_URL + ("" if path.name == "index.html" else path.name)
    if page.canonical != expected:
        errors.append(f"Incorrect canonical URL in {path.name}: {page.canonical}")
    for link in page.links:
        if link.startswith("#"):
            if unquote(link[1:]) not in page.ids:
                errors.append(f"Broken anchor in {path.name}: {link}")
        else:
            check(link, path.parent, link=True)
    for value in page.resources:
        check(value, path.parent)
for css in root.rglob("*.css"):
    if "_site" in css.relative_to(root).parts:
        continue
    for value in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", css.read_text()):
        check(value, css.parent)
homepage = pages.get(root / "index.html")
if homepage:
    for target in ("intro", "program", "speakers", "cfp", "dates", "organizers"):
        if target not in homepage.ids:
            errors.append(f"Missing workshop section: {target}")
if errors:
    sys.exit("\n".join(errors))
print(f"Validated {len(pages)} workshop pages, {sum(len(p.resources) for p in pages.values())} page resources, all local links, anchors and CSS resources.")
