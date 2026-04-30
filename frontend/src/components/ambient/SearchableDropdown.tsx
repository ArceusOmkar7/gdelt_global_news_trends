import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';

export type DropdownOption = {
  value: string | null;
  label: string;
  count?: number;
  disabled?: boolean;
  disabledReason?: string;
};

type SearchableDropdownProps = {
  title: string;
  value: string | null;
  options: DropdownOption[];
  placeholder?: string;
  onChange: (value: string | null) => void;
  disabled?: boolean;
  disabledReason?: string;
  widthClass?: string;
};

export const SearchableDropdown = ({
  title,
  value,
  options,
  placeholder,
  onChange,
  disabled = false,
  disabledReason,
  widthClass = 'min-w-[220px]',
}: SearchableDropdownProps) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const selected = useMemo(
    () => options.find((opt) => opt.value === value) || null,
    [options, value]
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((opt) => opt.label.toLowerCase().includes(needle));
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const handleClick = (event: MouseEvent) => {
      if (!wrapperRef.current) return;
      if (!wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const displayLabel = selected?.label || placeholder || 'Select';
  const isDisabled = disabled || false;
  const disabledTitle = disabledReason || (disabled ? 'Unavailable' : undefined);

  return (
    <div className={`flex flex-col gap-1 ${widthClass}`} ref={wrapperRef}>
      <span className="text-[9px] font-mono uppercase tracking-widest text-white/50">{title}</span>
      <button
        type="button"
        onClick={() => !isDisabled && setOpen((prev) => !prev)}
        className={`flex items-center justify-between gap-2 px-3 py-2 rounded border text-[11px] font-mono uppercase tracking-widest transition-colors ${isDisabled
          ? 'border-white/10 text-white/30 bg-surface-900/40 cursor-not-allowed'
          : 'border-white/15 text-white/70 bg-surface-900 hover:border-cyber-blue/40'
        }`}
        title={disabledTitle}
      >
        <span className="truncate">{displayLabel}</span>
        <ChevronDown size={14} className="text-white/40" />
      </button>

      {open && !isDisabled && (
        <div className="relative">
          <div className="absolute top-2 left-0 right-0 z-50 rounded border border-white/10 bg-surface-900 shadow-xl">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10">
              <Search size={12} className="text-white/40" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search..."
                className="w-full bg-transparent text-[11px] font-mono text-white/70 outline-none"
              />
            </div>
            <div className="max-h-56 overflow-y-auto custom-scrollbar">
              {filtered.length === 0 ? (
                <div className="px-3 py-2 text-[11px] font-mono text-white/40">No matches</div>
              ) : (
                filtered.map((opt) => (
                  <button
                    key={`${opt.label}-${opt.value ?? 'null'}`}
                    type="button"
                    onClick={() => {
                      if (opt.disabled) return;
                      onChange(opt.value ?? null);
                      setOpen(false);
                      setQuery('');
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 text-left text-[11px] font-mono uppercase tracking-widest transition-colors ${opt.disabled
                      ? 'text-white/30 cursor-not-allowed'
                      : 'text-white/70 hover:bg-white/5'
                    }`}
                    title={opt.disabledReason}
                  >
                    <span className="truncate">{opt.label}</span>
                    {typeof opt.count === 'number' && (
                      <span className="text-[10px] text-white/30">{opt.count.toLocaleString()}</span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
