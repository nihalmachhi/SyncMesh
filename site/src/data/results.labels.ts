export const resultCopy = {
  convergence: {
    title: "Convergence",
    caption: "Seeded operation schedules",
    unit: "schedules",
  },
  bandwidth: {
    title: "Bandwidth selection",
    caption: "Estimated JSON bytes under a page budget",
    unit: "bytes",
  },
  duplicates: {
    title: "Duplicate hints",
    caption: "Held-out synthetic catalog pairs",
    unit: "precision / recall",
  },
  honest:
    "Simulated networks and generated data. These numbers show the algorithms work in the tested model, not production performance or correctness for every execution.",
} as const;
