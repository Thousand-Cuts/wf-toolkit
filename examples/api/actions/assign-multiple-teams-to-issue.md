# assignMultiple — add teams (and/or users/roles) to an issue

## Working pattern (verified v18.0)

```
PUT /attask/api/v18.0/optask/{issueID}/assignMultiple
Content-Type: application/json
Authorization: Bearer <token>

{
  "teamIDs": [
    "aabbccdd000000000000000000000001",
    "aabbccdd000000000000000000000002"
  ],
  "userIDs": [],
  "roleIDs": []
}
```

## Dynamic body in Fusion (confirmed working)

```
{
  "teamIDs": ["{{join(map(DATA; "ID"); """,""")}}"],
  "userIDs": [],
  "roleIDs": []
}
```

`""","""` is Fusion's way of expressing the separator `","` — double-double-quote (`""`) is how Fusion escapes a literal quote inside a string expression.

## Notes

- Same pattern works for `task`: replace `optask` with `task` in the path.
- Pass all three array keys even if empty — omitting them has caused silent failures.
- Do NOT use `?action=assignMultiple` + query-string array params (`teamIDs[]=...`). That triggers a 422 "JSON parsing error."
- `Content-Type: application/json` is required — raw JSON body, not `updates=<JSON string>`.
- Do NOT use `\"` in Fusion expressions — not a valid escape sequence.
- Do NOT use `char(34)` — not a valid Fusion function.
- Do NOT use `join(...; ",")` with outer `["` `"]` — produces one quoted string, not an array.
