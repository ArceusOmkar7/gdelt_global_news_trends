"""Unit tests for LiveStreamService."""

import pytest
from unittest.mock import patch, MagicMock
from backend.infrastructure.services.live_stream_service import LiveStreamService

class TestLiveStreamService:
    def setup_method(self):
        self.service = LiveStreamService()

    def test_get_group_fallback_to_global(self):
        group = self.service.get_group("UNKNOWN_CODE")
        assert group is not None
        assert group["group_key"] == "GLOBAL"
        
        group2 = self.service.get_group(None)
        assert group2["group_key"] == "GLOBAL"

    def test_get_group_valid(self):
        group = self.service.get_group("US")
        assert group is not None
        assert group["group_key"] == "US"
        assert len(group["channels"]) > 0

    @patch("backend.infrastructure.services.live_stream_service.yt_dlp.YoutubeDL")
    def test_resolve_channel_success(self, mock_ytdl):
        mock_instance = MagicMock()
        mock_ytdl.return_value.__enter__.return_value = mock_instance
        
        mock_instance.extract_info.return_value = {
            "id": "video123",
            "title": "Live News",
            "allow_embed": True
        }
        
        res = self.service.resolve_channel("fake_id", "Fake Channel", force_refresh=True)
        assert res["status"] == "ok"
        assert res["video_id"] == "video123"

    @patch("backend.infrastructure.services.live_stream_service.yt_dlp.YoutubeDL")
    def test_resolve_channel_offline(self, mock_ytdl):
        mock_instance = MagicMock()
        mock_ytdl.return_value.__enter__.return_value = mock_instance
        
        mock_instance.extract_info.return_value = {}
        
        res = self.service.resolve_channel("fake_id", "Fake Channel", force_refresh=True)
        assert res["status"] == "error"
        assert res["video_id"] is None
        
    @patch("backend.infrastructure.services.live_stream_service.yt_dlp.YoutubeDL")
    def test_resolve_channel_error(self, mock_ytdl):
        mock_instance = MagicMock()
        mock_ytdl.return_value.__enter__.return_value = mock_instance
        
        mock_instance.extract_info.side_effect = Exception("YT DLP Error")
        
        res = self.service.resolve_channel("fake_id", "Fake Channel", force_refresh=True)
        assert res["status"] == "error"
        assert res["video_id"] is None
        
    def test_resolve_channel_caching(self):
        # Insert a fake cache entry
        self.service._cache["fake_id"] = {"status": "ok", "video_id": "fake_video", "updated_at": 9999999999}
        
        res = self.service.resolve_channel("fake_id", "Fake Channel", force_refresh=False)
        assert res["status"] == "ok"
        assert res["video_id"] == "fake_video"
        
        # Now force refresh
        with patch.object(self.service, "_fetch_live_info") as mock_fetch:
            mock_fetch.return_value = {"status": "error", "video_id": None}
            res_refresh = self.service.refresh_channel("fake_id")
            assert res_refresh["status"] == "error"
            assert mock_fetch.called
