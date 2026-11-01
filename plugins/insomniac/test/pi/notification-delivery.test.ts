import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import * as filesystem from "node:fs/promises";
import { expect, it, vi } from "vitest";
import type { NotificationExecutor } from "../../src/pi/desktop-notification.ts";
import { installNotifications } from "../../src/pi/notifications.ts";
import { installInsomniac } from "../../index.ts";
import { createAssertionProcess } from "../support/assertion-process.ts";
import { createPiHost } from "../support/pi-host.ts";

const flush = () => new Promise(setImmediate);

async function session(platform: NodeJS.Platform = "darwin", mode: ExtensionContext["mode"] = "tui") {
  const host = createPiHost(mode);
  let now = 0;
  const deliver = vi.fn().mockResolvedValue(undefined);
  installNotifications(host.pi, undefined, { platform, now: () => now, deliver });
  await Promise.all(host.emit("session_start"));

  return {
    ...host,
    deliver,
    time: (value: number) => {
      now = value;
    },
  };
}

// Dropping a zero start timestamp or using a strict threshold loses an eligible run.
it("submits once at 30 seconds from a zero timestamp", async () => {
  const host = await session();
  host.emit("agent_start");
  host.time(30_000);
  await Promise.all(host.emit("agent_settled", false));
  await flush();
  expect(host.deliver.mock.calls).toEqual([[{ title: "Pi run ended", body: "code · Review" }]]);
});

// Treating hasUI as TUI permission would allow RPC delivery.
it.each([
  ["linux", "tui"],
  ["win32", "tui"],
  ["darwin", "print"],
  ["darwin", "json"],
  ["darwin", "rpc"],
] as const)("allocates no delivery on %s in %s mode", async (platform, mode) => {
  const host = await session(platform, mode);
  host.emit("agent_start");
  host.time(60_000);
  host.emit("agent_settled", false);
  await flush();
  expect(host.deliver).not.toHaveBeenCalled();
});

// Restarting timing on retries loses waiting and recovery time.
it("retains the first start through turns, recovery, compaction and queued continuations", async () => {
  const host = await session();
  host.emit("agent_start");
  host.time(29_999);

  for (const event of [
    "turn_end",
    "agent_end",
    "session_compact",
    "agent_start",
    "agent_before_settle",
    "agent_start",
  ]) {
    host.emit(event);
    await flush();
    expect(host.deliver).not.toHaveBeenCalled();
  }

  host.time(30_000);
  host.emit("agent_settled", false);
  await flush();
  expect(host.deliver).toHaveBeenCalledOnce();
});

// Cancellation must consume the run without suppressing an independent later run.
it("suppresses aborted runs and independently qualifies later and simultaneous sessions", async () => {
  const a = await session();
  const b = await session();
  a.emit("agent_start");
  b.emit("agent_start");
  a.time(60_000);
  b.time(30_000);
  a.emit("agent_settled", true);
  a.emit("agent_settled", false);
  b.emit("agent_settled", false);
  await flush();
  expect(a.deliver).not.toHaveBeenCalled();
  expect(b.deliver).toHaveBeenCalledOnce();
  a.emit("agent_start");
  a.time(90_000);
  a.emit("agent_settled", false);
  await flush();
  expect(a.deliver).toHaveBeenCalledOnce();
});

// Using the startup value ignores assignments committed during an active run.
it("uses the effective preference at settlement without restarting duration", async () => {
  const host = await session();
  host.emit("agent_start");
  host.time(30_000);
  await host.command("disable");
  host.emit("agent_settled", false);
  await flush();
  expect(host.deliver).not.toHaveBeenCalled();
  host.emit("agent_start");
  host.time(60_000);
  await host.command("enable");
  host.emit("agent_settled", false);
  await flush();
  expect(host.deliver).toHaveBeenCalledOnce();
});

