export interface Event {
  global_event_id: number;
  sql_date: string;
  lat: number;
  lon: number;
  action_geo_country_code?: string;
  action_geo_lat?: number;
  action_geo_long?: number;
  actor1_country_code?: string;
  actor2_country_code?: string;
  quad_class?: number;
  actor1_type_code?: string;
  actor2_type_code?: string;
  event_code?: string;
  actor1_geo_country_code?: string;
  actor2_geo_country_code?: string;
  event_root_code?: string;
  goldstein_scale?: number;
  num_mentions: number;
  num_sources?: number;
  avg_tone?: number;
  source_url?: string;
  actor1_type?: string;
  actor2_type?: string;
  themes?: string[];
  persons?: string[];
  organizations?: string[];
  mentions_count?: number;
  avg_confidence?: number;
}

export interface MapAggregation {
  lat: number;
  lon: number;
  intensity: number;
  country_code?: string;
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

export interface BigQueryHealthDetail {
  connected: boolean;
  project: string;
  dataset: string;
  latency_ms?: number | null;
  error?: string | null;
}

export interface HotTierHealthDetail {
  path: string;
  available: boolean;
  parquet_files: number;
  cutoff_days: number;
  total_rows?: number;
  last_updated_at?: string | null;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy' | string;
  environment: string;
  version: string;
  bigquery: BigQueryHealthDetail;
  hot_tier: HotTierHealthDetail;
  uptime_seconds: number;
}

export interface RuntimeSettingsResponse {
  hot_tier_cutoff_days: number;
  cold_tier_max_window_days: number;
  cold_tier_monthly_query_limit: number;
  bq_max_scan_bytes: number;
  default_lookback_days: number;
  default_query_limit: number;
  realtime_fetch_interval_minutes: number;
  daily_batch_cron_utc: string;
  nightly_ai_cron_utc: string;
}
