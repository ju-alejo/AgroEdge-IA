import { spawn, execFile, type ChildProcess } from "node:child_process";
import { createInterface } from "node:readline";
import { resolve } from "node:path";
import { promisify } from "node:util";
import { getStore } from "./store.ts";
import { object } from "./domain.ts";

const exec=promisify(execFile);
const shared=globalThis as typeof globalThis & { agroUsb?:UsbAgent };
type UsbState = {state:string;port:string|null;baud:number;lastReading:string|null;stationId:string|null;error:string|null};

class UsbAgent {
  private child:ChildProcess|null=null;
  private status:UsbState={state:"DISCONNECTED",port:null,baud:115200,lastReading:null,stationId:null,error:null};
  private openAt=0;
  private launch(...args:string[]) {
    return spawn(process.env.AGROEDGE_PYTHON??"python",[resolve("hardware","bridge.py"),...args],{windowsHide:true});
  }
  async ports() {
    try {
      const {stdout}=await exec(process.env.AGROEDGE_PYTHON??"python",[resolve("hardware","bridge.py"),"--list"],{windowsHide:true,timeout:8000});
      const result=JSON.parse(stdout);
      return result.ports as {port:string;description:string}[];
    } catch(e) {
      const stdout=(e as {stdout?:string}).stdout;
      if(stdout) {const message=JSON.parse(stdout); if(message.error) throw new Error(message.error);}
      throw new Error("No se pudieron listar los puertos. Verifica Python y pyserial.");
    }
  }
  get() {
    const ttl=Number(process.env.AGROEDGE_STALE_SECONDS??30)*1000;
    const last=this.status.lastReading?Date.parse(this.status.lastReading):this.openAt;
    return {...this.status,state:["OPEN","RECEIVING"].includes(this.status.state)&&Date.now()-last>ttl?"STALE":this.status.state};
  }
  stop() {
    const old=this.child;
    this.child=null;
    old?.kill();
    this.status={...this.status,state:"DISCONNECTED"};
    return this.get();
  }
  start(port:unknown,baud:unknown) {
    if(typeof port!=="string"||!/^(COM[1-9][0-9]{0,2}|\/dev\/(ttyUSB|ttyACM|cu\.)[\w.-]{1,60})$/i.test(port)) throw new Error("Selecciona un puerto válido, por ejemplo COM4.");
    if(typeof baud!=="number"||![9600,19200,57600,115200,230400].includes(baud)) throw new Error("Velocidad serial no admitida.");
    if(this.child&&this.status.port===port&&this.status.baud===baud) return this.get();
    this.stop();
    this.status={state:"OPENING",port,baud,lastReading:null,stationId:null,error:null};
    const child=this.launch("--serial",port,"--baud",String(baud));
    this.child=child;
    const reader=createInterface({input:child.stdout});
    reader.on("line",line=>{
      if(this.child!==child) return;
      try {
        const msg=object(JSON.parse(line));
        if(msg.event==="state") {
          this.status.state=String(msg.state);
          if(msg.state==="OPEN") this.openAt=Date.now();
        } else if(msg.event==="error") this.status.error=String(msg.error);
        else if(msg.event==="reading") {
          const {status,reading}=getStore().ingest(msg.reading,"USB");
          if(status==="stored") this.status={...this.status,state:"RECEIVING",lastReading:reading.receivedAt,stationId:reading.stationId,error:null};
        }
      } catch(error) { this.status.error=error instanceof Error?error.message:String(error); }
    });
    child.stderr.on("data",d=>{if(this.child===child) this.status.error=String(d).slice(0,350);});
    child.once("error",()=>{if(this.child===child) {this.child=null;this.status={...this.status,state:"ERROR",error:"No se pudo iniciar Python. Revisa AGROEDGE_PYTHON."};}});
    child.once("exit",()=>{if(this.child===child) {this.child=null;this.status={...this.status,state:"ERROR",error:this.status.error??"El puente serial se cerró."};}});
    return this.get();
  }
}
export function usb() {return shared.agroUsb??=new UsbAgent();}

