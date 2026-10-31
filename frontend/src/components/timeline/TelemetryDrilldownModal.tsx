import { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  Brush,
} from 'recharts';
import { safeFormat } from '../../utils/date';
import {
  type DrilldownHandoff,
  type TelemetryDrilldownData,
} from '../../api/telemetry';

interface TelemetryDrilldownModalProps {
  data: TelemetryDrilldownData;
  initialHandoffId?: number | string | null;
  onClose: () => void;
}

export function TelemetryDrilldownModal({
  data,
  initialHandoffId,
  onClose,
}: TelemetryDrilldownModalProps) {
  // Find initial handoff or default to the first one
  const defaultHandoff = useMemo(() => {
    if (initialHandoffId != null) {
      const match = data.handoffs.find(
        (h) => String(h.handoff_id) === String(initialHandoffId)
      );
      if (match) return match;
    }
    return data.handoffs[0] || null;
  }, [data.handoffs, initialHandoffId]);

  const [selectedHandoff, setSelectedHandoff] = useState<DrilldownHandoff | null>(defaultHandoff);
  const [useAdjustedTime, setUseAdjustedTime] = useState<boolean>(true);
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  const { product, readings, handoffs, gaps, excursions, engine } = data;

  // Format readings for the chart
  const chartPoints = useMemo(() => {
    return readings.map((r) => {
      const tsRaw = new Date(r.reading_at_utc).getTime();
      const tsAdj = new Date(r.adjusted_reading_at_utc).getTime();
      const activeTs = useAdjustedTime ? tsAdj : tsRaw;

      return {
        ts: activeTs,
        rawTs: tsRaw,
        adjTs: tsAdj,
        temperature: r.temperature_c,
        reading_id: r.reading_id,
        logger_id: r.logger_id,
        device_code: r.device_code,
        membership_status: r.membership_status,
        clock_skew_seconds: r.clock_skew_seconds,
        quality_flag: r.quality_flag,
        handoff_id: r.handoff_id,
        is_above_safe: r.is_above_safe,
        is_below_safe: r.is_below_safe,
      };
    });
  }, [readings, useAdjustedTime]);

  // Identify high excursion intervals for red background shading
  const excursionHotSpans = useMemo(() => {
    const spans: { start: number; end: number }[] = [];
    let currentStart: number | null = null;

    chartPoints.forEach((p, idx) => {
      if (p.is_above_safe) {
        if (currentStart === null) currentStart = p.ts;
      } else {
        if (currentStart !== null) {
          spans.push({ start: currentStart, end: chartPoints[idx - 1].ts });
          currentStart = null;
        }
      }
    });
    if (currentStart !== null && chartPoints.length > 0) {
      spans.push({ start: currentStart, end: chartPoints[chartPoints.length - 1].ts });
    }
    return spans;
  }, [chartPoints]);

  // Identify cold excursion intervals for blue background shading
  const excursionColdSpans = useMemo(() => {
    const spans: { start: number; end: number }[] = [];
    let currentStart: number | null = null;

    chartPoints.forEach((p, idx) => {
      if (p.is_below_safe) {
        if (currentStart === null) currentStart = p.ts;
      } else {
        if (currentStart !== null) {
          spans.push({ start: currentStart, end: chartPoints[idx - 1].ts });
          currentStart = null;
        }
      }
    });
    if (currentStart !== null && chartPoints.length > 0) {
      spans.push({ start: currentStart, end: chartPoints[chartPoints.length - 1].ts });
    }
    return spans;
  }, [chartPoints]);

  // Zoom visible points calculation
  const visiblePoints = useMemo(() => {
    if (zoomLevel <= 1 || chartPoints.length <= 10) return chartPoints;
    const span = Math.max(10, Math.floor(chartPoints.length / zoomLevel));
    const start = Math.floor((chartPoints.length - span) / 2);
    return chartPoints.slice(start, start + span);
  }, [chartPoints, zoomLevel]);

  // Determine Y-axis domain
  const { minY, maxY } = useMemo(() => {
    if (chartPoints.length === 0) return { minY: 0, maxY: 20 };
    const temps = chartPoints.map((p) => p.temperature);
    const minVal = Math.min(...temps, product.min_temp_c);
    const maxVal = Math.max(...temps, product.max_temp_c);
    return {
      minY: Math.floor(minVal - 2),
      maxY: Math.ceil(maxVal + 2),
    };
  }, [chartPoints, product.min_temp_c, product.max_temp_c]);

  if (chartPoints.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-sm p-4">
        <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden p-6 space-y-4 text-center">
          <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto text-xl font-bold">
            ℹ
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">No Sensor Readings Available</h3>
            <p className="text-xs text-slate-500 mt-1">
              Shipment {data.shipment_code} does not have temperature logger observations recorded yet.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-full py-2 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 transition-colors shadow-sm"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  // Custom hover tooltip
  const renderCustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;
    const pt = payload[0].payload;

    return (
      <div className="bg-slate-900 text-white rounded-lg p-3 text-xs shadow-xl border border-slate-700 max-w-xs space-y-1.5 z-50">
        <div className="flex items-center justify-between border-b border-slate-700 pb-1">
          <span className="font-bold text-amber-400 font-mono">
            {safeFormat(pt.ts, 'yyyy-MM-dd HH:mm:ss')} UTC
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
            ID #{pt.reading_id}
          </span>
        </div>

        <div className="flex items-baseline justify-between">
          <span className="text-slate-400">Temperature:</span>
          <span
            className={`font-black text-sm font-mono ${
              pt.is_above_safe
                ? 'text-rose-400'
                : pt.is_below_safe
                ? 'text-blue-400'
                : 'text-emerald-400'
            }`}
          >
            {pt.temperature.toFixed(2)} °C
            {pt.is_above_safe && ' (HOT EXCURSION)'}
            {pt.is_below_safe && ' (COLD EXCURSION)'}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] pt-1 border-t border-slate-800">
          <div>
            <span className="text-slate-400">Logger ID:</span>{' '}
            <span className="font-mono text-slate-200">
              {pt.device_code || `LOG-${pt.logger_id}`}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Clock Skew:</span>{' '}
            <span className="font-mono text-slate-200">
              {pt.clock_skew_seconds > 0 ? `+${pt.clock_skew_seconds}s` : `${pt.clock_skew_seconds}s`}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Membership:</span>{' '}
            <span
              className={`font-semibold capitalize ${
                pt.membership_status === 'matched'
                  ? 'text-emerald-400'
                  : pt.membership_status === 'matched_with_skew'
                  ? 'text-amber-400'
                  : 'text-rose-400'
              }`}
            >
              {pt.membership_status.replace(/_/g, ' ')}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Quality:</span>{' '}
            <span className="font-mono text-slate-200">{pt.quality_flag}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-7xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Top Header */}
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white font-black text-sm">
              TD
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-black tracking-tight text-white">
                  Telemetry Drilldown — Shipment {data.shipment_code}
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-900/80 text-blue-300 border border-blue-700">
                  Engine: {engine.toUpperCase()}
                </span>
                {excursions.length > 0 && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-900/80 text-rose-300 border border-rose-700">
                    {excursions.length} Excursion(s)
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                High-resolution sensor telemetry joined with custody handoff windows in Exasol.
                {readings.length > 0 && (
                  <span className="ml-2 font-mono text-slate-300 font-medium">
                    | Latest recorded reading: {safeFormat(readings[readings.length - 1]?.reading_at_utc, 'yyyy-MM-dd HH:mm')} UTC
                  </span>
                )}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close drilldown (Esc)"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Controls & Legend Bar */}
        <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
          {/* Legend Items */}
          <div className="flex flex-wrap items-center gap-3 text-slate-600">
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-2.5 rounded-sm bg-emerald-500/20 border border-emerald-500" />
              <span>Safe Band ({product.min_temp_c}°C – {product.max_temp_c}°C)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-2.5 rounded-sm bg-rose-500/30 border border-rose-500" />
              <span>High Excursion (&gt; {product.max_temp_c}°C)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-2.5 rounded-sm bg-blue-500/30 border border-blue-500" />
              <span>Cold Excursion (&lt; {product.min_temp_c}°C)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-2.5 rounded-sm bg-slate-200 border border-slate-400" />
              <span>Handoff Window Band</span>
            </div>
            {gaps.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-2.5 rounded-sm bg-amber-200 border border-amber-400" />
                <span>Telemetry Gap ({gaps.length})</span>
              </div>
            )}
          </div>

          {/* Timestamp Mode & Zoom Controls */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 bg-white border border-slate-300 rounded-lg p-0.5">
              <button
                onClick={() => setUseAdjustedTime(true)}
                className={`px-2 py-1 rounded text-xs font-semibold transition-colors ${
                  useAdjustedTime ? 'bg-blue-600 text-white font-bold' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Clock-Skew Adjusted
              </button>
              <button
                onClick={() => setUseAdjustedTime(false)}
                className={`px-2 py-1 rounded text-xs font-semibold transition-colors ${
                  !useAdjustedTime ? 'bg-blue-600 text-white font-bold' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Raw Timestamps
              </button>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoomLevel((z) => Math.min(z + 0.5, 3))}
                className="px-2 py-1 rounded bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 font-bold"
                title="Zoom In"
              >
                +
              </button>
              <button
                onClick={() => setZoomLevel((z) => Math.max(z - 0.5, 1))}
                className="px-2 py-1 rounded bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 font-bold"
                title="Zoom Out"
              >
                −
              </button>
              <button
                onClick={() => setZoomLevel(1)}
                className="px-2 py-1 rounded bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 font-semibold"
                title="Reset Zoom"
              >
                {zoomLevel > 1 ? `Reset (${zoomLevel}x)` : 'Reset'}
              </button>
            </div>
          </div>
        </div>

        {/* Main Content Area: Chart (70%) + Side Panel (30%) */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 min-h-0 overflow-hidden">
          {/* Left Chart Area */}
          <div className="lg:col-span-8 p-4 flex flex-col border-r border-slate-200 overflow-y-auto">
            <div className="flex-1 w-full min-h-[380px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={visiblePoints} margin={{ top: 20, right: 30, left: 10, bottom: 25 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />

                  <XAxis
                    dataKey="ts"
                    type="number"
                    domain={['dataMin', 'dataMax']}
                    tickFormatter={(unix) => safeFormat(unix, 'HH:mm')}
                    tick={{ fontSize: 11, fill: '#64748b' }}
                  />

                  <YAxis
                    domain={[minY, maxY]}
                    tick={{ fontSize: 11, fill: '#64748b' }}
                    tickFormatter={(v) => `${v}°C`}
                  />

                  <Tooltip content={renderCustomTooltip} />

                  {/* Product Safe Temperature Band */}
                  <ReferenceArea
                    y1={product.min_temp_c}
                    y2={product.max_temp_c}
                    fill="#10b981"
                    fillOpacity={0.08}
                  />

                  {/* Upper and Lower Limit Lines */}
                  <ReferenceLine
                    y={product.max_temp_c}
                    stroke="#ef4444"
                    strokeDasharray="4 4"
                    label={{
                      value: `Max Safe: ${product.max_temp_c}°C`,
                      position: 'top',
                      fill: '#ef4444',
                      fontSize: 10,
                    }}
                  />
                  <ReferenceLine
                    y={product.min_temp_c}
                    stroke="#3b82f6"
                    strokeDasharray="4 4"
                    label={{
                      value: `Min Safe: ${product.min_temp_c}°C`,
                      position: 'bottom',
                      fill: '#3b82f6',
                      fontSize: 10,
                    }}
                  />

                  {/* Red Shading for Hot Excursions */}
                  {excursionHotSpans.map((span, idx) => (
                    <ReferenceArea
                      key={`hot-${idx}`}
                      x1={span.start}
                      x2={span.end}
                      y1={product.max_temp_c}
                      y2={maxY}
                      fill="#ef4444"
                      fillOpacity={0.25}
                    />
                  ))}

                  {/* Blue Shading for Cold Excursions */}
                  {excursionColdSpans.map((span, idx) => (
                    <ReferenceArea
                      key={`cold-${idx}`}
                      x1={span.start}
                      x2={span.end}
                      y1={minY}
                      y2={product.min_temp_c}
                      fill="#3b82f6"
                      fillOpacity={0.25}
                    />
                  ))}

                  {/* Handoff Window Shaded Vertical Bands */}
                  {handoffs.map((h) => {
                    const startTs = new Date(h.window_start_utc).getTime();
                    const endTs = new Date(h.window_end_utc).getTime();
                    const isSelected = selectedHandoff?.handoff_id === h.handoff_id;

                    return (
                      <ReferenceArea
                        key={`h-band-${h.handoff_id}`}
                        x1={startTs}
                        x2={endTs}
                        fill={isSelected ? '#3b82f6' : '#94a3b8'}
                        fillOpacity={isSelected ? 0.15 : 0.04}
                        stroke={isSelected ? '#3b82f6' : '#cbd5e1'}
                        strokeDasharray="3 3"
                        onClick={() => setSelectedHandoff(h)}
                        className="cursor-pointer"
                        label={{
                          value: `Leg ${h.sequence_no}`,
                          position: 'insideTopLeft',
                          fill: isSelected ? '#1d4ed8' : '#64748b',
                          fontSize: 10,
                          fontWeight: 700,
                        }}
                      />
                    );
                  })}

                  {/* Telemetry Gap Bands */}
                  {gaps.map((g, idx) => {
                    const startTs = new Date(g.gap_start_utc).getTime();
                    const endTs = new Date(g.gap_end_utc).getTime();
                    return (
                      <ReferenceArea
                        key={`gap-${idx}`}
                        x1={startTs}
                        x2={endTs}
                        fill="#f59e0b"
                        fillOpacity={0.2}
                        stroke="#f59e0b"
                        strokeDasharray="2 2"
                        label={{
                          value: `Gap (${g.duration_minutes}m)`,
                          position: 'insideTop',
                          fill: '#b45309',
                          fontSize: 9,
                        }}
                      />
                    );
                  })}

                  {/* Primary Temperature Curve */}
                  <Line
                    type="monotone"
                    dataKey="temperature"
                    stroke="#1e293b"
                    strokeWidth={2}
                    dot={{ r: 2, fill: '#1e293b' }}
                    activeDot={{ r: 5, fill: '#f59e0b', stroke: '#ffffff', strokeWidth: 2 }}
                    isAnimationActive={false}
                  />

                  {/* Time-window Brush for Pan & Zoom */}
                  <Brush
                    dataKey="ts"
                    height={28}
                    stroke="#3b82f6"
                    fill="#f8fafc"
                    tickFormatter={(unix) => safeFormat(unix, 'HH:mm')}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <p className="mt-2 text-[11px] text-slate-400 text-center">
              💡 Tip: Click any handoff band in the chart or the tabs on the right to inspect its custody details. Use the brush slider below the chart to pan or zoom into time windows.
            </p>
          </div>

          {/* Right Side Panel: Selected Handoff Details */}
          <div className="lg:col-span-4 p-5 bg-slate-50 overflow-y-auto space-y-4">
            <div>
              <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">
                Custody Segment Inspector
              </span>
              <h3 className="text-sm font-bold text-slate-800 mt-0.5">
                Select Handoff Window
              </h3>
            </div>

            {/* Quick Handoff Switcher Tabs */}
            <div className="flex flex-wrap gap-1.5">
              {handoffs.map((h) => {
                const isSelected = selectedHandoff?.handoff_id === h.handoff_id;
                return (
                  <button
                    key={h.handoff_id}
                    onClick={() => setSelectedHandoff(h)}
                    className={`px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                      isSelected
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    Leg #{h.sequence_no}
                  </button>
                );
              })}
            </div>

            {selectedHandoff ? (
              <div className="space-y-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm text-xs">
                {/* Segment Heading */}
                <div className="border-b border-slate-100 pb-3">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-700">
                      {selectedHandoff.handoff_type.replace(/_/g, ' ')}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                        selectedHandoff.attribution_confidence === 'high'
                          ? 'bg-rose-100 text-rose-800'
                          : selectedHandoff.attribution_confidence === 'medium'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}
                    >
                      Confidence: {selectedHandoff.attribution_confidence}
                      {selectedHandoff.confidence_score !== null && selectedHandoff.confidence_score !== undefined
                        ? ` (${Math.round(selectedHandoff.confidence_score * 100)}%)`
                        : ''}
                    </span>
                  </div>

                  <p className="font-black text-slate-900 text-sm mt-2">
                    {selectedHandoff.from_party}{' '}
                    <span className="text-slate-400 font-normal">→</span>{' '}
                    {selectedHandoff.to_party}
                  </p>
                  <p className="text-slate-500 text-[11px] mt-0.5">
                    📍 {selectedHandoff.location}
                  </p>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 gap-3 text-slate-700">
                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                    <p className="text-[10px] uppercase font-bold text-slate-400">Dwell Duration</p>
                    <p className="text-sm font-black text-slate-800 font-mono mt-0.5">
                      {selectedHandoff.dwell_minutes} min
                    </p>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                    <p className="text-[10px] uppercase font-bold text-slate-400">Readings Captured</p>
                    <p className="text-sm font-black text-slate-800 font-mono mt-0.5">
                      {selectedHandoff.reading_count} pts
                    </p>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                    <p className="text-[10px] uppercase font-bold text-slate-400">Exposure (°C·min)</p>
                    <p className="text-sm font-black text-rose-600 font-mono mt-0.5">
                      {selectedHandoff.exposure_degree_minutes !== null && selectedHandoff.exposure_degree_minutes !== undefined
                        ? selectedHandoff.exposure_degree_minutes.toFixed(1)
                        : 'Unavailable'}
                    </p>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                    <p className="text-[10px] uppercase font-bold text-slate-400">Exposure Share</p>
                    <p className="text-sm font-black text-slate-800 font-mono mt-0.5">
                      {selectedHandoff.exposure_share_pct !== null && selectedHandoff.exposure_share_pct !== undefined
                        ? `${selectedHandoff.exposure_share_pct.toFixed(1)}%`
                        : '—'}
                    </p>
                  </div>
                </div>

                {/* Window Timestamps */}
                <div className="space-y-1 text-[11px] text-slate-600 border-t border-slate-100 pt-3">
                  <p>
                    <span className="text-slate-400">Window Start:</span>{' '}
                    <span className="font-mono">
                      {safeFormat(selectedHandoff.window_start_utc, 'yyyy-MM-dd HH:mm:ss')} UTC
                    </span>
                  </p>
                  <p>
                    <span className="text-slate-400">Window End:</span>{' '}
                    <span className="font-mono">
                      {safeFormat(selectedHandoff.window_end_utc, 'yyyy-MM-dd HH:mm:ss')} UTC
                    </span>
                  </p>
                </div>

                {/* Evidence Notes */}
                {selectedHandoff.evidence_notes.length > 0 && (
                  <div className="border-t border-slate-100 pt-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                      Evidence Diagnostics
                    </p>
                    <ul className="space-y-1 text-[11px] text-slate-600 list-disc list-inside">
                      {selectedHandoff.evidence_notes.map((note, idx) => (
                        <li key={idx}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-6 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
                Select a handoff leg to view diagnostics.
              </div>
            )}

            {/* Mandatory scientific limitation note */}
            <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-[11px] text-amber-800">
              <span className="font-bold">Investigation Prototype Note:</span> Thermal exposure is calculated from ambient sensor readings. Product thermal mass and packaging barrier dampening are not modelled.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
