---
name: citing-authors
description: Find who cites a researcher. Given a person's name and institution, list their PubMed papers, collect every paper that cites them, and draw a bar chart of the authors who cite them most (all authors, last authors only, excluding the home institution, by citations or by papers). Use whenever the user asks who cites someone, who their top citers are, which labs follow their work, or for a "citing authors" or citation chart for any name and institution, even if they don't say "skill".
---

# Citing authors

Answer "who cites this researcher most?" from PubMed, for any name and institution. The script `scripts/citing_authors.py` does the work in two steps, so filters can change without re-downloading:

- `fetch`: finds the researcher's papers, the papers citing each one, and every author's affiliations. Saves one JSON cache.
- `chart`: tallies authors of the citing papers from the cache and draws a PNG bar chart. It also prints the ranking as text.

`<skill-dir>` below means the folder that contains this SKILL.md (in a plugin install it lives in the plugin cache, not the project). Use its absolute path.

The PubMed connector has no "cited by" lookup, so the script calls NCBI E-utilities directly (the same PubMed database). It sends only the search query and PubMed IDs. Run it with `python3 -I`. Keep the cache in the session scratchpad. Put the PNG where the user asked, or in the project folder if they didn't say.

## 1. Get the inputs

You need the researcher's **surname**, **first name as published**, and **institution**. If any is missing, ask. Also ask, or apply the defaults:

| Choice | Option | Default |
|---|---|---|
| Which authors of each citing paper count | `--position all / last / first` | `all` |
| What one citing paper adds | `--count citations` (adds one per cited work) or `papers` (adds 1) | `citations` |
| Drop people at the home institution | `--exclude-institution` | off |
| Drop the researcher's co-authors | `--exclude-coauthors` | off |
| Bars shown | `--top N` | 25 |

If the institution has other spellings (an English full name, an abbreviation, a translated name), pass each with `--alias`. Example: a short name plus "Institute of Technology" style long name. Affiliation matching is a plain case-insensitive text match.

## 2. Fetch, then check the paper list

```bash
python3 -I <skill-dir>/scripts/citing_authors.py fetch \
  --last <Surname> --first <FirstName> --institution "<Institution>" [--alias "<other spelling>"] \
  --out <scratchpad>/citing.json
```

It prints one line per paper found: PMID, year, citation count, title and authors. **Show this list to the user and ask whether every paper is theirs.** A namesake at the same institution would slip in. Drop wrong ones later with `--drop-own <PMID>`.

If nothing is found, try the first-name variant the person publishes under, or another spelling of the institution.

## 3. Chart

```bash
python3 -I <skill-dir>/scripts/citing_authors.py chart \
  --cache <scratchpad>/citing.json --png <output>.png \
  [--position last] [--count citations] [--exclude-institution] [--exclude-coauthors] [--top 25]
```

Show the PNG to the user (SendUserFile with `display: render`). For a follow-up such as "only last authors" or "drop my institution", rerun `chart` with new flags. Don't fetch again.

## 4. Report the caveats with the result

Always tell the user these, in plain words:

- **The counts are low.** PubMed's "cited by" only includes citing papers whose full text is in PubMed Central. Google Scholar or Scopus will show more.
- **Some names merge several people.** PubMed lists authors as surname plus initials, so common names (e.g. "Zhang J", "Wang Y") can be several different researchers counted as one.
- **Home-institution coverage depends on affiliations.** Before about 2014, PubMed often stored only the first author's affiliation. Early papers by the researcher may be missed, and exclusion may miss some colleagues.
- **Ties at the cutoff.** If the script prints a `NOTE` about ties, the last bars were picked alphabetically. Say so, or raise `--top`.
- Name any co-authors who remain in the chart (the text output marks them).
