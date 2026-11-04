import type { ExtensionContext, UIPromptKind } from "@earendil-works/pi-coding-agent";
import { afterEach, expect, it, vi } from "vitest";
import * as filesystem from "node:fs/promises";
import type { PreferenceFileSystem } from "../../src/pi/notification-preference.ts";
import { installInsomniac } from "../../index.ts";
import { createAssertionProcess } from "../support/assertion-process.ts";
import { installNotifications, type NotificationDependencies } from "../../src/pi/notifications.ts";
import { createPiHost } from "../support/pi-host.ts";

const prompt = (type: "ui_prompt_start" | "ui_prompt_end", kind: UIPromptKind = "confirm") =>
  ({ type, reason: "ui_prompt", kind, title: "secret command and dialog" }) as const;

async function session(
  dependencies: NotificationDependencies = {},
  mode: ExtensionContext["mode"] = "tui",
  files?: PreferenceFileSystem,
) {
  if (!vi.isFakeTimers())
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setImmediate", "clearImmediate", "performance"] });
  const host = createPiHost(mode);
  const discover = vi.fn<() => Promise<string | undefined>>().mockResolvedValue("/fake/terminal-notifier");
  const execute = vi.fn().mockResolvedValue(undefined);
  installNotifications(host.pi, files, { platform: "darwin", discover, execute, ...dependencies });
  await Promise.all(host.emit("session_start"));

  return { ...host, discover, execute };
}

afterEach(() => vi.useRealTimers());

// Accepting hasUI, any prompt, or a later start would notify outside active macOS confirmations.
it.each([
  ["linux", "tui", "confirm", true],
  ["win32", "tui", "confirm", true],
  ["darwin", "print", "confirm", true],
  ["darwin", "json", "confirm", true],
  ["darwin", "rpc", "confirm", true],
  ["darwin", "tui", "select", true],
  ["darwin", "tui", "input", true],
  ["darwin", "tui", "editor", true],
  ["darwin", "tui", "custom", true],
  ["darwin", "tui", "confirm", false],
] as const)("ignores %s %s %s with active work %s", async (platform, mode, kind, active) => {
  const host = await session({ platform }, mode);

  if (active) host.emit("agent_start");
  host.emit(prompt("ui_prompt_start", kind));

  if (!active) host.emit("agent_start");
  await vi.advanceTimersByTimeAsync(20_000);
  expect(host.discover).not.toHaveBeenCalled();
  expect(host.execute).not.toHaveBeenCalled();
});

// Reinstalling against the same saved preference must not replay in-memory attention work.
it("discards pending confirmation history across a fresh extension installation", async () => {
  const old = await session();
  await old.command("enable");
  old.emit("agent_start");
  old.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(9_999);
  old.emit("session_shutdown");
  const restarted = await session();
  restarted.emit("agent_settled", false);
  await vi.advanceTimersByTimeAsync(20_000);
  expect(old.execute).not.toHaveBeenCalled();
  expect(restarted.execute).not.toHaveBeenCalled();
  restarted.emit("agent_start");
  restarted.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(9_999);
  expect(restarted.execute).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(restarted.execute).toHaveBeenCalledOnce();
});

// Obsolete attention failures must not consume the next session or confirmation's warning allowance.
it.each([
  ["discovery", "session replacement"],
  ["execution", "session replacement"],
  ["discovery", "a later confirmation opens"],
  ["execution", "a later confirmation opens"],
])("contains late attention %s errors after %s", async (phase, transition) => {
  let reject!: (error: Error) => void;

  const pending = () =>
    new Promise<never>((_resolve, fail) => {
      reject = fail;
    });

  const discover = vi.fn<() => Promise<string | undefined>>().mockResolvedValue("/fake/terminal-notifier");
  const execute = vi.fn().mockResolvedValue(undefined);

  if (phase === "discovery") discover.mockImplementationOnce(pending);
  else execute.mockImplementationOnce(pending);
  const host = await session({ discover, execute });
  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(10_000);

  if (transition === "session replacement") await Promise.all(host.emit("session_start"));
  else {
    host.emit(prompt("ui_prompt_end"));
    host.emit(prompt("ui_prompt_start"));
  }

  reject(new Error("obsolete failure"));
  await vi.advanceTimersByTimeAsync(0);
  expect(host.notify).not.toHaveBeenCalled();
  execute.mockRejectedValue(new Error("current failure"));

  if (transition === "session replacement") {
    host.emit("agent_start");
    host.emit(prompt("ui_prompt_start"));
  }

  await vi.advanceTimersByTimeAsync(10_000);
  expect(host.notify.mock.calls).toEqual([["Could not submit Insomniac notification.", "warning"]]);
});

