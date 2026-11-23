export const columns = [
  ["id","ID de registro"],["stationId","Estación"],["sessionId","Sesión"],
  ["acquiredAt","Adquisición (UTC ISO 8601)"],["sequence","Secuencia"],["temperature","Temperatura (°C)"],
  ["humidity","Humedad relativa (%)"],["pressure","Presión (hPa)"],["origin","Origen"],["dataKind","Condición de datos"],
  ["quality","Calidad"],["missingBefore","Secuencias faltantes previas"],["receivedAt","Recepción (UTC ISO 8601)"],
  ["timeSource","Fuente horaria"],["issues","Observaciones (JSON)"],["classification","TinyML (JSON)"],
  ["schemaVersion","Versión de esquema"],["testTransport","Transporte bajo prueba"],
] as const;
export type Key=typeof columns[number][0];
export const mandatory = ["id","acquiredAt","origin","dataKind"] as const;
