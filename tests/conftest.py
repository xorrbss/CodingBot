"""모든 테스트 공유 fixture."""
import pytest


@pytest.fixture
def tmp_codingbot_home(tmp_path, monkeypatch):
    """격리된 가짜 ~/.codingbot 디렉터리."""
    home = tmp_path / "codingbot_home"
    home.mkdir()
    monkeypatch.setenv("CODINGBOT_HOME", str(home))
    return home


@pytest.fixture
def mock_anthropic(mocker):
    """anthropic.Anthropic 생성자를 mock으로 패치하고 반환."""
    mock_client = mocker.MagicMock()
    mocker.patch("anthropic.Anthropic", return_value=mock_client)
    return mock_client
