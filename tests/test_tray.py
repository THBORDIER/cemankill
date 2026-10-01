from pathlib import Path

from browser_bot.tray import BotController, build_bot_command


def test_tray_launches_the_safe_account_watcher(tmp_path):
    command = build_bot_command(Path(tmp_path), executable="pythonw.exe", headless=True)
    assert command[:3] == ["pythonw.exe", "-m", "browser_bot"]
    assert command[command.index("--profile-dir") + 1] == str(tmp_path / "data" / "account-profile")
    assert {"--all-sessions", "--archives", "--watch", "--headless"}.issubset(command)


def test_visible_tray_browser_uses_same_account_profile(tmp_path):
    command = build_bot_command(Path(tmp_path), executable="pythonw.exe", headless=False)

    assert command[command.index("--profile-dir") + 1] == str(tmp_path / "data" / "account-profile")
    assert {"--all-sessions", "--archives", "--watch"}.issubset(command)
    assert "--headless" not in command


def test_stale_or_legacy_pid_file_is_not_trusted(tmp_path):
    controller = BotController(tmp_path)
    controller.data_dir.mkdir()
    controller.pid_path.write_text("1234", encoding="ascii")

    assert controller.running_pid() is None
    assert not controller.pid_path.exists()
