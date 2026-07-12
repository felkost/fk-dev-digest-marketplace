import { strings } from "../i18n/strings";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <nav className="footer-links">
          {strings.footer.links.map((link) => (
            <a
              key={link.label}
              className="footer-link"
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <span>{strings.footer.copyright(new Date().getFullYear())}</span>
      </div>
    </footer>
  );
}
