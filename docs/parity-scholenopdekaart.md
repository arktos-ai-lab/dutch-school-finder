# Feature parity with Scholen op de kaart (SodK)

Status 2026-11-20 (first written 2026-11-10; gap-closing pass on 2026-11-20). Purpose: list what a school page on scholenopdekaart.nl shows, what we already show, and which open source could close each gap.

Method and limits. I viewed three public school pages (the primary school "De Maasparel" in Stevensweert, the secondary school Vossius Gymnasium in Amsterdam, the special-education school De Aventurijn in Assen) and their sub-pages (Het onderwijs, Resultaten, Tevredenheid) only to list section names and metric labels. No SodK data, text, document or number is stored or reused anywhere in this repo, and nothing was fetched at scale. The inventory below is a feature list in our own words. Where SodK labels a source at all it says only "Bron" (and, for the inspection block, the Inspectie); a large part of every page is text written by the school.

Legend for "Do we have it": yes = in `pipeline/out` now, partial = some of it, no = not shown.

## Parity table

| # | SodK feature | Do we have it | Open data source that could power it | Plan |
|---|---|---|---|---|
| 1 | School self-description: introduction, mission and vision, school characteristics | no | Not open (school-supplied, e.g. Vensters profile) | Out of scope. Link to the school website (`web`) instead. |
| 2 | Type of education, denomination, size class | yes | DUO address files | Done (`den`, `sbo`, `so_type`, `cl`). |
| 3 | Pupil count, 3-year trend, national average | yes | DUO leerlingen per vestiging (trend `pt`) | Done: trend `pt`, plus the national and province average next to the count (`context.json`, context only). |
| 4 | Pupils per leerjaar (PO) | yes | DUO leerlingen bo/sbo leerjaar geslacht 2025-2026 | Done: `lj` in detail_po. |
| 5 | Pupils per age or per verblijfsjaar (PO, SO, VSO) | yes | DUO "leerlingen po naar soort po, cluster en leeftijd" (`raw/so_leerlingen_2025-2026.csv`) | Done: `ag` in detail_po (6312 locations) and detail_so (595 locations). |
| 6 | VO pupils by onderwijssoort and leerjaar table | yes | DUO leerlingen VO per vestiging naar onderwijstype | Done: `tp` (totals) and `tj` (leerjaar cells per track, lower bounds flagged). |
| 7 | Where pupils live (postcode area, count, percent) | partial | VO: DUO leerlingen per vestiging naar postcode en leerjaar (have `cm`). PO: DUO publishes pupils per municipality and postcode, not per school, as far as the dataset title shows | VO done. PO: check the DUO "leerlingen per gemeente, postcode en leeftijd" file for a school key; otherwise not possible. |
| 8 | School hours, childcare (voor/na/tussen schooltijd), holiday dates | partial | Not open per school. Holiday regions are national (Rijksoverheid); DUO address file has VAKANTIEREGIO | Holidays done: calendar per region (2025-2026 to 2027-2028, CC0) linked through VAKANTIEREGIO (100 % of locations). School hours and childcare: not open. |
| 9 | Practical info: parent involvement, complaints procedure, admission policy, sick leave, leave | no | Not open (school-supplied) | Out of scope. Explain the generic Dutch rules in the guide (already partly there). |
| 10 | Ouderbijdrage amount and voluntariness | partial | Amount is school-supplied, not open. Inspectie standard WV1 "vrijwillige ouderbijdrage" for the few VO schools inspected on it | We show WV1 in `st` where present (22 + 57 rows). The amount stays unavailable. |
| 11 | Social safety: protocols, monitor, anti-bullying coordinator | partial | Documents are school-supplied. Inspectie standards VS1 Veiligheid and VS2 Schoolklimaat are open; Inspectie "schorsingen en verwijderingen" (CC0) | Standards in `inspection.st`. Suspensions and removals 2025-2026 added as counts per object van toezicht (`sv`, 1478 locations, context only). Protocols and monitors stay unavailable. |
| 12 | Staff: gender, age, function groups, specialists | partial | DUO functiemix instellingen (institution level, BRIN4) | FTE total, management, teaching, support and pupils per teaching FTE at school group level, October 2023 (`fm`, 7032 institutions). Gender, age and specialisms are not in the open data catalogue. |
| 13 | Time spent per subject / onderwijstijd | no | Not open (school-supplied) | Out of scope. |
| 14 | Class grouping, facilities, remedial specialists, early-years offer, vakleerkrachten, school plan, support profile | no | Not open (school-supplied PDFs and text) | Out of scope. |
| 15 | Doorstroomtoets: share reaching fundamental and target level | yes | DUO leerlingen per referentieniveau taal en rekenen | Done: `rn`, plus the Inspectie 3-year result against the signal value and the schoolweging (`lr`, `sw`, 5990 locations). |
| 16 | Interim test results (tussentijdse toetsen) | no | Not open | Out of scope. |
| 17 | School advice with comparison to similar schools | partial | DUO schooladviezen (have 5 years `at`) | National and province advice mix shown next to the school's bar (`context.json`); "vergelijkbare scholen" is SodK's own grouping and not reproduced. |
| 18 | Social development methods and values | no | Not open | Out of scope. |
| 19 | What the Inspectie says (judgement and per-standard scores, link) | yes | Inspectie open data oordelen (CC0), toezichtresultaten deep link | Done: `inspection.json` v2 (`o`, `st`, `xs`, `labels`, `deeplink`). |
| 20 | VO: placement in year 3 against the primary advice | yes | Inspectie onderwijsresultaten VO 2026 (CC0) | Done: `op` in detail_vo. |
| 21 | VO: progression in onderbouw and bovenbouw | yes | Same Inspectie file; DUO zittenblijvers, op- en afstroom | Done: `ov` (onderbouwsnelheid, bovenbouwsucces), `zb`. |
| 22 | Pass rate per exam year and trend | yes | DUO examenkandidaten en geslaagden | Done per track (`pr`). |
| 23 | Pass rate per profile | yes | DUO exam candidates file (`OPLEIDINGSNAAM` per profile) | Done: `pp` for HAVO and VWO, last 2 exam years, profile rows with at least 5 candidates. |
| 24 | Exam grades: SE, CE, final grade, with comparison | yes | DUO geslaagden, gezakten en cijfers | Done: `ce`, `se`, `cl` (same weighting and suppression rule) with the national and province mean for the latest year. Per-subject grades (large DUO files) are not built. |
| 25 | VO profile choice table (vwo profiles over years) | yes | DUO leerlingen VO naar onderwijstype: AFDELING holds the profile for "HAVO lj 4-5" and "VWO lj 4-6" (checked in the 2021 and 2025 files) | Done: `pf`, 2021 to 2025, 7 profile columns, lower bounds flagged. |
| 26 | Pupil satisfaction (overall score, per question, national average, 3-year trend) | no | Not open (school-supplied survey results published through Vensters) | Cannot be done. Say so in the methods page. |
| 27 | Parent and staff satisfaction | no | Not open | Cannot be done. |
| 28 | Atmosphere and safety survey scores | no | Not open per school | Cannot be done. Inspectie VS1/VS2 is the open substitute. |
| 29 | Open day and open evening | partial | features.json `open_days` from school websites (our own crawl, not an open dataset) | Keep, label as "from the school's website". |
| 30 | SO/VSO: cluster, school type | yes | DUO address file (CLUSTER, ONDERWIJS) | Done: `schools_so.json` (`so_type`, `cl`, `cls`). |
| 31 | SO/VSO: pupils per age or verblijfsjaar | yes | Same DUO age file as #5 | Done: `ag` in detail_so (SO and VSO charts). |
| 32 | SO/VSO: samenwerkingsverband and partner organisations | partial | SWV code in DUO files (BO pupil file, VO pupil file) | SWV shown for BO, SBO and VO (8157 of 8618 locations); only VO SWVs have a name in the open files, PO SWVs show a code. SO and VSO have no SWV in any open file; for VSO the VO SWV of the municipality is derived where unambiguous (400 of 528) and labelled. Partner lists stay unavailable. |
| 33 | SO/VSO: support profile, admission criteria (TLV), destination of leavers per school | partial | DUO "uitstroomprofiel VSO" per samenwerkingsverband (`raw/vso_uitstroom_2025-2026.csv`); the rest is school-supplied | Regional leaving profile of VSO pupils (day activities, work, further education, unknown) shown on VSO profiles whose SWV is known, labelled regional and as a profile (the route pupils are prepared for), not as where pupils ended up. Support profile and TLV criteria stay unavailable. |
| 34 | Contact: address, website, map | yes | DUO, PDOK | Done. |
| 35 | Contact: telephone, board name and board size | yes | DUO address files (TELEFOONNUMMER, BEVOEGD GEZAG NUMMER) and DUO board files | Done: telephone (95.9 % of locations), board name (100 %) and the number of locations of the board in this data (`extra.json`). |
| 36 | "Landelijk gemiddelde" and "vergelijkbare scholen" comparisons | partial | Computable from our files (national and province level) | National and province averages for pupils, advice mix, pass rates, exam grades (`context.json`). "Vergelijkbare scholen" is SodK's own grouping and not reproduced. |
| 37 | School guide and school plan downloads | no | Not open (school documents) | Out of scope; link to the school site. |
| 38 | Waiting list, phone-free, other school-set flags | no | Not open | Out of scope. |

