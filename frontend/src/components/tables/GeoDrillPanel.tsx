import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapPin } from 'lucide-react';

import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';
import type { GeoDrillItem } from '../../types';
import { SearchableDropdown, type DropdownOption } from '../ambient/SearchableDropdown';

type GeoFilter = { countryCode: string | null; stateName: string | null; cityName: string | null };

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

export const GeoDrillPanel = () => {
  const { dateRange, dateWindowReady, geoFilter, setGeoFilter } = useStore();

  const countriesQuery = useQuery({
    queryKey: ['geo-drill', 'countries', dateRange[0], dateRange[1], geoFilter.countryCode],
    queryFn: () => apiService.getGeoDrill(dateRange[0], dateRange[1]),
    enabled: dateWindowReady,
    staleTime: 60_000,
  });

  const citiesQuery = useQuery({
    queryKey: ['geo-drill', 'cities', dateRange[0], dateRange[1], geoFilter.countryCode, geoFilter.stateName],
    queryFn: () =>
      apiService.getGeoDrill(
        dateRange[0],
        dateRange[1],
        geoFilter.countryCode,
        geoFilter.stateName
      ),
    enabled: !!geoFilter.countryCode && !!geoFilter.stateName && dateWindowReady,
    staleTime: 60_000,
  });

  if (!geoFilter.countryCode || !geoFilter.stateName) return null;

  const countries = countriesQuery.data?.items ?? [];
  const cities = citiesQuery.data?.items ?? [];

  const activeCountry = useMemo(() => {
    return countries.find((item) => getCountryCode(item) === geoFilter.countryCode?.toUpperCase()) || null;
  }, [countries, geoFilter.countryCode]);

  const countryLabel = activeCountry ? formatCountryLabel(activeCountry) : geoFilter.countryCode;

  const handleClear = () => {
    setGeoFilter({
      countryCode: geoFilter.countryCode,
      stateName: null,
      cityName: null,
    });
  };

  const cityOptions = useMemo<DropdownOption[]>(() => {
    const base: DropdownOption = { value: null, label: 'ALL CITIES' };
    const options = cities.map((item) => ({
      value: item.name,
      label: item.name,
      count: item.count,
    }));
    return [base, ...options];
  }, [cities]);

  return (
    <section className="bg-surface-900/40 p-4 rounded-lg border border-white/10 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-cyber-blue">
          <MapPin size={12} className="text-cyber-blue" />
          <span>Location Filter</span>
        </div>
        <button
          onClick={handleClear}
          className="text-[9px] font-mono uppercase tracking-widest text-cyber-red/80 hover:text-cyber-red transition-colors"
        >
          Clear
        </button>
      </div>

      <div className="text-[11px] font-mono text-white/70">
        <div>Country: {countryLabel}</div>
        <div>State: {geoFilter.stateName}</div>
      </div>

      <SearchableDropdown
        title="City"
        value={geoFilter.cityName}
        options={cityOptions}
        placeholder="ALL CITIES"
        onChange={(value) => setGeoFilter({
          countryCode: geoFilter.countryCode,
          stateName: geoFilter.stateName,
          cityName: value,
        })}
      />
    </section>
  );
};
