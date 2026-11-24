import { labels, mean, percentile, round, std, variables, type Reading, type Variable } from "./domain.ts";

const floors = {temperature: .25, humidity: 1, pressure: .35};
const minReference = 15;
export const referenceSize = 60;
export const referenceAgeMs = 60 * 60 * 1000;
export const regimeSize = 10;
export const regimeChangeIssue = "Cambio de régimen sostenido en al menos dos variables. Se renovó la referencia estadística.";
export const detectorVersion = "regime-v2";

function referenceStats(reference: Reading[]) {
  return variables.map(variable => {
    const values = reference.map(reading => reading[variable]!);
    return {variable, center: mean(values), scale: Math.max(std(values), floors[variable])};
  });
}

function deviations(reading: Pick<Reading, Variable>, stats: ReturnType<typeof referenceStats>) {
  return stats.flatMap(({variable, center, scale}) => {
    const value = reading[variable];
    if (value === null) return [];
    const score = (value - center) / scale;
    return Math.abs(score) > 3.5 ? [{variable, score}] : [];
  });
}

function legacyIssue(variable: Variable, score: number, count: number) {
  return `${labels[variable]} se apartó ${round(Math.abs(score))} desviaciones de las ${count} lecturas válidas anteriores.`;
}

export function legacyAnomalies(reading: Pick<Reading, Variable>, reference: Reading[]) {
  if (reference.length < minReference) return [];
  return deviations(reading, referenceStats(reference)).map(({variable, score}) => legacyIssue(variable, score, reference.length));
}

function confirmsRegimeChange(run: Reading[], reference: Reading[], stats: ReturnType<typeof referenceStats>) {
  if (run.length !== regimeSize || run.some(row => row.quality === "INVALID" || row.quality === "MISSING")) return false;

  // The reference and run are ordered newest first, within the same station and boot session.
  const intervals = reference.slice(1).flatMap((older, i) => {
    const newer = reference[i];
    const gap = Date.parse(newer.acquiredAt) - Date.parse(older.acquiredAt);
    return newer.timeSource === run[0].timeSource && older.timeSource === newer.timeSource &&
      newer.sequence === older.sequence + 1 && gap > 0 ? [gap] : [];
  });
  const cadence = intervals.length >= 5 ? percentile(intervals, .5) : null;
  if (cadence === null || run.slice(1).some((older, i) => {
    const newer = run[i];
    const gap = Date.parse(newer.acquiredAt) - Date.parse(older.acquiredAt);
    return newer.sequence !== older.sequence + 1 || older.timeSource !== newer.timeSource ||
      gap < cadence * .6 || gap > cadence * 1.6;
  })) return false;

  let shifted = 0;
  for (const {variable, center, scale} of stats) {
    const values = run.map(row => row[variable]!);
    const low = Math.min(...values), high = Math.max(...values);
    if (high - low > floors[variable] * 3) return false;
    if (low - center > 3.5 * scale || center - high > 3.5 * scale) shifted++;
  }
  return shifted >= 2;
}

export function assessDeviation(reading: Reading, reference: Reading[], recent: Reading[], rebuilt: boolean) {
  if (reading.quality !== "VALID" || reference.length < (rebuilt ? regimeSize : minReference)) return;
  const stats = referenceStats(reference);
  const signals = deviations(reading, stats);
  if (!signals.length) return;

  reading.quality = "ANOMALY";
  if (rebuilt) {
    reading.issues.push(...signals.map(({variable, score}) =>
      `${labels[variable]} se apartó ${round(Math.abs(score))} desviaciones de la referencia del régimen reciente (${reference.length} lecturas).`));
  } else {
    reading.issues.push(...signals.map(({variable, score}) => legacyIssue(variable, score, reference.length)));
  }
  if (signals.length >= 2 && confirmsRegimeChange([reading, ...recent], reference, stats)) {
    reading.issues.push(regimeChangeIssue);
  }
}
