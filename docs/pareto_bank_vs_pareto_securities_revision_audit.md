# Bolagsidentitet och estimatmomentum – Pareto Bank vs Pareto Securities

**Status:** 22 oktober 2026, historisk granskning. INTE KÖPSIGNAL.
**Syfte:** rätta en riskfylld sammanblandning av bankaktien PARB
och analyshuset Pareto Securities (som bevakar Elekta).

## 1. Skilda rättssubjekt

| Roll | Juridiskt/kommersiellt namn | Aktie | ISIN | MIC |
|---|---|---|---|---|
| Analysobjekt | Pareto Bank ASA | PARB | NO0010397581 | XOSL |
| Analyshus som sänker bankens mål | DNB Carnegie | – | – | – |
| Analysobjekt | Elekta AB B | EKTA B | SE0000163628 | XSTO |
| Analyshus som ändrar Elektas mål | Pareto Securities | – | – | – |

Ingen bankriktkurs får påverka Elektas riktkursmomentum.

## 2. Pareto Bank: verklig negativ revidering

Den 13 oktober 2026 sänkte **DNB Carnegie** bankens 12-månadersriktkurs
**60 → 50 NOK (−16,67 %)** med bibehållen rekommendation **behåll**.
Samtidigt sänkte analyshuset sina egna vinstprognoser (EPS):
**2026: −18 %; 2027: −13 %**, främst på grund av högre förväntade
kreditförluster. Finansavisen redovisade ett förväntat
helårsbelopp **607 miljoner NOK** mot tidigare **537 miljoner**.

Dessa EPS-sänkningar gäller DNB Carnegies **egna estimat**,
inte nödvändigtvis marknadens samlade EPS-konsensus. Q3-rapporten
presenteras **29 oktober 2026** enligt bankens börsmeddelande.

Källor:
- https://www.finansavisen.no/tdn/2026/10/13/06603393/pareto-bank-dnb-carnegie-nedjusterer-kursmal-til-50-60
- https://www.finansavisen.no/finans/2026/10/14/8387621/dnb-carnegie-spar-tapsbombe-i-pareto-bank
- https://newsweb.oslobors.no/message/683626

**Preliminär slutsats:** Nej till en automatisk köpsignal
enbart för att PARB har fallit eller förefaller billigt.
Nästa rapport och utfallet i kreditförluster är centrala.

## 3. Elekta: Pareto Securities hade både sänkt och höjt

Den 29 maj 2026 sänkte Pareto Securities Elekta:
**70 → 65 SEK (−7,14 %)**, men upprepade köp.

Den 28 augusti 2026 höjde samma analyshus Elekta:
**65 → 68 SEK (+4,62 %)**, och upprepade köp.

Sammanlagt för båda ändringarna: **70 → 68 SEK (−2,86 %)**.
Över de senaste 90 dagarna är den enda observerade ändringen
från analyshuset däremot positiv. Under 30 dagar:
**ingen observerad ny ändring** – inte ett neutralt estimat.

**Morningstars Elekta-fair value 100 → 80 SEK är en
separat DCF-värdejustering** och får inte blandas in i
Pareto Securities eller bankernas 12-månadersriktkurser.

Källor:
- https://efn.se/elekta-far-sankt-rekommendation-se-dagens-rekar
- https://www.placera.se/nyheter/nagra-hojda-riktkurser-for-elekta-efter-rapporten-2026-08-28

## 4. Vad systemet nu måste validera

- ISIN + primärhandelsplats (MIC) + symbol + analyshus identiskt för varje
  historiskt revisionssteg.
- Samma valuta, välbelagda tidigare och nya riktkurser, källdatum.
- Historisk revisionskedja konsekvent (nytt pris föregående gång
  är gammalt pris nästkommande gång).
- Separata trendmått på 30, 90 och 180 dagar, där saknat underlag
  redovisas som `NO_OBSERVED_CHANGE`, aldrig som `FLAT`.
- Separat historik för *analyshusets egna EPS-revideringar* och
  för **hela marknadens** EPS-konsensus.
- Ingen 100-poängs buy-score förrän hela v2-due diligence (riktkurser,
  nettoskuld, kvalitet i kassaflöde, insiderförändringar, blankningsgrad
  och trend, realtidsverifiering och stop/target) är gjord.

Kod:
- `src/analyst_target_history.py`
- `data/pareto_company_broker_disambiguation_2026_10.json`
- `tests/test_analyst_target_history.py`
- `src/swedish_investment_due_diligence.py`

**Begränsning:** Bevisar historiska publika revisoner, inte att alla
analyshus eller konsensusdata undersökts. Ingen position öppnas;
tidigare preliminära poäng är inte ett köpgodkännande.
