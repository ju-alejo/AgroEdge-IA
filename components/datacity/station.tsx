"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent } from "react";
import { Activity, Bell, BrainCircuit, Cable, CloudRain, Database, Droplets, Gauge, LayoutDashboard,
  Leaf, Thermometer, Wifi } from "lucide-react";
import { SidebarProvider, Sidebar, SidebarHeader, SidebarContent, SidebarFooter, SidebarMenu,
  SidebarMenuItem, SidebarMenuButton, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { api, Badge, dateTime, Empty, fmt, Panel, SeriesChart, Trend } from "./shared";
import { columns, mandatory, type Key } from "@/lib/columns";
import { labels, units, colors, variables, qualities, type Origin, type Reading } from "@/lib/domain";
import { scenarios, type SimConfig } from "@/lib/simulator";
import type { Store } from "@/lib/store";
import type { getForecast } from "@/lib/forecast";
import { ForecastPanel, Alerts, Analysis, InferencePanel, ConnectionPanel } from "./views";
import ClimatePanel from "./climate-panel";

const sections=[
  ["dashboard","Panel principal",LayoutDashboard],["monitor","Monitoreo meteorológico",Activity],
  ["forecast","Pronóstico agrícola",CloudRain],["tiny","Clasificación TinyML",BrainCircuit],
  ["history","Historial y registros",Database],["alerts","Alertas",Bell],
  ["analysis","Análisis de datos",Gauge],["connection","Conexión",Cable],
] as const;
type View=typeof sections[number][0];
const descriptions:Record<View,string>={
  dashboard:"Estación agroclimática · Toca, Boyacá",
  monitor:"Consulta la evolución de la temperatura, la humedad y la presión de la estación.",
  forecast:"Precipitación y temperatura previstas para Toca.",
  tiny:"Último resultado recibido de la estación o ejemplo de simulación.",
  history:"Filtra por fecha, estación y sesión. Importa o exporta mediciones.",
  alerts:"Observaciones de calidad y avisos orientativos con fuente identificada.",
  analysis:"Estadística descriptiva y relación entre variables de la fuente activa.",
  connection:"Estado de recepción de la estación y configuración USB.",
};
export const sourceNames={SIMULATION:"SIMULACIÓN",USB:"USB · SENSOR",WIFI:"WI-FI · SENSOR"};
export const modeNames={SIMULATION:"Simulación",USB:"Adquisición por USB",WIFI:"Adquisición por Wi-Fi"};
const qualityNames={VALID:"Válida",INVALID:"Inválida",MISSING:"Incompleta",ANOMALY:"Atípica"};
type Snapshot=ReturnType<Store["snapshot"]>;
export type AppSnapshot=Snapshot&{usb:{state:string;port:string|null;stationId:string|null;lastReading:string|null;error:string|null;baud:number}; wifiTimeout:number};
export type ExternalForecast=Awaited<ReturnType<typeof getForecast>>;
const emptyConfig:SimConfig={seed:42,scenario:"balanced",intervalMs:2000,variation:1,tinyML:true};

const calendar=new Intl.DateTimeFormat("en-CA",{timeZone:"America/Bogota",year:"numeric",month:"2-digit",day:"2-digit"});
export function fullDate(value?:string|null) {
  if(!value) return "—";
  return new Date(value).toLocaleString("es-CO",{dateStyle:"short",timeStyle:"medium",timeZone:"America/Bogota"});
}
function bogotaDate(value:string,end:boolean) {
  const date=new Date(value+"T00:00:00-05:00");
  if(end) date.setUTCDate(date.getUTCDate()+1);
  return date.toISOString();
}
function age(value:string,now:number) {
  const seconds=Math.floor((now-Date.parse(value))/1000);
  if(seconds<0) return "Hora futura respecto al equipo";
  if(seconds<60) return `Hace ${seconds} s`;
  if(seconds<3600) return `Hace ${Math.floor(seconds/60)} min`;
  if(seconds<86400) return `Hace ${Math.floor(seconds/3600)} h`;
  return `Hace ${Math.floor(seconds/86400)} d`;
}
function StationNav({view,onView}:{view:View;onView:(v:View)=>void}) {
  const {setOpenMobile}=useSidebar();
  const go=(v:View)=>{onView(v);setOpenMobile(false);};
  return <Sidebar className="app-sidebar">
    <SidebarHeader className="brand-area">
      <button className="brand" onClick={()=>go("dashboard")} aria-label="Inicio AgroEdge IA">
        <span className="brand-icon"><Leaf size={23}/></span><span>AgroEdge <strong>IA</strong><small>Monitoreo agroclimático</small></span>
      </button>
    </SidebarHeader>
    <SidebarContent>
      <div className="workspace"><span className="workspace-icon"><Wifi size={18}/></span><div>Estación AgroEdge<small>Toca, Boyacá · Colombia</small></div></div>
      <SidebarMenu className="nav-menu">
        {sections.map(([id,label,Icon])=><SidebarMenuItem key={id}><SidebarMenuButton className="nav-link" isActive={view===id} aria-current={view===id?"page":undefined} onClick={()=>go(id)}><Icon size={18}/><span>{label}</span></SidebarMenuButton></SidebarMenuItem>)}
      </SidebarMenu>
    </SidebarContent>
    <SidebarFooter className="sidebar-bottom"><span className="version">Proyecto universitario · AgroEdge IA</span></SidebarFooter>
  </Sidebar>;
}
function Simulation({sim,configured,onAction,busy,onChange}:{sim:Snapshot["sim"]|undefined;configured:SimConfig;onAction:(v:string,c?:SimConfig)=>void;busy:boolean;onChange:(c:SimConfig)=>void}) {
  const state=sim?.state??"STOPPED", locked=state!=="STOPPED";
  return <Panel className="ag-section">
    <div className="ag-heading"><div><h2>Simulador de la estación</h2><p>Lecturas SIMULATED para demostración.</p></div><Badge tone={state==="RUNNING"?"green":"gray"}>{state==="RUNNING"?"En ejecución":state==="PAUSED"?"En pausa":"Detenido"}</Badge></div>
    <div className="ag-controls">
      <label>Escenario<select value={configured.scenario} disabled={locked||busy} onChange={e=>onChange({...configured,scenario:e.target.value as SimConfig["scenario"]})}>
        {Object.entries(scenarios).map(([key,v])=><option key={key} value={key}>{v.label}</option>)}
      </select></label>
      <label>Semilla<input type="number" min={0} max={4294967295} value={configured.seed} disabled={locked||busy} onChange={e=>onChange({...configured,seed:Number(e.target.value)})}/></label>
      <label>Intervalo<select value={configured.intervalMs} disabled={busy} onChange={e=>{
        const next={...configured,intervalMs:Number(e.target.value)};onChange(next);if(locked) onAction("speed",next);
      }}>{[500,1000,2000,5000,10000].map(ms=><option key={ms} value={ms}>{fmt(ms/1000)} s</option>)}</select></label>
      <label>Amplitud (0–2)<input type="number" min={0} max={2} step={.1} value={configured.variation} disabled={locked||busy} onChange={e=>onChange({...configured,variation:Number(e.target.value)})}/></label>
      <label className="ag-check"><input type="checkbox" checked={configured.tinyML} disabled={locked||busy} onChange={e=>onChange({...configured,tinyML:e.target.checked})}/> Incluir ejemplo TinyML</label>
    </div>
    <div className="ag-actions">
      <button className="button primary" disabled={busy||state==="RUNNING"} onClick={()=>onAction("start")}>{state==="PAUSED"?"Reanudar":"Iniciar"}</button>
      <button className="button secondary" disabled={busy||state!=="RUNNING"} onClick={()=>onAction("pause")}>Pausar</button>
      <button className="button secondary" disabled={busy||state==="STOPPED"} onClick={()=>onAction("stop")}>Detener</button>
      <button className="button secondary" disabled={busy} onClick={()=>onAction("reset")}>Reiniciar</button>
      {sim?.sessionId&&<span className="ag-note">{sim.sequence} lecturas en esta sesión. Reiniciar abre otra sesión.</span>}
    </div>
  </Panel>;
}
function ReadingCards({reading,previous,now,origin}:{reading:Reading|null|undefined;previous:Reading|null|undefined;now:number;origin:Origin}) {
  const icons={temperature:Thermometer,humidity:Droplets,pressure:Gauge};
  return <div className="metric-grid ag-metrics">{variables.map(k=>{
    const Icon=icons[k],current=reading?.[k],prev=previous?.[k];
    const delta=typeof current==="number"&&typeof prev==="number"&&previous?.sessionId===reading?.sessionId&&previous?.stationId===reading?.stationId?current-prev:null;
    return <article className="panel metric" key={k} style={{"--metric-color":colors[k]} as CSSProperties}>
      <div className="metric-label"><Icon size={19}/><span>{labels[k]}</span></div>
      <div className="metric-value">{fmt(current)} <span>{units[k]}</span></div>
      <div className="metric-footer"><Badge tone={origin==="SIMULATION"?"amber":"green"}>{reading?.testTransport?`Prueba ${reading.testTransport} · SIMULATED`:reading?.dataKind??sourceNames[origin]}</Badge><Trend value={delta} unit={units[k]}/></div>
      <p className="metric-description">{reading?`${fullDate(reading.acquiredAt)} · ${age(reading.acquiredAt,now)}`:"En espera de registros"}</p>
    </article>;
  })}</div>;
}

export default function Station() {
  const [view,setView]=useState<View>("dashboard"),[origin,setOrigin]=useState<Origin>("SIMULATION");
  const [snapshot,setSnapshot]=useState<{scope:string;origin:Origin;data:AppSnapshot;receivedAt:number}|null>(null);
  const [configured,setConfigured]=useState(emptyConfig),initialized=useRef(false);
  const [range,setRange]=useState("60"),[session,setSession]=useState(""),[station,setStation]=useState("");
  const [from,setFrom]=useState(""),[to,setTo]=useState(""),[quality,setQuality]=useState(""),[order,setOrder]=useState("desc"),[page,setPage]=useState(0);
  const [busy,setBusy]=useState(false),[error,setError]=useState<{scope:string;message:string}|null>(null),[notice,setNotice]=useState("");
  const [forecast,setForecast]=useState<ExternalForecast|null>(null),[forecastError,setForecastError]=useState(""),[forecastLoading,setForecastLoading]=useState(false);
  const [variable,setVariable]=useState<typeof variables[number]>("temperature");
  const [selected,setSelected]=useState<Key[]>(columns.map(([k])=>k)),[delimiter,setDelimiter]=useState("semicolon");
  const [refreshCount,setRefreshCount]=useState(0);
  const base=new URLSearchParams({origin,order});
  if(station) base.set("station",station);
  if(session) {const [s,id]=session.split("|");base.set("station",s);base.set("session",id);}
  const historyParams=new URLSearchParams(base);
  if(from) historyParams.set("from",bogotaDate(from,false));
  if(to) historyParams.set("to",bogotaDate(to,true));
  if(quality) historyParams.set("quality",quality);
  const historyQuery=historyParams.toString();
  const snapshotQuery=(view==="history"?historyParams:base).toString();
  const scope=JSON.stringify([snapshotQuery,view,view==="history"?page:range]);
  const data=snapshot?.scope===scope?snapshot.data:null;
  const clock=snapshot?.receivedAt??0;
  const refresh=useCallback(async()=>{setRefreshCount(n=>n+1);},[]);
  useEffect(()=>{
    const controller=new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    const loop=async()=>{
      const p=new URLSearchParams(snapshotQuery);
      if(view==="history") p.set("page",String(page));
      else if(view==="dashboard") p.set("from",new Date(Date.now()-3600000).toISOString());
      else if(range!=="all") p.set("from",new Date(Date.now()-Number(range)*60000).toISOString());
      try {
        const next=await api<AppSnapshot>("snapshot?"+p,undefined,controller.signal);
        if(controller.signal.aborted) return;
        setSnapshot({scope,origin,data:next,receivedAt:Date.now()});
        if(!initialized.current) {setConfigured(next.sim.config);initialized.current=true;}
        setError(null);
      } catch(e) {
        if(!controller.signal.aborted) setError({scope,message:(e as Error).message});
      }
      if(!controller.signal.aborted) timer=setTimeout(loop,850);
    };
    void loop();
    return()=>{controller.abort();clearTimeout(timer);};
  },[snapshotQuery,view,range,page,origin,scope,refreshCount]);

  const loadForecast=useCallback(async()=>{
    setForecastLoading(true);
    setForecastError("");
    try {setForecast(await api<ExternalForecast>("forecast"));}
    catch(e){setForecastError((e as Error).message);}
    finally{setForecastLoading(false);}
  },[]);
  useEffect(()=>{if(view==="forecast"||view==="alerts") void loadForecast();},[view,loadForecast]);

  function go(next:View){setView(next);setNotice("");window.scrollTo({top:0,behavior:"instant"});}
  function mode(next:Origin){setOrigin(next);setSession("");setStation("");setPage(0);setNotice("");}
  async function control(action:string,config=configured) {
    setBusy(true);setNotice("");
    try {
      await api("simulation",{action,config});
      if(action==="reset"||action==="start") {setSession("");setStation("");setPage(0);}
      await refresh();
    } catch(e){setNotice((e as Error).message);}
    finally{setBusy(false);}
  }
  async function download(format:"csv"|"xlsx") {
    setBusy(true);setNotice("");
    try {
      const p=new URLSearchParams(historyQuery);
      p.set("format",format);p.set("delimiter",delimiter);p.set("columns",selected.join(","));
      const response=await fetch("/api/export?"+p);
      if(!response.ok) throw new Error((await response.json()).error);
      const blob=await response.blob();
      const url=URL.createObjectURL(blob),a=document.createElement("a");
      a.href=url;
      a.download=response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1]??`AgroEdge_${origin}_${calendar.format(Date.now())}.${format}`;
      document.body.append(a);a.click();a.remove();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      setNotice("Archivo descargado con el filtro y el orden actuales.");
    } catch(e){setNotice((e as Error).message);}
    finally{setBusy(false);}
  }
  async function importFile(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form=event.currentTarget,file=new FormData(form).get("archive");
    if(!(file instanceof File)||!file.size) {setNotice("Selecciona un archivo CSV o XLSX.");return;}
    const extension=file.name.split(".").at(-1)?.toLowerCase();
    if(extension!=="xlsx"&&extension!=="csv") {setNotice("Selecciona un archivo .csv o .xlsx.");return;}
    setBusy(true);setNotice("");
    try {
      const response=await fetch("/api/import?format="+extension,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:file});
      const result=await response.json();
      if(!response.ok) throw new Error(result.error);
      setNotice(`${result.inserted} lecturas importadas · ${result.duplicates} duplicados omitidos. Consulta el modo de origen del archivo.`);
      form.reset();await refresh();
    } catch(e){setNotice((e as Error).message);}
    finally {setBusy(false);}
  }
  const reading=data?.latest;
  const deviceState=origin==="SIMULATION"?(data?.sim.state==="RUNNING"?"Simulación activa":data?.sim.state==="PAUSED"?"Simulación en pausa":"Simulación detenida"):
    origin==="USB"?(data?.usb.state==="RECEIVING"||data?.connections.some(c=>c.state==="RECEIVING"&&c.stationId!==data.usb.stationId)?"Recibiendo por USB":data?.usb.state==="STALE"?"USB sin lecturas recientes":data?.usb.state==="OPEN"?"Puerto abierto · esperando lecturas":"USB · Consulta Conexión"):
      data?.connections.some(c=>c.state==="RECEIVING")?"Recibiendo por Wi-Fi":data?.connections.length?"Wi-Fi sin lecturas recientes":"Esperando ESP32 por Wi-Fi";
  const active=deviceState.startsWith("Recibiendo")||deviceState==="Simulación activa";
  const sessions=(snapshot?.origin===origin?snapshot.data.sessions:[]);
  const filterSessions=sessions.filter(x=>!station||x.stationId===station);
  const stations=[...new Set(sessions.map(s=>s.stationId))];
  const newestStations=stations.map(id=><option key={id} value={id}>{id}</option>);
  const sessionOptions=filterSessions.map(s=><option key={`${s.stationId}|${s.sessionId}`} value={`${s.stationId}|${s.sessionId}`}>{s.stationId} · {fullDate(String(s.first))} · {s.count} lecturas · {s.sessionId}</option>);
  const modeFilters=<div className="ag-controls">
    <label>Estación<select value={station} onChange={e=>{setStation(e.target.value);setSession("");setPage(0);}}><option value="">Todas</option>{newestStations}</select></label>
    <label className="ag-session">Sesión<select value={session} onChange={e=>{setSession(e.target.value);setPage(0);}}><option value="">Todas</option>{sessionOptions}</select></label>
  </div>;
  const title=sections.find(([key])=>key===view)![1];

  return <SidebarProvider className="app-shell">
    <StationNav view={view} onView={go}/>
    <main className="main-shell">
      <header className="topbar ag-topbar"><div className="ag-top-left"><SidebarTrigger aria-label="Abrir navegación"/><span>AgroEdge IA <span className="ag-note">/ Toca, Boyacá</span></span></div>
        <label className="ag-mode">Modo de funcionamiento<select value={origin} onChange={e=>mode(e.target.value as Origin)}>
          {Object.entries(modeNames).map(([id,label])=><option key={id} value={id}>{label}</option>)}
        </select></label>
      </header>
      <div className="main-content ag-workspace">
        <div className="ag-page-heading"><div><h1>{title}</h1><p>{descriptions[view]}</p></div>
          <div className="ag-status"><span className={"status-dot "+(active?"":"muted")}/><strong>{deviceState}</strong></div></div>
        {error?.scope===scope&&<p className="error-banner" role="alert">{error.message}</p>}
        {notice&&<p className="ag-feedback" role="status">{notice}</p>}
        {view==="dashboard"&&<>
          <ReadingCards reading={reading} previous={data?.previous} now={clock} origin={origin}/>
          <Panel className="ag-section ag-observation"><div><h2>Última lectura guardada</h2><p>{reading?`${reading.stationId} · Secuencia ${reading.sequence} · ${fullDate(reading.acquiredAt)}`:"La fuente seleccionada aún no tiene lecturas."}</p></div>
            <div className="ag-tags">{reading&&<><Badge tone={reading.quality==="VALID"?"green":"amber"}>{qualityNames[reading.quality]}</Badge><Badge tone="gray">{reading.origin}</Badge></>}<button className="button secondary" onClick={()=>go("history")}>Ver registros</button></div>
          </Panel>
          <ClimatePanel onForecast={()=>go("forecast")}/>
          {origin==="SIMULATION"?<Simulation sim={data?.sim} configured={configured} onChange={setConfigured} onAction={(a,c)=>void control(a,c)} busy={busy}/>:
            <ConnectionPanel snapshot={data} origin={origin} onRefresh={refresh}/>}
          <Panel className="ag-section"><div className="ag-heading"><div><h2>{labels[variable]}</h2><p>Última hora · {sourceNames[origin]}</p></div><button className="button secondary" onClick={()=>{setRange("60");go("monitor");}}>Ver monitoreo</button></div>
            <WeatherChart data={data} variable={variable} days={Number(range)>=1440||range==="all"}/></Panel>
        </>}
        {(view==="monitor"||view==="analysis"||view==="alerts")&&<Panel className="ag-section">
          <div className="ag-filterbar">{modeFilters}<label>Periodo<select value={range} onChange={e=>setRange(e.target.value)}>
            <option value="5">Últimos 5 minutos</option><option value="60">Última hora</option><option value="360">Últimas 6 horas</option>
            <option value="1440">Últimas 24 horas</option><option value="10080">Últimos 7 días</option><option value="all">Todo el historial</option>
          </select></label></div>
          {data?.truncated&&<p className="ag-note">El análisis muestra las 10 000 lecturas más recientes del filtro.</p>}
        </Panel>}
        {view==="monitor"&&<><div className="ag-tabbar" aria-label="Variable meteorológica">{variables.map(k=><button key={k} type="button" className={variable===k?"button primary":"button secondary"} aria-pressed={variable===k} onClick={()=>setVariable(k)}>{labels[k]}</button>)}</div>
          <Panel className="ag-section"><div className="ag-heading"><h2>{labels[variable]} ({units[variable]})</h2><Badge tone="gray">{sourceNames[origin]}</Badge></div>
            <WeatherChart data={data} variable={variable} days={Number(range)>=1440||range==="all"}/><p className="ag-note">Los huecos indican valores ausentes o saltos detectados en la secuencia.</p></Panel></>}
        {view==="analysis"&&<Analysis data={data}/>}
        {view==="forecast"&&<ForecastPanel forecast={forecast} error={forecastError} loading={forecastLoading} reload={()=>void loadForecast()}/>}
        {view==="tiny"&&<><Panel className="ag-section">{modeFilters}</Panel><InferencePanel reading={data?.inference??null} origin={origin}/></>}
        {view==="alerts"&&<Alerts readings={data?.anomalies??[]} latest={data?.latestInPeriod??null} origin={origin} forecast={forecastError?null:forecast}/>}
        {view==="connection"&&<ConnectionPanel snapshot={data} origin={origin} onRefresh={refresh}/>}
        {view==="history"&&<>
          <Panel className="ag-section">
            {modeFilters}
            <div className="ag-controls">
              <label>Desde (Bogotá)<input type="date" value={from} max={to||undefined} onChange={e=>{setFrom(e.target.value);setPage(0);}}/></label>
              <label>Hasta (Bogotá)<input type="date" value={to} min={from||undefined} onChange={e=>{setTo(e.target.value);setPage(0);}}/></label>
              <label>Calidad<select value={quality} onChange={e=>{setQuality(e.target.value);setPage(0);}}><option value="">Todas</option>{qualities.map(k=><option key={k} value={k}>{qualityNames[k]}</option>)}</select></label>
              <label>Orden<select value={order} onChange={e=>{setOrder(e.target.value);setPage(0);}}><option value="desc">Más recientes primero</option><option value="asc">Más antiguas primero</option></select></label>
              <button className="button secondary" onClick={()=>{setFrom("");setTo("");setQuality("");setSession("");setStation("");setPage(0);}}>Limpiar filtros</button>
            </div>
          </Panel>
          <Panel className="ag-section">
            <div className="ag-heading"><h2>{data?.history.total??0} registros</h2><Badge tone="gray">{sourceNames[origin]}</Badge></div>
            <div className="ag-table-scroll"><table className="ag-table"><thead><tr>{["Adquisición · COL","Estación / sesión","Sec.","Temp. (°C)","HR (%)","Presión (hPa)","Origen","Calidad"].map(h=><th key={h} scope="col">{h}</th>)}</tr></thead>
              <tbody>{data?.history.rows.map(r=><tr key={r.id}><td>{fullDate(r.acquiredAt)}</td><td>{r.stationId}<small>{r.sessionId}</small></td><td>{r.sequence}</td>
                <td>{fmt(r.temperature)}</td><td>{fmt(r.humidity)}</td><td>{fmt(r.pressure)}</td><td>{r.origin}<small>{r.dataKind}{r.testTransport&&` · Prueba ${r.testTransport}`}</small></td>
                <td><Badge tone={r.quality==="VALID"?"green":"amber"}>{qualityNames[r.quality]}</Badge>{r.missingBefore>0&&<small>{r.missingBefore} secuencias faltantes al recibir</small>}{r.issues.length>0&&<details><summary>Detalles</summary><ul>{r.issues.map(i=><li key={i}>{i}</li>)}</ul></details>}</td></tr>)}</tbody>
            </table></div>
            {!data?.history.total&&<Empty title="Sin lecturas para este filtro" detail="Cambia las fechas, selecciona otra sesión o importa un archivo de AgroEdge."/>}
            {!!data?.history.total&&<div className="ag-actions">
              <button className="button secondary" disabled={data.history.page===0} onClick={()=>setPage(data.history.page-1)}>Anterior</button>
              <span>Página {data.history.page+1} de {Math.ceil(data.history.total/data.history.size)}</span>
              <button className="button secondary" disabled={(data.history.page+1)*data.history.size>=data.history.total} onClick={()=>setPage(data.history.page+1)}>Siguiente</button>
            </div>}
          </Panel>
          <div className="ag-two">
            <Panel className="ag-section"><h2>Exportar el rango filtrado</h2>
              <details className="ag-options"><summary>Seleccionar columnas</summary><div className="ag-checkboxes">
                {columns.map(([k,label])=><label key={k} className="ag-check"><input type="checkbox" checked={selected.includes(k)} disabled={mandatory.some(x=>x===k)} onChange={e=>setSelected(prev=>e.target.checked?[...prev,k]:prev.filter(x=>x!==k))}/>{label}</label>)}
              </div></details>
              <label>Delimitador CSV<select value={delimiter} onChange={e=>setDelimiter(e.target.value)}><option value="semicolon">Punto y coma</option><option value="comma">Coma</option><option value="tab">Tabulador</option></select></label>
              <div className="ag-actions"><button className="button primary" disabled={busy||!data?.history.total} onClick={()=>void download("xlsx")}>Descargar Excel</button><button className="button secondary" disabled={busy||!data?.history.total} onClick={()=>void download("csv")}>Descargar CSV</button></div>
            </Panel>
            <Panel className="ag-section"><h2>Importar mediciones</h2><p>Selecciona un CSV UTF-8 o un Excel exportado por AgroEdge. Se conserva el origen y se omiten duplicados.</p>
              <form className="ag-import" onSubmit={e=>void importFile(e)}><label>Archivo de mediciones<input name="archive" type="file" accept=".csv,.xlsx" required/></label><button className="button secondary" disabled={busy}>Importar archivo</button></form>
            </Panel>
          </div>
          <Panel className="ag-section"><h2>Sesiones guardadas</h2>{!filterSessions.length?<p className="ag-note">Esta fuente aún no tiene sesiones guardadas.</p>:
            <ul className="ag-session-list">{filterSessions.slice(0,20).map(s=><li key={`${s.stationId}|${s.sessionId}`}><button className="button secondary" onClick={()=>{setSession(`${s.stationId}|${s.sessionId}`);setFrom("");setTo("");setQuality("");setPage(0);}}>{s.stationId} · {fullDate(String(s.first))}</button><span>{s.count} lecturas · {s.sessionId}</span></li>)}</ul>}
            {filterSessions.length>20&&<p className="ag-note">Se muestran las 20 sesiones recientes. El selector incluye todas.</p>}
          </Panel>
        </>}
        <footer className="page-footer"><span>AgroEdge IA · Toca, Boyacá</span><span>Hora de Colombia (America/Bogota)</span></footer>
      </div>
    </main>
  </SidebarProvider>;
}
function WeatherChart({data,variable,days}:{data:AppSnapshot|null;variable:typeof variables[number];days:boolean}) {
  if(!data?.series.some(r=>r[variable]!==null)) return <Empty title="Sin datos en este periodo" detail="Inicia la simulación, recibe una lectura o selecciona otro periodo."/>;
  if(data.series.filter(r=>r[variable]!==null).length===1) {
    const p=data.series.find(r=>r[variable]!==null)!;
    return <div className="ag-single-reading"><strong>{fmt(p[variable])} {units[variable]}</strong><span>{dateTime(p.ts)} · Se necesitan dos lecturas para trazar la serie.</span></div>;
  }
  return <SeriesChart data={data.series} variable={variable} height={278} days={days}/>;
}

