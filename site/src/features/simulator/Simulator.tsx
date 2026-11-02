import { useState, type CSSProperties } from "react";
import fixture from "./__fixtures__/merge.json";
import {
  applyOperations,
  digest,
  fixtureParity,
  Mulberry32,
  quantityOf,
  shuffle,
  type SimOperation,
} from "./engine";

export default function Simulator() {
  const operations = fixture.operations as SimOperation[];
  const [seed, setSeed] = useState(42);
  const [run, setRun] = useState(0);
  const [partitioned, setPartitioned] = useState(true);
  const schedule = shuffle(operations, new Mulberry32(seed));
  const merged = applyOperations(schedule);
  const initial = operations.filter((operation) => operation.op_type === "create");
  const replicas = ["node-a", "node-b", "node-c"].map((peer) => {
    const local = operations.filter(
      (operation) => operation.origin_node_id === peer && operation.op_type !== "create",
    );
    return { peer, state: partitioned ? applyOperations([...initial, ...local]) : merged };
  });
  const replay = () => {
    setSeed((value) => value + 1);
    setRun((value) => value + 1);
  };

  return (
    <section className="sec" id="try">
      <h2>
        Partition the network.{" "}
        <span className="m">
          Then watch it{" "}
          <i className="ico" style={{ "--c": "#22c55e" } as CSSProperties}>
            <svg viewBox="0 0 24 24">
              <path d="M5 12.5l4.5 4.5L19 7.5" />
            </svg>
          </i>{" "}
          catch up.
        </span>
      </h2>
      <p className="lead2">
        Keep local writes separate, reconnect the peers, then inspect how identical merge rules
        produce the same inventory state.
      </p>
      <div className="sim">
        <div className="shead">
          <span>browser simulation · Python-generated fixture</span>
          <span className={`chip ${partitioned ? "no" : "ok"}`} aria-live="polite">
            {partitioned
              ? "network partitioned · local writes enabled"
              : "peers synchronized · replicas agree"}
          </span>
        </div>
        <div className="stats">
          <div className="stat">
            <b>{replicas.length}</b>
            <span>independent replicas</span>
          </div>
          <div className="stat">
            <b>{operations.length}</b>
            <span>operations in fixture</span>
          </div>
          <div className="stat">
            <b>{seed}</b>
            <span>delivery schedule seed</span>
          </div>
        </div>
        <div className="ctl">
          <button
            className="pill w"
            type="button"
            onClick={() => setPartitioned((value) => !value)}
          >
            {partitioned ? "Reconnect peers" : "Create partition"}
          </button>
          <button className="pill" type="button" onClick={replay}>
            Replay schedule · {run + 1}
          </button>
          <span className="sim-parity">
            {fixtureParity() ? "✓ Python merge parity" : "Fixture mismatch"}
          </span>
        </div>
        <div className="scols replica-layout">
          <div>
            <h3>{partitioned ? "Local replica views" : "Synchronized replica views"}</h3>
            <div className="replicas">
              {replicas.map(({ peer, state }) => (
                <article className="peer-card" key={peer}>
                  <div className="peer-head">
                    <i className={`peer-${peer}`} />
                    <b>{peer}</b>
                    <span>{partitioned ? "OFFLINE" : "SYNCED"}</span>
                  </div>
                  <div className="replica-row">
                    <span>item</span>
                    <strong>{String(state.fields.name ?? "—")}</strong>
                  </div>
                  <div className="replica-row">
                    <span>stock</span>
                    <strong>{quantityOf(state)} units</strong>
                  </div>
                  <div className="replica-hash">state · {digest(state)}</div>
                </article>
              ))}
            </div>
          </div>
          <div>
            <h3>Merge summary</h3>
            <div className="merge-summary">
              <div>
                <span>Network</span>
                <b className={partitioned ? "no" : "ok"}>
                  {partitioned ? "partitioned" : "reconnected"}
                </b>
              </div>
              <div>
                <span>Field winner</span>
                <b>{String(merged.fields.name ?? "—")}</b>
              </div>
              <div>
                <span>Merged stock</span>
                <b>{quantityOf(merged)} units</b>
              </div>
              <div>
                <span>State fingerprint</span>
                <code>{digest(merged)}</code>
              </div>
              <p>
                {partitioned
                  ? "Changes stay on their originating node until peers reconnect."
                  : "All replicas now show the same merged state."}
              </p>
            </div>
          </div>
        </div>
        <p className="sim-limits">
          Local-only UI simulation. The operation order is seeded; this does not inject real
          packet loss, process crashes, or database failures.
        </p>
      </div>
    </section>
  );
}
