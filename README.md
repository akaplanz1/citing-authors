# citing-authors

A Claude Code plugin that answers "who cites this researcher most?" from PubMed.

Give it a name and an institution. It finds the person's PubMed papers, collects every paper that cites them, and draws a bar chart of the citing authors. You can count all authors, last authors only or first authors only, count by citations or by citing papers, and leave out the home institution or the person's co-authors.

## Install

From a local copy of this folder, in Claude Code:

```
/plugin marketplace add /path/to/citing-authors
/plugin install citing-authors@akaplanz1-skills
```

From GitHub, once this folder is pushed as its own repository:

```
/plugin marketplace add <github-user>/<repo>
/plugin install citing-authors@akaplanz1-skills
```

Restart Claude Code (or run `/reload-plugins`) after installing.

## Use

Ask in plain words, for example:

- "Who cites Marie Curie from the Sorbonne?"
- "Same, but only last authors, and leave out people at her institution."
- "Count citing papers instead of citations."

Claude first shows the list of papers it found so you can confirm they are all by the right person, then draws the chart.

## Requirements

- Python 3 with `matplotlib`.
- Internet access to NCBI E-utilities (`eutils.ncbi.nlm.nih.gov`). Only the search query and PubMed IDs are sent.
- Optional: set `NCBI_API_KEY` for a higher rate limit.

## Limits

- PubMed's "cited by" only includes citing papers whose full text is in PubMed Central, so counts are lower than Google Scholar or Scopus.
- Authors are listed as surname plus initials, so common names can merge several people.
- Before about 2014, PubMed often stored only the first author's affiliation, so institution matching misses some older papers.

## Layout

```
citing-authors/
├── .claude-plugin/
│   ├── plugin.json         plugin manifest
│   └── marketplace.json    marketplace "akaplanz1-skills" listing this plugin
├── skills/citing-authors/
│   ├── SKILL.md            the method Claude follows
│   └── scripts/citing_authors.py
└── README.md
```
