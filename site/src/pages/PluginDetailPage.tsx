import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { InstallBlock } from "../components/InstallBlock";
import { strings } from "../i18n/strings";
import { useCatalog, usePlugin } from "../lib/catalog";
import { useFilters } from "../lib/filters";
import { fetchUsage, trackEvent, type PluginUsage } from "../lib/statsApi";
import type { Plugin } from "../lib/types";
import { commandLabel, initials } from "../lib/util";

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="section">
      <h2 className="section-title">{title}</h2>
      <p className="section-count">{strings.detail.available(count)}</p>
      <div className="table">{children}</div>
    </section>
  );
}

function Dependencies({ plugin }: { plugin: Plugin }) {
  const { catalog } = useCatalog();
  const navigate = useNavigate();
  if (!catalog || plugin.dependencies.length === 0) return null;

  return (
    <section className="section">
      <h2 className="section-title">{strings.detail.dependencies}</h2>
      <div className="dep-list">
        {plugin.dependencies.map((d) => {
          const dep = catalog.plugins.find((p) => p.name === d.name);
          const dn = dep ? dep.displayName : d.name;
          return (
            <button
              key={d.name}
              className="dep-row"
              disabled={!dep}
              onClick={() => {
                if (dep) {
                  navigate(`/plugin/${d.name}`);
                  window.scrollTo(0, 0);
                }
              }}
            >
              <span className="dep-left">
                <span className="dep-avatar">{initials(dn)}</span>
                <span>
                  <span className="dep-display">{dn}</span>
                  <span className="dep-pkg">
                    {d.name} {d.version || ""}
                  </span>
                </span>
              </span>
              <span className="dep-action">
                {dep ? strings.detail.depView : strings.detail.depExternal}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function Meta({ plugin, usage }: { plugin: Plugin; usage: PluginUsage | null }) {
  const { catalog } = useCatalog();
  const { setKeyword } = useFilters();
  const navigate = useNavigate();
  if (!catalog) return null;
  const mk = catalog.marketplace;
  const author = plugin.author || mk.owner;
  const hasUsage =
    usage !== null && ((usage.copy_install ?? 0) > 0 || (usage.plugin_view ?? 0) > 0);

  return (
    <section className="meta">
      <div className="meta-col-author">
        <p className="meta-label">{strings.detail.author}</p>
        <p className="meta-email">{author.email}</p>
      </div>
      <div className="meta-col-repo">
        <p className="meta-label">{strings.detail.repository}</p>
        <a
          className="meta-repo"
          href={plugin.repository || mk.repository}
          target="_blank"
          rel="noopener noreferrer"
        >
          {mk.repoShort}
        </a>
      </div>
      <div className="meta-col-keywords">
        <p className="meta-label">{strings.detail.keywords}</p>
        <div className="kw-chips">
          {(plugin.keywords || []).map((k) => (
            <button
              key={k}
              className="chip"
              onClick={() => {
                setKeyword(k);
                navigate("/");
                window.scrollTo(0, 0);
              }}
            >
              {k}
            </button>
          ))}
        </div>
      </div>
      {hasUsage && (
        <div className="meta-col-usage">
          <p className="meta-label">{strings.detail.usage}</p>
          <p className="meta-name">
            {strings.detail.usageLine(usage?.copy_install ?? 0, usage?.plugin_view ?? 0)}
          </p>
        </div>
      )}
    </section>
  );
}

export function PluginDetailPage() {
  const { name } = useParams<{ name: string }>();
  const { catalog, error } = useCatalog();
  const plugin = usePlugin(name);
  const navigate = useNavigate();
  const [usage, setUsage] = useState<PluginUsage | null>(null);

  // Count the view and load this plugin's usage numbers (both no-ops without VITE_STATS_API).
  useEffect(() => {
    if (!plugin) return;
    trackEvent("plugin_view", plugin.name);
    let active = true;
    void fetchUsage(plugin.name).then((u) => {
      if (active) setUsage(u);
    });
    return () => {
      active = false;
    };
  }, [plugin?.name]);

  if (error) return <Navigate to="/" replace />;
  if (!catalog) return null;
  if (!plugin) return <Navigate to="/" replace />;

  return (
    <main className="detail">
      <button className="back-btn" onClick={() => navigate("/")}>
        {strings.detail.back}
      </button>

      <div className="detail-head">
        <span className="detail-avatar">{initials(plugin.displayName)}</span>
        <div className="detail-headbody">
          <div className="detail-titlerow">
            <h1 className="detail-title">{plugin.displayName}</h1>
            <span className="badge-version">v{plugin.version}</span>
          </div>
          <div className="detail-metarow">
            <span className="accent">{plugin.category}</span>
            <span>·</span>
            <span>{plugin.name}</span>
            <span>·</span>
            <span>{plugin.license || strings.detail.noLicense}</span>
          </div>
        </div>
      </div>

      <p className="detail-desc">{plugin.description}</p>

      <InstallBlock plugin={plugin} />

      {plugin.skills.length > 0 && (
        <Section title={strings.detail.skills} count={plugin.skills.length}>
          {plugin.skills.map((s) => (
            <div className="trow" key={s.name}>
              <span className="tname">{s.name}</span>
              <span className="tdesc">{s.description}</span>
            </div>
          ))}
        </Section>
      )}

      {plugin.agents.length > 0 && (
        <Section title={strings.detail.agents} count={plugin.agents.length}>
          {plugin.agents.map((a) => (
            <div className="trow" key={a.name}>
              <span className="tname-flex">
                <span className="tname">{a.name}</span>
                {a.model && <span className="model-badge">{a.model}</span>}
              </span>
              <span className="tdesc">{a.description}</span>
            </div>
          ))}
        </Section>
      )}

      {plugin.commands.length > 0 && (
        <Section title={strings.detail.commands} count={plugin.commands.length}>
          {plugin.commands.map((c) => (
            <div className="trow" key={c.name}>
              <span className="tname cmd">{commandLabel(c.name)}</span>
              <span className="tdesc">{c.description}</span>
            </div>
          ))}
        </Section>
      )}

      {plugin.hookEvents.length > 0 && (
        <Section title={strings.detail.hooks} count={plugin.hookEvents.length}>
          {plugin.hookEvents.map((h) => (
            <div className="trow" key={h}>
              <span className="tname">{h}</span>
              <span className="tdesc">{strings.detail.hookRowDesc(h)}</span>
            </div>
          ))}
        </Section>
      )}

      <Dependencies plugin={plugin} />
      <Meta plugin={plugin} usage={usage} />
    </main>
  );
}