Counts: 17 yes, 10 partial, 11 no (38 rows). On 2026-11-10 it was 9 yes, 10 partial, 19 no. Of the 11 "no", all are school-supplied or survey content that no open source covers (#1, #9, #13, #14, #16, #18, #26, #27, #28, #37, #38). The rows closed on 2026-11-20 are #3, #5, #6, #23, #24, #25, #31 and #35 (now yes) and #8, #12, #32, #33 (no to partial).

## Top gaps that remain, and why

1. Satisfaction and safety surveys (#26 to #28). Collected by schools through Vensters; not published as open data per school.
2. School self-description and practical information (#1, #9, #13, #14, #37, #38) including schooltijden, opvang (#8) and the ouderbijdrage amount (#10). School-supplied text.
3. Staff profile (#12). The open data has only FTE and the pupil-teacher ratio per school group, from October 2023. Gender, age and specialisms are not published.
4. Special-education depth (#32, #33): the SWV of SO and VSO schools, ondersteuningsprofiel, TLV criteria, leaver destinations per school. Only a regional leaving profile per SWV is open, and PO SWVs have no names in the open files.
5. PO catchment per school and "similar schools" comparison (#7, #17, #36). The first has no per-school open file that I could find; the second is SodK's own grouping, so we offer national and province comparison instead.

## Open data built on 2026-11-20 (was "found and not built")

All CC0 or CC BY, all per school or per vestiging or per object van toezicht. Licences read on the publisher's page (Inspectie pages: page metadata `DCTERMS.rights` "CC0 1.0 Universal"; Rijksoverheid: licence field "CC0 1.0 Universal" in the data).

| Dataset | Source | Where it shows |
|---|---|---|
| Leerresultaten primair onderwijs 2024, 2025, 2026 | Inspectie, CC0 (https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/leerresultaten-primair-onderwijs) | PO profile: result against the signal value and outcome (`lr`), compare row |
| Schoolweging PO | Inspectie from CBS, CC0 (https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/schoolweging-po) | PO profile with a plain explanation (`sw`), compare row |
| Schorsingen en verwijderingen 2025-2026 | Inspectie, CC0 (https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/schorsingen-en-verwijderingen). Unit: object van toezicht, not board | Profile and compare, counts with a plain note (`sv`) |
| Excellente scholen | Inspectie, CC0, PDF only (https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/excellente-scholen). The predicaat is no longer awarded | Profile and compare, 98 locations (`ex`) |
| School holidays | Rijksoverheid open data, CC0 (https://opendata.rijksoverheid.nl/v1/infotypes/schoolholidays) | Profile, per holiday region (`extra.json`) |
| Functiemix instellingen, bevoegde gezagen | DUO, CC BY 4.0 | Profile: staff at school group level, board name and size |
| DUO exam files (SE, cijferlijst, profile rows), pupil files (leerjaar, profile choice, age), VSO uitstroom | DUO, CC BY 4.0, already in `raw/` | #5, #6, #23, #24, #25, #31, #33 |

## What we have that SodK lacks for expats

- English throughout: guide, field explanations, the Dutch system explained, English glosses for every Inspectie standard and judgement.
- Concept and international flags that DUO does not carry: tweetalig (tto), IB, international departments, newcomer classes (ISK, schakelklas), Technasium, Montessori, Dalton, Jenaplan, vrije school, each with evidence and a confidence level (features.json).
- Search from the family's own postcode with distance (PC4 centroid), instead of by municipality name only.
- Five-year school-advice mix per school and the average home-to-school distance (`dm`), which tell an expat family how local or regional a school's intake is.
- Heroverwegingen (advice reconsiderations) per school next to the doorstroomtoets levels.
- Explicit handling of small numbers: suppressed cells stay null, lower bounds are flagged, no subtraction tricks, no ranking of inspection results.
- Special education with the four clusters explained in plain English, together with the SBO schools.
- A Data sources page with licence and attribution per source, and a documented method.
- Deep link to the Inspectie's own results page per school.
