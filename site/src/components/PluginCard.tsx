import { useNavigate } from "react-router-dom";
import { strings } from "../i18n/strings";
import type { Plugin } from "../lib/types";
import { initials, plural } from "../lib/util";

export function PluginCard({ plugin }: { plugin: Plugin }) {
  const navigate = useNavigate();
  const stats: Array<{ count: number; labels: readonly [string, string] }> = [
    { count: plugin.skills.length, labels: strings.catalog.stats.skill },
    { count: plugin.agents.length, labels: strings.catalog.stats.agent },
    { count: plugin.commands.length, labels: strings.catalog.stats.command },
  ];

  return (
    <button className="plugin-card" onClick={() => navigate(`/plugin/${plugin.name}`)}>
      <div className="card-head">
        <span className="card-avatar">{initials(plugin.displayName)}</span>
        <span className="card-body">
          <span className="card-titlerow">
            <span className="card-title">{plugin.displayName}</span>
            <span className="card-version">v{plugin.version}</span>
          </span>
          <span className="card-category">{plugin.category}</span>
        </span>
      </div>
      <p className="card-desc">{plugin.description}</p>
      <div className="stats-row">
        {stats.map((st, i) => (
          <span className="stat-pill" key={i}>
            <b>{st.count}</b> {plural(st.count, st.labels[0], st.labels[1])}
          </span>
        ))}
      </div>
    </button>
  );
}
