import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowDownUp,
  Box,
  GitBranch,
  LayoutDashboard,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldAlert,
  Wifi,
  WifiOff,
} from "lucide-react";

type Item = { id: string; name: string; category: string; price: number; stock: number };
type Conflict = {
  conflict_id: string;
  entity_id: string;
  field: string;
  status: "OPEN" | "RESOLVED";
  resolution: string | null;
};
type GraphNode = { id: string; origin: string; sequence: number; type: string };
type GraphEdge = { from: string; to: string };
type CausalGraph = { nodes: GraphNode[]; edges: GraphEdge[]; frontier: string[]; antichain_width: number; longest_chain: number };
type PeerTopology = {
  nodes: { id: string; online: boolean }[];
  edges: { from: string; to: string; online: boolean }[];
  components: string[][];
};
type NodeState = {
  id: string;
  url: string;
  online: boolean;
  syncing: boolean;
  items: Item[];
  operations: number;
  pending: number;
  conflicts: number;
  vector: Record<string, number>;
  error?: string;
};

const nodes = [
  { id: "node-a", url: "http://localhost:8001", label: "North shop" },
  { id: "node-b", url: "http://localhost:8002", label: "Central warehouse" },
  { id: "node-c", url: "http://localhost:8003", label: "South shop" },
];
const emptyGraph: CausalGraph = { nodes: [], edges: [], frontier: [], antichain_width: 0, longest_chain: 0 };
const emptyTopology: PeerTopology = { nodes: [], edges: [], components: [] };

