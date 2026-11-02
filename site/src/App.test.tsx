import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("SyncMesh site", () => {
  it("shows the local replication demo and generated experiment data", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /Make offline changes/ })).toBeInTheDocument();
    expect(screen.getByText("Operation convergence").parentElement).toHaveTextContent(
      "1000/1000",
    );
    expect(await screen.findByText(/Python merge parity/)).toBeInTheDocument();
  });
  it("lets keyboard and pointer users change tour stages", () => {
    render(<App />);
    const writeTab = screen.getByRole("tab", { name: "Write" });
    fireEvent.keyDown(writeTab, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Exchange" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("tab", { name: "Merge" }));
    expect(screen.getByText("Fields and stock use different rules")).toBeInTheDocument();
  });
  it("shows divergent local replica values until peers reconnect", async () => {
    render(<App />);
    await screen.findByText(/Python merge parity/);
    expect(screen.getByText("Brown rice")).toBeInTheDocument();
    expect(screen.getAllByText("Whole grain rice")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Reconnect peers" }));
    expect(screen.getByText("peers synchronized · replicas agree")).toBeInTheDocument();
    expect(screen.getAllByText("SYNCED")).toHaveLength(3);
  });
  it("uses native disclosure controls for the FAQ", () => {
    render(<App />);
    const answer = screen.getByText(/For a fixed operation set/);
    expect(answer).not.toBeVisible();
    fireEvent.click(screen.getByText(/What does “converge” mean/));
    expect(answer).toBeVisible();
  });
});
