"""Tests for invoicing config_manager."""
import json
import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

from services.invoicing.config_manager import (
    load_company_config,
    save_company_config,
    DEFAULT_CONFIG,
)


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear the lru_cache on load_company_config between tests."""
    load_company_config.cache_clear()
    yield


@patch("services.invoicing.config_manager.os.path.exists", return_value=False)
def test_load_default_when_missing(mock_exists):
    with patch("services.invoicing.config_manager.save_company_config") as mock_save:
        config = load_company_config()
        assert config["company_name"] is not None
        assert "logo_path" in config


@patch("services.invoicing.config_manager.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open,
       read_data='{"company_name": "Test Corp", "cui": "RO12345", "reg_number": "J123", '
                 '"address": "Addr", "phone": "0712345678", "email": "t@t.com", '
                 '"logo_path": "", "company_color": "#6366f1", '
                 '"signature_path": "", "stamp_path": ""}')
def test_load_existing_config(mock_file, mock_exists):
    config = load_company_config()
    assert config["company_name"] == "Test Corp"
    assert config["cui"] == "RO12345"


@patch("services.invoicing.config_manager.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open,
       read_data='{"company_name": "Test Corp"}')
def test_load_config_missing_fields(mock_file, mock_exists):
    config = load_company_config()
    assert config["company_name"] == "Test Corp"
    # Defaults should fill missing fields
    assert "cui" in config
    assert "logo_path" in config


@patch("services.invoicing.config_manager.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open,
       read_data='"not a dict"')
def test_load_invalid_data(mock_file, mock_exists):
    config = load_company_config()
    assert isinstance(config, dict)
    assert config["company_name"] == DEFAULT_CONFIG["company_name"]


@patch("services.invoicing.config_manager.save_company_config")
@patch("services.invoicing.config_manager.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open,
       read_data='invalid json')
def test_load_invalid_json(mock_file, mock_exists, mock_save):
    config = load_company_config()
    assert isinstance(config, dict)


@patch("services.invoicing.config_manager.tempfile.mkstemp")
@patch("services.invoicing.config_manager.os.makedirs")
@patch("services.invoicing.config_manager.os.replace")
@patch("services.invoicing.config_manager.os.fdopen")
@patch("services.invoicing.config_manager.load_company_config.cache_clear")
def test_save_company_config(mock_cache_clear, mock_fdopen, mock_replace,
                              mock_makedirs, mock_mkstemp):
    mock_mkstemp.return_value = (1, "/tmp/tmpXXXX.json")
    mock_file = MagicMock()
    mock_fdopen.return_value.__enter__.return_value = mock_file
    data = {"company_name": "Test"}
    save_company_config(data)
    mock_replace.assert_called_with("/tmp/tmpXXXX.json",
                                    mock_makedirs.call_args[0][0] + "/company_config.json")
    mock_cache_clear.assert_called_once()
