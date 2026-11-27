#!/usr/bin/env python3
"""
Izsoļu / pārdošanas monitors.

Avoti (sk. SOURCES zemāk):
  * Possessor — izsoļu saraksts https://www.possessor.gov.lv/lv/auctions
  * Possessor — jaunumi (tikai tie, kuros minēta izsole / pārdošana / kapitāldaļas u.tml.)
  * LVĢMC Vides centrs — sadaļa "Izsoles" https://videscentrs.lvgmc.lv/lapas/izsoles
    (nekustamā un kustamā manta; dati no lapas JSON API)
  * LVĢMC Vides centrs — jaunumi (tikai ar atslēgvārdiem)

Katru reizi savāc ierakstus, salīdzina ar state.json un jaunos ieraksta
new_items.md (GitHub darbplūsma no tā izveido Issue => e-pasta paziņojums).
"""
import hashlib
import html as htmllib
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
REPORT_FILE = HERE / "new_items.md"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Atslēgvārdi jaunumu filtrēšanai (meklē virsrakstā un tekstā, bez reģistra)
NEWS_KEYWORDS = re.compile(
    r"izsol|atsavin|pārdo|pārdoš|izpārdo|daļu pārdo|akciju pārdo|"
    r"kustam\w* mant|nekustam\w* īpašum|pirkuma piedāvājum",
    re.I,
)


# ---------------------------------------------------------------- palīgi
def get(url: str, retries: int = 3) -> str:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept-Language": "lv,en;q=0.5"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(text or "")).strip()


def strip_html(h: str) -> str:
    return norm(BeautifulSoup(h or "", "html.parser").get_text(" "))


def soup_main(html: str) -> BeautifulSoup:
    s = BeautifulSoup(html, "html.parser")
    for t in s(["script", "style", "noscript", "header", "footer", "nav"]):
        t.decompose()
    return s


# ---------------------------------------------------------------- avoti
# Katra funkcija atgriež {unikāls_id: {"title": ..., "url": ...}}

def possessor_auctions():
    base = "https://www.possessor.gov.lv/lv/auctions"
    s = soup_main(get(base))
    items = {}
    for a in s.find_all("a", href=True):
        href = a["href"].split("#")[0]
        if not re.match(r"^(https://www\.possessor\.gov\.lv)?/lv/auctions/[^/?]+$", href):
            continue
        url = urljoin(base, href)
        text = norm(a.get_text(" "))
        if url not in items or len(text) > len(items[url]["title"]):
            items[url] = {"title": text, "url": url}
    if not items and "Rāda 0" not in s.get_text():
        raise RuntimeError("izsoļu sarakstā netika atrasts neviens ieraksts — "
                           "iespējams, mainījusies lapas struktūra")
    return items


def possessor_news(seen: dict):
    base = "https://www.possessor.gov.lv/jaunumi"
    s = soup_main(get(base))
    items = {}
    for li in s.select("li.news-item"):
        a = li.find("a", href=True)
        if not a:
            continue
        url = urljoin(base, a["href"])
        title = norm(li.get_text(" ")).replace("Lasīt vairāk", "").strip()
        items[url] = {"title": title, "url": url}
    if not items:
        raise RuntimeError("jaunumu sarakstā netika atrasts neviens ieraksts")
    # Jaunu rakstu tekstu ielādē un pārbauda atslēgvārdus
    for url, it in items.items():
        if url in seen:
            it["relevant"] = seen[url].get("relevant", False)
            continue
        art = soup_main(get(url))
        art = art.select_one("section.wysiwyg") or art.select_one(".formatedtext") or art
        body = norm(art.get_text(" "))
        it["relevant"] = bool(NEWS_KEYWORDS.search(it["title"] + " " + body))
    return items


LVGMC = "https://videscentrs.lvgmc.lv"


GENERIC = re.compile(r"^(pielikumi|dokumenti|izsoles (noteikumi|nolikums|rezultāti)|"
                     r"izsole norisinās|izsoles norisinās|izsoles sākums|kustamo mantu apskatīt)", re.I)


