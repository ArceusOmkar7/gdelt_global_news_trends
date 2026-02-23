"""Clustering service — NLP-based event clustering.

This is a prototype implementation using TF-IDF on synthetic text 
features followed by KMeans. Future versions will extract meaningful 
text from the `source_url`.
"""

from __future__ import annotations

import logging
from collections import Counter

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.domain.models.event import Event, EventCluster
from backend.domain.ports.ports import IClusteringService

logger = logging.getLogger(__name__)


class ClusteringService(IClusteringService):
    """Implementation of IClusteringService using TF-IDF and KMeans.
    
    Creates a synthetic "document" for each event by joining its categorical
    attributes (actor1, actor2, root code) and a bucketed Goldstein scale.
    """

    def cluster_events(
        self,
        events: list[Event],
        n_clusters: int,
    ) -> list[EventCluster]:
        """Group events into thematic clusters."""
        if not events:
            return []

        # If we have fewer events than requested clusters, reduce n_clusters
        n_clusters = min(n_clusters, len(events))
        if n_clusters <= 1:
            return [self._create_single_cluster(events)]

        # 1. Generate synthetic text for each event
        docs = [self._event_to_text(e) for e in events]

        # 2. Vectorize using TF-IDF
        vectorizer = TfidfVectorizer(stop_words="english", max_features=1000)
        try:
            X = vectorizer.fit_transform(docs)
        except ValueError as e:
            # E.g., if all documents only contain stop words or are empty
            logger.warning("TF-IDF vectorization failed: %s", e)
            return [self._create_single_cluster(events)]

        # 3. Cluster using KMeans
        # Setting n_init="auto" to suppress sklearn warnings
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        try:
            labels = kmeans.fit_predict(X)
        except ValueError as e:
            logger.warning("KMeans clustering failed: %s", e)
            return [self._create_single_cluster(events)]

        # 4. Group events by cluster label
        clusters_map: dict[int, list[Event]] = {i: [] for i in range(n_clusters)}
        for label, event in zip(labels, events):
            clusters_map[label].append(event)

        # 5. Build EventCluster domain models
        result = []
        for cluster_id, cluster_events in clusters_map.items():
            if not cluster_events:
                continue
            
            cluster_model = self._build_cluster_model(cluster_id, cluster_events)
            result.append(cluster_model)

        # Sort by event_count descending
        result.sort(key=lambda c: c.event_count, reverse=True)
        return result

    def _event_to_text(self, event: Event) -> str:
        """Create a synthetic text representation for TF-IDF."""
        parts = []
        if event.actor1_country_code:
            parts.append(f"actor_{event.actor1_country_code}")
        if event.actor2_country_code:
            parts.append(f"actor_{event.actor2_country_code}")
        if event.event_root_code:
            parts.append(f"event_{event.event_root_code}")
        
        # Bucket goldstein scale to categorical
        if event.goldstein_scale is not None:
            if event.goldstein_scale < -5:
                parts.append("tone_highly_negative")
            elif event.goldstein_scale < 0:
                parts.append("tone_negative")
            elif event.goldstein_scale > 5:
                parts.append("tone_highly_positive")
            elif event.goldstein_scale > 0:
                parts.append("tone_positive")
            else:
                parts.append("tone_neutral")
                
        # If we have literally nothing to cluster on, add a fallback token
        if not parts:
            parts.append("unknown_features")

        return " ".join(parts).lower()

    def _build_cluster_model(
        self,
        cluster_id: int,
        events: list[Event],
    ) -> EventCluster:
        """Create an EventCluster domain model from a list of events."""
        event_ids = [e.global_event_id for e in events]
        
        # Calculate stats
        goldstein_values = [e.goldstein_scale for e in events if e.goldstein_scale is not None]
        avg_goldstein = (
            sum(goldstein_values) / len(goldstein_values)
            if goldstein_values
            else None
        )

        country_codes = []
        event_codes = []
        for e in events:
            if e.actor1_country_code:
                country_codes.append(e.actor1_country_code)
            if e.actor2_country_code:
                country_codes.append(e.actor2_country_code)
            if e.event_root_code:
                event_codes.append(e.event_root_code)

        top_countries = [c for c, _ in Counter(country_codes).most_common(3)]
        top_events = [c for c, _ in Counter(event_codes).most_common(3)]

        # Generate a label based on the most common features
        label_parts = []
        if top_countries:
            label_parts.append("/".join(top_countries[:2]))
        if top_events:
            label_parts.append(f"Event {top_events[0]}")
        
        label = " - ".join(label_parts) if label_parts else "Mixed Cluster"

        return EventCluster(
            cluster_id=cluster_id,
            label=label,
            event_count=len(events),
            avg_goldstein_scale=avg_goldstein,
            top_country_codes=top_countries,
            top_event_codes=top_events,
            event_ids=event_ids,
        )

    def _create_single_cluster(self, events: list[Event]) -> EventCluster:
        """Fallback when clustering cannot be performed."""
        return self._build_cluster_model(0, events)
