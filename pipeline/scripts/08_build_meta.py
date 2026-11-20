"""Step 8: build out/meta.json (data years, generation date, counts, match rates, attribution lines)."""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RAW, OUT, read_jsonl, write_json_atomic


def load(n):
    with open(os.path.join(OUT, n), encoding="utf-8") as f:
        return json.load(f)


def main():
    po, vo, pc4 = load("schools_po.json"), load("schools_vo.json"), load("pc4.json")
    so = load("schools_so.json")
    gi_so = so["cols"].index("g")
    gi_po, gi_vo = po["cols"].index("g"), vo["cols"].index("g")
    cache = {r["k"]: r for r in read_jsonl(os.path.join(RAW, "geocode_cache.jsonl")) if "k" in r}
    addr = [r for k, r in cache.items() if not k.startswith("pc6|")]
    addr_ok = sum(1 for r in addr if r["s"] == "ok")
    addr_exact_suffix = sum(1 for r in addr if r["s"] == "ok" and r.get("x"))

    def q(rows, gi):
        c = {0: 0, 1: 0, 2: 0, 3: 0}
        for r in rows:
            c[r[gi]] += 1
        return {"address": c[0], "pc6_centroid": c[1], "pc4_centroid": c[2], "none": c[3]}

    meta = {
        "generated": datetime.date.today().isoformat(),
        "data_years": {
            "po_pupils": po["years"]["pupils"],
            "so_pupils": so["years"]["pupils"],
            "po_advice": po["years"]["advice"],
            "vo_pupils": vo["years"]["pupils"],
            "vo_exams": vo["years"]["exams"],
            "pc4_geometry": "CBS postcode4, jaarcode 2024 (PDOK OGC API)",
            "addresses": "DUO address files, retrieved " + datetime.date.today().isoformat(),
        },
        "counts": {
            "schools_po": len(po["rows"]),
            "schools_po_sbo": sum(1 for r in po["rows"] if r[po["cols"].index("sbo")]),
            "schools_so": len(so["rows"]),
            "schools_vo": len(vo["rows"]),
            "pc4": len(pc4),
        },
        "geocoding": {
            "address_keys": len(addr),
            "address_matched": addr_ok,
            "address_match_rate": round(addr_ok / len(addr), 4) if addr else None,
            "address_matched_incl_suffix": addr_exact_suffix,
            "quality_codes": {"0": "BAG address via PDOK Locatieserver", "1": "PC6 centroid fallback",
                              "2": "PC4 centroid fallback", "3": "no coordinates"},
            "po": q(po["rows"], gi_po),
            "so": q(so["rows"], gi_so),
            "vo": q(vo["rows"], gi_vo),
        },
        "detail": {"po": "detail_po.json", "vo": "detail_vo.json", "so": "detail_so.json", "inspection": "inspection.json",
                   "extra": "extra.json", "inspectie_extra": "inspectie_extra.json", "context": "context.json"},
        "attribution": [
            {"source": "DUO Open Onderwijsdata",
             "text": "School addresses, pupil numbers, schooladviezen and exam results: DUO (Dienst Uitvoering Onderwijs), "
                     "Open Onderwijsdata, https://duo.nl/open_onderwijsdata (also: pupil history, doorstroomtoets averages, "
                     "home-to-school distance, pupil home postcodes, exam pass rates, pass rates per profile and mean school-exam, central-exam and final-list grades 2021 to 2025, pupils per leerjaar, per profile and per age, special education (SO/VSO) locations and pupils per cluster, referentieniveaus taal en rekenen, heroverwegingen and bijgestelde adviezen, repeaters and up/down-streaming in VO, "
                     "telephone numbers, boards (bevoegd gezag), samenwerkingsverband codes and holiday regions from the address files, the board names files, VSO leavers per samenwerkingsverband, and the functiemix file with staff per school group). We selected, joined and calculated "
                     "percentages from the original files.",
             "licence": "CC BY 4.0 (DUO's own site also states CC0 1.0; we apply the stricter CC BY 4.0)",
             "licence_url": "https://creativecommons.org/licenses/by/4.0/",
             "url": "https://onderwijsdata.duo.nl"},
            {"source": "Inspectie van het Onderwijs",
             "text": "School quality judgements (oordelen) and the judgements per standard, peildatum 1 November 2026: Inspectie van het Onderwijs, "
                     "open data oordelen (Ministerie van Onderwijs, Cultuur en Wetenschap), with the names of the standards from the "
                     "Inspectie's data notes. Also the open data Onderwijsresultaten voortgezet onderwijs 2026 (onderbouwsnelheid, "
                     "bovenbouwsucces, examencijfers, onderwijspositie t.o.v. advies po; norms and calculated verdicts are the Inspectie's).",
             "licence": "CC0 1.0 Universal",
             "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
             "url": "https://www.onderwijsinspectie.nl/documenten/2026/11/03/oordelen-1-november-2026"},
            {"source": "Inspectie van het Onderwijs, leerresultaten primair onderwijs",
             "text": "Leerresultaten primair onderwijs 2024, 2025 and 2026 (reference levels on the doorstroomtoets, signaleringswaarden and the 3-year outcome per school): Inspectie van het Onderwijs, "
                     "Ministerie van Onderwijs, Cultuur en Wetenschap. We selected and re-formatted the figures; the signaleringswaarde and the outcome are the Inspectie's.",
             "licence": "CC0 1.0 Universal (page metadata of the Inspectie data page, checked 2026-11-20)",
             "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
             "url": "https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/leerresultaten-primair-onderwijs"},
            {"source": "Inspectie van het Onderwijs, schoolweging po",
             "text": "Schoolweging primair onderwijs 2022/23 to 2024/25 (3-year mean of the weights calculated by CBS): Inspectie van het Onderwijs, "
                     "Ministerie van Onderwijs, Cultuur en Wetenschap, based on CBS calculations. The weights are shown unchanged.",
             "licence": "CC0 1.0 Universal (page metadata of the Inspectie data page, checked 2026-11-20)",
             "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
             "url": "https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/schoolweging-po"},
            {"source": "Inspectie van het Onderwijs, schorsingen en verwijderingen",
             "text": "Schorsingen en verwijderingen, school year 2025-2026 (reported suspensions of more than one day and removals, counted per object van toezicht): Inspectie van het Onderwijs, "
                     "Ministerie van Onderwijs, Cultuur en Wetenschap. We matched the counts to school locations and summed the rows of a VO location.",
             "licence": "CC0 1.0 Universal (page metadata of the Inspectie data page, checked 2026-11-20)",
             "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
             "url": "https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/schorsingen-en-verwijderingen"},
            {"source": "Inspectie van het Onderwijs, excellente scholen",
             "text": "Overview of schools with the predicaat Excellente School, 2020 to 1 July 2026: Inspectie van het Onderwijs, "
                     "Ministerie van Onderwijs, Cultuur en Wetenschap (PDF list, matched to school locations by us).",
             "licence": "CC0 1.0 Universal (page metadata of the Inspectie data page, checked 2026-11-20)",
             "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
             "url": "https://www.onderwijsinspectie.nl/trends-en-ontwikkelingen/onderwijsdata/excellente-scholen"},
            {"source": "Rijksoverheid, schoolvakanties",
             "text": "School holiday dates per region (noord, midden, zuid) for 2025-2026 to 2027-2028: Rijksoverheid open data (Ministerie van Algemene Zaken), "
                     "opendata.rijksoverheid.nl. Each school is linked to its region through the VAKANTIEREGIO field of the DUO address files. "
                     "The autumn, spring and extra May holidays are advice dates; schools can differ.",
             "licence": "CC0 1.0 Universal (stated in the data itself)",
             "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
             "url": "https://opendata.rijksoverheid.nl/v1/infotypes/schoolholidays"},
            {"source": "CBS",
             "text": "Postcode (PC4) areas: CBS (Statistics Netherlands), dataset CBS Postcode4 statistics, "
                     "distributed via PDOK. Centroids computed by us.",
             "licence": "CC BY 4.0",
             "licence_url": "https://creativecommons.org/licenses/by/4.0/",
             "url": "https://api.pdok.nl/cbs/postcode4/ogc/v1"},
            {"source": "Kadaster / PDOK",
             "text": "Address coordinates and municipality names: Kadaster, BAG (Basisregistratie Adressen en Gebouwen) "
                     "via the PDOK Locatieserver. Source: Kadaster / PDOK.",
             "licence": "BAG is published as open data (Public Domain Mark 1.0 per data.overheid.nl); "
                        "credited here under CC BY 4.0 terms as a precaution",
             "licence_url": "https://creativecommons.org/licenses/by/4.0/",
             "url": "https://www.pdok.nl/ogc-apis/-/article/pdok-locatieserver"},
        ],
        "disclaimer": "Not affiliated with, or endorsed by, DUO, CBS, Kadaster, PDOK or the Inspectie van het Onderwijs. DUO hides counts below 5 "
                      "(shown as null); shares and pass rates computed from partial data are flagged.",
    }
    old_path = os.path.join(OUT, "meta.json")
    if os.path.exists(old_path):           # keep the features block written by 14_features_meta.py
        try:
            prev = json.load(open(old_path, encoding="utf-8"))
            if "features" in prev:
                meta["features"] = prev["features"]
        except ValueError:
            pass
    write_json_atomic(os.path.join(OUT, "meta.json"), meta)
    print("meta.json written; address match rate", meta["geocoding"]["address_match_rate"])


if __name__ == "__main__":
    main()
