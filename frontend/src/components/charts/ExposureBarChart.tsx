import React, { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { getShipmentExposure, HandoffExposureRecord, ShipmentExposureResponse } from '../../api/exposure';

interface Props {
  shipmentId: number;
}

export const ExposureBarChart: React.FC<Props> = ({ shipmentId }) => {
  const [data, setData] = useState<ShipmentExposureResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    getShipmentExposure(shipmentId)
      .then((res) => {
        if (isMounted) {
          setData(res);
          setError(null);
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [shipmentId]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-xs text-slate-400">
        Loading thermal exposure metrics...
      </div>
    );
  }

  if (error || !data) {
    return null;
  }

  const chartData = data.handoffs.map((h) => ({
    name: `Leg ${h.sequence_no}: ${h.to_party.length > 20 ? h.to_party.slice(0, 18) + '...' : h.to_party}`,
    degreeMinutes: h.total_degree_minutes,
    sharePct: h.share_pct,
    severity: h.exposure_severity,
    type: h.handoff_type,
    fromParty: h.from_party,
    toParty: h.to_party,
    duration: h.window_duration_minutes,
    minsAbove: h.minutes_above_safe,
    peakTemp: h.max_temp_c,
  }));

  const getBarColor = (severity: HandoffExposureRecord['exposure_severity']) => {
    switch (severity) {
      case 'critical':
        return '#dc2626'; // Red-600
      case 'high':
        return '#ea580c'; // Orange-600
      case 'medium':
        return '#d97706'; // Amber-600
      default:
        return '#10b981'; // Emerald-500
    }
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const p = payload[0].payload;
      return (
        <div className="bg-slate-900 text-white p-3 rounded-lg shadow-xl text-xs space-y-1.5 max-w-xs border border-slate-700">
          <div className="font-bold border-b border-slate-700 pb-1 text-slate-100">{p.name}</div>
          <div className="text-slate-300">
            <span className="font-semibold text-white">{p.fromParty}</span> → <span className="font-semibold text-white">{p.toParty}</span>
          </div>
          <div className="grid grid-cols-2 gap-x-2 gap-y-1 pt-1 text-[11px]">
            <div>Thermal Exposure:</div>
            <div className="font-bold text-amber-300 text-right">{p.degreeMinutes.toFixed(1)} °C·min</div>
            <div>Exposure Share:</div>
            <div className="font-bold text-white text-right">{p.sharePct.toFixed(1)}%</div>
            <div>Time Outside Range:</div>
            <div className="text-right">{p.minsAbove.toFixed(0)} mins</div>
            <div>Severity Rating:</div>
            <div className="text-right uppercase font-bold text-[10px]">{p.severity}</div>
          </div>
          <div className="pt-1.5 text-[9px] text-slate-400 border-t border-slate-700 leading-tight">
            Formula: ∑(Temp - Safe Threshold) × Duration at that temperature.
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900">
              Thermal Exposure by Custody Handoff
            </h3>
            <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-blue-50 text-blue-700 border border-blue-200">
              Exasol View v_handoff_thermal_exposure
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Degree-minutes calculated from interval-joined readings. Safe limits: {data.safe_range_c}.
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500 font-medium">Total Shipment Exposure</div>
          <div className="text-lg font-black text-rose-600">
            {data.total_shipment_degree_minutes.toFixed(1)}{' '}
            <span className="text-xs font-semibold text-slate-600">°C·min</span>
          </div>
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={chartData}
            margin={{ top: 10, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
            <XAxis
              type="number"
              unit=" °C·min"
              tick={{ fontSize: 11, fill: '#64748b' }}
              axisLine={{ stroke: '#cbd5e1' }}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11, fill: '#334155', fontWeight: 500 }}
              axisLine={{ stroke: '#cbd5e1' }}
              width={140}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="degreeMinutes" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.severity as any)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-emerald-500 inline-block" /> Safe (0)
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-amber-600 inline-block" /> Medium (&gt;0)
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-orange-600 inline-block" /> High (&gt;20)
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-red-600 inline-block" /> Critical (&gt;100)
          </div>
        </div>
        <div className="italic text-slate-400">
          * {data.disclaimer}
        </div>
      </div>
    </div>
  );
};
