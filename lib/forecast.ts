export const provider = "Open-Meteo";
const hour = 3600000;
const keys = ["temperature_2m","precipitation","precipitation_probability"] as const;
type Hour = {end:string; temperature:number|null; precipitation:number|null; probability:number|null};
type Forecast = {source:"EXTERNAL";provider:string;fetchedAt:string;location:{latitude:number;longitude:number};hourly:Hour[];
  horizons:{hours:number; from:string;to:string; precipitation:number|null;minTemperature:number|null;maxTemperature:number|null;maxProbability:number|null}[]};

const finite=(v:unknown,lo:number,hi:number)=>typeof v==="number"&&Number.isFinite(v)&&v>=lo&&v<=hi?v:null;
export function parseForecast(input:unknown,point:Forecast["location"],now:number):Forecast {
  const start=Math.floor(now/hour)*hour, end=start+48*hour;
  const data=input as {hourly?:Record<string,unknown[]>;hourly_units?:Record<string,string>} | null;
  if(!data?.hourly||!Array.isArray(data.hourly.time)||keys.some(k=>!Array.isArray(data.hourly![k]))
      ||data.hourly_units?.precipitation!=="mm"||data.hourly_units?.temperature_2m!=="°C"||data.hourly_units?.precipitation_probability!=="%") {
    throw new Error("El servicio devolvió un formato meteorológico incompleto o incompatible.");
  }
  const hourly=data.hourly.time.flatMap((t,i)=>{
    if(typeof t!=="number"||t*1000<=start||t*1000>end||t*1000%hour!==0) return [];
    return [{end:new Date(t*1000).toISOString(),temperature:finite(data.hourly![keys[0]][i],-100,100),
      precipitation:finite(data.hourly![keys[1]][i],0,1000),probability:finite(data.hourly![keys[2]][i],0,100)}];
  }).sort((a,b)=>a.end.localeCompare(b.end));
  if(hourly.length!==48||new Set(hourly.map(h=>h.end)).size!==48) throw new Error("El proveedor no entregó 48 horas consecutivas.");
  const horizons=[24,48].map(hours=>{
    const rows=hourly.slice(0,hours);
    const temp=rows.map(r=>r.temperature);
    const rain=rows.map(r=>r.precipitation);
    const probability=rows.map(r=>r.probability);
    const complete=(values:(number|null)[])=>values.every(v=>v!==null);
    return {hours,from:new Date(start).toISOString(),to:rows.at(-1)!.end,
      precipitation:complete(rain)?Math.round((rain as number[]).reduce((a,b)=>a+b,0)*10)/10:null,
      minTemperature:complete(temp)?Math.min(...temp as number[]):null,maxTemperature:complete(temp)?Math.max(...temp as number[]):null,
      maxProbability:complete(probability)?Math.max(...probability as number[]):null};
  });
  return {source:"EXTERNAL",provider,fetchedAt:new Date(now).toISOString(),location:point,hourly,horizons};
}
let cache:Forecast|undefined;
let pending:Promise<Forecast>|undefined;

export async function getForecast() {
  const now=Date.now();
  if(cache&&now-Date.parse(cache.fetchedAt)<15*60000) return cache;
  if(pending) return pending;
  const point={latitude:Number(process.env.AGROEDGE_LAT??"5.56112"),longitude:Number(process.env.AGROEDGE_LON??"-73.18294")};
  if(finite(point.latitude,-90,90)===null||finite(point.longitude,-180,180)===null) throw new Error("Coordenadas de pronóstico inválidas.");
  const url=new URL("https://api.open-meteo.com/v1/forecast");
  url.search=new URLSearchParams({latitude:String(point.latitude),longitude:String(point.longitude),
    hourly:keys.join(","),forecast_hours:"49",timezone:"GMT",timeformat:"unixtime"}).toString();
  pending=(async()=>{
    const res=await fetch(url,{signal:AbortSignal.timeout(6500),cache:"no-store"});
    if(!res.ok) throw new Error(`El servicio meteorológico respondió HTTP ${res.status}.`);
    return cache=parseForecast(await res.json(),point,now);
  })();
  try { return await pending; } finally { pending=undefined; }
}

