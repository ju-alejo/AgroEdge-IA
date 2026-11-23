export const variables = ["temperature", "humidity", "pressure"] as const;
export type Variable = typeof variables[number];
export const origins = ["SIMULATION", "USB", "WIFI"] as const;
export type Origin = typeof origins[number];
export const labels = { temperature: "Temperatura ambiental", humidity: "Humedad relativa", pressure: "Presión atmosférica" };
export const units = { temperature: "°C", humidity: "%", pressure: "hPa" };
export const colors = { temperature: "#65e0ac", humidity: "#77b8ff", pressure: "#ccabff" };
export const bounds: Record<Variable, [number, number]> = { temperature: [-40, 85], humidity: [0, 100], pressure: [300, 1100] };
export const qualities = ["VALID", "MISSING", "INVALID", "ANOMALY"] as const;
export type Quality = typeof qualities[number];
export type TinyML = {
  source: "ESP32" | "SIMULATED";
  state: "OK" | "ERROR";
  label: string | null;
  score: number | null;
  modelVersion: string;
  inferredAt: string;
  inferenceUs?: number;
  inferenceTimeSource?: "RECEIPT";
  modelStatus?: "PRELIMINARY" | "TRAINED";
};
export type Reading = {
  schemaVersion: 1;
  id: string;
  stationId: string;
  sessionId: string;
  acquiredAt: string;
  receivedAt: string;
  timeSource: "DEVICE" | "RECEIPT" | "SIMULATION";
  sequence: number;
  temperature: number | null;
  humidity: number | null;
  pressure: number | null;
  origin: Origin;
  dataKind: "REAL" | "SIMULATED";
  quality: Quality;
  missingBefore: number;
  issues: string[];
  classification: TinyML | null;
  testTransport?: "USB" | "WIFI";
};
export const round = (n: number, d = 1) => Number(n.toFixed(d));
export const mean = (a: number[]) => a.length ? a.reduce((s,x) => s+x,0)/a.length : 0;
export function std(a: number[]) {
  const m = mean(a);
  return a.length > 1 ? Math.sqrt(a.reduce((s,x) => s+(x-m)**2,0)/(a.length-1)) : 0;
}
export function percentile(a: number[], p: number) {
  if (!a.length) return null;
  const s = [...a].sort((a,b) => a-b);
  const i = (s.length-1)*p;
  const l = Math.floor(i);
  return s[l]+(s[Math.ceil(i)]-s[l])*(i-l);
}
export function statistics(rows: Reading[]) {
  return Object.fromEntries(variables.map(k => {
    const a = rows.filter(r => r.quality === "VALID" || r.quality === "ANOMALY").flatMap(r => r[k] === null ? [] : [r[k]]);
    return [k, {count:a.length, mean:a.length?round(mean(a),2):null,
      min:a.reduce<number|null>((m,x)=>m===null?x:Math.min(m,x),null),
      max:a.reduce<number|null>((m,x)=>m===null?x:Math.max(m,x),null),
      median:percentile(a,.5), std:a.length?round(std(a),2):null,
      p10:percentile(a,.1), p90:percentile(a,.9), p95:percentile(a,.95)}];
  })) as Record<Variable, {count:number; mean:number|null; min:number|null; max:number|null; median:number|null; std:number|null; p10:number|null; p90:number|null; p95:number|null}>;
}
export function pearson(a: number[], b: number[]) {
  if (a.length<3 || a.length!==b.length) return null;
  const ma=mean(a), mb=mean(b);
  const den=Math.sqrt(a.reduce((s,x)=>s+(x-ma)**2,0)*b.reduce((s,x)=>s+(x-mb)**2,0));
  return den?round(a.reduce((s,x,i)=>s+(x-ma)*(b[i]-mb),0)/den,3):null;
}
export function correlations(rows: Reading[]) {
  const clean = rows.filter(r=>r.quality==="VALID");
  if (new Set(clean.map(r=>r.stationId)).size>1) return [];
  const pairs: [Variable, Variable][] = [["temperature","humidity"],["temperature","pressure"],["humidity","pressure"]];
  return pairs.map(([x,y])=>({x,y,n:clean.length,r:pearson(clean.map(r=>r[x] as number),clean.map(r=>r[y] as number))}));
}
const floors = {temperature:.25, humidity:1, pressure:.35};
export function anomalies(values: Record<Variable, number|null>, recent: Reading[]) {
  if (recent.length<15) return [];
  return variables.flatMap(k => {
    const v=values[k];
    if(v===null) return [];
    const past=recent.map(r=>r[k] as number);
    const z=Math.abs(v-mean(past))/Math.max(std(past),floors[k]);
    return z>3.5 ? [`${labels[k]} se apartó ${round(z)} desviaciones de las ${past.length} lecturas válidas anteriores.`] : [];
  });
}
export function utc(value: unknown) {
  if (typeof value !== "string") throw new Error("Usa una fecha ISO 8601 con zona horaria.");
  const match = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d{1,3})?(Z|[+-]\d\d:\d\d)$/.exec(value);
  if (!match || !Number.isFinite(Date.parse(value))) throw new Error("Usa una fecha ISO 8601 con zona horaria.");
  const [, y, m, d, h, min, sec] = match;
  const check = new Date(`${y}-${m}-${d}T00:00:00Z`);
  if (check.getUTCDate()!==Number(d) || Number(h)>23 || Number(min)>59 || Number(sec)>59) throw new Error("La fecha u hora no existe.");
  return new Date(value).toISOString();
}
export function identifier(value: unknown, name: string) {
  if (typeof value !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$/.test(value)) {
    throw new Error(`${name} debe tener de 1 a 100 letras ASCII, números, puntos, guiones, guiones bajos o dos puntos.`);
  }
  return value;
}
export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value!=="object" || Array.isArray(value)) throw new Error("Se esperaba un objeto JSON.");
  return value as Record<string, unknown>;
}
export function parseClassification(raw: unknown, kind: Reading["dataKind"], usbReceipt?: string, importReceipt?: string): TinyML|null {
  if (raw===null || raw===undefined) return null;
  const c=object(raw);
  const source=kind==="REAL"?"ESP32":"SIMULATED";
  if(c.source!==source || (c.state!=="OK"&&c.state!=="ERROR")) throw new Error("Fuente o estado TinyML incompatible.");
  const modelVersion=identifier(c.modelVersion,"modelVersion");
  const {inferenceUs, modelStatus}=c;
  if(inferenceUs!==undefined && (typeof inferenceUs!=="number" || !Number.isSafeInteger(inferenceUs) || inferenceUs<0)) {
    throw new Error("inferenceUs debe ser un entero no negativo en microsegundos.");
  }
  if(modelStatus!==undefined && (source!=="ESP32" || (modelStatus!=="PRELIMINARY" && modelStatus!=="TRAINED"))) {
    throw new Error("Estado de entrenamiento TinyML incompatible.");
  }
  const fallback=c.inferredAt===undefined && source==="ESP32" && usbReceipt!==undefined;
  const inferredAt=fallback?usbReceipt:utc(c.inferredAt);
  if(c.inferenceTimeSource!==undefined && (c.inferenceTimeSource!=="RECEIPT" || !importReceipt || inferredAt!==importReceipt || source!=="ESP32")) {
    throw new Error("Fuente horaria de inferencia incompatible.");
  }
  const metadata: Pick<TinyML,"modelVersion"|"inferredAt"|"inferenceUs"|"inferenceTimeSource"|"modelStatus">={
    modelVersion,inferredAt,...(inferenceUs===undefined?{}:{inferenceUs}),
    ...(fallback||c.inferenceTimeSource==="RECEIPT"?{inferenceTimeSource:"RECEIPT" as const}:{}),
    ...(modelStatus===undefined?{}:{modelStatus})};
  if(c.state==="ERROR") {
    if(c.label!==null||c.score!==null) throw new Error("Una inferencia ERROR debe traer label y score nulos.");
    return {source,state:c.state,label:null,score:null,...metadata};
  }
  if (typeof c.label!=="string" || !c.label.trim() || c.label.length>100 || /[\u0000-\u001f]/.test(c.label)
      || typeof c.score!=="number" || !Number.isFinite(c.score) || c.score<0 || c.score>1) {
    throw new Error("TinyML necesita una clase y una puntuación entre 0 y 1.");
  }
  return {source,state:c.state,label:c.label,score:c.score,...metadata};
}

