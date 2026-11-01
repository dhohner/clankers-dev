import { runInNewContext } from "node:vm";
import { expect, it, vi } from "vitest";
import { createDesktopDelivery } from "../../src/pi/desktop-notification.ts";

// Interpolating labels into script source or a shell allows data to become code.
it("passes labels as arguments to a fixed script and requests only standard notification presentation", async () => {
  const execute = vi.fn().mockResolvedValue(undefined);
  const notice = { title: "Pi run ended", body: "雪\n'\"; $(touch /tmp/never)\u001b\u0000" };
  await createDesktopDelivery(execute)(notice);
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
