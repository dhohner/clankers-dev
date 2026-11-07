import { registerAgentDirectoryHooks } from "../support/agent-directory.ts";
import { execFile } from "node:child_process";

import * as filesystem from "node:fs/promises";
import { promisify } from "node:util";
import { join } from "node:path";
import { expect, it } from "vitest";
import { NotificationPreference } from "../../src/pi/notification-preference.ts";

registerAgentDirectoryHooks();

// Absence must remain distinguishable from a saved value and a read failure.
it("distinguishes an absent preference from valid values and failed reads", async () => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "preference.json");
  const store = new NotificationPreference(path);
  expect(await store.read()).toEqual({ status: "absent" });
  await filesystem.writeFile(path, "false");
  expect(await store.read()).toEqual({ status: "saved", value: false });
  await filesystem.writeFile(path, "null");
  expect(await store.read()).toEqual({ status: "failed", error: expect.any(Error) });
});

// Replacing an inode must not widen its access or touch Pi's unrelated settings.
it("preserves existing permissions and unrelated settings", async () => {
  const directory = process.env.PI_CODING_AGENT_DIR!;
  const path = join(directory, "preference.json");
  const settings = join(directory, "settings.json");
  await filesystem.writeFile(settings, '{"unrelated":true}');
  await filesystem.writeFile(path, "true", { mode: 0o600 });
  const store = new NotificationPreference(path);
  await store.write(false);
  expect((await filesystem.stat(path)).mode & 0o777).toBe(0o600);
  expect(await store.read()).toEqual({ status: "saved", value: false });
  expect(await filesystem.readFile(settings, "utf8")).toBe('{"unrelated":true}');
});

const ownerGroup = process.getgid?.();

const otherGroup = process.getgroups?.().find((group) => group !== ownerGroup);

// A replacement inheriting its directory's group can expose group-readable preferences to different principals.
it.skipIf(ownerGroup === undefined || otherGroup === undefined)(
  "preserves the saved owner and group when the directory has a different group",
  async () => {
    if (ownerGroup === undefined || otherGroup === undefined) throw new Error("Two process groups are required");
    const directory = process.env.PI_CODING_AGENT_DIR!;
    const originalDirectory = await filesystem.stat(directory);
    const path = join(directory, "preference.json");
    await filesystem.chown(directory, originalDirectory.uid, otherGroup);

    try {
      await filesystem.writeFile(path, "true", { mode: 0o640 });
      await filesystem.chown(path, originalDirectory.uid, ownerGroup);
      const before = await filesystem.stat(path);
      expect(before.gid).not.toBe((await filesystem.stat(directory)).gid);
      const store = new NotificationPreference(path);
      await expect(store.write(false)).resolves.toEqual({});
      const after = await filesystem.stat(path);
      expect({ uid: after.uid, gid: after.gid, mode: after.mode & 0o777 }).toEqual({
        uid: before.uid,
        gid: before.gid,
        mode: 0o640,
      });
      expect(await store.read()).toEqual({ status: "saved", value: false });
    } finally {
      await filesystem.chown(directory, originalDirectory.uid, originalDirectory.gid);
    }
  },
);

// Failure to restore ownership must leave both the saved data and access metadata intact.
it("retains content and ownership after a failed ownership change and permits a later save", async () => {
  const directory = process.env.PI_CODING_AGENT_DIR!;
  const path = join(directory, "preference.json");
  await filesystem.writeFile(path, "true", { mode: 0o640 });
  const before = await filesystem.stat(path);
  let fail = true;
  let contentsAtFailure: string | undefined;

  const store = new NotificationPreference(path, {
    ...filesystem,
    chown: async (file, uid, gid) => {
      if (fail) {
        contentsAtFailure = await filesystem.readFile(file, "utf8");
        throw new Error("ownership denied");
      }

      await filesystem.chown(file, uid, gid);
    },
  });

  await expect(store.write(false)).rejects.toThrow("ownership denied");
  expect(contentsAtFailure).toBe("");
  expect(await store.read()).toEqual({ status: "saved", value: true });
  const after = await filesystem.stat(path);
  expect({ uid: after.uid, gid: after.gid, mode: after.mode }).toEqual({
    uid: before.uid,
    gid: before.gid,
    mode: before.mode,
  });
  expect(await filesystem.readdir(directory)).toEqual(["preference.json"]);
  fail = false;
  await store.write(false);
  expect(await store.read()).toEqual({ status: "saved", value: false });
});

// Replacing a file with an ACL must not remove access restrictions that mode bits cannot represent.
it.skipIf(process.platform !== "darwin").each([false, true])(
  "retains a saved file with a macOS deny read ACL when assignment fails (xattr: %s)",
  async (withXattr) => {
    const execute = promisify(execFile);
    const path = join(process.env.PI_CODING_AGENT_DIR!, "preference.json");
    const store = new NotificationPreference(path);
    await filesystem.writeFile(path, "true", { mode: 0o600 });

    if (withXattr) await execute("/usr/bin/xattr", ["-w", "com.insomniac.test", "metadata", path]);
    await execute("/bin/chmod", ["+a", "everyone deny read", path]);

    try {
      expect(await store.read()).toMatchObject({ status: "failed", error: { cause: { code: "EACCES" } } });
      await expect(store.write(false)).rejects.toThrow("ACL");
      expect((await execute("/bin/ls", ["-lde", path])).stdout).toContain("everyone deny read");
      expect(await store.read()).toMatchObject({ status: "failed", error: { cause: { code: "EACCES" } } });
    } finally {
      await execute("/bin/chmod", ["-N", path]);
    }

    expect(await store.read()).toEqual({ status: "saved", value: true });
  },
);