async function request<T>(url: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(String(body.detail ?? response.statusText));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export default function App() {
  const [selected, setSelected] = useState(0);
  const [token, setToken] = useState("");
  const [data, setData] = useState<NodeState[]>([]);
  const [causal, setCausal] = useState<CausalGraph>(emptyGraph);
  const [topology, setTopology] = useState<PeerTopology>(emptyTopology);
  const [conflictRows, setConflictRows] = useState<Conflict[]>([]);
  const [message, setMessage] = useState("");
  const current = data[selected];

  const refresh = useCallback(async () => {
    const snapshots = await Promise.all(
      nodes.map(async (node): Promise<NodeState> => {
        try {
          const [health, itemResponse, stats] = await Promise.all([
            request<{ node_id: string }>(`${node.url}/health`, token),
            request<{ items: Item[] }>(`${node.url}/items`, token),
            request<Record<string, unknown>>(`${node.url}/stats`, token),
          ]);
          return {
            id: health.node_id,
            url: node.url,
            online: true,
            syncing: Boolean(stats.online),
            items: itemResponse.items,
            operations: Number(stats.operations ?? 0),
            pending: Number(stats.pending ?? 0),
            conflicts: Number(stats.conflicts ?? 0),
            vector: (stats.vector ?? {}) as Record<string, number>,
          };
        } catch (error) {
          return {
            id: node.id,
            url: node.url,
            online: false,
            syncing: false,
            items: [],
            operations: 0,
            pending: 0,
            conflicts: 0,
            vector: {},
            error: error instanceof Error ? error.message : "Node unavailable",
          };
        }
      }),
    );
    setData(snapshots);
    const active = snapshots[selected];
    if (!active?.online) return;
    const [conflictsResult, graphResult, topologyResult] = await Promise.allSettled([
      request<{ conflicts: Conflict[] }>(`${active.url}/conflicts`, token),
      request<CausalGraph>(`${active.url}/debug/causal-graph`, token),
      request<PeerTopology>(`${active.url}/debug/topology`, token),
    ]);
    if (conflictsResult.status === "fulfilled") setConflictRows(conflictsResult.value.conflicts);
    if (graphResult.status === "fulfilled") setCausal(graphResult.value);
    if (topologyResult.status === "fulfilled") setTopology(topologyResult.value);
  }, [selected, token]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const allOnline = useMemo(() => data.filter((node) => node.online).length, [data]);

  async function runAction(action: () => Promise<void>, success: string) {
    setMessage("");
    try {
      await action();
      setMessage(success);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    }
  }

  async function toggleSync(node: NodeState) {
    await runAction(async () => {
      await request(`${node.url}/admin/connectivity`, token, {
        method: "POST",
        body: JSON.stringify({ online: !node.syncing }),
      });
    }, `${node.id} sync ${node.syncing ? "paused" : "resumed"}.`);
  }

  async function syncNow() {
    await runAction(async () => {
      await Promise.all(
        data.filter((node) => node.online).map((node) =>
          request(`${node.url}/admin/sync`, token, { method: "POST" }),
        ),
      );
    }, "Peer exchange completed.");
  }

  async function addItem() {
    if (!current?.online) return;
    const name = window.prompt("Item name");
    if (!name?.trim()) return;
    await runAction(async () => {
      await request(`${current.url}/items`, token, {
        method: "POST",
        body: JSON.stringify({ name, category: "General", price: 0, quantity: 8 }),
      });
    }, `Created ${name.trim()} on ${current.id}.`);
  }

  async function replayPartition() {
    const item = current?.items[0];
    if (!item || data.filter((node) => node.online).length !== 3) {
      setMessage("Connect all three nodes and create an item before replaying a partition.");
      return;
    }
    await runAction(async () => {
      await Promise.all(data.map((node) => request(node.url + "/admin/connectivity", token, {
        method: "POST",
        body: JSON.stringify({ online: false }),
      })));
      await Promise.all(data.map((node, index) => request(`${node.url}/items/${item.id}/quantity`, token, {
        method: "POST",
        body: JSON.stringify({ delta: index + 1 }),
      })));
      await Promise.all(data.map((node) => request(node.url + "/admin/connectivity", token, {
        method: "POST",
        body: JSON.stringify({ online: true }),
      })));
      await Promise.all(data.map((node) => request(`${node.url}/admin/sync`, token, { method: "POST" })));
    }, "Partition healed. Check the stock on all three replicas.");
  }

  async function resolveConflict(conflict: Conflict, winner: "winner" | "loser") {
    const selectedValues = conflict.resolution ? JSON.parse(conflict.resolution) as {
      winner_value: Record<string, unknown>;
      loser_value: Record<string, unknown>;
    } : null;
    if (!selectedValues || !current) return;
    const valueKey = winner === "winner" ? "winner_value" : "loser_value";
    const fields = conflict.field.split(",").reduce<Record<string, unknown>>((result, field) => {
      const fieldName = field.trim();
      if (fieldName in selectedValues[valueKey]) result[fieldName] = selectedValues[valueKey][fieldName];
      return result;
    }, {});
    await runAction(async () => {
      await request(`${current.url}/conflicts/${conflict.conflict_id}/resolve`, token, {
        method: "POST",
        body: JSON.stringify({ fields }),
      });
    }, "Conflict resolution recorded as a new operation.");
  }

  return (
    <div className="layout">
      <aside>
        <div className="brand"><span className="brand-mark"><GitBranch size={18} /></span>SyncMesh</div>
        <small className="label">WORKSPACE</small>
        <div className="workspace"><i /> Retail network <span>{allOnline}/3 online</span></div>
        <small className="label">MONITOR</small>
        <a className="nav active" href="#overview"><LayoutDashboard size={15} /> Overview</a>
        <a className="nav" href="#replication"><ArrowDownUp size={15} /> Replication</a>
        <a className="nav" href="#conflicts"><ShieldAlert size={15} /> Conflicts</a>
        <a className="nav" href="#graphs"><Activity size={15} /> Graphs</a>
        <div className="side-foot">Offline first · Local lab</div>
      </aside>
      <main>
        <header><span>Workspace</span><b>/</b><b>Network overview</b>
          <label className="auth"><LockKeyhole size={14} /><input aria-label="Admin bearer token" type="password" placeholder="Admin token" value={token} onChange={(event) => setToken(event.target.value)} /></label>
          <div className="header-right"><span>{message}</span><button onClick={() => void refresh()}><RefreshCw size={13} /> Refresh</button></div>
        </header>
        <div className="content" id="overview">
          <div className="title"><div><small className="label">FIELD OPERATIONS</small><h1>Network overview</h1><p>Inventory and replication state across independent nodes.</p></div>
            <div className="actions"><button className="secondary" onClick={() => void syncNow()}><ArrowDownUp size={14} /> Sync now</button><button className="primary" onClick={() => void addItem()}><Plus size={14} /> New item</button></div>
          </div>
          <div className="metrics">
            <Metric icon={<GitBranch size={17} />} label="Connected nodes" value={`${allOnline} / 3`} />
            <Metric icon={<Box size={17} />} label="Inventory items" value={String(current?.items.length ?? "—")} />
            <Metric icon={<Activity size={17} />} label="Operations" value={String(current?.operations ?? "—")} />
            <Metric icon={<ShieldAlert size={17} />} label="Open conflicts" value={String(current?.conflicts ?? "—")} />
          </div>
          <section className="panel" id="replication">
            <div className="panel-head"><div><h2>Replica topology</h2><p>Pause outbound sync to create an offline window, then reconnect peers.</p></div><button className="secondary" onClick={() => void replayPartition()}><RefreshCw size={13} /> Replay partition lab</button></div>
            <div className="nodes">{nodes.map((node, index) => {
              const state = data[index];
              return <button className={`node ${index === selected ? "selected" : ""}`} key={node.id} onClick={() => setSelected(index)}>
                <div className="node-head"><span className={state?.online ? "up" : "down"}>{state?.online ? <Wifi size={15} /> : <WifiOff size={15} />}</span><small className={state?.online ? "up" : "down"}>{state?.online ? (state.syncing ? "SYNCING" : "PAUSED") : "OFFLINE"}</small></div>
                <b>{node.id.toUpperCase()}</b><p>{node.label}</p><div className="node-foot">{state?.items.length ?? 0} items <span>{state?.operations ?? 0} ops</span></div>
                {state?.online && <span className="node-control" onClick={(event) => { event.stopPropagation(); void toggleSync(state); }}>{state.syncing ? "Pause sync" : "Resume sync"}</span>}
              </button>;
            })}</div>
            <div className="vector">Version vector <code>{JSON.stringify(current?.vector ?? {})}</code></div>
          </section>
          <div className="bottom">
            <section className="panel"><div className="panel-head"><div><h2>Inventory · {current?.id ?? "connecting"}</h2><p>Stock allows negative values and marks oversold items.</p></div></div>
              <div className="table-scroll"><table><thead><tr><th>ITEM</th><th>CATEGORY</th><th>PRICE</th><th>STOCK</th></tr></thead><tbody>{current?.items.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.category}</td><td>${Number(item.price).toFixed(2)}</td><td>{item.stock} units</td></tr>)}{!current?.items.length && <tr><td colSpan={4} className="empty">No inventory items yet.</td></tr>}</tbody></table></div>
            </section>
            <section className="panel" id="conflicts"><div className="panel-head"><div><h2>Conflict review</h2><p>Concurrent values stay visible until reviewed.</p></div></div>
              {!conflictRows.filter((conflict) => conflict.status === "OPEN").length && <p className="empty">No open field conflicts.</p>}
              {conflictRows.filter((conflict) => conflict.status === "OPEN").map((conflict) => {
                const values = conflict.resolution ? JSON.parse(conflict.resolution) as { winner_value: Record<string, unknown>; loser_value: Record<string, unknown> } : null;
                return <div className="conflict" key={conflict.conflict_id}><div><b>{conflict.field}</b><small>{conflict.entity_id}</small></div><div className="values"><span>Winner: {JSON.stringify(values?.winner_value ?? {})}</span><span>Other: {JSON.stringify(values?.loser_value ?? {})}</span></div><div className="conflict-actions"><button onClick={() => void resolveConflict(conflict, "winner")}>Keep winner</button><button onClick={() => void resolveConflict(conflict, "loser")}>Keep other</button></div></div>;
              })}
            </section>
          </div>
          <div className="bottom graph-panels" id="graphs">
            <section className="panel"><div className="panel-head"><div><h2>Causal history</h2><p>{causal.longest_chain} longest chain · {causal.antichain_width} concurrent frontier width</p></div></div><CausalSvg graph={causal} /></section>
            <section className="panel"><div className="panel-head"><div><h2>Peer graph</h2><p>{topology.components.length} connected component{topology.components.length === 1 ? "" : "s"}</p></div></div><TopologySvg graph={topology} /></section>
          </div>
          <footer>SyncMesh is an educational replication lab. Synthetic schedules do not prove production correctness.<span>SQLite · FastAPI · React</span></footer>
        </div>
      </main>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="metric">{icon}<small>{label}</small><b>{value}</b></div>;
}

function CausalSvg({ graph }: { graph: CausalGraph }) {
  if (!graph.nodes.length) return <p className="empty">Write operations to see their causal history.</p>;
  const positions = new Map(graph.nodes.map((node, index) => [node.id, { x: 36 + index % 4 * 82, y: 40 + Math.floor(index / 4) * 72 }]));
  return <div className="graph-scroll"><svg className="graph" viewBox={`0 0 ${Math.max(360, Math.ceil(graph.nodes.length / 4) * 72)} 190`} role="img" aria-label="Causal operation graph">
    {graph.edges.map((edge) => { const from = positions.get(edge.from); const to = positions.get(edge.to); return from && to ? <line key={`${edge.from}-${edge.to}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} /> : null; })}
    {graph.nodes.map((node) => { const point = positions.get(node.id); return point ? <g key={node.id} transform={`translate(${point.x} ${point.y})`}><circle r="17" /><text textAnchor="middle" y="4">{node.origin.slice(-1)}:{node.sequence}</text></g> : null; })}
  </svg></div>;
}

function TopologySvg({ graph }: { graph: PeerTopology }) {
  if (!graph.nodes.length) return <p className="empty">Peer configuration is empty.</p>;
  const positions = graph.nodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / graph.nodes.length - Math.PI / 2;
    return { ...node, x: 160 + 112 * Math.cos(angle), y: 108 + 74 * Math.sin(angle) };
  });
  const lookup = new Map(positions.map((node) => [node.id, node]));
  return <svg className="graph topology" viewBox="0 0 320 220" role="img" aria-label="Peer network topology">
    {graph.edges.map((edge) => { const left = lookup.get(edge.from); const right = lookup.get(edge.to); return left && right ? <line className={edge.online ? "edge-on" : "edge-off"} key={`${edge.from}-${edge.to}`} x1={left.x} y1={left.y} x2={right.x} y2={right.y} /> : null; })}
    {positions.map((node) => <g key={node.id} transform={`translate(${node.x} ${node.y})`}><circle className={node.online ? "node-on" : "node-off"} r="25" /><text textAnchor="middle" y="4">{node.id}</text></g>)}
  </svg>;
}
