import { strings } from "../i18n/strings";
import { useFilters } from "../lib/filters";
import type { Plugin } from "../lib/types";

export function Sidebar({ plugins }: { plugins: Plugin[] }) {
  const { category, keyword, setCategory, toggleKeyword } = useFilters();

  const cats = [
    strings.catalog.allCategory,
    ...Array.from(new Set(plugins.map((p) => p.category))),
  ];
  const keywords = Array.from(new Set(plugins.flatMap((p) => p.keywords || []))).sort();

  return (
    <aside className="sidebar">
      <div className="side-group">
        <p className="side-label">{strings.catalog.categoryLabel}</p>
        <div className="cat-list">
          {cats.map((c) => (
            <button
              key={c}
              className={"cat-btn" + (c === category ? " active" : "")}
              onClick={() => setCategory(c)}
            >
              <span>{c}</span>
              <span className="cat-count">
                {c === strings.catalog.allCategory
                  ? plugins.length
                  : plugins.filter((p) => p.category === c).length}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div>
        <p className="side-label">{strings.catalog.keywordsLabel}</p>
        <div className="kw-wrap">
          {keywords.map((k) => (
            <button
              key={k}
              className={"chip" + (k === keyword ? " active" : "")}
              onClick={() => toggleKeyword(k)}
            >
              {k}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
