export function initials(displayName: string): string {
  const parts = displayName.trim().split(/\s+/);
  let s = ((parts[0] || "")[0] || "") + ((parts[1] || "")[0] || "");
  if (!s) s = displayName.slice(0, 2);
  return s.toLowerCase();
}

export function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

export function commandLabel(name: string): string {
  return name.startsWith("/") ? name : "/" + name;
}

export function copyText(txt: string): void {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      void navigator.clipboard.writeText(txt);
      return;
    }
  } catch {
    /* fall through to the textarea fallback */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = txt;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  } catch {
    /* clipboard unavailable — nothing else we can do */
  }
}