// Awaiting delivery in prompt/settlement handlers would hold sleep protection or block work.
it("keeps sleep protection while waiting and releases at settlement while delivery remains pending", async () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
  const host = createPiHost();
  const assertion = createAssertionProcess();
  let finish!: () => void;

  const deliver = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );

  installInsomniac(host.pi, { platform: "darwin", spawn: assertion.spawn }, { deliver });
  await Promise.all(host.emit("session_start"));
  host.emit("agent_start");
  assertion.children[0].emit("spawn");
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(10_000);
  expect(deliver).toHaveBeenCalledOnce();
  expect(assertion.children[0].kill).not.toHaveBeenCalled();
  expect(host.render()).toContain("☕ awake");
  await Promise.all(host.emit(prompt("ui_prompt_end")));
  await Promise.all(host.emit("agent_settled", false));
  expect(assertion.children[0].kill).toHaveBeenCalledOnce();
  expect(host.render()).toContain("💤 can sleep");
  host.emit("agent_start");
  assertion.children[1].emit("spawn");
  finish();
  await vi.advanceTimersByTimeAsync(0);
  expect(host.render()).toContain("☕ awake");
  expect(assertion.children[1].kill).not.toHaveBeenCalled();
  host.emit("session_shutdown");
});

// Publishing an unsaved disable cancels a request even though notifications remain enabled.
it.each([false, true])("retains saved effective %s after a failed attention preference change", async (enabled) => {
  await filesystem.writeFile(`${process.env.PI_CODING_AGENT_DIR}/insomniac-notifications.json`, String(enabled));

  const host = await session({}, "tui", {
    ...filesystem,
    rename: async () => {
      throw new Error("save denied");
    },
  });

  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(9_999);
  await host.command(enabled ? "disable" : "enable");
  await vi.advanceTimersByTimeAsync(1);
  expect(host.execute).toHaveBeenCalledTimes(enabled ? 1 : 0);
  expect(host.notify).toHaveBeenCalledWith(expect.stringContaining("save denied"), "error");
});

// Uncaught boundary failures or discovery without a deadline could escape or retain pending work.
it.each([
  "discovery throw",
  "discovery reject",
  "discovery timeout",
  "execute throw",
  "execute reject",
  "execute timeout",
])("contains %s without retry and permits a later confirmation", async (failure) => {
  const error = new Error(failure);

  const fail = () => {
    if (failure.endsWith("throw")) throw error;

    return Promise.reject(error);
  };

  const discover = vi.fn<() => Promise<string | undefined>>().mockResolvedValue("/fake/terminal-notifier");
  const execute = vi.fn().mockResolvedValue(undefined);

  if (failure === "discovery timeout") discover.mockImplementationOnce(() => new Promise(() => {}));
  else if (failure.startsWith("discovery")) discover.mockImplementationOnce(fail);
  else execute.mockImplementationOnce(fail);
  const host = await session({ discover, execute });
  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(10_999);

  if (failure === "discovery timeout") expect(host.notify).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(host.notify.mock.calls).toEqual([["Could not submit Insomniac notification.", "warning"]]);
  await vi.advanceTimersByTimeAsync(30_000);
  expect(discover).toHaveBeenCalledOnce();
  expect(execute).toHaveBeenCalledTimes(failure.startsWith("discovery") ? 0 : 1);
  host.emit(prompt("ui_prompt_end"));
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(10_000);
  expect(discover).toHaveBeenCalledTimes(2);
  expect(execute).toHaveBeenCalledTimes(failure.startsWith("discovery") ? 1 : 2);
  expect(host.notify).toHaveBeenCalledOnce();
});

// Separate warning budgets or retrying a selected transport would duplicate noise or notices.
it.each([false, true])(
  "shares one warning for attention and completion (completion first: %s)",
  async (completionFirst) => {
    const execute = vi.fn().mockRejectedValue(new Error("native submission failed"));
    const host = await session({ execute });
    host.emit("agent_start");

    if (completionFirst) {
      await vi.advanceTimersByTimeAsync(30_000);
      host.emit("agent_settled", false);
      await vi.advanceTimersByTimeAsync(1);
      host.emit("agent_start");
    }

    host.emit(prompt("ui_prompt_start"));
    await vi.advanceTimersByTimeAsync(10_000);

    if (!completionFirst) {
      await vi.advanceTimersByTimeAsync(20_000);
      host.emit("agent_settled", false);
      await vi.advanceTimersByTimeAsync(1);
    }

    await vi.advanceTimersByTimeAsync(30_000);
    expect(execute).toHaveBeenCalledTimes(2);
    expect(host.notify.mock.calls).toEqual([["Could not submit Insomniac notification.", "warning"]]);
    host.emit(prompt("ui_prompt_end"));
    host.emit("agent_start");
    host.emit(prompt("ui_prompt_start"));
    await vi.advanceTimersByTimeAsync(9_999);
    expect(execute).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(execute.mock.calls.map(([file]) => file)).toEqual(Array(3).fill("/fake/terminal-notifier"));
    expect(host.notify).toHaveBeenCalledOnce();
  },
);

