import { useEffect, useRef, useState } from 'react';
import { GlobalEventMap } from './components/map/GlobalEventMap';
import { IntelligencePanel } from './components/tables/IntelligencePanel';
import { SystemControlPanel } from './components/tables/SystemControlPanel';
import { GlobalStatsTicker } from './components/ambient/GlobalStatsTicker';
import { TopThreatCard } from './components/ambient/TopThreatCard';
import { SpikeAlertsCard } from './components/ambient/SpikeAlertsCard';
import { DateRangeSlider } from './components/ambient/DateRangeSlider';
import { useStore } from './store/useStore';
import { apiService } from './services/api';
import { useQuery } from '@tanstack/react-query';
import { Globe, Calendar, Terminal, PanelLeftClose, PanelLeftOpen, Database, Activity, Layers } from 'lucide-react';

function formatDistanceToNow(dateStr: string | null): string {
  if (!dateStr) return 'NEVER';
  const lastUpdate = new Date(dateStr);
  const diffMs = new Date().getTime() - lastUpdate.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'JUST NOW';
  if (diffMin < 60) return `${diffMin} MIN AGO`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours} HR AGO`;
  return `${Math.floor(diffHours / 24)} DAYS AGO`;
}

function toIsoDateLocal(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function App() {
  const {
    dateRange,
    mapMode,
    setMapMode,
    setDateRange,
    dateWindowReady,
    setDateWindowReady,
  } = useStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const hasAlignedDateWindow = useRef(false);

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: apiService.getHealth,
    refetchInterval: 60000,
  });

  const pulseQuery = useQuery({
    queryKey: ['global-pulse', dateRange[0], dateRange[1]],
    queryFn: () => apiService.getGlobalPulse(dateRange[0], dateRange[1]),
    refetchInterval: 60000,
    enabled: dateWindowReady,
  });

  useEffect(() => {
    if (hasAlignedDateWindow.current) return;

    if (healthQuery.isError) {
      hasAlignedDateWindow.current = true;
      setDateWindowReady(true);
      return;
    }

    const lastUpdatedAt = healthQuery.data?.hot_tier.last_updated_at;
    if (!lastUpdatedAt) {
      if (healthQuery.isSuccess) {
        hasAlignedDateWindow.current = true;
        setDateWindowReady(true);
      }
      return;
    }

    const hotTierLastDate = new Date(lastUpdatedAt);
    if (Number.isNaN(hotTierLastDate.getTime())) {
      hasAlignedDateWindow.current = true;
      setDateWindowReady(true);
      return;
    }

    const currentEnd = new Date(`${dateRange[1]}T00:00:00`);
    const hotTierEnd = new Date(
      hotTierLastDate.getFullYear(),
      hotTierLastDate.getMonth(),
      hotTierLastDate.getDate()
    );

    // If selected window is ahead of available local data, shift it back.
    if (currentEnd > hotTierEnd) {
      const alignedEnd = hotTierEnd;
      const alignedStart = new Date(alignedEnd);
      alignedStart.setDate(alignedEnd.getDate() - 7);
      setDateRange([toIsoDateLocal(alignedStart), toIsoDateLocal(alignedEnd)]);
    }

    hasAlignedDateWindow.current = true;
    setDateWindowReady(true);
  }, [
    dateRange,
    healthQuery.data?.hot_tier.last_updated_at,
    healthQuery.isError,
    healthQuery.isSuccess,
    setDateRange,
    setDateWindowReady,
  ]);

  return (
    <div className="flex flex-col h-screen w-screen bg-surface-900 overflow-hidden">

      {/* ── Header ── */}
      <header className="h-14 border-b border-white/10 flex items-center justify-between px-6 bg-surface-800 z-50 shrink-0">
        <div className="flex items-center gap-4">
          {/* Sidebar toggle */}
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="w-8 h-8 flex items-center justify-center rounded-sm hover:bg-white/10 transition-colors text-cyber-blue"
            title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {sidebarOpen
              ? <PanelLeftClose size={18} />
              : <PanelLeftOpen size={18} />}
          </button>

          <div className="w-8 h-8 bg-cyber-blue flex items-center justify-center rounded-sm">
            <Globe size={18} className="text-surface-900" />
          </div>
          <div>
            <h1 className="text-sm font-bold font-mono tracking-tighter glowing-text">
              GNIEM
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`w-1.5 h-1.5 ${healthQuery.isSuccess ? 'bg-terminal-green animate-pulse' : 'bg-cyber-red'} rounded-full`} />
              <span className="data-ink uppercase">
                LAST SYNC: {formatDistanceToNow(healthQuery.data?.hot_tier.last_updated_at || null)}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 px-3 py-1 bg-surface-900 border border-white/10 rounded">
            <Calendar size={14} className="text-cyber-blue" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/70">
              {dateRange[0]} — {dateRange[1]}
            </span>
          </div>
          
          {/* Map Mode Toggle */}
          <div className="flex items-center bg-surface-900 border border-white/10 rounded overflow-hidden">
            <button
              onClick={() => setMapMode('heatmap')}
              className={`flex items-center gap-2 px-3 py-1 transition-colors ${mapMode === 'heatmap' ? 'bg-cyber-blue text-surface-900' : 'hover:bg-white/5 text-white/50'}`}
            >
              <Activity size={12} />
              <span className="text-[9px] font-mono font-bold uppercase tracking-tight">HEATMAP</span>
            </button>
            <div className="w-[1px] h-4 bg-white/10" />
            <button
              onClick={() => setMapMode('clusters')}
              className={`flex items-center gap-2 px-3 py-1 transition-colors ${mapMode === 'clusters' ? 'bg-cyber-blue text-surface-900' : 'hover:bg-white/5 text-white/50'}`}
            >
              <Layers size={12} />
              <span className="text-[9px] font-mono font-bold uppercase tracking-tight">CLUSTERS</span>
            </button>
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      {/* pb-8 reserves space for the fixed GlobalStatsTicker bar */}
      <main className="flex-1 relative overflow-hidden pb-8">

        {/* Map fills the whole canvas */}
        <GlobalEventMap />

        {/* Intelligence panel — right side */}
        <IntelligencePanel />

        {/*
          ── Left sidebar ──
          Slides in/out via transform. pointer-events-none on the wrapper so
          transparent gaps don't eat map events; each child re-enables them.
          w-[22rem] = 352px — wide enough that panels don't clip.
        */}
        <div
          className={`
            absolute top-6 left-6 bottom-10 z-10
            w-[22rem]
            flex flex-col gap-3
            overflow-y-auto overflow-x-hidden pr-1
            pointer-events-none
            transition-transform duration-300 ease-in-out
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-[calc(100%+1.5rem)]'}
          `}
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}
        >
          {/* Mission Parameters */}
          <div className="glass-panel p-4 space-y-4 pointer-events-auto shrink-0">
            <div className="flex items-center justify-between">
              <div className="data-ink uppercase">Filters</div>
              <Terminal size={12} className="text-white/20" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-[11px] font-mono text-white/60">
                <div className="flex items-center gap-2">
                  <Database size={12} className="text-cyber-blue" />
                  <span>HOT TIER</span>
                </div>
                <span className="text-terminal-green uppercase">
                  {healthQuery.data?.hot_tier.coverage_days || 0} Days Coverage
                </span>
              </div>
              <div className="flex justify-between text-[11px] font-mono text-white/60">
                <div className="flex items-center gap-2">
                  <Activity size={12} className="text-cyber-blue" />
                  <span>EVENTS TODAY</span>
                </div>
                <span className="text-terminal-green">
                  {pulseQuery.data?.total_events_today.toLocaleString() || 0}
                </span>
              </div>
            </div>
          </div>

          {/* Activity Spike Alerts (PHASE 4) */}
          <div className="pointer-events-auto shrink-0">
            <SpikeAlertsCard />
          </div>

          {/* 15.2 Threat Monitor */}
          <div className="pointer-events-auto shrink-0">
            <TopThreatCard />
          </div>

          {/* Runtime Controls + System Health */}
          <div className="pointer-events-auto shrink-0">
            <SystemControlPanel />
          </div>
        </div>

        {/* 15.1 Global Stats Ticker — fixed to bottom of viewport */}
        <DateRangeSlider />
        <GlobalStatsTicker />

      </main>
    </div>
  );
}

export default App;
