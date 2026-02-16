"""Tests for workflow functions."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.workflows import setup_site_hugo, setup_site_wordpress


def _setup_site_config(tmp_path: Path, site_id: str = "site1") -> str:
    """Helper to set up site config CSV."""
    csv_content = (
        "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
        "llm_provider,site_title,site_description,theme,seo_plugin,internal_linking_mode\n"
        f"{site_id},example.com,test-server,prompts.yaml,test topic,wordpress,10,2,openai,"
        "Test Site,Test Description,twentytwentyfour,rankmath,disabled\n"
    )
    csv_file = tmp_path / "sites.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


class TestSetupSiteWordpress:
    """Test setup_site_wordpress function."""

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.WordPressDeployer")
    @patch("site_automator.workflows.WordOpsProvisioner")
    def test_creates_new_site_successfully(
        self,
        mock_wordops_class,
        mock_wp_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test creating a new site from scratch (happy path)."""
        # Setup
        csv_path = _setup_site_config(tmp_path)

        # Mock WordOps and WordPress
        mock_wordops = Mock()
        mock_wordops_class.return_value = mock_wordops

        mock_wordpress = Mock()
        mock_wordpress.site_exists.return_value = False  # Site doesn't exist yet
        mock_wp_class.return_value = mock_wordpress

        # Execute
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": csv_path}):
            setup_site_wordpress("site1")

        # Verify WordOps and WordPress calls
        mock_wordops_class.assert_called_once_with(host="test-server")
        mock_wordpress.site_exists.assert_called_once_with("example.com")
        mock_wordops.create_site.assert_called_once_with(
            "example.com", flags=["--wpfc"]
        )
        mock_wordops.ensure_ssl.assert_called_once_with("example.com")
        mock_gen_topics.assert_called_once_with("site1")
        mock_gen_articles.assert_called_once_with("site1")
        mock_wordpress.initial_setup.assert_called_once_with(
            "example.com",
            "Test Site",
            "Test Description",
            "twentytwentyfour",
            "rankmath",
            "disabled",
        )
        mock_wordops.close.assert_called_once()

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.WordPressDeployer")
    @patch("site_automator.workflows.WordOpsProvisioner")
    def test_skips_creation_if_site_exists(
        self,
        mock_wordops_class,
        mock_wp_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test that site creation is skipped if site already exists."""
        # Setup
        csv_path = _setup_site_config(tmp_path)

        mock_wordops = Mock()
        mock_wordops_class.return_value = mock_wordops

        mock_wordpress = Mock()
        mock_wordpress.site_exists.return_value = True  # Site already exists
        mock_wp_class.return_value = mock_wordpress

        # Execute
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": csv_path}):
            setup_site_wordpress("site1")

        # Verify site creation was skipped
        mock_wordpress.site_exists.assert_called_once_with("example.com")
        mock_wordops.create_site.assert_not_called()
        mock_wordops.ensure_ssl.assert_not_called()

        # But topics, articles, and initial setup still happen
        mock_gen_topics.assert_called_once()
        mock_gen_articles.assert_called_once()
        mock_wordpress.initial_setup.assert_called_once()
        mock_wordops.close.assert_called_once()

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.WordPressDeployer")
    @patch("site_automator.workflows.WordOpsProvisioner")
    def test_wipes_and_installs_when_wipe_true(
        self,
        mock_wordops_class,
        mock_wp_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test wipe and install is called when wipe=True."""
        # Setup
        csv_path = _setup_site_config(tmp_path)

        mock_wordops = Mock()
        mock_wordops_class.return_value = mock_wordops

        mock_wordpress = Mock()
        mock_wordpress.site_exists.return_value = True
        mock_wp_class.return_value = mock_wordpress

        # Execute with wipe=True
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": csv_path}):
            setup_site_wordpress("site1", wipe=True)

        # Verify wipe and install was called
        mock_wordpress.wipe_and_install.assert_called_once_with(
            "example.com",
            "Test Site",
            exclude_dirs=["stats"],
            confirm=True,
        )
        mock_wordops.close.assert_called_once()

    @patch("site_automator.workflows.shutil.rmtree")
    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.WordPressDeployer")
    @patch("site_automator.workflows.WordOpsProvisioner")
    def test_deletes_local_content_when_flag_true(
        self,
        mock_wordops_class,
        mock_wp_class,
        mock_gen_topics,
        mock_gen_articles,
        mock_rmtree,
        tmp_path,
    ):
        """Test local content folder is deleted when delete_local_content=True."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        site_dir = content_path / "site1"
        site_dir.mkdir(parents=True, exist_ok=True)

        mock_wordops = Mock()
        mock_wordops_class.return_value = mock_wordops

        mock_wordpress = Mock()
        mock_wordpress.site_exists.return_value = True
        mock_wp_class.return_value = mock_wordpress

        # Execute with delete_local_content=True
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            setup_site_wordpress("site1", delete_local_content=True)

        # Verify rmtree was called on the site directory
        mock_rmtree.assert_called_once_with(site_dir)
        mock_wordops.close.assert_called_once()

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.WordPressDeployer")
    @patch("site_automator.workflows.WordOpsProvisioner")
    def test_closes_connection_even_on_error(
        self,
        mock_wordops_class,
        mock_wp_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test that wordops.close() is called even when an error occurs."""
        # Setup
        csv_path = _setup_site_config(tmp_path)

        mock_wordops = Mock()
        mock_wordops_class.return_value = mock_wordops

        mock_wordpress = Mock()
        mock_wordpress.site_exists.return_value = False
        mock_wordpress.initial_setup.side_effect = Exception("Setup failed!")
        mock_wp_class.return_value = mock_wordpress

        # Execute and expect error
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": csv_path}):
            with pytest.raises(Exception, match="Setup failed!"):
                setup_site_wordpress("site1")

        # Verify close was still called (cleanup in finally block)
        mock_wordops.close.assert_called_once()

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.WordPressDeployer")
    @patch("site_automator.workflows.WordOpsProvisioner")
    def test_continues_on_ssl_failure(
        self,
        mock_wordops_class,
        mock_wp_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test that SSL failure is caught and setup continues."""
        # Setup
        csv_path = _setup_site_config(tmp_path)

        mock_wordops = Mock()
        mock_wordops.ensure_ssl.side_effect = Exception("SSL failed!")
        mock_wordops_class.return_value = mock_wordops

        mock_wordpress = Mock()
        mock_wordpress.site_exists.return_value = False
        mock_wp_class.return_value = mock_wordpress

        # Execute - should not raise error
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": csv_path}):
            setup_site_wordpress("site1")

        # Verify setup continued despite SSL failure
        mock_gen_topics.assert_called_once()
        mock_gen_articles.assert_called_once()
        mock_wordpress.initial_setup.assert_called_once()
        mock_wordops.close.assert_called_once()


class TestSetupSiteHugo:
    """Test setup_site_hugo function."""

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.HugoDeployer")
    @patch("site_automator.workflows.CaddyProvisioner")
    def test_setup_without_wipe_correct_order(
        self,
        mock_caddy_class,
        mock_hugo_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test setup without wipe follows correct order."""
        # Setup
        csv_content = (
            "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
            "llm_provider,llm_batch_mode,theme\n"
            "site1,example.com,test-server,prompts.yaml,test topic,hugo,10,2,openai,false,ananke\n"
        )
        csv_path = tmp_path / "sites.csv"
        csv_path.write_text(csv_content)

        mock_caddy = Mock()
        mock_ssh = Mock()
        mock_caddy.ssh = mock_ssh
        mock_caddy_class.return_value = mock_caddy

        mock_hugo = Mock()
        mock_hugo_class.return_value = mock_hugo

        # Execute
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": str(csv_path)}):
            setup_site_hugo("site1", wipe=False)

        # Verify Caddy setup
        mock_caddy_class.assert_called_once_with(host="test-server")

        # Verify DNS cache flush
        mock_ssh.run_command.assert_any_call("resolvectl flush-caches", check=False)

        mock_caddy.enable_domain.assert_called_once_with("example.com")
        mock_hugo.check_hugo_installed.assert_called_once()

        # Verify wipe was NOT called
        mock_hugo.wipe_site.assert_not_called()

        # Verify content generation
        mock_gen_topics.assert_called_once_with("site1")
        mock_gen_articles.assert_called_once_with("site1", add_hugo_frontmatter=True)

        # Verify initial setup
        mock_hugo.initial_setup.assert_called_once_with("example.com")

        # Verify cleanup
        mock_caddy.close.assert_called_once()

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.HugoDeployer")
    @patch("site_automator.workflows.CaddyProvisioner")
    def test_setup_with_wipe_correct_order(
        self,
        mock_caddy_class,
        mock_hugo_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test setup with wipe=True follows correct order: wipe THEN initialize."""
        # Setup
        csv_content = (
            "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
            "llm_provider,llm_batch_mode,theme\n"
            "site1,example.com,test-server,prompts.yaml,test topic,hugo,10,2,openai,false,ananke\n"
        )
        csv_path = tmp_path / "sites.csv"
        csv_path.write_text(csv_content)

        mock_caddy = Mock()
        mock_ssh = Mock()
        mock_caddy.ssh = mock_ssh
        mock_caddy_class.return_value = mock_caddy

        mock_hugo = Mock()
        mock_hugo_class.return_value = mock_hugo

        # Execute with wipe=True
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": str(csv_path)}):
            setup_site_hugo("site1", wipe=True)

        # Verify DNS cache flush
        mock_ssh.run_command.assert_any_call("resolvectl flush-caches", check=False)

        # Verify wipe is called BEFORE initial_setup
        call_order = []
        for call in mock_hugo.method_calls:
            if call[0] in ["wipe_site", "initial_setup"]:
                call_order.append(call[0])

        assert call_order == [
            "wipe_site",
            "initial_setup",
        ], f"Expected wipe → initial_setup, got {call_order}"

        # Verify wipe was called with correct args
        mock_hugo.wipe_site.assert_called_once_with(
            "example.com", confirm=True, exclude_dirs=["public/stats"]
        )

        # Verify cleanup
        mock_caddy.close.assert_called_once()

    @patch("site_automator.workflows.shutil.rmtree")
    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.HugoDeployer")
    @patch("site_automator.workflows.CaddyProvisioner")
    def test_deletes_local_content_when_flag_true(
        self,
        mock_caddy_class,
        mock_hugo_class,
        mock_gen_topics,
        mock_gen_articles,
        mock_rmtree,
        tmp_path,
    ):
        """Test local content folder is deleted when delete_local_content=True."""
        # Setup
        csv_content = (
            "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
            "llm_provider,llm_batch_mode,theme\n"
            "site1,example.com,test-server,prompts.yaml,test topic,hugo,10,2,openai,false,ananke\n"
        )
        csv_path = tmp_path / "sites.csv"
        csv_path.write_text(csv_content)

        content_path = tmp_path / "content"
        site_dir = content_path / "site1"
        site_dir.mkdir(parents=True, exist_ok=True)

        mock_caddy = Mock()
        mock_ssh = Mock()
        mock_caddy.ssh = mock_ssh
        mock_caddy_class.return_value = mock_caddy

        mock_hugo = Mock()
        mock_hugo_class.return_value = mock_hugo

        # Execute with delete_local_content=True
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": str(csv_path),
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            setup_site_hugo("site1", delete_local_content=True)

        # Verify rmtree was called on the site directory
        mock_rmtree.assert_called_once_with(site_dir)
        mock_caddy.close.assert_called_once()

    @patch("site_automator.workflows.generate_articles_llm")
    @patch("site_automator.workflows.generate_topics_site_id")
    @patch("site_automator.workflows.HugoDeployer")
    @patch("site_automator.workflows.CaddyProvisioner")
    def test_closes_connection_even_on_error(
        self,
        mock_caddy_class,
        mock_hugo_class,
        mock_gen_topics,
        mock_gen_articles,
        tmp_path,
    ):
        """Test that caddy.close() is called even when an error occurs."""
        # Setup
        csv_content = (
            "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
            "llm_provider,llm_batch_mode,theme\n"
            "site1,example.com,test-server,prompts.yaml,test topic,hugo,10,2,openai,false,ananke\n"
        )
        csv_path = tmp_path / "sites.csv"
        csv_path.write_text(csv_content)

        mock_caddy = Mock()
        mock_ssh = Mock()
        mock_caddy.ssh = mock_ssh
        mock_caddy_class.return_value = mock_caddy

        mock_hugo = Mock()
        mock_hugo.initial_setup.side_effect = Exception("Setup failed!")
        mock_hugo_class.return_value = mock_hugo

        # Execute and expect error
        with patch.dict("os.environ", {"SITES_CONFIG_PATH": str(csv_path)}):
            with pytest.raises(Exception, match="Setup failed!"):
                setup_site_hugo("site1")

        # Verify close was still called (cleanup in finally block)
        mock_caddy.close.assert_called_once()
