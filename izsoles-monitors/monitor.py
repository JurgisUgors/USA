#!/usr/bin/env python3
"""
Izsoļu / pārdošanas monitors.

Katru reizi atver uzraudzītās lapas (ar īstu pārlūku, lai darbotos arī JS lapas),
savāc visas saites, kuru tekstā vai adresē ir atslēgvārdi (izsole, pārdod,
atsavināšana, kapitāldaļas, ...), un salīdzina ar iepriekš redzētajām.
Jaunos ierakstus izdrukā un ieraksta failā new_items.md (to izmanto GitHub
darbplūsma, lai izveidotu Issue => e-pasta paziņojums).
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urldefrag

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "sites.json").read_text(encoding="utf-8"))
STATE_FILE = HERE / "state.json"
REPORT_FILE = HERE / "new_items.md"

KEYWORDS = [k.lower() for k in CONFIG["keywords"]]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def matches(text: str, href: str) -> bool:
    blob = f"{text} {href}".lower()
    return any(k in blob for k in KEYWORDS)


def extract_items(html: str, base_url: str, all_links: bool):
    """Atgriež {url: teksts} visām atbilstošajām saitēm lapā."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # Navigācijas/kājenes saites parasti nav sludinājumi
    for tag in soup.select("header, footer, nav"):
        tag.decompose()

    items = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urldefrag(urljoin(base_url, href))[0]
        text = norm(a.get_text(" "))
        # Ja saitei ir maz teksta, paņem apkārtējā bloka tekstu (kartīte/rinda)
        if len(text) < 15:
            parent = a.find_parent(["article", "li", "tr", "div"])
            if parent is not None:
                text = norm(parent.get_text(" "))[:300]
        if not text:
            continue
        if all_links or matches(text, url):
            if url not in items or len(text) > len(items[url]):
                items[url] = text[:300]
    return items


def fetch_rendered(urls):
    from playwright.sync_api import sync_playwright

    pages = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(locale="lv-LV", user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"))
        for url in urls:
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2000)
                pages[url] = (page.content(), None)
            except Exception as e:  # noqa: BLE001
                pages[url] = (None, str(e))
            finally:
                page.close()
        browser.close()
    return pages


def main():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    first_run = not state
    all_urls = [u for s in CONFIG["sites"] for u in s["urls"]]
    fetched = fetch_rendered(all_urls)

    report, errors = [], []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for site in CONFIG["sites"]:
        seen = state.setdefault(site["name"], {})
        new_here = []
        for url in site["urls"]:
            html, err = fetched[url]
            if err:
                errors.append(f"- {site['name']}: {url} — kļūda: {err}")
                continue
            items = extract_items(html, url, site.get("all_links", False))
            if not items:
                errors.append(f"- {site['name']}: {url} — netika atrasta neviena atbilstoša saite "
                              "(iespējams, mainījusies lapas struktūra)")
            for item_url, text in items.items():
                if item_url not in seen:
                    seen[item_url] = {"text": text, "first_seen": now}
                    new_here.append((item_url, text))
        if new_here:
            report.append(f"### {site['name']}\n")
            report += [f"- [{t[:150]}]({u})" for u, t in new_here]
            report.append("")

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True),
                          encoding="utf-8")

    body = []
    if report and not first_run:
        body.append("## Jauni izsoļu / pārdošanas sludinājumi\n")
        body += report
    if errors:
        body.append("## Brīdinājumi\n")
        body += errors
    if first_run:
        print("Pirmā palaišana: saglabāts sākumstāvoklis, paziņojums netiek sūtīts.")
        print("\n".join(report))
    REPORT_FILE.write_text("\n".join(body), encoding="utf-8")
    print("\n".join(body) or "Nekā jauna.")


if __name__ == "__main__":
    sys.exit(main())
