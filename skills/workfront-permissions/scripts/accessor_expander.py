"""Expand a Workfront AccessRule accessor into the set of users effectively
granted access via that accessor.

Pure function. The caller pre-builds three indices (group → members,
team → members, role → users) via API and hands them in. The expander
just looks up; no API calls.

Used by the "who has access to object Y?" audit flow
(knowledge/permissions/05-audit-recipes.md).
"""

from __future__ import annotations

from typing import Literal

AccessorObjCode = Literal["USER", "GROUP", "TEAMOB", "ROLE"]


def expand_accessor_to_users(
    accessor: dict,
    *,
    group_member_index: dict[str, list[str]] | None = None,
    team_member_index: dict[str, list[str]] | None = None,
    role_member_index: dict[str, list[str]] | None = None,
    group_parent_index: dict[str, list[str]] | None = None,
    group_child_index: dict[str, list[str]] | None = None,
    cascade_to_parent_groups: bool = False,
    cascade_to_subgroups: bool = False,
) -> list[str]:
    """Return the unique userIDs effectively granted access via `accessor`.

    `accessor` shape: {"objCode": "GROUP" | "TEAMOB" | "ROLE" | "USER", "id": ...}

    For GROUP accessors: members of the group. If `cascade_to_subgroups`
    is True, include members of subgroups (computed via group_child_index).
    If `cascade_to_parent_groups` is True, include members of parent groups.

    For TEAMOB / ROLE: straight-up lookup in the relevant index.
    For USER: returns `[id]`.

    Unknown objCode returns []. Cycles in the group hierarchy are
    handled — no infinite loops.
    """
    group_member_index = group_member_index or {}
    team_member_index = team_member_index or {}
    role_member_index = role_member_index or {}
    group_parent_index = group_parent_index or {}
    group_child_index = group_child_index or {}

    objcode = accessor.get("objCode")
    accessor_id = accessor.get("id")
    if not accessor_id:
        return []

    if objcode == "USER":
        return [accessor_id]

    if objcode == "TEAMOB":
        return _dedup(team_member_index.get(accessor_id, []))

    if objcode == "ROLE":
        return _dedup(role_member_index.get(accessor_id, []))

    if objcode == "GROUP":
        visited_groups: set[str] = set()
        users: list[str] = []
        _collect_group_users(
            group_id=accessor_id,
            group_member_index=group_member_index,
            group_parent_index=group_parent_index,
            group_child_index=group_child_index,
            cascade_to_parent_groups=cascade_to_parent_groups,
            cascade_to_subgroups=cascade_to_subgroups,
            visited_groups=visited_groups,
            users=users,
        )
        return _dedup(users)

    return []


def _collect_group_users(
    *,
    group_id: str,
    group_member_index: dict[str, list[str]],
    group_parent_index: dict[str, list[str]],
    group_child_index: dict[str, list[str]],
    cascade_to_parent_groups: bool,
    cascade_to_subgroups: bool,
    visited_groups: set[str],
    users: list[str],
) -> None:
    if group_id in visited_groups:
        return
    visited_groups.add(group_id)

    users.extend(group_member_index.get(group_id, []))

    if cascade_to_subgroups:
        for child in group_child_index.get(group_id, []):
            _collect_group_users(
                group_id=child,
                group_member_index=group_member_index,
                group_parent_index=group_parent_index,
                group_child_index=group_child_index,
                cascade_to_parent_groups=cascade_to_parent_groups,
                cascade_to_subgroups=cascade_to_subgroups,
                visited_groups=visited_groups,
                users=users,
            )

    if cascade_to_parent_groups:
        for parent in group_parent_index.get(group_id, []):
            _collect_group_users(
                group_id=parent,
                group_member_index=group_member_index,
                group_parent_index=group_parent_index,
                group_child_index=group_child_index,
                cascade_to_parent_groups=cascade_to_parent_groups,
                cascade_to_subgroups=cascade_to_subgroups,
                visited_groups=visited_groups,
                users=users,
            )


def _dedup(items: list[str]) -> list[str]:
    """Preserve order, drop duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
