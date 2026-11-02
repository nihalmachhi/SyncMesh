import type { CSSProperties } from "react";
import { content } from "../data/content";
import report from "../data/results.generated.json";

const icons: Record<string, string> = {
  edit: "M4 17.5V20h2.5L19.8 6.7l-2.5-2.5L4 17.5zM15.9 5.6l2.5 2.5",
  arrows: "M4 8h15m-4-4 4 4-4 4M20 16H5m4 4-4-4 4-4",
  merge: "M6 4v4c0 2 2 4 6 4s6 2 6 4v4M6 20v-4c0-2 2-4 6-4m0 0V4m-4 4 4-4 4 4",
  box: "M4 7l8-4 8 4v10l-8 4-8-4V7zm0 0 8 4 8-4m-8 4v10",
  clock: "M12 3a9 9 0 1 0 9 9m-9-9v9l6 3m0-12v3m3 3h-3",
  hash: "M5 9h14M4 15h14M10 4 8 20m8-16-2 16",
  graph: "M4 18V6m0 12h16M7 15l4-5 3 3 5-7",
  spark:
    "M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3zm6 12 .8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8L18 15z",
  scan: "M4 8V4h4m8 0h4v4m0 8v4h-4m-8 0H4v-4M7 12h10M9 9h.01M15 15h.01",
  lock: "M6 10h12v10H6zM9 10V7a3 3 0 0 1 6 0v3m-3 4v2",
  out: "M12 4v12m-5-5 5 5 5-5M5 20h14",
  check: "M5 12.5l4.5 4.5L19 7.5",
  bulb: "M9 18h6m-5 3h4m-2-19a7 7 0 0 0-4 12.7c.6.4 1 1.1 1 1.8h6c0-.7.4-1.4 1-1.8A7 7 0 0 0 12 2z",
  question:
    "M9.1 9a3 3 0 1 1 5.7 1.3c-.8 1.2-2.8 1.6-2.8 3.7m0 3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  alert: "M12 3 2.8 20h18.4L12 3zm0 6v5m0 3h.01",
  layers: "m12 3 9 5-9 5-9-5 9-5zm-9 9 9 5 9-5M3 16l9 5 9-5",
};

function Glyph({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={icons[name] ?? icons.check} />
    </svg>
  );
}
function InlineIcon({ name, color }: { name: string; color: string }) {
  return (
    <i className="ico" style={{ "--c": color } as CSSProperties}>
      <Glyph name={name} />
    </i>
  );
}
function CardIcon({ name, color }: { name: string; color: string }) {
  return (
    <div className="ib" style={{ "--c": color } as CSSProperties}>
      <Glyph name={name} />
    </div>
  );
}

