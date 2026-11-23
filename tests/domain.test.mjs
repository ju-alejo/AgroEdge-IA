import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { Store } from "../lib/store.ts";
import { synthetic } from "../lib/simulator.ts";
import { utc } from "../lib/domain.ts";
import { parseForecast } from "../lib/forecast.ts";
import { exportFile, parseFile } from "../lib/transfer.ts";

const now=Date.parse("2026-11-19T19:01:00Z");
const at=new Date(now).toISOString();
const base={schemaVersion:1,stationId:"QA-ONLY",sessionId:"boot-1",sequence:1,acquiredAt:at,temperature:15,humidity:72,pressure:735};
const config={seed:42,scenario:"dry",intervalMs:500,variation:1,tinyML:true};
const query=(origin="SIMULATION",order="asc")=>new URLSearchParams({origin,order});

test("reproduces measurements by seed with temporal continuity",()=>{
  assert.deepEqual(synthetic(config,55,at),synthetic(config,55,at));
  const series=Array.from({length:150},(_,i)=>synthetic(config,i+1,at));
  assert.ok(series.some((sample,i)=>sample.temperature!==synthetic({...config,seed:43},i+1,at).temperature));
  assert.ok(series.slice(1).every((r,i)=>Math.abs(r.temperature-series[i].temperature)<1));
  assert.ok(synthetic({...config,scenario:"humid"},20,at).humidity>synthetic(config,20,at).humidity);
  assert.throws(()=>utc("2026-02-30T01:10:00Z"));
  assert.equal(utc("2026-11-19T14:01:00-05:00"),at);
});

test("start, pause, resume, stop, reset and speed preserve finished sessions",()=>{
  const store=new Store(":memory:");
  try {
    const first=store.control({action:"start",config},now);
    assert.equal(first.sequence,1);
    assert.equal(store.poll(now+1000).sequence,3);
    store.control({action:"pause",config},now+1200);
    assert.equal(store.poll(now+3000).sequence,3);
    assert.equal(store.control({action:"start",config},now+3100).sequence,4);
    store.control({action:"speed",config:{...config,intervalMs:2000}},now+3200);
    assert.equal(store.poll(now+5000).sequence,4);
    assert.equal(store.poll(now+5200).sequence,5);
    store.control({action:"stop",config},now+5201);
    assert.equal(store.poll(now+8000).sequence,5);
    const second=store.control({action:"reset",config},now+9000);
    assert.notEqual(second.sessionId,first.sessionId);
    assert.equal(second.sequence,1);
    assert.equal(store.query(query()).total,6);
    assert.equal(store.sessions("SIMULATION").length,2);
  } finally {store.close();}
});

test("quality, gaps, IDs, isolation and persistence across database reopening",()=>{
  const dir=mkdtempSync(join(tmpdir(),"agroedge-store-"));
  const path=join(dir,"data.sqlite");
  let db=new Store(path);
  try {
    const input={...base,acquiredAt:undefined};
    const first=db.ingest(input,"USB",undefined,now);
    assert.equal(first.reading.timeSource,"RECEIPT");
    assert.equal(db.ingest(input,"USB",undefined,now+1000).status,"duplicate");
    assert.throws(()=>db.ingest({...input,pressure:690},"USB"),/Conflicto/);
    assert.throws(()=>db.ingest(input,"WIFI"),/sincronizado/);
    const next=db.ingest({...base,sequence:4,temperature:null,humidity:111},"USB",undefined,now+2000).reading;
    assert.equal(next.missingBefore,2);
    assert.equal(next.quality,"INVALID");
    assert.equal(next.temperature,null);
    assert.equal(next.humidity,null);
    assert.equal(next.pressure,735);
    for(let i=1;i<=16;i++) db.ingest({...base,sequence:i,acquiredAt:new Date(now+i*1000).toISOString(),temperature:i===16?22:15},"WIFI",undefined,now+i*1000);
    assert.equal(db.query(query("WIFI","desc")).rows[0].quality,"ANOMALY");
    assert.throws(()=>db.ingest({...base,sequence:17,classification:{source:"SIMULATED"}},"WIFI"),/TinyML/);
    const test=db.ingest({...base,stationId:"FIXTURE",origin:"WIFI"},"SIMULATION","WIFI",now).reading;
    assert.equal(test.dataKind,"SIMULATED");
    assert.equal(test.testTransport,"WIFI");
    db.close();db=new Store(path);
    assert.equal(db.query(query("USB")).total,2);
    assert.equal(db.query(query("WIFI")).total,16);
    assert.equal(db.query(query()).total,1);
  } finally {db.close();rmSync(dir,{recursive:true,force:true});}
});

