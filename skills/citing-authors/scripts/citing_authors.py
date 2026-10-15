#!/usr/bin/env python3
"""Who cites a researcher? Two steps, both against NCBI E-utilities (PubMed).

  fetch  Find the researcher's papers (name + institution), the papers citing
         them (PubMed "cited in" links), and every author's affiliations.
         Writes one JSON cache file.
  chart  Tally authors of the citing papers from that cache and draw a
         horizontal bar chart (PNG). Prints the ranking as text too.

Only PubMed IDs and the search query are sent to NCBI. Set NCBI_API_KEY to
raise the rate limit (optional).
"""
import argparse, collections, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
KEY = os.environ.get("NCBI_API_KEY")
PAUSE = 0.12 if KEY else 0.4


def call(endpoint, **params):
    if KEY:
        params["api_key"] = KEY
    url = EUTILS + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:  # transient 429/5xx: back off and retry
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def search(term):
    r = json.loads(call("esearch.fcgi", db="pubmed", term=term, retmax=10000, retmode="json"))
    return r["esearchresult"]["idlist"]


def cited_by(pmid):
    r = json.loads(call("elink.fcgi", dbfrom="pubmed", db="pubmed",
                        linkname="pubmed_pubmed_citedin", id=pmid, retmode="json"))
    return [l for ls in r.get("linksets", []) for db in ls.get("linksetdbs", []) for l in db["links"]]


def fetch_records(pmids):
    """pmid -> {title, year, journal, authors: [[name, affiliation], ...]} (author order kept)."""
    out = {}
    for i in range(0, len(pmids), 150):
        root = ET.fromstring(call("efetch.fcgi", db="pubmed", retmode="xml", id=",".join(pmids[i:i + 150])))
        for art in root.iter("PubmedArticle"):
            pmid = art.findtext(".//MedlineCitation/PMID")
            authors = []
            for a in art.iter("Author"):
                last = a.findtext("LastName")
                if not last:  # collective/consortium name
                    continue
                name = f"{last} {a.findtext('Initials') or ''}".strip()
                authors.append([name, " | ".join(t.text or "" for t in a.iter("Affiliation"))])
            out[pmid] = {
                "title": "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else "",
                "year": art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "")[:4],
                "journal": art.findtext(".//Journal/ISOAbbreviation") or "",
                "authors": authors,
            }
    return out


def cmd_fetch(a):
    inst = [a.institution] + (a.alias or [])
    aff_q = " OR ".join(f'"{s}"[Affiliation]' for s in inst)
    term = f'"{a.last} {a.first}"[Full Author Name] AND ({aff_q})'
    if a.date_from or a.date_to:
        term += f' AND ("{a.date_from or 1800}"[pdat] : "{a.date_to or 3000}"[pdat])'
    own = search(term)
    print(f"Query: {term}\nOwn papers: {len(own)}", file=sys.stderr)
    if not own:
        sys.exit("No papers found. Check the name spelling and institution.")
    cited = {}
    for n, p in enumerate(own, 1):
        cited[p] = cited_by(p)
        print(f"  cited-by {n}/{len(own)}: {p} -> {len(cited[p])}", file=sys.stderr)
    citing = sorted({c for v in cited.values() for c in v})
    records = fetch_records(own + [c for c in citing if c not in own])
    json.dump({"query": term, "researcher": {"last": a.last, "first": a.first},
               "institution": inst, "own": own, "cited": cited, "records": records},
              open(a.out, "w"), ensure_ascii=False)
    print(f"Unique citing papers: {len(citing)}  (records fetched: {len(records)})", file=sys.stderr)
    for p in own:
        r = records.get(p, {})
        names = ", ".join(n for n, _ in r.get("authors", []))
        print(f"{p}\t{r.get('year','')}\t{len(cited[p])} cit\t{r.get('title','')[:80]}\t{names[:80]}")


