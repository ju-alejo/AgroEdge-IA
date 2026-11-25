import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {DatabaseSync} from "node:sqlite";
import {validateImport} from "../lib/measurements.ts";
import {parseFile} from "../lib/transfer.ts";

const [snapshot,csv,xlsx,...sessions]=process.argv.slice(2);
if(!snapshot||!csv||!xlsx||!sessions.length) throw new Error("Uso: node scripts/verify-campaign-exports.mjs SQLITE CSV XLSX SESION [SESION ...]");

const db=new DatabaseSync(snapshot,{readOnly:true});
let stored;
try {
  stored=db.prepare("SELECT payload FROM real_readings WHERE origin='USB'").all()
    .map(({payload})=>validateImport(JSON.parse(payload)));
} finally { db.close(); }

const byId=new Map(stored.map(row=>[row.id,row]));
const countSessions=rows=>Object.fromEntries(sessions.map(session=>[session,rows.filter(row=>row.sessionId===session).length]));
const expected=countSessions(stored);
assert.ok(Object.values(expected).every(n=>n>0),"Alguna sesión no existe en SQLite.");
let csvIds;
for(const [path,format] of [[csv,"csv"],[xlsx,"xlsx"]]) {
  const rows=(await parseFile(await readFile(path),format)).map(validateImport);
  const ids=new Set(rows.map(row=>row.id));
  assert.equal(ids.size,rows.length,`IDs duplicados en ${format}.`);
  for(const row of rows) assert.deepEqual(row,byId.get(row.id),`Diferencia en ${format} para ${row.id}.`);
  const counts=countSessions(rows);
  assert.deepEqual(counts,expected,`Campaña incompleta en ${format}.`);
  if(csvIds) assert.deepEqual(ids,csvIds,"CSV y Excel contienen registros distintos.");
  else csvIds=ids;
  const campaignCount=Object.values(counts).reduce((total,n)=>total+n,0);
  console.log(JSON.stringify({format,total:rows.length,campaign:campaignCount,otherSessions:rows.length-campaignCount,sessions:counts}));
}
