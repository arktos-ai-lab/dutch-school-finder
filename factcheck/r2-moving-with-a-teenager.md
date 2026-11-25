# r2 moving-with-a-teenager

RO = https://www.rijksoverheid.nl. Law text read from repository.officiele-overheidspublicaties.nl (BWBR0044212 WVO 2020, BWBR0045787 Uitvoeringsbesluit WVO 2020 = UB, BWBR0002628 Leerplichtwet 1969 = Lpw, versions of 2026-08-01). Checked 2026-11-25.

| Claim | Verdict | Basis |
|---|---|---|
| ISK is for pupils from 12 who arrived recently and speak little or no Dutch | correct | RO /onderwerpen/basisonderwijs/onderwijs-voor-nieuwkomers: "internationale schakelklassen (isk's) voor jongeren vanaf 12 jaar ... die sinds kort in Nederland zijn en nog geen of weinig Nederlands spreken". |
| ISK is free, as regular education | correct | Same page: secondary education in NL is free. Parents may still be asked to pay for extra activities. |
| ISK "on average about two years" | not verifiable | RO does not state an ISK length. The only two-year figure is for a tijdelijke nieuwkomersvoorziening (funding for the first 2 years, enrolment no more than 2 years in total). VO-raad page (pointer only) returned HTTP 500. Suggest: "How long a pupil stays depends on the pupil. A newcomer provision can enrol a pupil for at most two years in total." |
| tto: at least half of lessons in lower years of havo/vwo, 30 percent in vmbo | correct | RO tto Q&A: "minstens 50% van de lessen" in the onderbouw for havo/vwo, 30% for vmbo. |
| Exams in Dutch, regular diploma plus a certificate | correct | Same RO page. |
| Nuffic evaluation not legally binding, usually at least 10 working weeks, universities decide admission | correct (waiting time as of Nov 2026) | Nuffic: "A credential evaluation is not legally binding." "...after at least 10 working weeks." "Dutch universities and universities of applied science determine themselves which students they admit." Cost is not on the page. |
| vmbo 4, havo 5, vwo 6 years | correct | Nuffic education system page. |
| Leerplicht ends at end of the school year in which the child turns 16, or earlier after 12 full school years | correct | Lpw art 3(1): ends "aan het einde van het schooljaar na afloop waarvan de jongere ten minste twaalf volledige schooljaren ... heeft bezocht" or "aan het einde van het schooljaar waarin de jongere de leeftijd van zestien jaar heeft bereikt". Art 3(2): finishing primary in under 8 years counts as 8. |
| "Every child who lives in the Netherlands must go to school, whatever the nationality" | correct | Lpw art 2 binds parents and carers, no nationality condition. WVO art 8.4(1)(b) admits foreign pupils under 18. Residence status is not addressed on the RO page. |
| Kwalificatieplicht: 16 and 17 year olds without havo, vwo or mbo 2 (or higher) must keep going to school | correct | RO: "Jongeren tussen 16 en 18 jaar die nog geen startkwalificatie hebben behaald zijn kwalificatieplichtig." Lpw art 4b: lasts until age 18 or startkwalificatie. Missing: holders of a praktijkonderwijs diploma and certain vso exit profiles are exempt (Lpw art 4a(2)). |
| They may not work full time; bbl counts | correct | RO: "Ze mogen niet voltijd werken." bbl: "kan hij leren en werken combineren". Lpw art 4a(1) names "een bij de wet geregelde combinatie van leren en werken". |
| "Mbo is free for students under 18" | partly correct | RO lesgeld/cursusgeld page: lesgeld and cursusgeld apply to students 18 or older on 1 August. So no tuition fee under 18, but books and materials are not free. Holds per study year, age on 1 August. Suggest: "Mbo has no tuition fee for students who are under 18 on 1 August. Books and materials may still cost money." The cited kwalificatieplicht page does not say this. |
| School abroad: Belgium or Germany, ask the leerplichtambtenaar for an exemption, report each year | correct | RO leerplicht-buitenlandse-school: "Woont u in Nederland en gaat uw kind naar school in België of Duitsland?" Exemption from the leerplichtambtenaar, proof of enrolment, "elk jaar opnieuw" tell the municipality. Lpw art 5(c) is the legal ground. |
| "The regular school decides on the level it will offer, looking at results and age" | partly correct | WVO art 8.6(1): the bevoegd gezag decides on admission. Art 8.6(2): admission to year 1 rests on the definitive school advice. UB art 8.3(1): "Indien voor een kandidaat-leerling geen definitief schooladvies ... is vastgesteld", the decision rests on a doorstroomtoets, and "Indien de leerling geen doorstroomtoets heeft afgelegd", on "een onderzoek naar de geschiktheid van de kandidaat-leerling". Nota van toelichting (Stcrt 2021, 46424): this can cover "leerlingen die zich vanuit het buitenland ... aanmelden". Suggest: "A pupil from abroad has no Dutch school advice. The school looks at a doorstroomtoets if the pupil took one. If not, it may run a suitability check. The school decides on admission and level." For years 2 and up the year-1 rules (art 8.5, 8.6(2)) do not apply. Age and results as factors are not named in the law text. |
| Register at more than one school; a school may take a few weeks to decide | correct | RO inschrijven VO: you may register at more than one school. WVO art 8.8(1): parents state at which other schools they applied. Art 8.8(2): decision within 6 weeks, a delay of at most 4 more weeks. |
| You can register during the school year | correct | RO inschrijven VO: if you move house you can register at any time of year. |
| Dutch returning teen has the same duties and rights | correct | Lpw art 2, WVO art 8.4(1)(a). School decides year and level: see the admission row. |

## Source links

- RO newcomers, leerplicht, school abroad, tto, Nuffic evaluation: load (RO URLs redirect to /themas/ or /documenten/ paths, still work).
- Nuffic system URL redirects to https://www.nuffic.nl/en/study-and-work-in-the-netherlands/education-in-the-netherlands. Update it.
- VO-raad (sector council, pointer only): HTTP 500 on fetch. Not needed for any claim; consider removing.
- Add the RO lesgeld page (https://www.rijksoverheid.nl/vraag-en-antwoord/middelbaar-beroepsonderwijs/hoogte-lesgeld-en-cursusgeld-mbo) for the under-18 mbo claim.

## Missing, important for expat parents

- Pupils from abroad have no Dutch advice: UB art 8.3 (above). Also WVO art 8.5(1)(b): a pupil from a primary school who turns 14 by the end of the school year can be admitted to year 1.
- Mbo entry (RO "Uit welke mbo-opleidingen kan ik kiezen"): entree (level 1) needs no prior diploma, minimum age 16 on 1 August. Levels 2 and 3 need a listed vmbo or mbo diploma, or "bewijs dat je de eerste 3 leerjaren van de havo of het vwo goed hebt doorlopen". That page does not cover foreign diplomas; say "ask the mbo school, Nuffic can evaluate".
- Kwalificatieplicht exemptions (praktijkonderwijs, vso profiles), Lpw art 4a(2).
- Dutch language support is not "extra ondersteuning" in the law: WVO art 8.9(1).
- WVO art 8.8(1): register in writing at least 10 weeks before the start "indien mogelijk".

Counts: correct 12, partly correct 2, not verifiable 1, wrong 0, outdated 0.
