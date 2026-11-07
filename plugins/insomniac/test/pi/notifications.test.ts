import { registerAgentDirectoryHooks } from "../support/agent-directory.ts";
import { execFile } from "node:child_process";

import * as filesystem from "node:fs/promises";
import { promisify } from "node:util";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { installNotifications } from "../../src/pi/notifications.ts";
import { NotificationPreference } from "../../src/pi/notification-preference.ts";
import { expect, it, vi } from "vitest";
import { installInsomniac } from "../../index.ts";
import { createPiHost } from "../support/pi-host.ts";
import { createAssertionProcess } from "../support/assertion-process.ts";

registerAgentDirectoryHooks();

async function session() {
  const host = createPiHost();
  installInsomniac(host.pi, { platform: "linux" });
  await Promise.all(host.emit("session_start"));

  return host;
}

// Publishing only in memory loses assignments on restart; sharing state leaks changes into session B.
it("persists assignments across restart while other sessions retain their effective preference", async () => {
  const a = await session();
  const b = await session();
  await a.command("disable");
  await a.command("status");
  expect(a.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
  await b.command("status");
  expect(b.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
  const c = await session();
  await c.command();
  expect(c.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
  await c.command("enable");
  const d = await session();
  await d.command();
  expect(d.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
});

// A persistence error must not escape, publish a new value, or poison later assignments.
it("reports failed saves, retains effective and saved values, and permits a later assignment", async () => {
  const host = createPiHost();
  let fail = true;
  installNotifications(host.pi, {
    ...filesystem,
    rename: async (...args) => {
      if (fail) throw new Error("rename denied");
      await filesystem.rename(...args);
    },
  });
  await Promise.all(host.emit("session_start"));
  await host.command("disable");
  expect(host.notify).toHaveBeenLastCalledWith(expect.stringContaining("rename denied"), "error");
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
  expect(await readdir(process.env.PI_CODING_AGENT_DIR!)).toEqual([]);
  fail = false;
  await host.command("disable");
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
  expect(
    await new NotificationPreference(join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json")).read(),
  ).toEqual({ status: "saved", value: false });
});

// Parallel commands can otherwise commit and publish in reverse order.
it("serializes delayed assignments through commit and publication and repeats assignments", async () => {
  const host = createPiHost();
  let release!: () => void;
  let entered!: () => void;

  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });

  const started = new Promise<void>((resolve) => {
    entered = resolve;
  });

  const writes: string[] = [];
  const mkdir = vi.fn(filesystem.mkdir);
  installNotifications(host.pi, {
    ...filesystem,
    mkdir,
    writeFile: async (path, value, options) => {
      if (value !== "") writes.push(String(value));
      await filesystem.writeFile(path, value, options);
    },
    rename: async (...args) => {
      if (writes.length === 1) {
        entered();
        await gate;
      }

      await filesystem.rename(...args);
    },
  });
  await Promise.all(host.emit("session_start"));
  const first = host.command("disable");
  await started;
  const second = host.command("enable");
  await Promise.resolve();
  const beforeCommit = [...writes];
  const attemptsBeforeCommit = mkdir.mock.calls.length;
  const messagesBeforeCommit = host.notify.mock.calls.length;
  release();
  await Promise.all([first, second]);
  expect(beforeCommit).toEqual(["false"]);
  expect(attemptsBeforeCommit).toBe(1);
  expect(messagesBeforeCommit).toBe(0);
  await host.command("status");
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
  expect(
    await new NotificationPreference(join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json")).read(),
  ).toEqual({ status: "saved", value: true });
  await host.command("enable");
  expect(
    await new NotificationPreference(join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json")).read(),
  ).toEqual({ status: "saved", value: true });
});

// A late save from a disposed session must not publish into its replacement.
it.each([false, true])("contains a pending save after session replacement (failure: %s)", async (fail) => {
  const host = createPiHost();
  let release!: () => void;
  let entered!: () => void;

  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });

  const started = new Promise<void>((resolve) => {
    entered = resolve;
  });

  installNotifications(host.pi, {
    ...filesystem,
    rename: async (...args) => {
      entered();
      await gate;

      if (fail) throw new Error("late save failure");
      await filesystem.rename(...args);
    },
  });
  await Promise.all(host.emit("session_start"));
  const old = host.command("disable");
  await started;
  const queued = host.command("enable");
  host.emit("session_shutdown");
  await Promise.all(host.emit("session_start"));
  release();
  await Promise.all([old, queued]);
  expect(host.notify).not.toHaveBeenCalled();
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
  const future = await session();
  await future.command();
  expect(future.notify).toHaveBeenLastCalledWith(`Insomniac notifications: ${fail ? "enabled" : "disabled"}.`, "info");
});

// Damaged content must disable notifications, report the failure, and reset to a valid disabled value.
it.each(["broken", "null", "{}", '"false"', "0", ""])("recovers from damaged preference %j", async (content) => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json");
  await filesystem.writeFile(path, content);
  const host = await session();
  expect(host.notify).toHaveBeenCalledWith(expect.stringContaining("Read notification preference"), "error");
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
  expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: false });
  const restarted = await session();
  expect(restarted.notify).not.toHaveBeenCalled();
  await restarted.command("enable");
  expect(restarted.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
});

// Unreadable content is not absence; a failed recovery must leave Pi and later commands usable.
it.each([false, true])("disables and reports unreadable storage when reset failure is %s", async (resetFails) => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json");
  await filesystem.writeFile(path, "true");
  const host = createPiHost();
  let fail = resetFails;
  installNotifications(host.pi, {
    ...filesystem,
    readFile: async () => {
      throw Object.assign(new Error("read denied"), { code: "EACCES" });
    },
    rename: async (...args) => {
      if (fail) throw new Error("reset denied");
      await filesystem.rename(...args);
    },
  });
  await Promise.all(host.emit("session_start"));
  expect(host.notify).toHaveBeenCalledWith(expect.stringContaining("Read notification preference"), "error");

  if (resetFails) expect(host.notify).toHaveBeenLastCalledWith(expect.stringContaining("reset denied"), "error");
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
  expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: resetFails });
  fail = false;
  await host.command("disable");
  expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: false });
});

