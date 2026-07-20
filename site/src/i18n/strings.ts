// Every user-facing UI string lives here (English only in v1). Adding a locale later means
// adding a sibling file with the same shape — components never hardcode display text.

export const strings = {
  brand: {
    badge: "fk",
    title: "Dev Digest",
    subtitle: "plugin marketplace",
  },
  header: {
    searchPlaceholder: "Search plugins, skills, keywords…",
    clearSearch: "Clear",
    paletteTitle: "Command palette (Ctrl / ⌘ + K)",
    themeTitle: "Toggle theme",
    themeLight: "Light",
    themeDark: "Dark",
    homeTitle: "Home",
  },
  hero: {
    eyebrow: (n: number) => `${n} plugins`,
    titleLine1: "A calmer developer workflow,",
    titleLine2: "one plugin at a time.",
    tagline:
      "Reviews, tests, docs, and shippable digests for Claude Code. Browse the catalog, then add the marketplace and install what you need.",
  },
  stats: {
    externalClones: "external clones",
    externalClones14d: "external clones · last 14 days",
    copyInstalls: "install copies",
    views: "plugin views",
    caption:
      "Clone counts exclude this repository's own CI checkouts, but still include bots and mirrors — read them as an interest trend, not an install count. Copies and views are deliberate actions on this site.",
  },
  catalog: {
    categoryLabel: "Category",
    keywordsLabel: "Keywords",
    allCategory: "All",
    showingAll: (n: number) => `Showing all ${n} plugins`,
    matchCount: (n: number) => `${n} ${n === 1 ? "plugin" : "plugins"} match`,
    clearFilters: "clear filters ×",
    emptyTitle: "Nothing matches that.",
    emptySub: "Try a different keyword or clear your filters.",
    emptyReset: "Reset",
    stats: {
      skill: ["skill", "skills"] as const,
      agent: ["agent", "agents"] as const,
      command: ["command", "commands"] as const,
    },
  },
  detail: {
    back: "← all plugins",
    install: "Install",
    copy: "copy",
    copied: "✓ copied",
    installCommentAdd: "# add the marketplace once",
    installCommentPlugin: "# then install this plugin",
    skills: "Skills",
    agents: "Agents",
    commands: "Commands",
    hooks: "Hooks",
    dependencies: "Dependencies",
    available: (n: number) => `${n} available`,
    hookRowDesc: (event: string) => `Runs on the ${event} event.`,
    depView: "view →",
    depExternal: "external",
    author: "Author",
    repository: "Repository",
    keywords: "Keywords",
    usage: "Usage",
    usageLine: (copies: number, views: number) => `${copies} copy-installs · ${views} views`,
    noLicense: "—",
  },
  palette: {
    kbd: "⌘K",
    esc: "esc",
    placeholder: "Jump to a plugin, skill, agent, or command…",
    empty: "No matches.",
    enter: "↵",
  },
  footer: {
    links: [
      { label: "LinkedIn", url: "https://www.linkedin.com/in/feliks-kostukevych-44172396/" },
      { label: "GitHub", url: "https://github.com/felkost/dev-digest" },
    ],
    copyright: (year: number) => `© Feliks Kostukevych ${year}`,
  },
  error: {
    title: "Could not load the catalog.",
    sub: (message: string) => `The site could not fetch catalog.json (${message}).`,
    hint: "Serve this folder over HTTP — e.g. npm run preview — rather than opening files directly.",
  },
} as const;