def cmd_chart(a):
    d = json.load(open(a.cache))
    recs, cited, own = d["records"], d["cited"], d["own"]
    drop = set(a.drop_own or [])
    own = [p for p in own if p not in drop]
    pat = re.compile("|".join(re.escape(s) for s in d["institution"] + (a.alias or [])), re.I)
    at_inst = {n for r in recs.values() for n, aff in r["authors"] if aff and pat.search(aff)}
    # Surname + first initial, so "Bustamante CJ" and "Bustamante C" match.
    loose = lambda n: n.rsplit(" ", 1)[0] + " " + n.rsplit(" ", 1)[-1][:1] if " " in n else n
    co_keys = {loose(n) for p in own for n, _ in recs.get(p, {}).get("authors", [])}
    is_coauthor = lambda n: loose(n) in co_keys
    inv = collections.defaultdict(set)  # citing pmid -> set of own papers it cites
    for p in own:
        for c in cited.get(p, []):
            inv[c].add(p)
    citing = [c for c in inv if c not in own] if a.no_self_papers else list(inv)

    tally, missing = collections.Counter(), 0
    for c in citing:
        names = [n for n, _ in recs.get(c, {}).get("authors", [])]
        if not names:
            missing += 1
            continue
        if a.position == "last":
            names = names[-1:]
        elif a.position == "first":
            names = names[:1]
        for n in set(names):
            if a.exclude_institution and n in at_inst:
                continue
            if a.exclude_coauthors and is_coauthor(n):
                continue
            tally[n] += len(inv[c]) if a.count == "citations" else 1

    ranked = sorted(tally, key=lambda n: (-tally[n], n))
    top = ranked[:a.top]
    # Don't cut through a tie silently: report how many share the cutoff value.
    if top and len(ranked) > len(top):
        cut = tally[top[-1]]
        tied = sum(1 for n in ranked if tally[n] == cut)
        shown = sum(1 for n in top if tally[n] == cut)
        if tied > shown:
            print(f"NOTE: {tied} authors have {cut}; only {shown} shown (alphabetical).", file=sys.stderr)
    print(f"Own papers: {len(own)} | citing papers: {len(citing)} | without author data: {missing}"
          f" | institution-affiliated names: {len(at_inst)}", file=sys.stderr)
    for n in top:
        flag = " (co-author)" if is_coauthor(n) else ""
        print(f"{tally[n]}\t{n}{flag}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = top[::-1]
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(rows) + 1.8))
    ax.barh(rows, [tally[n] for n in rows], color="#2a6fdb", height=0.7)
    for i, n in enumerate(rows):
        ax.text(tally[n] + max(tally[top[0]], 1) * 0.01, i, str(tally[n]), va="center", fontsize=9)
    r = d["researcher"]
    who = {"all": "authors", "last": "last authors", "first": "first authors"}[a.position]
    excl = f"non-{d['institution'][0]} " if a.exclude_institution else ""
    unit = ("Citations (a paper citing 2 of the works counts as 2)" if a.count == "citations"
            else "Citing papers")
    ax.set_title(f"Top {excl}{who} citing {r['first']} {r['last']} ({d['institution'][0]} papers, PubMed)\n"
                 f"{len(own)} papers · {len(citing)} citing papers", fontsize=11)
    ax.set_xlabel(unit)
    ax.tick_params(axis="y", labelsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(a.png, dpi=150)
    print(f"Chart: {a.png}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="find papers, citing papers and affiliations")
    f.add_argument("--last", required=True, help="surname, e.g. Curie")
    f.add_argument("--first", required=True, help="first name as published, e.g. Marie")
    f.add_argument("--institution", required=True, help="affiliation text, e.g. Sorbonne")
    f.add_argument("--alias", action="append", help="other spellings of the institution (repeatable)")
    f.add_argument("--date-from"), f.add_argument("--date-to")
    f.add_argument("--out", required=True, help="cache JSON path")
    f.set_defaults(func=cmd_fetch)

    c = sub.add_parser("chart", help="tally citing authors and draw the bar chart")
    c.add_argument("--cache", required=True)
    c.add_argument("--png", required=True)
    c.add_argument("--count", choices=["citations", "papers"], default="citations",
                   help="citations: a paper citing k works adds k (default); papers: adds 1")
    c.add_argument("--position", choices=["all", "last", "first"], default="all",
                   help="which author(s) of each citing paper to count")
    c.add_argument("--exclude-institution", action="store_true",
                   help="drop anyone ever listed at the institution in the fetched records")
    c.add_argument("--exclude-coauthors", action="store_true", help="drop the researcher's co-authors")
    c.add_argument("--no-self-papers", action="store_true",
                   help="ignore citing papers that are themselves in the researcher's list")
    c.add_argument("--alias", action="append", help="extra institution spellings for exclusion")
    c.add_argument("--drop-own", action="append", help="PMID wrongly matched to the researcher (repeatable)")
    c.add_argument("--top", type=int, default=25)
    c.set_defaults(func=cmd_chart)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
