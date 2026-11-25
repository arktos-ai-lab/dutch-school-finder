# r3: about, sources, compare, map and find pages (checked 2026-11-25)

Scope: `about.*`, `sources.*`, `attr.*`, `foot.*`, `find.*`, `map.*`, `cmp.*`, `filters.*`, `od.*`, `feat.*`, `src.*` labels. Checked against the site's own code (`site/app.js`, `site/data/meta.json`) and DUO, Inspectie and Rijksoverheid pages.

| # | Claim | Verdict | Fact and source |
|---|---|---|---|
| 1 | about.priv.0: "no ads, no analytics, no tracking scripts and no accounts. It sets no cookies." | correct | `site/app.js` uses `localStorage` only; external hosts in code: cdnjs.cloudflare.com, tile.openstreetmap.org, openstreetmap.org (links); no analytics string in `site/index.html`. |
| 2 | about.priv.2: map loads Leaflet from cdnjs.cloudflare.com and tiles from OpenStreetMap; nothing else from another site | correct | Same grep; fonts are in `site/fonts`. |
| 3 | about.priv.1: saves language, age, postcode, filters, compare list in local storage | correct | `app.js` lines for `KEY`, `CMP_KEY`, `LS_LANG`. |
| 4 | about.data1: "School data comes from open government data, mainly DUO and the Inspectie. The rules and dates in the guides come from official sources, mostly the Rijksoverheid." | partly correct | The source list also carries non-official pages: IamExpat (`iamexpat_school_fees_third_party_guide`), ISA fees, VO-raad, OCO Amsterdam, BOVO Haaglanden, De VO Gids, KiesMBO, Studiekeuze123, SIO, MBO Raad, Onderwijsloket. The site labels IamExpat as third party, the others not. |
| 5 | about.ai1: "Every fact is tied to an official source and dated where it can change." | partly correct, overstated | Round 1 and 2 found loose wording in several guides, and some figures rest on non-official pages (fees from ISA and IamExpat). Suggest "Each rule is tied to a source, mostly official, and dated where it can change." |
| 6 | attr.fallback: "School data: DUO Open Onderwijsdata (CC BY 4.0). ... Postcode areas: CBS (CC BY 4.0)" | partly correct | DUO states "Op de open onderwijsdata die DUO beschikbaar stelt, is een CC0-verklaring van toepassing" (https://duo.nl/open_onderwijsdata/veelgestelde-vragen/, 200). `meta.json` already says "DUO's own site also states CC0 1.0; we apply the stricter CC BY 4.0". The fallback string in en.json gives CC BY 4.0 without that explanation. CBS CC BY 4.0 not checked (CBS is not on the allowed source list). Suggest "DUO Open Onderwijsdata (CC0; credited here as a courtesy)". |
| 7 | sources.blocks: licences "(CC0)" for Inspectie data and Rijksoverheid holiday data | not verifiable | The Inspectie pages I opened (schorsingen, excellente scholen) state no licence; `meta.json` says "page metadata of the Inspectie data page, checked 2026-11-20". Rijksoverheid holiday data licence not opened. |
| 8 | sources.check.text: "Facts were checked against official sources ... on 10 November 2026" | outdated | Route and guide `checked` dates are 2026-11-25; one edge is 2026-11-10 (pro to mbo). Update to the true last-check date per page. Also lists VO-raad among "official sources": VO-raad is a sector council. |
| 9 | sources.read.items.0: DUO hides any count below 5; "real figure is a little higher" | correct | DUO statistische beveiliging (see r3-school-page items 2 and 3 for the flow exception). |
| 10 | sources.read.items.2: "judgement is only published after a school visit, and visits are often triggered by concerns"; lowest programme judgement is "our own rule" | partly correct | Own-rule part correct. "After a visit ... triggered by concerns" not found in the Inspectie note; see r3-school-page item 12. |
| 11 | sources.read.items.3: many schools have no final judgement or basic supervision; not a rating | correct | Inspectie note (Toelichting oordelen en standaarden 2025/2026). |
| 12 | sources.counts.by: "The rated set leans towards schools the Inspectie visited after concerns." | not verifiable | No official statement found. Suggest deleting or marking as our reading. |
| 13 | sources.blocks.0: pupils per year group, count date 1 October, 2021-22 to 2025-26 | correct | DUO count date 1 October. File ranges are data facts. |
| 14 | sources.blocks.4/5: Inspectie "onderwijsresultaten voortgezet onderwijs 2026", "oordelen, 1 November 2026"; "English names of the standards are our own short glosses" | correct | Technical note 2026-02-24 exists (https://www.onderwijsinspectie.nl/site/binaries/site-content/collections/documents/2026/02/24/onderwijsresultaten-voortgezet-onderwijs-2026-technische-toelichting/orm-2026-vo-technische-toelichting.pdf); `inspectie_oordelen_2026` link answers 200. |
| 15 | sources.blocks.1: "Support profiles and admission criteria are not open data per school" | not verifiable | Not found in any DUO page read; plausible. |
| 16 | sources.blocks.7: "Staff at school group level: DUO functiemix (October 2023)" | not verifiable | Not opened. |
| 17 | sources.blocks.8: "School holiday dates: Rijksoverheid open data" and meta note "autumn, spring and extra May holidays are advice dates" | wrong (May) | May holiday is one of three fixed holidays (Rijksoverheid vaststellen-data-schoolvakanties). See r3-school-page item 38. |
| 18 | find.note, map.note, cmp.notes: pupil counts from 1 October 2025 (VO provisional); "never sorted by best" | correct | `meta.json` data_years: 2025-2026 peildatum 2025-10-01. |
| 19 | map.note: "Secondary schools take the colour of the highest level they offer" | not verifiable | Site behaviour (see `app.js` line with `tr&64` vwo, `tr&32` havo, then vmbo gl/tl, vmbo bb/kb, pro): consistent. Data statement, not a Dutch-system claim. |
| 20 | cmp.noteTests: test averages from different tests (IEP, Route 8, Dia) are on different scales | correct | Different providers, different scales; see r3-school-page item 5. |
| 21 | cmp.noteInsp: "No current final judgement and basic supervision are not ratings" | correct | Inspectie note. |
| 22 | cmp.noteSo: "Admission to special education needs a toelaatbaarheidsverklaring (TLV)" | partly correct | Clusters 1 and 2: the institution decides. See r3-school-page item 40. |
| 23 | cmp.noteOv and cmp.row.ov*: "Inspectie's three-year figures, with norms corrected for the pupil population" | partly correct | Three of four indicators; not the placement measure. See r3-school-page item 23. |
| 24 | cmp.row.ovObSm etc. "Inspectie, three years" | correct | 2026 technical note. |
| 25 | panel.isk.note, ft.newcomer: name search; "ISK or newcomer class" | correct | Site method statement. |
| 26 | panel.vo.note: "Exam pass rate ... shown when at least 30 candidates took the exam" | not verifiable | Site rule, not a Dutch-system claim. |
| 27 | foot.notAffiliated: not affiliated with DUO, CBS, Kadaster, PDOK, Inspectie | correct | Disclaimer. |
| 28 | src labels: `src.advies` "Rijksoverheid: admission to secondary school based on the final school advice", `src.pro` "how long pupils may stay", `src.schema` "Nuffic: diagram" | correct | Links answered 200 and match titles; Nuffic diagram has no readable text. |
| 29 | src.wetten_uitvoeringsbesluit_wvo_2020 "Uitvoeringsbesluit WVO 2020, article 8.9" | correct | https://wetten.overheid.nl/BWBR0045787/2026-08-01 answers 200 here; art 8.9 text matches (see r3-system item 12). |

## Source links
97 URLs in `SRC_URL` tested with GET (redirects followed). Failures: `voraad`, `brug`, `vo_raad_moving_from_vmbo_to_havo_and_fro` (vo-raad.nl, HTTP 500). `src.nuf` redirects to the Nuffic study-and-work page (works). Content support: `mboRijks` does not mention praktijkonderwijs (cited for the pro edge); `schema` is an image page.

## Missing for expat parents
- About page: no statement that the site is not legal advice or that municipality rules differ per city (the sources page says to check with school and municipality, which covers it).
- Sources page lists no Dutch law text at all for the route rules; add WEB art 8.1.1b, 8.2.1, WVO 2020 art 8.6 and 8.9a (links above in r3-system.md).
