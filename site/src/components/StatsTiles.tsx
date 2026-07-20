import { useEffect, useState } from "react";
import { strings } from "../i18n/strings";
import { fetchSummary, statsEnabled, type StatsSummary } from "../lib/statsApi";

function formatCount(n: number): string {
  if (n >= 10_000) return (n / 1000).toFixed(n >= 100_000 ? 0 : 1).replace(/\.0$/, "") + "k";
  return n.toLocaleString("en-US");
}

// Homepage stat tiles fed by GET /api/stats. Renders nothing when the backend is not configured
// (VITE_STATS_API unset) or has no data yet, so the hero looks unchanged until numbers exist.
export function StatsTiles() {
  const [summary, setSummary] = useState<StatsSummary | null>(null);

  useEffect(() => {
    if (!statsEnabled()) return;
    let active = true;
    void fetchSummary().then((s) => {
      if (active) setSummary(s);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!summary) return null;

  // Clone tiles show the externally-attributable count only — the raw GitHub figure counts this
  // repo's own CI checkouts as clones, which says nothing about interest in the plugins.
  const tiles: Array<{ value: number; label: string; accent?: boolean }> = [
    { value: summary.externalClones, label: strings.stats.externalClones, accent: true },
    { value: summary.externalClones14d, label: strings.stats.externalClones14d },
    { value: summary.copyInstalls, label: strings.stats.copyInstalls },
    { value: summary.views, label: strings.stats.views },
  ];

  // Until tracking has been running longer than the 14-day window, every recorded clone is also a
  // last-14-days clone, so the second tile would just repeat the first. Show it only once it says
  // something the total does not.
  const redundant14d = summary.externalClones14d === summary.externalClones;

  // Until the clone harvester has run, both clone tiles are 0 — drop them so we never show an
  // all-zero row; keep any tile that has data.
  const shown = tiles.filter(
    (t) => t.value > 0 && !(redundant14d && t.label === strings.stats.externalClones14d),
  );
  if (shown.length === 0) return null;

  return (
    <div className="stats">
      <div className="stats-tiles">
        {shown.map((t) => (
          <div className={"stat-tile" + (t.accent ? " accent" : "")} key={t.label}>
            <span className="stat-value">{formatCount(t.value)}</span>
            <span className="stat-label">{t.label}</span>
          </div>
        ))}
      </div>
      <p className="stats-caption">{strings.stats.caption}</p>
    </div>
  );
}
