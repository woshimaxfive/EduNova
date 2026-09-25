export function tokenCount(total: number | null | undefined, known?: number | null): string {
  if (total != null) return total.toLocaleString();
  return known != null ? `已知 ${known.toLocaleString()} · 部分未知` : "未知";
}