// Errors after replacement are warnings, and must not roll back the effective committed value.
it("publishes a committed assignment even when directory cleanup fails", async () => {
  const host = createPiHost();
  const directory = process.env.PI_CODING_AGENT_DIR!;
  installNotifications(host.pi, {
    ...filesystem,
    open: async (path, ...args) => {
      const file = await filesystem.open(path, ...args);

      if (path === directory) {
        const close = file.close.bind(file);
        file.close = async () => {
          await close();
          throw new Error("directory cleanup failed");
        };
      }

      return file;
    },
  });
  await Promise.all(host.emit("session_start"));
  await host.command("disable");
  expect(host.notify).toHaveBeenCalledWith(expect.stringContaining("directory cleanup failed"), "warning");
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
  expect(await new NotificationPreference(join(directory, "insomniac-notifications.json")).read()).toEqual({
    status: "saved",
    value: false,
  });
});

// Agent directory isolation must apply to reads and writes even before its directory exists.
it("creates storage only on assignment in the selected agent directory", async () => {
  const parent = process.env.PI_CODING_AGENT_DIR!;
  const directory = join(parent, "new-agent");
  vi.stubEnv("PI_CODING_AGENT_DIR", directory);
  const host = await session();
  await host.command("status");
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
  expect(await readdir(parent)).toEqual([]);
  await host.command("disable");
  expect(await new NotificationPreference(join(directory, "insomniac-notifications.json")).read()).toEqual({
    status: "saved",
    value: false,
  });
  expect((await filesystem.stat(join(directory, "insomniac-notifications.json"))).mode & 0o777).toBe(0o600);
});

// Invalid operations must not silently look like successful status or assignments.
it("reports command syntax for invalid arguments without changing storage", async () => {
  const host = await session();
  await host.command("toggle");
  expect(host.notify).toHaveBeenLastCalledWith("Usage: /insomniac-notifications [status|enable|disable]", "error");
  expect(await readdir(process.env.PI_CODING_AGENT_DIR!)).toEqual([]);
  await host.command("  disable  ");
  await host.command("status");
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
});

// Preference commands must leave the footer and owned sleep assertion working through save failures.
it("preserves footer output and sleep ownership during successful and failed changes", async () => {
  const host = createPiHost();
  const assertion = createAssertionProcess();
  installInsomniac(host.pi, { platform: "darwin", spawn: assertion.spawn });
  await Promise.all(host.emit("session_start"));
  host.emit("agent_start");
  expect(assertion.children).toHaveLength(1);
  assertion.children[0].emit("spawn");
  const before = host.render();
  expect(before).toContain("☕ awake");
  await host.command("disable");
  expect(host.render()).toBe(before);
  const directory = process.env.PI_CODING_AGENT_DIR!;
  await filesystem.chmod(directory, 0o500);

  try {
    await host.command("enable");
    expect(host.notify).toHaveBeenLastCalledWith(expect.stringContaining("Could not save"), "error");
    expect(host.render()).toBe(before);
    expect(assertion.children[0].kill).not.toHaveBeenCalled();
    await host.command();
    expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
    host.emit("agent_settled");
    expect(assertion.children[0].kill).toHaveBeenCalledOnce();
    expect(host.render()).toContain("💤 can sleep");
  } finally {
    await filesystem.chmod(directory, 0o700);
    host.emit("session_shutdown");
  }
});

