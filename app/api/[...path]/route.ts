import { timingSafeEqual } from "node:crypto";
import { object } from "@/lib/domain";
import { transport } from "@/lib/measurements";
import { getStore } from "@/lib/store";
import { exportFile, normalizeDelimiter, parseFile } from "@/lib/transfer";
import { getForecast } from "@/lib/forecast";
import { getClimateFeed } from "@/lib/agroclima";
import { usb } from "@/lib/usb";

export const runtime="nodejs";
export const dynamic="force-dynamic";
const json=(value:unknown,status=200)=>Response.json(value,{status,headers:{"Cache-Control":"no-store"}});
const apiPath=(r:Request)=>new URL(r.url).pathname.replace(/^\/api\//,"").replace(/\/$/,"");
const safeMsg=(e:unknown)=>e instanceof Error?e.message:"No fue posible completar la operación.";
function browserUrl(r:Request) {
  const url=new URL(r.url),host=r.headers.get("host");
  return host?new URL(url.protocol+"//"+host):url;
}
const isLocal=(r:Request)=>["127.0.0.1","localhost","[::1]"].includes(browserUrl(r).hostname);

function authorized(r:Request) {
  const token=process.env.AGROEDGE_DEVICE_TOKEN;
  if(!token) return false;
  const sent=Buffer.from(r.headers.get("authorization")??"");
  const expected=Buffer.from("Bearer "+token);
  return sent.length===expected.length&&timingSafeEqual(sent,expected);
}
function localWrite(r:Request) {
  const url=browserUrl(r), origin=r.headers.get("origin");
  return isLocal(r)&&(!origin||origin===url.origin)&&r.headers.get("sec-fetch-site")!=="cross-site";
}
async function body(r:Request,max:number) {
  const reader=r.body?.getReader();
  if(!reader) throw new Error("La solicitud está vacía.");
  const pieces:Uint8Array[]=[];
  let size=0;
  while(true) {
    const {value,done}=await reader.read();
    if(done) break;
    size+=value.byteLength;
    if(size>max) {await reader.cancel();throw new Error("La solicitud supera el tamaño admitido.");}
    pieces.push(value);
  }
  return new Uint8Array(Buffer.concat(pieces));
}
async function payload(r:Request) {
  if(r.headers.get("content-type")?.split(";")[0]!=="application/json") throw new Error("Envía Content-Type: application/json.");
  return JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(await body(r,16384)));
}
export async function GET(request:Request) {
  const path=apiPath(request),p=new URL(request.url).searchParams;
  if(!isLocal(request)) return json({error:"Abre el panel desde localhost en el computador de la estación."},403);
  try {
    if(path==="agroclima") return json(getClimateFeed());
    if(path==="forecast") {
      try { return json(await getForecast()); }
      catch(e){return json({error:"Pronóstico externo no disponible. "+safeMsg(e),source:"EXTERNAL"},503);}
    }
    if(path==="usb/ports") return json({ports:await usb().ports()});
    if(path==="snapshot") return json({...getStore().snapshot(p),usb:usb().get(),wifiTimeout:Number(process.env.AGROEDGE_STALE_SECONDS??30)});
    if(path==="measurements") return json(getStore().query(p));
    if(path==="sessions") return json(getStore().sessions(transport(p.get("origin")??"SIMULATION")));
    if(path==="export") {
      const format=p.get("format");
      if(format!=="csv"&&format!=="xlsx") throw new Error("Selecciona CSV o XLSX.");
      const origin=transport(p.get("origin")??"SIMULATION"), {rows}=getStore().query(p,true);
      if(!rows.length) throw new Error("El filtro no tiene registros para exportar.");
      const now=new Date(), localDate=now.toLocaleDateString("en-CA",{timeZone:"America/Bogota"});
      const times=rows.map(r=>r.acquiredAt), direction=p.get("order")==="asc";
      const unique=(key:"stationId"|"sessionId")=>{const a=[...new Set(rows.map(r=>r[key]))];return a.length===1?a[0]:`${a.length} (véase Mediciones)`;};
      const bytes=await exportFile(rows,format,{cols:p.get("columns"),delimiter:normalizeDelimiter(p.get("delimiter")),meta:{
        "Origen":origin,"Condición":rows[0].dataKind,"Estación":unique("stationId"),"Sesión":unique("sessionId"),
        "Primera adquisición UTC":(direction?times[0]:times.at(-1))!,
        "Última adquisición UTC":(direction?times.at(-1):times[0])!,
        "Filtro desde UTC (inclusivo)":p.get("from")??"Sin filtro","Filtro hasta UTC (exclusivo)":p.get("to")??"Sin filtro",
        "Generado UTC":now.toISOString(),"Orden":direction?"Ascendente":"Descendente","Registros":rows.length}});
      const type=format==="csv"?"text/csv; charset=utf-8":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      return new Response(Uint8Array.from(bytes),{headers:{"Content-Type":type,"Content-Disposition":`attachment; filename="AgroEdge_${origin}_${localDate}.${format}"`,"Cache-Control":"no-store"}});
    }
    return json({error:"Ruta no encontrada."},404);
  } catch(e) { return json({error:safeMsg(e)},400); }
}

export async function POST(request:Request) {
  const path=apiPath(request);
  const live=path==="measurements/usb"||path==="measurements/wifi";
  if(live?!authorized(request):!localWrite(request)) return json({error:live?"Token de dispositivo inválido o sin configurar.":"Operación disponible desde el panel local."},403);
  try {
    if(live) {
      const via=path.endsWith("/wifi")?"WIFI":"USB";
      const value=await payload(request);
      try {
        const result=getStore().ingest(value,via);
        return json(result,result.status==="stored"?201:200);
      } catch(e) {
        getStore().recordConnectionError(via,value,safeMsg(e));
        throw e;
      }
    }
    if(path==="test/usb"||path==="test/wifi") {
      if(process.env.AGROEDGE_ALLOW_TESTS!=="1") return json({error:"El modo de pruebas está deshabilitado."},403);
      const result=getStore().ingest(await payload(request),"SIMULATION",path.endsWith("/wifi")?"WIFI":"USB");
      return json(result,result.status==="stored"?201:200);
    }
    if(path==="simulation") return json(getStore().control(await payload(request)));
    if(path==="usb") {
      const p=object(await payload(request));
      if(p.action==="start") return json(usb().start(p.port,p.baud));
      if(p.action==="stop") return json(usb().stop());
      throw new Error("Acción USB desconocida.");
    }
    if(path==="import") {
      const format=new URL(request.url).searchParams.get("format");
      if(format!=="csv"&&format!=="xlsx") throw new Error("Selecciona un archivo CSV o XLSX.");
      const rows=await parseFile(await body(request,25*1024*1024),format);
      return json(getStore().import(rows));
    }
    return json({error:"Ruta no encontrada."},404);
  } catch(e) {
    return json({error:safeMsg(e)},safeMsg(e).startsWith("Conflicto")?409:400);
  }
}

