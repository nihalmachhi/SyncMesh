export type TourTab = {
  label: string;
  title: string;
  subtitle: string;
  rows: { key: string; value: string; oldValue?: string; status?: "good" | "warn" }[];
  asideTitle: string;
  asideRows: string[];
};

export const content = {
  nav: [
    { label: "How it works", href: "#how" },
    { label: "Partition lab", href: "#try" },
    { label: "Results", href: "#results" },
    { label: "Features", href: "#features" },
    { label: "Quick start", href: "#start" },
    { label: "FAQ", href: "#faq" },
  ],
  hero: {
    eyebrow: "OFFLINE-FIRST REPLICATION LAB",
    title: "Edit offline. Converge everywhere.",
    body: "SyncMesh gives every node its own database, lets each one keep writing while the network is down, and merges the changes with version vectors and deterministic rules that produce the same state on every replica.",
    github: "https://github.com/nihalmachhi/SyncMesh",
  },
  tour: [
    {
      label: "Write",
      title: "A local edit becomes an operation",
      subtitle: "node-a · sequence 18 · SQLite transaction",
      rows: [
        { key: "entity", value: "item · brown rice" },
        { key: "operation", value: "set_field" },
        { key: "sequence", value: "node-a:18" },
        { key: "base vector", value: "{ node-a: 17, node-b: 12 }" },
        { key: "hybrid clock", value: "1800000000421 · 3" },
      ],
      asideTitle: "Committed together",
      asideRows: ["immutable change log", "materialized item view", "local write acknowledged"],
    },
    {
      label: "Exchange",
      title: "Peers compare what they have",
      subtitle: "three independent stores · bounded pages",
      rows: [
        { key: "node-a", value: "{ a:18, b:12, c:9 }" },
        { key: "node-b", value: "{ a:16, b:12, c:9 }", status: "warn" },
        { key: "node-c", value: "{ a:18, b:12, c:8 }", status: "warn" },
        { key: "missing at b", value: "node-a:17–18" },
        { key: "missing at c", value: "node-c:9" },
      ],
      asideTitle: "Compact checks",
      asideRows: ["version vector", "per-origin hash ranges", "max 500 operations per page"],
    },
    {
      label: "Merge",
      title: "Fields and stock use different rules",
      subtitle: "independent fields · additive stock components",
      rows: [
        { key: "name · node-a", value: "Brown rice" },
        { key: "price · node-b", value: "$4.25" },
        { key: "stock +", value: "node-a: +5" },
        { key: "stock −", value: "node-b: −2" },
        { key: "merged stock", value: "13 units", status: "good" },
      ],
      asideTitle: "Stable ordering",
      asideRows: [
        "field registers",
        "HLC + node + operation ID",
        "positive − negative counters",
      ],
    },
    {
      label: "Conflicts",
      title: "The losing value stays reviewable",
      subtitle: "same field · concurrent writers · open review record",
      rows: [
        { key: "field", value: "category" },
        { key: "node-a · winner", value: "Grains", status: "good" },
        { key: "node-c · other value", value: "Pantry", status: "warn" },
        { key: "conflict", value: "same pair ID on both peers" },
        { key: "resolution", value: "new ordinary operation" },
      ],
      asideTitle: "Nothing hidden",
      asideRows: ["both operation IDs", "both field values", "review state: open"],
    },
    {
      label: "Converge",
      title: "Reconnect and compare final state",
      subtitle: "after buffered dependencies arrive",
      rows: [
        { key: "node-a digest", value: "a82f…1c90", status: "good" },
        { key: "node-b digest", value: "a82f…1c90", status: "good" },
        { key: "node-c digest", value: "a82f…1c90", status: "good" },
        { key: "pending operations", value: "0" },
        { key: "replicas agree", value: "in this simulated schedule", status: "good" },
      ],
      asideTitle: "What the test means",
      asideRows: ["fixed code and seed", "modeled message delivery", "not a formal proof"],
    },
  ] satisfies TourTab[],
  pipeline: [
    {
      icon: "edit",
      title: "1. Write locally",
      body: "Every node accepts inventory changes in its own SQLite database. The log entry and the visible item update commit in one transaction.",
      mini: "local edit  →  operation ID\nnode-a:18 · HLC · base vector",
    },
    {
      icon: "arrows",
      title: "2. Exchange missing work",
      body: "Peers compare vectors and per-origin digests, then send bounded operation pages. Incomplete causal histories wait in a buffer.",
      mini: "version vector  +  range hashes\npage ≤ 500 · HMAC signed",
    },
    {
      icon: "merge",
      title: "3. Merge by meaning",
      body: "Each field uses an independently ordered register, while stock uses positive and negative components. Concurrent field values remain available for review.",
      mini: "field register  +  PN-counter\ncausal dependencies before apply",
    },
  ],
  resultsIntro:
    "Seeded schedules, generated graphs, and a small synthetic catalog measure the modeled algorithms.",
  honestReading:
    "Simulated networks and generated data. These numbers show the algorithms work in the tested model, not production performance or correctness for every execution.",
  features: [
    {
      icon: "merge",
      title: "Per-field merge",
      body: "Name and price can change independently without overwriting each other.",
    },
    {
      icon: "box",
      title: "PN-counter stock",
      body: "Each origin keeps positive and negative components for retry-safe additions.",
    },
    {
      icon: "clock",
      title: "Hybrid logical clocks",
      body: "Stable ordering keeps concurrent field writes independent of delivery order.",
    },
    {
      icon: "arrows",
      title: "Causal delivery",
      body: "Missing sequence numbers and vector dependencies stay buffered.",
    },
    {
      icon: "hash",
      title: "Digest anti-entropy",
      body: "Per-origin SHA-256 ranges highlight log divergence compactly.",
    },
    {
      icon: "graph",
      title: "Causal and peer graphs",
      body: "Inspect operation history, concurrency width, topology, and partitions.",
    },
    {
      icon: "spark",
      title: "Local duplicate hints",
      body: "Optional text similarity suggests catalog candidates; it never merges automatically.",
    },
    {
      icon: "scan",
      title: "Barcode and photo helpers",
      body: "Optional EAN validation, QR lookup, content hashes, and dHash checks.",
    },
    {
      icon: "lock",
      title: "Authenticated peers",
      body: "Timestamped HMAC and admin bearer checks protect lab controls.",
    },
    {
      icon: "out",
      title: "Not in this release",
      body: "Real-time collaboration, row-level permissions, multi-region deployment, and a formal proof of correctness are out of scope.",
      wide: true,
    },
  ],
  quickStart: [
    {
      title: "1. Install",
      body: "Python 3.12+ and uv. Copy the example environment and set distinct secrets for production mode.",
      powershell:
        "uv sync --extra dev\nCopy-Item .env.example .env\n# Set SYNCMESH_ADMIN_TOKEN\n# and SYNCMESH_PEER_SECRET",
      bash: "uv sync --extra dev\ncp .env.example .env\n# Set SYNCMESH_ADMIN_TOKEN\n# and SYNCMESH_PEER_SECRET",
    },
    {
      title: "2. Run the lab",
      body: "Start three independent nodes and the local dashboard with Docker Compose.",
      powershell:
        "docker compose up --build\n# Dashboard: http://localhost:5173\n# Node APIs: :8001, :8002, :8003",
      bash: "docker compose up --build\n# Dashboard: http://localhost:5173\n# Node APIs: :8001, :8002, :8003",
    },
    {
      title: "3. Replay a schedule",
      body: "Run one reproducible seed or regenerate the convergence, gossip, and catalog reports.",
      powershell: "make simulate SEED=42\nmake reproduce\n# See reports/reproduce.json",
      bash: "make simulate SEED=42\nmake reproduce\n# See reports/reproduce.json",
    },
  ],
  scope: {
    in: [
      "Offline-first writes on separate SQLite nodes",
      "Operation log replication and snapshot bootstrap",
      "Deterministic field merge and additive stock",
      "Seeded convergence and gossip experiments",
      "Local duplicate suggestions and barcode lookup",
    ],
    out: [
      "Production database workloads",
      "Strong consistency across disconnected nodes",
      "Real-time collaborative editing",
      "Internet-scale peer discovery",
      "Correctness claims beyond tested schedules",
    ],
  },
  faq: [
    {
      q: "What does “converge” mean here, and how do you know?",
      a: "For a fixed operation set and simulated delivery order, every replica ends with the same fields and stock. The generated report covers 1,000 deterministic schedules; that is evidence about this model, not a formal proof.",
    },
    {
      q: "What happens to a concurrent edit that loses?",
      a: "The per-field winner is selected by HLC, node ID, and operation ID. Both values and operation IDs are saved in an open conflict row; a review creates a new ordinary operation.",
    },
    {
      q: "Why not use last-write-wins for the whole item?",
      a: "The project keeps one register per field, so a concurrent name edit does not erase a price edit. Only concurrent writes to the same field need a deterministic winner.",
    },
    {
      q: "How does stock behave when two nodes update it offline?",
      a: "Each node contributes positive and negative PN-counter components. The displayed stock is the total positive amount minus the total negative amount, and may be negative with an oversold flag.",
    },
    {
      q: "How are duplicate items detected?",
      a: "The optional local NLP extra normalizes names and scores character n-grams plus token overlap. It only suggests candidates; the ten-pair generated evaluation is too small to estimate real catalog accuracy.",
    },
    {
      q: "Is barcode scanning a general image recognizer?",
      a: "No. The optional vision extra supports local QR decoding, EAN-13 checksum checks, content-addressed photo bytes, and a small perceptual hash helper.",
    },
    {
      q: "How are peers authenticated?",
      a: "Peer routes verify timestamped HMAC-SHA256 signatures; admin controls use a bearer token. Production mode fails closed without both secrets. Use TLS beyond a trusted lab network.",
    },
    {
      q: "What are the simulator's limits?",
      a: "It models operations, selected partitions, reordering, duplicate delivery, and deterministic clocks. It does not reproduce real packet loss, storage faults, process crashes, or production load.",
    },
    {
      q: "Is SyncMesh production ready?",
      a: "No. It is an educational lab. The authentication, fixed-window rate limits, SQLite schema, and simulations are demonstrations, not a substitute for production security or database operations.",
    },
  ],
  footer:
    "An educational lab for seeing how independent inventory nodes exchange and merge offline changes.",
};