// A status query must not rewrite an existing preference, even with the same saved value.
it("queries an existing saved preference without writing it", async () => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json");
  await filesystem.writeFile(path, "false");
  const writeFile = vi.fn(filesystem.writeFile);
  const host = createPiHost();
  installNotifications(host.pi, { ...filesystem, writeFile });
  await Promise.all(host.emit("session_start"));
  await host.command("status");
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
  expect(writeFile).not.toHaveBeenCalled();
});

// Recovery and explicit commands must fail without removing ACLs or publishing unsaved assignments.
it.skipIf(process.platform !== "darwin").each(["read", "write"])(
  "retains a macOS ACL denying %s through startup and command failure",
  async (denied) => {
    const execute = promisify(execFile);
    const path = join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json");
    const acl = `everyone deny ${denied}`;
    await filesystem.writeFile(path, "true", { mode: 0o600 });
    await execute("/bin/chmod", ["+a", acl, path]);
    const host = createPiHost();
    installInsomniac(host.pi, { platform: "linux" });

    try {
      await Promise.all(host.emit("session_start"));

      if (denied === "read") {
        expect(host.notify).toHaveBeenCalledWith(expect.stringContaining("Read notification preference"), "error");
        expect(host.notify).toHaveBeenLastCalledWith(expect.stringContaining("ACL"), "error");
      } else {
        expect(host.notify).not.toHaveBeenCalled();
      }

      await host.command("disable");
      expect(host.notify).toHaveBeenLastCalledWith(expect.stringContaining("ACL"), "error");
      await host.command();
      expect(host.notify).toHaveBeenLastCalledWith(
        `Insomniac notifications: ${denied === "read" ? "disabled" : "enabled"}.`,
        "info",
      );
      expect((await execute("/bin/ls", ["-lde", path])).stdout).toContain(acl);
      await execute("/bin/chmod", ["-N", path]);
      expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: true });
      await host.command("disable");
      expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
      expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: false });
    } finally {
      await execute("/bin/chmod", ["-N", path]);
      host.emit("session_shutdown");
    }
  },
);

// Ownership errors during assignments or startup recovery must not publish or persist an unsaved value.
it.each(["true", "broken"])(
  "retains saved metadata and effective state after ownership failure with %s",
  async (content) => {
    const path = join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json");
    await filesystem.writeFile(path, content, { mode: 0o640 });
    const before = await filesystem.stat(path);
    const host = createPiHost();
    let fail = true;
    installNotifications(host.pi, {
      ...filesystem,
      chown: async (...args) => {
        if (fail) throw new Error("ownership denied");
        await filesystem.chown(...args);
      },
    });

    await Promise.all(host.emit("session_start"));

    if (content === "broken") {
      expect(host.notify).toHaveBeenLastCalledWith(expect.stringContaining("ownership denied"), "error");
    }

    await host.command("disable");
    expect(host.notify).toHaveBeenLastCalledWith(expect.stringContaining("ownership denied"), "error");
    await host.command("status");
    expect(host.notify).toHaveBeenLastCalledWith(
      `Insomniac notifications: ${content === "true" ? "enabled" : "disabled"}.`,
      "info",
    );
    expect(await filesystem.readFile(path, "utf8")).toBe(content);
    const after = await filesystem.stat(path);
    expect({ uid: after.uid, gid: after.gid, mode: after.mode }).toEqual({
      uid: before.uid,
      gid: before.gid,
      mode: before.mode,
    });
    fail = false;
    await host.command("disable");
    expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: disabled.", "info");
    expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: false });
  },
);

// Defaulting to disabled or writing during a status query breaks a fresh installation.
it("reports enabled without creating storage for an absent preference", async () => {
  const host = await session();
  await host.command();
  expect(host.notify).toHaveBeenLastCalledWith("Insomniac notifications: enabled.", "info");
  expect(await readdir(process.env.PI_CODING_AGENT_DIR!)).toEqual([]);
});
