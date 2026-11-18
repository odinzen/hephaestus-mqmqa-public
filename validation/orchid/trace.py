"""Trace every parameter of the SGTE binary collection to a published source.

    python -I trace.py <sgte-binary dir> <hallstedt2025.txt> <out dir>

Each dataset names the assessment it was taken from, lists its sources (LIST-OF-REFERENCE) and
tags every parameter with one of them. This reads that chain, classifies each binary parameter by
the kind of source behind it, resolves each cited paper to a DOI (through the reference list of
Hallstedt, Calphad 89 (2025) 102833, else a Crossref field search) and checks every DOI against
its registry record field by field: first author, year, volume, first page.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = "hephaestus-provenance-check/1.0 (python urllib)"
CONVENTION = {"SAME", "LIN", "REFLAV", "NULL", ""}


def statements(text):
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("$"))
    return [s.strip() for s in body.split("!")]


def references(text):
    m = re.search(r"LIST[-_]OF[-_]REFERENCE(.*?)!", text, re.S | re.I)
    refs = {}
    if m:
        for tag, val in re.findall(r"^\s*(\S+)\s+'(.*?)'", m.group(1), re.S | re.M):
            refs[tag.upper()] = " ".join(val.split())
    return refs


def source_kind(tag, text):
    t = (text or "").lower()
    if tag in CONVENTION or "unknown source" in t or t.startswith("same or similar") \
            or "convention" in t or "linear combination" in t:
        return "convention"
    if any(w in t for w in ("unpublished", "private", "thesis", "report", "personal")):
        return "unpublished"
    if re.search(r"\(\s*(19|20)\d\d\s*\)", t) and not t.startswith("sgte"):
        return "paper"
    if "database" in t or t.startswith("sgte") or "cost" in t:
        return "database"
    return "other"


def cite_key(text):
    """(volume, first page, year) of the first journal citation in a reference text."""
    m = re.search(r"[\s,.]\s*([A-Za-z]?\d+[A-Za-z]?)\s*,\s*([A-Za-z]?\d+)\s*(?:-\s*[A-Za-z]?\d+)?\s*"
                  r"\(\s*((?:19|20)\d\d)\s*\)", text)
    if not m:
        return None
    return (re.sub(r"[A-Za-z]", "", m.group(1)), m.group(2).lstrip("0"), m.group(3))


def fold(s):
    s = (s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s)


def fold_loose(s):
    """umlauts dropped rather than spelled out (Groebner vs Grobner)"""
    s = "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower()) if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s)


def first_surname(text):
    a = text.split(",")[0].strip()
    a = re.sub(r"^((?:[A-Z][a-z]?\.)(?:-[A-Z][a-z]?\.)?\s*)+", "", a)
    return a.split()[-1] if a.split() else ""


def hallstedt_refs(txt):
    t = txt[txt.find("References\n[1]"):]
    lines = [l for l in t.splitlines()
             if not re.match(r"^\s*(B\. Hallstedt|Calphad 89 \(2025\) 102833|\d+)\s*$", l)]
    t = "\n".join(lines)
    out = {}
    for n, body in re.findall(r"^\[(\d+)\]\s(.*?)(?=^\[\d+\]\s|\Z)", t, re.S | re.M):
        body = " ".join(body.split())
        doi = None
        m = re.search(r"https?://\s*doi\.\s*org/\s*(.+)$", body)
        if m:
            doi = re.sub(r"\s+", "", m.group(1)).rstrip(".")
        k = re.search(r"\s(\d+)\s\(((?:19|20)\d\d)\)\s([A-Za-z]?\d+)", body)
        out[int(n)] = {"text": body, "doi": doi,
                       "key": (k.group(1), k.group(3).lstrip("0"), k.group(2)) if k else None}
    return out


def _get(url, accept=None):
    h = {"User-Agent": UA}
    if accept:
        h["Accept"] = accept
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 406):
                return {"_error": str(e.code)}
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return {"_error": "unreachable"}


def _years(msg):
    ys = set()
    for k in ("issued", "published-print", "published-online", "published"):
        dp = (msg.get(k) or {}).get("date-parts") or [[None]]
        if dp and dp[0] and dp[0][0]:
            ys.add(str(dp[0][0]))
    return sorted(ys)


def _record(msg, agency):
    authors = msg.get("author") or []
    return {"agency": agency,
            "authors": [[a.get("family") or a.get("literal") or "", a.get("given") or ""] for a in authors],
            "years": _years(msg),
            "volume": str(msg.get("volume") or ""),
            "page": str(msg.get("page") or msg.get("article-number") or "").split("-")[0].split("–")[0],
            "title": (msg.get("title") or [""])[0] if isinstance(msg.get("title"), list) else msg.get("title", "")}


def registry(doi, cache):
    """The DOI's record: Crossref first, else the registering agency through doi.org."""
    if doi in cache:
        return cache[doi]
    j = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))
    if "_error" not in j:
        cache[doi] = _record(j["message"], "crossref")
        return cache[doi]
    j2 = _get("https://doi.org/" + urllib.parse.quote(doi, safe="/"), "application/vnd.citationstyles.csl+json")
    cache[doi] = _record(j2, "doi.org") if "_error" not in j2 else {"error": j["_error"] + "/" + j2["_error"]}
    return cache[doi]


def search(text, cache):
    key = "search:" + text
    if key in cache:
        return cache[key]
    q = urllib.parse.quote(re.sub(r";.*$", "", text))
    j = _get(f"https://api.crossref.org/works?rows=5&query.bibliographic={q}")
    items = [] if "_error" in j else j["message"].get("items", [])
    cache[key] = [{"doi": it.get("DOI"), **_record(it, "crossref")} for it in items]
    return cache[key]


