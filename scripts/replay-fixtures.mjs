import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

export async function replay(root, send=fetch) {
  const serial=execFileSync(process.env.AGROEDGE_PYTHON??"python",["hardware/bridge.py","--fixture","examples/usb-demo.ndjson"],{encoding:"utf8"})
    .trim().split(/\r?\n/).map(line=>JSON.parse(line));
  const wifi=JSON.parse(await readFile("examples/wifi-demo.json","utf8"));
  const outputs=[];
  for(const [type,rows] of [["usb",serial.map(m=>{if(m.event!=="reading") throw new Error(m.error);return m.reading;})],["wifi",[wifi]]]) {
    for(const data of rows) {
      const response=await send(`${root}/api/test/${type}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
      const result=await response.json();
      if(!response.ok) throw new Error(result.error);
      if(result.reading.dataKind!=="SIMULATED"||result.reading.testTransport!==type.toUpperCase()) throw new Error("La etiqueta de prueba no se preservó.");
      outputs.push(result);
    }
  }
  return outputs;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  const result=await replay(process.argv[2]??"http://127.0.0.1:5173");
  console.log(result.map(r=>`${r.status} ${r.reading.dataKind} ${r.reading.testTransport} sec. ${r.reading.sequence}`).join("\n"));
}

