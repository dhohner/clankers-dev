import { expect, it, vi } from "vitest";
import { installNotifications } from "../../src/pi/notifications.ts";
import { createPiHost } from "../support/pi-host.ts";

const flush = () => new Promise(setImmediate);

// Discovery completion must use the original target and must discard an invalidated dispatch.
it.each(["complete", "replace", "shutdown"])("keeps delayed discovery isolated on %s", async (action) => {
  const host = createPiHost();
  const environment: NodeJS.ProcessEnv = { TERM_PROGRAM: "ghostty" };
  let now = 0;
  let complete!: (tool: string) => void;
  const execute = vi.fn().mockResolvedValue(undefined);
  installNotifications(host.pi, undefined, {
    platform: "darwin",
    environment,
    now: () => now,
    execute,
    discover: () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  });
  await Promise.all(host.emit("session_start"));
  host.emit("agent_start");
  now = 30_000;
  host.emit("agent_settled", false);
  await flush();
  environment.TERM_PROGRAM = "Apple_Terminal";

  if (action === "replace") await Promise.all(host.emit("session_start"));

  if (action === "shutdown") host.emit("session_shutdown");
  complete("/fake/helper");
  await flush();

  if (action === "complete") {
    expect(execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", "com.mitchellh.ghostty"]);
  } else {
    expect(execute).not.toHaveBeenCalled();
  }

  expect(host.notify).not.toHaveBeenCalled();
});

// Looking up identity at settlement or dispatch retargets an accepted notice.
it("keeps independent targets through delayed delivery and session replacement", async () => {
  const environment: NodeJS.ProcessEnv = { TERM_PROGRAM: "ghostty" };
  const a = await sourceSession(environment);
  environment.TERM_PROGRAM = "iTerm.app";
  const b = await sourceSession(environment);
  environment.TERM_PROGRAM = "Apple_Terminal";
  environment.INSOMNIAC_SOURCE_APP = "org.example.Later";
  await a.settle();
  await b.settle();
  expect(a.execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", "com.mitchellh.ghostty"]);
  expect(b.execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", "com.googlecode.iterm2"]);
  await Promise.all(a.emit("session_start"));
  await a.settle();
  expect(a.execute.mock.calls[1][1].slice(-2)).toEqual(["-activate", "org.example.Later"]);
});

// A valid override must not add a custom click action to the fixed fallback script.
it("leaves osascript click behavior to macOS even with an override", async () => {
  const host = await sourceSession({ INSOMNIAC_SOURCE_APP: "org.example.Override" }, null);
  await host.settle();
  expect(host.execute.mock.calls[0][0]).toBe("/usr/bin/osascript");
  expect(host.execute.mock.calls[0][1].slice(4)).toEqual(["--", "Pi run ended", "code · Review"]);
});

// SSH and multiplexer markers must not suppress a deliberate local activation override.
it.each(["SSH_CONNECTION", "TMUX", "STY"])("honors a valid override with %s present", async (marker) => {
  const host = await sourceSession({ [marker]: "synthetic", INSOMNIAC_SOURCE_APP: "org.example.Local" });
  await host.settle();
  expect(host.execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", "org.example.Local"]);
});

// Qualification must still prevent all process creation when a target is available.
it.each([
  ["darwin", "tui", 29_999, false, true],
  ["darwin", "tui", 30_000, true, true],
  ["darwin", "tui", 30_000, false, false],
  ["linux", "tui", 30_000, false, true],
  ["darwin", "rpc", 30_000, false, true],
] as const)(
  "suppresses activation on %s/%s at %i aborted=%s enabled=%s",
  async (platform, mode, elapsed, aborted, enabled) => {
    const host = createPiHost(mode);
    let now = 0;
    const execute = vi.fn().mockResolvedValue(undefined);
    const discover = vi.fn().mockResolvedValue("/fake/helper");
    installNotifications(host.pi, undefined, {
      platform,
      environment: { INSOMNIAC_SOURCE_APP: "org.example.App" },
      now: () => now,
      execute,
      discover,
    });
    await Promise.all(host.emit("session_start"));

    if (!enabled) await host.command("disable");
    host.emit("agent_start");
    now = elapsed;
    host.emit("agent_settled", aborted);
    await flush();
    expect(discover).not.toHaveBeenCalled();
    expect(execute).not.toHaveBeenCalled();
  },
);

// Bundle identifiers are case insensitive; equivalent identity must not be treated as a conflict.
it("accepts matching source metadata regardless of bundle identifier case", async () => {
  const host = await sourceSession({ TERM_PROGRAM: "ghostty", __CFBundleIdentifier: "COM.MITCHELLH.GHOSTTY" });
  await host.settle();
  expect(host.execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", "com.mitchellh.ghostty"]);
});

// Testing marker truthiness permits automatic activation when a context marker is present but empty.
it.each(["SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY", "TMUX", "STY"])(
  "omits automatic activation when %s is empty",
  async (marker) => {
    const host = await sourceSession({ TERM_PROGRAM: "ghostty", [marker]: "" });
    await host.settle();
    expect(host.execute.mock.calls[0][1]).toEqual(["-title", "\\Pi run ended", "-message", "\\code · Review"]);
  },
);

// Trusting inherited or malformed identity can activate an unrelated local app.
it.each([
  {},
  { TERM_PROGRAM: "unknown" },
  { TERM_PROGRAM: "toString" },
  { __CFBundleIdentifier: "com.app\n" },
  { __CFBundleIdentifier: "-help" },
  { __CFBundleIdentifier: "com.app;open" },
  { TERM_PROGRAM: "ghostty", __CFBundleIdentifier: "com.apple.Terminal" },
  { TERM_PROGRAM: "ghostty", SSH_CONNECTION: "synthetic" },
  { TERM_PROGRAM: "ghostty", SSH_CLIENT: "synthetic" },
  { TERM_PROGRAM: "ghostty", SSH_TTY: "/fake/tty" },
  { TERM_PROGRAM: "ghostty", TMUX: "/fake/tmux" },
  { TERM_PROGRAM: "ghostty", STY: "screen" },
  { TERM_PROGRAM: "ghostty", INSOMNIAC_SOURCE_APP: "com.app\n" },
])("omits activation for unknown or unreliable source %j", async (environment) => {
  const host = await sourceSession(environment);
  await host.settle();
  expect(host.execute.mock.calls[0][1]).toEqual(["-title", "\\Pi run ended", "-message", "\\code · Review"]);
});

// Invalid explicit values must suppress activation instead of falling back to detection.
it.each([
  "",
  " ",
  "com.example app",
  "com.example\nApp",
  "com.example\u0000App",
  "com.example\u001bApp",
  "-activate",
  "--help",
  "$(open app)",
  "com.example;open",
  "com.example/App",
  "com.example_App",
  "com.雪.App",
  ".com.app",
  "com..app",
  "com.app.",
])("delivers without activation for invalid override %j", async (value) => {
  const host = await sourceSession({ TERM_PROGRAM: "ghostty", INSOMNIAC_SOURCE_APP: value });
  await host.settle();
  expect(host.execute.mock.calls[0].slice(0, 2)).toEqual([
    "/fake/helper",
    ["-title", "\\Pi run ended", "-message", "\\code · Review"],
  ]);
});

// Overly strict reverse DNS or letter-only validation rejects legal bundle IDs.
it.each(["App", "123", "COM.Example.App-2", "org.123.4-App", "a.b", "org.example.-App"])(
  "accepts the bundle identifier boundary %s",
  async (target) => {
    const host = await sourceSession({ INSOMNIAC_SOURCE_APP: target });
    await host.settle();
    expect(host.execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", target]);
  },
);

// Ignoring the explicit setting or retaining a removed override selects the wrong app.
it("gives the override precedence and detects again in a new session after removal", async () => {
  const environment: NodeJS.ProcessEnv = { TERM_PROGRAM: "ghostty", INSOMNIAC_SOURCE_APP: "org.example.Override" };
  const host = await sourceSession(environment);
  await host.settle();
  expect(host.execute.mock.calls[0][1].slice(-2)).toEqual(["-activate", "org.example.Override"]);
  delete environment.INSOMNIAC_SOURCE_APP;
  await Promise.all(host.emit("session_start"));
  await host.settle();
  expect(host.execute.mock.calls[1][1].slice(-2)).toEqual(["-activate", "com.mitchellh.ghostty"]);
});

async function sourceSession(environment: NodeJS.ProcessEnv, tool: string | null = "/fake/helper") {
  const host = createPiHost();
  let now = 0;
  const execute = vi.fn().mockResolvedValue(undefined);
  installNotifications(host.pi, undefined, {
    platform: "darwin",
    environment,
    now: () => now,
    discover: async () => tool ?? undefined,
    execute,
  });
  await Promise.all(host.emit("session_start"));

  return {
    ...host,
    execute,
    async settle() {
      host.emit("agent_start");
      now += 30_000;
      host.emit("agent_settled", false);
      await flush();
    },
  };
}

// Dropping source detection or either notifier's activation argument loses native click activation.
it.each([
  ["ghostty", undefined, "com.mitchellh.ghostty"],
  ["iTerm.app", undefined, "com.googlecode.iterm2"],
  ["Apple_Terminal", undefined, "com.apple.Terminal"],
  ["other", "org.example.Other-App", "org.example.Other-App"],
])("activates %s from its originating identity with both notifiers", async (terminal, bundle, target) => {
  for (const tool of ["/fake/Pi Notifier.app/terminal-notifier", "/fake/terminal-notifier"]) {
    const host = await sourceSession({ TERM_PROGRAM: terminal, __CFBundleIdentifier: bundle }, tool);
    await host.settle();
    expect(host.execute.mock.calls).toEqual([
      [
        tool,
        ["-title", "\\Pi run ended", "-message", "\\code · Review", "-activate", target],
        { timeout: 10_000, maxBuffer: 16_384 },
      ],
    ]);
  }
});
