import ExcelJS from "exceljs";
import { parse } from "csv-parse/sync";
import { object, type Reading } from "./domain.ts";

import { columns, mandatory, type Key } from "./columns.ts";
const jsonColumn = "Registro íntegro (JSON)";
const numeric = new Set<Key>(["temperature","humidity","pressure","sequence","missingBefore","schemaVersion"]);
const structured = new Set<Key>(["issues","classification"]);
const utf8 = new TextDecoder("utf-8",{fatal:true});

function cell(r:Reading,k:Key) {
  return structured.has(k)?JSON.stringify(r[k]):r[k]??"";
}
function csvCell(x:unknown) { return '"'+String(x??"").replaceAll('"','""')+'"'; }
export function normalizeDelimiter(value:string|null) {
  if(value===null||value==="comma") return ",";
  if(value==="semicolon") return ";";
  if(value==="tab") return "\t";
  throw new Error("Delimitador desconocido.");
}

export function exportMatrix(rows:Reading[],selection?:string|null) {
  const requested=selection===null||selection===undefined?null:new Set(selection.split(","));
  if(requested && [...requested].some(k=>!columns.some(([id])=>id===k))) throw new Error("Se pidió una columna desconocida.");
  const visible=columns.filter(([k])=>!requested||requested.has(k)||mandatory.some(x=>x===k));
  const projected=visible.length<columns.length;
  return [ [...visible.map(([,h])=>h),...(projected?[jsonColumn]:[])],
    ...rows.map(r=>[...visible.map(([k])=>cell(r,k)),...(projected?[JSON.stringify(r)]:[])]) ];
}
export async function exportFile(rows:Reading[],format:"csv"|"xlsx",options:{cols?:string|null;delimiter:string;meta:Record<string,string|number>}) {
  const matrix=exportMatrix(rows,options.cols);
  if(format==="csv") return new TextEncoder().encode("\ufeff"+matrix.map(r=>r.map(csvCell).join(options.delimiter)).join("\r\n")+"\r\n");
  const book=new ExcelJS.Workbook();
  const readings=book.addWorksheet("Mediciones",{views:[{state:"frozen",ySplit:1}]});
  readings.addRows(matrix);
  readings.getRow(1).font={bold:true,color:{argb:"FFFFFFFF"}};
  readings.getRow(1).fill={type:"pattern",pattern:"solid",fgColor:{argb:"FF16533E"}};
  readings.columns.forEach((c,i)=>{c.width=Math.min(36,Math.max(16,String(matrix[0][i]).length+4));});
  readings.autoFilter={from:{row:1,column:1},to:{row:Math.max(1,matrix.length),column:matrix[0].length}};
  if(matrix[0].at(-1)===jsonColumn) readings.getColumn(matrix[0].length).hidden=true;
  const meta=book.addWorksheet("Metadatos");
  meta.columns=[{header:"Campo",key:"field",width:28},{header:"Valor",key:"value",width:68}];
  meta.addRows(Object.entries(options.meta));
  meta.getRow(1).font={bold:true};
  return new Uint8Array(await book.xlsx.writeBuffer());
}
function readCell(x: unknown,k: Key) {
  if(numeric.has(k)) {
    if(x===null||x===undefined||x==="") return null;
    if(typeof x==="number") return x;
    if(typeof x==="string"&&/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[+-]?\d+)?$/i.test(x)) return Number(x);
    throw new Error(`Se esperaba un número con punto decimal en ${k}.`);
  }
  if(structured.has(k)) {
    if(typeof x!=="string") throw new Error(`${k} debe contener JSON.`);
    return JSON.parse(x);
  }
  if(k==="testTransport"&&(x===null||x===undefined||x==="")) return undefined;
  if(typeof x!=="string") throw new Error(`Se esperaba texto en ${k}.`);
  return x;
}
function headerMap(raw:unknown[]) {
  const byHeader=new Map<string,Key>(columns.map(([k,h])=>[h,k]));
  if(new Set(raw).size!==raw.length || raw.some(x=>typeof x!=="string"||(!byHeader.has(x)&&x!==jsonColumn))) throw new Error("Encabezados desconocidos o repetidos. Usa los nombres y unidades de una exportación AgroEdge.");
  const full=raw.indexOf(jsonColumn);
  if(full<0&&raw.length!==columns.length || full>=0&&mandatory.some(k=>!raw.includes(columns.find(([x])=>x===k)![1]))) throw new Error("Faltan columnas obligatorias de una exportación AgroEdge.");
  return {full,keys:raw.map(x=>byHeader.get(String(x)))};
}
function recordRows(matrix:unknown[][]) {
  if(matrix.length<2) throw new Error("El archivo no contiene mediciones.");
  if(matrix.length>25001) throw new Error("Importa máximo 25 000 lecturas por archivo.");
  const {full,keys}=headerMap(matrix[0]);
  return matrix.slice(1).map((row,i)=>{
    try {
      if(row.length>keys.length) throw new Error("La fila tiene más celdas que el encabezado.");
      const values=Object.fromEntries(keys.flatMap((k,j)=>k?[[k,readCell(row[j],k)]]:[]));
      if(full<0) return values;
      if(typeof row[full]!=="string") throw new Error("Falta el registro íntegro de la exportación parcial.");
      const complete=object(JSON.parse(row[full] as string));
      if(Object.entries(values).some(([k,v])=>JSON.stringify(v)!==JSON.stringify(complete[k]))) throw new Error("Las columnas seleccionadas contradicen el registro íntegro.");
      return complete;
    } catch(e) { throw new Error(`Fila ${i+2}: ${e instanceof Error?e.message:e}`); }
  });
}
export async function parseFile(bytes:Uint8Array,format:"csv"|"xlsx") {
  if(format==="xlsx") {
    const book=new ExcelJS.Workbook();
    try { await book.xlsx.load(Buffer.from(bytes) as never); }
    catch { throw new Error("El archivo no es un libro Excel .xlsx válido."); }
    const sheet=book.getWorksheet("Mediciones");
    if(!sheet) throw new Error('El libro necesita una hoja "Mediciones".');
    if(sheet.rowCount>25001||sheet.columnCount>columns.length+1) throw new Error("El libro supera el tamaño permitido de filas o columnas.");
    const grid=Array.from({length:sheet.rowCount},(_,i)=>Array.from({length:sheet.columnCount},(_,j)=>sheet.getRow(i+1).getCell(j+1).value));
    return recordRows(grid);
  }
  let text:string;
  try { text=utf8.decode(bytes); } catch { throw new Error("Guarda el CSV en UTF-8 antes de importarlo."); }
  for(const delimiter of [",",";","\t"]) {
    try {
      const [header]=parse(text,{delimiter,to_line:1,skip_empty_lines:true,bom:true}) as string[][];
      headerMap(header??[]);
    } catch { continue; }
    let matrix:string[][];
    try { matrix=parse(text,{delimiter,skip_empty_lines:true,bom:true,max_record_size:100000}) as string[][]; }
    catch { throw new Error("El CSV tiene comillas o separadores incorrectos."); }
    return recordRows(matrix);
  }
  throw new Error("Encabezados CSV incompatibles. Usa una exportación AgroEdge con coma, punto y coma o tabulador.");
}

