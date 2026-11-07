import { execFile } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { runInNewContext } from "node:vm";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createDesktopDelivery, createNotifierDiscovery } from "../../src/pi/desktop-notification.ts";

const displayLabels = [
  "",
  "Pi run ended",
  "-help",
  "-sound",
  "--diagnose",
  "[array]",
  "{key=value;}",
  "'quoted'",
  "\\path with spaces",
  "雪\n'\"; $(touch /tmp/never)",
];

const activationTargets = [undefined, "", "com.apple.Terminal", "App", "123", "org.example.-App"];

// Missing escaping on either label exposes display text to NSUserDefaults parsing.
describe.each(displayLabels)("native arguments with title %j", (title) => {
  describe.each(displayLabels)("body %j", (body) => {
    it.each(activationTargets)("preserves labels with activation target %j", async (activationTarget) => {
      const execute = vi.fn().mockResolvedValue(undefined);
      await createDesktopDelivery(
        execute,
        async () => "/fake tools/terminal-notifier",
      )({
        title,
        body,
        activationTarget,
      });
      expect(execute.mock.calls).toEqual([
        [
          "/fake tools/terminal-notifier",
          [
            "-title",
            `\\${title}`,
            "-message",
            `\\${body}`,
            ...(activationTarget ? ["-activate", activationTarget] : []),
          ],
          { timeout: 10_000, maxBuffer: 16_384 },
        ],
      ]);
    });
  });
});

// Shell or script interpolation would alter labels instead of keeping them in argv.
describe.each(displayLabels)("fallback arguments with title %j", (title) => {
  it.each(displayLabels)("preserves body %j", async (body) => {
    const execute = vi.fn().mockResolvedValue(undefined);
    await createDesktopDelivery(execute, async () => undefined)({ title, body });
    expect(execute).toHaveBeenCalledOnce();
    const [file, args, options] = execute.mock.calls[0];
    expect(file).toBe("/usr/bin/osascript");
    expect(args.slice(0, 3)).toEqual(["-l", "JavaScript", "-e"]);
    expect(args.slice(4)).toEqual(["--", title, body]);
    expect(options).toEqual({ timeout: 10_000, maxBuffer: 16_384 });
  });
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

    await vi.advanceTimersByTimeAsync(999);
    expect(failure).toBeUndefined();
    expect(execute).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
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
describe.skipIf(process.platform !== "darwin")("Foundation argument parser", () => {
  const executeFile = promisify(execFile);
  let directory: string | undefined;
  let executable: string;

  beforeAll(async () => {
    directory = mkdtempSync(join(tmpdir(), "insomniac-arguments-"));
    executable = join(directory, "fake notifier");
    await executeFile(
      "cc",
      [
        "-framework",
        "Foundation",
        "-o",
        executable,
        fileURLToPath(new URL("../fixtures/notifier-arguments.m", import.meta.url)),
      ],
      { timeout: 10_000 },
    );
  });

  afterAll(() => {
    if (directory) rmSync(directory, { recursive: true, force: true });
  });

  it.for([
    ...["-help", "[array]", "{key=value;}", "'quoted'", "\\path with spaces", "雪\n'\"; $(touch /tmp/never)"].flatMap(
      (label) => [
        { title: label, body: "project", activationTarget: undefined },
        { title: "Pi run ended", body: label, activationTarget: undefined },
      ],
    ),
    ...["com.apple.Terminal", "App", "123", "org.example.-App"].map((activationTarget) => ({
      title: "Pi run ended",
      body: "project",
      activationTarget,
    })),
  ])("keeps native labels inert for %j", async ({ title, body, activationTarget }, { signal }) => {
    const execute = vi.fn().mockResolvedValue(undefined);
    const deliver = createDesktopDelivery(execute, async () => executable);
    await deliver({ title, body, activationTarget });
    const [, args] = execute.mock.calls[0];
    const result = await executeFile(executable, args, { encoding: "utf8", timeout: 4_000, signal });
    expect(JSON.parse(result.stdout)).toEqual(activationTarget ? [title, body, activationTarget] : [title, body]);
  });
});

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
