import bucketsConfig from "../../../scoring_buckets.json";

interface BucketGroup {
  label: string;
  points: number;
  formats: string[];
  rule?: string;
}

const GROUPS: readonly BucketGroup[] = (bucketsConfig as { groups: BucketGroup[] }).groups;

export const FORMAT_BUCKETS: Record<string, string> = Object.fromEntries(
  GROUPS.flatMap((g) => g.formats.map((fmt) => [fmt, g.label] as const)),
);

export function formatsForBucket(bucket: string): string[] {
  return GROUPS.find((g) => g.label === bucket)?.formats ?? [];
}

export interface BucketDef {
  label: string;
  points: number;
  rule?: "lcq_draft_2";
}

export const BUCKET_DEFS: readonly BucketDef[] = GROUPS.map((g) => ({
  label: g.label,
  points: g.points,
  rule: g.rule as "lcq_draft_2" | undefined,
}));
