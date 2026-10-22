# Stock Analyst – revision-first due diligence (2026-W43, 22 oktober)

## Status: EVIDENSBASERAD FORSKNING, INGA GODKANDA KOPLAGEN

Detta dokument ersatter **den tidigare preliminara veckopoangslistan**
`docs/stockholm_weekly_value_ranking_2026_w43.md` som beslutsunderlag.
Tidigare 76/100 SKF, 74/100 ABB, 69/100 Elekta var subjektiva
*research*-poang satta UTAN fullstandig revisions- och blankningsgranskning.
De ska **inte** betraktas som validerade dagens-kopbetyg.

Den nya kontrollen kallas `src/swedish_investment_due_diligence.py`.
Den visar `final_buy_opportunity_score: null` och
`actionable: false` om vinstrevidering, finansiella risker eller
verifierat Stockholmsbørs-pris saknas. Inget koep, inga order,
inga Telegram-aendringar och ingen merge till main.

## Varfoer positiva revisionsforandringar ar vaerd att foelja

En riktkurs pa 80 SEK trots ett aktiepris pa 55 SEK kan betyda
uppsida, men ocksa att en gammal analys inte hunnit uppdateras.
En sankt riktkurs kan indikera att framtida resultat kommer senare
eller blir lagre. Vinstprognosens faktisk **foeraendring** ar da
ofta mer relevant an aktiens statiska rabatt.

Vetenskapligt underlag:

- Asquith, Mikhail & Au, Journal of Financial Economics (2005):
  rekommendations-, prognos- och riktkursforandringar medfoer
  marknadsreaktioner; ej en garanti for framtida avkastning.
  https://www.nber.org/papers/w9246
- Chen m.fl., Journal of Business Finance & Accounting (2020):
  vinstprognosrevideringar uppvisar seriellt momentum, men styrkan
  varierar med nyhets- och informationsmiljon.
  https://doi.org/10.1111/jbfa.12491
- Empiriska studier visar aven att efterreaktioner kan bli svagare
  med battre marknadseffektivitet och transaktionskostnader.
  https://www.sciencedirect.com/science/article/pii/S0304405X15001713

Detta aer motiv foer kontroll, inte en kaend statistisk
sannolikhet foer uppgang pa Nasdaq Stockholm i dag.

## Tre skilda datatyper, aldrig sammanblandade

1. **Moeklarnas riktkursrevideringar:** samma analyshus foer och
   efter i samma valuta och foer samma aktie. Senaste haendelsen
   per analyshus under 90 dagar ger en roest. Uppenbara
   valuta- och depabevissymbolfel maste avvisas vid datainsamling.
2. **Morningstars upplevda fair value / DCF:** en separerad
   analytikermodell med laengre horisont. Sankt fran 100 till 80
   kr den 18 september aer −20 % i MORNINGSTARS MODELL,
   INTE −20 % foer alla maeklares konsensusriktkurs.
3. **Vinstprognosrevision (EPS/EBIT/EBITA/FCF):** jaemfoer
   foeraendringar 30/90 dagar foer EXAKT samma raekenskapsar,
   resultatdefinition och aktieslag samt rapportera antalet
   analyshus. Detta är PRIORITERAT men faktiska tidsserier
   har **INTE** kunnat verifieras foer de tre bolagen.

## Verifierat urval av riktkursrevideringar

Alla observationer nedan kommer fran daterade sammanstaellningar
av broker-nyheter, INTE analytikernas fullstaendiga egna modeller.
Urvalet ar inte en fullstaendig analytikerkonsensus.

| Aktie | Höjningar/sänkningar (senaste per hus, 90 dagar) | Signal |
|---|---:|---|
| **SKF B** | 12 / 1 | Brett positivt riktkursmomentum |
| **Elekta B** | 3 / 3 | Blandat riktkursmomentum |
| **ABB** | 0 / 3 (särskilt 21 okt) | Negativt riktkursmomentum efter Q3 |

Exempel SKF:
- 16 okt SEB 251 -> 285 kr
- 15 okt SHB 290 -> 310 kr
- 15 okt DNB Carnegie 290 -> 315 kr
- 13 okt Goldman Sachs 229 -> 226 kr
Källa: https://www.borskollen.se/aktie/skf/riktkurs

Exempel Elekta:
- 1 sep Barclays 44,5 -> 45,5 kr (FORTFARANDE undervikt!)
- 28 aug Pareto 65 -> 68 kr, SB1 Markets 59 -> 60 kr
- 19 aug Nordea 65 -> 63 kr
- 18 aug SEB 58 -> 57 kr
- 29 jul Goldman Sachs 55 -> 50 kr
- 18 sep Morningstar DCF fair value 100 -> 80 kr (REDOVISAS
  SEPARAT, EJ brokerriktkurs)
Källor:
https://www.borskollen.se/aktie/elekta/riktkurs
https://global.morningstar.com/sv/aktier/stockholmsbrsen-r-vervrderad-bara-en-aktie-r-undervrderad