test("CSV and Excel round-trip with selected columns, units, ordering and duplicate detection",async()=>{
  const source=new Store(":memory:"),target=new Store(":memory:");
  try {
    source.control({action:"start",config},now);
    source.poll(now+1500);
    const rows=source.query(query("SIMULATION","desc")).rows;
    assert.deepEqual(rows.map(r=>r.sequence),[4,3,2,1]);
    const opts={cols:"temperature,humidity,pressure,classification",delimiter:";",meta:{Origen:"SIMULATION"}};
    const csv=await exportFile(rows,"csv",opts);
    const xlsx=await exportFile(rows,"xlsx",opts);
    assert.equal(Buffer.from(xlsx).subarray(0,2).toString(),"PK");
    const fromCsv=await parseFile(csv,"csv");
    assert.equal(target.import(fromCsv).inserted,4);
    const fromExcel=await parseFile(xlsx,"xlsx");
    assert.deepEqual(fromExcel.map(r=>r.sequence),[4,3,2,1]);
    assert.equal(target.import(fromExcel).duplicates,4);
    const full=await exportFile(rows,"xlsx",{...opts,cols:null});
    assert.equal(target.import(await parseFile(full,"xlsx")).duplicates,4);
    for(const delimiter of [",",";","\t"]) {
      const complete=await exportFile(rows,"csv",{...opts,cols:null,delimiter});
      assert.equal(target.import(await parseFile(complete,"csv")).duplicates,4);
    }
    const bad=new TextEncoder().encode(new TextDecoder().decode(csv).replace("Temperatura (°C)","Temperatura (°F)"));
    await assert.rejects(parseFile(bad,"csv"),/incompatibles/);
    assert.throws(()=>target.import([{...fromCsv[0],temperature:"14"}]),/valor o unidad/);
    assert.throws(()=>target.import([{...fromCsv[0],acquiredAt:"2026-02-30T01:10:00Z"}]),/fecha/);
    assert.throws(()=>target.import([{...fromCsv[0],id:"new",sequence:25},{...fromCsv[1],sequence:26}]),/conflicto|corresponden/i);
    assert.equal(target.query(query()).total,4);
  } finally {source.close();target.close();}
});

test("transport rejects incompatible provenance without altering saved readings",()=>{
  const store=new Store(":memory:");
  try {
    for(const origin of ["USB","WIFI"]) {
      assert.throws(()=>store.ingest({...base,dataKind:"SIMULATED"},origin),/condición de datos/);
      assert.throws(()=>store.ingest({...base,testTransport:origin},origin),/transporte de prueba/);
      assert.equal(store.query(query(origin)).total,0);
      assert.equal(store.ingest({...base,dataKind:"REAL"},origin).reading.dataKind,"REAL");
    }
    assert.throws(()=>store.ingest({...base,dataKind:"REAL"},"SIMULATION","WIFI"),/condición de datos/);
    assert.equal(store.ingest(base,"SIMULATION","USB").reading.testTransport,"USB");
    assert.equal(store.ingest(base,"SIMULATION","USB").status,"duplicate");
    assert.throws(()=>store.ingest(base,"SIMULATION","WIFI"),/Conflicto/);
    assert.equal(store.query(query()).total,1);
  } finally {store.close();}
});

test("USB classifications retain latency, model status and receipt time through SQLite and exports",async()=>{
  const store=new Store(":memory:");
  const restored=new Store(":memory:");
  const payload={...base,acquiredAt:undefined,classification:{source:"ESP32",state:"OK",label:"Humedad ambiental alta",
    score:0.8,modelVersion:"humidity-prototype-1",modelStatus:"PRELIMINARY",inferenceUs:3}};
  try {
    const result=store.ingest(payload,"USB",undefined,now).reading;
    assert.equal(result.classification.inferredAt,at);
    assert.equal(result.classification.inferenceTimeSource,"RECEIPT");
    assert.equal(result.classification.inferenceUs,3);
    assert.equal(result.classification.modelStatus,"PRELIMINARY");
    assert.equal(store.ingest(payload,"USB",undefined,now+1000).status,"duplicate");
    for(const format of ["csv","xlsx"]) {
      const file=await exportFile([result],format,{delimiter:",",meta:{}});
      assert.deepEqual((await parseFile(file,format))[0].classification,result.classification);
      restored.import(await parseFile(file,format));
    }
    assert.equal(restored.ingest(payload,"USB",undefined,now+3000).status,"duplicate");
    assert.throws(()=>store.ingest({...payload,acquiredAt:at},"WIFI",undefined,now),/fecha ISO/);
    assert.throws(()=>store.ingest({...payload,sequence:2,classification:{...payload.classification,inferenceUs:-1}},"USB"),/microsegundos/);
    assert.throws(()=>store.ingest({...payload,sequence:2,classification:{...payload.classification,inferenceTimeSource:"RECEIPT"}},"USB"),/Fuente horaria/);
  } finally {store.close();restored.close();}
});

test("the previously delivered exports remain importable", async()=>{
  const store=new Store(":memory:");
  try {
    const example=(format)=>new URL(`../examples/AgroEdge_SIMULATION_2026-11-19.${format}`,import.meta.url);
    const rows=await parseFile(await readFile(example("csv")),"csv");
    assert.ok(rows.length>0);
    assert.deepEqual(store.import(rows),{inserted:rows.length,duplicates:0});
    const workbook=await parseFile(await readFile(example("xlsx")),"xlsx");
    assert.deepEqual(store.import(workbook),{inserted:0,duplicates:rows.length});
  } finally {store.close();}
});

test("forecast resolves preceding-hour precipitation and rejects incomplete horizons",()=>{
  const start=Math.floor(now/3600000)*3600000;
  const hourly={time:Array.from({length:49},(_,i)=>(start+i*3600000)/1000),
    temperature_2m:Array.from({length:49},(_,i)=>12+i%7),precipitation:Array(49).fill(.2),precipitation_probability:Array(49).fill(50)};
  hourly.precipitation[0]=99;
  const fixture={hourly,hourly_units:{temperature_2m:"°C",precipitation:"mm",precipitation_probability:"%"}};
  const point={latitude:5.56,longitude:-73.18};
  const result=parseForecast(fixture,point,now);
  assert.equal(result.hourly.length,48);
  assert.equal(result.horizons[0].precipitation,4.8);
  assert.equal(result.horizons[1].precipitation,9.6);
  hourly.precipitation[25]=null;
  assert.equal(parseForecast(fixture,point,now).horizons[1].precipitation,null);
  hourly.time.pop();
  assert.throws(()=>parseForecast(fixture,point,now),/48 horas/);
});

