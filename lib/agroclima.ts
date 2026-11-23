import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import archived from "../examples/r5/boletin-verificado.json";

export type Edition = {
  revision: string; published: string; title: string; status: string; summary: string;
  source: string; url: string; first_seen: string; last_seen: string; live_seen: string | null;
};
export type ClimateFeed = {
  bundled: boolean;
  editions: Edition[];
  lastRun: { at: string; method: string; outcome: string; detail: string } | null;
};

export function getClimateFeed(): ClimateFeed {
  const file = resolve(process.env.AGROEDGE_R5_DIR || "data", "agroclima.sqlite");
  if (!existsSync(file)) return { editions: [archived], bundled: true, lastRun: null };
  const db = new DatabaseSync(file, { readOnly: true });
  try {
    db.exec("PRAGMA busy_timeout=3000; BEGIN");
    if (db.prepare("PRAGMA application_id").get()?.application_id !== 0x41475235)
      throw new Error("El archivo agroclimático tiene un formato desconocido.");
    const editions = db.prepare(
      "SELECT revision,published,title,status,summary,source,url,first_seen,last_seen,live_seen " +
      "FROM editions ORDER BY published DESC,last_seen DESC,revision LIMIT 12"
    ).all() as Edition[];
    const lastRun = db.prepare("SELECT at,method,outcome,detail FROM runs ORDER BY id DESC LIMIT 1").get();
    return { editions: editions.length ? editions : [archived], bundled: !editions.length,
      lastRun: (lastRun as ClimateFeed["lastRun"]) ?? null };
  } finally { db.close(); }
}
