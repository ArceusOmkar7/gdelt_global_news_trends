import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CalendarRange, ChevronDown, ChevronUp, Clock3 } from 'lucide-react';

import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';

type DayWindow = {
  min: Date;
  max: Date;
  totalDays: number;
};

type PresetWindow = {
  label: string;
  days: number | 'full';
};

const DAY_MS = 24 * 60 * 60 * 1000;
const PRESET_WINDOWS: PresetWindow[] = [
  { label: '1D', days: 1 },
  { label: '3D', days: 3 },
  { label: '7D', days: 7 },
  { label: '14D', days: 14 },
  { label: 'FULL', days: 'full' },
];

function normalizeLocalDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function parseIsoDay(value: string): Date | null {
  const parts = value.split('-');
  if (parts.length !== 3) return null;
  const y = Number(parts[0]);
  const m = Number(parts[1]);
  const day = Number(parts[2]);
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(day)) return null;
  const parsed = new Date(y, m - 1, day);
  if (Number.isNaN(parsed.getTime())) return null;
  return normalizeLocalDay(parsed);
}

function toIsoDay(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addDays(base: Date, days: number): Date {
  const next = new Date(base);
  next.setDate(next.getDate() + days);
  return normalizeLocalDay(next);
}

function diffDays(start: Date, end: Date): number {
  return Math.round((normalizeLocalDay(end).getTime() - normalizeLocalDay(start).getTime()) / DAY_MS);
}

function clampDate(d: Date, min: Date, max: Date): Date {
  const value = normalizeLocalDay(d).getTime();
  const minTs = normalizeLocalDay(min).getTime();
  const maxTs = normalizeLocalDay(max).getTime();
  return new Date(Math.max(minTs, Math.min(value, maxTs)));
}

function formatDateLabel(d: Date): string {
  return toIsoDay(d);
}

function resolveWindow(
  lastUpdatedAt: string | null | undefined,
  coverageDays: number | null | undefined
): DayWindow | null {
  if (!lastUpdatedAt) return null;

  const parsed = new Date(lastUpdatedAt);
  if (Number.isNaN(parsed.getTime())) return null;

  const max = normalizeLocalDay(parsed);
  const safeCoverage = Math.max(1, Number.isFinite(coverageDays ?? 0) ? Number(coverageDays) : 1);
  const min = addDays(max, -(safeCoverage - 1));
  return {
    min,
    max,
    totalDays: diffDays(min, max) + 1,
  };
}

function indicesFromDateRange(window: DayWindow, startIso: string, endIso: string): { startIdx: number; endIdx: number } {
  const rawStart = parseIsoDay(startIso) ?? window.min;
  const rawEnd = parseIsoDay(endIso) ?? window.max;

  const safeStart = clampDate(rawStart, window.min, window.max);
  const safeEnd = clampDate(rawEnd, window.min, window.max);

  const orderedStart = safeStart.getTime() <= safeEnd.getTime() ? safeStart : safeEnd;
  const orderedEnd = safeStart.getTime() <= safeEnd.getTime() ? safeEnd : safeStart;

  return {
    startIdx: diffDays(window.min, orderedStart),
    endIdx: diffDays(window.min, orderedEnd),
  };
}

export const DateRangeSlider = () => {
  const {
    dateRange,
    setDateRange,
    tickerCollapsed,
    dateSliderCollapsed,
    setDateSliderCollapsed,
  } = useStore();
  const [startIdx, setStartIdx] = useState(0);
  const [endIdx, setEndIdx] = useState(0);

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: apiService.getHealth,
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: 1,
  });

  const availableWindow = useMemo(
    () => resolveWindow(healthQuery.data?.hot_tier.last_updated_at, healthQuery.data?.hot_tier.coverage_days),
    [healthQuery.data?.hot_tier.coverage_days, healthQuery.data?.hot_tier.last_updated_at]
  );

  useEffect(() => {
    if (!availableWindow) return;
    const indices = indicesFromDateRange(availableWindow, dateRange[0], dateRange[1]);
    setStartIdx((prev) => (prev === indices.startIdx ? prev : indices.startIdx));
    setEndIdx((prev) => (prev === indices.endIdx ? prev : indices.endIdx));
  }, [availableWindow, dateRange]);

  const minIdx = 0;
  const maxIdx = Math.max(0, (availableWindow?.totalDays ?? 1) - 1);
  const disabled = !availableWindow || maxIdx <= 0;

  const selectedStart = availableWindow ? addDays(availableWindow.min, startIdx) : null;
  const selectedEnd = availableWindow ? addDays(availableWindow.min, endIdx) : null;
  const selectedSpan = selectedStart && selectedEnd ? diffDays(selectedStart, selectedEnd) + 1 : 0;

  const trackStartPct = maxIdx === 0 ? 0 : (startIdx / maxIdx) * 100;
  const trackEndPct = maxIdx === 0 ? 100 : (endIdx / maxIdx) * 100;
  const activeTrackStyle = {
    left: `${trackStartPct}%`,
    width: `${Math.max(0, trackEndPct - trackStartPct)}%`,
  };

  const bottomClass = tickerCollapsed ? 'bottom-8' : 'bottom-10';

  const commitDateRange = (nextStartIdx: number, nextEndIdx: number) => {
    if (!availableWindow) return;
    const clampedStart = addDays(availableWindow.min, nextStartIdx);
    const clampedEnd = addDays(availableWindow.min, nextEndIdx);
    const nextStart = toIsoDay(clampedStart);
    const nextEnd = toIsoDay(clampedEnd);
    if (dateRange[0] !== nextStart || dateRange[1] !== nextEnd) {
      setDateRange([nextStart, nextEnd]);
    }
  };

  const onStartChange = (value: number) => {
    const next = Math.min(value, endIdx);
    setStartIdx(next);
    commitDateRange(next, endIdx);
  };

  const onEndChange = (value: number) => {
    const next = Math.max(value, startIdx);
    setEndIdx(next);
    commitDateRange(startIdx, next);
  };

  const applyPreset = (preset: PresetWindow) => {
    if (!availableWindow) return;
    if (preset.days === 'full') {
      setStartIdx(minIdx);
      setEndIdx(maxIdx);
      commitDateRange(minIdx, maxIdx);
      return;
    }

    const span = Math.min(preset.days, maxIdx + 1);
    const nextEnd = maxIdx;
    const nextStart = Math.max(minIdx, nextEnd - span + 1);
    setStartIdx(nextStart);
    setEndIdx(nextEnd);
    commitDateRange(nextStart, nextEnd);
  };

  const isPresetActive = (preset: PresetWindow): boolean => {
    if (!availableWindow) return false;
    if (preset.days === 'full') {
      return startIdx === minIdx && endIdx === maxIdx;
    }

    const span = Math.min(preset.days, maxIdx + 1);
    const expectedEnd = maxIdx;
    const expectedStart = Math.max(minIdx, expectedEnd - span + 1);
    return startIdx === expectedStart && endIdx === expectedEnd;
  };

  return (
    <div
      className={`
        fixed left-1/2 -translate-x-1/2 ${bottomClass} z-40
        w-[min(92vw,860px)] px-3
      `}
    >
      <div className="glass-panel rounded-md overflow-hidden shadow-[0_0_22px_rgba(0,243,255,0.08)]">
        <button
          onClick={() => setDateSliderCollapsed(!dateSliderCollapsed)}
          className="
            w-full flex items-center justify-between
            px-4 py-3 border-b border-white/5
            hover:bg-white/5 transition-colors
          "
        >
          <div className="flex items-center gap-2 text-cyber-blue">
            <CalendarRange size={14} />
            <span className="data-ink">Timeline Window</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] md:text-[10px] font-mono uppercase tracking-widest text-white/45">
              {selectedStart && selectedEnd
                ? `${formatDateLabel(selectedStart)} to ${formatDateLabel(selectedEnd)}`
                : 'window unavailable'}
            </span>
            {dateSliderCollapsed ? (
              <ChevronDown size={13} className="text-white/30" />
            ) : (
              <ChevronUp size={13} className="text-white/30" />
            )}
          </div>
        </button>

        {!dateSliderCollapsed && (
          <div className="p-3 md:p-4 flex flex-col gap-2 md:gap-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[10px] md:text-[11px] font-mono uppercase tracking-wider text-white/75">
                From <span className="text-cyber-blue font-bold">{selectedStart ? formatDateLabel(selectedStart) : '--'}</span>
              </div>
              <div className="text-[10px] md:text-[11px] font-mono uppercase tracking-wider text-white/75">
                To <span className="text-cyber-blue font-bold">{selectedEnd ? formatDateLabel(selectedEnd) : '--'}</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-mono text-white/60">
                <Clock3 size={12} className="text-cyber-blue" />
                {availableWindow ? `${availableWindow.totalDays} days available` : 'waiting for data'}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[9px] uppercase tracking-[0.16em] font-mono text-white/45">
                  Quick Range
                </span>
                {PRESET_WINDOWS.map((preset) => {
                  const active = isPresetActive(preset);
                  return (
                    <button
                      key={preset.label}
                      type="button"
                      disabled={disabled}
                      onClick={() => applyPreset(preset)}
                      className={`
                        px-2 py-1 text-[9px] md:text-[10px] font-mono uppercase tracking-[0.14em]
                        border rounded-sm transition-colors
                        ${active
                          ? 'bg-cyber-blue/20 text-cyber-blue border-cyber-blue/65'
                          : 'bg-surface-900/55 text-white/60 border-white/15 hover:border-cyber-blue/40 hover:text-cyber-blue'}
                        disabled:opacity-40 disabled:cursor-not-allowed
                      `}
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="relative h-9 select-none">
              <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-[3px] rounded-full bg-white/15" />
              <div
                className="absolute top-1/2 -translate-y-1/2 h-[4px] rounded-full bg-cyber-blue shadow-[0_0_14px_rgba(0,243,255,0.55)]"
                style={activeTrackStyle}
              />

              <input
                type="range"
                min={minIdx}
                max={maxIdx}
                value={startIdx}
                onChange={(e) => onStartChange(Number(e.target.value))}
                disabled={disabled}
                aria-label="Start date"
                className="absolute inset-0 w-full h-full appearance-none bg-transparent pointer-events-auto slider-thumb"
              />
              <input
                type="range"
                min={minIdx}
                max={maxIdx}
                value={endIdx}
                onChange={(e) => onEndChange(Number(e.target.value))}
                disabled={disabled}
                aria-label="End date"
                className="absolute inset-0 w-full h-full appearance-none bg-transparent pointer-events-auto slider-thumb"
              />
            </div>

            <div className="flex items-center justify-between gap-3 text-[9px] md:text-[10px] uppercase font-mono tracking-[0.12em]">
              <span className="text-white/40">
                {availableWindow ? formatDateLabel(availableWindow.min) : 'no coverage'}
              </span>
              <span className="text-cyber-blue font-semibold">
                {selectedSpan > 0 ? `${selectedSpan} day window` : 'window unavailable'}
              </span>
              <span className="text-white/40">
                {availableWindow ? formatDateLabel(availableWindow.max) : '--'}
              </span>
            </div>

            {!availableWindow && (
              <div className="text-[10px] uppercase tracking-wider font-mono text-cyber-red/80">
                Timeline unavailable: hot-tier coverage metadata is missing.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
