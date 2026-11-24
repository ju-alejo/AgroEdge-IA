import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {DatabaseSync} from "node:sqlite";
import {validateImport} from "../lib/measurements.ts";
import {parseFile} from "../lib/transfer.ts";

const [snapshot,csv,xlsx,session]=process.argv.slice(2);
if(!snapshot||!csv||!xlsx||!session) throw new Error("Uso: node scripts/verify-campaign-exports.mjs SQLITE CSV XLSX SESION");

const db=new DatabaseSync(snapshot,{readOnly:true});
let stored;
try {
  stored=db.prepare("SELECT payload FROM real_readings WHERE origin='USB'").all()
    .map(({payload})=>validateImport(JSON.parse(payload)));
} finally { db.close(); }

const byId=new Map(stored.map(row=>[row.id,row]));
const campaignCount=stored.filter(row=>row.sessionId===session).length;
assert.ok(campaignCount>0,"La sesión no existe en SQLite.");
for(const [path,format] of [[csv,"csv"],[xlsx,"xlsx"]]) {
  const rows=(await parseFile(await readFile(path),format)).map(validateImport);
  assert.equal(new Set(rows.map(row=>row.id)).size,rows.length,`IDs duplicados en ${format}.`);
  for(const row of rows) assert.deepEqual(row,byId.get(row.id),`Diferencia en ${format} para ${row.id}.`);
  assert.equal(rows.filter(row=>row.sessionId===session).length,campaignCount,`Campaña incompleta en ${format}.`);
  console.log(JSON.stringify({format,total:rows.length,campaign:campaignCount,otherSessions:rows.length-campaignCount}));
}
