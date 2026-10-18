# HoodieMap skóre: metodika

**Verzia metodiky:** 0.2 (18. 10. 2026) · **Stav:** prototyp · **Kód:** `src/score.py`, `src/score_method.py`, `src/ahp.py`

Tento dokument popisuje, ako HoodieMap počíta skóre adresy, aby si výpočet mohol ktokoľvek overiť a zopakovať. Každé číslo v ňom má zdroj. Kde zdroj zatiaľ chýba, je to výslovne napísané a uvedené v časti [Otvorené body](#10-otvorené-body).

---

## 1. Zásady

1. **Meriame fakty, nie dojmy.** Vstupom sú merateľné údaje: vzdialenosť v metroch, plocha v hektároch, počet miest.
2. **Každý prah má zdroj:** norma (WHO, Natural England), publikovaná metodika (Walk Score) alebo výsledok expertného panelu.
3. **Váhy sú hodnotový úsudok, preto ich robíme priehľadne.** Pochádzajú z expertného panelu metódou AHP (časť 6). Kým panel neodpovie, platia **rovnaké váhy**, čo je predvolený postup podľa príručky OECD/JRC.
4. **Výpočet je opakovateľný.** Rovnaké dáta a rovnaká verzia metodiky dajú vždy rovnaký výsledok. Váhy sú uložené vo verzovanom súbore, nie v databáze.
5. **Ukazujeme výpočet.** Pri každom skóre je na stránke rozpis krok za krokom: fakt, čiastkové skóre, váha, body.
6. **Postup** vychádza z príručky *Handbook on Constructing Composite Indicators* (OECD a JRC, 2008): rámec, ukazovatele, normalizácia, váhy, agregácia, citlivosť.

## 2. Čo skóre meria

Štyri samostatné skóre 0–100. Nespájame ich do jedného čísla, lebo každé odpovedá na inú otázku:

| Skóre | Otázka |
|---|---|
| **Pešo** | Čo vybavím bez auta? |
| **Zeleň** | Koľko je okolo verejnej zelene a prírody? |
| **Rodina** | Ako je miesto vybavené pre rodinu s deťmi? |
| **Pokoj** | Ako ďaleko sú zdroje hluku? *(orientačné, časť 7)* |

## 3. Dáta

- **Zdroj:** OpenStreetMap (© prispievatelia OpenStreetMap, licencia ODbL), v produkcii z lokálneho Overpass servera so slovenským extraktom z Geofabriku (aktualizovaný denne).
- **Jeden dopyt na adresu:**
  - miesta (obchody, školy…) do **2,5 km** ako body,
  - zeleň do **2 km** s geometriou plôch,
  - cesty a železnica do **600 m** s geometriou čiar,
  - bary do **200 m**.
- **Kvalita:** chýbajúce alebo neoznačené miesto v OSM skóre zníži. Stránka vždy uvedie, čo sa nenašlo.

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

Koeficient 1,3 vyjadruje, že ulice nevedú priamo. Rýchlosť 80 m/min (4,8 km/h) je bežne uvádzaná rýchlosť chôdze. Obe čísla sú zatiaľ **predpoklad** (časť 10). Nahradí ich skutočná trasa po uliciach (OSRM nad OSM).

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

### Zeleň a Rodina: AHP panel, dovtedy rovnaké váhy

Kým panel neodpovie, má každý ukazovateľ rovnakú váhu: Zeleň 3 × 33,3 %, Rodina 6 × 16,7 %.

### Metóda AHP (Analytic Hierarchy Process, Saaty 1980)

1. **Porovnanie dvojíc.** Expert pri každej dvojici kritérií (napr. škôlka a ihrisko) povie, ktoré je dôležitejšie a o koľko, na Saatyho škále: 1 rovnako, 3 mierne, 5 výrazne, 7 veľmi výrazne, 9 extrémne. Opačný smer je prevrátená hodnota (1/3, 1/5…). Pri *n* kritériách je to n·(n−1)/2 otázok: Rodina 15, Zeleň 3.
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
2. **Odpovede:** experti odpovedajú online na `/ahp` s kódom panelu. Kontrolu konzistencie vidia hneď.
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
Adresa: **Záhradná, Pezinok** (48,28646, 17,27221), dáta OpenStreetMap, metodika 0.2 (2026-10-18).

#### Pešo: 99 (Všetko vybavíte pešo)

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

#### Zeleň: 36 (Málo zelene)

| Ukazovateľ | Fakt | Čiastkové skóre | Váha | Body |
|---|---|---:|---:|---:|
| Verejná zeleň aspoň 0,5 ha blízko | 351 m k ploche 0,6 ha | 92,4 | 33,3 % | 30,8 |
| Podiel zelene do 300 m | 5 % plochy kruhu 300 m, cieľ 30 % | 17,1 | 33,3 % | 5,7 |
| Les alebo veľký park (20 ha) do 2 km | nie | 0,0 | 33,3 % | 0,0 |
| **Skóre** | | | | **36,5 → 36** |

#### Rodina: 79 (Dobré pre rodiny)

| Ukazovateľ | Fakt | Čiastkové skóre | Váha | Body |
|---|---|---:|---:|---:|
| Materská škola | 281 m vzdušne = 366 m chôdze | 100,0 | 16,7 % | 16,7 |
| Základná škola | 953 m vzdušne = 1239 m chôdze | 39,6 | 16,7 % | 6,6 |
| Detské ihrisko | 51 m vzdušne = 67 m chôdze | 100,0 | 16,7 % | 16,7 |
| Lekár | 124 m vzdušne = 161 m chôdze | 100,0 | 16,7 % | 16,7 |
| Potraviny | 71 m vzdušne = 92 m chôdze | 100,0 | 16,7 % | 16,7 |
| Zeleň (skóre Zeleň) | skóre Zeleň 36 | 36,0 | 16,7 % | 6,0 |
| **Skóre** | | | | **79,4 → 79** |

#### Pokoj: 82 (Pokojné)

| Zdroj | Vzdialenosť | Body |
|---|---|---:|
| Začiatok | | 100 |
| Cesta II. triedy | 80 m | -8 |
| Železnica | 292 m | -5 |
| Bary a kluby do 150 m | 1 podnik | -5 |
| **Skóre** | | **82** |
<!-- EXAMPLE:END -->

## 9. Obmedzenia

- Úplnosť OSM sa líši podľa miesta. V malých obciach častejšie chýbajú škôlky alebo ambulancie.
- Vzdialenosti sú vzdušné × 1,3, nie skutočné trasy.
- Zeleň počíta verejnú zeleň. Vinohrady a polia okolo dedín sa nezapočítavajú.
- Skóre MHD zatiaľ chýba (potrebuje cestovné poriadky). Ukazujeme len najbližšiu zastávku.
- V hustých centrách miest sa Pešo blíži k 100, rovnako ako Walk Score.

## 10. Otvorené body

| Bod | Stav | Ako ho uzavrieť |
|---|---|---|
| Koeficient trasy 1,3 a rýchlosť 80 m/min | predpoklad | skutočné trasy (OSRM) |
| Body krivky chôdze 800/1 200/1 600 m | podľa publikovaného tvaru | overiť v prílohe E a v patente Walk Score (US 8738422) |
| Váhy Walk Score | prevzaté z citácie | overiť v pôvodnom článku Brewster a kol. (2009) |
| Váhy Zeleň a Rodina | rovnaké | AHP panel |
| Pokoj | orientačný odhad | hlukové mapy, CNOSSOS-EU |
| Zelené plochy namiesto korún stromov | náhrada | dáta o korunách stromov (Copernicus, Urban Atlas) |
| Vážený alebo geometrický priemer | vážený | rozhodnutie panelu, citlivostná analýza |

## 11. Verzie

| Verzia | Dátum | Zmena |
|---|---|---|
| 0.2 | 18. 10. 2026 | Rovnaké váhy namiesto odhadu pre Zeleň a Rodinu; pre deti rovnaká krivka chôdze ako pre dospelých (bez vymyslených prahov); les alebo park podľa ANGSt (20 ha do 2 km) namiesto 10 ha do 1 km; Pokoj označený ako orientačný; električky a cesty III. triedy; rozpis výpočtu; AHP panel. |
| 0.1 | 18. 10. 2026 | Prvý prototyp. |

## Literatúra

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
