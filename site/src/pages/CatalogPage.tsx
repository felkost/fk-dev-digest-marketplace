import { useMemo } from "react";
import { Hero } from "../components/Hero";
import { PluginCard } from "../components/PluginCard";
import { Sidebar } from "../components/Sidebar";
import { strings } from "../i18n/strings";
import { useCatalog } from "../lib/catalog";
import { useFilters } from "../lib/filters";
import { buildEntries, buildIndex, matchingPlugins } from "../lib/search";

export function CatalogPage() {
  const { catalog, error } = useCatalog();
  const { search, category, keyword, clearAll } = useFilters();

  const index = useMemo(() => (catalog ? buildIndex(buildEntries(catalog)) : null), [catalog]);

  const filtered = useMemo(() => {
    if (!catalog || !index) return [];
    const matchSet = matchingPlugins(index, search);
    return catalog.plugins.filter(
      (p) =>
        (matchSet === null || matchSet.has(p.name)) &&
        (category === strings.catalog.allCategory || p.category === category) &&
        (!keyword || (p.keywords || []).includes(keyword)),
    );
  }, [catalog, index, search, category, keyword]);

  if (error) {
    return (
      <div className="load-error">
        <p className="load-error-title">{strings.error.title}</p>
        <p className="load-error-sub">{strings.error.sub(error)}</p>
        <p className="load-error-hint">{strings.error.hint}</p>
      </div>
    );
  }
  if (!catalog) return null;

  const total = catalog.plugins.length;
  const n = filtered.length;
  const filtersActive = !!(search || category !== strings.catalog.allCategory || keyword);
  const summary = n === total ? strings.catalog.showingAll(n) : strings.catalog.matchCount(n);

  return (
    <main className="page">
      <Hero total={total} />
      <div className="layout">
        <Sidebar plugins={catalog.plugins} />
        <div className="results">
          <div className="results-head">
            <p className="result-summary">{summary}</p>
            {filtersActive && (
              <button className="link-btn" onClick={clearAll}>
                {strings.catalog.clearFilters}
              </button>
            )}
          </div>
          {n > 0 ? (
            <div className="card-grid">
              {filtered.map((p) => (
                <PluginCard key={p.name} plugin={p} />
              ))}
            </div>
          ) : (
            <div className="empty">
              <p className="empty-title">{strings.catalog.emptyTitle}</p>
              <p className="empty-sub">{strings.catalog.emptySub}</p>
              <button className="empty-reset" onClick={clearAll}>
                {strings.catalog.emptyReset}
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
