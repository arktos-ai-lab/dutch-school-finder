"""Step 19: download the open files used by steps 20 to 23 (skips files already present).

New sources (all checked 2026-11-20, see pipeline/README.md "Licences of the step 19 files"):
  - Inspectie van het Onderwijs: leerresultaten PO, schorsingen en verwijderingen, schoolweging PO, excellente scholen
    (the four pages carry the page metadata DCTERMS.rights = "CC0 1.0 Universal")
  - Rijksoverheid: schoolvakanties per schooljaar and vakantieregio (JSON, licence field "CC0 1.0 Universal")
  - DUO: functiemix instellingen (staff composition per institution), bevoegde gezagen BO/SO/VO (board names)

Entries are added to raw/MANIFEST.json (URL, size, sha256). Polite: one request per ~2 s, retry with backoff (http_get),
each file is written to a .part file, fsynced and renamed, and the manifest is rewritten after every file, so an interrupted
run resumes by skipping what is on disk. A failed optional file is logged and skipped. Never put an email address here.
"""
import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RAW, http_get, write_json_atomic

INSP = "https://www.onderwijsinspectie.nl/site/binaries/site-content/collections/documents/"
RO = "https://opendata.rijksoverheid.nl/v1/infotypes/schoolholidays/schoolyear/%s?output=json"
DUO = "https://onderwijsdata.duo.nl/dataset/"
FILES = {
    "inspectie_leerresultaten_po_2026.ods": INSP + "2026/10/13/leerresultaten-primair-onderwijs-2024-2025-en-2026/"
                                                   "-20261030-gemiddelde-referentieniveaus-per-school-2324-2425-2526-open-data.ods",
    "inspectie_schorsingen_2025-2026.ods": INSP + "2026/10/19/schorsingen-en-verwijderingen-schooljaar-2025-2026/"
                                                  "schorsingen-en-verwijderingen-2025-2026.ods",
    "inspectie_schoolweging_po_2022-2025.ods": INSP + "2026/02/09/schoolweging-2022-2023---2023-2024---2024-2025/"
                                                      "schoolweging-2022-2023-2024.ods",
    "inspectie_excellente_scholen_2026.pdf": INSP + "2022/06/27/overzicht-excellente-scholen-2020-tot-1-juli-2026/"
                                                    "overzicht-scholen-predicaat-excellente-scholen-2020-tot-1-juli-2026.pdf",
    "duo_functiemix_instellingen.csv": DUO + "68f23148-ceba-4e3d-b11e-594f4eadca4d/resource/8f781c95-8e1b-470f-9596-edcffc11cf0a/download/functiemix-instellingen.csv",
    "duo_besturen_bo.csv": DUO + "786f12ea-6224-42fd-ab72-de4d7d879535/resource/d06cc759-ec8c-4430-91ad-14631b6c7bed/download/besturenbo.csv",
    "duo_besturen_so.csv": DUO + "033ab279-8e6f-44a2-8455-6ad42147762f/resource/cb92b932-6b7f-4948-b405-4dd97e561aba/download/besturenso.csv",
    "duo_besturen_vo.csv": DUO + "c8e6ffdd-cc2b-44ee-880f-0ff03f72e868/resource/bfc13171-de6b-4a3b-a095-e05d312107c4/download/besturenvo.csv",
}
for y in ("2025-2026", "2026-2027", "2027-2028"):
    FILES["schoolvakanties_%s.json" % y] = RO % y


def looks_bad(data, name):
    head = data[:600].lstrip().lower()
    if name.endswith((".ods", ".xlsx")):
        return data[:2] != b"PK"
    if name.endswith(".pdf"):
        return data[:4] != b"%PDF"
    if name.endswith(".json"):
        return not head.startswith(b"{")
    return head.startswith(b"<!doctype") or head.startswith(b"<html")


def main():
    man_path = os.path.join(RAW, "MANIFEST.json")
    man = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}
    for local, url in FILES.items():
        p = os.path.join(RAW, local)
        if not os.path.exists(p) or os.path.getsize(p) < 500:
            try:
                data = http_get(url, timeout=240)
            except Exception as e:                      # noqa: BLE001 - optional file, report and go on
                print("SKIP (download failed)", local, e)
                continue
            if looks_bad(data, local):
                print("SKIP (not a data file)", local)
                continue
            tmp = p + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
            time.sleep(2.0)
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        man[local] = {"url": url, "bytes": os.path.getsize(p), "sha256": h}
        write_json_atomic(man_path, man)                 # checkpoint after each file
        print("ok", local, os.path.getsize(p))


if __name__ == "__main__":
    main()
