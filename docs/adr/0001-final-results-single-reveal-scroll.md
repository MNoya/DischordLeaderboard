# P0P1 final results is a single reveal scroll

The final-results view briefly shipped as three tabs (OVERVIEW / FULL RESULTS / BREAKDOWN) — the only page-level tab bar on the site. We replaced it with one narrative scroll: broadcast top-3 → highlights reel → full standings. The page is consumed as a one-time reveal moment announced in Discord, so paced top-to-bottom storytelling beats random access, and `?tab=` deep links carry no value.

Two deliberate asymmetries with the midway phase:

- **The GIH winrate breakdown is cut from final** while midway keeps its inline `MidwayBreakdownList`. The highlights reel and the per-row pick-grid expanders already tell the final data story; the raw breakdown earned a tab only because a tab bar existed.
- **The full standings mount progressively** (chunks of rows ahead of an IntersectionObserver sentinel, lazy art-crop images, `content-visibility` row containment) instead of eagerly or via virtualization. The field is expected at 100–300 ballots and each row's contribution bar carries up to 8 card-art images, so an eager mount stalls visibly, while a virtual list is unwarranted complexity at this scale.

The alternate `?top3=spotlight` champion treatment was deleted at the same time; broadcast is the only top-3 treatment.
