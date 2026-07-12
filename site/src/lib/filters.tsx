// Catalog filter state (search text, category, keyword). Lives above the router so the header
// search box and both pages share it.

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { strings } from "../i18n/strings";

interface FiltersState {
  search: string;
  category: string;
  keyword: string | null;
  setSearch: (v: string) => void;
  setCategory: (v: string) => void;
  toggleKeyword: (v: string) => void;
  setKeyword: (v: string | null) => void;
  clearAll: () => void;
}

const FiltersContext = createContext<FiltersState | null>(null);

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>(strings.catalog.allCategory);
  const [keyword, setKeyword] = useState<string | null>(null);

  const value = useMemo<FiltersState>(
    () => ({
      search,
      category,
      keyword,
      setSearch,
      setCategory,
      setKeyword,
      toggleKeyword: (k) => setKeyword((prev) => (prev === k ? null : k)),
      clearAll: () => {
        setSearch("");
        setCategory(strings.catalog.allCategory);
        setKeyword(null);
      },
    }),
    [search, category, keyword],
  );

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersState {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useFilters must be used inside FiltersProvider");
  return ctx;
}
