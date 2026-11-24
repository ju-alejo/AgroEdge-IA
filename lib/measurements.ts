import { createHash } from "node:crypto";
import { bounds, identifier, object, origins, parseClassification, qualities, utc, variables,
  type Origin, type Reading, type Quality } from "./domain.ts";

export function transport(value: unknown): Origin {
  if (!origins.includes(value as Origin)) throw new Error("Selecciona SIMULATION, USB o WIFI.");
  return value as Origin;
}
function seq(value: unknown) {
  if (typeof value!=="number" || !Number.isSafeInteger(value) || value<1) throw new Error("sequence debe ser un entero positivo.");
  return value;
}
export function identity(v: Record<string, unknown>, origin: Origin) {
  if (v.schemaVersion!==1) throw new Error("schemaVersion debe ser 1.");
  const stationId=identifier(v.stationId,"stationId"), sessionId=identifier(v.sessionId,"sessionId"), sequence=seq(v.sequence);
  const id=v.id===undefined?"ag-"+createHash("sha256").update(JSON.stringify([origin,stationId,sessionId,sequence])).digest("hex").slice(0,32):identifier(v.id,"id");
  return {id,stationId,sessionId,sequence};
}
export function sourceKind(v: Record<string, unknown>, origin: Origin, testTransport?: "USB"|"WIFI") {
  if (v.origin!==undefined && v.origin!==(testTransport??origin)) throw new Error("El origen del JSON no coincide con el endpoint.");
  const kind=origin==="SIMULATION"?"SIMULATED":"REAL";
  if((v.dataKind!==undefined&&v.dataKind!==kind)||
      (v.testTransport!==undefined&&(!testTransport||v.testTransport!==testTransport))) {
    throw new Error("La condición de datos o el transporte de prueba no coinciden con el endpoint.");
  }
  return kind;
}
export function validateLive(v: Record<string, unknown>, origin: Origin, previousSequence: number,
  receivedAt: string, testTransport?: "USB"|"WIFI"): Reading {
  const ids=identity(v,origin);
  const kind=sourceKind(v,origin,testTransport);
  const hasTime=v.acquiredAt!==undefined && v.acquiredAt!==null;
  if (origin==="WIFI" && !hasTime) throw new Error("Wi-Fi requiere acquiredAt con un reloj sincronizado.");
  const acquiredAt=hasTime?utc(v.acquiredAt):receivedAt;
  const values={temperature:null,humidity:null,pressure:null} as Pick<Reading, typeof variables[number]>;
  const issues:string[]=[];
  let quality:Quality="VALID";
  for (const k of variables) {
    const n=v[k], [lo,hi]=bounds[k];
    if(n===null||n===undefined) {
      issues.push(`${k}: ausente`);
      if(quality==="VALID") quality="MISSING";
    } else if(typeof n!=="number"||!Number.isFinite(n)||n<lo||n>hi) {
      issues.push(`${k}: tipo o rango inválido (${lo} a ${hi})`);
      quality="INVALID";
    } else values[k]=n;
  }
  const missingBefore=Math.max(0,ids.sequence-previousSequence-1);
  const timeSource=origin==="SIMULATION"?"SIMULATION":hasTime?"DEVICE":"RECEIPT";
  return {schemaVersion:1,...ids,...values,origin,dataKind:kind,quality,missingBefore,issues,
    classification:parseClassification(v.classification,kind,origin==="USB"?receivedAt:undefined),
    acquiredAt,receivedAt,timeSource,...(testTransport?{testTransport}:{})};
}
export function validateImport(v: Record<string, unknown>): Reading {
  const origin=transport(v.origin), dataKind=origin==="SIMULATION"?"SIMULATED":"REAL";
  const ids=identity(v,origin);
  if(v.id===undefined||v.dataKind!==dataKind||!qualities.includes(v.quality as Quality)) throw new Error("Origen, condición de datos o calidad incompatible.");
  const timeSource=v.timeSource;
  if ((timeSource!=="SIMULATION"&&timeSource!=="DEVICE"&&timeSource!=="RECEIPT")||
      (dataKind==="SIMULATED")!==(timeSource==="SIMULATION")) throw new Error("Fuente horaria incompatible.");
  const acquiredAt=utc(v.acquiredAt), receivedAt=utc(v.receivedAt);
  if(timeSource==="RECEIPT"&&acquiredAt!==receivedAt) throw new Error("Las horas de adquisición y recepción deben coincidir si el reloj es RECEIPT.");
  const values={temperature:null,humidity:null,pressure:null} as Pick<Reading, typeof variables[number]>;
  for(const k of variables) {
    const n=v[k], [lo,hi]=bounds[k];
    if(n!==null && (typeof n!=="number"||!Number.isFinite(n)||n<lo||n>hi)) throw new Error(`${k}: valor o unidad incompatible`);
    values[k]=n;
  }
  const quality=v.quality as Quality;
  const incomplete=variables.some(k=>values[k]===null);
  if(incomplete!==(quality==="MISSING"||quality==="INVALID")) throw new Error("La calidad declarada contradice los valores ausentes.");
  if(typeof v.missingBefore!=="number" || !Number.isSafeInteger(v.missingBefore) || v.missingBefore<0 || v.missingBefore>=ids.sequence) throw new Error("Cantidad de secuencias faltantes inválida.");
  if(!Array.isArray(v.issues)||v.issues.some(e=>typeof e!=="string"||e.length>500)||v.issues.length>12) throw new Error("Observaciones de calidad inválidas.");
  const testTransport=v.testTransport;
  if(testTransport!==undefined && (dataKind!=="SIMULATED" || (testTransport!=="USB"&&testTransport!=="WIFI"))) throw new Error("Solo SIMULATED admite un transporte de prueba.");
  return {schemaVersion:1,...ids,...values,origin,dataKind,quality,missingBefore:v.missingBefore,issues:v.issues,
    classification:parseClassification(v.classification,dataKind,undefined,origin==="USB"?receivedAt:undefined),
    acquiredAt,receivedAt,timeSource,...(testTransport?{testTransport}:{})};
}