// Delivery errors must be contained, consumed, and limited to one warning per session.
it.each(["missing", "throw", "reject"])(
  "contains %s delivery failures and attempts later runs without retries",
  async (failure) => {
    const host = await session();
    host.deliver.mockImplementation(() => {
      const error = new Error(failure === "missing" ? "ENOENT" : "delivery failed");

      if (failure !== "reject") throw error;

      return Promise.reject(error);
    });

    for (const elapsed of [30_000, 60_000]) {
      host.emit("agent_start");
      host.time(elapsed);
      expect(() => host.emit("agent_settled", false)).not.toThrow();
      await flush();
      host.emit("agent_settled", false);
    }

    expect(host.deliver).toHaveBeenCalledTimes(2);
    expect(host.notify.mock.calls).toEqual([["Could not submit Insomniac notification.", "warning"]]);
  },
);

// An invalidated dispatch must not start, and old failures must not warn in a replacement.
it.each(["reload", "shutdown", "replace"])("invalidates pending dispatch and late failures on %s", async (action) => {
  const host = await session();
  host.emit("agent_start");
  host.time(30_000);
  host.emit("agent_settled", false);

  if (action !== "replace") host.emit("session_shutdown");
  await Promise.all(host.emit("session_start"));
  await flush();
  expect(host.deliver).not.toHaveBeenCalled();
  let reject!: (error: Error) => void;
  host.deliver.mockImplementationOnce(
    () =>
      new Promise((_resolve, fail) => {
        reject = fail;
      }),
  );
  host.emit("agent_start");
  host.time(60_000);
  host.emit("agent_settled", false);
  await flush();
  await Promise.all(host.emit("session_start"));
  reject(new Error("old failure"));
  await flush();
  expect(host.notify).not.toHaveBeenCalled();
  host.deliver.mockRejectedValue(new Error("new failure"));
  host.emit("agent_settled", false);
  host.emit("agent_start");
  host.time(90_000);
  host.emit("agent_settled", false);
  await flush();
  expect(host.deliver).toHaveBeenCalledTimes(2);
  expect(host.notify).toHaveBeenCalledOnce();
});

// Only display labels may cross the delivery boundary, with controls rendered inert.
it.each([undefined, "'雪'\n$(touch /tmp/never)\u001b[31m\u0007"])(
  "snapshots safe labels with session %j",
  async (name) => {
    const host = await session();
    host.ctx.cwd = "/private/project '雪'\n$(echo harmless)\u001b[31m\u0007";
    vi.spyOn(host.manager, "getSessionName").mockReturnValue(name);
    host.emit("agent_start");
    host.time(30_000);
    host.emit("agent_settled", false);
    host.ctx.cwd = "/replacement/other";
    vi.mocked(host.manager.getSessionName).mockReturnValue("other");
    await flush();
    expect(host.deliver.mock.calls).toEqual([
      [
        {
          title: "Pi run ended",
          body:
            name === undefined
              ? "project '雪' $(echo harmless)"
              : "project '雪' $(echo harmless) · '雪' $(touch /tmp/never)",
        },
      ],
    ]);
  },
);

// Slow delivery must never delay assertion release, footer refresh, or subsequent work.
it("releases sleep protection before dispatch and keeps working while delivery is pending", async () => {
  const host = createPiHost();
  const assertion = createAssertionProcess();
  let now = 0;
  let complete!: () => void;

  const deliver = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        complete = resolve;
      }),
  );

  installInsomniac(host.pi, { platform: "darwin", spawn: assertion.spawn }, { now: () => now, deliver });
  await Promise.all(host.emit("session_start"));
  host.emit("agent_start");
  assertion.children[0].emit("spawn");
  expect(host.render()).toContain("☕ awake");
  now = 30_000;
  await Promise.all(host.emit("agent_settled", false));
  expect(assertion.children[0].kill).toHaveBeenCalledOnce();
  expect(host.render()).toContain("💤 can sleep");
  expect(deliver).not.toHaveBeenCalled();
  await flush();
  expect(deliver).toHaveBeenCalledOnce();
  host.emit("agent_start");
  assertion.children[1].emit("spawn");
  complete();
  await flush();
  expect(host.render()).toContain("☕ awake");
  expect(assertion.children[1].kill).not.toHaveBeenCalled();
  host.emit("session_shutdown");
});

