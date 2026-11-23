import { DatabaseSync, type SQLInputValue } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { randomUUID, createHash } from "node:crypto";
import { object, statistics, correlations, utc, type Origin, type Reading } from "./domain.ts";
import { identity, sourceKind, transport, validateImport, validateLive } from "./measurements.ts";
import { simulationConfig, synthetic, type SimConfig } from "./simulator.ts";
import { predict } from "./trend.ts";

export const maxExport = 25000;
const tableFor=(origin: Origin)=>origin==="SIMULATION"?"simulated_readings":"real_readings";
const iso=(ms=Date.now())=>new Date(ms).toISOString();
const defaults:SimConfig={seed:42,scenario:"balanced",intervalMs:2000,variation:1,tinyML:true};
type Simulator = {state:"RUNNING"|"PAUSED"|"STOPPED";config:SimConfig;sessionId:string|null;sequence:number;due:number|null};
export type Connection = {stationId?:string;port?:string;state:string;updatedAt:string;lastReading?:string;error?:string;receiptTimeout?:number};

export class Store {
  private db: DatabaseSync;
  constructor(path: string) {
    if(path!==":memory:") mkdirSync(dirname(resolve(path)),{recursive:true});
    this.db=new DatabaseSync(path);
    this.db.exec("PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL;");
    for(const [table, allowed] of [["simulated_readings","'SIMULATION'"],["real_readings","'USB','WIFI'"]]) {
      this.db.exec(`CREATE TABLE IF NOT EXISTS ${table} (
        id TEXT PRIMARY KEY, origin TEXT NOT NULL CHECK(origin IN (${allowed})), station TEXT NOT NULL,
        session TEXT NOT NULL, seq INTEGER NOT NULL, acquired TEXT NOT NULL, quality TEXT NOT NULL,
        payload TEXT NOT NULL, fingerprint TEXT, UNIQUE(origin,station,session,seq)
      ) STRICT;
      CREATE INDEX IF NOT EXISTS ${table}_time ON ${table}(origin,acquired,id);`);
    }
    this.db.exec("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;");
  }
  close() { this.db.close(); }
  private transaction<T>(fn:()=>T) {
    this.db.exec("BEGIN IMMEDIATE");
    try { const result=fn(); this.db.exec("COMMIT"); return result; }
    catch(error) { this.db.exec("ROLLBACK"); throw error; }
  }
  private state<T>(key:string): T|undefined {
    const row=this.db.prepare("SELECT value FROM state WHERE key=?").get(key);
    return row?JSON.parse(String(row.value)):undefined;
  }
  private put(key:string,value:unknown) {
    this.db.prepare("INSERT INTO state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(key,JSON.stringify(value));
  }
  private lookup(origin:Origin, ids:ReturnType<typeof identity>) {
    return this.db.prepare(`SELECT id,payload,fingerprint FROM ${tableFor(origin)}
      WHERE id=? OR (origin=? AND station=? AND session=? AND seq=?)`).all(ids.id,origin,ids.stationId,ids.sessionId,ids.sequence);
  }
  private insert(r:Reading,fingerprint:string|null) {
    this.db.prepare(`INSERT INTO ${tableFor(r.origin)} VALUES (?,?,?,?,?,?,?,?,?)`)
      .run(r.id,r.origin,r.stationId,r.sessionId,r.sequence,r.acquiredAt,r.quality,JSON.stringify(r),fingerprint);
  }
  ingest(value:unknown,origin:Origin,testTransport?:"USB"|"WIFI",now=Date.now()) {
    return this.transaction(()=>this.saveLive(object(value),origin,iso(now),testTransport));
  }
  private saveLive(v:Record<string,unknown>,origin:Origin,received:string,testTransport?:"USB"|"WIFI") {
    sourceKind(v,origin,testTransport);
    const ids=identity(v,origin), table=tableFor(origin);
    const ordered=(x:unknown):unknown=>x&&typeof x==="object"&&!Array.isArray(x)?
      Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b)).map(([k,y])=>[k,ordered(y)])):x;
    const fingerprint=createHash("sha256").update(JSON.stringify(ordered(v))).digest("hex");
    const existing=this.lookup(origin,ids);
    if(existing.length) {
      const prior=JSON.parse(String(existing[0].payload)) as Reading;
      if(existing.length===1&&prior.id===ids.id&&prior.testTransport===testTransport&&existing[0].fingerprint===fingerprint) {
        return {status:"duplicate",reading:prior};
      }
      if(existing.length===1&&existing[0].fingerprint===null&&prior.id===ids.id) {
        const candidate=validateLive(v,origin,[],Math.max(0,ids.sequence-1),prior.receivedAt,testTransport);
        const fields=["id","stationId","sessionId","sequence","acquiredAt","timeSource","temperature","humidity","pressure","origin","classification","testTransport"] as const;
        if(fields.every(k=>JSON.stringify(candidate[k])===JSON.stringify(prior[k]))) return {status:"duplicate",reading:prior};
      }
      throw new Error("Conflicto de ID o secuencia: ya existe una lectura distinta.");
    }
    const acquired=v.acquiredAt===undefined||v.acquiredAt===null?received:utc(v.acquiredAt);
    const past=this.db.prepare(`SELECT payload FROM ${table} WHERE origin=? AND station=? AND session=?
      AND seq<? AND quality='VALID' AND acquired>=? AND acquired<=? ORDER BY seq DESC LIMIT 60`)
      .all(origin,ids.stationId,ids.sessionId,ids.sequence,iso(Date.parse(acquired)-3600000),acquired);
    const prev=this.db.prepare(`SELECT COALESCE(MAX(seq),0) AS seq FROM ${table}
      WHERE origin=? AND station=? AND session=? AND seq<?`).get(origin,ids.stationId,ids.sessionId,ids.sequence)!;
    const reading=validateLive(v,origin,past.map(r=>JSON.parse(String(r.payload))),Number(prev.seq),received,testTransport);
    this.insert(reading,fingerprint);
    if(origin!=="SIMULATION") {
      const key=`connection:${origin}:${reading.stationId}`;
      this.put(key,{stationId:reading.stationId,state:"RECEIVING",updatedAt:received,lastReading:received});
    }
    return {status:"stored",reading};
  }
  import(records:Record<string,unknown>[]) {
    const validated=records.map((v,i)=>{
      try { return validateImport(v); }
      catch(e) { throw new Error(`Fila ${i+2}: ${e instanceof Error?e.message:e}`); }
    });
    return this.transaction(()=>{
      let inserted=0, duplicates=0;
      validated.forEach((r,i)=>{
        const prior=this.lookup(r.origin,r);
        if(!prior.length) { this.insert(r,null); inserted++; return; }
        if(prior.length===1&&String(prior[0].payload)===JSON.stringify(r)) { duplicates++; return; }
        // Compare canonical fields, since import and acquisition construct property order independently.
        const same=prior.length===1&&Object.entries(r).every(([k,v])=>JSON.stringify(v)===JSON.stringify(JSON.parse(String(prior[0].payload))[k]))
          && Object.keys(JSON.parse(String(prior[0].payload))).length===Object.keys(r).length;
        if(!same) throw new Error(`Fila ${i+2}: el ID o la secuencia corresponden a otro registro. Se canceló la importación completa.`);
        duplicates++;
      });
      return {inserted,duplicates};
    });
  }
  private sim(): Simulator {
    return this.state<Simulator>("simulator")??{state:"STOPPED",config:defaults,sessionId:null,sequence:0,due:null};
  }
  private advance(sim:Simulator,now:number) {
    if(sim.state!=="RUNNING"||sim.due===null||!sim.sessionId||sim.due>now) return sim;
    const interval=sim.config.intervalMs;
    // After an inactive browser or machine suspend, resume at the present rather than creating invented downtime history.
    if(now-sim.due>Math.max(10000,interval*3)) sim.due=now;
    while(sim.due!==null&&sim.due<=now) {
      const captured=iso(sim.due);
      this.saveLive({schemaVersion:1,stationId:"TOCA-DEMO",sessionId:sim.sessionId,sequence:++sim.sequence,
        ...synthetic(sim.config,sim.sequence,captured)},"SIMULATION",iso(now));
      sim.due+=interval;
    }
    this.put("simulator",sim);
    return sim;
  }
  poll(now=Date.now()) {
    const s=this.sim();
    if(s.state!=="RUNNING"||s.due===null||s.due>now) return s;
    return this.transaction(()=>this.advance(this.sim(),now));
  }
  control(value:unknown,now=Date.now()) {
    const {action,config}=object(value);
    const valid=simulationConfig(config);
    return this.transaction(()=>{
      let sim=this.advance(this.sim(),now);
      if(action==="reset"||(action==="start"&&sim.state==="STOPPED")) {
        sim={state:"RUNNING",config:valid,sessionId:"sim-"+randomUUID(),sequence:0,due:now};
      } else if(action==="start"&&sim.state==="PAUSED") {
        sim={...sim,state:"RUNNING",due:now};
      } else if(action==="pause"&&sim.state==="RUNNING") {
        sim={...sim,state:"PAUSED",due:null};
      } else if(action==="stop") {
        sim={...sim,state:"STOPPED",due:null};
      } else if(action==="speed") {
        sim={...sim,config:{...sim.config,intervalMs:valid.intervalMs},due:sim.state==="RUNNING"?now+valid.intervalMs:null};
      } else if(!["start","pause"].includes(String(action))) throw new Error("Control de simulación desconocido.");
      this.put("simulator",sim);
      return this.advance(sim,now);
    });
  }
  private filter(p:URLSearchParams) {
    const origin=transport(p.get("origin")??"SIMULATION");
    const where=["origin=?"], params:SQLInputValue[]=[origin];
    for(const [key,column] of [["station","station"],["session","session"],["quality","quality"]]) {
      const q=p.get(key);
      if(q) {where.push(column+"=?");params.push(q);}
    }
    const from=p.get("from"),to=p.get("to");
    if(from) {where.push("acquired>=?");params.push(utc(from));}
    if(to) {where.push("acquired<?");params.push(utc(to));}
    if(from&&to&&Date.parse(from)>=Date.parse(to)) throw new Error("El inicio debe ser anterior al final.");
    const dir=p.get("order")==="asc"?"ASC":"DESC";
    return {origin,table:tableFor(origin),where:where.join(" AND "),params,dir};
  }
  query(p:URLSearchParams, exporting=false) {
    const {table,where,params,dir}=this.filter(p);
    const total=Number(this.db.prepare(`SELECT COUNT(*) n FROM ${table} WHERE ${where}`).get(...params)?.n);
    if(exporting&&total>maxExport) throw new Error(`Hay ${total} filas. Acota el filtro a ${maxExport} registros por archivo.`);
    const size=exporting?maxExport:50;
    const requested=Number(p.get("page")??0);
    const page=exporting||!Number.isSafeInteger(requested)?0:Math.min(Math.max(0,requested),Math.max(0,Math.ceil(total/size)-1));
    const list=this.db.prepare(`SELECT payload FROM ${table} WHERE ${where} ORDER BY acquired ${dir},seq ${dir},id ${dir} LIMIT ? OFFSET ?`)
      .all(...params,size,page*size);
    return {rows:list.map(x=>JSON.parse(String(x.payload)) as Reading),total,page,size};
  }
  sessions(origin:Origin) {
    return this.db.prepare(`SELECT station AS stationId,session AS sessionId,COUNT(*) AS count,MIN(acquired) AS first,MAX(acquired) AS last
      FROM ${tableFor(origin)} WHERE origin=? GROUP BY station,session ORDER BY last DESC`).all(origin)
      .map(r=>({stationId:String(r.stationId),sessionId:String(r.sessionId),count:Number(r.count),first:String(r.first),last:String(r.last)}));
  }
  connections(origin:Origin) {
    if(origin==="SIMULATION") return [];
    return this.db.prepare("SELECT value FROM state WHERE key LIKE ? ORDER BY key").all(`connection:${origin}:%`).map(r=>JSON.parse(String(r.value)) as Connection)
      .map(c=>({...c,state:Date.now()-Date.parse(c.lastReading??c.updatedAt)>Number(process.env.AGROEDGE_STALE_SECONDS??30)*1000?"STALE":c.state}));
  }
  recordConnectionError(origin:"USB"|"WIFI",value:unknown,error:string) {
    if(!value||typeof value!=="object") return;
    const {stationId}=value as {stationId?:unknown};
    if(typeof stationId!=="string"||!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$/.test(stationId)) return;
    const key=`connection:${origin}:${stationId}`;
    this.put(key,{...this.state<Connection>(key),stationId,state:"ERROR",updatedAt:iso(),error});
  }
  snapshot(p:URLSearchParams) {
    const sim=this.poll(), {origin,table,where,params}=this.filter(p);
    const f=new URLSearchParams({origin});
    for(const k of ["station","session"]) {const v=p.get(k); if(v) f.set(k,v);}
    const latest=this.query(f).rows;
    const sampled=this.db.prepare(`SELECT payload FROM ${table} WHERE ${where} ORDER BY acquired DESC,seq DESC,id DESC LIMIT 10001`).all(...params);
    const rows=sampled.slice(0,10000).reverse().map(x=>JSON.parse(String(x.payload)) as Reading);
    const skip=Math.max(1,Math.ceil(rows.length/700));
    const series=rows.filter((r,i)=>i%skip===0||i===rows.length-1||r.missingBefore>0||r.quality==="MISSING"||r.quality==="INVALID").flatMap((r,i,all)=>{
      const prev=all[i-1],ts=Date.parse(r.acquiredAt);
      const gap=r.missingBefore>0&&prev&&prev.stationId===r.stationId&&prev.sessionId===r.sessionId&&ts>Date.parse(prev.acquiredAt);
      return [...(gap?[{ts:(ts+Date.parse(prev.acquiredAt))/2, temperature:null,humidity:null,pressure:null,status:"gap"}]:[]),
        {ts,temperature:r.temperature,humidity:r.humidity,pressure:r.pressure,status:r.quality==="VALID"?"normal":r.quality}];
    });
    const selected=this.filter(f);
    const classificationRow=this.db.prepare(`SELECT payload FROM ${table} WHERE ${selected.where}
      AND json_type(payload,'$.classification')='object' ORDER BY acquired DESC,seq DESC LIMIT 1`).get(...selected.params);
    return {sim,latest:latest[0]??null,previous:latest[1]??null,latestInPeriod:rows.at(-1)??null,
      stats:statistics(rows),correlations:correlations(rows),trend:predict(rows),series,
      anomalies:rows.filter(r=>r.quality!=="VALID"||r.missingBefore>0).slice(-15).reverse(),truncated:sampled.length>10000,
      inference:classificationRow?JSON.parse(String(classificationRow.payload)) as Reading:null,
      sessions:this.sessions(origin),connections:this.connections(origin),history:this.query(p)};
  }
}

const shared=globalThis as typeof globalThis & {agroEdgeStore?:Store};
export function getStore() {
  return shared.agroEdgeStore??=new Store(process.env.AGROEDGE_DB??resolve("data","agroedge.sqlite"));
}

