"""Tests for new remote client wrappers (freight exchange, copilot, feature flags)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from client.remote_freight_exchange import RemoteFreightExchangeService
from client.remote_copilot import RemoteCopilotService
from client.remote_feature_flags import RemoteFeatureFlagService


class TestRemoteFreightExchangeService:
    """Tests for client/remote_freight_exchange.py"""

    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteFreightExchangeService(api)

    def test_list_providers_calls_get(self, service, api):
        api._get.return_value = {"providers": [{"id": "timocom"}]}
        result = service.list_providers()
        api._get.assert_called_once_with("/api/v1/freight/providers")
        assert result == [{"id": "timocom"}]

    def test_list_providers_returns_empty_on_none(self, service, api):
        api._get.return_value = None
        result = service.list_providers()
        assert result == []

    def test_list_providers_returns_empty_on_missing_key(self, service, api):
        api._get.return_value = {}
        result = service.list_providers()
        assert result == []

    def test_connect_provider_calls_post(self, service, api):
        api._post.return_value = {"status": "ok"}
        result = service.connect_provider("timocom", "client_1", "secret_1", scope=["loads"])
        api._post.assert_called_once_with(
            "/api/v1/freight/providers/connect",
            json_data={
                "provider_id": "timocom",
                "client_id": "client_1",
                "client_secret": "secret_1",
                "scope": ["loads"],
            },
        )
        assert result == {"status": "ok"}

    def test_connect_provider_default_scope(self, service, api):
        api._post.return_value = {}
        service.connect_provider("p", "c", "s")
        _, kwargs = api._post.call_args
        assert kwargs["json_data"]["scope"] == []

    def test_connect_provider_default_scope_none(self, service, api):
        api._post.return_value = {}
        service.connect_provider("p", "c", "s", scope=None)
        _, kwargs = api._post.call_args
        assert kwargs["json_data"]["scope"] == []

    def test_disconnect_provider_calls_post(self, service, api):
        api._post.return_value = {}
        service.disconnect_provider("timocom")
        api._post.assert_called_once_with("/api/v1/freight/providers/timocom/disconnect")

    def test_test_provider_calls_post(self, service, api):
        api._post.return_value = {}
        service.test_provider("timocom")
        api._post.assert_called_once_with("/api/v1/freight/providers/timocom/test")

    def test_search_loads_calls_post(self, service, api):
        api._post.return_value = {"results": [], "providers_queried": 0}
        kwargs = {
            "origin_location": "Berlin",
            "destination_location": "Munich",
            "pickup_date_from": "2025-01-01",
            "pickup_date_to": "2025-01-07",
        }
        service.search_loads(**kwargs)
        api._post.assert_called_once_with(
            "/api/v1/freight/search",
            json_data=kwargs,
        )

    def test_search_loads_strips_none_values(self, service, api):
        api._post.return_value = {}
        service.search_loads(
            origin_location="Berlin",
            destination_location="Munich",
            pickup_date_from="2025-01-01",
            pickup_date_to="2025-01-07",
            adr_required=None,
        )
        call_body = api._post.call_args[1]["json_data"]
        assert "adr_required" not in call_body

    def test_search_loads_passes_falsy_values(self, service, api):
        """Falsy but non-None values (0, False, empty string) should be kept."""
        api._post.return_value = {}
        service.search_loads(
            origin_location="Berlin",
            destination_location="Munich",
            pickup_date_from="2025-01-01",
            pickup_date_to="2025-01-07",
            weight_kg_min=0,
            adr_required=False,
        )
        call_body = api._post.call_args[1]["json_data"]
        assert call_body["weight_kg_min"] == 0
        assert call_body["adr_required"] is False

    def test_get_recent_searches_calls_get(self, service, api):
        api._get.return_value = {"searches": [{"id": "s1"}]}
        result = service.get_recent_searches(limit=10)
        api._get.assert_called_once_with("/api/v1/freight/searches", params={"limit": 10})
        assert result == [{"id": "s1"}]

    def test_get_recent_searches_default_limit(self, service, api):
        api._get.return_value = {"searches": []}
        service.get_recent_searches()
        api._get.assert_called_once_with("/api/v1/freight/searches", params={"limit": 20})

    def test_get_recent_searches_empty_on_none(self, service, api):
        api._get.return_value = None
        assert service.get_recent_searches() == []

    def test_get_recent_searches_empty_on_missing_key(self, service, api):
        api._get.return_value = {}
        assert service.get_recent_searches() == []

    def test_save_search_calls_post(self, service, api):
        api._post.return_value = {"id": "s1"}
        result = service.save_search("My Search", {"origin": "Berlin"}, provider_ids=["timo"])
        api._post.assert_called_once_with(
            "/api/v1/freight/searches",
            json_data={"label": "My Search", "filters": {"origin": "Berlin"}, "provider_ids": ["timo"]},
        )
        assert result == {"id": "s1"}

    def test_save_search_none_provider_ids(self, service, api):
        api._post.return_value = {}
        service.save_search("Label", {})
        _, kwargs = api._post.call_args
        assert kwargs["json_data"]["provider_ids"] is None

    def test_refresh_search_calls_post(self, service, api):
        api._post.return_value = {}
        service.refresh_search("s1")
        api._post.assert_called_once_with("/api/v1/freight/searches/s1/refresh")

    def test_get_load_calls_get(self, service, api):
        api._get.return_value = {"id": "l1"}
        result = service.get_load("timocom", "l1")
        api._get.assert_called_once_with("/api/v1/freight/loads/timocom/l1")
        assert result == {"id": "l1"}

    def test_import_load_calls_post(self, service, api):
        api._post.return_value = {"trip_id": 42}
        result = service.import_load("timocom", "l1")
        api._post.assert_called_once_with("/api/v1/freight/loads/timocom/l1/import")
        assert result == {"trip_id": 42}

    def test_evaluate_load_calls_get(self, service, api):
        api._get.return_value = {"score": 0.85}
        result = service.evaluate_load("timocom", "l1", candidate_vehicle_id=5)
        api._get.assert_called_once_with(
            "/api/v1/freight/loads/timocom/l1/evaluate",
            params={"candidate_vehicle_id": 5},
        )
        assert result == {"score": 0.85}

    def test_evaluate_load_no_vehicle(self, service, api):
        api._get.return_value = {}
        service.evaluate_load("timocom", "l1")
        api._get.assert_called_once_with(
            "/api/v1/freight/loads/timocom/l1/evaluate",
            params={},
        )

    def test_match_trucks_calls_get(self, service, api):
        api._get.return_value = {"matches": [{"truck": "V1"}]}
        result = service.match_trucks("timocom", "l1", top_n=3)
        api._get.assert_called_once_with(
            "/api/v1/freight/loads/timocom/l1/match",
            params={"top_n": 3},
        )
        assert result == [{"truck": "V1"}]

    def test_match_trucks_default_top_n(self, service, api):
        api._get.return_value = {"matches": []}
        service.match_trucks("timocom", "l1")
        _, kwargs = api._get.call_args
        assert kwargs["params"]["top_n"] == 5

    def test_match_trucks_empty_on_none(self, service, api):
        api._get.return_value = None
        assert service.match_trucks("timocom", "l1") == []

    def test_match_trucks_empty_on_missing_key(self, service, api):
        api._get.return_value = {}
        assert service.match_trucks("timocom", "l1") == []


class TestRemoteCopilotService:
    """Tests for client/remote_copilot.py"""

    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteCopilotService(api, auth_token="jwt123")

    def test_chat_calls_post_with_utterance_and_language(self, service, api):
        api._post.return_value = {"response_text": "Hello"}
        result = service.chat("Hello", language="en")
        api._post.assert_called_once_with(
            "/api/v1/copilot/chat",
            json_data={"utterance": "Hello", "language": "en"},
        )
        assert result == {"response_text": "Hello"}

    def test_chat_with_conversation_id(self, service, api):
        api._post.return_value = {}
        service.chat("Hi", conversation_id="conv_1")
        body = api._post.call_args[1]["json_data"]
        assert body["conversation_id"] == "conv_1"

    def test_chat_default_language(self, service, api):
        api._post.return_value = {}
        service.chat("Hi")
        body = api._post.call_args[1]["json_data"]
        assert body["language"] == "en"

    def test_chat_without_conversation_id(self, service, api):
        """When conversation_id is omitted, it should not appear in the body."""
        api._post.return_value = {}
        service.chat("Hello")
        body = api._post.call_args[1]["json_data"]
        assert "conversation_id" not in body

    def test_voice_input_calls_post(self, service, api):
        api._post.return_value = {}
        service.voice_input("Hello", conversation_id="conv_1", language="de")
        api._post.assert_called_once_with(
            "/api/v1/copilot/voice",
            json_data={"utterance": "Hello", "language": "de", "conversation_id": "conv_1"},
        )

    def test_voice_input_defaults(self, service, api):
        api._post.return_value = {}
        service.voice_input("Hi")
        body = api._post.call_args[1]["json_data"]
        assert body["language"] == "en"
        assert "conversation_id" not in body

    def test_get_plan_calls_get(self, service, api):
        api._get.return_value = {"id": "plan_1"}
        result = service.get_plan("plan_1")
        api._get.assert_called_once_with("/api/v1/copilot/plans/plan_1")
        assert result == {"id": "plan_1"}

    def test_confirm_plan_calls_post(self, service, api):
        api._post.return_value = {"status": "executing"}
        service.confirm_plan("plan_1")
        api._post.assert_called_once_with("/api/v1/copilot/plans/plan_1/confirm")

    def test_cancel_plan_calls_post(self, service, api):
        api._post.return_value = {}
        service.cancel_plan("plan_1")
        api._post.assert_called_once_with("/api/v1/copilot/plans/plan_1/cancel")

    def test_undo_plan_calls_post(self, service, api):
        api._post.return_value = {}
        service.undo_plan("plan_1")
        api._post.assert_called_once_with("/api/v1/copilot/plans/plan_1/undo")

    def test_list_conversations_calls_get(self, service, api):
        api._get.return_value = {"items": [{"id": "c1"}], "next_cursor": "abc"}
        result = service.list_conversations(limit=10, cursor="abc")
        api._get.assert_called_once_with(
            "/api/v1/copilot/conversations",
            params={"limit": 10, "cursor": "abc"},
        )
        assert result == [{"id": "c1"}]

    def test_list_conversations_unwraps_items(self, service, api):
        api._get.return_value = {"items": [{"id": "c1"}], "next_cursor": None}
        result = service.list_conversations()
        assert result == [{"id": "c1"}]

    def test_list_conversations_empty_on_none(self, service, api):
        api._get.return_value = None
        assert service.list_conversations() == []

    def test_list_conversations_empty_on_missing_items(self, service, api):
        api._get.return_value = {}
        assert service.list_conversations() == []

    def test_list_conversations_default_limit(self, service, api):
        api._get.return_value = {"items": []}
        service.list_conversations()
        _, kwargs = api._get.call_args
        assert kwargs["params"]["limit"] == 20

    def test_list_conversations_without_cursor(self, service, api):
        """When cursor is None, it should not appear in params."""
        api._get.return_value = {"items": []}
        service.list_conversations()
        _, kwargs = api._get.call_args
        assert "cursor" not in kwargs["params"]

    def test_get_conversation_calls_get(self, service, api):
        api._get.return_value = {"id": "conv_1"}
        result = service.get_conversation("conv_1")
        api._get.assert_called_once_with("/api/v1/copilot/conversations/conv_1")
        assert result == {"id": "conv_1"}

    def test_list_insights_calls_get(self, service, api):
        api._get.return_value = {"items": [{"id": "i1"}], "limit": 20}
        result = service.list_insights(limit=10, status_filter="active")
        api._get.assert_called_once_with(
            "/api/v1/copilot/insights",
            params={"limit": 10, "status_filter": "active"},
        )
        assert result == [{"id": "i1"}]

    def test_list_insights_unwraps_items(self, service, api):
        api._get.return_value = {"items": [{"id": "i1"}]}
        result = service.list_insights()
        assert result == [{"id": "i1"}]

    def test_list_insights_empty_on_none(self, service, api):
        api._get.return_value = None
        assert service.list_insights() == []

    def test_list_insights_empty_on_missing_items(self, service, api):
        api._get.return_value = {}
        assert service.list_insights() == []

    def test_list_insights_default_limit(self, service, api):
        api._get.return_value = {"items": []}
        service.list_insights()
        _, kwargs = api._get.call_args
        assert kwargs["params"]["limit"] == 20

    def test_list_insights_without_status_filter(self, service, api):
        """When status_filter is None, it should not appear in params."""
        api._get.return_value = {"items": []}
        service.list_insights()
        _, kwargs = api._get.call_args
        assert "status_filter" not in kwargs["params"]

    def test_ws_url_uses_wss_for_https(self, service, api):
        api._base_url = "https://api.example.com"
        result = service.ws_url("conv_1")
        assert result.startswith("wss://")
        assert "conv_1" in result
        assert "token=jwt123" in result

    def test_ws_url_uses_ws_for_http(self, service, api):
        api._base_url = "http://localhost:8000"
        result = service.ws_url("conv_1")
        assert result.startswith("ws://localhost:8000")

    def test_ws_url_without_auth_token(self, api):
        service = RemoteCopilotService(api, auth_token="")
        api._base_url = "https://api.example.com"
        result = service.ws_url("conv_1")
        assert "token=" in result
        # Token value should be empty string
        assert result.endswith("token=")

    def test_ws_url_strips_trailing_slash(self, service, api):
        api._base_url = "https://api.example.com/"
        result = service.ws_url("conv_1")
        # No double slashes
        assert "//api/v1" not in result
        assert result.startswith("wss://api.example.com/api/v1/copilot/ws/conv_1")


class TestRemoteFeatureFlagService:
    """Tests for client/remote_feature_flags.py"""

    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteFeatureFlagService(api)

    def test_list_flags_calls_get(self, service, api):
        api._get.return_value = {"flags": [{"key": "copilot", "enabled": True}]}
        result = service.list_flags()
        api._get.assert_called_once_with("/api/v1/feature-flags/")
        assert result == [{"key": "copilot", "enabled": True}]

    def test_list_flags_empty_on_none(self, service, api):
        api._get.return_value = None
        assert service.list_flags() == []

    def test_list_flags_empty_on_missing_key(self, service, api):
        api._get.return_value = {}
        assert service.list_flags() == []

    def test_is_enabled_calls_get(self, service, api):
        api._get.return_value = {"key": "copilot", "enabled": True}
        result = service.is_enabled("copilot", company_id=42)
        api._get.assert_called_once_with(
            "/api/v1/feature-flags/copilot",
            params={"company_id": 42},
        )
        assert result is True

    def test_is_enabled_returns_false_on_exception(self, service, api):
        api._get.side_effect = Exception("network error")
        result = service.is_enabled("copilot", company_id=42)
        assert result is False

    def test_is_enabled_default_company_id(self, service, api):
        api._get.return_value = {"enabled": False}
        service.is_enabled("test_flag")
        _, kwargs = api._get.call_args
        assert kwargs["params"]["company_id"] == 0

    def test_is_enabled_returns_false_when_field_missing(self, service, api):
        api._get.return_value = {"key": "copilot"}  # no "enabled" field
        result = service.is_enabled("copilot")
        assert result is False

    def test_is_enabled_returns_false_when_response_none(self, service, api):
        api._get.return_value = None
        result = service.is_enabled("copilot")
        assert result is False

    def test_set_enabled_calls_enable_post(self, service, api):
        api._post.return_value = {"key": "copilot", "enabled": True}
        result = service.set_enabled("copilot", True, company_id=42)
        api._post.assert_called_once_with(
            "/api/v1/feature-flags/copilot/enable",
            json_data={"company_id": 42},
        )
        assert result == {"key": "copilot", "enabled": True}

    def test_set_enabled_calls_disable_post(self, service, api):
        api._post.return_value = {"key": "copilot", "enabled": False}
        result = service.set_enabled("copilot", False)
        api._post.assert_called_once_with(
            "/api/v1/feature-flags/copilot/disable",
            json_data={"company_id": 0},
        )

    def test_are_all_enabled_true_when_all_true(self, service, api):
        def mock_get(path, **kwargs):
            if "flag_a" in path:
                return {"enabled": True}
            if "flag_b" in path:
                return {"enabled": True}
            return {"enabled": False}
        api._get.side_effect = mock_get
        assert service.are_all_enabled(["flag_a", "flag_b"]) is True

    def test_are_all_enabled_false_when_any_false(self, service, api):
        def mock_get(path, **kwargs):
            if "flag_a" in path:
                return {"enabled": True}
            return {"enabled": False}
        api._get.side_effect = mock_get
        assert service.are_all_enabled(["flag_a", "flag_b"]) is False

    def test_are_all_enabled_empty_list(self, service, api):
        """An empty list of flags should return True (vacuous truth)."""
        assert service.are_all_enabled([]) is True

    def test_are_all_enabled_passes_company_id(self, service, api):
        """are_all_enabled should forward company_id to is_enabled calls."""
        api._get.return_value = {"enabled": True}
        service.are_all_enabled(["flag_a"], company_id=99)
        # Verify the company_id was passed in params
        _, kwargs = api._get.call_args
        assert kwargs["params"]["company_id"] == 99

    def test_is_enabled_returns_false_on_http_error(self, service, api):
        """Simulate what happens when backend returns 404 for unknown flag."""
        api._get.side_effect = RuntimeError("404 Client Error")
        result = service.is_enabled("nonexistent_flag")
        assert result is False