// An inherited ACL on the replacement can grant access absent from the original file.
it.skipIf(process.platform !== "darwin")(
  "retains the original when the temporary file inherits a macOS ACL",
  async () => {
    const execute = promisify(execFile);
    const directory = process.env.PI_CODING_AGENT_DIR!;
    const path = join(directory, "preference.json");
    await filesystem.writeFile(path, "true", { mode: 0o600 });
    await execute("/bin/chmod", ["+a", "everyone allow read,file_inherit", directory]);

    const temporaryContents: string[] = [];

    const store = new NotificationPreference(path, {
      ...filesystem,
      writeFile: async (file, ...args) => {
        await filesystem.writeFile(file, ...args);
        temporaryContents.push(await filesystem.readFile(file, "utf8"));
      },
    });

    try {
      await expect(store.write(false)).rejects.toThrow("ACL");
      expect(temporaryContents).toEqual([""]);
      expect((await execute("/bin/ls", ["-lde", path])).stdout).not.toContain("everyone allow read");
      expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: true });
      expect(await filesystem.readdir(directory)).toEqual(["preference.json"]);
    } finally {
      await execute("/bin/chmod", ["-N", directory]);
      await execute("/bin/chmod", ["-N", path]);
    }
  },
);

// An ACL inspection error must stop replacement and report the operation that failed.
it.skipIf(process.platform !== "darwin")(
  "retains the saved value when ACL inspection of the temporary file fails",
  async () => {
    const execute = promisify(execFile);
    const path = join(process.env.PI_CODING_AGENT_DIR!, "preference.json");
    await filesystem.writeFile(path, "true", { mode: 0o600 });
    let temporary = "";

    const store = new NotificationPreference(path, {
      ...filesystem,
      writeFile: async (file, ...args) => {
        await filesystem.writeFile(file, ...args);
        temporary = String(file);
        await execute("/bin/chmod", ["+a", "everyone deny readsecurity", temporary]);
      },
    });

    try {
      await expect(store.write(false)).rejects.toThrow("Inspect macOS ACL");
      expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: true });
    } finally {
      if (temporary) {
        await execute("/bin/chmod", ["-N", temporary]).catch(() => undefined);
        await filesystem.rm(temporary, { force: true });
      }
    }
  },
);

// ACL inspection must treat filenames as inert data and mask their embedded line breaks.
it.skipIf(process.platform !== "darwin")(
  "saves a preference whose filename contains a fake ACL line and shell syntax",
  async () => {
    const directory = process.env.PI_CODING_AGENT_DIR!;
    const name = "preference\n 0: everyone deny read;$(printf marker).json";
    const path = join(directory, name);
    await filesystem.writeFile(path, "true", { mode: 0o600 });
    const store = new NotificationPreference(path);
    await expect(store.write(false)).resolves.toEqual({});
    expect(await store.read()).toEqual({ status: "saved", value: false });
    expect(await filesystem.readdir(directory)).toEqual([name]);
  },
);

// A rename before flushing the temporary file can acknowledge data not committed to storage.
it("flushes the saved data before replacement and keeps the old value on sync failure", async () => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "preference.json");
  await filesystem.writeFile(path, "true");

  const store = new NotificationPreference(path, {
    ...filesystem,
    open: async (...args) => {
      const file = await filesystem.open(...args);
      file.sync = async () => {
        throw new Error("sync failed");
      };

      return file;
    },
  });

  await expect(store.write(false)).rejects.toThrow("sync failed");
  expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: true });
});

// A cleanup failure must not hide the failed save or lose its path and original cause.
it("reports both persistence and cleanup failures without replacing the saved value", async () => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "preference.json");
  await filesystem.writeFile(path, "true");

  const store = new NotificationPreference(path, {
    ...filesystem,
    writeFile: async () => {
      throw new Error("disk full");
    },
    rm: async () => {
      throw new Error("cleanup denied");
    },
  });

  let failure: unknown;

  try {
    await store.write(false);
  } catch (error) {
    failure = error;
  }

  expect(failure).toBeInstanceOf(Error);

  if (!(failure instanceof Error)) throw new Error("Expected save failure");
  expect(failure.message).toContain(path);
  expect(failure.message).toContain("disk full");
  expect(failure.message).toContain("cleanup denied");
  expect(failure.cause).toBeInstanceOf(AggregateError);
  expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: true });
});

// Writing directly to the destination destroys the last durable value after a partial write.
it("retains the saved preference when writing fails after partial output", async () => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "insomniac-notifications.json");
  await filesystem.writeFile(path, "true", { mode: 0o600 });

  const store = new NotificationPreference(path, {
    ...filesystem,
    writeFile: async (file) => {
      await filesystem.writeFile(file, "partial");
      throw new Error("disk full");
    },
  });

  await expect(store.write(false)).rejects.toThrow("disk full");
  expect(await new NotificationPreference(path).read()).toEqual({ status: "saved", value: true });
  expect(await filesystem.readdir(process.env.PI_CODING_AGENT_DIR!)).toEqual(["insomniac-notifications.json"]);
});
