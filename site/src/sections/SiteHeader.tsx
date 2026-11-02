import type { CSSProperties } from "react";
import { content } from "../data/content";
import { TourSlide } from "./Tour";

const iconUrl = `${import.meta.env.BASE_URL}readme-icon.png`;

export function SiteHeader({
  active,
  setActive,
  paused,
  holding,
  onToggle,
}: {
  active: number;
  setActive: (value: number) => void;
  paused: boolean;
  holding: boolean;
  onToggle: () => void;
}) {
  const navigation = ["Pipeline", "Try it", "Results", "Features", "Quick start", "FAQ"];
  const anchors = ["#how", "#try", "#results", "#features", "#start", "#faq"];
  return (
    <>
      <nav className="top" aria-label="Main">
        <a className="brand" href="#top">
          <img className="brand-icon" src={iconUrl} alt="" width="22" height="22" />
          SyncMesh
        </a>
        <div className="links">
          {navigation.map((label, index) => (
            <a href={anchors[index]} key={label}>
              {label}
            </a>
          ))}
        </div>
        <div className="sp">
          <a className="pill" href={content.hero.github} target="_blank" rel="noreferrer">
            GitHub
          </a>
          <a className="pill w" href="#start">
            Run it locally
          </a>
        </div>
      </nav>
      <header className={`hero ${paused || holding ? "hold" : ""}`} id="top">
        <h1>
          Make offline changes.
          <br />
          See every replica converge.
        </h1>
        <p>
          SyncMesh lets independent inventory nodes keep working without a network, then
          exchange and merge their changes with deterministic, reviewable rules.
        </p>
        <div className="cta">
          <a className="pill w" href="#try">
            Try the replication lab
          </a>
          <a className="pill" href={content.hero.github} target="_blank" rel="noreferrer">
            View on GitHub
          </a>
        </div>
        <div className="tabs">
          <div className="tl" role="tablist" aria-label="Replication stages" id="tl">
            {content.tour.map((stage, index) => (
              <button
                className="tab"
                type="button"
                role="tab"
                id={`stage-${index}`}
                aria-selected={active === index}
                aria-controls="tour-panel"
                tabIndex={active === index ? 0 : -1}
                key={stage.label}
                onClick={() => setActive(index)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                    event.preventDefault();
                    const next =
                      (active + (event.key === "ArrowRight" ? 1 : -1) + content.tour.length) %
                      content.tour.length;
                    setActive(next);
                    document.getElementById(`stage-${next}`)?.focus();
                  }
                }}
              >
                {stage.label}
                <i className="bar" />
              </button>
            ))}
          </div>
          <button
            className="ctrl"
            type="button"
            aria-label={paused ? "Resume the automatic tour" : "Pause the automatic tour"}
            title={paused ? "Resume" : "Pause"}
            onClick={onToggle}
          >
            {paused ? "▶" : "❚❚"}
          </button>
        </div>
        <div className="win" id="win">
          <aside className="side" aria-hidden="true">
            <div className="dots">
              <i />
              <i />
              <i />
            </div>
            <div className="it on">
              Overview <span>3</span>
            </div>
            <div className="it">
              Inventory <span>18</span>
            </div>
            <div className="it">
              Operations <span>42</span>
            </div>
            <div className="it">
              Conflicts <span>2</span>
            </div>
            <h4>Connected peers</h4>
            <div className="it f" style={{ "--c": "var(--ok)" } as CSSProperties}>
              node-a
            </div>
            <div className="it f" style={{ "--c": "#fbbf24" } as CSSProperties}>
              node-b
            </div>
            <div className="it f" style={{ "--c": "#a78bfa" } as CSSProperties}>
              node-c
            </div>
            <h4>Sync mode</h4>
            <div className="it">Offline-first</div>
          </aside>
          <div
            className="main"
            id="tour-panel"
            role="tabpanel"
            aria-labelledby={`stage-${active}`}
            aria-live="off"
          >
            <TourSlide active={active} />
          </div>
        </div>
      </header>
    </>
  );
}
