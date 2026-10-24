"""Small helpers for explicit database CHECK constraints."""

from enum import Enum

from sqlalchemy import CheckConstraint


def enum_check(column_name: str, enum_type: type[Enum], *, nullable: bool = False) -> CheckConstraint:
    values = ", ".join(f"'{item.value}'" for item in enum_type)
    predicate = f"{column_name} IN ({values})"
    if nullable:
        predicate = f"{column_name} IS NULL OR ({predicate})"
    return CheckConstraint(predicate, name=f"{column_name}_valid")