def lvgmc_auctions():
    """Sadaļa 'Izsoles'. Ieraksts = katrs dokuments (saite) zem sava izsoles virsraksta.
    Jauna izsole vienmēr nāk ar jauniem dokumentiem (sludinājums, noteikumi ...)."""
    data = json.loads(get(f"{LVGMC}/data/tekstu_lapas?url=izsoles"))
    if not data:
        raise RuntimeError("API neatgrieza datus par sadaļu 'Izsoles'")
    items = {}
    for sec in data:
        blocks = [sec.get("teksts") or ""]
        for it in sec.get("items") or []:
            blocks.append(it.get("teksts") or "")
            for ak in it.get("akordeoni_items") or []:
                blocks.append(f"<p><strong>{ak.get('nosaukums') or ''}</strong></p>")
                blocks.append(ak.get("teksts") or "")
        s = BeautifulSoup("".join(blocks), "html.parser")
        heading = sec.get("nosaukums") or ""
        for p in s.find_all(["p", "li", "h1", "h2", "h3", "h4", "div"], recursive=True):
            txt = norm(p.get_text(" "))
            if not txt:
                continue
            links = p.find_all("a", href=True)
            # Virsraksts = garāks teksts bez dokumentu saitēm (vai ar saiti uz izsoļu portālu)
            if (len(txt) >= 20 and not GENERIC.match(txt)
                    and (not links or all("izsoles.ta.gov.lv" in l["href"] for l in links))):
                heading = txt
            for l in links:
                href = l["href"].strip()
                if "izsoles.ta.gov.lv" in href and href.rstrip("/").endswith("ta.gov.lv"):
                    continue
                url = urljoin(LVGMC + "/", href)
                key = "lvgmc-doc:" + url
                items.setdefault(key, {
                    "title": f"{sec.get('nosaukums')}: {heading[:220]} — {norm(l.get_text(' ')) or 'dokuments'}",
                    "group": heading[:220],
                    "url": url,
                })
    if not items:
        raise RuntimeError("sadaļā 'Izsoles' netika atrasts neviens dokuments")
    return items


def lvgmc_news(seen: dict):
    data = json.loads(get(f"{LVGMC}/data/jaunumi?valoda=lv-LV"))
    if not data:
        raise RuntimeError("jaunumu API neatgrieza datus")
    items = {}
    for n in data:
        url = f"{LVGMC}/jaunumi/{n['id']}"
        title = norm(n.get("virsraksts"))
        body = strip_html(n.get("teksts"))
        items[url] = {"title": f"{n.get('pub_datums', '')[:10]} {title}", "url": url,
                      "relevant": bool(NEWS_KEYWORDS.search(title + " " + body))}
    return items


SOURCES = [
    ("Possessor — izsoles", possessor_auctions, False),
    ("Possessor — jaunumi par pārdošanu", possessor_news, True),
    ("LVĢMC Vides centrs — izsoles", lvgmc_auctions, False),
    ("LVĢMC Vides centrs — jaunumi par pārdošanu", lvgmc_news, True),
]


# ---------------------------------------------------------------- galvenais
def main():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report, errors = [], []

    for name, fn, takes_seen in SOURCES:
        first_run = name not in state
        seen = state.setdefault(name, {})
        try:
            items = fn(seen) if takes_seen else fn()
        except Exception as e:  # noqa: BLE001
            errors.append(f"- **{name}**: {e}")
            continue

        new = []
        for key, it in items.items():
            if key not in seen:
                seen[key] = {"title": it["title"], "first_seen": today}
                if "relevant" in it:
                    seen[key]["relevant"] = it["relevant"]
                if it.get("relevant", True):
                    new.append(it)

        if first_run:
            print(f"[{name}] pirmā palaišana — saglabāti {len(items)} ieraksti, paziņojums netiek sūtīts")
            continue
        if not new:
            continue

        report.append(f"### {name}\n")
        groups = {}
        for it in new:
            groups.setdefault(it.get("group"), []).append(it)
        for group, its in groups.items():
            if group:  # LVĢMC: viens izsoles virsraksts + tā jaunie dokumenti
                report.append(f"- **{group}**")
                report += [f"  - [{it['title'].rsplit(' — ', 1)[-1]}]({it['url']})" for it in its]
            else:
                report += [f"- [{it['title'][:200]}]({it['url']})" for it in its]
        report.append("")

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")

    body = []
    if report:
        body.append("## Jauni izsoļu / pārdošanas ieraksti\n")
        body += report
    if errors:
        body.append("## Brīdinājumi (lapu neizdevās pārbaudīt)\n")
        body += errors
    REPORT_FILE.write_text("\n".join(body), encoding="utf-8")
    print("\n".join(body) or "Nekā jauna.")


if __name__ == "__main__":
    sys.exit(main())
