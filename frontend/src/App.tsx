import { useEffect, useRef, useState } from 'react';
import { GlobalEventMap } from './components/map/GlobalEventMap';
import { IntelligencePanel } from './components/tables/IntelligencePanel';
import { SystemControlPanel } from './components/tables/SystemControlPanel';
import { GlobalStatsTicker } from './components/ambient/GlobalStatsTicker';
import { TopThreatCard } from './components/ambient/TopThreatCard';
import { SpikeAlertsCard } from './components/ambient/SpikeAlertsCard';
import { TrendingNewsFeed } from './components/tables/TrendingNewsFeed';
import { DateRangeSlider } from './components/ambient/DateRangeSlider';
import { EventTrendChart } from './components/ambient/EventTrendChart';
import { GeoFilterBar } from './components/ambient/GeoFilterBar';
import { SearchableDropdown, type DropdownOption } from './components/ambient/SearchableDropdown';
import { useStore } from './store/useStore';
import { apiService } from './services/api';
import { useQuery } from '@tanstack/react-query';
import { Globe, Calendar, Terminal, Database, Activity, Layers, Map as MapIcon, ArrowLeft, X, Sun, Moon } from 'lucide-react';

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

const CATEGORIES = ['ALL', 'CONFLICT', 'DIPLOMACY', 'COOPERATION', 'PRESSURE'];

const CATEGORY_TO_ROOT_CODES: Record<string, string[] | null> = {
  ALL: null,
  CONFLICT: ['18', '19', '20'],
  DIPLOMACY: ['01', '02', '03'],
  COOPERATION: ['04', '05', '06', '07', '08'],
  PRESSURE: ['09', '10', '11', '12', '13'],
};

const THEME_CATEGORIES = [
  { key: 'POLITICS', label: 'POLITICS' },
  { key: 'ECONOMY', label: 'ECONOMY' },
  { key: 'HEALTH', label: 'HEALTH' },
  { key: 'ENVIRONMENT', label: 'ENVIRONMENT' },
  { key: 'TECHNOLOGY', label: 'TECHNOLOGY' },
  { key: 'ENERGY', label: 'ENERGY' },
  { key: 'HUMAN_RIGHTS', label: 'HUMAN RIGHTS' },
];

