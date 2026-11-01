import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { DesktopNotice } from "./notifications.ts";

export type NotificationExecutor = (
  file: string,
  args: string[],
  options: { timeout: number; maxBuffer: number },
) => Promise<void>;

// Display data stays in argv; no label becomes JavaScript or shell source.
const script = `function run(argv) {
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;
  app.displayNotification(argv[1], { withTitle: argv[0] });
}`;

const executeFile: NotificationExecutor = async (file, args, options) => {
  await promisify(execFile)(file, args, options);
};

export function createDesktopDelivery(
  execute: NotificationExecutor = executeFile,
): (notice: DesktopNotice) => Promise<void> {
  return async (notice) => {
    await execute("/usr/bin/osascript", ["-l", "JavaScript", "-e", script, "--", notice.title, notice.body], {
      timeout: 10_000,
      maxBuffer: 16_384,
    });
  };
}