// A discovery finishing after invalidation must never submit into the next session.
it.each(["replace", "shutdown", "reload"])("discards delayed discovery on %s after releasing sleep", async (action) => {
  const host = createPiHost();
  const assertion = createAssertionProcess();
  let now = 0;
  let complete!: (file: string) => void;

  const discover = vi.fn(
    () =>
      new Promise<string>((resolve) => {
        complete = resolve;
      }),
  );

  const execute = vi.fn().mockResolvedValue(undefined);
  installInsomniac(host.pi, { platform: "darwin", spawn: assertion.spawn }, { now: () => now, discover, execute });
  await Promise.all(host.emit("session_start"));
  host.emit("agent_start");
  assertion.children[0].emit("spawn");
  now = 30_000;
  await Promise.all(host.emit("agent_settled", false));
  expect(assertion.children[0].kill).toHaveBeenCalledOnce();
  expect(host.render()).toContain("💤 can sleep");
  expect(discover).not.toHaveBeenCalled();
  await flush();
  expect(discover).toHaveBeenCalledOnce();

  if (action !== "replace") host.emit("session_shutdown");

  if (action !== "shutdown") await Promise.all(host.emit("session_start"));
  complete("/fake tools/helper");
  await flush();
  expect(execute).not.toHaveBeenCalled();
  expect(host.notify).not.toHaveBeenCalled();
  host.emit("session_shutdown");
});

// Discovery failures must use the session warning limiter and must not create a delivery process.
it.each(["throw", "reject"])("contains discovery %s and permits later independent attempts", async (failure) => {
  const host = createPiHost();
  let now = 0;

  const discover = vi.fn(() => {
    const error = new Error("discovery failed");

    if (failure === "throw") throw error;

    return Promise.reject(error);
  });

  const execute = vi.fn().mockResolvedValue(undefined);
  installNotifications(host.pi, undefined, { platform: "darwin", now: () => now, discover, execute });
  await Promise.all(host.emit("session_start"));

  for (const elapsed of [30_000, 60_000]) {
    host.emit("agent_start");
    now = elapsed;
    host.emit("agent_settled", false);
    await flush();
  }

  expect(discover).toHaveBeenCalledTimes(2);
  expect(execute).not.toHaveBeenCalled();
  expect(host.notify.mock.calls).toEqual([["Could not submit Insomniac notification.", "warning"]]);
});

// Late rejection from discovery or native delivery must not warn or consume the next session's warning.
it.each(["discovery", "delivery"])(
  "discards late %s failures and keeps replacement warnings independent",
  async (phase) => {
    const host = createPiHost();
    let now = 0;
    let reject!: (error: Error) => void;

    const pending = () =>
      new Promise<never>((_resolve, fail) => {
        reject = fail;
      });

    const discover = vi.fn<() => Promise<string | undefined>>().mockResolvedValue("/fake/helper");
    const execute = vi.fn<NotificationExecutor>().mockResolvedValue(undefined);

    if (phase === "discovery") discover.mockImplementationOnce(pending);
    else execute.mockImplementationOnce(pending);
    installNotifications(host.pi, undefined, { platform: "darwin", now: () => now, discover, execute });
    await Promise.all(host.emit("session_start"));
    host.emit("agent_start");
    now = 30_000;
    host.emit("agent_settled", false);
    await flush();
    host.emit("session_shutdown");
    await Promise.all(host.emit("session_start"));
    reject(new Error("old failure"));
    await flush();
    expect(host.notify).not.toHaveBeenCalled();
    execute.mockRejectedValue(new Error("new failure"));
    host.emit("agent_start");
    now = 60_000;
    host.emit("agent_settled", false);
    await flush();
    expect(host.notify.mock.calls).toEqual([["Could not submit Insomniac notification.", "warning"]]);
  },
);

