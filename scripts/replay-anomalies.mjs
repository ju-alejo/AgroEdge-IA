import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import {join} from "node:path";
import {DatabaseSync} from "node:sqlite";
import {parse} from "csv-parse/sync";
import {detectorVersion, legacyAnomalies, referenceAgeMs, referenceSize, regimeChangeIssue} from "../lib/anomaly.ts";
import {Store} from "../lib/store.ts";

const [snapshot, v1, output]=process.argv.slice(2);
if (!snapshot || !v1 || !output) throw new Error("Uso: node scripts/replay-anomalies.mjs SQLITE DIRECTORIO_V1 NUEVO_DIRECTORIO_V2");

const hash=value=>createHash("sha256").update(value).digest("hex");
const read=(dir,name)=>readFile(join(dir,name));
const sourceSummary=await read(v1,"resumen.json");
const sourceManifest=JSON.parse(sourceSummary);
const sourceCsv=await read(v1,"mediciones.csv");
const snapshotSha=hash(await readFile(snapshot));
assert.equal(snapshotSha,sourceManifest.sqlite_sha256,"La copia SQLite no coincide con el manifiesto v1.");
const digests=new Map((await read(v1,"SHA256SUMS.txt")).toString().trim().split(/\r?\n/).map(line=>line.split("  ").reverse()));
assert.equal(hash(sourceCsv),digests.get("mediciones.csv"),"El CSV v1 no coincide con su huella.");
assert.equal(hash(sourceSummary),digests.get("resumen.json"),"El resumen v1 no coincide con su huella.");
const original=parse(sourceCsv,{bom:true,columns:true});
const database=new DatabaseSync(snapshot,{readOnly:true});
let captured;
try {
  captured=database.prepare("SELECT payload FROM real_readings WHERE origin='USB' AND station=? AND session=? ORDER BY seq")
    .all(sourceManifest.station,sourceManifest.session).map(row=>JSON.parse(row.payload));
} finally { database.close(); }
assert.equal(captured.length,original.length);

const replay=new Store(":memory:");
const formerValid=[], oldTail=[], results=[], resets=[], issueGroups={}, phaseCounts={};
const total={original_anomaly:0,revised_anomaly:0,revised_no_statistical_flag:0,timing_uncertain:0};
try {
  for (const [i, row] of captured.entries()) {
    const prior=original[i], now=Date.parse(row.receivedAt), stamp=Date.parse(row.acquiredAt);
    assert.equal(prior.reading_id,row.id);
    assert.equal(prior.quality_original,row.quality);
    assert.deepEqual(JSON.parse(prior.issues_json),row.issues);
    assert.equal(prior.rain_observation,"");
    assert.equal(prior.ml_split,"unassigned_pilot");
    const physical=row.quality==="VALID"||row.quality==="ANOMALY";
    let revised=row;
    if (physical) {
      const oldReference=formerValid.filter(r=>r.stamp>=stamp-referenceAgeMs&&r.stamp<=stamp)
        .slice(-referenceSize).reverse().map(r=>r.row);
      assert.deepEqual(legacyAnomalies(row,oldReference),row.issues,`La regla original difiere en la secuencia ${row.sequence}.`);
      if (row.quality==="VALID") {
        formerValid.push({row,stamp});
        oldTail.length=0;
      } else {
        const first=oldReference.at(-1)?.sequence??null, last=oldReference[0]?.sequence??null;
        oldTail.push({sequence:row.sequence,receipt:row.receivedAt,first,last});
        const group=row.issues.map(issue=>issue.split(" se apartó ")[0]).join(" + ");
        issueGroups[group]=(issueGroups[group]??0)+1;
      }
      const {schemaVersion,id,stationId,sessionId,sequence,temperature,humidity,pressure,classification}=row;
      const packet={schemaVersion,id,stationId,sessionId,sequence,temperature,humidity,pressure,
        acquiredAt:row.timeSource==="DEVICE"?row.acquiredAt:null};
      if (classification) {
        const {inferenceTimeSource,...wire}=classification;
        packet.classification=inferenceTimeSource==="RECEIPT"?{...wire,inferredAt:undefined}:wire;
      }
      revised=replay.ingest(packet,"USB",undefined,now).reading;
    } else {
      // The original raw out-of-range value cannot be recovered from SQLite's normalized null.
      replay.import([row]);
    }

    const changed=revised.issues.includes(regimeChangeIssue);
    const uncertain=prior.receipt_timing_uncertain==="1";
    const assessment=changed?"REGIME_CHANGE":revised.quality==="ANOMALY"?"STATISTICAL_OUTLIER":
      revised.quality==="VALID"?"NO_STATISTICAL_FLAG":revised.quality;
    if (changed) resets.push({sequence:row.sequence,receipt_utc:row.receivedAt,phase:prior.phase});
    const reasons=["UNASSIGNED_PILOT",...(uncertain?["RECEIPT_UNCERTAIN"]:[]),
      ...(["transfer","settling"].includes(prior.phase)?["TRANSFER_OR_SETTLING"]:[]),
      ...(assessment==="NO_STATISTICAL_FLAG"?[]:[assessment])];
    results.push({...prior,quality_revised:revised.quality,assessment_revised:assessment,
      issues_revised_json:JSON.stringify(revised.issues),review_reasons_json:JSON.stringify(reasons),detector_version:detectorVersion});
    const phase=phaseCounts[prior.phase]??={original:{},revised:{}};
    phase.original[row.quality]=(phase.original[row.quality]??0)+1;
    phase.revised[assessment]=(phase.revised[assessment]??0)+1;
    total.original_anomaly+=Number(row.quality==="ANOMALY");
    total.revised_anomaly+=Number(revised.quality==="ANOMALY");
    total.revised_no_statistical_flag+=Number(assessment==="NO_STATISTICAL_FLAG");
    total.timing_uncertain+=Number(uncertain);
  }
} finally { replay.close(); }

const legacyTail=oldTail.length?{rows:oldTail.length,start:oldTail[0],end:oldTail.at(-1),
  frozen_reference:oldTail.every(r=>r.first===oldTail[0].first&&r.last===oldTail[0].last)}:null;
const summary={schema:"agroedge.usb-observational.v2",detector:detectorVersion,campaign:sourceManifest.campaign,
  rows:results.length,sqlite_sha256:snapshotSha,v1_csv_sha256:hash(sourceCsv),v1_manifest_sha256:hash(sourceSummary),
  observed_move_utc:sourceManifest.observed_move_utc,provisional_settling_end_utc:sourceManifest.provisional_settling_end_utc,
  legacy_issue_groups:issueGroups,legacy_tail:legacyTail,regime_changes:resets,counts:total,by_phase:phaseCounts,
  independent_rain_labels:0,ml_split:"unassigned_pilot"};
const fields=Object.keys(results[0]), escape=value=>`"${String(value).replaceAll('"','""')}"`;
const csv="\ufeff"+[fields.map(escape).join(","),...results.map(row=>fields.map(k=>escape(row[k])).join(","))].join("\r\n")+"\r\n";
const manifest=JSON.stringify(summary,null,2)+"\n";
await mkdir(output);
await writeFile(join(output,"mediciones.csv"),csv,{flag:"wx"});
await writeFile(join(output,"resumen.json"),manifest,{flag:"wx"});
await writeFile(join(output,"SHA256SUMS.txt"),`${hash(csv)}  mediciones.csv\n${hash(manifest)}  resumen.json\n`,{flag:"wx"});
console.log(manifest);
