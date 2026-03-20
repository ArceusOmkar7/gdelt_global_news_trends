import { create } from 'zustand';
import type { ViewState, Event, EventAnalysis } from '../types';

interface DashboardState {
  // Map State
  viewState: ViewState;
  setViewState: (viewState: ViewState) => void;
  
  // Selection State
  selectedEventId: number | null;
  selectedEvent: Event | null;
  setSelectedEvent: (event: Event | null) => void;
  selectedCountry: string | null;
  setSelectedCountry: (countryCode: string | null) => void;
  
  // Analysis State
  currentAnalysis: EventAnalysis | null;
  setCurrentAnalysis: (analysis: EventAnalysis | null) => void;
  isAnalyzing: boolean;
  setIsAnalyzing: (isAnalyzing: boolean) => void;
  
  // Filter State
  dateRange: [string, string];
  setDateRange: (range: [string, string]) => void;
  eventRootCode: string | null;
  setEventRootCode: (code: string | null) => void;

  // Runtime UI Settings
  autoRefreshEnabled: boolean;
  setAutoRefreshEnabled: (enabled: boolean) => void;
  fetchIntervalSeconds: number;
  setFetchIntervalSeconds: (seconds: number) => void;
  healthPollIntervalSeconds: number;
  setHealthPollIntervalSeconds: (seconds: number) => void;

  // UI State
  tickerCollapsed: boolean;
  setTickerCollapsed: (v: boolean) => void;
  threatCardCollapsed: boolean;
  setThreatCardCollapsed: (v: boolean) => void;
}

const getSevenDaysAgo = () => {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().split('T')[0];
};

const getToday = () => {
  return new Date().toISOString().split('T')[0];
};

export const useStore = create<DashboardState>((set) => ({
  // Defaults
  viewState: {
    longitude: 20,
    latitude: 20,
    zoom: 2,
    pitch: 0,
    bearing: 0,
  },
  setViewState: (viewState) => set({ viewState }),
  
  selectedEventId: null,
  selectedEvent: null,
  setSelectedEvent: (event) => set({ 
    selectedEvent: event, 
    selectedEventId: event?.global_event_id || null,
    currentAnalysis: null,
    selectedCountry: event?.action_geo_country_code || null
  }),
  selectedCountry: null,
  setSelectedCountry: (countryCode) => set({ 
    selectedCountry: countryCode,
    selectedEvent: null,
    selectedEventId: null,
    currentAnalysis: null
  }),
  
  currentAnalysis: null,
  setCurrentAnalysis: (currentAnalysis) => set({ currentAnalysis }),
  isAnalyzing: false,
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  
  dateRange: [getSevenDaysAgo(), getToday()],
  setDateRange: (dateRange) => set({ dateRange }),
  eventRootCode: null,
  setEventRootCode: (eventRootCode) => set({ eventRootCode }),

  autoRefreshEnabled: true,
  setAutoRefreshEnabled: (autoRefreshEnabled) => set({ autoRefreshEnabled }),
  fetchIntervalSeconds: 30,
  setFetchIntervalSeconds: (fetchIntervalSeconds) =>
    set({ fetchIntervalSeconds: Math.max(5, Math.min(fetchIntervalSeconds, 300)) }),
  healthPollIntervalSeconds: 60,
  setHealthPollIntervalSeconds: (healthPollIntervalSeconds) =>
    set({ healthPollIntervalSeconds: Math.max(10, Math.min(healthPollIntervalSeconds, 300)) }),

  tickerCollapsed: false,
  setTickerCollapsed: (tickerCollapsed) => set({ tickerCollapsed }),
  threatCardCollapsed: false,
  setThreatCardCollapsed: (threatCardCollapsed) => set({ threatCardCollapsed }),
}));
