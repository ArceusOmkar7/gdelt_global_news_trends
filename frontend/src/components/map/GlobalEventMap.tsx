import React, { useState, useMemo, useRef } from 'react';
import Map, { Layer, Source } from 'react-map-gl/mapbox';
import type { MapRef, MapMouseEvent } from 'react-map-gl/mapbox';
import type { Feature, FeatureCollection, Point } from 'geojson';
import { useQuery } from '@tanstack/react-query';
import { useStore } from '../../store/useStore';
import { apiService } from '../../services/api';
import type { MapAggregation, Event } from '../../types';

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;
const HAS_MAPBOX_TOKEN =
  typeof MAPBOX_ACCESS_TOKEN === 'string' && MAPBOX_ACCESS_TOKEN.trim().length > 0;
const DETAIL_ZOOM_THRESHOLD = 9;

export const GlobalEventMap: React.FC = () => {
  const { 
    viewState, 
    setViewState, 
    dateRange, 
    eventRootCode,
    setSelectedEvent,
    setSelectedCountry,
    selectedEventId,
  } = useStore();

  const mapRef = useRef<MapRef>(null);
  const [mapBBox, setMapBBox] = useState({ n: 90, s: -90, e: 180, w: -180 });

  // Helper to validate BBOX
  const isValidBBox = (bbox: any) => {
    return !Object.values(bbox).some(val => typeof val !== 'number' || isNaN(val));
  };

  const updateBBox = () => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    const bounds = map.getBounds();
    if (!bounds) return;

    const nextBBox = {
      w: bounds.getWest(),
      s: bounds.getSouth(),
      e: bounds.getEast(),
      n: bounds.getNorth()
    };

    if (isValidBBox(nextBBox)) {
      setMapBBox(nextBBox);
    }
  };

  const queryZoom = Number(viewState.zoom.toFixed(2));

  const { data: mapResponse, isLoading, isFetching, isError, error } = useQuery({
    queryKey: ['map-data', mapBBox, queryZoom, dateRange, eventRootCode],
    queryFn: async ({ signal }) => {
      if (!isValidBBox(mapBBox)) return { zoom: queryZoom, is_aggregated: true, count: 0, data: [] };

      const res = await apiService.getMapData(
        mapBBox,
        queryZoom,
        dateRange[0],
        dateRange[1],
        eventRootCode,
        signal
      );
      return res;
    },
    staleTime: 1000 * 15,
  });

  const aggregatedGeoJson = useMemo<FeatureCollection<Point, any> | null>(() => {
    if (!mapResponse?.is_aggregated || mapResponse.count === 0) return null;
    const aggData = mapResponse.data as MapAggregation[];
    return {
      type: 'FeatureCollection',
      features: aggData.map(
        (d): Feature<Point, any> => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [d.lon, d.lat] },
          properties: { 
            intensity: d.intensity,
            country_code: d.country_code 
          },
        })
      ),
    };
  }, [mapResponse]);

  const detailedGeoJson = useMemo<FeatureCollection<Point, any> | null>(() => {
    if (!mapResponse || mapResponse.is_aggregated || mapResponse.count === 0) return null;
    const eventData = mapResponse.data as any[];
    return {
      type: 'FeatureCollection',
      features: eventData.map(
        (d): Feature<Point, any> => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [d.lon ?? d.ActionGeo_Long, d.lat ?? d.ActionGeo_Lat] },
          properties: { 
            ...d,
            // Mapbox requires strings for property IDs in some contexts, 
            // but we need the raw number for our logic.
            global_event_id: Number(d.global_event_id)
          },
        })
      ),
    };
  }, [mapResponse]);

  const onMapClick = (evt: MapMouseEvent) => {
    // 1. Individual events (detailed view)
    const eventFeature = evt.features?.find((f) => f.layer?.id === 'events-layer');
    if (eventFeature && eventFeature.properties) {
      const eventId = Number(eventFeature.properties.global_event_id);
      const originalEvent = (mapResponse?.data as Event[])?.find(e => Number(e.global_event_id) === eventId);
      if (originalEvent) {
        setSelectedEvent(originalEvent);
        return;
      }

      // Fallback to clicked feature properties when a refresh races the click.
      const clickedGeometry = eventFeature.geometry as Point;
      const [lon, lat] = clickedGeometry.coordinates;
      setSelectedEvent({
        global_event_id: eventId,
        sql_date: String(eventFeature.properties.sql_date || ''),
        lat: Number(eventFeature.properties.lat ?? lat),
        lon: Number(eventFeature.properties.lon ?? lon),
        action_geo_country_code: eventFeature.properties.action_geo_country_code || undefined,
        action_geo_lat: eventFeature.properties.action_geo_lat !== undefined ? Number(eventFeature.properties.action_geo_lat) : undefined,
        action_geo_long: eventFeature.properties.action_geo_long !== undefined ? Number(eventFeature.properties.action_geo_long) : undefined,
        actor1_country_code: eventFeature.properties.actor1_country_code || undefined,
        actor2_country_code: eventFeature.properties.actor2_country_code || undefined,
        event_root_code: eventFeature.properties.event_root_code || undefined,
        goldstein_scale: eventFeature.properties.goldstein_scale !== undefined ? Number(eventFeature.properties.goldstein_scale) : undefined,
        num_mentions: Number(eventFeature.properties.num_mentions ?? 0),
        num_sources: eventFeature.properties.num_sources !== undefined ? Number(eventFeature.properties.num_sources) : undefined,
        avg_tone: eventFeature.properties.avg_tone !== undefined ? Number(eventFeature.properties.avg_tone) : undefined,
        source_url: eventFeature.properties.source_url || undefined,
        actor1_type: eventFeature.properties.actor1_type || undefined,
        actor2_type: eventFeature.properties.actor2_type || undefined,
        themes: Array.isArray(eventFeature.properties.themes) ? eventFeature.properties.themes : undefined,
        persons: Array.isArray(eventFeature.properties.persons) ? eventFeature.properties.persons : undefined,
        organizations: Array.isArray(eventFeature.properties.organizations) ? eventFeature.properties.organizations : undefined,
        mentions_count: eventFeature.properties.mentions_count !== undefined ? Number(eventFeature.properties.mentions_count) : undefined,
        avg_confidence: eventFeature.properties.avg_confidence !== undefined ? Number(eventFeature.properties.avg_confidence) : undefined,
      });
      return;
    }

    // 2. Aggregate bins (drill-down)
    const aggregateFeature = evt.features?.find((f) => f.layer?.id === 'agg-circle-layer');
    if (aggregateFeature && aggregateFeature.properties) {
      const props = aggregateFeature.properties;
      const aggregatePoint = aggregateFeature.geometry as Point;
      const [longitude, latitude] = aggregatePoint.coordinates;
      
      if (props.country_code) {
        setSelectedCountry(props.country_code);
      }
      setSelectedEvent(null);

      const nextZoom = Math.max(viewState.zoom + 2, DETAIL_ZOOM_THRESHOLD + 0.2);
      setViewState({
        ...viewState,
        longitude,
        latitude,
        zoom: nextZoom,
      });
      return;
    }
  };

  if (!HAS_MAPBOX_TOKEN) {
    return (
      <div className="relative w-full h-full">
        <div className="absolute inset-0 bg-surface-900" />
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-50 bg-cyber-red/20 border border-cyber-red p-4 rounded backdrop-blur-md max-w-xl text-center">
          <p className="text-cyber-red font-bold font-mono text-sm">CRITICAL SYSTEM ALERT: MAPBOX TOKEN MISSING</p>
          <p className="text-white/70 text-[10px] mt-2 font-mono uppercase">
            Set VITE_MAPBOX_ACCESS_TOKEN in frontend/.env.local or in workspace root .env and restart vite.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Data Scanning Progress Bar */}
      {(isLoading || isFetching) && (
        <div className="absolute top-0 left-0 w-full h-[2px] z-50 overflow-hidden bg-cyber-blue/10">
          <div className="h-full bg-cyber-blue animate-[progress_2s_infinite_linear]" 
               style={{ width: '30%', boxShadow: '0 0 10px #00f3ff' }} />
        </div>
      )}

      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        onLoad={updateBBox}
          onMoveEnd={updateBBox}
        onClick={onMapClick}
        interactiveLayerIds={['agg-circle-layer', 'events-layer']}
        mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        style={{ width: '100%', height: '100%' }}
      >
        {aggregatedGeoJson && (
          <Source id="agg-source" type="geojson" data={aggregatedGeoJson}>
            <Layer
              id="agg-heatmap-layer"
              type="heatmap"
              maxzoom={22}
              paint={{
                'heatmap-weight': [
                  'interpolate',
                  ['linear'],
                  ['ln', ['+', ['get', 'intensity'], 1]],
                  0,
                  0,
                  6,
                  1,
                ],
                'heatmap-intensity': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  1,
                  0.9,
                  5,
                  1.4,
                  8.9,
                  1.8,
                ],
                'heatmap-radius': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  1,
                  18,
                  2.5,
                  26,
                  3.6,
                  20,
                ],
                'heatmap-color': [
                  'interpolate',
                  ['linear'],
                  ['heatmap-density'],
                  0,
                  'rgba(0, 0, 0, 0)',
                  0.2,
                  'rgba(0, 220, 255, 0.25)',
                  0.4,
                  'rgba(0, 255, 190, 0.45)',
                  0.6,
                  'rgba(255, 220, 0, 0.62)',
                  0.8,
                  'rgba(255, 120, 0, 0.75)',
                  1,
                  'rgba(255, 45, 45, 0.88)',
                ],
                'heatmap-opacity': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  1,
                  0.6,
                  7,
                  0.5,
                  12,
                  0.35,
                  18,
                  0.2,
                ],
              }}
            />
            <Layer
              id="agg-circle-layer"
              type="circle"
              minzoom={0}
              maxzoom={22}
              paint={{
                'circle-color': [
                  'interpolate',
                  ['linear'],
                  ['ln', ['+', ['get', 'intensity'], 1]],
                  0,
                  'rgba(0, 243, 255, 0.6)',
                  2,
                  'rgba(0, 255, 65, 0.7)',
                  4,
                  'rgba(255, 220, 0, 0.8)',
                  6,
                  'rgba(255, 120, 0, 0.85)',
                  8,
                  'rgba(255, 0, 60, 0.9)',
                ],
                'circle-radius': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  0,
                  2,
                  3,
                  4,
                  6,
                  6,
                  9,
                  8,
                  12,
                  10,
                ],
                'circle-opacity': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  0,
                  0.4,
                  8,
                  0.6,
                  12,
                  0.65,
                  18,
                  0.6,
                ],
                'circle-stroke-width': 1,
                'circle-stroke-color': 'rgba(255,255,255,0.1)',
              }}
            />
          </Source>
        )}

        {detailedGeoJson && (
          <Source id="events-source" type="geojson" data={detailedGeoJson} maxzoom={24}>
            <Layer
              id="events-layer"
              type="circle"
              paint={{
                'circle-color': [
                  'case',
                  ['<', ['coalesce', ['get', 'goldstein_scale'], 0], -2],
                  '#ff003c',
                  ['>', ['coalesce', ['get', 'goldstein_scale'], 0], 2],
                  '#00ff41',
                  '#00f3ff',
                ],
                'circle-radius': [
                  'interpolate',
                  ['linear'],
                  ['ln', ['+', ['coalesce', ['get', 'num_mentions'], 0], 1]],
                  0,
                  8,
                  8,
                  24,
                ],
                'circle-stroke-width': [
                  'case',
                  ['==', ['to-number', ['get', 'global_event_id']], selectedEventId ?? -1],
                  3,
                  1.5,
                ],
                'circle-stroke-color': '#ffffff',
                'circle-opacity': 1.0,
              }}
            />
          </Source>
        )}
      </Map>

      {(isLoading || isFetching) && (
        <div className="absolute top-4 right-4 z-10 px-3 py-1 bg-surface-800/80 border border-cyber-blue/30 rounded flex items-center gap-2">
          <div className="w-2 h-2 bg-cyber-blue rounded-full animate-pulse" />
          <span className="data-ink text-cyber-blue">Uplink Active</span>
        </div>
      )}

      {isError && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-20 px-4 py-2 bg-cyber-red/15 border border-cyber-red/40 rounded">
          <span className="data-ink text-cyber-red">
            MAP QUERY FAILED: {error instanceof Error ? error.message : 'Unknown error'}
          </span>
        </div>
      )}

      {mapResponse?.count === 0 && !(isLoading || isFetching) && (
        <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-10 px-4 py-2 bg-surface-900/80 border border-white/10 rounded">
           <span className="data-ink text-white/50">NO SIGNAL DETECTED IN THIS SECTOR</span>
        </div>
      )}
      
      <div className="absolute bottom-4 left-4 z-10 bg-surface-900/50 backdrop-blur-sm p-2 panel-border rounded">
         <span className="data-ink">Zoom: {viewState.zoom.toFixed(1)} | Points: {mapResponse?.count || 0}</span>
      </div>
    </div>
  );
};
