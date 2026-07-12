import { useEffect, useState } from "react";
import { HashRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { CommandPalette } from "./components/CommandPalette";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { CatalogProvider } from "./lib/catalog";
import { FiltersProvider } from "./lib/filters";
import { ThemeProvider, useTheme } from "./lib/theme";
import { CatalogPage } from "./pages/CatalogPage";
import { PluginDetailPage } from "./pages/PluginDetailPage";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function Shell() {
  const { theme } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);

  // ⌘/Ctrl-K toggles the command palette from anywhere.
  useEffect(() => {
    function onKeydown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    }
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, []);

  return (
    <div className="app-root" data-theme={theme}>
      <div className="top-strip" />
      <Header onOpenPalette={() => setPaletteOpen(true)} paletteOpen={paletteOpen} />
      <div className="app-main">
        <ScrollToTop />
        <Routes>
          <Route path="/" element={<CatalogPage />} />
          <Route path="/plugin/:name" element={<PluginDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <CatalogProvider>
        <FiltersProvider>
          <HashRouter>
            <Shell />
          </HashRouter>
        </FiltersProvider>
      </CatalogProvider>
    </ThemeProvider>
  );
}
