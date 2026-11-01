import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { join } from "node:path";
import { NotificationPreference, type PreferenceFileSystem } from "./notification-preference.ts";

interface NotificationSession {
  enabled: boolean;
  store: NotificationPreference;
  tail: Promise<void>;
}

export function installNotifications(pi: ExtensionAPI, filesystem?: PreferenceFileSystem): void {
  let current: NotificationSession | undefined;
  pi.on("session_start", async (_event, ctx) => {
    const session: NotificationSession = {
      enabled: true,
      store: new NotificationPreference(join(getAgentDir(), "insomniac-notifications.json"), filesystem),
      tail: Promise.resolve(),
    };

    current = session;
    session.tail = session.store.read().then(async (value) => {
      if (current !== session) return;
      session.enabled = value.status === "absent" || (value.status === "saved" && value.value);

      if (value.status === "failed") {
        ctx.ui.notify(`${value.error.message}; notifications disabled.`, "error");

        try {
          const { warning } = await session.store.write(false);

          if (current === session && warning) ctx.ui.notify(warning.message, "warning");
        } catch (error) {
          if (current === session) ctx.ui.notify(`Could not reset Insomniac notifications: ${String(error)}`, "error");
        }
      }

      return undefined;
    });
    await session.tail;
  });
  pi.on("session_shutdown", () => {
    current = undefined;
  });
  pi.registerCommand("insomniac-notifications", {
    description: "Inspect or change notifications: status, enable, disable",
    handler: (input, ctx) => {
      const args = input.trim();
      const session = current;

      if (!session) return Promise.resolve();

      const result = session.tail.then(async () => {
        if (current !== session) return;

        if (!["", "status", "enable", "disable"].includes(args)) {
          ctx.ui.notify("Usage: /insomniac-notifications [status|enable|disable]", "error");

          return;
        }

        if (args === "enable" || args === "disable") {
          const value = args === "enable";

          try {
            const { warning } = await session.store.write(value);

            if (current !== session) return;
            session.enabled = value;

            if (warning) ctx.ui.notify(warning.message, "warning");
          } catch (error) {
            if (current === session) ctx.ui.notify(`Could not save Insomniac notifications: ${String(error)}`, "error");

            return;
          }
        }

        ctx.ui.notify(`Insomniac notifications: ${session.enabled ? "enabled" : "disabled"}.`, "info");

        return undefined;
      });

      session.tail = result.catch(() => undefined);

      return result;
    },
  });
}
