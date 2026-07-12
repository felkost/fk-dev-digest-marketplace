import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { strings } from "../i18n/strings";
import { useFilters } from "../lib/filters";
import { useTheme } from "../lib/theme";

interface HeaderProps {
  onOpenPalette: () => void;
  paletteOpen: boolean;
}

export function Header({ onOpenPalette, paletteOpen }: HeaderProps) {
  const { search, setSearch } = useFilters();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const inputRef = useRef<HTMLInputElement>(null);

  // "/" focuses the search box unless the user is already typing somewhere or the palette is open.
  useEffect(() => {
    function onKeydown(e: KeyboardEvent) {
      if (paletteOpen) return;
      const target = e.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA");
      if (e.key === "/" && !typing) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, [paletteOpen]);

  function onSearchChange(value: string) {
    setSearch(value);
    if (location.pathname !== "/") navigate("/");
  }

  function goHome() {
    navigate("/");
    window.scrollTo(0, 0);
  }

  return (
    <header className="site-header">
      <div className="header-inner">
        <button className="logo-btn" title={strings.header.homeTitle} onClick={goHome}>
          <span className="logo-badge">{strings.brand.badge}</span>
          <span className="logo-text">
            <span className="logo-title">{strings.brand.title}</span>
            <span className="logo-sub">{strings.brand.subtitle}</span>
          </span>
        </button>

        <div className="search-box">
          <span className="search-slash">/</span>
          <input
            ref={inputRef}
            className="search-input"
            type="text"
            autoComplete="off"
            spellCheck={false}
            placeholder={strings.header.searchPlaceholder}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape" && search) onSearchChange("");
            }}
          />
          {search && (
            <button
              className="search-clear"
              title={strings.header.clearSearch}
              onClick={() => onSearchChange("")}
            >
              ×
            </button>
          )}
        </div>

        <button className="header-btn" title={strings.header.paletteTitle} onClick={onOpenPalette}>
          <span style={{ fontSize: 13 }}>⌘</span>K
        </button>

        <button className="header-btn" title={strings.header.themeTitle} onClick={toggleTheme}>
          <span className="theme-dot" />
          {theme === "dark" ? strings.header.themeDark : strings.header.themeLight}
        </button>
      </div>
    </header>
  );
}
