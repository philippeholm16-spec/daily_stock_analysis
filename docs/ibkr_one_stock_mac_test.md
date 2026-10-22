# Stock Analyst – testa en svensk aktie med IBKR på Mac

**Pilot:** Volvo B, ISIN `SE0000115446`. Kontrollera alltid aktieslaget mot
en aukktoritativ Nasdaq-lista innan köpbeslut. Alla anrop är read-only.
Ingen handel, kontoinformation, Telegram-leverans eller betalning sker här.

## Förutsättningar

- IBKR-konto eller IBKR-demo/papperskonto, TWS eller IB Gateway på **din
  Mac**, och API tillåtet för `127.0.0.1`. För **verkliga** realtidskurser
  behövs uttrycklig Nasdaq Nordic Level 1-behörighet och tillåtna villkor
  för automatiserad intern analys; en demo eller paper-login räcker inte
  i sig. Abonnemang aktiveras inte av våra skript.
- I TWS: **Global Configuration → API → Settings → Enable ActiveX and
  Socket Clients**. Behåll **Read-Only API** aktiverat och
  **Allow connections from localhost only**. Välj port som matchar
  din TWS/Gateway-konfiguration: vanliga standardportar
  TWS paper `7497`, TWS live `7496`, Gateway paper `4002`,
  Gateway live `4001`. Ingen port-forwarding.
- Python 3.11 eller senare. Installera IBKR:s officiella Python-API från
  deras TWS API-distribution (med tillhörande licensvillkor) i en virtuell
  miljö, eller följ den aktuella dokumenterade `ibapi`-installationen.
  Ladda **inte** ner inloggningsfiler eller hemligheter till GitHub.
- Vi fortsätter handla manuellt på **Avanza**.

Officiella installationssidor:
https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/
https://www.interactivebrokers.eu/campus/trading-lessons/accessing-the-tws-python-api-source-code/
https://www.interactivebrokers.com/docs/tws-api/contracts/contracts-specified-by-cusip-figi-or-isin

## 1 – Ladda utvecklingsgrenen

I Terminal på Mac:

```sh
git clone --branch feature/swedish-market-scanner \
  https://github.com/philippeholm16-spec/daily_stock_analysis.git
cd daily_stock_analysis
python3 -m venv .venv
source .venv/bin/activate
```

Installera därefter **IBKR:s officiella `ibapi`** enligt deras TWS API-anvisning
i samma aktiva Python-miljö. Du kan verifiera med:

```sh
python -m pip show ibapi
```

## 2 – Kontrollera att TWS/Gateway är igång

```sh
python -m scripts.ibkr_one_stock_preflight --port 7497
```

Utfallet `ready_for_isin_lookup: true` innebär **bara** att Python-paketet
finns och att en lokal socket svarar. Det är inte ett bevis på inloggning,
Nasdaq-behörighet, levande kurser eller en accepterad strategi.

Vid fel `tws_or_gateway_local_socket_not_reachable` kontrollerar du att
TWS är igång, socket-klienter är tillåtna och att porten stämmer.

## 3 – Hitta verkligt IBKR-kontrakt via ISIN

```sh
python -m scripts.ibkr_contract_lookup --isin SE0000115446 --port 7497
```

Vid ett unikt och säkerställt kontrakt får du
`ISIN_VERIFIED` samt `instrument.conid` och IBKR:s egna
symbol-/börsbeteckningar. `primary_exchange_unverified` är **inte**
ett bevis på att en framtida tick kommer från XSTO.

Om IBKR inte lämnar ISIN i `ContractDetails.secIdList` avbryts
identifieringen. Vi gissar aldrig kontrakts-ID.

## 4 – Ett verkligt tick-/orderbokstest (read-only)

När steg 3 har returnerat ett verifierat `conid` och du har **bekräftat
primär Nasdaq-venue** för detta instrument hos IBKR, kör:

```sh
python -m scripts.ibkr_local_live_probe \
  --conid DITT_VERIFIERADE_CONID \
  --isin SE0000115446 \
  --symbol 'VOLV B' \
  --exchange-code VERIFIERAD_IBKR_NASDAQ_KOD \
  --port 7497 \
  --duration 50
```

Ersätt platshållarna, inklusive börskoden, med kontrollerade verkliga värden.
Blanda inte symbol och aktieslag. Ingen användaridentitet eller IBKR-
åtkomstnyckel ska skickas i chatten.

Skriptet **avslår realtidsstatus som standard** även om ticks kommer:
operatören måste separat verifiera utgivarens kontrakt/ISIN,
Nasdaq-börskod, relevant L1-abonnemang och att intern botanalys omfattas
av avtalet. När dessa faktorer verkligen är verifierade kan de tre
manuella bekräftelseflaggorna anges (`--help`), men flaggorna **kontrollerar
inte licensavtalet automatiskt**.

För godkännande krävs bland annat:
- IBKR meddelar `marketDataType == 1` (inte delayed=3);
- färska trade-/booktidsstämplar under ordinarie Stockholmsbörs;
- både bid och ask härledda ur verifierade IBKR SmartComponents-börskoder;
- de prisnivåer som kommer från streamad BBO och tickByTick överensstämmer;
- korrekt, entydigt IBKR `conid` och ISIN;
- ingen handelsstoppad aktie och giltiga rättigheter.

Fältet `live_primary_quote_verified` ska vara `true` **först när alla
kontroller passerar**. Om inte, dela gärna endast `status`, `reasons`,
IBKR:s numeriska felkoder och `live_primary_quote_verified` för felsökning.
Skicka aldrig kontouppgifter, API-hemligheter eller privata tokens.

## 5 – Prova Stock Analysts Telegram-format utan att skicka

Spara en **nyligen beräknad**, aktieslagsverifierad Stock Analyst-analys
som lokal JSON, `analyst_result.json`, och ange vid steg 4:

```sh
  --analysis-file analyst_result.json
```

Kommandot genererar en förhandsvisning **endast** om realtidsdata, frisk
teknisk analys, mål, stop och 1%-risk är godkända. Det skickar **inte**
Telegram och placerar aldrig order.

## Begränsningar och rättighetskontroll

GitHub Actions kör inte inne på din Mac och kan inte nå
`127.0.0.1:7497` hos dig. Därför kan de automatiska testerna bekräfta
kodens korrekthet men **inte** att ett verkligt IBKR-aktieabonnemang
levererar realtidskurser. IBKR:s tickByTick BidAsk anger ingen separat
börs; våra kontroller jämför därför motsvarande primärmarknadskodad
`reqMktData`-BBO och kräver bevis för både bid och ask.

IBKR:s datalicens kan skilja på visning, intern automatiserad (non-display)
användning och vidareförmedling. Granska avtalet innan tjänsten används
i kontinuerlig analys/Telegram. Det finns ännu **ingen aktiverad**
realtidsanslutning till vår GitHub-bot och `main` är oförändrad.
