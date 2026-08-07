from nextrole import __version__
from nextrole.cli import main


def test_cli_shows_help_when_no_command_is_given(capsys: object) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Collect and analyze junior technology job postings" in output


def test_cli_reports_the_package_version(capsys: object) -> None:
    try:
        main(["--version"])
    except SystemExit as error:
        assert error.code == 0

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert output.strip() == f"nextrole {__version__}"


def test_cli_prints_only_non_secret_configuration(monkeypatch: object, capsys: object) -> None:
    monkeypatch.setenv("NEXTROLE_DATABASE_URL", "postgresql://user:secret@localhost/db")  # type: ignore[attr-defined]

    assert main(["config"]) == 0

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "environment=development" in output
    assert "database_configured=True" in output
    assert "secret" not in output
