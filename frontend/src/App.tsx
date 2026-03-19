import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GlobalEventMap } from './components/map/GlobalEventMap';
import { IntelligencePanel } from './components/tables/IntelligencePanel';
import { SystemControlPanel } from './components/tables/SystemControlPanel';
import { useStore } from './store/useStore';
import { Globe, Calendar, Terminal } from 'lucide-react';

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

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex flex-col h-screen w-screen bg-surface-900 overflow-hidden">
        {/* Header */}
        <header className="h-14 border-b border-white/10 flex items-center justify-between px-6 bg-surface-800 z-50">
          <div className="flex items-center gap-4">
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

        {/* Main Content */}
        <main className="flex-1 relative">
           <GlobalEventMap />
           <IntelligencePanel />
           
           {/* UI Overlays */}
           <div className="absolute top-6 left-6 z-10 space-y-4">
              <div className="glass-panel p-4 w-64 space-y-4">
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
                  <SystemControlPanel />
           </div>
        </main>
      </div>
    </QueryClientProvider>
  );
}

export default App;
