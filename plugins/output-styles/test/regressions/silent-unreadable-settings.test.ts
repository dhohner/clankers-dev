// Defect: one catch covered the settings lock, the read, and the JSON parse of the persisted style
// name and returned "no stored selection" for all of them. A settings file held by a concurrent Pi
// settings write therefore looked exactly like a fresh installation: the stored style was dropped in
// silence, the session started with the built-in default, and the footer stayed empty.
import { join } from "node:path";
import { expect, it } from "vitest";
import { STYLES_DIR_NAME } from "../../src/pi/registration.js";
import { SETTINGS_FILE_NAME } from "../../src/storage/settings.js";
import { MemoryStylePersistence } from "../support/persistence.js";
import { registerHarnessHooks, agentDir, createHarness, styleFile, writeStyle } from "../support/extension-harness.js";

registerHarnessHooks();

it("reports the settings file instead of starting silently as a fresh installation", async () => {
  await writeStyle(join(agentDir, STYLES_DIR_NAME), "terse.md", styleFile("One-line answers.", "Answer in one line."));
  const settingsPath = join(agentDir, SETTINGS_FILE_NAME);
  const persistence = new MemoryStylePersistence();
  persistence.values.set(settingsPath, "terse");
  persistence.readFailures.set(settingsPath, "Lock file is already being held");
  const harness = createHarness({ trusted: false, persistence });

  await harness.start();

  expect(harness.notifications).toHaveLength(1);
  expect(harness.notifications[0]?.level).toBe("warning");
  expect(harness.notifications[0]?.message).toContain(`Output style settings could not be read: ${settingsPath} (`);
  expect(harness.notifications[0]?.message).toContain("The session continues.");
  // The session still starts, with the built-in default style and no footer entry.
  expect(harness.status()).toBeUndefined();
});
