# HoodieMap skóre: metodika

**Verzia metodiky:** 0.6 (18. 10. 2026) · **Stav:** prototyp · **Kód:** `src/score.py`, `src/score_method.py`, `src/ahp.py`

Tento dokument popisuje, ako HoodieMap počíta skóre adresy, aby si výpočet mohol ktokoľvek overiť a zopakovať. Každé číslo v ňom má zdroj. Kde zdroj zatiaľ chýba, je to výslovne napísané a uvedené v časti [Otvorené body](#11-otvorené-body).

---

## 1. Zásady

1. **Meriame fakty, nie dojmy.** Vstupom sú merateľné údaje: vzdialenosť v metroch, plocha v hektároch, počet miest.
2. **Každý prah má zdroj:** norma (WHO, Natural England), publikovaná metodika (Walk Score), publikovaný rámec (OECD) alebo výsledok expertného panelu.
3. **Váhy sú hodnotový úsudok, preto ich robíme priehľadne.** Pochádzajú z expertného panelu metódou AHP (časť 6). Kým panel neodpovie, platia **rovnaké váhy**, čo je predvolený postup podľa príručky OECD/JRC.
4. **Výpočet je opakovateľný.** Rovnaké dáta a rovnaká verzia metodiky dajú vždy rovnaký výsledok. Váhy sú uložené vo verzovanom súbore, nie v databáze.
5. **Ukazujeme výpočet.** Pri každom skóre je na stránke rozpis krok za krokom: fakt, čiastkové skóre, váha, body.
6. **Postup** vychádza z príručky *Handbook on Constructing Composite Indicators* (OECD a JRC, 2008): rámec, ukazovatele, normalizácia, váhy, agregácia, citlivosť.
7. **Len objektívne údaje, žiadny dotazník.** Skóre nevychádza z toho, ako ľudia miesto vnímajú, ale z merateľných podmienok. Čo meriame, určujú normy pre okolie adresy a rámec OECD pre územie (časť 2). Dotazník môže skóre neskôr len overiť (časť 9).

## 2. Rámec: okolie adresy a územie

Index HoodieMap odpovedá na otázku **„aké sú objektívne podmienky na tejto adrese?“** Má dve vrstvy:

- **Okolie adresy:** to, čím sa líšia dva byty v jednom meste. Každá oblasť sa hodnotí voči **norme**: Walk Score pre pešiu dostupnosť, odporúčania WHO pre zeleň (a neskôr hluk a ovzdušie).
- **Územie:** ako je na tom obec, okres alebo kraj v štatistikách. Oblasti preberáme z rámca **OECD Regional Well-Being** (*How's Life in Your Region?*, OECD 2014), ktorý porovnáva regióny podľa objektívnych ukazovateľov. Z jeho 11 rozmerov berieme tie, ktoré sa dajú merať štatistikou; spokojnosť so životom a sociálnu oporu OECD meria prieskumom, preto ich nepoužívame.

| Oblasť | Vrstva | Ukazovatele | Norma alebo rámec | Stav |
|---|---|---|---|---|
| Služby pešo | okolie | skóre Pešo | Walk Score (Brewster a kol. 2009) | áno |
| Deti a zdravie | okolie | materská škola, základná škola, detské ihrisko, lekár, lekáreň | krivka chôdze Walk Score | áno |
| Doprava | okolie | zastávka MHD alebo vlaku | krivka chôdze Walk Score | áno (chýba frekvencia spojov) |
| Zeleň | okolie | verejná zeleň ≥ 0,5 ha, podiel zelene do 300 m, prírodná zeleň ≥ 20 ha do 2 km | WHO Európa 2016, 3-30-300, ANGSt | áno |
| Pokoj | okolie | skóre Pokoj | zatiaľ orientačné zrážky; cieľ: hlukové mapy a limity WHO 2018 | **orientačné** |
| Ovzdušie | okolie | PM2,5 a NO₂ | WHO Air Quality Guidelines 2021 | pripravujeme |
| Príjem | územie | priemerná mzda v okrese | OECD: príjem domácností na osobu | áno (náhradný ukazovateľ) |
| Práca | územie | evidovaná nezamestnanosť v okrese | OECD: miera nezamestnanosti | áno |
| Bývanie | územie | obyvatelia na trvalo obývaný byt v obci | OECD: obytné miestnosti na osobu | áno (náhradný ukazovateľ) |
| Bezpečnosť | územie | zistené trestné činy na 1 000 obyvateľov v kraji | OECD: vraždy na 100 000 obyvateľov | áno, **len za kraj** |
| Zdravie | územie | stredná dĺžka života v okrese | OECD: stredná dĺžka života | pripravujeme |
| Vzdelanie | územie | najvyššie dosiahnuté vzdelanie v obci (sčítanie 2021) | OECD: podiel pracovnej sily aspoň so stredoškolským vzdelaním | pripravujeme |
| Občianska angažovanosť | územie | volebná účasť v obci | OECD: volebná účasť | pripravujeme |

**Náhradný ukazovateľ** znamená, že OECD meria vec inak a my používame najbližšie verejne dostupné číslo. Rozdiel je vždy napísaný pri oblasti (napríklad OECD meria príjem domácností, ŠÚ SR ho za okresy nezverejňuje, preto mzda).

### Výpočet indexu

1. **Ukazovateľ → čiastkové skóre 0–100** podľa normy alebo publikovanej krivky, štatistiky územia percentilom (časť 5).
2. **Oblasť = priemer jej ukazovateľov s rovnakou váhou.**
3. **Index HoodieMap = priemer oblastí s rovnakou váhou.** Rovnaké váhy sú predvolený postup príručky OECD/JRC (2008) a predvolené nastavenie OECD Better Life Index, kým nie je dôvod vážiť inak.
4. **Do indexu vstupujú len oblasti, ktoré majú dáta pre každú adresu na Slovensku** (dnes 9). Oblasti „pripravujeme“ sú na stránke uvedené aj s normou, ale index neovplyvňujú, kým ich nedoplníme pre celé Slovensko. Index sa tak nemení podľa toho, kde máme viac dát.
5. **Index sa počíta, len keď majú dáta všetky oblasti indexu.** Mimo Slovenska chýbajú štatistiky územia, preto index nepočítame a ukážeme len oblasti okolia.

Chýbajúce miesto v OSM nie je chýbajúci údaj: ak sa do 2,5 km nenájde lekár, ukazovateľ má 0 bodov a stránka to napíše.

**Prečo tieto vrstvy, a nie dotazník:** do verzie 0.5 sme oblasti pomenúvali podľa aspektov dotazníka WHOQOL-BREF. Ten však meria, ako človek svoje prostredie **vníma**, a my sme jeho názvy napĺňali objektívnymi údajmi. Názov tak sľuboval niečo, čo výpočet nerobil. Od verzie 0.6 sa každá oblasť odvoláva len na normu alebo rámec, ktorý meria to isté ako my.

**Čo index znamená pri porovnaní adries:** štyri oblasti územia sú rovnaké pre všetky adresy v jednej obci (bývanie), okrese (príjem, práca) alebo kraji (bezpečnosť). Dve adresy v jednom meste sa preto líšia len okolím; rozdiel v indexe je menší ako rozdiel v okolí samotnom. Porovnanie preto ukazuje aj jednotlivé oblasti.

### Skóre pre používateľa

| Skóre | Otázka | Vzťah k indexu |
|---|---|---|
| **Index HoodieMap** | Aké sú objektívne podmienky na adrese? | priemer 9 oblastí |
| **Pešo** | Čo vybavím bez auta? | oblasť Služby pešo |
| **Zeleň** | Koľko je okolo verejnej zelene a prírody? | oblasť Zeleň |
| **Pokoj** | Ako ďaleko sú zdroje hluku? *(orientačné)* | oblasť Pokoj |
| **Rodina, Senior, Bez auta** | Ako dobré je miesto pre daný typ domácnosti? | tie isté oblasti s váhami z panelu (časť 6); kým panel neodpovie, rovnajú sa indexu a stránka ich neukazuje |

## 3. Dáta

- **Zdroj:** OpenStreetMap (© prispievatelia OpenStreetMap, licencia ODbL), v produkcii z lokálneho Overpass servera so slovenským extraktom z Geofabriku (aktualizovaný denne).
- **Jeden dopyt na adresu:**
  - miesta (obchody, školy…) do **2,5 km** ako body,
  - zeleň do **2 km** s geometriou plôch,
  - cesty a železnica do **600 m** s geometriou čiar,
  - bary do **200 m**.
- **Kvalita:** chýbajúce alebo neoznačené miesto v OSM skóre zníži. Stránka vždy uvedie, čo sa nenašlo.

### Štatistiky území

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
| Základná škola (Deti a zdravie) | `amenity=school` a názov obsahuje „základná“ alebo „ZŠ“, alebo `isced:level` 1, alebo `school=primary`; nie ZUŠ |
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

### Krivka chôdze (Pešo, Deti a zdravie, Doprava)

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

Percentil hovorí, **ako je územie na tom oproti ostatným na Slovensku**, nie či je hodnota „dobrá“ v absolútnom zmysle. Rovnako, teda poradím medzi regiónmi, hodnotí regióny aj OECD Regional Well-Being (škála 0–10). Pri Bezpečnosti (8 krajov) je hrubý: všetky adresy v jednom kraji majú rovnakú hodnotu.

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

Verejná zeleň blízko, podiel zelene a prírodná zeleň vážia po 33,3 %, rovnako ako ukazovatele vnútri ostatných oblastí (OECD/JRC 2008).

### Profily: AHP panel, dovtedy rovnaké váhy

Index HoodieMap váži 9 oblastí rovnako (časť 2). **Profil** odpovedá na inú otázku: ako dobré je miesto pre konkrétny typ domácnosti. Tie isté oblasti preto váži inak.

| Profil | Otázka pre panel |
|---|---|
| Rodina s deťmi | Čo je pre rodinu s deťmi dôležitejšie v okolí domova? |
| Senior | Čo je pre staršieho človeka dôležitejšie v okolí domova? |
| Bez auta | Čo je dôležitejšie pre domácnosť, ktorá nemá auto? |

- **Skóre profilu** = Σ (skóre oblasti × váha oblasti v profile) cez 9 oblastí indexu.
- **Profil sa počíta za rovnakých podmienok ako index:** všetky oblasti indexu majú dáta.
- **Kým panel neodpovie, majú oblasti v profile rovnakú váhu** a profil sa rovná indexu. Stránka ho preto neukazuje, aby neopakovala to isté číslo pod iným názvom.

AHP sa teda nepoužíva na samotný index. Používa sa len na **rozdiely medzi profilmi**.

### Metóda AHP (Analytic Hierarchy Process, Saaty 1980)

1. **Porovnanie dvojíc.** Expert pri každej dvojici kritérií (napr. škôlka a ihrisko) povie, ktoré je dôležitejšie a o koľko, na Saatyho škále: 1 rovnako, 3 mierne, 5 výrazne, 7 veľmi výrazne, 9 extrémne. Opačný smer je prevrátená hodnota (1/3, 1/5…). Pri *n* kritériách je to n·(n−1)/2 otázok: profil s 9 oblasťami má 36 porovnaní.
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
| Rodina (profil s váhami z panelu) | 80+ Výborné · 60+ Dobré · 40+ Priemerné · pod 40 Slabé pre rodiny |
| Index HoodieMap | bez slovných pásiem: pre celý index nepoznáme normu, ktorá by ich zdôvodnila |
| Pokoj | 80+ Pokojné · 60+ Väčšinou pokojné · 40+ Rušnejšie · pod 40 Rušné |

### Pokoj: náprava odhadu

Nahradiť zrážky meraným alebo modelovaným hlukom:
1. **Strategické hlukové mapy** podľa smernice 2002/49/ES (MŽP SR, Európska environmentálna agentúra) pre aglomerácie, hlavné cesty a železnice: pásma L<sub>den</sub> 55, 60, 65, 70, 75 dB.
2. **Inde výpočet podľa CNOSSOS-EU** (smernica 2015/996) z intenzity dopravy.
3. **Prahy** podľa smerníc WHO pre hluk v prostredí (2018): cestná doprava L<sub>den</sub> 53 dB, železnica 54 dB.

## 8. Príklad výpočtu

Vygenerované skriptom `scripts/method_example.py` z rovnakého kódu, aký počíta stránku.

<!-- EXAMPLE:START -->
Adresa: **Záhradná, Pezinok** (48,28646, 17,27221), dáta OpenStreetMap, metodika 0.6 (2026-10-18).

#### Index HoodieMap po oblastiach

| Oblasť | Vrstva | Skóre | Ukazovatele (čiastkové skóre) |
|---|---|---:|---|
| Služby pešo | Okolie adresy | 99 | Skóre Pešo (Walk Score) 99 |
| Deti a zdravie | Okolie adresy | 88 | Materská škola 100; Základná škola 40; Detské ihrisko 100; Lekár 100; Lekáreň 100 |
| Doprava | Okolie adresy | 100 | Zastávka MHD alebo vlak 100 |
| Zeleň | Okolie adresy | 36 | Verejná zeleň aspoň 0,5 ha 92; Podiel zelene do 300 m 17; Prírodná zeleň aspoň 20 ha do 2 km 0 |
| Pokoj | Okolie adresy | 82 | Skóre Pokoj (orientačné) 82 |
| Ovzdušie | Okolie adresy | – | pripravujeme: ročné koncentrácie PM2,5 a NO₂ (SHMÚ, EEA) |
| Príjem | Územie (štatistiky) | 40 | Priemerná mzda (okres) 40 |
| Práca | Územie (štatistiky) | 77 | Nezamestnanosť (okres) 77 |
| Bývanie | Územie (štatistiky) | 89 | Obyvatelia na obývaný byt (obec) 89 |
| Bezpečnosť | Územie (štatistiky) | 14 | Trestné činy na 1 000 obyvateľov (kraj) 14 |
| Zdravie | Územie (štatistiky) | – | pripravujeme: stredná dĺžka života v okrese (ŠÚ SR) |
| Vzdelanie | Územie (štatistiky) | – | pripravujeme: najvyššie dosiahnuté vzdelanie v obci (sčítanie 2021) |
| Občianska angažovanosť | Územie (štatistiky) | – | pripravujeme: účasť vo voľbách v obci (ŠÚ SR, volby.statistics.sk) |

**Index HoodieMap:** (99 + 88 + 100 + 36 + 82 + 40 + 77 + 89 + 14) / 9 = 69,4 → **69**

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

Profil Rodina sa pri rovnakých váhach rovná indexu, preto ho neuvádzame.

##### Pokoj: 82 (Pokojné)

| Zdroj | Vzdialenosť | Body |
|---|---|---:|
| Začiatok | | 100 |
| Cesta II. triedy | 80 m | -8 |
| Železnica | 292 m | -5 |
| Bary a kluby do 150 m | 1 podnik | -5 |
| **Skóre** | | **82** |
<!-- EXAMPLE:END -->

## 9. Neskôr (voliteľné): overenie

**Výpočet skóre od overenia nezávisí a teraz ho nerobíme.** Zapisujeme dve možné cesty.

### Porovnanie s nezávislým indexom

Spriemerujeme index HoodieMap cez adresy v okresných mestách a porovnáme ho s nezávislým indexom miest, napríklad Indexom kvality života (Obce v dátach, 71 okresných miest; česká predloha pre 206 ORP). Ten má iné ukazovatele aj iný celok (mesto, nie adresa). Silná korelácia by ukázala, že dva nezávislé postupy vedú k podobnému poradiu; slabá, kde a prečo sa líšia. Ich hodnoty do nášho skóre nepreberáme.

### Overenie dotazníkom WHOQOL-BREF

Dotazník meria, ako ľudia svoje prostredie **vnímajú**. Na to slúži správne: ako nezávislá kontrola, či naše objektívne oblasti súvisia so skúsenosťou obyvateľov. Plán (s univerzitným partnerom):

| | |
|---|---|
| **Otázka** | Súvisia naše oblasti s hodnotením príbuzných položiek oblasti 4 Prostredie dotazníka WHOQOL-BREF (napr. Zeleň a Pokoj s Q9 zdravé fyzické prostredie, Doprava s Q25, Bezpečnosť s Q8)? |
| **Vzorka** | 400 až 500 dospelých v 20 až 30 lokalitách, rozvrstvených na centrum mesta, sídlisko, okraj mesta a obec |
| **Veľkosť** | korelácia r = 0,2 sa pri α = 0,05 a sile testu 80 % odhalí pri n ≈ 194 (Fisherova transformácia). Pri 20 až 30 lokalitách a zhlukovaní v nich preto plánujeme 15 až 20 respondentov na lokalitu |
| **Meranie** | WHOQOL-BREF (oblasť 4 a jej 8 položiek) a k adrese respondenta naše oblasti; kontrolné premenné: vek, pohlavie, príjem domácnosti, dĺžka bývania |
| **Analýza** | korelácia oblasti s príbuznou položkou; viacúrovňová regresia (respondenti v lokalitách); z nej **empirické váhy** oblastí, porovnané s váhami panelu AHP |
| **Výsledok** | zverejnené korelácie a váhy; ukazovatele, ktoré so skúsenosťou nesúvisia, prehodnotíme |
| **Etika a GDPR** | súhlas respondentov, adresy uložené pseudonymne a len na výpočet, posúdenie etickou komisiou partnera |

### Licencia WHOQOL-BREF

- Podľa príručky WHO sa WHOQOL-BREF nesmie použiť bez dohody so skupinou WHOQOL. Povolenie sa žiada cez formulár WHO, pre jednotlivé jazykové verzie u národných centier. Prevádzkovatelia národných verzií udeľujú povolenie na konkrétnu štúdiu a zakazujú dotazník ďalej šíriť.
- **V produkte WHOQOL-BREF nepoužívame** (ani jeho názvy či členenie). Dotazník použijeme len v štúdii a s povolením.
- **Jazyková verzia:** existuje overená česká verzia (Dragomirecká a Bartoňová, 2006). Overenú slovenskú verziu WHOQOL-BREF sme nenašli. Štúdia preto buď použije českú verziu, alebo slovenský preklad podľa postupu WHO pre nové jazykové verzie.

## 10. Obmedzenia

- Úplnosť OSM sa líši podľa miesta. V malých obciach častejšie chýbajú škôlky alebo ambulancie.
- Vzdialenosti sú vzdušné × 1,3, nie skutočné trasy.
- Zeleň počíta verejnú zeleň. Vinohrady a polia okolo dedín sa nezapočítavajú.
- Doprava hodnotí len vzdialenosť k zastávke, nie frekvenciu spojov (potrebuje cestovné poriadky).
- Lekára a školy (Deti a zdravie) zatiaľ hodnotíme len pešo. Na vidieku, kde sa k nim chodí autom, je oblasť preto nízka.
- Bezpečnosť je len za kraj, príjem a práca za okres, bývanie za obec. Adresy v jednom území sa v nich nelíšia, a preto sa v indexe dve adresy v jednom meste líšia menej ako v okolí samotnom.
- Pešo a Deti a zdravie sa čiastočne prekrývajú (škola a lekáreň sú aj v kategóriách Walk Score). Walk Score preberáme celé, aby zostalo porovnateľné s pôvodnou metodikou.
- Mzdy sú podľa miesta práce (pracovisková metóda), nie podľa bydliska. V okresoch okolo Bratislavy preto podhodnocujú príjmy obyvateľov.
- Obyvatelia na byt hovoria o zahustení bytov v obci, nie o konkrétnom byte. Nízka hodnota môže znamenať aj veľa jednočlenných domácností.
- V hustých centrách miest sa Pešo blíži k 100, rovnako ako Walk Score.

## 11. Otvorené body

| Bod | Stav | Ako ho uzavrieť |
|---|---|---|
| Koeficient trasy 1,3 a rýchlosť 80 m/min | predpoklad | skutočné trasy (OSRM) |
| Body krivky chôdze 800/1 200/1 600 m | podľa publikovaného tvaru | overiť v prílohe E a v patente Walk Score (US 8738422) |
| Váhy Walk Score | prevzaté z citácie | overiť v pôvodnom článku Brewster a kol. (2009) |
| Váhy profilov (rodina, senior, bez auta) | rovnaké, profily sa neukazujú | AHP panel |
| Pokoj | orientačný odhad | hlukové mapy, CNOSSOS-EU |
| Zelené plochy namiesto korún stromov | náhrada | dáta o korunách stromov (Copernicus, Urban Atlas) |
| Vážený alebo geometrický priemer | vážený | rozhodnutie panelu, citlivostná analýza |
| Ovzdušie, Zdravie, Vzdelanie, Občianska angažovanosť | pripravujeme, mimo indexu | SHMÚ a EEA (PM2,5, NO₂), ŠÚ SR (dĺžka života), sčítanie 2021 (vzdelanie), volby.statistics.sk |
| Deti a zdravie len pešo | na vidieku je lekár ďaleko pešo a skóre 0 | dostupnosť autom a MHD (čas jazdy), nemocnice |
| Príjem a Bývanie | náhradné ukazovatele (mzda, obyvatelia na byt) | príjem domácností a obytné miestnosti, ak ich ŠÚ SR zverejní za okresy a obce |
| Slovenská verzia WHOQOL-BREF | nenašli sme overenú; týka sa len voliteľného overenia | česká verzia alebo preklad podľa postupu WHO |
| Bezpečnosť za okresy | len za kraj | tabuľky MV SR podľa okresov (žiadosť podľa zákona o slobodnom prístupe k informáciám) |
| Dopravná nehodovosť | nepoužitá, chýbajú popisy ukazovateľov | overiť význam kódov do3806rr u ŠÚ SR alebo MV SR |
| Ceny bývania oproti príjmu | chýba | ceny NBS sú len za kraje; zvážiť Realitný barometer pre ~30 miest |
| Údaje o dome a byte | chýba | z inzerátu (energetická trieda, rok, stav) |

## 12. Verzie

| Verzia | Dátum | Zmena |
|---|---|---|
| 0.6 | 18. 10. 2026 | Rámec bez dotazníka: oblasti okolia adresy podľa noriem (Walk Score, WHO, ANGSt) a oblasti územia podľa OECD Regional Well-Being; 9 oblastí v indexe s rovnakou váhou, index len pri dátach pre všetky; Ovzdušie, Zdravie, Vzdelanie a Občianska angažovanosť ako „pripravujeme“ mimo indexu; knižnica, pomenovaný park, športovisko a kultúra už nie sú samostatné ukazovatele (sú v Pešo); profily sa neukazujú, kým ich váhy neurčí panel; WHOQOL-BREF len na voliteľné overenie. |
| 0.5 | 18. 10. 2026 | Doplnené F16 (kriminalita za kraj), F17 (obyvatelia na obývaný byt v obci, sčítanie 2021), F18 (mzda a nezamestnanosť v okrese); štatistiky hodnotené percentilom medzi územiami SR; adresy priradené k územiam cez hranice OSM s úradnými kódmi; index prostredia a profil Rodina sa na Slovensku počítajú. |
| 0.4 | 18. 10. 2026 | Rodina je profil nad 8 aspektmi WHOQOL (počíta sa pri aspoň 75 % váhy); AHP určuje len rozdiely medzi profilmi (rodina, senior, bez auta), nie index; Zeleň s rovnakými váhami troch častí; overovacia štúdia presunutá medzi voliteľné budúce kroky. |
| 0.3 | 18. 10. 2026 | Rámec podľa oblasti Prostredie WHOQOL-BREF: profil 8 aspektov F16–F23, aspekt = priemer ukazovateľov, index = priemer aspektov, len pri aspoň 6 z 8 (pravidlo WHOQOL-BREF); nové ukazovatele knižnica, športovisko, kultúra; návrh overovacej štúdie; licencia. |
| 0.2 | 18. 10. 2026 | Rovnaké váhy namiesto odhadu pre Zeleň a Rodinu; pre deti rovnaká krivka chôdze ako pre dospelých (bez vymyslených prahov); les alebo park podľa ANGSt (20 ha do 2 km) namiesto 10 ha do 1 km; Pokoj označený ako orientačný; električky a cesty III. triedy; rozpis výpočtu; AHP panel. |
| 0.1 | 18. 10. 2026 | Prvý prototyp. |

## Literatúra

- ŠÚ SR, DATAcube: np3110rr (mzdy podľa okresov), om7102rr (obyvateľstvo), sk3003rr (kriminalita podľa krajov).
- ÚPSVaR: mesačná štatistika o počte a štruktúre uchádzačov o zamestnanie (tabuľka 1).
- ŠÚ SR: Sčítanie obyvateľov, domov a bytov 2021, Štatistický lexikón obcí Slovenskej republiky.

- OECD (2014): *How's Life in Your Region? Measuring Regional and Local Well-being for Policy Making.* OECD Publishing.
- OECD: *Better Life Index* a *Regional Well-Being* (oecdregionalwellbeing.org), predvolené rovnaké váhy rozmerov.
- WHO (2021): *WHO global air quality guidelines: particulate matter (PM2.5 and PM10), ozone, nitrogen dioxide, sulfur dioxide and carbon monoxide.*

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
