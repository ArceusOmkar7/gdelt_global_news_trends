import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GlobalEventMap } from './components/map/GlobalEventMap';
import { IntelligencePanel } from './components/tables/IntelligencePanel';
import { SystemControlPanel } from './components/tables/SystemControlPanel';
import { GlobalStatsTicker } from './components/ambient/GlobalStatsTicker';
import { TopThreatCard } from './components/ambient/TopThreatCard';
import { useStore } from './store/useStore';
import { Globe, Calendar, Terminal, PanelLeftClose, PanelLeftOpen } from 'lucide-react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  const { dateRange } = useStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <QueryClientProvider client={queryClient}>
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
                GNIEM <span className="text-white/40">V0.1.0</span>
              </h1>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="w-1.5 h-1.5 bg-terminal-green rounded-full animate-pulse" />
                <span className="data-ink">Satellite Link Established</span>
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
            <div className="flex items-center gap-2 px-3 py-1 bg-surface-900 border border-white/10 rounded">
              <Terminal size={14} className="text-cyber-blue" />
              <span className="data-ink">OP-MODE: INTELLIGENCE</span>
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
              <div className="data-ink">Mission Parameters</div>
              <div className="space-y-2">
                <div className="flex justify-between text-[11px] font-mono text-white/60">
                  <span>GEO-SYNC</span>
                  <span className="text-terminal-green">ACTIVE</span>
                </div>
                <div className="flex justify-between text-[11px] font-mono text-white/60">
                  <span>LLM-UPLINK</span>
                  <span className="text-terminal-green">READY</span>
                </div>
              </div>
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
          <GlobalStatsTicker />

        </main>
      </div>
    </QueryClientProvider>
  );
}

export default App;
