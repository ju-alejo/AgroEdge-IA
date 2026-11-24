import assert from "node:assert/strict";
import {mkdtempSync, rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import test from "node:test";
import {regimeChangeIssue} from "../lib/anomaly.ts";
import {Store} from "../lib/store.ts";

const start=Date.parse("2026-11-23T23:00:00Z");
const greenhouse={temperature:22,humidity:63,pressure:736};
const outdoor={temperature:15,humidity:83,pressure:736.1};
function ingest(store, sequence, values=greenhouse, now=start+sequence*5000, sessionId="qa-boot") {
  const payload={schemaVersion:1,stationId:"QA-REGIME",sessionId,sequence,...values};
  return store.ingest(payload,"USB",undefined,now).reading;
}
function baseline(store) {
  for(let i=1;i<=30;i++) assert.equal(ingest(store,i).quality,"VALID");
}

test("a sustained joint shift seeds a new reference without rewriting earlier flags, including after reopening",()=>{
  const dir=mkdtempSync(join(tmpdir(),"agroedge-regime-"));
  const file=join(dir,"regime.sqlite");
  let store=new Store(file);
  try {
    baseline(store);
    for(let i=31;i<40;i++) {
      const r=ingest(store,i,outdoor);
      assert.equal(r.quality,"ANOMALY");
      assert.ok(!r.issues.includes(regimeChangeIssue));
    }
    const transition=ingest(store,40,outdoor);
    assert.equal(transition.quality,"ANOMALY");
    assert.ok(transition.issues.includes(regimeChangeIssue));
    store.close();
    store=new Store(file);
    assert.equal(ingest(store,41,outdoor).quality,"VALID");
    assert.equal(ingest(store,42,greenhouse).quality,"ANOMALY");
    assert.equal(ingest(store,43,outdoor).quality,"VALID");
    assert.equal(ingest(store,1,greenhouse,start+44*5000,"qa-new-context").quality,"VALID");
    const bySequence=new Map(store.query(new URLSearchParams({origin:"USB",session:"qa-boot",limit:"100"})).rows.map(row=>[row.sequence,row]));
    assert.equal(bySequence.get(31).quality,"ANOMALY");
    assert.deepEqual(bySequence.get(40).issues,transition.issues);
  } finally {
    store.close();
    rmSync(dir,{recursive:true,force:true});
  }
});

test("isolated peaks and sustained one-channel shifts remain flagged",()=>{
  const store=new Store(":memory:");
  try {
    baseline(store);
    const isolated=ingest(store,31,outdoor);
    assert.equal(isolated.quality,"ANOMALY");
    assert.ok(!isolated.issues.includes(regimeChangeIssue));
    assert.equal(ingest(store,32).quality,"VALID");
    for(let i=33;i<=105;i++) {
      const r=ingest(store,i,{...greenhouse,pressure:760});
      assert.equal(r.quality,"ANOMALY");
      assert.ok(!r.issues.includes(regimeChangeIssue));
    }
    assert.equal(ingest(store,106).quality,"VALID");
  } finally { store.close(); }
});

test("missing or impossible sensor values and buffered receipts cannot renew the reference",()=>{
  const store=new Store(":memory:");
  try {
    baseline(store);
    for(let i=31;i<=39;i++) ingest(store,i,outdoor);
    const invalid=ingest(store,40,{...outdoor,humidity:110});
    assert.equal(invalid.quality,"INVALID");
    assert.equal(invalid.humidity,null);
    assert.ok(invalid.issues.some(issue=>/humidity: tipo o rango inválido/.test(issue)));
    assert.equal(ingest(store,41,{...outdoor,pressure:null}).quality,"MISSING");
    for(let i=42;i<=53;i++) {
      const r=ingest(store,i,outdoor,start+400000+(i-42)*50);
      assert.equal(r.quality,"ANOMALY");
      assert.ok(!r.issues.includes(regimeChangeIssue));
    }
    assert.equal(ingest(store,54).quality,"VALID");
  } finally { store.close(); }
});
