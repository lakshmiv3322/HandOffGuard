import {
  ComposedChart,
  Line,
  ReferenceLine,
  ReferenceArea,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { safeFormat } from '../../utils/date';
import type { TemperatureReading, Handoff, ExcursionEvent } from '../../types/api';

// Palette for up to 8 loggers
const LOGGER_COLORS = [
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#f59e0b', // amber
  '#10b981', // emerald
  '#ef4444', // red
  '#ec4899', // pink
  '#64748b', // slate
];

interface ChartPoint {
  ts: number;
  [key: string]: number | null;
}

interface TemperatureChartProps {
  readings: TemperatureReading[];
  handoffs: Handoff[];
  excursionIntervals: ExcursionEvent[];
  minTempC: number;
  maxTempC: number;
  suspectedHandoffId?: string | number | null;
  highlightedHandoffId?: string | number | null;
}

interface TooltipPayloadItem {
  dataKey: string;
  value: number | null;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: number;
  minTempC: number;
  maxTempC: number;
}

function CustomTooltip({ active, payload, label, minTempC, maxTempC }: CustomTooltipProps) {
  if (!active || !payload?.length || label === undefined) return null;

  const time = safeFormat(label, 'yyyy-MM-dd HH:mm:ss') + ' UTC';

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-lg text-xs max-w-xs">
      <p className="font-semibold text-slate-700 mb-1">{time}</p>
      {payload
        .filter((p) => p.value !== null)
        .map((p) => {
          const temp = p.value as number;
          const outOfRange = temp < minTempC || temp > maxTempC;
          return (
            <div key={p.dataKey} className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
              <span className="text-slate-600">{p.dataKey}:</span>
              <span className={`font-medium ${outOfRange ? 'text-red-600' : 'text-slate-900'}`}>
                {temp.toFixed(2)}°C
                {outOfRange && <span className="ml-1 text-red-500">⚠</span>}
              </span>
            </div>
          );
        })}
      <p className="mt-1 text-slate-400">
        Safe range: {minTempC}°C – {maxTempC}°C
      </p>
    </div>
  );
}

