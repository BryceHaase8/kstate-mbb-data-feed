# Preseason 2026–27 NIL audit: international professional players without recent CBB stats

Status: **RESEARCH ONLY — no price changes and no site deploy**. Updated 2026-10-27.

## Exact-ID national coverage

Audit: `research_qa/international_nil_first_year_2027_audit.json`
- 5,541 ESPN roster memberships; 2,238 have no ESPN Division I box record **within 2022–23 through 2025–26**. That is a *lookback limit*, not proof that the player never attended college.
- 533 satisfy only a broad non-U.S. birthplace clue (including 462 ESPN "NA" endings and 71 Australian/Canadian province/state abbreviations). **These 533 are NOT certified international or professional players.** Hometown/birthplace must never determine an NIL premium by itself.
- 159 of the 533 are currently priced at exactly $50,000; 138 are on Torvik top-100 teams. Prioritize confirmed league experience and verified market role, not all 533 at once.
- Nine exact ESPN athletes are verified as recent professional / national team recruits from their universities; see the evidence URLs, existing prices, and athlete IDs in the audit JSON.

## Immediate corroborated pricing-review group (prices unchanged)

| ESPN athlete ID | School | Player | Oct. 27 model | Outside-CBB evidence |
|---|---|---|---:|---|
| 5281137 | LSU | Saliou Niang | $1,203,000 | Virtus EuroLeague; 2025 NBA draft |
| 5464194 | LSU | Brice Dessert | $50,000 | Anadolu Efes Turkish BSL and EuroLeague |
| 5458830 | LSU | Michael Ruzic | $60,400 | Joventut EuroCup / Liga ACB |
| 5167829 | Gonzaga | Izan Almansa | $50,000 | Real Madrid Liga ACB; G League Ignite; Spain U19 MVP |
| 5214635 | St. John's | Quinn Ellis | $50,000 | Olimpia Milano EuroLeague rotation/starter |
| 5044386 | St. John's | Zsombor Maronka | $50,000 | Hamburg Bundesliga and EuroCup |
| 5110117 | St. John's | Babacar Sane | $50,000 | Bundesliga; NBA G League; Senegal national team |
| 5399797 | Texas Tech | Bassala Bagayoko | $67,800 | Bilbao Basket Liga ACB |
| 5456498 | Ohio State | Lee Aaliya | $66,700 | UCAM Murcia Liga ACB; Argentina national team |

These **are NOT verified NIL salaries** and do not automatically translate to a specific dollar amount. Fees paid to release foreign club contracts (e.g., reported for LSU signings) are a different economic item from an athlete's NIL amount. School bio and press citations are embedded in the JSON.

## Bayes publisher: blocking flaw and proposed fix

The `scripts/nil_model/nil_season_engine.py` publisher correctly freezes preseason anchors. However, when a player has a frozen price **but no earlier ESPN CBB box**, the current logic falls into the branch: keep `score=baseline`; set `w=0`. This prevents even an international starter's NIL estimate from updating after games. It is **not season-ready for no-prior entrants**; do not treat a green workflow badge as proof of international rookie tracking.

Proposed architecture (hold for quantitative validation before publishing):
1. Separate `originalV4`, `freshmanHighSchool`, `internationalProfessional`, `otherNoPrior`. Keep a verified evidence tier, source links, confidence, and explicit opening-market price (when staff signs off).
2. Anchor every player's `P0` as immutable as-of Oct 27; Stock Watch must show zero preseason movement until verified box evidence. Keep club buyouts distinct from player NIL.
3. For prior ESPN CBB players, retain the current v3 same-model ratio approach. For entrants without prior CBB, create an **explicitly modeled neutral reference** using translated pro-league quality, role/expected minutes, team strength, age, size, competition, and scouting input. Never synthesize actual games or attach another player's stats.
4. With verified 2026–27 game and minutes evidence, score current college contribution against that fixed reference and apply a bounded, game/minutes-weighted *relative* update to P0. Freeze for low sample / no reference. Do not blend an uncalibrated absolute college model toward a professional NIL prior.
5. Test exposure gates (1, 5, 10, 20, 30 games at 5–30 MPG), injury/DNP handling, transfer / identity changes, and returner anchors. Reprice only via specific reviewed high-value player overrides; all other launch anchors stay intact.
6. Check team aggregate NIL against independently researched high-major spending ranges **without coercing individual prices to meet a team budget**.

**Do not yet apply a blanket percentage increase to players with non-US birthplaces.** This could overprice developmental players and underprice proven professional imports.

## West Florida team issue: resolved separately

The latest ESPN roster already contains 15 real athlete IDs for team 2697. The actual Teams-tab blank arose from the Torvik row missing its `espnTeamId`; the validated Torvik research publisher has been patched to map `West Florida` to `2697`, with a regression test. This does not change NIL prices, the ESPN roster, the website, or Google Sheets.
