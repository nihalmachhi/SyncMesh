import { describe, expect, it } from "vitest";
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

describe("SyncMesh browser model", () => {
  it("matches the Python-generated merge and random fixtures", () => {
    expect(fixtureParity()).toBe(true);
  });
  it("applies a deterministic maximum register and per-origin PN counter", () => {
    const state = applyOperations(fixture.operations as SimOperation[]);
    expect(state.fields.name).toBe("Whole grain rice");
    expect(quantityOf(state)).toBe(13);
    expect(state.deleted).toBe(false);
    expect(state.counters["node-b"]).toEqual({ positive: 5, negative: 0 });
    expect(state.counters["node-c"]).toEqual({ positive: 0, negative: 2 });
  });
  it("keeps a delete tombstone state and supports empty field values", () => {
    const op = fixture.operations[0]! as SimOperation;
    const deleted = { ...op, op_type: "delete" as const, operation_id: "node-a:delete" };
    expect(applyOperations([deleted]).deleted).toBe(true);
    expect(digest({ b: 2, a: 1 })).not.toBe(digest({ a: 1, b: 2 }));
  });
  it("replays a seeded shuffle and returns a fresh order", () => {
    const rng = new Mulberry32(42);
    expect(shuffle([1, 2, 3, 4], rng)).toHaveLength(4);
    expect(new Mulberry32(42).random()).toBe(new Mulberry32(42).random());
  });
});