// Dialog data, full paths or executable label syntax must never cross the transport boundary.
it.each([
  ["/fake/terminal-notifier", undefined],
  ["/fake/terminal-notifier", "-help '雪'\n$(echo session)\u001b[31m\u0007"],
  [undefined, undefined],
  [undefined, "-help '雪'\n$(echo session)\u001b[31m\u0007"],
] as const)("sends only sanitized labels through %s with session %j", async (file, name) => {
  const host = await session({ discover: async () => file, environment: { TERM_PROGRAM: "ghostty" } });
  host.ctx.cwd = "/private/sensitive/-sound '雪'\n$(echo project)\u001b[31m\u0007";
  vi.spyOn(host.manager, "getSessionName").mockReturnValue(name);
  host.emit("agent_start");
  host.emit({ ...prompt("ui_prompt_start"), title: "/private/dialog: command password; response; tool error" });
  await vi.advanceTimersByTimeAsync(10_000);

  const body =
    name === undefined ? "-sound '雪' $(echo project)" : "-sound '雪' $(echo project) · -help '雪' $(echo session)";

  const [command, args, options] = host.execute.mock.calls[0];
  expect(command).toBe(file ?? "/usr/bin/osascript");
  expect(file ? args : args.slice(4)).toEqual(
    file
      ? ["-title", "\\Pi needs your attention", "-message", `\\${body}`, "-activate", "com.mitchellh.ghostty"]
      : ["--", "Pi needs your attention", body],
  );
  expect(options).toEqual({ timeout: 10_000, maxBuffer: 16_384 });
});

// Shared cancellation or mutable source identity would suppress or retarget another session.
it("keeps concurrent preferences, cancellation and captured activation targets independent", async () => {
  const environment = { TERM_PROGRAM: "ghostty" };
  let release!: (file: string) => void;

  const discover = vi.fn(
    () =>
      new Promise<string>((resolve) => {
        release = resolve;
      }),
  );

  const a = await session({ environment, discover });
  const b = await session({ environment: { TERM_PROGRAM: "Apple_Terminal" } });
  environment.TERM_PROGRAM = "iTerm.app";

  for (const host of [a, b]) {
    host.emit("agent_start");
    host.emit(prompt("ui_prompt_start"));
  }

  await vi.advanceTimersByTimeAsync(10_000);
  await a.command("disable");
  release("/fake/terminal-notifier");
  await vi.advanceTimersByTimeAsync(0);
  expect(a.execute).not.toHaveBeenCalled();
  expect(b.execute.mock.calls[0][1]).toEqual([
    "-title",
    "\\Pi needs your attention",
    "-message",
    "\\code · Review",
    "-activate",
    "com.apple.Terminal",
  ]);
  await a.command("enable");
  a.emit(prompt("ui_prompt_end"));
  a.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(10_000);
  release("/fake/terminal-notifier");
  await vi.advanceTimersByTimeAsync(0);
  expect(a.execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", "com.mitchellh.ghostty"]);
  expect(b.execute).toHaveBeenCalledOnce();
});

// A queued transport must yield to a close even when its timer has just reached the threshold.
it.each([0, 9_999, 10_000, 10_001])("cancels before transport starts at %i milliseconds", async (elapsed) => {
  const host = await session();
  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  vi.advanceTimersByTime(elapsed);
  host.emit(prompt("ui_prompt_end"));
  await vi.advanceTimersByTimeAsync(20_000);
  expect(host.execute).not.toHaveBeenCalled();
  expect(host.discover).not.toHaveBeenCalled();
});

// Rescheduling reminders or resetting the run on a continuation duplicates or loses dispatches.
it("gives each confirmation one full delay and no recurring reminders through continuations", async () => {
  const host = await session();
  host.emit(prompt("ui_prompt_end"));
  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(9_999);
  expect(host.execute).not.toHaveBeenCalled();

  for (const event of ["agent_start", "agent_end", "turn_end", "session_compact", "agent_before_settle"])
    host.emit(event);
  await vi.advanceTimersByTimeAsync(1);
  expect(host.execute).toHaveBeenCalledOnce();
  await vi.advanceTimersByTimeAsync(50_000);
  expect(host.execute).toHaveBeenCalledOnce();
  host.emit(prompt("ui_prompt_end"));
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(9_999);
  expect(host.execute).toHaveBeenCalledOnce();
  await vi.advanceTimersByTimeAsync(1);
  expect(host.execute).toHaveBeenCalledTimes(2);
});

// Enabling must not revive a request opened disabled or canceled by a committed disable.
it.each(["disabled", "waiting", "discovery"])("keeps %s confirmations canceled after enabling", async (phase) => {
  let release!: (file: string) => void;
  const discover = vi.fn<() => Promise<string | undefined>>().mockResolvedValue("/fake/terminal-notifier");

  if (phase === "discovery")
    discover.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve;
        }),
    );
  const host = await session({ discover });
  host.emit("agent_start");

  if (phase === "disabled") await host.command("disable");
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(phase === "discovery" ? 10_000 : 9_999);

  if (phase !== "disabled") await host.command("disable");
  await host.command("enable");

  if (phase === "discovery") release("/fake/terminal-notifier");
  await vi.advanceTimersByTimeAsync(10_000);
  expect(host.execute).not.toHaveBeenCalled();
  host.emit(prompt("ui_prompt_end"));
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(9_999);
  expect(host.execute).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(host.execute).toHaveBeenCalledOnce();
});