export function Pipeline() {
  return (
    <section className="sec" id="how">
      <h2>
        Three steps.{" "}
        <span className="m">
          One <InlineIcon name="check" color="#22c55e" /> shared state.
        </span>
      </h2>
      <p className="lead2">
        Local edits become operations, peers exchange what they missed, and deterministic rules
        bring each replica back together.
      </p>
      <div className="steps">
        {content.pipeline.map((step) => (
          <article className="step" key={step.title}>
            <CardIcon
              name={step.icon}
              color={
                ["#8b5cf6", "#06b6d4", "#f59e0b"][content.pipeline.indexOf(step)] ?? "#8b5cf6"
              }
            />
            <h3>{step.title}</h3>
            <p>{step.body}</p>
            <div className="mini">
              {step.mini.split("\n").map((line) => (
                <div key={line}>{line}</div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

type Report = {
  convergence: { converged: number; schedules_run: number };
  gossip: { converged: boolean }[];
  duplicate_detection: { precision: number; recall: number; evaluation_pairs: number };
};
const metrics = report as Report;
function ResultCard({
  title,
  description,
  rows,
}: {
  title: string;
  description: string;
  rows: [string, number, string, string][];
}) {
  return (
    <article className="rc">
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="tb">
        {rows.map(([label, width, color, value]) => (
          <div className="mr" key={label}>
            <span>{label}</span>
            <div className="track">
              <div
                className="grow"
                style={
                  {
                    "--w": `${width}%`,
                    "--c": color,
                    width: `${width}%`,
                    animation: "none",
                  } as CSSProperties
                }
              />
            </div>
            <b>{value}</b>
          </div>
        ))}
      </div>
    </article>
  );
}

export function Results() {
  const convergence = metrics.convergence;
  const gossipCount = metrics.gossip.filter((entry) => entry.converged).length;
  const duplicates = metrics.duplicate_detection;
  return (
    <section className="sec" id="results">
      <h2>
        Seeded schedules.{" "}
        <span className="m">
          Measured, <InlineIcon name="graph" color="#06b6d4" /> not guessed.
        </span>
      </h2>
      <p className="lead2">
        Generated experiment reports run from the Python implementation and are checked into the
        repository.
      </p>
      <div className="rg">
        <ResultCard
          title="Operation convergence"
          description="Seeded reorder and duplicate-delivery schedules."
          rows={[
            [
              "Converged",
              (100 * convergence.converged) / convergence.schedules_run,
              "var(--ok)",
              `${convergence.converged}/${convergence.schedules_run}`,
            ],
            ["Fixed seed", 74, "#8b5cf6", "2026"],
          ]}
        />
        <ResultCard
          title="Peer gossip"
          description="Generated connected topologies with deterministic propagation."
          rows={[
            [
              "Converged",
              (100 * gossipCount) / metrics.gossip.length,
              "var(--ok)",
              `${gossipCount}/${metrics.gossip.length}`,
            ],
            ["Schedules", 100, "#06b6d4", `${metrics.gossip.length} graphs`],
          ]}
        />
        <ResultCard
          title="Duplicate hints"
          description="Tiny synthetic held-out set; it does not estimate real catalog quality."
          rows={[
            [
              "Precision",
              100 * duplicates.precision,
              "#f59e0b",
              `${(duplicates.precision * 100).toFixed(0)}%`,
            ],
            [
              "Recall",
              100 * duplicates.recall,
              "#f59e0b",
              `${(duplicates.recall * 100).toFixed(0)}%`,
            ],
            ["Examples", 60, "#8b5cf6", `${duplicates.evaluation_pairs} pairs`],
          ]}
        />
      </div>
      <p className="note">{content.honestReading}</p>
    </section>
  );
}

export function Features() {
  return (
    <section className="sec" id="features">
      <h2>
        A small system.{" "}
        <span className="m">
          Built to be <InlineIcon name="layers" color="#8b5cf6" /> inspected.
        </span>
      </h2>
      <p className="lead2">
        The replica protocol, synchronization loop, graphs and optional local helpers are kept
        visible as separate parts.
      </p>
      <div className="bento">
        {content.features.map((feature, index) => {
          const size = feature.wide ? "f" : index < 2 || index === 6 || index === 7 ? "w" : "";
          const colors = [
            "#8b5cf6",
            "#06b6d4",
            "#f59e0b",
            "#22c55e",
            "#ec4899",
            "#f97316",
            "#22c55e",
            "#a78bfa",
            "#ef4444",
            "#62626b",
          ];
          return (
            <article className={`bc ${size}`} key={feature.title}>
              <CardIcon name={feature.icon} color={colors[index] ?? "#8b5cf6"} />
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
              <div className="tags">
                {(index === 0
                  ? ["per-field registers", "HLC order", "conflict review"]
                  : index === 1
                    ? ["per-origin components", "retry safe", "oversold flag"]
                    : ["SyncMesh", "local-first"]
                ).map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function QuickStart() {
  return (
    <section className="sec" id="start">
      <h2>
        Three commands.{" "}
        <span className="m">
          A <InlineIcon name="arrows" color="#22c55e" /> local cluster.
        </span>
      </h2>
      <p className="lead2">
        Python 3.12+, uv and Docker Compose. Set distinct admin and peer secrets before
        production mode.
      </p>
      <div className="steps qs">
        {content.quickStart.map((step) => (
          <article className="step" key={step.title}>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
            <div className="code">
              <span className="c"># PowerShell</span>
              <br />
              {step.powershell.split("\n").map((line) => (
                <div key={line}>{line}</div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function Scope() {
  const groups: [string, string, string, string[]][] = [
    ["In scope", "#22c55e", "check", content.scope.in],
    ["Out of scope", "#ef4444", "out", content.scope.out],
  ];
  return (
    <section className="sec" id="scope">
      <h2>
        Built to <InlineIcon name="bulb" color="#f97316" /> <span className="m">teach.</span>
      </h2>
      <p className="lead2">
        SyncMesh is an educational replication lab. It is not a production database or formal
        correctness proof.
      </p>
      <div className="sc">
        {groups.map(([title, color, icon, items]) => (
          <article className="scc" key={title}>
            <CardIcon name={icon} color={color} />
            <h3>{title}</h3>
            <ul>
              {items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

export function Faq() {
  return (
    <section className="sec" id="faq">
      <h2>
        Any <InlineIcon name="question" color="#ec4899" /> <span className="m">questions?</span>
      </h2>
      <div className="faq">
        {content.faq.map((item) => (
          <details key={item.q}>
            <summary>{item.q}</summary>
            <p>{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
