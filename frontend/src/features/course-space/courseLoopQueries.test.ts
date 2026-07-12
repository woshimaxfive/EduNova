import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { courseLoopKeys, courseLoopQueryKeys, invalidateCourseLearningLoop } from "./courseLoopQueries";

describe("course learning loop query identity", () => {
  it("uses one stable key for each course closure dataset", () => {
    expect(courseLoopKeys(808)).toEqual([
      ["courses", "learning-state", 808],
      ["courses", "mastery-map", 808],
      ["resources", "course", 808],
      ["paths", "current", 808],
      ["reports", "latest", 808],
      ["practice", "latest", 808]
    ]);
    expect(courseLoopQueryKeys.resources(808)).toEqual(["resources", "course", 808]);
  });

  it("invalidates every cached dataset without touching another course", async () => {
    const queryClient = new QueryClient();
    for (const queryKey of courseLoopKeys(808)) queryClient.setQueryData(queryKey, { ready: true });
    for (const queryKey of courseLoopKeys(809)) queryClient.setQueryData(queryKey, { ready: true });

    await invalidateCourseLearningLoop(queryClient, 808);

    expect(courseLoopKeys(808).every((queryKey) => queryClient.getQueryState(queryKey)?.isInvalidated)).toBe(true);
    expect(courseLoopKeys(809).every((queryKey) => !queryClient.getQueryState(queryKey)?.isInvalidated)).toBe(true);
  });
});
