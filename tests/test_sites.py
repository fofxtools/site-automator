import json
from pathlib import Path
from unittest.mock import patch

import pytest

from site_automator.sites import (
    load_all_sites,
    load_site_config,
    load_site_config_by_domain,
    initialize_site,
)

VALID_HEADERS = "site_id,domain,server,seed_topic,prompts_file,cms,pages_per_site,posts_per_day,llm_provider,llm_batch_mode\n"
VALID_ROW = (
    "site1,example.com,test-server,gardening,prompts.yaml,wordpress,10,2,openai,true\n"
)


def _write_csv(tmp_path: Path, content: str) -> str:
    csv_file = tmp_path / "sites.csv"
    csv_file.write_text(content)
    return str(csv_file)


class TestLoadAllSites:
    def test_loads_valid_csv(self, tmp_path):
        path = _write_csv(tmp_path, VALID_HEADERS + VALID_ROW)
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            rows = load_all_sites()
        assert len(rows) == 1
        assert rows[0]["site_id"] == "site1"

    def test_file_not_found(self, tmp_path):
        with patch.dict(
            "os.environ", {"SITES_CONFIG_PATH": str(tmp_path / "nope.csv")}
        ):
            with pytest.raises(FileNotFoundError):
                load_all_sites()

    def test_missing_required_header(self, tmp_path):
        path = _write_csv(tmp_path, "site_id,domain\nsite1,example.com\n")
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            with pytest.raises(ValueError, match="Missing required columns"):
                load_all_sites()

    def test_duplicate_site_ids(self, tmp_path):
        path = _write_csv(tmp_path, VALID_HEADERS + VALID_ROW + VALID_ROW)
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            with pytest.raises(ValueError, match="Duplicate site_id"):
                load_all_sites()


class TestLoadSiteConfig:
    def test_returns_normalized_row(self, tmp_path):
        path = _write_csv(tmp_path, VALID_HEADERS + VALID_ROW)
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            config = load_site_config("site1")
        assert config["pages_per_site"] == 10
        assert config["posts_per_day"] == 2
        assert config["llm_batch_mode"] is True

    def test_site_not_found(self, tmp_path):
        path = _write_csv(tmp_path, VALID_HEADERS + VALID_ROW)
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            with pytest.raises(ValueError, match="site_id not found"):
                load_site_config("nonexistentsite")

    def test_missing_boolean_column_defaults_false(self, tmp_path):
        headers = "site_id,domain,server,seed_topic,prompts_file,cms,pages_per_site,posts_per_day,llm_provider\n"
        row = "site1,example.com,test-server,gardening,prompts.yaml,wordpress,10,2,openai\n"
        path = _write_csv(tmp_path, headers + row)
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            config = load_site_config("site1")
        assert config["llm_batch_mode"] is False


class TestLoadSiteConfigByDomain:
    def test_returns_normalized_row_by_domain(self, tmp_path):
        path = _write_csv(tmp_path, VALID_HEADERS + VALID_ROW)
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            config = load_site_config_by_domain("example.com")
        assert config["site_id"] == "site1"
        assert config["domain"] == "example.com"
        assert config["server"] == "test-server"
        assert config["pages_per_site"] == 10
        assert config["posts_per_day"] == 2
        assert config["llm_batch_mode"] is True

    def test_domain_not_found(self, tmp_path):
        path = _write_csv(tmp_path, VALID_HEADERS + VALID_ROW)
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": path}):
            with pytest.raises(ValueError, match="domain not found"):
                load_site_config_by_domain("nonexistent.com")


class TestInitializeSite:
    def _setup_env(self, tmp_path: Path) -> dict[str, str]:
        csv_path = _write_csv(tmp_path, VALID_HEADERS + VALID_ROW)
        content_path = str(tmp_path / "content")
        return {"SITES_CONFIG_PATH": csv_path, "SITES_CONTENT_PATH": content_path}

    def test_creates_site_dir_and_json(self, tmp_path):
        env = self._setup_env(tmp_path)
        with patch.dict("os.environ", env):
            config = initialize_site("site1")

        init_json = tmp_path / "content" / "site1" / "site.init.json"
        assert init_json.exists()
        data = json.loads(init_json.read_text())
        assert data["site_id"] == "site1"
        assert data["pages_per_site"] == 10
        assert config["site_id"] == "site1"

    def test_does_not_overwrite_existing_json(self, tmp_path):
        env = self._setup_env(tmp_path)
        site_dir = tmp_path / "content" / "site1"
        site_dir.mkdir(parents=True)
        init_json = site_dir / "site.init.json"
        init_json.write_text('{"old": "data"}')

        with patch.dict("os.environ", env):
            config = initialize_site("site1")

        assert json.loads(init_json.read_text()) == {"old": "data"}
        assert config["site_id"] == "site1"

    def test_invalid_site_id_raises_no_dir_created(self, tmp_path):
        env = self._setup_env(tmp_path)
        with patch.dict("os.environ", env):
            with pytest.raises(ValueError, match="site_id not found"):
                initialize_site("nonexistent")
        assert not (tmp_path / "content" / "nonexistent").exists()
