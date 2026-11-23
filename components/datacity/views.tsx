"use client";

import { useState } from "react";
import { Activity, CloudRain, TriangleAlert, Wifi } from "lucide-react";
import { api, Badge, Empty, fmt, Panel, ScatterPlot, SeriesChart } from "./shared";
import { fullDate, sourceNames, type AppSnapshot, type ExternalForecast } from "./station";
import { colors, labels, units, variables, type Origin, type Reading } from "@/lib/domain";

export function ForecastPanel({forecast,error,loading,reload}:{forecast:ExternalForecast|null;error:string;loading:boolean;reload:()=>void}) {
  if(!forecast||error) return <Panel className="ag-section">
    <div className="ag-heading"><h2>Consulta externa</h2><Badge tone="blue">Open-Meteo · EXTERNAL</Badge></div>
    <Empty title={loading?"Consultando el pronóstico":"Pronóstico no disponible"} detail={error||"La consulta requiere conexión a Internet."}/>
    <button className="button secondary" disabled={loading} onClick={reload}>Volver a consultar</button>
  </Panel>;
  return <div className="ag-detail-grid">
    {forecast.horizons.map(f=><Panel className="ag-section ag-forecast" key={f.hours}>
      <div className="ag-heading"><h2><CloudRain size={20}/> {f.hours} horas</h2><Badge tone="blue">EXTERNAL</Badge></div>
      <strong className="ag-large">{fmt(f.precipitation)} <small>mm</small></strong>
      <p>Precipitación acumulada prevista</p>
      <dl className="ag-dl">
        <div><dt>Temperatura mín. / máx.</dt><dd>{fmt(f.minTemperature)} / {fmt(f.maxTemperature)} °C</dd></div>
        <div><dt>Probabilidad horaria máxima</dt><dd>{fmt(f.maxProbability,0)} %</dd></div>
        <div><dt>Periodo en Colombia</dt><dd>{fullDate(f.from)} – {fullDate(f.to)}</dd></div>
      </dl>
    </Panel>)}
    <Panel className="ag-section ag-span">
      <div className="ag-heading"><div><h2>Precipitación por hora</h2><p>Acumulado en los 60 minutos que terminan a la hora indicada.</p></div>
        <button className="button secondary" disabled={loading} onClick={reload}>Actualizar pronóstico</button></div>
      <details className="ag-options"><summary>Ver las 48 horas</summary>
        <div className="ag-table-scroll"><table className="ag-table"><thead><tr><th>Hora de cierre · COL</th><th>Precipitación (mm)</th><th>Probabilidad (%)</th><th>Temperatura (°C)</th></tr></thead>
          <tbody>{forecast.hourly.map(row=><tr key={row.end}><td>{fullDate(row.end)}</td><td>{fmt(row.precipitation)}</td><td>{fmt(row.probability,0)}</td><td>{fmt(row.temperature)}</td></tr>)}</tbody></table></div>
      </details>
      <p className="ag-note">Fuente <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> · Consulta {fullDate(forecast.fetchedAt)} · Punto de referencia {forecast.location.latitude}, {forecast.location.longitude}.</p>
    </Panel>
  </div>;
}

