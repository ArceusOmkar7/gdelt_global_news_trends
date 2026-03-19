import React, { useState, useMemo, useEffect, useRef } from 'react';
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

export const GlobalEventMap: React.FC = () => {
  const { 
    viewState, 
    setViewState, 
    dateRange, 
    eventRootCode,
    setSelectedEvent,
    selectedEventId,
    autoRefreshEnabled,
    fetchIntervalSeconds,
  } = useStore();

  const mapRef = useRef<MapRef>(null);
  const [mapBBox, setMapBBox] = useState({ n: 90, s: -90, e: 180, w: -180 });

  // Helper to validate BBOX
  const isValidBBox = (bbox: any) => {
    return !Object.values(bbox).some(val => typeof val !== 'number' || isNaN(val));
  };

  useEffect(() => {
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
        console.log('Map BBOX Updated:', nextBBox, 'Zoom:', viewState.zoom);
      } else {
        console.warn('Map BBOX calculation resulted in NaN, skipping update.');
      }
    };

    const timer = setTimeout(updateBBox, 300);
    return () => clearTimeout(timer);
  }, [viewState]);

  const { data: mapResponse, isLoading } = useQuery({
    queryKey: ['map-data', mapBBox, Math.round(viewState.zoom), dateRange, eventRootCode],
    queryFn: async () => {
      // Final guard against NaN in query
      if (!isValidBBox(mapBBox)) {
        console.error('Blocking API call due to invalid BBOX:', mapBBox);
        return { zoom: viewState.zoom, is_aggregated: true, count: 0, data: [] };
      }

      const res = await apiService.getMapData(
        mapBBox,
        viewState.zoom,
        dateRange[0],
        dateRange[1],
        eventRootCode
      );
      console.log('API Response:', res.count, 'items', 'Aggregated:', res.is_aggregated);
      return res;
    },
    placeholderData: (previousData) => previousData,
    staleTime: 1000 * 30,
    refetchInterval: autoRefreshEnabled ? fetchIntervalSeconds * 1000 : false,
  });

  const aggregatedGeoJson = useMemo<FeatureCollection<Point, { intensity: number }> | null>(() => {
    if (!mapResponse?.is_aggregated || mapResponse.count === 0) return null;
    const aggData = mapResponse.data as MapAggregation[];
    return {
      type: 'FeatureCollection',
      features: aggData.map(
        (d): Feature<Point, { intensity: number }> => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [d.lon, d.lat] },
          properties: { intensity: d.intensity },
        })
      ),
    };
  }, [mapResponse]);

  const detailedGeoJson = useMemo<FeatureCollection<Point, Event> | null>(() => {
    if (!mapResponse || mapResponse.is_aggregated || mapResponse.count === 0) return null;
    const eventData = mapResponse.data as Event[];
    return {
      type: 'FeatureCollection',
      features: eventData.map(
        (d): Feature<Point, Event> => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [d.lon, d.lat] },
          properties: d,
        })
      ),
    };
  }, [mapResponse]);

  const onMapClick = (evt: MapMouseEvent) => {
    if (mapResponse?.is_aggregated) {
      const featureFromEvent = evt.features?.find((f) => f.layer?.id === 'agg-circle-layer');
      const featureFromQuery = mapRef.current
        ?.queryRenderedFeatures(evt.point, { layers: ['agg-circle-layer'] })
        ?.[0];
      const aggregateFeature = featureFromEvent ?? featureFromQuery;
      if (!aggregateFeature) return;

      const aggregatePoint = aggregateFeature.geometry as Point;
      const [longitude, latitude] = aggregatePoint.coordinates;
      const nextZoom = 9.2;

      // Clear selected event while drilling from aggregate bins to event-level detail.
      setSelectedEvent(null);
      setViewState({
        ...viewState,
        longitude,
        latitude,
        zoom: nextZoom,
      });
      return;
    }

    const feature = evt.features?.[0];
    const props = feature?.properties as Event | undefined;
    if (!props || !props.global_event_id) return;
    setSelectedEvent({
      ...props,
      global_event_id: Number(props.global_event_id),
      lat: Number(props.lat),
      lon: Number(props.lon),
      num_mentions: Number(props.num_mentions ?? 0),
      num_sources: props.num_sources == null ? undefined : Number(props.num_sources),
      goldstein_scale: props.goldstein_scale == null ? undefined : Number(props.goldstein_scale),
      avg_tone: props.avg_tone == null ? undefined : Number(props.avg_tone),
    });
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
      {isLoading && (
        <div className="absolute top-0 left-0 w-full h-[2px] z-50 overflow-hidden bg-cyber-blue/10">
          <div className="h-full bg-cyber-blue animate-[progress_2s_infinite_linear]" 
               style={{ width: '30%', boxShadow: '0 0 10px #00f3ff' }} />
        </div>
      )}

      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        onClick={onMapClick}
        interactiveLayerIds={mapResponse?.is_aggregated ? ['agg-circle-layer'] : ['events-layer']}
        mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        style={{ width: '100%', height: '100%' }}
      >
        {aggregatedGeoJson && (
          <Source id="agg-source" type="geojson" data={aggregatedGeoJson}>
            <Layer
              id="agg-heatmap-layer"
              type="heatmap"
              maxzoom={3.6}
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
                  0.58,
                  2.5,
                  0.48,
                  3.2,
                  0.2,
                  3.6,
                  0,
                ],
              }}
            />
            <Layer
              id="agg-circle-layer"
              type="circle"
              minzoom={0}
              paint={{
                'circle-color': [
                  'interpolate',
                  ['linear'],
                  ['ln', ['+', ['get', 'intensity'], 1]],
                  0,
                  'rgba(0, 220, 255, 0.45)',
                  2,
                  'rgba(0, 255, 190, 0.5)',
                  4,
                  'rgba(255, 220, 0, 0.56)',
                  6,
                  'rgba(255, 120, 0, 0.62)',
                  8,
                  'rgba(255, 45, 45, 0.72)',
                ],
                'circle-radius': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  0,
                  8,
                  2.4,
                  6,
                  4,
                  4,
                  8.9,
                  3,
                ],
                'circle-opacity': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  0,
                  0.1,
                  2.4,
                  0.14,
                  3,
                  0.2,
                  5,
                  0.34,
                  8.9,
                  0.3,
                ],
                'circle-blur': 0.1,
              }}
            />
          </Source>
        )}

        {detailedGeoJson && (
          <Source id="events-source" type="geojson" data={detailedGeoJson}>
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
                  4,
                  8,
                  14,
                ],
                'circle-stroke-width': [
                  'case',
                  ['==', ['to-number', ['get', 'global_event_id']], selectedEventId ?? -1],
                  2,
                  0,
                ],
                'circle-stroke-color': '#ffffff',
                'circle-opacity': [
                  'interpolate',
                  ['linear'],
                  ['ln', ['+', ['coalesce', ['get', 'num_mentions'], 0], 1]],
                  0,
                  0.22,
                  8,
                  0.58,
                ],
              }}
            />
          </Source>
        )}
      </Map>

      {isLoading && (
        <div className="absolute top-4 right-4 z-10 px-3 py-1 bg-surface-800/80 border border-cyber-blue/30 rounded flex items-center gap-2">
          <div className="w-2 h-2 bg-cyber-blue rounded-full animate-pulse" />
          <span className="data-ink text-cyber-blue">Uplink Active</span>
        </div>
      )}

      {mapResponse?.count === 0 && !isLoading && (
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
