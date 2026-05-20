import React from 'react';
import { useStore } from '../../store/useStore';

export const MapLegend: React.FC = () => {
  const { mapMode } = useStore();
  const isHeatmap = mapMode === 'heatmap';

  return (
    <div className="absolute top-6 right-6 z-10 w-[min(340px,calc(100vw-3rem))] glass-panel px-4 py-3.5 rounded shadow-xl border-cyber-blue/30 animate-in fade-in duration-300">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="font-mono text-[10px] font-bold uppercase tracking-widest text-cyber-blue">
          {isHeatmap ? 'Heatmap Density' : 'Signal Clusters'}
        </div>
        <div className="h-px flex-1 bg-white/10" />
      </div>

      {isHeatmap ? (
        <div className="flex flex-col gap-2">
          {/* Gradient bar representing the exact paint colors */}
          <div 
            className="h-2.5 w-full rounded border border-white/5 shadow-inner"
            style={{
              background: 'linear-gradient(to right, rgba(0, 243, 255, 0.2), rgba(0, 255, 65, 0.5), rgba(255, 210, 0, 0.7), rgba(255, 110, 0, 0.8), rgba(255, 0, 60, 0.95))'
            }}
          />
          <div className="flex justify-between font-mono text-[9px] uppercase tracking-wide text-white/50">
            <span>Low Activity</span>
            <span>Active Peak</span>
          </div>
          <p className="text-[9px] text-white/35 font-mono uppercase mt-0.5 leading-normal">
            Volume density based on geocoded real-time event concentrations.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: '#ff003c' }} />
            <div className="min-w-0">
              <div className="text-white/90 text-[11px] font-semibold leading-none truncate">Conflict</div>
              <div className="text-white/45 text-[10px] mt-1 truncate">Goldstein &lt; -2</div>
            </div>
          </div>

          <div className="flex items-center gap-2 min-w-0">
            <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: '#00ff41' }} />
            <div className="min-w-0">
              <div className="text-white/90 text-[11px] font-semibold leading-none truncate">Cooperative</div>
              <div className="text-white/45 text-[10px] mt-1 truncate">Goldstein &gt; 2</div>
            </div>
          </div>

          <div className="flex items-center gap-2 min-w-0">
            <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: '#00f3ff' }} />
            <div className="min-w-0">
              <div className="text-white/90 text-[11px] font-semibold leading-none truncate">Neutral</div>
              <div className="text-white/45 text-[10px] mt-1 truncate">Goldstein -2 to 2</div>
            </div>
          </div>

          <div className="flex items-center gap-2 min-w-0">
            <div className="text-base leading-none shrink-0" style={{ color: 'silver' }}>★</div>
            <div className="min-w-0">
              <div className="text-white/90 text-[11px] font-semibold leading-none truncate">Popular</div>
              <div className="text-white/45 text-[10px] mt-1 truncate">Mentions &gt; 10</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
