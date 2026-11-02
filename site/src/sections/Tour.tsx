import type { CSSProperties } from "react";
import { content } from "../data/content";

export function TourSlide({ active }: { active: number }) {
  const panel = content.tour[active] ?? content.tour[0]!;
  return (
    <div className="body" key={active}>
      <div className="col cv">
        <h3>{panel.title}</h3>
        <div className="sub">{panel.subtitle}</div>
        <p className="tx rise">A closer look at the messages and state behind this step.</p>
        {panel.rows.map((row, index) => (
          <div
            className="sp-r rise"
            style={{ "--i": index + 1 } as CSSProperties}
            key={row.key}
          >
            <span className={`k ${row.status ?? ""}`}>{row.key}</span>
            {row.value}
          </div>
        ))}
      </div>
      <div className="col cv">
        <h4>{panel.asideTitle}</h4>
        <ul className="lst">
          {panel.asideRows.map((row, index) => (
            <li className="rise" style={{ "--i": index + 1 } as CSSProperties} key={row}>
              {row}
            </li>
          ))}
        </ul>
        <p className="tx" style={{ color: "var(--mu)", fontSize: ".84rem" }}>
          A deterministic demo of SyncMesh behavior. No service requests are made.
        </p>
      </div>
    </div>
  );
}
