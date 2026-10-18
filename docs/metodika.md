# HoodieMap skóre: metodika

**Verzia metodiky:** 0.5 (18. 10. 2026) · **Stav:** prototyp · **Kód:** `src/score.py`, `src/score_method.py`, `src/ahp.py`

Tento dokument popisuje, ako HoodieMap počíta skóre adresy, aby si výpočet mohol ktokoľvek overiť a zopakovať. Každé číslo v ňom má zdroj. Kde zdroj zatiaľ chýba, je to výslovne napísané a uvedené v časti [Otvorené body](#11-otvorené-body).

---

## 1. Zásady

1. **Meriame fakty, nie dojmy.** Vstupom sú merateľné údaje: vzdialenosť v metroch, plocha v hektároch, počet miest.
2. **Každý prah má zdroj:** norma (WHO, Natural England), publikovaná metodika (Walk Score) alebo výsledok expertného panelu.
3. **Váhy sú hodnotový úsudok, preto ich robíme priehľadne.** Pochádzajú z expertného panelu metódou AHP (časť 6). Kým panel neodpovie, platia **rovnaké váhy**, čo je predvolený postup podľa príručky OECD/JRC.
4. **Výpočet je opakovateľný.** Rovnaké dáta a rovnaká verzia metodiky dajú vždy rovnaký výsledok. Váhy sú uložené vo verzovanom súbore, nie v databáze.
5. **Ukazujeme výpočet.** Pri každom skóre je na stránke rozpis krok za krokom: fakt, čiastkové skóre, váha, body.
6. **Postup** vychádza z príručky *Handbook on Constructing Composite Indicators* (OECD a JRC, 2008): rámec, ukazovatele, normalizácia, váhy, agregácia, citlivosť.
7. **Rámec nevymýšľame:** čo meriame, určuje oblasť Prostredie dotazníka kvality života WHO (WHOQOL-BREF), časť 2.

## 2. Rámec: oblasť Prostredie podľa WHOQOL-BREF

**WHOQOL-BREF** je dotazník kvality života Svetovej zdravotníckej organizácie (WHO, Programme on Mental Health, 1996). Má 26 otázok, overený bol v 20 centrách v 18 krajinách. Kvalitu života delí na 4 oblasti: fyzické zdravie, psychické zdravie, sociálne vzťahy a **prostredie**.

**Oblasť Prostredie má 8 aspektov** a každý pokrýva v dotazníku jedna otázka. My **meriame objektívne podmienky** každého aspektu na adrese. Dotazník samotný **nepoužívame**: z WHOQOL-BREF preberáme len členenie na aspekty a pravidlá výpočtu oblasti, nie znenie otázok. Výpočet skóre od dotazníka nezávisí.

| Aspekt (WHOQOL) | Otázka | Čo meriame na adrese | Stav |
|---|---|---|---|
| F16 Bezpečnosť | Q8 | zistené trestné činy na 1 000 obyvateľov | áno, **len za kraj** (za okresy nie sú verejné tabuľky) |
| F17 Domáce prostredie | Q23 | obyvatelia na trvalo obývaný byt v obci alebo mestskej časti (sčítanie 2021) | čiastočne (chýbajú údaje o samotnom dome a byte) |
| F18 Finančné podmienky | Q12 | priemerná mesačná mzda a miera evidovanej nezamestnanosti v okrese | áno (chýbajú ceny bývania oproti príjmu) |
| F19 Zdravotná a sociálna starostlivosť | Q24 | lekár, lekáreň | čiastočne (chýba nemocnica, sociálne služby, dostupnosť autom) |
| F20 Informácie a vzdelávanie | Q13 | materská škola, základná škola, knižnica | čiastočne (chýba rýchlosť internetu) |
| F21 Rekreácia a voľný čas | Q14 | pomenovaný park, športovisko, kultúra, ihrisko, prírodná zeleň ≥ 20 ha do 2 km | áno |
| F22 Fyzické prostredie | Q9 | verejná zeleň ≥ 0,5 ha, podiel zelene do 300 m, Pokoj | čiastočne (Pokoj orientačný, chýba ovzdušie) |
| F23 Doprava | Q25 | pešia dostupnosť služieb (Pešo), zastávka MHD alebo vlak | čiastočne (chýba frekvencia spojov) |

Pešia dostupnosť je pod F23, lebo aspekt Doprava hodnotí, ako sa človek dostane, kam potrebuje. Bez auta sa to deje pešo a MHD.

### Výpočet profilu a indexu

1. **Ukazovateľ → čiastkové skóre 0–100** podľa normy alebo publikovanej krivky (časť 5).
2. **Aspekt = priemer jeho ukazovateľov s rovnakou váhou.** Vnútri aspektu môže váhy neskôr určiť AHP panel (časť 6).
3. **Index prostredia = priemer aspektov s rovnakou váhou.** Tak počíta oblasť aj samotný WHOQOL-BREF: priemerom položiek s rovnakou váhou (syntax `MEAN.6(Q8, Q9, Q12, Q13, Q14, Q23, Q24, Q25) × 4`).
4. **Index sa nepočíta, ak má dáta menej ako 6 z 8 aspektov.** Je to rovnaké pravidlo, aké WHOQOL-BREF používa pre túto oblasť (aspoň 6 z 8 položiek). Na Slovensku majú dáta všetky aspekty, takže index sa počíta. Mimo Slovenska chýbajú štatistiky území (F16–F18) a index sa nepočíta.

WHOQOL-BREF prepočítava oblasť na 0–100 vzorcom (priemer × 4 − 4) × 100/16, lebo jeho položky majú škálu 1–5. Naše čiastkové skóre sú už 0–100, preto ďalšie prepočítanie netreba.

### Skóre pre používateľa

Štyri skóre na stránke zostávajú ako zrozumiteľný pohľad na tie isté merania:

| Skóre | Otázka | Súvisí s aspektmi |
|---|---|---|
| **Pešo** | Čo vybavím bez auta? | F23 (a služby z F19, F21) |
| **Zeleň** | Koľko je okolo verejnej zelene a prírody? | F21, F22 |
| **Rodina** | Ako dobré je miesto pre rodinu s deťmi? | profil: všetkých 8 aspektov vážených pre rodinu (časť 6) |
| **Pokoj** | Ako ďaleko sú zdroje hluku? *(orientačné)* | F22 |

## 3. Dáta

- **Zdroj:** OpenStreetMap (© prispievatelia OpenStreetMap, licencia ODbL), v produkcii z lokálneho Overpass servera so slovenským extraktom z Geofabriku (aktualizovaný denne).
- **Jeden dopyt na adresu:**
  - miesta (obchody, školy…) do **2,5 km** ako body,
  - zeleň do **2 km** s geometriou plôch,
  - cesty a železnica do **600 m** s geometriou čiar,
  - bary do **200 m**.
- **Kvalita:** chýbajúce alebo neoznačené miesto v OSM skóre zníži. Stránka vždy uvedie, čo sa nenašlo.

### Štatistiky území (F16–F18)

Adresu priradíme k **obci alebo mestskej časti, okresu a kraju** podľa hraníc z OpenStreetMap (`regions/boundaries.json`, skript `scripts/build_regions.py`). Hranice nesú **úradné kódy**: kódy okresov a krajov sú rovnaké ako v DATAcube ŠÚ SR, obce a mestské časti majú kód ZÚJ zo sčítania (napr. Pezinok 508179). Štatistiky sa preto párujú cez kód, nie cez názov. Extrakt má 8 krajov, 79 okresov a 2 927 obcí a mestských častí, presne toľko, koľko ich má sčítanie 2021.

| Ukazovateľ | Úroveň | Obdobie | Zdroj | Výpočet |
|---|---|---|---|---|
| Zistené trestné činy na 1 000 obyvateľov | kraj (8) | 2025 | ŠÚ SR, DATAcube sk3003rr (trestné činy spolu, údaje MV SR) / om7102rr (stredný stav obyvateľstva) | trestné činy / stredný stav obyvateľstva × 1 000 |
| Obyvatelia na trvalo obývaný byt | obec / mestská časť (2926) | 2021 | ŠÚ SR, Sčítanie obyvateľov, domov a bytov 2021, Štatistický lexikón obcí (kap. IV) | počet obyvateľov / počet trvalo obývaných bytov |
| Priemerná mesačná mzda zamestnanca | okres (79) | 2025 | ŠÚ SR, DATAcube np3110rr (pracovisková metóda: podľa miesta práce) | hodnota z tabuľky |
| Miera evidovanej nezamestnanosti (PDU) | okres (79) | 2026-08 | ÚPSVaR, mesačná štatistika, tabuľka 1: podiel disponibilných UoZ na obyvateľstve v produktívnom veku | hodnota z tabuľky |

Hodnoty so zdrojom, obdobím a dátumom stiahnutia (2026-10-18) sú v `regions/stats.json` (skript `scripts/build_region_stats.py`). Kontrola: kriminalita v Bratislavskom kraji vychádza 10,12 a v Košickom 10,29 na 1 000 obyvateľov. SITA podľa MV SR uvádza 10,14 a 10,28; rozdiel je v tom, či sa delí stredným, alebo koncoročným stavom obyvateľstva.

**Zámerne nepoužité:**
- **Kriminalita za okresy:** MV SR ju zverejňuje len v mapách s rozpätiami (napr. „539–619 činov“), nie v tabuľke.
- **Dopravná nehodovosť** (DATAcube do3806rr): ukazovatele nemajú v tabuľke popisy (`NEH_ZRANENI`, `POC_USMRT`…) a ich význam by sme museli hádať.

### Ako rozpoznávame miesta (značky OSM)

| Kategória | Značky |
|---|---|
| Potraviny | `shop=supermarket, convenience, greengrocer, grocery` |
| Reštaurácie | `amenity=restaurant, fast_food, food_court` |
| Kaviarne | `amenity=cafe` |
| Obchody a služby | ostatné `shop=*` okrem `vacant` |
| Banka alebo pošta | `amenity=bank, post_office` |
| Park (pre Pešo) | `leisure=park` **s názvom**; vzdialenosť k okraju plochy |
| Škola (pre Pešo) | `amenity=school` |
| Základná škola (pre Rodinu) | `amenity=school` a názov obsahuje „základná“ alebo „ZŠ“, alebo `isced:level` 1, alebo `school=primary`; nie ZUŠ |
| Materská škola | `amenity=kindergarten, childcare` |
| Lekár | `amenity=doctors, clinic`, `healthcare=doctor` |
| Lekáreň | `amenity=pharmacy` |
| Kultúra a šport | `amenity=library, theatre, cinema, arts_centre, community_centre`; `leisure=sports_centre, fitness_centre, swimming_pool` |
| Ihrisko | `leisure=playground` |
| Verejná zeleň | `leisure=park, nature_reserve`; `landuse=forest, recreation_ground, village_green`; `natural=wood`; bez `access=private` |
| Zeleň pre podiel plochy | navyše `landuse=grass, meadow`, `natural=scrub, grassland` |
| Doprava (Pokoj) | `highway=motorway, trunk, primary, secondary, tertiary`; `railway=rail, light_rail, tram` (bez vlečiek) |
| Nočný život (Pokoj) | `amenity=bar, pub, nightclub` |

## 4. Vzdialenosť a chôdza

**Vzdialenosť chôdze = vzdušná vzdialenosť × 1,3.** Čas chôdze = vzdialenosť chôdze / 80 m za minútu.

Koeficient 1,3 vyjadruje, že ulice nevedú priamo. Rýchlosť 80 m/min (4,8 km/h) je bežne uvádzaná rýchlosť chôdze. Obe čísla sú zatiaľ **predpoklad** (časť 11). Nahradí ich skutočná trasa po uliciach (OSRM nad OSM).

## 5. Normalizácia: z faktu na čiastkové skóre 0–100

### Krivka chôdze (Pešo, Rodina)

Podľa publikovanej metodiky Walk Score: plný počet bodov do 5 minút chôdze, potom body rýchlo klesajú a po 30 minútach je nula. Medzi bodmi lineárne:

| Vzdialenosť chôdze | 0 m | 400 m | 800 m | 1 200 m | 1 600 m | 2 400 m |
|---|---:|---:|---:|---:|---:|---:|
| Podiel bodov | 100 % | 100 % | 72 % | 42 % | 18 % | 0 % |

Zdroj: walkscore.com/methodology (5 min = plné body, 30 min = nula); tvar krivky podľa prílohy E štúdie arXiv 2212.05192.

### Zeleň

| Časť | Čiastkové skóre | Zdroj |
|---|---|---|
| Verejná zeleň ≥ 0,5 ha blízko | 100 do 300 m vzdušne, 70 pri 500 m, 20 pri 1 000 m, 0 od 1 500 m | WHO Európa 2016 (≥ 0,5 ha do 300 m); Berlín a Holandsko (500 m) |
| Podiel zelene do 300 m | podiel zelených plôch v kruhu s polomerom 300 m / 30 %, najviac 100 | pravidlo 3-30-300 (30 % korún stromov); zelené plochy sú náhrada, kým nemáme dáta o korunách stromov |
| Les alebo veľký park | 100, ak je do 2 km plocha ≥ 20 ha; inak 0 | Natural England, ANGSt |

### Štatistiky území: percentil

Pre mzdy, nezamestnanosť, kriminalitu ani zahustenie bytov neexistuje norma ako pri zeleni („do 300 m“). Preto ich hodnotíme **poradím medzi všetkými územiami Slovenska rovnakej úrovne** (percentil):

**čiastkové skóre = 100 × poradie / (počet území − 1)**, kde poradie je 0 pre najhoršie územie; rovnaké hodnoty dostanú priemerné poradie. Pri ukazovateľoch, kde je menej lepšie (nezamestnanosť, kriminalita, obyvatelia na byt), sa poradie počíta od najvyššej hodnoty.

Príklad: okres Pezinok má mzdu 1 579 € (2025). Nižšiu má 31 zo 79 okresov, preto je čiastkové skóre 100 × 31 / 78 = 39,7.

Percentil hovorí, **ako je územie na tom oproti ostatným na Slovensku**, nie či je hodnota „dobrá“ v absolútnom zmysle. Pri F16 (8 krajov) je hrubý: všetky adresy v jednom kraji majú rovnakú hodnotu.

### Pokoj

Od 100 bodov odpočítavame za najbližší zdroj každého typu:

| Zdroj | Zrážka podľa vzdialenosti |
|---|---|
| Diaľnica, rýchlostná cesta | do 100 m −45, do 200 m −30, do 300 m −18, do 500 m −6 |
| Cesta I. triedy | do 50 m −30, do 100 m −20, do 200 m −10, do 300 m −4 |
| Cesta II. triedy | do 50 m −15, do 100 m −8, do 200 m −3 |
| Cesta III. triedy | do 30 m −8, do 60 m −4 |
| Železnica | do 100 m −25, do 200 m −12, do 300 m −5 |
| Električka | do 30 m −15, do 60 m −8, do 120 m −3 |
| Bary a kluby do 150 m | bar a krčma −5, klub −12, spolu najviac −25 |

**Tieto zrážky sú orientačný odhad, nie hlukový model.** Preto je Pokoj na stránke označený ako *orientačné*. Postup nápravy je v časti 7.

## 6. Váhy

### Pešo: váhy Walk Score

Za každú kategóriu sa započíta najbližších N miest, každé s vlastnou váhou:

| Kategória | Započítané miesta a ich váhy | Spolu |
|---|---|---:|
| Potraviny | 3 | 3 |
| Reštaurácie | 0,75 · 0,45 · 0,25 · 0,25 · 0,225 · 0,225 · 0,225 · 0,225 · 0,2 · 0,2 | 3 |
| Kaviarne | 1,25 · 0,75 | 2 |
| Obchody a služby | 0,5 · 0,45 · 0,4 · 0,35 · 0,3 | 2 |
| Banka alebo pošta, Park, Škola, Lekáreň, Kultúra a šport | po 1 | 5 |
| **Spolu** | | **15** |

Zdroj: váhy Walk Score podľa Brewster a kol. (2009). Potraviny vážia najviac, lebo sú najčastejším cieľom chôdze (Lee a Moudon, 2006). Pôvodné kategórie „kníhkupectvo“ a „zábava“ sme nahradili lekárňou a kultúrou a športom.

### Zeleň: tri časti s rovnakou váhou

Verejná zeleň blízko, podiel zelene a prírodná zeleň vážia po 33,3 %, rovnako ako ukazovatele vnútri aspektov WHOQOL.

### Profily: AHP panel, dovtedy rovnaké váhy

Index prostredia váži 8 aspektov rovnako (časť 2). **Profil** odpovedá na inú otázku: ako dobré je miesto pre konkrétny typ domácnosti. Tie isté aspekty preto váži inak.

| Profil | Otázka pre panel |
|---|---|
| Rodina s deťmi | Čo je pre rodinu s deťmi dôležitejšie v okolí domova? |
| Senior | Čo je pre staršieho človeka dôležitejšie v okolí domova? |
| Bez auta | Čo je dôležitejšie pre domácnosť, ktorá nemá auto? |

- **Skóre profilu** = Σ (skóre aspektu × váha aspektu v profile) cez aspekty s dátami. Váhy týchto aspektov sa prepočítajú na súčet 1.
- **Profil sa počíta, len ak aspekty s dátami tvoria aspoň 75 % jeho váhy.** Pri rovnakých váhach je to presne pravidlo WHOQOL-BREF „6 z 8“. Pri váhach z panelu má rovnaký význam: chýbať smie najviac štvrtina toho, na čom profilu záleží.
- **Kým panel neodpovie, majú aspekty v profile rovnakú váhu** a profily sa od seba ani od indexu nelíšia.
- **Skóre Rodina** na stránke je profil Rodina s deťmi. Na Slovensku má dáta všetkých 8 aspektov. Kým panel neodpovie, sa rovná indexu prostredia.

AHP sa teda nepoužíva na samotný index ani na profil prostredia, ktoré vychádzajú z WHOQOL. Používa sa len na **rozdiely medzi profilmi**.

### Metóda AHP (Analytic Hierarchy Process, Saaty 1980)

1. **Porovnanie dvojíc.** Expert pri každej dvojici kritérií (napr. škôlka a ihrisko) povie, ktoré je dôležitejšie a o koľko, na Saatyho škále: 1 rovnako, 3 mierne, 5 výrazne, 7 veľmi výrazne, 9 extrémne. Opačný smer je prevrátená hodnota (1/3, 1/5…). Pri *n* kritériách je to n·(n−1)/2 otázok: profil s 8 aspektmi má 28 porovnaní.
2. **Matica.** Odpovede tvoria recipročnú maticu A: a<sub>ij</sub> = úsudok „i oproti j“, a<sub>ji</sub> = 1/a<sub>ij</sub>, a<sub>ii</sub> = 1.
3. **Váhy** sú hlavný vlastný vektor matice A, normalizovaný na súčet 1 (počítaný mocninovou metódou).
4. **Konzistencia.** λ<sub>max</sub> je hlavné vlastné číslo, **CI = (λ<sub>max</sub> − n) / (n − 1)**, **CR = CI / RI**. RI je náhodný index (Saaty): n = 3: 0,58 · 4: 0,90 · 5: 1,12 · 6: 1,24 · 7: 1,32 · 8: 1,41 · 9: 1,45 · 10: 1,49. **Odpovede s CR ≥ 0,10 nepoužijeme.** Dotazník expertovi rovno ukáže, ktoré porovnanie najviac nesedí.
5. **Panel.** Úsudky konzistentných expertov spojíme **geometrickým priemerom** každej odpovede (Aczél a Saaty, 1983) a z výslednej matice vypočítame váhy a skupinové CR.

**Spočítaný príklad** (úsudky sú ilustračné):

| | Škôlka | Škola | Ihrisko | Lekár |
|---|---:|---:|---:|---:|
| Škôlka | 1 | 1 | 3 | 5 |
| Škola | 1 | 1 | 3 | 5 |
| Ihrisko | 1/3 | 1/3 | 1 | 2 |
| Lekár | 1/5 | 1/5 | 1/2 | 1 |

Váhy: škôlka 39,4 %, škola 39,4 %, ihrisko 13,7 %, lekár 7,5 %. λ<sub>max</sub> = 4,0042, CI = 0,0014, CR = 0,0015. Výpočet overuje test `tests/test_ahp.py`.

### Postup panelu

1. **Zloženie:** 5 až 9 expertov z rôznych odborov (urbanista, realitný znalec, hypotekárny špecialista, sociológ, odborník na verejné zdravie, zástupca samosprávy, rodič).
2. **Odpovede:** experti odpovedajú online na `/ahp` s kódom panelu, každý na profily, ku ktorým sa cíti povolaný. Kontrolu konzistencie vidia hneď.
3. **Výsledok:** správca v `/admin` vidí CR každého experta a skupinové váhy a stiahne súbor `methodology/weights.json`.
4. **Zverejnenie:** súbor sa commitne a zvýši sa verzia metodiky. V metodike zverejníme roly expertov (nie mená), ich počet, skupinové CR a dátum.

## 7. Agregácia a pásma

**Skóre = Σ (čiastkové skóre × váha)**, teda vážený aritmetický priemer zaokrúhlený na celé číslo. Pokoj = 100 − Σ zrážok, najmenej 0.

Vážený priemer je kompenzačný: slabé miesto sa dá vyvážiť silným. Je to bežná voľba pre zrozumiteľnosť. Geometrický priemer by kompenzoval menej, výber medzi nimi je otvorený bod (časť 10).

| Skóre | Pásma |
|---|---|
| Pešo | 90+ Všetko vybavíte pešo · 70+ Väčšinu vybavíte pešo · 50+ Niečo vybavíte pešo · 25+ Väčšinou autom · pod 25 Takmer všetko autom (pásma Walk Score) |
| Zeleň | 80+ Zeleň za rohom · 60+ Dosť zelene · 40+ Trochu zelene · pod 40 Málo zelene |
| Rodina | 80+ Výborné · 60+ Dobré · 40+ Priemerné · pod 40 Slabé pre rodiny |
| Pokoj | 80+ Pokojné · 60+ Väčšinou pokojné · 40+ Rušnejšie · pod 40 Rušné |

### Pokoj: náprava odhadu

Nahradiť zrážky meraným alebo modelovaným hlukom:
1. **Strategické hlukové mapy** podľa smernice 2002/49/ES (MŽP SR, Európska environmentálna agentúra) pre aglomerácie, hlavné cesty a železnice: pásma L<sub>den</sub> 55, 60, 65, 70, 75 dB.
2. **Inde výpočet podľa CNOSSOS-EU** (smernica 2015/996) z intenzity dopravy.
3. **Prahy** podľa smerníc WHO pre hluk v prostredí (2018): cestná doprava L<sub>den</sub> 53 dB, železnica 54 dB.

## 8. Príklad výpočtu

Vygenerované skriptom `scripts/method_example.py` z rovnakého kódu, aký počíta stránku.

<!-- EXAMPLE:START -->
Adresa: **Záhradná, Pezinok** (48,28646, 17,27221), dáta OpenStreetMap, metodika 0.5 (2026-10-18).

#### Profil prostredia podľa WHOQOL-BREF

| Aspekt | Položka | Skóre | Ukazovatele (čiastkové skóre) |
|---|---|---:|---|
| F16 Bezpečnosť | Q8 | 14 | Trestné činy na 1 000 obyvateľov (kraj) 14 |
| F17 Domáce prostredie | Q23 | 89 | Obyvatelia na obývaný byt (obec) 89 |
| F18 Finančné podmienky | Q12 | 58 | Priemerná mzda (okres) 40; Nezamestnanosť (okres) 77 |
| F19 Zdravotná a sociálna starostlivosť | Q24 | 100 | Lekár 100; Lekáreň 100 |
| F20 Informácie a vzdelávanie | Q13 | 80 | Materská škola 100; Základná škola 40; Knižnica 100 |
| F21 Rekreácia a voľný čas | Q14 | 74 | Park (pomenovaný) 86; Športovisko 84; Kultúra (divadlo, kino, kultúrne centrum) 100; Detské ihrisko 100; Prírodná zeleň aspoň 20 ha do 2 km 0 |
| F22 Fyzické prostredie | Q9 | 64 | Verejná zeleň aspoň 0,5 ha 92; Podiel zelene do 300 m 17; Pokoj (orientačné) 82 |
| F23 Doprava | Q25 | 100 | Pešia dostupnosť služieb 99; Zastávka MHD alebo vlak 100 |

**Index prostredia:** 72 (dáta pre 8 z 8 aspektov, potrebných aspoň 6).

#### Skóre pre používateľa

##### Pešo: 99 (Všetko vybavíte pešo)

| Ukazovateľ | Fakt | Čiastkové skóre | Váha | Body |
|---|---|---:|---:|---:|
| Potraviny | 71 m vzdušne = 92 m chôdze | 100,0 | 20,0 % | 20,0 |
| Reštaurácie | 10 z 10 najbližších započítaných, najbližšie 54 m vzdušne = 70 m chôdze | 100,0 | 20,0 % | 20,0 |
| Kaviarne | 2 z 2 najbližších započítaných, najbližšie 109 m vzdušne = 142 m chôdze | 100,0 | 13,3 % | 13,3 |
| Obchody a služby | 5 z 5 najbližších započítaných, najbližšie 113 m vzdušne = 146 m chôdze | 100,0 | 13,3 % | 13,3 |
| Banka alebo pošta | 105 m vzdušne = 136 m chôdze | 100,0 | 6,7 % | 6,7 |
| Park | 467 m vzdušne = 607 m chôdze | 85,5 | 6,7 % | 5,7 |
| Škola | 152 m vzdušne = 197 m chôdze | 100,0 | 6,7 % | 6,7 |
| Lekáreň | 91 m vzdušne = 118 m chôdze | 100,0 | 6,7 % | 6,7 |
| Kultúra a šport | 306 m vzdušne = 398 m chôdze | 100,0 | 6,7 % | 6,7 |
| **Skóre** | | | | **99,1 → 99** |

##### Zeleň: 36 (Málo zelene)

| Ukazovateľ | Fakt | Čiastkové skóre | Váha | Body |
|---|---|---:|---:|---:|
| Verejná zeleň aspoň 0,5 ha blízko | 351 m k ploche 0,6 ha | 92,4 | 33,3 % | 30,8 |
| Podiel zelene do 300 m | 5 % plochy kruhu 300 m, cieľ 30 % | 17,1 | 33,3 % | 5,7 |
| Les alebo veľký park (20 ha) do 2 km | nie | 0,0 | 33,3 % | 0,0 |
| **Skóre** | | | | **36,5 → 36** |

##### Rodina: 72 (Dobré pre rodiny)

| Ukazovateľ | Fakt | Čiastkové skóre | Váha | Body |
|---|---|---:|---:|---:|
| F16 Bezpečnosť | aspekt 14 | 14,0 | 12,5 % | 1,8 |
| F17 Domáce prostredie | aspekt 89 | 89,0 | 12,5 % | 11,1 |
| F18 Finančné podmienky | aspekt 58 | 58,0 | 12,5 % | 7,2 |
| F19 Zdravotná a sociálna starostlivosť | aspekt 100 | 100,0 | 12,5 % | 12,5 |
| F20 Informácie a vzdelávanie | aspekt 80 | 80,0 | 12,5 % | 10,0 |
| F21 Rekreácia a voľný čas | aspekt 74 | 74,0 | 12,5 % | 9,2 |
| F22 Fyzické prostredie | aspekt 64 | 64,0 | 12,5 % | 8,0 |
| F23 Doprava | aspekt 100 | 100,0 | 12,5 % | 12,5 |
| **Skóre** | | | | **72,3 → 72** |

##### Pokoj: 82 (Pokojné)

| Zdroj | Vzdialenosť | Body |
|---|---|---:|
| Začiatok | | 100 |
| Cesta II. triedy | 80 m | -8 |
| Železnica | 292 m | -5 |
| Bary a kluby do 150 m | 1 podnik | -5 |
| **Skóre** | | **82** |
<!-- EXAMPLE:END -->

## 9. Neskôr (voliteľné): overenie dotazníkom

**Výpočet skóre od tejto štúdie nezávisí a teraz ju nerobíme.** Zapisujeme ju ako možný budúci krok: ak by sme chceli dokázať, že objektívne skóre súvisí s tým, ako miesto prežívajú jeho obyvatelia, plán by bol takýto (s univerzitným partnerom):

| | |
|---|---|
| **Otázka** | Súvisí naše skóre aspektov F16–F23 s hodnotením tých istých aspektov v dotazníku WHOQOL-BREF? |
| **Vzorka** | 400 až 500 dospelých v 20 až 30 lokalitách, rozvrstvených na centrum mesta, sídlisko, okraj mesta a obec |
| **Veľkosť** | korelácia r = 0,2 sa pri α = 0,05 a sile testu 80 % odhalí pri n ≈ 194 (Fisherova transformácia). Pri 20 až 30 lokalitách a zhlukovaní v nich preto plánujeme 15 až 20 respondentov na lokalitu |
| **Meranie** | WHOQOL-BREF (oblasť 4 a jej 8 položiek) a k adrese respondenta naše skóre aspektov; kontrolné premenné: vek, pohlavie, príjem domácnosti, dĺžka bývania |
| **Analýza** | korelácia objektívneho aspektu s jeho položkou (napr. F22 s Q9); viacúrovňová regresia (respondenti v lokalitách); z nej **empirické váhy** ukazovateľov, porovnané s váhami panelu AHP |
| **Výsledok** | zverejnené korelácie a váhy; ukazovatele, ktoré s prežívaním nesúvisia, prehodnotíme |
| **Etika a GDPR** | súhlas respondentov, adresy uložené pseudonymne a len na výpočet, posúdenie etickou komisiou partnera |

### Licencia WHOQOL-BREF

- Podľa príručky WHO sa WHOQOL-BREF nesmie použiť bez dohody so skupinou WHOQOL. Povolenie sa žiada cez formulár WHO, pre jednotlivé jazykové verzie u národných centier. Prevádzkovatelia národných verzií udeľujú povolenie na konkrétnu štúdiu a zakazujú dotazník ďalej šíriť.
- **V produkte používame len rámec (názvy a členenie aspektov), nie znenie otázok.** Samotný dotazník použijeme až v štúdii a s povolením.
- **Jazyková verzia:** existuje overená česká verzia (Dragomirecká a Bartoňová, 2006). Overenú slovenskú verziu WHOQOL-BREF sme nenašli. Štúdia preto buď použije českú verziu, alebo slovenský preklad podľa postupu WHO pre nové jazykové verzie.

## 10. Obmedzenia

- Úplnosť OSM sa líši podľa miesta. V malých obciach častejšie chýbajú škôlky alebo ambulancie.
- Vzdialenosti sú vzdušné × 1,3, nie skutočné trasy.
- Zeleň počíta verejnú zeleň. Vinohrady a polia okolo dedín sa nezapočítavajú.
- Skóre MHD zatiaľ chýba (potrebuje cestovné poriadky). Ukazujeme len najbližšiu zastávku.
- Zdravotnú starostlivosť (F19) zatiaľ hodnotíme len pešo. Na vidieku, kde sa k lekárovi chodí autom, je preto nízka.
- Bezpečnosť (F16) je len za kraj, finančné podmienky (F18) za okres. Adresy v jednom kraji alebo okrese sa v nich nelíšia.
- Mzdy sú podľa miesta práce (pracovisková metóda), nie podľa bydliska. V okresoch okolo Bratislavy preto podhodnocujú príjmy obyvateľov.
- Obyvatelia na byt hovoria o zahustení bytov v obci, nie o konkrétnom byte. Nízka hodnota môže znamenať aj veľa jednočlenných domácností.
- V hustých centrách miest sa Pešo blíži k 100, rovnako ako Walk Score.

## 11. Otvorené body

| Bod | Stav | Ako ho uzavrieť |
|---|---|---|
| Koeficient trasy 1,3 a rýchlosť 80 m/min | predpoklad | skutočné trasy (OSRM) |
| Body krivky chôdze 800/1 200/1 600 m | podľa publikovaného tvaru | overiť v prílohe E a v patente Walk Score (US 8738422) |
| Váhy Walk Score | prevzaté z citácie | overiť v pôvodnom článku Brewster a kol. (2009) |
| Váhy profilov (rodina, senior, bez auta) | rovnaké | AHP panel |
| Pokoj | orientačný odhad | hlukové mapy, CNOSSOS-EU |
| Zelené plochy namiesto korún stromov | náhrada | dáta o korunách stromov (Copernicus, Urban Atlas) |
| Vážený alebo geometrický priemer | vážený | rozhodnutie panelu, citlivostná analýza |
| Aspekty F16, F17, F18 | chýbajú dáta, index sa nepočíta | Polícia SR, údaje z inzerátu, ŠÚ SR, ÚPSVaR, NBS |
| F19 len pešo | na vidieku je lekár ďaleko pešo a skóre 0 | dostupnosť autom a MHD (čas jazdy), nemocnice |
| Slovenská verzia WHOQOL-BREF | nenašli sme overenú; týka sa len voliteľnej štúdie | česká verzia alebo preklad podľa postupu WHO |
| F16 za okresy | len za kraj | tabuľky MV SR podľa okresov (žiadosť podľa zákona o slobodnom prístupe k informáciám) |
| Dopravná nehodovosť | nepoužitá, chýbajú popisy ukazovateľov | overiť význam kódov do3806rr u ŠÚ SR alebo MV SR |
| Ceny bývania oproti príjmu (F18) | chýba | ceny NBS sú len za kraje; zvážiť Realitný barometer pre ~30 miest |
| Údaje o dome a byte (F17) | chýba | z inzerátu (energetická trieda, rok, stav) |

## 12. Verzie

| Verzia | Dátum | Zmena |
|---|---|---|
| 0.5 | 18. 10. 2026 | Doplnené F16 (kriminalita za kraj), F17 (obyvatelia na obývaný byt v obci, sčítanie 2021), F18 (mzda a nezamestnanosť v okrese); štatistiky hodnotené percentilom medzi územiami SR; adresy priradené k územiam cez hranice OSM s úradnými kódmi; index prostredia a profil Rodina sa na Slovensku počítajú. |
| 0.4 | 18. 10. 2026 | Rodina je profil nad 8 aspektmi WHOQOL (počíta sa pri aspoň 75 % váhy); AHP určuje len rozdiely medzi profilmi (rodina, senior, bez auta), nie index; Zeleň s rovnakými váhami troch častí; overovacia štúdia presunutá medzi voliteľné budúce kroky. |
| 0.3 | 18. 10. 2026 | Rámec podľa oblasti Prostredie WHOQOL-BREF: profil 8 aspektov F16–F23, aspekt = priemer ukazovateľov, index = priemer aspektov, len pri aspoň 6 z 8 (pravidlo WHOQOL-BREF); nové ukazovatele knižnica, športovisko, kultúra; návrh overovacej štúdie; licencia. |
| 0.2 | 18. 10. 2026 | Rovnaké váhy namiesto odhadu pre Zeleň a Rodinu; pre deti rovnaká krivka chôdze ako pre dospelých (bez vymyslených prahov); les alebo park podľa ANGSt (20 ha do 2 km) namiesto 10 ha do 1 km; Pokoj označený ako orientačný; električky a cesty III. triedy; rozpis výpočtu; AHP panel. |
| 0.1 | 18. 10. 2026 | Prvý prototyp. |

## Literatúra

- ŠÚ SR, DATAcube: np3110rr (mzdy podľa okresov), om7102rr (obyvateľstvo), sk3003rr (kriminalita podľa krajov).
- ÚPSVaR: mesačná štatistika o počte a štruktúre uchádzačov o zamestnanie (tabuľka 1).
- ŠÚ SR: Sčítanie obyvateľov, domov a bytov 2021, Štatistický lexikón obcí Slovenskej republiky.

- WHO, Programme on Mental Health (1996): *WHOQOL-BREF: Introduction, Administration, Scoring and Generic Version of the Assessment. Field Trial Version.* Ženeva.
- The WHOQOL Group (1998): Development of the World Health Organization WHOQOL-BREF quality of life assessment. *Psychological Medicine* 28(3).
- Dragomirecká, E., Bartoňová, J. (2006): *WHOQOL-BREF, WHOQOL-100: příručka pro uživatele české verze dotazníků kvality života Světové zdravotnické organizace.* Psychiatrické centrum Praha.

- OECD, JRC (2008): *Handbook on Constructing Composite Indicators: Methodology and User Guide.* OECD Publishing.
- Saaty, T. L. (1980): *The Analytic Hierarchy Process.* McGraw-Hill.
- Aczél, J., Saaty, T. L. (1983): Procedures for synthesizing ratio judgements. *Journal of Mathematical Psychology* 27(1).
- Walk Score: *Walk Score Methodology,* walkscore.com/methodology.shtml; patent US 8738422.
- Brewster, M. a kol. (2009): Walkscore.com: A New Methodology to Explore Associations Between Neighborhood Resources, Race, and Health.
- Lee, C., Moudon, A. V. (2006): Correlates of walking for transportation or recreation purposes. *Journal of Physical Activity and Health* 3(s1).
- WHO Regional Office for Europe (2016): *Urban green spaces and health: a review of evidence.*
- WHO Regional Office for Europe (2018): *Environmental Noise Guidelines for the European Region.*
- Natural England (2010): *Nature Nearby: Accessible Natural Greenspace Guidance* (ANGSt).
- Konijnendijk, C. C. (2021, 2023): pravidlo 3-30-300.
- Smernica 2002/49/ES o posudzovaní a riadení hluku vo vonkajšom prostredí; smernica Komisie (EÚ) 2015/996 (CNOSSOS-EU).
