export function normalizeMindmapMarkdown(markdown: string) {
  return markdown
    .replace(/\$?\\rightarrow\$?/g, "→")
    .replace(/\$?\\leftarrow\$?/g, "←")
    .replace(/\$?\\leftrightarrow\$?/g, "↔");
}
