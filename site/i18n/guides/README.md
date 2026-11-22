# Guides

One JSON file per guide, per language: `site/i18n/guides/<lang>/<slug>.json`. The build
(`build/prerender.py`, `guide_pages`) turns each file into `/guides/<slug>/` and lists it on
`/guides/`. The guide files are not shipped to the browser; the pages are static HTML.

To translate a guide, copy the file to the other language folder and translate the text values.
Keep `slug`, section `id`s, `group`, `related_*`, `links` and URLs as they are.

## Format

```json
{
  "slug": "newcomer-classes",            // same as the file name, lowercase-with-dashes, becomes the URL
  "group": "arrive",                     // one of en.json guides.groups: arrive, choose, during, support
  "order": 1,                            // position inside its group on /guides/
  "home": 1,                             // optional: show on the start page, in this order (keep it to about 4 guides)
  "title": "...",                        // <title>, at most 65 characters, ends without the brand
  "desc": "...",                         // meta description, 150 to 160 characters
  "h1": "...",                           // the visible heading
  "lede": "...",                         // one or two sentences: the short answer
  "checked": "2026-11-22",               // date the facts were checked against the sources
  "sections": [
    {"id": "by-age", "h": "Section heading", "blocks": [
      {"p": "Paragraph. <b>Bold</b> and [links](/system/) or [outside links](https://www.rijksoverheid.nl/...)."},
      {"ul": ["item", "item"]},
      {"steps": ["first do this", "then this"]},
      {"say": "A sentence a parent can say or ask at the school."},
      {"note": "Small print, such as 'rules differ per municipality'."},
      {"table": {"caption": "optional", "head": ["Age", "Where"], "rows": [["4 to 11", "..."]]}}
    ]}
  ],
  "sources": [{"label": "Rijksoverheid: ...", "url": "https://..."}],
  "related_guides": ["other-slug"],
  "related_questions": ["without-dutch"],   // ids from en.json faq.groups[].items[]
  "links": ["route", "find", "system", "intl", "munis", "sources"]
}
```

Internal links start with `/` and are relative to the site root (`/questions/without-dutch/`,
`/guides/repeating-a-year/`, `/international/amsterdam/`, `/system/#vo`). The build checks them
with `python -I build/check_site.py`.

Four or more sections get an "On this page" list automatically.
