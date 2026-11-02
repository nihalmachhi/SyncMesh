import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useTour } from "./useTour";

afterEach(() => {
  vi.useRealTimers();
});

describe("useTour", () => {
  it("advances on its interval and can pause", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useTour(5, 1000));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.active).toBe(1);
    act(() => {
      result.current.setPaused(true);
    });
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(result.current.active).toBe(1);
  });
  it("holds progress while the user is focused or hovering", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useTour(5, 1000));
    act(() => {
      result.current.setHeld(true);
    });
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(result.current.active).toBe(0);
    act(() => {
      result.current.setHeld(false);
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.active).toBe(1);
  });
});
