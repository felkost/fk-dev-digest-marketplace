import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { strings } from "../i18n/strings";
import { useCatalog } from "../lib/catalog";
import { buildEntries, buildIndex, searchEntries, type SearchEntry } from "../lib/search";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const { catalog } = useCatalog();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const entries = useMemo(() => (catalog ? buildEntries(catalog) : []), [catalog]);
  const index = useMemo(() => (entries.length ? buildIndex(entries) : null), [entries]);
  const list = useMemo<SearchEntry[]>(
    () => (index ? searchEntries(index, entries, query) : []),
    [index, entries, query],
  );
  const clampedActive = Math.min(active, Math.max(0, list.length - 1));

  // Reset and focus each time the palette opens.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      const t = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(t);
    }
  }, [open]);

  // Keyboard: Escape closes; arrows move; Enter selects.
  useEffect(() => {
    if (!open) return;
    function onKeydown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(a + 1, list.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(a - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const entry = list[clampedActive];
        if (entry) select(entry);
      }
    }
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  });

  // Keep the active row in view.
  useEffect(() => {
    resultsRef.current
      ?.querySelector('[aria-selected="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [clampedActive, list]);

  function select(entry: SearchEntry) {
    onClose();
    navigate(`/plugin/${entry.plugin}`);
    window.scrollTo(0, 0);
  }

  if (!open) return null;

  return (
    <div
      className="palette-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={strings.header.paletteTitle}
        className="palette-dialog"
      >
        <div className="palette-head">
          <span className="palette-kbd">{strings.palette.kbd}</span>
          <input
            ref={inputRef}
            className="palette-input"
            type="text"
            autoComplete="off"
            spellCheck={false}
            placeholder={strings.palette.placeholder}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
          />
          <span className="palette-esc">{strings.palette.esc}</span>
        </div>
        <div className="palette-results" ref={resultsRef}>
          {list.length === 0 ? (
            <div className="pal-empty">{strings.palette.empty}</div>
          ) : (
            list.map((entry, i) => (
              <button
                key={entry.id}
                className="pal-row"
                aria-selected={i === clampedActive}
                onClick={() => select(entry)}
                onMouseMove={() => setActive(i)}
              >
                <span
                  className={
                    "pal-type" +
                    (entry.type === "plugin" || entry.type === "command" ? " accent" : "")
                  }
                >
                  {entry.type}
                </span>
                <span className="pal-body">
                  <span className={"pal-label" + (entry.type === "plugin" ? " serif" : "")}>
                    {entry.label}
                  </span>
                  <span className="pal-sub">{entry.sub}</span>
                </span>
                <span className="pal-go">{strings.palette.enter}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
