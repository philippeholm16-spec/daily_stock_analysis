> **ARKIVERAT / ERSATT SOM KOPRANKNING 22 OKTOBER 2026**: Den manuella 100-poangslistan nedan saknade samlad broker-riktkursmomentum, fulla vinstestimatrevideringar och systematisk FI-blankningsgranskning. De angivna poangen kan enbart anvandas som historiska undersokningsnoteringar, inte som vardering av dagens koplage. Anvand `docs/stockholm_revision_first_due_diligence_2026_w43.md` och `scripts/weekly_revision_audit.py` for den uppdaterade forskningsbedomningen. Inga affarssignaler ar aktiva.\n\n# Stock Analyst: Fundamental veckorankning – 2026-W43 (22 oktober 2026)

Detta är ett separat **manuellt forskningsbetyg** för ett urval av sju
Nasdaq Stockholm-aktier, inte den tidigare tekniska Stock Analyst-analysen
och inte en rekommendation om att köpa idag.

## Viktning (100 poäng)

| Faktor | Max | Vad vi väger |
| --- | ---: | --- |
| Värdering och säkerhetsmarginal | 30 | Historiska och framåtblickande vinsttal, FCF, rabatt mot välmotiverat substans-/fair value, multipel och estimatosäkerhet |
| Operativ kvalitet | 25 | Omsättning/order, marginaler, kassaflöde, skuldsättning, stabilitet |
| Verifierbar katalysator | 15 | Rapport, avknoppning, orderingång, förändring i lönsamhet; aldrig pressens köpstämpel |
| Köplägets timing | 20 | Kursfallets storlek, rapportreaktion, likviditet, stöd/motstånd, volatilitet och eventrisk |
| Begränsad nedsiderisk | 10 | Högre betyg endast när balansräkning, vinstrisk och cyklicitet ger bättre riskskydd |

Alla delfaktorer granskas med kommenterade HTTPS-källor i
`data/swedish_research_2026_w43.json`. Poängen är subjektiva
bedömningar av de redovisade uppgifterna, **inte en objektivt
kalibrerad sannolikhet** för kursuppgång. En tidnings köprekommendation
ger inga poäng i sig.

## Faktiskt granskade aktier i veckans lilla urval

| Rang | Aktie | Värdering/30 | Kvalitet/25 | Katalysator/15 | Timing/20 | Riskskydd/10 | Summa/100 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | SKF B | 20 | 21 | 13 | 15 | 7 | **76** |
| 2 | ABB | 17 | 24 | 14 | 13 | 6 | **74** |
| 3 | Skanska B | 22 | 17 | 11 | 14 | 6 | **70** |
| 4 | Elekta B | 27 | 13 | 11 | 13 | 5 | **69** |
| 5 | Ericsson B | 16 | 18 | 11 | 10 | 6 | **61** |
| 6 | Essity B | 19 | 14 | 8 | 11 | 7 | **59** |
| 7 | Evolution | 21 | 15 | 8 | 6 | 3 | **53** |

Samtliga referenskurser är **den 21 oktober 2026**, inte realtidskurser
från Nasdaq Stockholm den 22 oktober. Färska rapporter 22 oktober
(t.ex. Essity) har bedömts i kvalitets- och katalysatorfälten, men
ingen pågående börskurs har verifierats mot rapportsvaret.

SKF:s Q3 den 21 oktober visade 4,3 % organisk tillväxt och 16,3 %
justerad rörelsemarginal. SKF Vertevo väntas noteras 1 december 2026.
ABB:s Q3 den 20 oktober visade rekordordrar (+40 %) och högre EBITA
(+24 %), men omkring 31–33x P/E på senaste vinsten, så **ett fall på
10 % innebär inte automatiskt undervärdering**. Elekta har störst
*analytikeruppskattad rabatt* (Morningstar, fair value 80 kr), men
fortsatt svag omsättning och Kina. Skanska har en möjlig SOTP-rabatt
och rapporterar Q3 först 5 november. Evolution rapporterar Q3 redan
23 oktober – betydande rapportgaprisk.

## ABB – observationer före nästa eventuella köp