export function InferencePanel({reading,origin}:{reading:Reading|null;origin:Origin}) {
  const result=reading?.classification;
  return <Panel className="ag-section">
    <div className="ag-heading"><h2>Resultado de inferencia</h2><Badge tone={origin==="SIMULATION"?"amber":"blue"}>{origin==="SIMULATION"?"SIMULATED":"ESP32"}</Badge></div>
    {!result?<Empty title="Sin inferencias recibidas" detail={origin==="SIMULATION"?"Activa el ejemplo TinyML e inicia una sesión de simulación.":"La inferencia aparece cuando el ESP32 envía el objeto classification junto con una medición."}/>:
      <dl className="ag-dl">
        <div><dt>Estado de inferencia</dt><dd>{result.state==="OK"?"Procesada":"Error informado por el dispositivo"}</dd></div>
        <div><dt>Clase</dt><dd>{result.label??"—"}</dd></div>
        <div><dt>Puntuación</dt><dd>{fmt(result.score,3)}</dd></div>
        <div><dt>Versión del modelo</dt><dd>{result.modelVersion}</dd></div>
        <div><dt>{result.inferenceTimeSource==="RECEIPT"?"Hora de recepción USB":"Momento de la inferencia"}</dt><dd>{fullDate(result.inferredAt)}</dd></div>
        {result.inferenceUs!==undefined&&<div><dt>Latencia de clasificación</dt><dd>{result.inferenceUs} µs</dd></div>}
        <div><dt>Estación y lectura</dt><dd>{reading.stationId} · sec. {reading.sequence}</dd></div>
      </dl>}
    <p className="ag-note">{origin==="SIMULATION"?"La clase y la puntuación son valores de demostración.":result?.modelStatus==="PRELIMINARY"?
      "Modelo preliminar con referencias de humedad ambiental definidas para probar la integración. La puntuación expresa la separación entre clases.":
      "La puntuación corresponde a la salida reportada por el dispositivo."}</p>
  </Panel>;
}

export function Alerts({readings,latest,origin,forecast}:{readings:Reading[];latest:Reading|null;origin:Origin;forecast:ExternalForecast|null}) {
  const external=forecast?.horizons[0];
  return <div className="ag-detail-grid">
    <Panel className="ag-section">
      <div className="ag-heading"><h2>Lecturas de la estación</h2><Badge tone={origin==="SIMULATION"?"amber":"blue"}>{sourceNames[origin]}</Badge></div>
      {latest?.quality==="VALID"&&<p>Última lectura {fullDate(latest.acquiredAt)} · {latest.stationId} · {latest.origin} / {latest.dataKind}. Se registraron {fmt(latest.humidity)} % de humedad ambiental. Verifica la humedad del suelo en el lote si vas a revisar el riego.</p>}
      {readings.length?<ul className="ag-alerts">{readings.map(r=><li key={r.id}><TriangleAlert size={18}/><div>
        <strong>{r.stationId} · secuencia {r.sequence}</strong><small>{r.origin} · {r.dataKind} · {fullDate(r.acquiredAt)}</small>
        {r.issues.map(i=><p key={i}>{i}</p>)}{r.missingBefore>0&&<p>Se detectaron {r.missingBefore} secuencias faltantes al recibir.</p>}
        <p>{r.quality==="ANOMALY"?"Contrasta el cambio con lecturas consecutivas y verifica la ubicación del sensor.":"Revisa el sensor, el cableado y el intervalo de envío."}</p>
      </div></li>)}</ul>:<Empty title="Sin incidencias en el periodo" detail="Aquí aparecen las lecturas incompletas, los saltos de secuencia y los cambios atípicos."/>}
    </Panel>
    <Panel className="ag-section">
      <div className="ag-heading"><h2>Lluvia prevista</h2><Badge tone="blue">Open-Meteo · EXTERNAL</Badge></div>
      {external?.precipitation!==undefined&&external.precipitation!==null?<><p>Acumulado previsto de {fmt(external.precipitation)} mm para el periodo de 24 h. Consulta {fullDate(forecast?.fetchedAt)}.</p>
        <p>{external.precipitation>0?"Consulta en qué horas se espera lluvia y comprueba la humedad del suelo antes de decidir el riego.":"Comprueba la humedad del suelo y las condiciones en el lote antes de decidir el riego."}</p></>:<p>Precipitación externa pendiente o no disponible.</p>}
      <p className="ag-note">Orientación para contrastar con una observación en el lote.</p>
    </Panel>
  </div>;
}

const statuses:Record<string,string>={DISCONNECTED:"Desconectado",OPENING:"Abriendo puerto",OPEN:"Puerto abierto · esperando lecturas",
  RECONNECTING:"Intentando reconectar",RECEIVING:"Recibiendo mediciones",STALE:"Sin comunicación reciente",ERROR:"Error del dispositivo"};