function App() {
  const {
    dateRange,
    mapMode,
    setMapMode,
    setDateRange,
    dateWindowReady,
    setDateWindowReady,
    eventRootCodes,
    setEventRootCodes,
    geoFilter,
    isDarkTheme,
    setIsDarkTheme,
  } = useStore();

  // Apply theme to root element whenever it changes
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDarkTheme ? 'dark' : 'light');
  }, [isDarkTheme]);
  const [viewMode, setViewMode] = useState<'dashboard' | 'map'>('dashboard');
  const [activeCategory, setActiveCategory] = useState('ALL');
  const [activeThemeCategory, setActiveThemeCategory] = useState<string | null>(null);
  const [showDateSlider, setShowDateSlider] = useState(false);
  const [showSystemPanel, setShowSystemPanel] = useState(false);
  const hasAlignedDateWindow = useRef(false);

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: apiService.getHealth,
    refetchInterval: 60000,
  });

  const pulseQuery = useQuery({
    queryKey: ['global-pulse', dateRange[0], dateRange[1], eventRootCodes, geoFilter, activeThemeCategory],
    queryFn: () => apiService.getGlobalPulse(dateRange[0], dateRange[1], eventRootCodes, geoFilter, activeThemeCategory),
    refetchInterval: 60000,
    enabled: dateWindowReady,
  });

  const themeCategoriesQuery = useQuery({
    queryKey: ['theme-categories'],
    queryFn: () => apiService.getThemeCategories(),
    staleTime: 1000 * 60 * 30,
    retry: 1,
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
    <div className="flex flex-col h-screen w-screen bg-surface-900 overflow-hidden" style={{ color: isDarkTheme ? 'white' : '#0F172A' }}>

      {/* ── Header ── */}
      <header className="h-14 border-b border-white/10 flex items-center justify-between px-6 bg-surface-800 z-50 shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-cyber-blue flex items-center justify-center rounded-sm shadow-[0_0_15px_rgba(0,243,255,0.4)]">
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

        <div className="flex items-center gap-3">
          {/* Date range picker */}
          <div className="relative">
            <button
              onClick={() => setShowDateSlider(!showDateSlider)}
              className={`flex items-center gap-2 px-3 py-1.5 bg-surface-900 border ${showDateSlider ? 'border-cyber-blue' : 'border-white/10 hover:border-white/30'} rounded transition-colors`}
            >
              <Calendar size={14} className={showDateSlider ? 'text-cyber-blue' : 'text-white/70'} />
              <span className={`text-[10px] font-mono uppercase tracking-widest ${showDateSlider ? 'text-cyber-blue' : 'text-white/70'}`}>
                {dateRange[0]} — {dateRange[1]}
              </span>
            </button>
            {showDateSlider && (
              <div className="absolute top-12 right-0 w-[500px] z-50 animate-in slide-in-from-top-2 fade-in duration-200">
                <DateRangeSlider />
              </div>
            )}
          </div>

          {/* System / Runtime Controls button */}
          <button
            onClick={() => setShowSystemPanel(true)}
            className={`flex items-center gap-2 px-3 py-1.5 bg-surface-900 border border-white/10 hover:border-terminal-green/50 rounded transition-colors group`}
            title="Runtime Controls & System Health"
          >
            <Terminal size={14} className="text-white/50 group-hover:text-terminal-green transition-colors" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/50 group-hover:text-terminal-green transition-colors hidden sm:block">System</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={() => setIsDarkTheme(!isDarkTheme)}
            title={isDarkTheme ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            className="relative flex items-center gap-2 px-3 py-1.5 rounded border border-white/10 bg-surface-900 hover:border-cyber-blue/50 transition-colors group overflow-hidden"
          >
            {/* Animated background pill */}
            <span
              className={`absolute inset-0 rounded transition-all duration-500 ${isDarkTheme
                  ? 'bg-transparent'
                  : 'bg-gradient-to-r from-amber-100/30 to-sky-100/20'
                }`}
            />
            <span className="relative flex items-center gap-2">
              {isDarkTheme ? (
                <>
                  <Sun
                    size={14}
                    className="text-amber-400 group-hover:rotate-90 transition-transform duration-500"
                  />
                  <span className="text-[10px] font-mono uppercase tracking-widest text-white/50 group-hover:text-amber-400 transition-colors hidden sm:block">
                    Light
                  </span>
                </>
              ) : (
                <>
                  <Moon
                    size={14}
                    className="text-cyber-blue group-hover:-rotate-12 transition-transform duration-500"
                  />
                  <span className="text-[10px] font-mono uppercase tracking-widest hidden sm:block" style={{ color: '#0F6FBF' }}>
                    Dark
                  </span>
                </>
              )}
            </span>
          </button>

          {/* Map Mode Toggle */}
          {viewMode === 'map' && (
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
          )}
        </div>
      </header>

      {/* ── Filters Row ── */}
      <div className="border-b border-white/5 bg-surface-800/50 px-6 py-3">
        <div className="flex flex-wrap items-end gap-4">
          <SearchableDropdown
            title="Category"
            value={activeCategory}
            options={CATEGORIES.map((cat) => ({ value: cat, label: cat }))}
            placeholder="ALL"
            onChange={(value) => {
              const next = value || 'ALL';
              setActiveCategory(next);
              setEventRootCodes(CATEGORY_TO_ROOT_CODES[next] || null);
            }}
          />

          <SearchableDropdown
            title="Theme"
            value={activeThemeCategory}
            options={((): DropdownOption[] => {
              const counts = themeCategoriesQuery.data?.data || {};
              const base: DropdownOption = { value: null, label: 'ALL THEMES' };
              const options = THEME_CATEGORIES.map((cat) => ({
                value: cat.key,
                label: cat.label,
                count: counts[cat.key],
              }));
              return [base, ...options];
            })()}
            placeholder="ALL THEMES"
            onChange={(value) => setActiveThemeCategory(value)}
          />
        </div>
      </div>

      <GeoFilterBar />

      {/* ── Main Layout ── */}
      <main className="flex-1 relative overflow-hidden flex flex-col">
        {viewMode === 'dashboard' ? (
          <div className="flex-1 overflow-y-auto p-6 md:p-8 custom-scrollbar">
            <div className="max-w-7xl mx-auto space-y-6">

              {/* KPI Metrics Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="glass-panel p-5 rounded-xl flex flex-col justify-between shadow-lg border-white/5 hover:border-cyber-blue/30 transition-colors relative overflow-hidden group">
                  <div className="absolute -right-4 -top-4 w-16 h-16 bg-cyber-blue/5 rounded-full group-hover:scale-150 transition-transform duration-500 blur-xl" />
                  <div className="flex items-center gap-2 mb-2">
                    <Activity size={14} className="text-cyber-blue" />
                    <span className="data-ink text-[10px]">Global Events</span>
                  </div>
                  <div className="text-3xl font-bold font-mono text-white glowing-text">
                    {pulseQuery.isLoading ? '...' : pulseQuery.data?.total_events_today.toLocaleString() || 0}
                  </div>
                  <div className="text-[10px] font-mono text-white/40 mt-2 uppercase">24 Hour Window</div>
                </div>

                <div className="glass-panel p-5 rounded-xl flex flex-col justify-between shadow-lg border-white/5 hover:border-terminal-green/30 transition-colors relative overflow-hidden group">
                  <div className="absolute -right-4 -top-4 w-16 h-16 bg-terminal-green/5 rounded-full group-hover:scale-150 transition-transform duration-500 blur-xl" />
                  <div className="flex items-center gap-2 mb-2">
                    <Globe size={14} className="text-terminal-green" />
                    <span className="data-ink text-terminal-green text-[10px]">Most Active Region</span>
                  </div>
                  <div className="text-2xl font-bold font-mono text-white truncate">
                    {pulseQuery.isLoading ? '...' : pulseQuery.data?.most_active_display || pulseQuery.data?.most_active_country || 'None'}
                  </div>
                  <div className="text-[10px] font-mono text-white/40 mt-2 uppercase">Highest Volume</div>
                </div>

                <div className="glass-panel p-5 rounded-xl flex flex-col justify-between shadow-lg border-white/5 hover:border-cyber-red/30 transition-colors relative overflow-hidden group">
                  <div className="absolute -right-4 -top-4 w-16 h-16 bg-cyber-red/5 rounded-full group-hover:scale-150 transition-transform duration-500 blur-xl" />
                  <div className="flex items-center gap-2 mb-2">
                    <Activity size={14} className="text-cyber-red" />
                    <span className="data-ink text-cyber-red text-[10px]">Highest Hostility</span>
                  </div>
                  <div className="text-2xl font-bold font-mono text-white truncate">
                    {pulseQuery.isLoading ? '...' : pulseQuery.data?.most_hostile_display || pulseQuery.data?.most_hostile_country || 'None'}
                  </div>
                  <div className="text-[10px] font-mono text-white/40 mt-2 uppercase">Lowest Goldstein Avg</div>
                </div>

                <div className="glass-panel p-5 rounded-xl flex flex-col justify-between shadow-lg border-white/5 hover:border-amber-400/30 transition-colors relative overflow-hidden group">
                  <div className="absolute -right-4 -top-4 w-16 h-16 bg-amber-400/5 rounded-full group-hover:scale-150 transition-transform duration-500 blur-xl" />
                  <div className="flex items-center gap-2 mb-2">
                    <Database size={14} className="text-amber-400" />
                    <span className="data-ink text-amber-400 text-[10px]">Conflict Ratio</span>
                  </div>
                  <div className="text-3xl font-bold font-mono text-white">
                    {pulseQuery.isLoading ? '...' : pulseQuery.data?.global_conflict_ratio != null ? (pulseQuery.data.global_conflict_ratio * 100).toFixed(1) + '%' : '--'}
                  </div>
                  <div className="text-[10px] font-mono text-white/40 mt-2 uppercase">Global Average</div>
                </div>
              </div>

              {/* Event Volume Trend Chart */}
              <EventTrendChart
                eventRootCodes={eventRootCodes}
                geoFilter={geoFilter}
                themeCategory={activeThemeCategory}
              />

              {/* Bento Grid layout */}
              {activeCategory === 'ALL' ? (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

                  {/* Main Middle Column - Top Threats & Map */}
                  <div className="lg:col-span-8 flex flex-col gap-6">
                    {/* Map Launch Hero Card (Condensed) */}
                    <div
                      onClick={() => setViewMode('map')}
                      className="map-launch-card w-full h-32 glass-panel rounded-xl overflow-hidden relative group cursor-pointer border-cyber-blue/30 hover:border-cyber-blue transition-all duration-500 shadow-lg hover:shadow-[0_0_30px_rgba(0,243,255,0.15)] flex items-center px-8 justify-between"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-cyber-blue/5 to-transparent group-hover:from-cyber-blue/10 transition-colors duration-500" />
                      <div className="absolute inset-0 bg-[url('https://upload.wikimedia.org/wikipedia/commons/e/ec/World_map_blank_without_borders.svg')] bg-right bg-cover opacity-10 group-hover:opacity-20 transition-opacity duration-700 pointer-events-none" />

                      <div className="relative z-10 flex items-center gap-6">
                        <div className="w-14 h-14 rounded-full bg-cyber-blue/10 border border-cyber-blue/50 flex items-center justify-center group-hover:scale-110 group-hover:bg-cyber-blue/20 transition-all duration-500">
                          <MapIcon size={28} className="text-cyber-blue" />
                        </div>
                        <div>
                          <h2 className="text-xl md:text-2xl font-mono font-bold uppercase tracking-widest text-white glowing-text">
                            Launch Interactive Map
                          </h2>
                          <p className="text-xs font-mono text-white/70 tracking-wide mt-1">
                            View global geospatial clusters and realtime intel
                          </p>
                        </div>
                      </div>

                      <div className="relative z-10 hidden md:flex items-center gap-2 text-cyber-blue/80 group-hover:text-cyber-blue transition-colors font-mono text-xs uppercase tracking-widest font-bold bg-cyber-blue/10 px-4 py-2 rounded-full border border-cyber-blue/20">
                        Open View <ArrowLeft size={14} className="rotate-180 group-hover:translate-x-1 transition-transform" />
                      </div>
                    </div>

                    {/* Top Threats */}
                    <div className="flex-1 rounded-xl overflow-hidden shadow-lg border border-white/5 min-h-[400px]">
                      <TopThreatCard />
                    </div>
                  </div>

                  {/* Right Column - Spike Alerts only now */}
                  <div className="lg:col-span-4 flex flex-col gap-6">
                    <div className="flex-1 rounded-xl overflow-hidden shadow-lg border border-white/5 min-h-[400px]">
                      <SpikeAlertsCard />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-6">
                  {/* Map Launch Hero Card (Condensed) */}
                  <div
                    onClick={() => setViewMode('map')}
                    className="map-launch-card w-full h-32 glass-panel rounded-xl overflow-hidden relative group cursor-pointer border-cyber-blue/30 hover:border-cyber-blue transition-all duration-500 shadow-lg hover:shadow-[0_0_30px_rgba(0,243,255,0.15)] flex items-center px-8 justify-between"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-cyber-blue/5 to-transparent group-hover:from-cyber-blue/10 transition-colors duration-500" />
                    <div className="absolute inset-0 bg-[url('https://upload.wikimedia.org/wikipedia/commons/e/ec/World_map_blank_without_borders.svg')] bg-right bg-cover opacity-10 group-hover:opacity-20 transition-opacity duration-700 pointer-events-none" />

                    <div className="relative z-10 flex items-center gap-6">
                      <div className="w-14 h-14 rounded-full bg-cyber-blue/10 border border-cyber-blue/50 flex items-center justify-center group-hover:scale-110 group-hover:bg-cyber-blue/20 transition-all duration-500">
                        <MapIcon size={28} className="text-cyber-blue" />
                      </div>
                      <div>
                        <h2 className="text-xl md:text-2xl font-mono font-bold uppercase tracking-widest text-white glowing-text">
                          {activeCategory} INTELLIGENCE MAP
                        </h2>
                        <p className="text-xs font-mono text-white/70 tracking-wide mt-1">
                          View interactive geospatial clusters and intel filtered for {activeCategory}
                        </p>
                      </div>
                    </div>

                    <div className="relative z-10 hidden md:flex items-center gap-2 text-cyber-blue/80 group-hover:text-cyber-blue transition-colors font-mono text-xs uppercase tracking-widest font-bold bg-cyber-blue/10 px-4 py-2 rounded-full border border-cyber-blue/20">
                      Open View <ArrowLeft size={14} className="rotate-180 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </div>

                  {/* The Trending News Feed for this category */}
                  <TrendingNewsFeed
                    category={activeCategory}
                    eventRootCodes={eventRootCodes}
                    geoFilter={geoFilter}
                    themeCategory={activeThemeCategory}
                  />
                </div>
              )}

              {/* Padding at the bottom so the ticker doesn't overlap */}
              <div className="h-24"></div>
            </div>
          </div>
        ) : (
          <div className="flex-1 relative overflow-hidden bg-black">
            <GlobalEventMap themeCategory={activeThemeCategory} />

            {/* Map overlay controls */}
            <div className="absolute top-6 left-6 z-10">
              <button
                onClick={() => setViewMode('dashboard')}
                className="glass-panel px-4 py-2.5 rounded shadow-xl flex items-center gap-3 hover:bg-white/10 transition-colors text-white group border-cyber-blue/30"
              >
                <ArrowLeft size={16} className="text-cyber-blue group-hover:-translate-x-1 transition-transform" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-cyber-blue">Return to Dashboard</span>
              </button>
            </div>
          </div>
        )}

        {/* Intelligence Panel floats over everything when an entity is selected */}
        <IntelligencePanel />

        {/* Ambient controls stuck to bottom */}
        <div className="absolute bottom-0 w-full z-20">
          <GlobalStatsTicker
            eventRootCodes={eventRootCodes}
            geoFilter={geoFilter}
            themeCategory={activeThemeCategory}
          />
        </div>

        {/* ── System Panel Drawer ── */}
        {showSystemPanel && (
          <>
            {/* Backdrop */}
            <div
              className="absolute inset-0 z-40 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowSystemPanel(false)}
            />
            {/* Drawer */}
            <div className="absolute top-0 right-0 h-full w-full max-w-md z-50 flex flex-col bg-surface-800 border-l border-white/10 shadow-2xl animate-in slide-in-from-right duration-300">
              {/* Drawer Header */}
              <div className="h-14 flex items-center justify-between px-5 border-b border-white/10 shrink-0">
                <div className="flex items-center gap-3">
                  <Terminal size={16} className="text-terminal-green" />
                  <span className="font-mono text-sm font-bold uppercase tracking-widest text-white">Runtime Controls</span>
                </div>
                <button
                  onClick={() => setShowSystemPanel(false)}
                  className="p-2 rounded hover:bg-white/10 transition-colors text-white/50 hover:text-white"
                >
                  <X size={16} />
                </button>
              </div>
              {/* Drawer Content */}
              <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
                <SystemControlPanel />
              </div>
            </div>
          </>
        )}

      </main>
    </div>
  );
}

export default App;
