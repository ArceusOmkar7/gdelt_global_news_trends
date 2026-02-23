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
  
  // Analysis State
  currentAnalysis: EventAnalysis | null;
  setCurrentAnalysis: (analysis: EventAnalysis | null) => void;
  
  // Filter State
  dateRange: [string, string];
  setDateRange: (range: [string, string]) => void;
  eventRootCode: string | null;
  setEventRootCode: (code: string | null) => void;
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
    currentAnalysis: null // Clear analysis when event changes
  }),
  
  currentAnalysis: null,
  setCurrentAnalysis: (currentAnalysis) => set({ currentAnalysis }),
  
  dateRange: [getSevenDaysAgo(), getToday()],
  setDateRange: (dateRange) => set({ dateRange }),
  eventRootCode: null,
  setEventRootCode: (eventRootCode) => set({ eventRootCode }),
}));
