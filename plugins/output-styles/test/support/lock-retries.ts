import { expect, vi } from "vitest";

/** Keep filesystem operations real while advancing only the lock retry timers. */
export function controlLockRetries() {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  const timers = vi.spyOn(globalThis, "setTimeout");
  let observed = 0;

  return async (delay: number) => {
    observed += 1;
    const retries = () => timers.mock.calls.filter(([, timeout]) => timeout !== undefined && timeout <= 100);
    // A zero interval lets filesystem callbacks run without advancing the fake clock.
    await vi.waitFor(() => expect(retries()).toHaveLength(observed), { interval: 0 });
    expect(retries().at(-1)?.[1]).toBe(delay);
  };
}
