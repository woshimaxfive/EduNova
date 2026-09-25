export function suggestedModelBaseUrl(value: string): string | null {
  try {
    const url = new URL(value.trim());
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) return null;
    const path = url.pathname.replace(/\/+$/, "");
    const base = path.replace(/\/(chat\/completions|responses|models)$/, "");
    return base !== path ? `${url.origin}${base}` : null;
  } catch { return null; }
}
