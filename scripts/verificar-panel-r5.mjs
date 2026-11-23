import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { createRequire, registerHooks } from "node:module";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const tmp = await mkdtemp(join(tmpdir(),"agroedge-r5-"));
const expected = JSON.parse(await readFile("examples/r5/boletin-verificado.json","utf8"));
const py = process.env.AGROEDGE_PYTHON || (process.platform==="win32" ? "py" : "python3");
const fixture = "tests/fixtures/noaa-enso-es-2026-11-12.html";
const handler = require("../.next/server/app/api/[...path]/route.js").routeModule.userland;
const apiURL = "http://localhost/api/agroclima";

async function readFeed() {
  const response = await handler.GET(new Request(apiURL));
  assert.equal(response.status, 200);
  return response.json();
}

try {
  process.env.AGROEDGE_R5_DIR = tmp;
  const initial = await readFeed();
  assert.equal(initial.bundled,true);
  assert.equal(initial.editions[0].revision,expected.revision);
  const dashboard = await readFile(".next/server/app/index.html","utf8");
  assert.ok(dashboard.includes("Boletín agroclimático externo"));
  assert.ok(dashboard.includes(expected.summary));
  for (const outcome of ["NUEVA","DUPLICADA"]) {
    const result = spawnSync(py,["scraper/agroclima.py","--dir",tmp,"capture",fixture],{encoding:"utf8",windowsHide:true});
    assert.equal(result.status, 0, result.stderr || String(result.error));
    assert.equal(JSON.parse(result.stdout).resultado,outcome);
  }
  const feed = await readFeed();
  assert.equal(feed.lastRun.outcome,"DUPLICADA");
  assert.equal(feed.bundled,false);
  assert.equal(feed.editions.length,1);
  assert.equal(feed.editions[0].revision,expected.revision);

  // Render the same component as the dashboard with the response from the compiled Next route.
  const hooks = registerHooks({load(url,context,next) {
    if (!url.endsWith("/climate-panel.tsx")) return next(url,context);
    const {outputText} = ts.transpileModule(readFileSync(fileURLToPath(url),"utf8"),{
      compilerOptions:{module:ts.ModuleKind.CommonJS, jsx:ts.JsxEmit.ReactJSX, target:ts.ScriptTarget.ES2022,
        esModuleInterop:true}});
    return {format:"commonjs",source:outputText,shortCircuit:true};
  }});
  const {ClimateBulletins} = require("../components/datacity/climate-panel.tsx");
  hooks.deregister();
  const panel = renderToStaticMarkup(createElement(ClimateBulletins,{feed,error:"",onForecast() {}}));
  for (const value of [expected.summary,expected.status,expected.url,expected.published,"archivo HTML"]) {
    assert.ok(panel.includes(value),value);
  }
  assert.ok(!panel.includes("Boletín archivado incluido"));
  const arg = process.argv.find(a=>a.startsWith("--html="));
  if (arg) {
    const path = resolve(arg.slice(7));
    assert.ok(path.endsWith(".html"), "El archivo de evidencia debe terminar en .html.");
    const css = await readFile("app/agroedge.css","utf8");
    await writeFile(path,'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AgroEdge IA · Evidencia R5</title><style>body{background:#0d1820;color:#eef4f1;font:16px/1.5 system-ui;max-width:960px;margin:3rem auto;padding:1rem}h2,h3,p{margin:0}.panel{border:1px solid #38505f;border-radius:12px}.button{display:none}header{margin-bottom:1rem}</style><style>'+css+'</style><main><header><strong>AgroEdge IA · Evidencia R5</strong><p>Vista estática del componente del dashboard, renderizada con la respuesta de la ruta compilada después de la segunda extracción.</p></header>'+panel+'</main></html>',"utf8");
  }
  console.log("OK: dashboard compilado, captura HTML x2, SQLite, GET /api/agroclima y componente React con los datos recuperados.");
} finally {
  await rm(tmp,{recursive:true,force:true});
}