export function TemperatureChart({
  readings,
  handoffs,
  excursionIntervals,
  minTempC,
  maxTempC,
  suspectedHandoffId,
  highlightedHandoffId,
}: TemperatureChartProps) {
  if (!readings || readings.length === 0) {
    return (
      <div className="w-full h-64 flex flex-col items-center justify-center bg-slate-50 border border-dashed border-slate-200 rounded-xl text-slate-400 text-xs">
        <svg className="w-8 h-8 mb-2 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <p className="font-semibold text-slate-500">No Temperature Telemetry Recorded</p>
        <p className="text-[11px] text-slate-400 mt-1">This shipment has no sensor readings stored in Exasol.</p>
      </div>
    );
  }

  // Group readings by logger_id
  const loggerIds = Array.from(new Set(readings.map((r) => r.logger_id)));

  // Build unified time-series data: one object per unique timestamp
  // For each timestamp we have one key per logger
  const timeMap = new Map<number, ChartPoint>();

  readings.forEach((r) => {
    const ts = new Date(r.recorded_at_utc).getTime();
    if (!timeMap.has(ts)) {
      timeMap.set(ts, { ts });
    }
    const point = timeMap.get(ts)!;
    // Use quality flag to decide whether to show as null (break line)
    if (r.quality_flag === 'missing') {
      point[r.logger_id] = null;
    } else {
      point[r.logger_id] = r.temperature_c;
    }
  });

  const chartData = Array.from(timeMap.values()).sort((a, b) => a.ts - b.ts);

  // Insert line breaks (null readings) across unsupported gaps (> 600s)
  // so telemetry gaps are not falsely connected as continuous observations
  const GAP_THRESHOLD_MS = 600 * 1000;
  const withGaps: ChartPoint[] = [];
  for (let i = 0; i < chartData.length; i++) {
    const curr = chartData[i];
    if (i > 0) {
      const prev = chartData[i - 1];
      if (curr.ts - prev.ts > GAP_THRESHOLD_MS) {
        const gapBreak: ChartPoint = { ts: prev.ts + 1000 };
        loggerIds.forEach((lid) => {
          gapBreak[lid] = null;
        });
        withGaps.push(gapBreak);
      }
    }
    withGaps.push(curr);
  }

  // Pad all logger columns (null for missing timestamps to allow line breaks)
  const filled = withGaps.map((point) => {
    const obj: ChartPoint = { ts: point.ts };
    loggerIds.forEach((lid) => {
      obj[lid] = point[lid] !== undefined ? point[lid] : null;
    });
    return obj;
  });

  // Y-axis domain with some padding
  const allTemps = readings.map((r) => r.temperature_c).filter(Boolean);
  const dataMin = allTemps.length ? Math.min(...allTemps) : minTempC - 5;
  const dataMax = allTemps.length ? Math.max(...allTemps) : maxTempC + 5;
  const yMin = Math.floor(Math.min(dataMin, minTempC) - 2);
  const yMax = Math.ceil(Math.max(dataMax, maxTempC) + 2);

  // X-axis domain
  const xMin = filled.length ? filled[0].ts : Date.now();
  const xMax = filled.length ? filled[filled.length - 1].ts : Date.now();

  const formatXTick = (value: number) => safeFormat(value, 'MM-dd HH:mm');

  return (
    <div className="w-full" style={{ height: 380 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={filled} margin={{ top: 8, right: 24, bottom: 24, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />

          {/* Safe zone shading */}
          <ReferenceArea
            y1={minTempC}
            y2={maxTempC}
            fill="#22c55e"
            fillOpacity={0.1}
            ifOverflow="hidden"
          />

          {/* Excursion red shadings */}
          {excursionIntervals.map((ex) => (
            <ReferenceArea
              key={ex.excursion_id}
              x1={new Date(ex.started_at_utc).getTime()}
              x2={new Date(ex.ended_at_utc).getTime()}
              fill="#ef4444"
              fillOpacity={0.25}
              ifOverflow="hidden"
            />
          ))}

          {/* Handoff vertical lines */}
          {handoffs.map((h) => {
            const isHighlighted = highlightedHandoffId != null && String(h.handoff_id) === String(highlightedHandoffId);
            const isSuspected = suspectedHandoffId != null && String(h.handoff_id) === String(suspectedHandoffId);
            return (
              <ReferenceLine
                key={h.handoff_id}
                x={new Date(h.window_start_utc).getTime()}
                stroke={isSuspected ? '#f97316' : isHighlighted ? '#2563eb' : '#94a3b8'}
                strokeWidth={isSuspected ? 2.5 : isHighlighted ? 2 : 1}
                strokeDasharray={isSuspected ? '0' : '4 4'}
                label={{
                  value: `#${h.sequence_no}`,
                  position: 'insideTopRight',
                  fontSize: 10,
                  fill: isSuspected ? '#f97316' : '#64748b',
                }}
              />
            );
          })}

          {/* Min/Max reference lines */}
          <ReferenceLine
            y={minTempC}
            stroke="#3b82f6"
            strokeDasharray="6 3"
            strokeWidth={1.5}
            label={{ value: `Min ${minTempC}°C`, position: 'left', fontSize: 10, fill: '#3b82f6' }}
          />
          <ReferenceLine
            y={maxTempC}
            stroke="#ef4444"
            strokeDasharray="6 3"
            strokeWidth={1.5}
            label={{ value: `Max ${maxTempC}°C`, position: 'left', fontSize: 10, fill: '#ef4444' }}
          />

          <XAxis
            dataKey="ts"
            type="number"
            scale="time"
            domain={[xMin, xMax]}
            tickFormatter={formatXTick}
            tick={{ fontSize: 10, fill: '#64748b' }}
            tickLine={false}
            label={{ value: 'Time (UTC)', position: 'insideBottom', offset: -12, fontSize: 11, fill: '#94a3b8' }}
          />
          <YAxis
            domain={[yMin, yMax]}
            tick={{ fontSize: 10, fill: '#64748b' }}
            tickLine={false}
            tickFormatter={(v: number) => `${v}°C`}
          />

          <Tooltip
            content={
              <CustomTooltip minTempC={minTempC} maxTempC={maxTempC} />
            }
          />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
            formatter={(value: string) => `Logger: ${value}`}
          />

          {/* One line per logger */}
          {loggerIds.map((lid, idx) => (
            <Line
              key={lid}
              type="monotone"
              dataKey={String(lid)}
              name={String(lid)}
              stroke={LOGGER_COLORS[idx % LOGGER_COLORS.length]}
              dot={{ r: 3, strokeWidth: 1 }}
              activeDot={{ r: 4 }}
              strokeWidth={1.8}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
