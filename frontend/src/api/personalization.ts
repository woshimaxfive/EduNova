export type PersonalizationFreshness = {
  status: "current" | "stale" | "legacy";
  profile_applied_version: number | null;
  current_profile_applied_version: number;
  reason: string;
};
