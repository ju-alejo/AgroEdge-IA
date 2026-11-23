import { object, round, utc } from "./domain.ts";

export const scenarios = {
  balanced: { label: "Condiciones estables", temperature: 16, humidity: 68, pressure: 735 },
  dry: { label: "Condiciones secas", temperature: 20, humidity: 42, pressure: 738 },
  humid: { label: "Condiciones húmedas", temperature: 13, humidity: 88, pressure: 732 },
  temperature: { label: "Cambio de temperatura", temperature: 16, humidity: 69, pressure: 735 },
  pressure: { label: "Variación de presión", temperature: 16, humidity: 68, pressure: 735 },
};
export type Scenario = keyof typeof scenarios;
export type SimConfig = {seed: number; scenario: Scenario; intervalMs: number; variation: number; tinyML: boolean};

export function simulationConfig(value: unknown): SimConfig {
  const v=object(value);
  if(typeof v.seed!=="number" || !Number.isInteger(v.seed) || v.seed<0 || v.seed>0xffffffff) throw new Error("La semilla debe ser un entero de 0 a 4294967295.");
  if(typeof v.scenario!=="string" || !Object.hasOwn(scenarios,v.scenario)) throw new Error("Escenario desconocido.");
  if(typeof v.intervalMs!=="number" || ![500,1000,2000,5000,10000].includes(v.intervalMs)) throw new Error("Velocidad no admitida.");
  if(typeof v.variation!=="number" || !Number.isFinite(v.variation) || v.variation<0 || v.variation>2) throw new Error("La amplitud debe estar entre 0 y 2.");
  if(typeof v.tinyML!=="boolean") throw new Error("Selecciona si deseas el ejemplo TinyML.");
  return {seed:v.seed,scenario:v.scenario as Scenario,intervalMs:v.intervalMs,variation:v.variation,tinyML:v.tinyML};
}
function noise(n: number, seed: number, channel: number) {
  let x = (Math.imul(n, 0x9e3779b1) ^ seed ^ Math.imul(channel,0x85ebca6b)) >>> 0;
  x = Math.imul(x ^ x >>> 16, 0x7feb352d);
  x = Math.imul(x ^ x >>> 15, 0x846ca68b);
  return ((x ^ x >>> 16) >>> 0)/0xffffffff - .5;
}
// Adapts DataCity's deterministic cycle and noise. Overlapping noise windows
// and smooth scenario envelopes make consecutive samples temporally related.
export function synthetic(config: SimConfig, sequence: number, capturedAt: string) {
  const s=scenarios[config.scenario];
  const phase=sequence/36;
  const cycle=Math.sin(phase);
  const spike=Math.sin(sequence/28);
  const noiseAt=(channel:number)=>Array.from({length:8},(_,i)=>noise(sequence-i,config.seed,channel)).reduce((a,b)=>a+b,0)/8;
  const v=config.variation;
  const tempShift=config.scenario==="temperature"?4*spike:0;
  const pressShift=config.scenario==="pressure"?6*Math.sin(sequence/24):0;
  const humidity=round(Math.max(0,Math.min(100,s.humidity+v*(-4*cycle+noiseAt(2)*2))));
  return {
    acquiredAt: utc(capturedAt),
    temperature:round(s.temperature+v*(1.6*cycle+tempShift+noiseAt(1)*.6)),
    humidity,
    pressure:round(s.pressure+v*(.8*Math.sin(phase*.6)+pressShift+noiseAt(3)*.4)),
    classification:config.tinyML?{source:"SIMULATED",state:"OK",label:humidity>=75?"Ejemplo · ambiente húmedo":"Ejemplo · ambiente moderado",
      score:.5,modelVersion:"demo-sin-modelo",inferredAt:capturedAt}:null,
  };
}

