// MiniSearch-backed search over every plugin, skill, agent, and command. One index serves both
// the catalog filter (map hits back to owning plugins) and the command palette (individual hits).

import MiniSearch from "minisearch";
import type { Catalog } from "./types";
import { commandLabel } from "./util";

export type EntryType = "plugin" | "skill" | "agent" | "command";

export interface SearchEntry {
  id: string;
  type: EntryType;
  /** Display label (plugin displayName / skill name / "/command"). */
  label: string;
  /** Secondary line: owning plugin (or category for plugins). */
  sub: string;
  /** Owning plugin's package name — what a hit resolves to. */
  plugin: string;
  description: string;
  keywords: string;
}

export function buildEntries(catalog: Catalog): SearchEntry[] {
  const entries: SearchEntry[] = [];
  for (const p of catalog.plugins) {
    entries.push({
      id: "plugin__" + p.name,
      type: "plugin",
      label: p.displayName,
      sub: p.category,
      plugin: p.name,
      description: p.description + " " + p.name,
      keywords: (p.keywords || []).join(" "),
    });
    for (const s of p.skills || []) {
      entries.push({
        id: "skill__" + p.name + "__" + s.name,
        type: "skill",
        label: s.name,
        sub: p.displayName,
        plugin: p.name,
        description: s.description,
        keywords: "",
      });
    }
    for (const a of p.agents || []) {
      entries.push({
        id: "agent__" + p.name + "__" + a.name,
        type: "agent",
        label: a.name,
        sub: p.displayName,
        plugin: p.name,
        description: a.description,
        keywords: "",
      });
    }
    for (const c of p.commands || []) {
      entries.push({
        id: "command__" + p.name + "__" + c.name,
        type: "command",
        label: commandLabel(c.name),
        sub: p.displayName,
        plugin: p.name,
        description: c.description,
        keywords: "",
      });
    }
  }
  return entries;
}

export function buildIndex(entries: SearchEntry[]): MiniSearch<SearchEntry> {
  const index = new MiniSearch<SearchEntry>({
    fields: ["label", "description", "keywords", "sub"],
    storeFields: ["type", "label", "sub", "plugin"],
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
      combineWith: "AND",
    },
  });
  index.addAll(entries);
  return index;
}

/** Palette hits for a query (all entries, capped, when the query is empty). */
export function searchEntries(
  index: MiniSearch<SearchEntry>,
  entries: SearchEntry[],
  query: string,
  limit = 40,
): SearchEntry[] {
  const q = query.trim();
  if (!q) return entries.slice(0, limit);
  return index.search(q).slice(0, limit) as unknown as SearchEntry[];
}

/** Set of plugin names matching a query via any of their components; null means "no filter". */
export function matchingPlugins(index: MiniSearch<SearchEntry>, query: string): Set<string> | null {
  const q = query.trim();
  if (!q) return null;
  const hits = index.search(q) as unknown as Array<{ plugin: string }>;
  return new Set(hits.map((h) => h.plugin));
}
