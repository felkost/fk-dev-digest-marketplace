// Optional usage-stats client. The backend base URL comes from VITE_STATS_API at build time;
// when it is unset every function here is a graceful no-op, so the site works with no backend
// at all. Events are fire-and-forget (keepalive) and carry no PII — just an event type and a
// plugin name.

export type StatsEventType = "copy_install" | "plugin_view";

export interface PluginUsage {
  copy_install?: number;
  plugin_view?: number;
}

export interface ClonesSummary {
  since: string | null;
  recordedDays: number;
  totalSinceTracking: number;
  last14dCount: number;
  last14dUniques: number;
}

export interface StatsResponse {
  generatedAt: string;
  perPlugin?: Record<string, PluginUsage>;
  totals?: PluginUsage;
  clones?: ClonesSummary;
}

/** The homepage tile numbers, derived from the full stats payload. */
export interface StatsSummary {
  copyInstalls: number;
  views: number;
  clonesTotal: number;
  clones14d: number;
}

const base = (import.meta.env.VITE_STATS_API as string | undefined)?.replace(/\/+$/, "");

export function statsEnabled(): boolean {
  return Boolean(base);
}

export function trackEvent(type: StatsEventType, plugin: string): void {
  if (!base) return;
  try {
    void fetch(`${base}/api/events`, {
      method: "POST",
      keepalive: true,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ type, plugin }),
    }).catch(() => {
      /* stats are best-effort — never surface a failure to the user */
    });
  } catch {
    /* ignore */
  }
}

// The whole site needs /api/stats at most once per load: the homepage tile and any open detail
// page read from the same payload. Cache the in-flight promise so concurrent callers share it.
let statsPromise: Promise<StatsResponse | null> | null = null;

export function fetchStats(): Promise<StatsResponse | null> {
  if (!base) return Promise.resolve(null);
  if (!statsPromise) {
    statsPromise = fetch(`${base}/api/stats`)
      .then((res) => (res.ok ? (res.json() as Promise<StatsResponse>) : null))
      .catch(() => null);
  }
  return statsPromise;
}

export async function fetchUsage(plugin: string): Promise<PluginUsage | null> {
  const data = await fetchStats();
  return data?.perPlugin?.[plugin] ?? null;
}

export async function fetchSummary(): Promise<StatsSummary | null> {
  const data = await fetchStats();
  if (!data) return null;
  return {
    copyInstalls: data.totals?.copy_install ?? 0,
    views: data.totals?.plugin_view ?? 0,
    clonesTotal: data.clones?.totalSinceTracking ?? 0,
    clones14d: data.clones?.last14dCount ?? 0,
  };
}
