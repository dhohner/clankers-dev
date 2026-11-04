// Load the actual Pi extension factory and dispatch lifecycle events through Pi's runner.
// OS process creation and notification delivery are replaced; model networking is disabled.
import assert from "node:assert/strict";
import childProcess from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
import { once } from "node:events";
import { basename, resolve, dirname } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { mock } from "node:test";
// Pi queues prompt events as microtasks; yield a turn so their Promise continuations also finish.
import { setImmediate as yieldToEventLoop } from "node:timers/promises";

const realSetTimeout = setTimeout;

const realDelay = (milliseconds) => new Promise((complete) => realSetTimeout(complete, milliseconds));

// Source identity is controlled without reading the host's environment or foreground app.
for (const key of [
  "INSOMNIAC_SOURCE_APP",
  "__CFBundleIdentifier",
  "SSH_CONNECTION",
  "SSH_CLIENT",
  "SSH_TTY",
  "TMUX",
  "STY",
]) {
  delete process.env[key];
}

process.env.TERM_PROGRAM = "ghostty";

// Real discovery sees only controlled files; every possible notifier is intercepted below.
const toolsDirectory = resolve(process.env.PI_CODING_AGENT_DIR, "tools with spaces");

const standardPath = resolve(toolsDirectory, "terminal-notifier");

process.env.PATH = toolsDirectory;

for (const file of process.env.INSOMNIAC_TEST_TOOLS === "standard" ? [standardPath] : []) {
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, "#!/bin/sh\nexit 99\n", { mode: 0o700 });
}

const realSpawn = childProcess.spawn;

const realExecFile = childProcess.execFile;

const desktopRequests = [];

let elapsed = 0;

Object.defineProperty(performance, "now", { value: () => elapsed });

childProcess.execFile = (command, args, options, callback) => {
  if (!["/usr/bin/osascript", standardPath].includes(command)) return realExecFile(command, args, options, callback);
  desktopRequests.push({ command, args, options });

  return realExecFile(process.execPath, ["-e", ""], options, callback);
};

childProcess.execFile[promisify.custom] = (command, args, options) =>
  new Promise((complete, reject) => {
    childProcess.execFile(command, args, options, (error, stdout, stderr) => {
      if (error) reject(error);
      else complete({ stdout, stderr });
    });
  });

const children = [];

childProcess.spawn = (command, args, options) => {
  if (command !== "/usr/bin/caffeinate") return realSpawn(command, args, options);
  const child = realSpawn(process.env.INSOMNIAC_TEST_EXECUTABLE, args, options);
  children.push(child);

  return child;
};

syncBuiltinESMExports();

const host = await import(process.env.INSOMNIAC_TEST_PI ?? "@earendil-works/pi-coding-agent");

assert.equal(host.VERSION, "1.5.0");

console.log(`Pi runtime: ${host.VERSION}`);

const plugin = resolve(import.meta.dirname, "../../index.ts");

const loaded = await host.discoverAndLoadExtensions([plugin], process.cwd(), process.env.PI_CODING_AGENT_DIR);

assert.deepEqual(loaded.errors, []);

assert.equal(children.length, 0, "loading the factory must not start resources");

loaded.runtime.getThinkingLevel = () => "high";

const models = await host.ModelRuntime.create({
  authPath: resolve(process.env.PI_CODING_AGENT_DIR, "auth.json"),
  modelsPath: null,
  modelsStorePath: resolve(process.env.PI_CODING_AGENT_DIR, "models-cache.json"),
  allowModelNetwork: false,
  refreshOnCreate: false,
});

const sessionManager = host.SessionManager.inMemory();

sessionManager.appendSessionInfo("Demo review");

const runner = new host.ExtensionRunner(
  loaded.extensions,
  loaded.runtime,
  process.cwd(),
  sessionManager,
  new host.ModelRegistry(models),
);

const errors = [];

runner.onError((error) => errors.push(error));

let footer;

let renders = 0;

const notifications = [];

const confirmations = [];

const promptEvents = [];

const emit = runner.emit.bind(runner);

runner.emit = (event) => {
  if (event.type === "ui_prompt_start" || event.type === "ui_prompt_end") promptEvents.push(event);

  return emit(event);
};

