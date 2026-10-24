from alembic import command
from sqlalchemy import create_engine, inspect

from conftest import EXPECTED_TABLES, _alembic_config


def test_migration_can_downgrade_to_base_and_upgrade_again(migrated_test_database) -> None:
    config = _alembic_config(migrated_test_database)
    command.downgrade(config, "base")
    engine = create_engine(migrated_test_database)
    try:
        assert not (EXPECTED_TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(migrated_test_database)
    try:
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
