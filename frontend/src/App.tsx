import { Routes, Route, NavLink, Link } from 'react-router-dom';
import { ShipmentsPage } from './pages/ShipmentsPage';
import { TimelinePage } from './pages/TimelinePage';
import { AttributionPage } from './pages/AttributionPage';
import { EvidenceReportPage } from './pages/EvidenceReportPage';
import { PreventionPage } from './pages/PreventionPage';
import { BenchmarkPage } from './pages/BenchmarkPage';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans antialiased">
      {/* Top Navigation Bar — hidden in print */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200 no-print">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white font-black text-sm shadow-sm">
                HG
              </span>
              <span className="text-lg font-black tracking-tight text-slate-900">
                Handoff<span className="text-blue-600">Guard</span>
              </span>
            </Link>
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold tracking-wide text-amber-800 border border-amber-200">
              PROTOTYPE
            </span>
          </div>

          <nav className="flex items-center gap-1 sm:gap-2">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-bold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`
              }
            >
              Shipments
            </NavLink>
            <NavLink
              to="/prevention"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-bold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`
              }
            >
              Prevention Prototype
            </NavLink>
            <NavLink
              to="/exasol/benchmark"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-bold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`
              }
            >
              Exasol Benchmark
            </NavLink>
          </nav>
        </div>
      </header>

      {/* Main Page Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <Routes>
          <Route path="/" element={<ShipmentsPage />} />
          <Route path="/shipments/:shipment_id" element={<TimelinePage />} />
          <Route
            path="/shipments/:shipment_id/excursions/:excursion_id"
            element={<AttributionPage />}
          />
          <Route
            path="/shipments/:shipment_id/excursions/:excursion_id/report"
            element={<EvidenceReportPage />}
          />
          <Route path="/prevention" element={<PreventionPage />} />
          <Route path="/exasol/benchmark" element={<BenchmarkPage />} />
        </Routes>
      </main>

      {/* Footer — hidden in print */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-400 no-print">
        <div className="max-w-7xl mx-auto px-4 space-y-1">
          <p>
            HandoffGuard — ExaThon India 2026 Pharmaceutical Cold-Chain Prototype.
          </p>
          <p className="text-[11px] text-slate-400">
            Thermal exposure is estimated from ambient/logger data; thermal mass and packaging are not modelled in this prototype.
          </p>
        </div>
      </footer>
    </div>
  );
}
