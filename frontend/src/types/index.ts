export interface Event {
  global_event_id: number;
  sql_date: string;
  lat: number;
  lon: number;
  actor1_country_code?: string;
  actor2_country_code?: string;
  event_root_code?: string;
  goldstein_scale?: number;
  num_mentions: number;
  num_sources?: number;
  avg_tone?: number;
  source_url?: string;
  actor1_type?: string;
  actor2_type?: string;
}

export interface MapAggregation {
  lat: number;
  lon: number;
  intensity: number;
}

export interface MapDataResponse {
  zoom: number;
  is_aggregated: boolean;
  count: number;
  data: MapAggregation[] | Event[];
}

export interface EventAnalysis {
  summary: string;
  sentiment: 'Positive' | 'Neutral' | 'Negative';
  entities: string[];
  themes: string[];
  confidence: number;
}

export interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}
