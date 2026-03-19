import type {
  HealthResponse,
  MapDataResponse,
  EventAnalysis,
  RuntimeSettingsResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiService = {
  getMapData: async (
    bbox: { n: number; s: number; e: number; w: number },
    zoom: number,
    startDate: string,
    endDate: string,
    eventRootCode?: string | null
  ): Promise<MapDataResponse> => {
    const params = new URLSearchParams({
      bbox_n: bbox.n.toString(),
      bbox_s: bbox.s.toString(),
      bbox_e: bbox.e.toString(),
      bbox_w: bbox.w.toString(),
      zoom: Math.round(zoom).toString(),
      start_date: startDate,
      end_date: endDate,
    });

    if (eventRootCode) {
      params.append('event_root_code', eventRootCode);
    }

    const response = await fetch(`${API_BASE_URL}/events/map?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch map data: ${response.statusText}`);
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