runner.setUIContext(
  {
    confirm(_title, _message, options) {
      return new Promise((complete, reject) => {
        const abort = () => complete(false);

        const finish = (value) => {
          options?.signal?.removeEventListener("abort", abort);
          complete(value);
        };

        options?.signal?.addEventListener("abort", abort, { once: true });

        if (options?.signal?.aborted) abort();
        confirmations.push({ complete: finish, reject });
      });
    },
    notify(message, type) {
      notifications.push({ message, type });
      console.log(`${type}: ${message}`);
    },
    setFooter(factory) {
      footer?.dispose?.();
      footer = factory?.(
        { requestRender: () => renders++ },
        { getThinkingBorderColor: () => (text) => text },
        {
          getGitBranch: () => "main",
          getExtensionStatuses: () => new Map([["other", "other active"]]),
          getAvailableProviderCount: () => 0,
          onBranchChange: () => () => {},
        },
      );
    },
  },
  "tui",
);

const render = () => footer.render(100).join("\n");

const live = (pid) => {
  try {
    process.kill(pid, 0);

    return true;
  } catch {
    return false;
  }
};

const gone = async (child) => {
  if (child.exitCode === null && child.signalCode === null) await once(child, "exit");
  assert.equal(live(child.pid), false);
};

try {
  await runner.emit({ type: "session_start" });
  assert.match(render(), /can sleep/u);
  assert.match(render(), /~\$0\.000/u);
  const preference = runner.getCommand("insomniac-notifications");
  assert.ok(preference, "notification command must be registered");
  const commandContext = runner.createCommandContext();
  await preference.handler("status", commandContext);
  await preference.handler("disable", commandContext);
  await preference.handler("status", commandContext);
  await runner.emit({ type: "session_shutdown", reason: "reload" });
  await runner.emit({ type: "session_start" });
  await preference.handler("status", runner.createCommandContext());
  await preference.handler("enable", runner.createCommandContext());
  assert.deepEqual(notifications, [
    { message: "Insomniac notifications: enabled.", type: "info" },
    { message: "Insomniac notifications: disabled.", type: "info" },
    { message: "Insomniac notifications: disabled.", type: "info" },
    { message: "Insomniac notifications: disabled.", type: "info" },
    { message: "Insomniac notifications: enabled.", type: "info" },
  ]);
  sessionManager.appendUsage("cache_warm", "test", "test", {
    input: 100,
    output: 0,
    cacheRead: 0,
    cacheWrite: 0,
    totalTokens: 100,
    cost: { input: 0.123, output: 0, cacheRead: 0, cacheWrite: 0, total: 0.123 },
  });
  assert.match(render(), /~\$0\.123/u);
  process.env.TERM_PROGRAM = "Apple_Terminal";
  await runner.emit({ type: "agent_start" });
  assert.equal(children.length, 1);
  await once(children[0], "spawn");

  elapsed = 30_000;
  assert.match(render(), /awake/u);
  assert.ok(renders > 0);
  await runner.emit({ type: "agent_end", messages: [] });
  await runner.emit({ type: "agent_start" });
  assert.equal(children.length, 1);
  assert.equal(live(children[0].pid), true);
  await runner.emit({ type: "agent_settled", aborted: false });
  assert.match(render(), /can sleep/u);
  await gone(children[0]);

  for (let attempt = 0; attempt < 100 && desktopRequests.length === 0; attempt++) {
    await new Promise((complete) => setTimeout(complete, 5));
  }

  assert.equal(desktopRequests.length, 1, "qualified settlement submits one request");

  const expectedCommand = process.env.INSOMNIAC_TEST_TOOLS === "standard" ? standardPath : "/usr/bin/osascript";

  assert.equal(desktopRequests[0].command, expectedCommand);
  assert.deepEqual(
    expectedCommand === "/usr/bin/osascript" ? desktopRequests[0].args.slice(4) : desktopRequests[0].args,
    expectedCommand === "/usr/bin/osascript"
      ? ["--", "Pi run ended", `${basename(process.cwd())} · Demo review`]
      : [
          "-title",
          "\\Pi run ended",
          "-message",
          `\\${basename(process.cwd())} · Demo review`,
          "-activate",
          "com.mitchellh.ghostty",
        ],
  );
  assert.equal(notifications.filter(({ type }) => type === "warning").length, 0);
  await runner.emit({ type: "agent_start" });
  await once(children[1], "spawn");
  await runner.emit({ type: "session_shutdown", reason: "reload" });
  await gone(children[1]);
  assert.match(render(), /can sleep/u);
  await runner.emit({ type: "session_start" });
  await runner.emit({ type: "agent_start" });
  await once(children[2], "spawn");
  await runner.emit({ type: "session_shutdown", reason: "exit" });
  await gone(children[2]);
  assert.match(render(), /can sleep/u);
  // Use the real UI wrapper with controlled answers and deterministic attention timers.
  mock.timers.enable({ apis: ["setTimeout"] });

  const advance = async (milliseconds) => {
    elapsed += milliseconds;
    mock.timers.tick(milliseconds);
    await yieldToEventLoop();
  };

  const ui = runner.createContext().ui;

  const waitForNotice = async (count) => {
    for (let attempt = 0; attempt < 100 && desktopRequests.length < count; attempt++) await realDelay(5);
    assert.equal(desktopRequests.length, count);
  };

  for (const outcome of ["resolve", "dismiss", "abort", "reject"]) {
    await runner.emit({ type: "session_start" });
    await runner.emit({ type: "agent_start" });
    const child = children.at(-1);
    await once(child, "spawn");
    const controller = new AbortController();
    const eventsBefore = promptEvents.length;
    const confirmation = ui.confirm("Sensitive dialog", "Private command and response", { signal: controller.signal });

    const result = confirmation.then(
      (value) => value,
      (error) => error.message,
    );

    await yieldToEventLoop();
    assert.equal(promptEvents.at(-1).type, "ui_prompt_start");
    assert.equal(promptEvents.at(-1).kind, "confirm");
    await advance(9_999);

    if (outcome === "abort") controller.abort();
    else if (outcome === "reject") confirmations.at(-1).reject(new Error("fixture rejection"));
    else confirmations.at(-1).complete(outcome === "resolve");
    assert.equal(await result, outcome === "reject" ? "fixture rejection" : outcome === "resolve");
    await yieldToEventLoop();
    assert.deepEqual(
      promptEvents.slice(eventsBefore).map(({ type, kind }) => [type, kind]),
      [
        ["ui_prompt_start", "confirm"],
        ["ui_prompt_end", "confirm"],
      ],
    );
    await advance(1);
    await realDelay(5);
    assert.equal(desktopRequests.length, 1, `${outcome} cancels attention`);
    assert.equal(live(child.pid), true, "confirmation waits preserve sleep ownership");
    await runner.emit({ type: "agent_settled", aborted: outcome === "abort" });
    await gone(child);
    assert.match(render(), /can sleep/u);
  }

  await runner.emit({ type: "session_start" });
  await runner.emit({ type: "agent_start" });
  const waitingChild = children.at(-1);
  await once(waitingChild, "spawn");
  const eventsBefore = promptEvents.length;
  const outer = ui.confirm("Outer secret", "Do not send this command");
  const outerControl = confirmations.at(-1);
  const nested = ui.confirm("Nested secret", "Do not send this response");
  const nestedControl = confirmations.at(-1);
  await yieldToEventLoop();
  assert.equal(promptEvents.length, eventsBefore + 1, "nested prompts share the outer lifecycle");
  await advance(10_000);
  await waitForNotice(2);
  assert.equal(live(waitingChild.pid), true);
  const attention = desktopRequests.at(-1);
  assert.deepEqual(
    expectedCommand === "/usr/bin/osascript" ? attention.args.slice(4) : attention.args,
    expectedCommand === "/usr/bin/osascript"
      ? ["--", "Pi needs your attention", `${basename(process.cwd())} · Demo review`]
      : [
          "-title",
          "\\Pi needs your attention",
          "-message",
          `\\${basename(process.cwd())} · Demo review`,
          "-activate",
          "com.apple.Terminal",
        ],
  );
  outerControl.complete(true);
  assert.equal(await outer, true);
  await advance(20_000);
  assert.equal(promptEvents.length, eventsBefore + 1, "outer completion alone does not end the nested wait");
  assert.equal(desktopRequests.length, 2, "no recurring or nested attention attempt");
  nestedControl.complete(false);
  assert.equal(await nested, false);
  await yieldToEventLoop();
  assert.equal(promptEvents.at(-1).type, "ui_prompt_end");
  assert.equal(promptEvents.at(-1).title, "Outer secret");
  await runner.emit({ type: "agent_settled", aborted: true });
  await gone(waitingChild);
  await runner.emit({ type: "session_shutdown", reason: "exit" });
  assert.deepEqual(errors, []);
  console.log(
    "Pi confirmation integration passed: resolve, dismiss, abort, reject, nested lifecycle, attention, sleep ownership",
  );
  console.log(
    "Pi lifecycle integration passed: session cost, startup, duplicate/retry, settlement, reload, shutdown, real child termination",
  );
} finally {
  mock.timers.reset();

  for (const child of children) child.kill();
  footer?.dispose?.();
}
