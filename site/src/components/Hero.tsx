import { strings } from "../i18n/strings";
import { StatsTiles } from "./StatsTiles";

export function Hero({ total }: { total: number }) {
  return (
    <section className="hero">
      <p className="hero-eyebrow">{strings.hero.eyebrow(total)}</p>
      <h1 className="hero-title">
        {strings.hero.titleLine1}
        <br />
        {strings.hero.titleLine2}
      </h1>
      <p className="hero-tagline">{strings.hero.tagline}</p>
      <StatsTiles />
    </section>
  );
}
