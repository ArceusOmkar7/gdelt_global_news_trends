import type {
  HealthResponse,
  MapDataResponse,
  EventAnalysis,
  RuntimeSettingsResponse,
  RiskScoreResponse,
  ForecastResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiService = {
  getMapData: async (
    bbox: { n: number; s: number; e: number; w: number },
    zoom: number,
    startDate: string,
    endDate: string,
    eventRootCode?: string | null,
    signal?: AbortSignal
  ): Promise<MapDataResponse> => {
    const params = new URLSearchParams({
      bbox_n: bbox.n.toString(),
      bbox_s: bbox.s.toString(),
      bbox_e: bbox.e.toString(),
      bbox_w: bbox.w.toString(),
      zoom: zoom.toString(),
      start_date: startDate,
      end_date: endDate,
    });

    if (eventRootCode) {
      params.append('event_root_code', eventRootCode);
    }

    const response = await fetch(`${API_BASE_URL}/events/map?${params}`, { signal });
    if (!response.ok) {
      throw new Error(`Failed to fetch map data: ${response.statusText}`);
    }
    return response.json();
  },

  getEventsByRegion: async (
    countryCode: string,
    startDate: string,
    endDate: string,
    limit: number = 10
  ) => {
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      limit: limit.toString(),
    });

    const response = await fetch(`${API_BASE_URL}/events/region/${countryCode}?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch regional events: ${response.statusText}`);
    }
    return response.json();
  },

  getRegionalStats: async (
    countryCode: string,
    startDate: string,
    endDate: string
  ) => {
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
    });

    const response = await fetch(`${API_BASE_URL}/events/region/${countryCode}/stats?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch regional stats: ${response.statusText}`);
    }
    return response.json();
  },

  getRiskScore: async (
    countryCode: string,
    startDate: string,
    endDate: string
  ): Promise<RiskScoreResponse> => {
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
    });

    const response = await fetch(`${API_BASE_URL}/events/region/${countryCode}/risk-score?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch risk score: ${response.statusText}`);
    }
    return response.json();
  },

  getForecast: async (countryCode: string): Promise<ForecastResponse> => {
    const response = await fetch(`${API_BASE_URL}/analytics/forecast/${countryCode}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch forecast: ${response.statusText}`);
    }
    return response.json();
  },

  analyzeEvent: async (eventId: number): Promise<EventAnalysis> => {
    const response = await fetch(`${API_BASE_URL}/events/${eventId}/analyze`);
    if (!response.ok) {
      throw new Error(`Failed to analyze event: ${response.statusText}`);
    }
    return response.json();
  },

  getHealth: async (): Promise<HealthResponse> => {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`Failed to fetch health status: ${response.statusText}`);
    }
    return response.json();
  },

  getRuntimeSettings: async (): Promise<RuntimeSettingsResponse> => {
    const response = await fetch(`${API_BASE_URL}/health/settings`);
    if (!response.ok) {
      throw new Error(`Failed to fetch runtime settings: ${response.statusText}`);
    }
    return response.json();
  },
};
