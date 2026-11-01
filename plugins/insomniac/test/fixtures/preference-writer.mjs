import * as filesystem from "node:fs/promises";
import { NotificationPreference } from "../../src/pi/notification-preference.ts";

const [path, value] = process.argv.slice(2);

const replace = new Promise((resolve) => process.once("message", resolve));

const store = new NotificationPreference(path, {
  ...filesystem,
  rename: async (...args) => {
    process.send("prepared");
    await replace;
    await filesystem.rename(...args);
    process.send("committed");
  },
});

await store.write(value === "true");

process.disconnect();
