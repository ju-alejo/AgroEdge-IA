import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";

const localForecastUrl = "https://eltiempoen.net/colombia/el-tiempo-en-toca";
export type LocalForecast = {
  fetchedAt:string; method:string; url:string;
  hours:{validAt:string;sky:string|null;temperatureC:number|null;precipitationMm:number|null;
    probabilityPct:number|null;windKmh:number|null;humidityPct:number|null}[];
};

export function getLocalForecast():LocalForecast|null {
  const file=resolve(process.env.AGROEDGE_R5_DIR||"data","pronostico-toca.sqlite");
  if(!existsSync(file)) return null;
  const database=new DatabaseSync(file,{readOnly:true});
  try {
    if(database.prepare("PRAGMA application_id").get()?.application_id!==0x41474643) throw new Error("Base de pronóstico local incompatible.");
    const row=database.prepare("SELECT fetched_at,method,payload FROM snapshots ORDER BY fetched_at DESC LIMIT 1").get();
    return row?{fetchedAt:String(row.fetched_at),method:String(row.method),url:localForecastUrl,hours:JSON.parse(String(row.payload))}:null;
  } finally { database.close(); }
}
