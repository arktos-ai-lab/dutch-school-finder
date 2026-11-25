# Fact-check brief (Dutch School Guide)

Goal: check every factual claim on the assigned pages against official sources only, and report. The owner
does not want the current text assumed right: on 2026-11-25 a claim-by-claim check of the school advice guide
found loose wording ("often" where the source says "some", a rule dated to the wrong year). Each claim may be
correct, partly correct or wrong.

## Where the text is

- Guides: `site/i18n/guides/en/<slug>.json` (sections, blocks, sources, `checked` date).
- Question pages and other page text: `site/i18n/en.json` (search for the slug or the page heading). The built
  pages are in `_site/` if you want to see the rendered text, e.g. `_site/questions/<slug>/index.html`.

## Sources

Allowed for a verdict: wetten.overheid.nl (laws and their articles), zoek.officielebekendmakingen.nl
(Staatsblad, Staatscourant, Kamerstukken), rijksoverheid.nl, onderwijsinspectie.nl, duo.nl, government.nl,
belastingdienst.nl, ind.nl, nuffic.nl, the municipality's own site for local rules, ibo.org for IB facts, and a
school's or foundation's own official page for its own fees and admission rules. News, forums, expat sites and
sector councils only as pointers, never as the verdict. If wetten.overheid.nl blocks fetching, use the
repository.officiele-overheidspublicaties.nl XML of the same law, or cite the article from Rijksoverheid.
Fetch in Dutch where the official page is Dutch. No e-mail address in any request.

## What to report (write to `factcheck/<round>-<slug>.md`, one file per page)

For each claim: the claim quoted (short), verdict (correct / partly correct / wrong / outdated / not
verifiable), the rule or fact with article number or page, a short quote (max 2 sentences) and the URL, and,
when not fully correct, a suggested replacement in plain English (no en or em dashes, no hype words). Mark
claims that expire (dates per school year, fees per year, amounts) with the year they hold for. Then list
anything important for expat parents that the page misses, with source. Also check that each listed source
link still works and supports what it is cited for.

Rules: read-only on the site (do not edit `site/`, `build/` or `data/`), no commit, no push. Temp files go in a scratch folder outside the repo and are deleted at the end. Do not overstate: if a source does not settle a claim, say so.
