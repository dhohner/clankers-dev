import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import { expect, it, vi } from "vitest";
import { createDesktopDelivery, createNotifierDiscovery } from "../../src/pi/desktop-notification.ts";

// Ignoring discovery always submits through the fallback instead of the installed tool.
it("submits through the discovered executable with inert native arguments", async () => {
  const execute = vi.fn().mockResolvedValue(undefined);
  const notice = { title: "Pi run ended", body: "-help 雪\n'\"; $(touch /tmp/never)" };
  await createDesktopDelivery(execute, async () => "/fake tools/terminal-notifier")(notice);
  expect(execute.mock.calls).toEqual([
    [
      "/fake tools/terminal-notifier",
      ["-title", "\\Pi run ended", "-message", `\\${notice.body}`],
      { timeout: 10_000, maxBuffer: 16_384 },
    ],
  ]);
});

it.each([
  [["/tools with spaces/terminal-notifier", "/second/terminal-notifier"], "/tools with spaces/terminal-notifier"],
  [["/second/terminal-notifier"], "/second/terminal-notifier"],
  [[], undefined],
] as const)("selects the first installed tool from %j", async (installed, expected) => {
  const isExecutable = vi.fn(async (file: string) => installed.some((path) => path === file));

  const discover = createNotifierDiscovery({
    searchPath: "relative::/tools with spaces:/second",
    isExecutable,
  });

  const execute = vi.fn().mockResolvedValue(undefined);
  await createDesktopDelivery(execute, discover)({ title: "Pi run ended", body: "project" });
  expect(execute.mock.calls.map(([file]) => file)).toEqual([expected ?? "/usr/bin/osascript"]);
  expect(isExecutable.mock.calls.every(([file]) => file.startsWith("/"))).toBe(true);
});

// Existence alone would select a directory or an inaccessible file instead of the fallback.
it("requires executable files during filesystem discovery", async () => {
  const directory = mkdtempSync(join(tmpdir(), "insomniac-discovery-"));
  const standard = join(directory, "terminal-notifier");

  try {
    mkdirSync(standard);
    const discover = createNotifierDiscovery({ searchPath: directory });
    expect(await discover()).toBeUndefined();
    rmSync(standard, { recursive: true });
    writeFileSync(standard, "", { mode: 0o600 });
    expect(await discover()).toBeUndefined();
    chmodSync(standard, 0o700);
    expect(await discover()).toBe(standard);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

// A hung discovery must finish without spawning a process, and a later run can try again.
it("bounds discovery to one second", async () => {
  vi.useFakeTimers();

  try {
    const execute = vi.fn().mockResolvedValue(undefined);

    const discover = vi
      .fn<() => Promise<string | undefined>>()
      .mockImplementationOnce(() => new Promise(() => {}))
      .mockResolvedValue(undefined);

    const deliver = createDesktopDelivery(execute, discover);
    let failure: unknown;

    const result = deliver({ title: "Pi run ended", body: "project" }).catch((error: Error) => {
      failure = error;
    });

    await vi.advanceTimersByTimeAsync(1_000);
    expect(failure).toEqual(new Error("Notification tool discovery timed out"));
    await result;
    expect(execute).not.toHaveBeenCalled();
    await deliver({ title: "Pi run ended", body: "later" });
    expect(execute).toHaveBeenCalledOnce();
  } finally {
    vi.useRealTimers();
  }
});

// Removing the escape prefix lets NSUserDefaults turn display text into flags or property lists.
it.skipIf(process.platform !== "darwin")(
  "keeps native labels inert through the actual Foundation argument parser",
  async () => {
    const directory = mkdtempSync(join(tmpdir(), "insomniac-arguments-"));
    const executable = join(directory, "fake notifier");

    try {
      execFileSync("cc", [
        "-framework",
        "Foundation",
        "-o",
        executable,
        fileURLToPath(new URL("../fixtures/notifier-arguments.m", import.meta.url)),
      ]);
      const execute = vi.fn().mockResolvedValue(undefined);
      const deliver = createDesktopDelivery(execute, async () => executable);

      for (const body of [
        "-help",
        "-sound",
        "--diagnose",
        "[array]",
        "{key=value;}",
        "'quoted'",
        "\\path with spaces",
        "雪\n'\"; $(touch /tmp/never)",
      ]) {
        for (const activationTarget of [undefined, "com.apple.Terminal", "App", "123", "org.example.-App"]) {
          await deliver({ title: "Pi run ended", body, activationTarget });
          // SAFETY: The awaited delivery records an execute call before resolving.
          const [, args] = execute.mock.calls.at(-1)!;
          const result = spawnSync(executable, args, { encoding: "utf8", timeout: 10_000 });
          expect(result.status, result.stderr).toBe(0);
          expect(JSON.parse(result.stdout)).toEqual(
            activationTarget ? ["Pi run ended", body, activationTarget] : ["Pi run ended", body],
          );
        }
      }
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  },
);

// Interpolating labels into script source or a shell allows data to become code.
it("passes labels as arguments to a fixed script and requests only standard notification presentation", async () => {
  const execute = vi.fn().mockResolvedValue(undefined);
  const notice = { title: "Pi run ended", body: "雪\n'\"; $(touch /tmp/never)\u001b\u0000" };
  await createDesktopDelivery(execute, async () => undefined)(notice);
  expect(execute).toHaveBeenCalledOnce();
  const [command, args, options] = execute.mock.calls[0];
  expect(command).toBe("/usr/bin/osascript");
  expect(args.slice(0, 3)).toEqual(["-l", "JavaScript", "-e"]);
  expect(args.slice(4)).toEqual(["--", notice.title, notice.body]);
  expect(options).toEqual({ timeout: 10_000, maxBuffer: 16_384 });
  const displayNotification = vi.fn();
  const app = { includeStandardAdditions: false, displayNotification };
  runInNewContext(`${args[3]}; run(argv);`, {
    Application: { currentApplication: () => app },
    argv: [notice.title, notice.body],
  });
  expect(app.includeStandardAdditions).toBe(true);
  expect(displayNotification.mock.calls).toEqual([[notice.body, { withTitle: "Pi run ended" }]]);
});