Stängning 21 oktober: ca 860,6 kr. Historiskt rapportdagslägsta
20 oktober: 837,0 kr. Nära motstånd, endast observationer från de
senaste dagarnas OHLC: cirka 875 kr och 887 kr. En fortsatt rörelse
under 837 kr är ett tecken på att fallet inte stabiliserats; en
återhämtning över 875–887 kr med högre omsättning skulle ge ett
bättre tekniskt underlag att analysera. Dessa siffror är **inte**
verifierade köp-/stoppnivåer.

ABG Sundal Collier: riktkurs 1 000 kr (höjning till köp 21/10).
Pareto Securities: riktkurs 1 100 kr (köp upprepas, riktkurs sänks).
Detta är **andras prognoser och inte botens tekniskt härledda målkurser**.
Abb:s pris på ca 860,6 kr motsvarar ungefär +16,2 respektive +27,8 %
för uppgång till de riktkurserna, före courtage och risk.

## Viktig skillnad från Stock Analysts köpsignaler

**Veckobetyg 75+** betyder endast `PRIORITERAD_FUNDAMENTAL_BEVAKNING`,
65–74 betyder intressant men avvakta, och under 65 är lägre
veckoprioritet. Ingen nivå blir automatiskt `KÖP IDAG`.

Även den högst rankade aktien måste **separat**:
- klara Stock Analysts tekniska `VERY_GOOD`-grind (85/100),
- ha tillräcklig färsk pris-/volymhistorik och verifierad XSTO-kurs,
- ha strukturellt observerad stop-loss och målkurs,
- klara risk/reward minst 2:1 efter courtage/spread/slippage,
- hålla risken högst 1 % av det konfigurerade tradingkapitalet.

Veckopoängen är **inte en sannolikhet att stiga idag**, inte heller
ett tillstånd att skicka Telegram-affärslarm. Historik för den verkliga
träffsäkerheten måste byggas över ett större urval och flera
icke-överlappande tidsperioder.

## Återskapa rankningen

```sh
python -m scripts.weekly_value_board \
  --file data/swedish_research_2026_w43.json \
  --as-of 2026-10-22T12:00:00+02:00
```

CI validerar poängsumma, faktakällor, XSTO-identitet, kursens tidsstämpel,
dubletter, att veckan inte blandas och att ingen handelssignal skapas.
Modellen kan senare få faktorsiffror automatiskt från finansiella API:er
när källor och datakvalitet är verifierade.

## Urval och källor

Endast **sju undersökta aktier** ingår, inte en komplett börsscreening,
och IPO, First North och småbolag är inte systematiskt kontrollerade.
Beloppen i veckorankningen beskriver heller inte användarens privata
portfölj – inget sådant har lagrats i ett offentligt GitHub-repository.

- ABB Q3 2026: https://www.abb.com/global/en/news/139696/q3-2026-results
- ABB kursserie: https://stockanalysis.com/quote/sto/ABB/history/
- ABB analytiker 21 oktober: https://efn.se/dagens-rekar-abb-kopstamplas-sankt-riktkurs-for-storbanken
- SKF Q3 2026: https://www.mfn.se/cis/a/skf/skf-q3-2026-improved-margin-and-selectively-higher-demand-033ff65f
- SKF Vertevo: https://www.skf.com/ph/investors/skf-as-an-investment/separation-of-automotive
- Elekta Morningstar: https://global.morningstar.com/sv/aktier/stockholmsbrsen-r-vervrderad-bara-en-aktie-r-undervrderad
- Elekta Q1 2026/27: https://ir.elekta.com/sv/investerare/pressmeddelanden/2026/forsta-kvartalet-majjuli-202627/
- Skanska värderingsargument: https://efn.se/efter-skanskas-mandagsras-storbanken-vander-till-kop
- Essity Q3: https://www.marketscreener.com/news/essity-report-q32026-report-eng-ce785cd9de88f720
- Ericsson Q3: https://www.ericsson.com/sv/press-releases/2026/10/ericsson-reports-third-quarter-results-2026
- Evolution Q3-kalender: https://se.marketscreener.com/kurs/aktie/EVOLUTION-AB-58808466/kalender/
