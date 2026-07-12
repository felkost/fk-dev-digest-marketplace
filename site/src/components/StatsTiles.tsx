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

  const tiles: Array<{ value: number; label: string; accent?: boolean }> = [
    { value: summary.clonesTotal, label: strings.stats.clonesTotal, accent: true },
    { value: summary.clones14d, label: strings.stats.clones14d },
    { value: summary.copyInstalls, label: strings.stats.copyInstalls },
    { value: summary.views, label: strings.stats.views },
  ];

  // Until the clone harvester has run, both clone tiles are 0 — drop them so we never show an
  // all-zero row; keep any tile that has data.
  const shown = tiles.filter((t) => t.value > 0);
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
