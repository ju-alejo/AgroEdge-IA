"use client";

import { useEffect, useState } from "react";
import type { ClimateFeed, Edition } from "../../lib/agroclima";
import archived from "../../examples/r5/boletin-verificado.json";

const dateOnly = new Intl.DateTimeFormat("es-CO", {
  day:"numeric", month:"long", year:"numeric", timeZone:"UTC"
});
const bogota = new Intl.DateTimeFormat("es-CO", {
  dateStyle:"medium", timeStyle:"short", timeZone:"America/Bogota"
});
const formatStamp = (stamp:string) => bogota.format(new Date(stamp));
const methods: Record<string, string> = {
  ARCHIVO_HTML:"archivo HTML", HTTPS:"consulta a NOAA", SYNC:"sincronización"
};

function Issue({item}:{item:Edition}) {
  return <article className="ag-issue">
    <div className="ag-heading"><h3>{item.status}</h3><time dateTime={item.published}>
      {dateOnly.format(new Date(item.published + "T12:00:00Z"))}</time></div>
    <p className="ag-issue-title">{item.title}</p>
    <p>{item.summary}</p>
    <p className="ag-note">{item.source} · {item.live_seen
      ? "Última consulta directa registrada: " + formatStamp(item.live_seen)
      : "HTML guardado · Procesado en Bogotá: " + formatStamp(item.last_seen)} · <a href={item.url} target="_blank" rel="noreferrer">
      Ver boletín en NOAA</a></p>
  </article>;
}

export function ClimateBulletins({feed, error, onForecast}:{
  feed:ClimateFeed|null; error:string; onForecast:()=>void
}) {
  const [latest, ...older] = feed?.editions ?? [];
  const run = feed?.lastRun;
  return <section className="panel ag-section ag-climate" aria-labelledby="ag-climate-heading">
    <div className="ag-heading"><div><h2 id="ag-climate-heading">Boletín agroclimático externo</h2>
      <p>Contexto estacional del Pacífico · El Niño y La Niña</p></div>
      <button className="button secondary" onClick={onForecast}>Ver lluvia prevista en Toca</button></div>
    {error && <p role="status" className="error-banner">{error}</p>}
    {feed?.bundled && <p className="ag-note">Boletín archivado incluido con la versión 0.2.0. Ejecuta el recolector para consultar la edición vigente.</p>}
    {latest ? <Issue item={latest}/> : <p>{feed
      ? "Aún no hay boletines guardados. Ejecuta el recolector R5 o importa una captura HTML."
      : error ? "Los boletines guardados podrán consultarse al restablecer la conexión local." : "Consultando el archivo de boletines…"}</p>}
    {older.length > 0 && <details className="ag-options"><summary>Ver versiones anteriores ({older.length})</summary>
      {older.map(item=><Issue key={item.revision} item={item}/>)}</details>}
    {run && <p className="ag-note">Última operación en AgroEdge (Bogotá): {formatStamp(run.at)} · {methods[run.method] ?? run.method}
      {run.outcome==="ERROR" && <> · Falló la actualización. {run.detail}</>}</p>}
    <p className="ag-note">Para planear las próximas 24 o 48 horas, consulta la lluvia prevista por Open-Meteo y las lecturas de tu estación.</p>
  </section>;
}

export default function ClimatePanel({onForecast}:{onForecast:()=>void}) {
  const [feed,setFeed] = useState<ClimateFeed>({bundled:true, editions:[archived], lastRun:null});
  const [error,setError] = useState("");
  useEffect(()=>{
    const controller = new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const response = await fetch("/api/agroclima",{signal:controller.signal, cache:"no-store"});
        if (!response.ok) throw new Error("No se pudo consultar el archivo agroclimático.");
        const result:ClimateFeed = await response.json();
        if (!controller.signal.aborted) { setFeed(result); setError(""); }
      } catch {
        if (!controller.signal.aborted) setError("No se pudo actualizar la información agroclimática.");
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh,60000);
      }
    }
    void refresh();
    return ()=>{controller.abort();clearTimeout(timer);};
  },[]);
  return <ClimateBulletins feed={feed} error={error} onForecast={onForecast}/>;
}
