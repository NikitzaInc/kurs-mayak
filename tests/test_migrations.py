from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_history_is_catalog_then_quotes() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    revisions = list(scripts.walk_revisions())
    assert [revision.revision for revision in revisions] == [
        "0002_quotes_storage",
        "0001_catalog_and_sessions",
    ]
    assert revisions[0].down_revision == "0001_catalog_and_sessions"
    assert revisions[1].down_revision is None

    migration_files = list((project_root / "infrastructure/db/migrations/versions").glob("*.py"))
    assert {path.name for path in migration_files} == {
        "0001_catalog_and_sessions.py",
        "0002_quotes_storage.py",
    }