def checks_for(text, rec):
    vol, page, year = cite_key(text)
    sn = first_surname(text)
    names = [x for fam, giv in rec.get("authors", []) for x in (fam, giv)]
    author = any(fold(sn) and (fold(sn) == fold(n) or fold_loose(sn) == fold_loose(n) or
                               fold(sn) in fold(n)) for n in names) if names else False
    if not author and names:     # surname printed with the first author's names reversed, or a particle
        author = any(fold(sn) in fold(f + g) for f, g in rec["authors"][:1])
    return {"volume": rec.get("volume", "") == vol,
            "page": rec.get("page", "").lstrip("0") == page,
            "year": year in rec.get("years", []),
            "author": author}


def main():
    src, hal_txt, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    hal = hallstedt_refs(hal_txt.read_text(encoding="utf-8"))
    by_key = defaultdict(list)
    for n, h in hal.items():
        if h["key"]:
            by_key[h["key"]].append(n)

    files = []
    for f in sorted(src.glob("*.tdb")):
        text = f.read_text(encoding="latin-1")
        refs = references(text)
        stem_tag = f.stem.split("-")[1].upper() if "-" in f.stem else ""
        head = " ".join(l.strip("$ ").strip() for l in text.splitlines()[:8] if l.startswith("$"))
        primaries = [t for t in refs if t == stem_tag] or [t for t in refs if t.startswith(stem_tag) and stem_tag]
        params = []
        for st in statements(text):
            m = re.match(r"PAR(?:AMETER)?\s+([A-Z]+)\((.*?)\)\s*(.*)$", st, re.S | re.I)
            if not m:
                continue
            tm = re.search(r"\sN(?:\s+(\S+))?\s*$", st)
            tag = (tm.group(1) or "").upper() if tm else ""
            cons = re.split(r"[,:]", m.group(2).split(";")[0])[1:]
            els = {c.strip().upper() for c in cons if c.strip() and c.strip().upper() not in ("VA", "*")}
            params.append({"tag": tag, "unary": len(els) <= 1 and m.group(1).upper() == "G"})
        kinds, tags = Counter(), Counter()
        for p in params:
            if p["unary"]:
                continue
            if p["tag"] in primaries:
                kind = "primary"
            elif p["tag"] and p["tag"] not in refs and p["tag"] not in CONVENTION:
                kind = "missing_tag"
            else:
                kind = source_kind(p["tag"], refs.get(p["tag"]))
            kinds[kind] += 1
            tags[p["tag"]] += 1
        files.append({"file": f.name, "primary_tags": primaries, "header": head[:300],
                      "primary_refs": [refs[t] for t in primaries], "kinds": dict(kinds),
                      "tags": dict(tags), "refs": {t: refs.get(t) for t in tags}})

    cited = set()
    for fr in files:
        for t, txt in fr["refs"].items():
            if txt and source_kind(t, txt) == "paper":
                cited.add(txt)
        for txt in fr["primary_refs"]:
            if source_kind("", txt) == "paper":
                cited.add(txt)
    cache_file = out / "registry_cache.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    res = {}
    for txt in sorted(cited):
        k = cite_key(txt)
        if not k:
            res[txt] = {"key": None, "status": "unparsed"}
            continue
        cands = by_key.get(k, [])
        sn = fold(first_surname(txt))
        pick = [n for n in cands if sn and sn in fold(hal[n]["text"][:60])] or cands
        doi = hal[pick[0]]["doi"] if len(pick) == 1 else None
        res[txt] = {"key": k, "hallstedt": pick, "doi": doi, "via": "hallstedt" if doi else None}

    dois = sorted({r["doi"] for r in res.values() if r.get("doi")})
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda d: registry(d, cache), dois))
    for txt, r in res.items():
        if r.get("status"):
            continue
        rec = cache.get(r["doi"]) if r["doi"] else None
        if rec and "error" not in rec:
            r["record"], r["checks"] = rec, checks_for(txt, rec)
            if all(r["checks"].values()):
                r["status"] = "verified"
                continue
        # not in Hallstedt's list, no DOI there, or its record disagrees: search Crossref by fields
        hits = search(txt, cache)
        good = [h for h in hits if all(checks_for(txt, h).values())]
        if len(good) == 1 or (good and len({h["doi"] for h in good}) == 1):
            prev = r.get("doi")
            r.update({"doi": good[0]["doi"], "record": good[0], "checks": checks_for(txt, good[0]),
                      "via": "crossref search", "hallstedt_doi_rejected": prev if prev and prev != good[0]["doi"] else None,
                      "status": "verified"})
        elif r.get("checks"):
            r["status"] = "mismatch:" + ",".join(k for k, v in r["checks"].items() if not v)
        elif r.get("doi"):
            r["status"] = "doi_" + cache.get(r["doi"], {}).get("error", "unknown")
        else:
            r["status"] = "no_doi_found"
        cache_file.write_text(json.dumps(cache), encoding="utf-8")
    cache_file.write_text(json.dumps(cache), encoding="utf-8")
    (out / "files.json").write_text(json.dumps(files, indent=1), encoding="utf-8")
    (out / "citations.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("files", len(files), "cited papers", len(res), dict(Counter(r["status"] for r in res.values())))
    tot = Counter()
    for fr in files:
        tot.update(fr["kinds"])
    print("binary parameters by source kind", dict(tot))


if __name__ == "__main__":
    main()