export function ConnectionPanel({snapshot,origin,onRefresh}:{snapshot:AppSnapshot|null;origin:Origin;onRefresh:()=>Promise<void>}) {
  const [ports,setPorts]=useState<{port:string;description:string}[]>([]),[port,setPort]=useState(""),[baud,setBaud]=useState(115200);
  const [error,setError]=useState(""),[busy,setBusy]=useState(false);
  const usb=snapshot?.usb;
  async function execute(fn:()=>Promise<void>) {
    setBusy(true);setError("");
    try {await fn();}
    catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }
  if(origin==="SIMULATION") return <Panel className="ag-section"><Empty title="Estación en simulación" detail="Selecciona adquisición por USB o por Wi-Fi en el encabezado para configurar una conexión física."/></Panel>;
  if(origin==="WIFI") return <Panel className="ag-section">
    <div className="ag-heading"><h2><Wifi size={20}/> Recepción en la red local</h2><Badge tone="blue">WIFI</Badge></div>
    <p>Configura el ESP32 con la IP real del computador y envía las lecturas a <code>/api/measurements/wifi</code>. El modo LAN y el token se configuran en el README.</p>
    <p className="ag-note">La comunicación se marca interrumpida después de {snapshot?.wifiTimeout??30} s sin una lectura nueva.</p>
    {snapshot?.connections.length?<ul className="ag-alerts">{snapshot.connections.map(c=><li key={c.stationId}><Activity size={18}/><div><strong>{c.stationId} · {statuses[c.state]??c.state}</strong>
      <small>Última recepción {fullDate(c.lastReading)}</small>{c.error&&<p role="alert">{c.error}</p>}</div></li>)}</ul>:
      <p className="ag-note">En espera de la primera lectura autenticada.</p>}
  </Panel>;
  return <Panel className="ag-section">
    <div className="ag-heading"><div><h2>Puerto serial local</h2><p>Arduino UNO o ESP32 conectado por USB.</p></div><Badge tone={usb?.state==="RECEIVING"?"green":"gray"}>{statuses[usb?.state??"DISCONNECTED"]}</Badge></div>
    <div className="ag-controls">
      <label>Puerto COM<input value={port} onChange={e=>setPort(e.target.value)} list="agro-ports" placeholder="Selecciona tu puerto" autoComplete="off"/>
        <datalist id="agro-ports">{ports.map(p=><option key={p.port} value={p.port}>{p.description}</option>)}</datalist></label>
      <label>Baudios<select value={baud} onChange={e=>setBaud(Number(e.target.value))}>{[9600,19200,57600,115200,230400].map(b=><option key={b}>{b}</option>)}</select></label>
      <button className="button secondary" disabled={busy} onClick={()=>void execute(async()=>{const r=await api<{ports:typeof ports}>("usb/ports");setPorts(r.ports);setPort(port||r.ports[0]?.port||"");if(!r.ports.length)setError("No se detectaron puertos seriales.");})}>Buscar puertos</button>
      <button className="button primary" disabled={busy||!port.trim()} onClick={()=>void execute(async()=>{await api("usb",{action:"start",port:port.trim(),baud});await onRefresh();})}>Conectar USB</button>
      <button className="button secondary" disabled={busy||!usb?.port||usb.state==="DISCONNECTED"} onClick={()=>void execute(async()=>{await api("usb",{action:"stop"});await onRefresh();})}>Desconectar</button>
    </div>
    {error&&<p role="alert" className="ag-feedback">{error}</p>}
    {usb?.error&&<p role="alert" className="ag-feedback">{usb.error}</p>}
    <p className="ag-note">Puerto seleccionado {usb?.port??"—"} · Última recepción serial {fullDate(usb?.lastReading)}{usb?.stationId&&` · ${usb.stationId}`}.</p>
    {snapshot?.connections.filter(c=>c.stationId!==usb?.stationId).map(c=><p className="ag-note" key={c.stationId}>Servicio USB externo · {c.stationId} · {statuses[c.state]} · {fullDate(c.lastReading)} {c.error}</p>)}
  </Panel>;
}

