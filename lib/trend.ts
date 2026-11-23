import { mean, round, variables, type Reading } from "./domain.ts";

// DataCity's 30-minute regression, using averages per minute and a held-out diagnostic.
export function predict(rows:Reading[]) {
  const clean=rows.filter(r=>r.quality==="VALID");
  if(!clean.length||new Set(clean.map(r=>r.stationId+"|"+r.sessionId)).size>1) return [];
  const end=Date.parse(clean.at(-1)!.acquiredAt),start=end-3600000;
  return variables.flatMap(variable=>{
    const buckets=new Map<number,number[]>();
    for(const r of clean) {
      const ts=Date.parse(r.acquiredAt),value=r[variable];
      if(ts<start||value===null) continue;
      const bucket=Math.floor(ts/60000)*60000;
      const a=buckets.get(bucket)??[];
      a.push(value);buckets.set(bucket,a);
    }
    const points=[...buckets].map(([ts,a])=>({ts,value:mean(a)}));
    if(points.length<20) return [];
    const fit=(data:typeof points)=>{
      const origin=data[0].ts,x=data.map(p=>(p.ts-origin)/60000),y=data.map(p=>p.value),mx=mean(x),my=mean(y);
      const denominator=x.reduce((sum,n)=>sum+(n-mx)**2,0);
      const slope=denominator?x.reduce((sum,n,i)=>sum+(n-mx)*(y[i]-my),0)/denominator:0;
      return(ts:number)=>my+slope*((ts-origin)/60000-mx);
    };
    const model=fit(points),heldOut=points.slice(-10),backtest=fit(points.slice(0,-10));
    return [{variable,predicted:round(model(end+1800000)),
      mae:round(mean(heldOut.map(p=>Math.abs(p.value-backtest(p.ts)))),2),
      points:Array.from({length:7},(_,i)=>({ts:end+i*300000,value:round(model(end+i*300000))}))}];
  });
}

