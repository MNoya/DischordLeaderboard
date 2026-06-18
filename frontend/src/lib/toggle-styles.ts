// Shared active/inactive treatments for toggle controls so a change to the look cascades at once.
// Two variants: TOGGLE_* is the subtle tint for color chips and dropdown triggers; FILTER_* is the
// solid green selection for filter pills and segmented sorts, matching nav and the set switcher.

export const TOGGLE_ACTIVE = "border-green bg-green/10 text-green";
export const TOGGLE_INACTIVE = "border-border2 bg-transparent text-muted hover:bg-surface";

export const FILTER_ACTIVE = "border-green bg-green text-bg";
export const FILTER_INACTIVE = "border-border bg-transparent text-text hover:border-green";
