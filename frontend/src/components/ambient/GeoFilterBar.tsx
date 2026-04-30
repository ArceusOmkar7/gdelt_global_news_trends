import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';

import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';
import type { GeoDrillItem } from '../../types';
import { SearchableDropdown, type DropdownOption } from './SearchableDropdown';

function getCountryCode(item: GeoDrillItem): string {
  return (item.code || item.name || '').toUpperCase();
}

function formatCountryLabel(item: GeoDrillItem): string {
  if (item.display) return item.display;
  if (item.code && item.name && item.name !== item.code) {
    return `${item.name} (${item.code})`;
  }
  return item.name;
}

export const GeoFilterBar = () => {
  const { dateRange, dateWindowReady, geoFilter, setGeoFilter } = useStore();

  const countriesQuery = useQuery({
    queryKey: ['geo-drill', 'countries', dateRange[0], dateRange[1], geoFilter.countryCode],
    queryFn: () => apiService.getGeoDrill(dateRange[0], dateRange[1]),
    enabled: dateWindowReady,
    staleTime: 60_000,
  });

  const statesQuery = useQuery({
    queryKey: ['geo-drill', 'states', dateRange[0], dateRange[1], geoFilter.countryCode],
    queryFn: () => apiService.getGeoDrill(dateRange[0], dateRange[1], geoFilter.countryCode, null),
    enabled: !!geoFilter.countryCode && dateWindowReady,
    staleTime: 60_000,
  });

  const countries = countriesQuery.data?.items ?? [];
  const states = statesQuery.data?.items ?? [];
  const stateAvailable = statesQuery.data?.state_available ?? true;
  const stateReason =
    statesQuery.data?.state_reason ||
    'State drill requires ActionGeo lat/long; refresh hot-tier data (daily pull or realtime fetch).';

  const countryOptions = useMemo<DropdownOption[]>(() => {
    const base: DropdownOption = { value: null, label: 'GLOBAL' };
    const options = countries
      .map((item): DropdownOption | null => {
        const code = getCountryCode(item);
        if (!code) return null;
        return {
          value: code,
          label: formatCountryLabel(item),
          count: item.count,
        };
      })
      .filter((opt): opt is DropdownOption => opt !== null);
    return [base, ...options];
  }, [countries]);

  const stateOptions = useMemo<DropdownOption[]>(() => {
    if (!stateAvailable) return [];
    return states.map((item) => ({
      value: item.name,
      label: item.name,
      count: item.count,
    }));
  }, [stateAvailable, states]);

  const handleClear = () => {
    setGeoFilter({ countryCode: null, stateName: null, cityName: null });
  };

  return (
    <>
      <SearchableDropdown
        title="Country"
        value={geoFilter.countryCode}
        options={countryOptions}
        placeholder="GLOBAL"
        onChange={(value) => setGeoFilter({ countryCode: value, stateName: null, cityName: null })}
      />

      <SearchableDropdown
        title="State"
        value={geoFilter.stateName}
        options={stateOptions}
        placeholder="All states"
        disabled={!geoFilter.countryCode || !stateAvailable}
        disabledReason={!geoFilter.countryCode ? 'Select a country first.' : stateReason}
        onChange={(value) => setGeoFilter({
          countryCode: geoFilter.countryCode,
          stateName: value,
          cityName: null,
        })}
      />

      {(geoFilter.countryCode || geoFilter.stateName || geoFilter.cityName) && (
        <button
          onClick={handleClear}
          className="ml-auto flex items-center gap-1 px-3 py-2 rounded border border-cyber-red/40 text-cyber-red/80 hover:text-cyber-red hover:border-cyber-red/70 transition-all text-[10px] font-mono uppercase tracking-widest"
        >
          <X size={12} />
          Clear
        </button>
      )}
    </>
  );
};
