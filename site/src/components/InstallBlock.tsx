import { useEffect, useRef, useState } from "react";
import { strings } from "../i18n/strings";
import { installCommandFor, useCatalog } from "../lib/catalog";
import { trackEvent } from "../lib/statsApi";
import type { Plugin } from "../lib/types";
import { copyText } from "../lib/util";

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect
        x="5.5"
        y="5.5"
        width="8.5"
        height="8.5"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M3.5 10.5H2.75A1.25 1.25 0 0 1 1.5 9.25v-6.5A1.25 1.25 0 0 1 2.75 1.5h6.5A1.25 1.25 0 0 1 10.5 2.75v.75"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3 8.5l3 3 7-7"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface InstallRowProps {
  comment: string;
  command: string;
  copied: boolean;
  onCopy: () => void;
  showCaret?: boolean;
}

function InstallRow({ comment, command, copied, onCopy, showCaret }: InstallRowProps) {
  return (
    <div className="install-row">
      <div className="install-row-lines">
        <span className="comment">{comment}</span>
        <code className="install-row-cmd">
          {command}
          {showCaret && <span className="caret" />}
        </code>
      </div>
      <button
        className={"icon-copy-btn" + (copied ? " copied" : "")}
        onClick={onCopy}
        title={copied ? strings.detail.copied : strings.detail.copy}
        aria-label={copied ? strings.detail.copied : strings.detail.copy}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
    </div>
  );
}

export function InstallBlock({ plugin }: { plugin: Plugin }) {
  const { catalog } = useCatalog();
  const [copiedAdd, setCopiedAdd] = useState(false);
  const [copiedInstall, setCopiedInstall] = useState(false);
  const addTimer = useRef<number | undefined>(undefined);
  const installTimer = useRef<number | undefined>(undefined);

  useEffect(
    () => () => {
      window.clearTimeout(addTimer.current);
      window.clearTimeout(installTimer.current);
    },
    [],
  );

  if (!catalog) return null;
  const addCmd = catalog.marketplace.addCommand;
  const installCmd = installCommandFor(catalog, plugin.name);

  function onCopyAdd() {
    copyText(addCmd);
    setCopiedAdd(true);
    window.clearTimeout(addTimer.current);
    addTimer.current = window.setTimeout(() => setCopiedAdd(false), 1800);
  }

  function onCopyInstall() {
    copyText(installCmd);
    trackEvent("copy_install", plugin.name);
    setCopiedInstall(true);
    window.clearTimeout(installTimer.current);
    installTimer.current = window.setTimeout(() => setCopiedInstall(false), 1800);
  }

  return (
    <div className="install">
      <div className="install-head">
        <span className="install-left">
          <span className="dots">
            <span className="dot" />
            <span className="dot" />
            <span className="dot accent" />
          </span>
          <span className="install-label">{strings.detail.install}</span>
        </span>
      </div>
      <div className="install-rows">
        <InstallRow
          comment={strings.detail.installCommentAdd}
          command={addCmd}
          copied={copiedAdd}
          onCopy={onCopyAdd}
        />
        <InstallRow
          comment={strings.detail.installCommentPlugin}
          command={installCmd}
          copied={copiedInstall}
          onCopy={onCopyInstall}
          showCaret
        />
      </div>
    </div>
  );
}