Exempel ABB, 21 okt:
- ABG Sundal Collier 1 025 -> 1 000 kr; uppgraderade
  separat rekommendationen BEHALL till KOP
- Pareto 1 150 -> 1 100 kr; upprepade KOP
- Handelsbanken USD 105 -> USD 94; upprepade BEHALL
  (USD->USD i eget hus ar tillatet som procentuell revidering,
  men USD- och SEK-belopp blandas ALDRIG som snittkurs).
Källor:
https://efn.se/dagens-rekar-abb-kopstamplas-sankt-riktkurs-for-storbanken
https://www.borskollen.se/aktie/abb

**OBS**: Brokerarnas riktkurser aer grova uppskattningar.
Att de foer SKF hojdes trots att aktiekursen redan stigit
visar INTE att naesta dags avkastning gar att forutsa.
ABB:s riktkurser ligger fortfarande oever marknadskursen men
deras negativa aendring efter Q3 aer betydelsefull.

## Blankningslaege (FI 20 oktober)

- **Elekta**: FI-rapporterad summa ca **15,39 %** av
  aktiekapitalet. Viktig risk; en kortsiktig blankningsnedgang
  aer inte ensamt ett koepskael.
- **SKF**: FI-rapporterad summa ca **7,37 %**, ocksa vaesentligt.
- **ABB**: en gammal siffra från mars 2025 ar inte
  en faersk observation och kan INTE anvandas som 0 % nu.
  Faersk FI-verifiering saknas i datamaterialet.

Primarkalla: https://fi.se/sv/vara-register/blankningsregistret/

Siffrorna galler **rapporterade korta nettopositioner**,
inte alla enskilda blankningstransaktioner eller ett fullstandigt
kortfattat maatt av verklig negativ attityd. Historik maaste
ha samma FI-meetod/grans for att en trend skall kunna beraknas.

## V2 planerad vaegning (100 poaeng) – ingen automatisk poaeng idag

| Faktor | Max |
| --- | ---: |
| Värdering med stresstester | 15 |
| Verksamhet och vinstkvalitet | 20 |
| Reviderade **vinstprognoser** (samma år/bas) | **20** |
| Reviderade **mäklarriktkurser** (separata per hus) | **15** |
| FI-blankning, nivå och trend | 10 |
| Skulder och kassaflöde | 10 |
| Observerat tekniskt ingångsläge | 5 |
| Händelser, rapport- och katalysatorrisk | 5 |
| **Totalt** | **100** |

En rankning får **inte** visa ett slutligt 0–100-tal när nödvändiga
data saknas. `final_buy_opportunity_score: null` ar korrekt foer
alla tre bolagen i W43. Underliggande kaellor maaste identifiera ISIN
och ticker pa samma aktieslag; old-/new-riktkurser jamfoers i
egen valuta och aldrig med Morningstar som proxy foer maeklarna.

## Obligatoriskt granskningsprotokoll innan riktiga affarer

For varje ny aktie:
- Verify ID: XSTO / ISIN, B-/A-aktie, nyheter om rätt bolag.
- Bolagsresultat: tillvaext, justerade OCH redovisade vinster,
  engangs-, valutakurs- och kassafloeeffekter.
- Valuation: EPS/EV/EBITA/FCF/DCF med pessimism, base och optimism,
  estimathistorik – inte statisk rapporteringssiffra.
- Prognoser: 30/90 dagar per maeklare samt trend i faktiskt EPS/
  EBIT-konsensus för identiskt prognosår.
- FI: aktuell rapporterad blankning, förändring 7/30/90 dagar,
  antal och storlek; aggregerad data och sma offentliga delposter
  far inte blandas.
- Finansiell risk: nettoskuld, skuldfall, raenta, covenants,
  justeringar, kassafloede, utspädning och emissioner.
- Insider/aegare: nykoep, forsäljningar, storägare, transaktioners
  tidsstämplar, enligt FI:s insynsregister.
- Timing: rapportkalender, kursvolym, verklig XSTO spread,
  historiska stoed/motstand, nettorisk, risk/reward, courtage.
- Portfoelj: sektoroeverlapp mot Avanza Global/Zero,
  kapitalbindning, riskspridning, skatter och händelserisk.
- Beslut: enbart vid komplett underlag, separat teknisk
  `VERY_GOOD`-grind och godkaent live-kurs. Ingen AI-order.

## Körbar källspårbar researchaudit

```sh
python -m scripts.weekly_revision_audit \
  --file data/swedish_revision_evidence_2026_w43.json \
  --as-of 2026-10-22T14:40:00+02:00
```

Koden publicerar de observerade revisionsuppgifterna plus
`missing_risk_modules`; `ready_to_buy_count` ska vara 0.

Status: endast arbetsgrenen `feature/swedish-market-scanner`.
Ingen avtalsbunden realtidsdataström, ingen komplett Nasdaq-scanner,
ingen aktivering av Telegram eller inköpsorder.