export function Analysis({data}:{data:AppSnapshot|null}) {
  const [pair,setPair]=useState("0"),[question,setQuestion]=useState("summary");
  const c=data?.correlations[Number(pair)];
  const s=data?.stats;
  if(!s||!variables.some(k=>s[k].count)) return <Panel className="ag-section"><Empty title="Aún no hay valores para analizar" detail="Selecciona otra estación, otra sesión o un intervalo más amplio."/></Panel>;
  const anomalies=data?.anomalies.length??0;
  return <div className="ag-detail-grid">
    <Panel className="ag-section ag-span"><div className="ag-heading"><h2>Estadísticas del periodo</h2><span className="ag-note">Lecturas completas, incluidas las atípicas</span></div>
      <div className="ag-table-scroll"><table className="ag-table"><thead><tr>{["Variable","N","Promedio","Mínimo","Máximo","Mediana","Desv. estándar","P10","P90","P95"].map(t=><th key={t}>{t}</th>)}</tr></thead>
        <tbody>{variables.map(k=>{const v=s[k];return <tr key={k}><th scope="row" style={{color:colors[k]}}>{labels[k]} ({units[k]})</th><td>{v.count}</td>{[v.mean,v.min,v.max,v.median,v.std,v.p10,v.p90,v.p95].map((n,i)=><td key={i}>{fmt(n,2)}</td>)}</tr>;})}</tbody></table></div>
    </Panel>
    <Panel className="ag-section"><h2>Consulta rápida de datos</h2>
      <label>Pregunta<select value={question} onChange={e=>setQuestion(e.target.value)}><option value="summary">¿Cuáles fueron los promedios?</option><option value="range">¿Cuánto varió la presión?</option><option value="alerts">¿Qué incidentes se detectaron?</option></select></label>
      <p>{question==="summary"?variables.map(k=>`${labels[k]} ${fmt(s[k].mean,2)} ${units[k]}`).join(" · "):
        question==="range"?`Presión entre ${fmt(s.pressure.min,2)} y ${fmt(s.pressure.max,2)} hPa.`:
        `${anomalies} incidencias recientes visibles en Alertas para el periodo consultado.`}</p>
    </Panel>
    <Panel className="ag-section"><h2>Correlación de Pearson</h2>
      {c?<><label>Variables<select value={pair} onChange={e=>setPair(e.target.value)}>{data!.correlations.map((v,i)=><option key={i} value={i}>{labels[v.x]} / {labels[v.y]}</option>)}</select></label>
        <p>r = {fmt(c.r,3)} · {c.n} lecturas válidas</p><ScatterPlot data={data!.series} x={c.x} y={c.y}/>
        <p className="ag-note">Se requieren al menos tres lecturas y variación en ambas variables.</p></>:<p>Selecciona una estación para explorar la relación entre variables.</p>}
    </Panel>
    <Panel className="ag-section ag-span">
      <div className="ag-heading"><h2>Tendencia local a 30 minutos</h2><Badge tone="gray">Regresión lineal</Badge></div>
      {data?.trend.length?<div className="ag-trend-grid">{data.trend.map(t=><article key={t.variable}><h3>{labels[t.variable]}</h3>
        <p>Estimación {fmt(t.predicted)} {units[t.variable]} · error retrospectivo {fmt(t.mae,2)} {units[t.variable]}</p>
        <SeriesChart data={t.points.map(p=>({ts:p.ts,[t.variable]:p.value}))} variable={t.variable} height={168} future/>
      </article>)}</div>:<p>Requiere al menos 20 minutos distintos de lecturas válidas de una sola sesión y estación durante la última hora.</p>}
    </Panel>
  </div>;
}

