import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { once } from "node:events";
import { tmpdir } from "node:os";
import { join } from "node:path";
import net from "node:net";
import { randomUUID } from "node:crypto";
import { setTimeout as wait } from "node:timers/promises";
import { parseFile } from "../lib/transfer.ts";
import { replay } from "./replay-fixtures.mjs";

const temp=await mkdtemp(join(tmpdir(),"agroedge-http-"));
const direct=process.argv.includes("--routes");
async function freePort() {
  const socket=net.createServer();
  socket.listen(0,"127.0.0.1");
  await once(socket,"listening");
  const {port}=socket.address();
  await new Promise(resolve=>socket.close(resolve));
  return port;
}
const port=direct?5173:await freePort();
const root=`http://127.0.0.1:${port}`;
const token=randomUUID();
const testEnv={AGROEDGE_DB:join(temp,"test.sqlite"),AGROEDGE_DEVICE_TOKEN:token,
  AGROEDGE_ALLOW_TESTS:"1",NEXT_TELEMETRY_DISABLED:"1"};
const require=createRequire(import.meta.url);
let server;
let routes;
async function send(address,options) {
  if(!direct) return fetch(address,options);
  if(address===root) return new Response(await readFile(".next/server/app/index.html"));
  const request=new Request(address,options);
  return routes[request.method](request);
}
async function start() {
  if(direct) {
    Object.assign(process.env,testEnv);
    routes=require("../.next/server/app/api/[...path]/route.js").routeModule.userland;
    return;
  }
  let log="";
  server=spawn(process.execPath,["node_modules/next/dist/bin/next","start","-H","127.0.0.1","-p",String(port)],{
    windowsHide:true,env:{...process.env,...testEnv},stdio:["ignore","pipe","pipe"]});
  server.stdout.on("data",d=>log+=d);server.stderr.on("data",d=>log+=d);
  for(let n=0;n<50;n++) {
    if(server.exitCode!==null) break;
    try{if((await send(root+"/api/snapshot?origin=SIMULATION",{signal:AbortSignal.timeout(1500)})).ok) return;}
    catch(error) {
      if(error.cause?.code==="EACCES") throw new Error("El entorno bloquea la conexión local. Ejecuta npm.cmd run test:app -- --routes para probar las rutas compiladas.");
    }
    await wait(300);
  }
  throw new Error("La app no quedó disponible.\n"+log);
}
async function stop() {
  if(direct) {
    globalThis.agroEdgeStore?.close();
    delete globalThis.agroEdgeStore;
    return;
  }
  if(server?.exitCode===null) {const exit=once(server,"exit");server.kill();await exit;}
}
function url(path) {return root+"/api/"+path;}
function post(path,value,auth=false) {
  return send(url(path),{method:"POST",headers:{"Content-Type":"application/json",...(auth?{Authorization:"Bearer "+token}:{})},body:JSON.stringify(value)});
}
async function read(path) {
  const response=await send(url(path));
  const data=await response.json();
  assert.ok(response.ok,JSON.stringify(data));
  return data;
}
const config={seed:42,scenario:"balanced",intervalMs:500,variation:1,tinyML:true};
try {
  await start();
  const html=await (await send(root)).text();
  assert.match(html,/AgroEdge IA/);
  assert.match(html,/Panel principal/);
  const sim=await (await post("simulation",{action:"start",config})).json();
  assert.equal(sim.state,"RUNNING");
  await wait(1250);
  const running=await read("snapshot?origin=SIMULATION");
  assert.ok(running.history.total>=3);
  assert.equal(running.inference.classification.source,"SIMULATED");
  const earliest=running.previous.acquiredAt;
  const range=new URLSearchParams({origin:"SIMULATION",from:earliest,to:running.latest.acquiredAt});
  const filtered=await read("measurements?"+range);
  assert.deepEqual(filtered.rows.map(r=>r.acquiredAt),[earliest]);
  const filteredSnapshot=await read("snapshot?"+range);
  assert.equal(filteredSnapshot.latestInPeriod.acquiredAt,earliest);
  assert.ok(filteredSnapshot.latest.acquiredAt>earliest);
  assert.equal((await post("simulation",{action:"stop",config})).status,200);
  const replayed=await replay(root,send);
  assert.equal(replayed[1].reading.quality,"MISSING");
  assert.equal(replayed[1].reading.missingBefore,1);
  assert.equal((await read("measurements?origin=WIFI")).total,0);
  assert.equal((await read("measurements?origin=USB")).total,0);
  const fixture={schemaVersion:1,stationId:"TEST-ONLY",sessionId:"integration-isolated",sequence:1,
    acquiredAt:new Date().toISOString(),temperature:14,humidity:75,pressure:736};
  assert.equal((await post("measurements/wifi",fixture)).status,403);
  for(const origin of ["wifi","usb"]) {
    const ineligible=await post("measurements/"+origin,{...fixture,dataKind:"SIMULATED"},true);
    assert.equal(ineligible.status,400);
    assert.match((await ineligible.json()).error,/condición de datos/);
    assert.equal((await read("measurements?origin="+origin.toUpperCase())).total,0);
    const serial=origin==="usb";
    const payload={...fixture,acquiredAt:serial?undefined:fixture.acquiredAt,origin:origin.toUpperCase(),
      classification:{source:"ESP32",state:"OK",label:"Fixture de QA",score:.625,modelVersion:"qa-only",
        ...(serial?{modelStatus:"PRELIMINARY",inferenceUs:3}:{inferredAt:fixture.acquiredAt})}};
    const first=await post("measurements/"+origin,payload,true);
    assert.equal(first.status,201,await first.clone().text());
    assert.equal((await post("measurements/"+origin,payload,true)).status,200);
    const snapshot=await read("snapshot?origin="+origin.toUpperCase());
    assert.equal(snapshot.latest.temperature,14);
    assert.equal(snapshot.inference.classification.modelVersion,"qa-only");
    if(serial) {
      assert.equal(snapshot.inference.classification.inferenceTimeSource,"RECEIPT");
      assert.equal(snapshot.inference.classification.inferredAt,snapshot.inference.receivedAt);
      assert.equal(snapshot.inference.classification.inferenceUs,3);
    }
  }
  for(const origin of ["SIMULATION","USB","WIFI"]) {
    for(const format of ["csv","xlsx"]) {
      const params=new URLSearchParams({origin,format,delimiter:"semicolon",order:"desc"});
      if(origin==="SIMULATION") params.set("from","2020-01-01T00:00:00Z");
      const file=await send(url("export?"+params));
      assert.equal(file.status,200,await file.clone().text().then(t=>t.slice(0,60)));
      assert.match(file.headers.get("content-disposition"),new RegExp(`AgroEdge_${origin}_\\d{4}-\\d{2}-\\d{2}\\.${format}`));
      const bytes=new Uint8Array(await file.arrayBuffer());
      const records=await parseFile(bytes,format);
      assert.ok(records.every((r,i)=>r.origin===origin&&(i===0||records[i-1].acquiredAt>=r.acquiredAt)));
      const response=await send(url("import?format="+format),{method:"POST",body:bytes});
      const result=await response.json();
      assert.deepEqual(result,{inserted:0,duplicates:records.length});
      if(origin==="SIMULATION"&&process.env.AGROEDGE_WRITE_EXAMPLES==="1") {
        const name=file.headers.get("content-disposition").split('"')[1];
        await writeFile(join("examples",name),bytes);
      }
    }
  }
  const incompatible=await send(url("import?format=csv"),{method:"POST",body:"fecha,grados\n2026-11-19,14"});
  assert.equal(incompatible.status,400);
  const stored=(await read("measurements?origin=SIMULATION")).total;
  await stop();
  await start();
  assert.equal((await read("measurements?origin=SIMULATION")).total,stored);
  assert.equal((await read("measurements?origin=USB")).total,1);
  assert.equal((await read("measurements?origin=WIFI")).total,1);
  console.log(`${direct?"Rutas compiladas":"Aplicación por HTTP"}: simulación, fixture serial, TinyML, CSV, XLSX, duplicados y persistencia comprobados.`);
} finally {
  await stop();
  await rm(temp,{recursive:true,force:true});
}