// The threshold is inclusive and a late timer must still qualify from its monotonic opening time.
it.each([0, 9_999, 10_000, 10_001])("qualifies only after %i elapsed milliseconds", async (elapsed) => {
  let now = 0;
  const host = await session({ now: () => now });
  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  now = elapsed;
  await vi.advanceTimersByTimeAsync(10_000);
  expect(host.execute).toHaveBeenCalledTimes(elapsed >= 10_000 ? 1 : 0);
  host.emit(prompt("ui_prompt_end"));
});

// Timer wakeups must use elapsed monotonic time rather than assuming their delay elapsed.
it("rechecks elapsed time at an early wakeup and includes exactly ten seconds", async () => {
  let now = 0;
  const host = await session({ now: () => now });
  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  expect(host.discover).not.toHaveBeenCalled();
  now = 9_999;
  await vi.advanceTimersByTimeAsync(10_000);
  expect(host.discover).not.toHaveBeenCalled();
  now = 10_000;
  await vi.advanceTimersByTimeAsync(1);
  expect(host.execute).toHaveBeenCalledOnce();
});

// Closure or settlement must invalidate both the waiting timer and asynchronous discovery.
it.each(["close", "settle", "abort", "reload", "shutdown", "replace", "restart"])(
  "cancels waiting and discovery on %s without replay",
  async (action) => {
    for (const discovering of [false, true]) {
      let release!: (file: string) => void;

      const discover = vi.fn(
        () =>
          new Promise<string>((resolve) => {
            release = resolve;
          }),
      );

      const host = await session({ discover });
      host.emit("agent_start");
      host.emit(prompt("ui_prompt_start"));
      await vi.advanceTimersByTimeAsync(discovering ? 10_000 : 9_999);

      if (action === "close") host.emit(prompt("ui_prompt_end"));
      else if (action === "settle" || action === "abort") host.emit("agent_settled", action === "abort");
      else {
        if (action !== "replace") host.emit("session_shutdown");

        if (action !== "shutdown") await Promise.all(host.emit("session_start"));
      }

      if (!discovering) expect(vi.getTimerCount()).toBe(0);

      if (discovering) release("/fake/terminal-notifier");
      await vi.advanceTimersByTimeAsync(30_000);
      expect(host.execute).not.toHaveBeenCalled();
      expect(host.notify).not.toHaveBeenCalled();
      expect(vi.getTimerCount()).toBe(0);
      host.emit("agent_settled", true);
      host.emit("session_shutdown");
    }
  },
);

// Removing attention detection loses a short run's confirmation even when completion cannot qualify.
it("submits an unanswered active confirmation at ten seconds with safe labels", async () => {
  const host = await session();
  host.emit("agent_start");
  host.emit(prompt("ui_prompt_start"));
  await vi.advanceTimersByTimeAsync(10_000);
  expect(host.execute.mock.calls).toEqual([
    [
      "/fake/terminal-notifier",
      ["-title", "\\Pi needs your attention", "-message", "\\code · Review"],
      { timeout: 10_000, maxBuffer: 16_384 },
    ],
  ]);
  host.emit(prompt("ui_prompt_end"));
  host.emit("agent_settled", false);
  await vi.advanceTimersByTimeAsync(1);
  expect(host.execute).toHaveBeenCalledOnce();
});
