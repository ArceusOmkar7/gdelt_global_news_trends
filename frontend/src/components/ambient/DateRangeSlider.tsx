import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CalendarRange, Clock3, CalendarDays } from 'lucide-react';

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

function indicesFromDateRange(
  window: DayWindow,
  startIso: string,
  endIso: string
): { startIdx: number; endIdx: number } {
  const rawStart = parseIsoDay(startIso) ?? window.min;
  const rawEnd = parseIsoDay(endIso) ?? window.max;

  const safeStart = clampDate(rawStart, window.min, window.max);
  const safeEnd = clampDate(rawEnd, window.min, window.max);

  // Always maintain start <= end
  const orderedStart = safeStart.getTime() <= safeEnd.getTime() ? safeStart : safeEnd;
  const orderedEnd = safeStart.getTime() <= safeEnd.getTime() ? safeEnd : safeStart;

  return {
    startIdx: diffDays(window.min, orderedStart),
    endIdx: diffDays(window.min, orderedEnd),
  };
}

export const DateRangeSlider = () => {
  const { dateRange, setDateRange } = useStore();
  const [startIdx, setStartIdx] = useState(0);
  const [endIdx, setEndIdx] = useState(0);

  // Refs for the hidden native date picker inputs
  const startPickerRef = useRef<HTMLInputElement>(null);
  const endPickerRef = useRef<HTMLInputElement>(null);

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: apiService.getHealth,
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: 1,
  });

  const availableWindow = useMemo(
    () => resolveWindow(
      healthQuery.data?.hot_tier.last_updated_at,
      healthQuery.data?.hot_tier.coverage_days
    ),
    [healthQuery.data?.hot_tier.coverage_days, healthQuery.data?.hot_tier.last_updated_at]
  );

  useEffect(() => {
    if (!availableWindow) return;
    const indices = indicesFromDateRange(availableWindow, dateRange[0], dateRange[1]);
    // Defer state updates to avoid synchronous setState inside useEffect
    queueMicrotask(() => {
      setStartIdx((prev) => (prev === indices.startIdx ? prev : indices.startIdx));
      setEndIdx((prev) => (prev === indices.endIdx ? prev : indices.endIdx));
    });
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

  const commitDateRange = (nextStartIdx: number, nextEndIdx: number) => {
    if (!availableWindow) return;
    // Guard: always ensure start <= end before committing
    const safeStart = Math.min(nextStartIdx, nextEndIdx);
    const safeEnd = Math.max(nextStartIdx, nextEndIdx);
    const nextStart = toIsoDay(addDays(availableWindow.min, safeStart));
    const nextEnd = toIsoDay(addDays(availableWindow.min, safeEnd));
    if (dateRange[0] !== nextStart || dateRange[1] !== nextEnd) {
      setDateRange([nextStart, nextEnd]);
    }
  };

  const onStartChange = (value: number) => {
    // Clamp: start must not exceed end
    const next = Math.min(value, endIdx);
    setStartIdx(next);
    commitDateRange(next, endIdx);
  };

  const onEndChange = (value: number) => {
    // Clamp: end must not be before start
    const next = Math.max(value, startIdx);
    setEndIdx(next);
    commitDateRange(startIdx, next);
  };

  // When thumbs are at the same position (or start >= end), elevate start thumb
  // so the user can drag it to the left. Otherwise end thumb is on top.
  const startThumbZ = startIdx >= endIdx ? 4 : 3;
  const endThumbZ = startIdx >= endIdx ? 3 : 4;

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

  // True when no preset button matches current selection (custom range)
  const isCustomRange = availableWindow != null && !PRESET_WINDOWS.some((p) => isPresetActive(p));

  // Open the native browser date picker
  const openDatePicker = (which: 'start' | 'end') => {
    const ref = which === 'start' ? startPickerRef : endPickerRef;
    if (!ref.current) return;
    try {
      ref.current.showPicker();
    } catch {
      ref.current.focus();
    }
  };

  // Handle native date input changes
  const handleDatePickerChange = (which: 'start' | 'end', isoValue: string) => {
    if (!availableWindow || !isoValue) return;
    const parsed = parseIsoDay(isoValue);
    if (!parsed) return;
    const clamped = clampDate(parsed, availableWindow.min, availableWindow.max);
    const idx = diffDays(availableWindow.min, clamped);

    if (which === 'start') {
      // Ensure start <= end; if selected start > end, push end up to start
      const safeStart = idx;
      const safeEnd = Math.max(endIdx, safeStart);
      setStartIdx(safeStart);
      setEndIdx(safeEnd);
      commitDateRange(safeStart, safeEnd);
    } else {
      // Ensure end >= start; if selected end < start, push start down to end
      const safeEnd = idx;
      const safeStart = Math.min(startIdx, safeEnd);
      setStartIdx(safeStart);
      setEndIdx(safeEnd);
      commitDateRange(safeStart, safeEnd);
    }
  };

  return (
    <div className="w-full">
      <div className="glass-panel rounded-md overflow-hidden shadow-[0_0_30px_rgba(0,0,0,0.8)] border border-cyber-blue/30 bg-surface-900/95 backdrop-blur-xl">

        {/* ── Header bar ── */}
        <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between bg-surface-800/50">
          <div className="flex items-center gap-2 text-cyber-blue">
            <CalendarRange size={14} />
            <span className="data-ink">Timeline Window</span>
          </div>
          <div className="text-[9px] md:text-[10px] font-mono uppercase tracking-widest text-white/45">
            {selectedStart && selectedEnd
              ? (formatDateLabel(selectedStart) === formatDateLabel(selectedEnd)
                  ? formatDateLabel(selectedStart)
                  : `${formatDateLabel(selectedStart)} to ${formatDateLabel(selectedEnd)}`)
              : 'window unavailable'}
          </div>
        </div>

        <div className="p-4 flex flex-col gap-4">

          {/* ── From / To clickable labels with hidden date pickers ── */}
          {selectedStart && selectedEnd && formatDateLabel(selectedStart) === formatDateLabel(selectedEnd) ? (
            /* Single-day selection — show one centred date with both pickers accessible */
            <div className="flex items-center justify-center gap-2">
              <button
                type="button"
                disabled={disabled}
                onClick={() => openDatePicker('start')}
                title="Click to pick date"
                className="group flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-white/75 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <CalendarDays size={11} className="text-cyber-blue/60 group-hover:text-cyber-blue transition-colors" />
                <span className="text-cyber-blue font-bold group-hover:underline underline-offset-2">
                  {formatDateLabel(selectedStart)}
                </span>
                <span className="text-white/40 text-[9px] font-mono uppercase tracking-widest ml-1">(single day)</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-3">
              {/* Start date — click to open browser date picker */}
              <button
                type="button"
                disabled={disabled}
                onClick={() => openDatePicker('start')}
                title="Click to pick start date"
                className="group flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-white/75 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                From{' '}
                <span className="text-cyber-blue font-bold group-hover:underline underline-offset-2">
                  {selectedStart ? formatDateLabel(selectedStart) : '--'}
                </span>
                <CalendarDays size={11} className="text-cyber-blue/60 group-hover:text-cyber-blue transition-colors" />
              </button>

              {/* End date — click to open browser date picker */}
              <button
                type="button"
                disabled={disabled}
                onClick={() => openDatePicker('end')}
                title="Click to pick end date"
                className="group flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-white/75 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <CalendarDays size={11} className="text-cyber-blue/60 group-hover:text-cyber-blue transition-colors" />
                <span className="text-cyber-blue font-bold group-hover:underline underline-offset-2">
                  {selectedEnd ? formatDateLabel(selectedEnd) : '--'}
                </span>
                {' '}To
              </button>
            </div>
          )}

          {/* ── Hidden native date picker inputs ── */}
          <input
            ref={startPickerRef}
            type="date"
            tabIndex={-1}
            aria-hidden="true"
            min={availableWindow ? toIsoDay(availableWindow.min) : undefined}
            max={availableWindow ? toIsoDay(addDays(availableWindow.min, endIdx)) : undefined}
            value={selectedStart ? toIsoDay(selectedStart) : ''}
            onChange={(e) => handleDatePickerChange('start', e.target.value)}
            className="absolute opacity-0 pointer-events-none w-0 h-0 overflow-hidden"
          />
          <input
            ref={endPickerRef}
            type="date"
            tabIndex={-1}
            aria-hidden="true"
            min={availableWindow ? toIsoDay(addDays(availableWindow.min, startIdx)) : undefined}
            max={availableWindow ? toIsoDay(availableWindow.max) : undefined}
            value={selectedEnd ? toIsoDay(selectedEnd) : ''}
            onChange={(e) => handleDatePickerChange('end', e.target.value)}
            className="absolute opacity-0 pointer-events-none w-0 h-0 overflow-hidden"
          />

          {/* ── Quick range presets + CUSTOM badge ── */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-4">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-mono text-white/60">
              <Clock3 size={12} className="text-cyber-blue" />
              {availableWindow ? `${availableWindow.totalDays} days available` : 'waiting for data'}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[9px] uppercase tracking-[0.16em] font-mono text-white/45 mr-1">
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
                      px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.14em]
                      border rounded transition-colors
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

              {/* CUSTOM badge — appears when no preset matches */}
              {isCustomRange && (
                <span
                  className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.14em]
                    border rounded bg-amber-400/10 text-amber-400 border-amber-400/50
                    animate-in fade-in duration-200"
                >
                  Custom
                </span>
              )}
            </div>
          </div>

          {/* ── Dual-range slider ── */}
          <div className="relative h-12 select-none mt-2">
            {/* Track background */}
            <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-[4px] rounded-full bg-white/10" />
            {/* Active segment */}
            <div
              className="absolute top-1/2 -translate-y-1/2 h-[4px] rounded-full bg-cyber-blue shadow-[0_0_15px_rgba(0,243,255,0.6)]"
              style={activeTrackStyle}
            />

            {/*
              Both inputs use pointer-events: none on the track (set via .slider-thumb class)
              and pointer-events: all only on the thumb pseudo-element (set in index.css).
              This ensures both thumbs are independently draggable without the track
              of one input intercepting clicks meant for the other.

              Z-index trick: when startIdx >= endIdx (thumbs at same spot),
              elevate start thumb so it can be dragged leftward.
            */}
            <input
              type="range"
              min={minIdx}
              max={maxIdx}
              value={startIdx}
              onChange={(e) => onStartChange(Number(e.target.value))}
              disabled={disabled}
              aria-label="Start date"
              style={{ zIndex: startThumbZ }}
              className="absolute inset-0 w-full h-full appearance-none bg-transparent slider-thumb cursor-pointer"
            />
            <input
              type="range"
              min={minIdx}
              max={maxIdx}
              value={endIdx}
              onChange={(e) => onEndChange(Number(e.target.value))}
              disabled={disabled}
              aria-label="End date"
              style={{ zIndex: endThumbZ }}
              className="absolute inset-0 w-full h-full appearance-none bg-transparent slider-thumb cursor-pointer"
            />
          </div>

          {/* ── Timeline axis labels ── */}
          <div className="flex items-center justify-between gap-3 text-[10px] uppercase font-mono tracking-[0.12em] mt-1">
            <span className="text-white/40">
              {availableWindow ? formatDateLabel(availableWindow.min) : 'no coverage'}
            </span>
            <span className="text-cyber-blue font-bold">
              {selectedSpan > 0 ? `${selectedSpan} day window` : 'window unavailable'}
            </span>
            <span className="text-white/40">
              {availableWindow ? formatDateLabel(availableWindow.max) : '--'}
            </span>
          </div>

          {!availableWindow && (
            <div className="text-[10px] uppercase tracking-wider font-mono text-cyber-red/80 mt-2">
              Timeline unavailable: hot-tier coverage metadata is missing.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
