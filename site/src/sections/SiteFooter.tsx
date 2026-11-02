import type { CSSProperties } from "react";
import { content } from "../data/content";

const iconUrl = `${import.meta.env.BASE_URL}readme-icon.png`;

function Brand() {
  return (
    <a className="brand" href="#top">
      <img className="brand-icon" src={iconUrl} alt="" width="22" height="22" />
      SyncMesh
    </a>
  );
}

function Architecture() {
  const nodes = [
    { x: 0, delay: "0.0s", lines: ["Local", "inventory edit"] },
    { x: 142, delay: "0.9s", lines: ["SQLite", "operation log"] },
    { x: 284, delay: "1.8s", lines: ["Peer sync", "vectors + pages"] },
    { x: 426, delay: "2.7s", lines: ["Causal", "dependencies"] },
    { x: 568, delay: "3.6s", lines: ["Field registers", "PN-counter"] },
    { x: 710, delay: "4.5s", lines: ["Conflict review", "tombstones"] },
    { x: 852, delay: "5.4s", lines: ["Converged", "replica views"], last: true },
  ];
  return (
    <svg
      className="flow arch"
      viewBox="0 0 964 90"
      role="img"
      aria-label="SyncMesh data flow from local inventory edits through operation logs, peer synchronization, causal merge rules, and converged replica views"
    >
      {[112, 254, 396, 538, 680, 822].map((x) => (
        <path className="fl" d={`M${x} 45H${x + 30}`} key={x} />
      ))}
      {nodes.map((node) => {
        const y = 45 - ((node.lines.length - 1) * 13) / 2 + 3.5;
        return (
          <g
            className={`gn st${node.last ? " last" : ""}`}
            style={{ "--d": node.delay } as CSSProperties}
            key={node.x}
          >
            <rect x={node.x} y="12" width="112" height="66" rx="9" />
            <text textAnchor="middle">
              {node.lines.map((line, index) => (
                <tspan x={node.x + 56} y={y + index * 13} key={line}>
                  {line}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
      <circle r="3.2" fill="#f4f4f5">
        <animateMotion dur="6.3s" repeatCount="indefinite" path="M0 45H964" />
      </circle>
    </svg>
  );
}

export function ClosingCta() {
  return (
    <section className="cta2 rv-wrap" aria-label="Get started">
      <div className="rv archw" style={{ "--r": "0" } as CSSProperties}>
        <Architecture />
      </div>
      <h2 className="rv" style={{ "--r": "1" } as CSSProperties}>
        Run it.
        <br />
        <span className="m">
          Watch peers <span className="pulse">converge.</span>
        </span>
      </h2>
      <div className="btns rv" style={{ "--r": "2" } as CSSProperties}>
        <a className="pill w" href={content.hero.github} target="_blank" rel="noreferrer">
          View on GitHub
        </a>
        <a className="pill" href="#try">
          Back to the replication lab
        </a>
      </div>
    </section>
  );
}

export function SiteFooter() {
  const columns: { title: string; links: [string, string][] }[] = [
    {
      title: "Product",
      links: [
        ["Overview", "#top"],
        ["Pipeline", "#how"],
        ["Simulator", "#try"],
        ["Results", "#results"],
      ],
    },
    {
      title: "Explore",
      links: [
        ["Features", "#features"],
        ["Quick start", "#start"],
        ["FAQ", "#faq"],
        ["Scope", "#scope"],
      ],
    },
    {
      title: "Source",
      links: [
        ["GitHub", content.hero.github],
        ["Docs", `${content.hero.github}/tree/main/docs`],
        ["Source code", `${content.hero.github}/tree/main/src`],
        ["Issues", `${content.hero.github}/issues`],
      ],
    },
  ];
  return (
    <footer className="wrap">
      <div className="foot">
        <div className="fcols">
          <div>
            <Brand />
            <p className="tg">{content.footer}</p>
          </div>
          {columns.map((column) => (
            <div key={column.title}>
              <h5>{column.title}</h5>
              <ul>
                {column.links.map(([label, href]) => (
                  <li key={label}>
                    <a
                      href={href}
                      target={href.startsWith("https:") ? "_blank" : undefined}
                      rel={href.startsWith("https:") ? "noreferrer" : undefined}
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="fbot">
          <span>Educational simulation; not a production database.</span>
          <span>Python · SQLite · React · TypeScript</span>
        </div>
        <div className="mark" aria-hidden="true">
          SyncMesh
        </div>
      </div>
    </footer>
  );
}
