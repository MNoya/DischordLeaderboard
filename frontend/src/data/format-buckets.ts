import bucketsConfig from "../../../scoring_buckets.json";

interface BucketGroup {
  label: string;
  points: number;
  formats: string[];
  rule?: string;
}

const config = bucketsConfig as {
  groups: BucketGroup[];
  pod?: { trophy_points?: number; win_2_1_points?: number };
};
const GROUPS: readonly BucketGroup[] = config.groups;

export const POD_TROPHY_POINTS = config.pod?.trophy_points ?? 5;
export const POD_WIN_2_1_POINTS = config.pod?.win_2_1_points ?? 2;

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