// Retrying a failed selected transport can duplicate an already accepted OS request.
it.each(["ENOENT", "rejection", "throw", "timeout"])(
  "contains selected transport %s without fallback and retries only later runs",
  async (failure) => {
    const host = createPiHost();
    let now = 0;
    const discover = vi.fn().mockResolvedValue("/fake tools/helper");

    const execute = vi.fn<NotificationExecutor>(() => {
      const error = new Error(failure);

      if (failure === "throw") throw error;

      return Promise.reject(error);
    });

    installNotifications(host.pi, undefined, { platform: "darwin", now: () => now, discover, execute });
    await Promise.all(host.emit("session_start"));

    for (const elapsed of [30_000, 60_000]) {
      host.emit("agent_start");
      now = elapsed;
      host.emit("agent_settled", false);
      host.emit("agent_settled", false);
      await flush();
    }

    expect(execute.mock.calls.map(([file]) => file)).toEqual(["/fake tools/helper", "/fake tools/helper"]);
    expect(discover).toHaveBeenCalledTimes(2);
    expect(host.notify.mock.calls).toEqual([["Could not submit Insomniac notification.", "warning"]]);
  },
);

// Checking only the injected legacy delivery seam can hide accidental discovery in unsupported hosts.
it.each([
  ["linux", "tui"],
  ["win32", "tui"],
  ["darwin", "print"],
  ["darwin", "json"],
  ["darwin", "rpc"],
] as const)("does not discover tools on %s in %s", async (platform, mode) => {
  const host = createPiHost(mode);
  let now = 0;
  const discover = vi.fn().mockResolvedValue(undefined);
  const execute = vi.fn().mockResolvedValue(undefined);
  installNotifications(host.pi, undefined, { platform, now: () => now, discover, execute });
  await Promise.all(host.emit("session_start"));
  host.emit("agent_start");
  now = 30_000;
  host.emit("agent_settled", false);
  await flush();
  expect(discover).not.toHaveBeenCalled();
  expect(execute).not.toHaveBeenCalled();
});

// A failed save must not publish an unsaved assignment into qualification.
it.each([false, true])("retains effective %s after a failed preference assignment", async (enabled) => {
  await filesystem.writeFile(`${process.env.PI_CODING_AGENT_DIR}/insomniac-notifications.json`, String(enabled));
  const host = createPiHost();
  let now = 0;
  const deliver = vi.fn().mockResolvedValue(undefined);
  installNotifications(
    host.pi,
    {
      ...filesystem,
      rename: async () => {
        throw new Error("save denied");
      },
    },
    { platform: "darwin", now: () => now, deliver },
  );
  await Promise.all(host.emit("session_start"));
  host.emit("agent_start");
  await host.command(enabled ? "disable" : "enable");
  now = 30_000;
  host.emit("agent_settled", false);
  await flush();
  expect(deliver).toHaveBeenCalledTimes(enabled ? 1 : 0);
  expect(host.notify).toHaveBeenCalledWith(expect.stringContaining("save denied"), "error");
});

// An active run must be discarded on replacement even when no dispatch is pending yet.
it.each(["session_start", "session_shutdown"])("discards active duration at %s without replay", async (event) => {
  const host = await session();
  host.emit("agent_start");
  host.time(30_000);
  await Promise.all(host.emit(event));

  if (event === "session_shutdown") await Promise.all(host.emit("session_start"));
  host.emit("agent_settled", false);
  await flush();
  expect(host.deliver).not.toHaveBeenCalled();
});

// Every settlement must consume its run, including short and aborted runs.
it.each([0, 29_999, 30_000, 30_001])(
  "consumes the run at %i milliseconds without duplicate delivery",
  async (elapsed) => {
    const host = await session();
    host.emit("agent_settled", false);
    host.emit("agent_start");
    host.time(elapsed);
    host.emit("agent_settled", false);
    await flush();
    host.time(90_000);
    host.emit("agent_settled", false);
    await flush();
    expect(host.deliver).toHaveBeenCalledTimes(elapsed >= 30_000 ? 1 : 0);
  },
);
