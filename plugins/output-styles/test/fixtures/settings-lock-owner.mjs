import { once } from "node:events";
import { readFile, writeFile } from "node:fs/promises";
import lockfile from "proper-lockfile";

const [path] = process.argv.slice(2);

const release = await lockfile.lock(path, { realpath: false });

const commit = once(process, "message");

process.send("locked");

try {
  await commit;
  const settings = JSON.parse(await readFile(path, "utf8"));
  settings.theme = "dark";
  await writeFile(path, JSON.stringify(settings), "utf8");
} finally {
  await release();
}

process.send("committed");

process.disconnect();
