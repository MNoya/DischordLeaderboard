export const FORMAT_BUCKETS: Record<string, string> = {
  PremierDraft: "Premier",
  ContenderDraft: "Premier",
  TradDraft: "Trad",
  Sealed: "Sealed",
  TradSealed: "Sealed",
  ArenaDirect_Sealed: "Sealed",
  QualifierPlayInSealed: "Sealed",
  QualifierPlayInTradSealed: "Sealed",
  Qualifier_D1_Sealed: "Sealed",
  Qualifier_D2_Sealed: "Sealed",
  QuickDraft: "Quick",
  PickTwoDraft: "Quick",
  Emblem_QuickDraft: "Quick",
  LimitedChampionshipQualifier_Draft1: "LCQ Draft 1",
  LimitedChampionshipQualifier_Draft2: "LCQ Draft 2",
};

export function formatsForBucket(bucket: string): string[] {
  return Object.entries(FORMAT_BUCKETS)
    .filter(([, b]) => b === bucket)
    .map(([fmt]) => fmt);
}
