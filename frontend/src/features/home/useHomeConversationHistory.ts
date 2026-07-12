import { useInfiniteQuery } from "@tanstack/react-query";

import { listHomeTutorHistory } from "../../api/tutor";

export const homeHistoryQueryKey = (query = "") => ["tutor", "home-history", query.trim()] as const;

export function useHomeConversationHistory(query = "", enabled = true) {
  return useInfiniteQuery({
    queryKey: homeHistoryQueryKey(query),
    queryFn: ({ pageParam }) => listHomeTutorHistory({ page: pageParam, pageSize: 30, query }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (lastPage.data?.has_more ? lastPage.data.page + 1 : undefined),
    enabled,
    staleTime: 30_000
  });
}
