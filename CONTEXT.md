# LLU Leaderboard

Discord bot + public website ranking an MTGA community's drafting within the current Magic set, plus side contests like Pack 0 Pick 1 (P0P1).

## Language

### P0P1 highlights

**Highlight**:
One entry in the final-results highlights reel — a Trap or a Sleeper.
_Avoid_: Overrated/underrated tile, rank gap

**The Trap**:
A card many voters picked that underperformed the best card available in its slot.
_Avoid_: Overrated, mistake, bad pick

**The Sleeper**:
A card almost nobody (possibly nobody) picked that outperformed the slot's crowd favorite. Zero-vote cards are eligible. The only voter-named highlight — its pickers are shown by name; personal callouts are positive-only, negative stories stay at the card level.
_Avoid_: Underrated, hidden gem, Prophet (retired award, merged into the Sleeper)

**Drama score**:
The per-category magnitude used to select and order highlights; normalized within category to interleave the mixed feed.
_Avoid_: Gap, rank gap, weight

**Eligible pool**:
All cards a slot's filter admits, regardless of whether anyone picked them. Distinct from pick stats, which only contain cards with at least one vote.
_Avoid_: Candidates, options

**Crowd favorite**:
The most-picked card in a slot.
_Avoid_: Most popular, consensus pick

**Slot best**:
The highest-GIHWR above-floor card in a slot's eligible pool. May differ from the best-possible team's card for that slot (the team optimizes across slots under the uniqueness constraint).
_Avoid_: Best pick, winner

**Sample floor**:
The minimum 17lands GIH sample (500) below which a card's rating is treated as missing data.
_Avoid_: Threshold, cutoff
