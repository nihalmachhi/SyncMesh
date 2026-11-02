import fixture from "./__fixtures__/merge.json";

export type SimOperation = {
  operation_id: string;
  origin_node_id: string;
  origin_seq: number;
  op_type: "create" | "set_field" | "adjust_quantity" | "delete";
  payload: { fields?: Record<string, unknown>; quantity?: number; delta?: number };
  hlc: { physical_ms: number; logical: number };
};

export type SimState = {
  fields: Record<string, unknown>;
  registers: Record<string, { value: unknown; key: [number, number, string, string] }>;
  counters: Record<string, { positive: number; negative: number }>;
  deleted: boolean;
};

export const emptyState = (): SimState => ({
  fields: {},
  registers: {},
  counters: {},
  deleted: false,
});

export function compareKey(a: SimState["registers"][string]["key"], b: typeof a): number {
  for (let i = 0; i < a.length; i += 1) {
    if (a[i]! < b[i]!) return -1;
    if (a[i]! > b[i]!) return 1;
  }
  return 0;
}

export function applyOperations(operations: SimOperation[]): SimState {
  const state = emptyState();
  for (const op of operations) {
    if (op.op_type === "create" || op.op_type === "adjust_quantity") {
      const delta =
        op.op_type === "create" ? (op.payload.quantity ?? 0) : (op.payload.delta ?? 0);
      const counter = (state.counters[op.origin_node_id] ??= { positive: 0, negative: 0 });
      if (delta >= 0) counter.positive += delta;
      else counter.negative += Math.abs(delta);
    }
    if (op.op_type === "delete") state.deleted = true;
    if (op.op_type === "create" || op.op_type === "set_field") {
      const key: [number, number, string, string] = [
        op.hlc.physical_ms,
        op.hlc.logical,
        op.origin_node_id,
        op.operation_id,
      ];
      for (const [field, value] of Object.entries(op.payload.fields ?? {})) {
        const current = state.registers[field];
        if (!current || compareKey(key, current.key) > 0) {
          state.registers[field] = { value, key };
          state.fields[field] = value;
        }
      }
    }
  }
  return state;
}

export function quantityOf(state: SimState): number {
  return Object.values(state.counters).reduce(
    (total, part) => total + part.positive - part.negative,
    0,
  );
}

export class Mulberry32 {
  private state: number;
  constructor(seed: number) {
    this.state = seed >>> 0;
  }
  random(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let value = this.state;
    value = Math.imul(value ^ (value >>> 15), value | 1) >>> 0;
    const mixed = (value + Math.imul(value ^ (value >>> 7), value | 61)) >>> 0;
    value = (value ^ mixed) >>> 0;
    value = (value ^ (value >>> 14)) >>> 0;
    return value / 4294967296;
  }
  integer(max: number): number {
    return Math.floor(this.random() * max);
  }
}

export function fixtureParity(): boolean {
  const result = applyOperations(fixture.operations as SimOperation[]);
  const expected = fixture.expected;
  const expectedRegisters = expected.field_registers as Record<string, { value: unknown }>;
  const rng = new Mulberry32(42);
  const randomMatches = fixture.seeded_random.mulberry32_first_8.every(
    (n) => Math.abs(n - rng.random()) < 1e-12,
  );
  return (
    JSON.stringify(result.fields) === JSON.stringify(expected.fields) &&
    quantityOf(result) === expected.quantity &&
    Object.keys(expectedRegisters).every(
      (key) => result.fields[key] === expectedRegisters[key]!.value,
    ) &&
    randomMatches
  );
}

export function digest(value: unknown): string {
  const input = JSON.stringify(value);
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1)
    hash = Math.imul(hash ^ input.charCodeAt(i), 16777619);
  return (hash >>> 0).toString(16).padStart(8, "0");
}

export function shuffle<T>(items: T[], rng: Mulberry32): T[] {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = rng.integer(i + 1);
    [result[i]!, result[j]!] = [result[j]!, result[i]!];
  }
  return result;
}
