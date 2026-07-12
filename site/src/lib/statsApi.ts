// Optional usage-stats client. The backend base URL comes from VITE_STATS_API at build time;
// when it is unset every function here is a graceful no-op, so the site works with no backend
// at all. Events are fire-and-forget (keepalive) and carry no PII — just an event type and a
// plugin name.

export type StatsEventType = "copy_install" | "plugin_view";

export interface PluginUsage {
  copy_install?: number;
  plugin_view?: number;
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

export async function fetchUsage(plugin: string): Promise<PluginUsage | null> {
  if (!base) return null;
  try {
    const res = await fetch(`${base}/api/stats`);
    if (!res.ok) return null;
    const data = (await res.json()) as { perPlugin?: Record<string, PluginUsage> };
    return data.perPlugin?.[plugin] ?? null;
  } catch {
    return null;
  }
}
