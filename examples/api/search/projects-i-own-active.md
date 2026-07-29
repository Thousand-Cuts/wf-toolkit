# Search: Active Projects I Own

**What this shows:** GET `/project/search` filtered to current (active) projects owned by the calling user, with a selective `fields=` list.

## Request

```
GET https://<domain>.my.workfront.com/attask/api/v17.0/project/search?ownerID=$$USER.ID&status=CUR&status_Mod=eq&fields=name,status,plannedCompletionDate,percentComplete,DE:Region
sessionID: <your_session_token>
```

## Response shape

```json
{
  "data": [
    {
      "ID": "4c7882...",
      "name": "Website Redesign",
      "status": "CUR",
      "plannedCompletionDate": "2026-08-15T00:00:00:000-0700",
      "percentComplete": 45.0,
      "DE:Region": "North America"
    }
  ]
}
```

## Variants

### Filter by portfolio as well

Add `portfolioID=<portfolioID>&portfolioID_Mod=eq` to the query string.

### Return only projects due in the next 30 days

```
&plannedCompletionDate=$$TODAY&plannedCompletionDate_Mod=gte
&plannedCompletionDate=$$TODAY+30d&plannedCompletionDate_Mod=lte
```

Note: when using the same parameter name twice for a range, the API applies both constraints (AND logic by default).

### Include the portfolio name

Add `portfolio:name` to the `fields=` list. The API traverses the relationship automatically.

## Notes

- `$$USER.ID` resolves to the ID of the user whose token is making the request — no hardcoded ID needed.
- `status=CUR` is the enum for "Current" (active). See `10-status-and-enum-codes.md` for other values.
- The default response cap is 2,000 records. For large portfolios, add `$$LIMIT` and `$$FIRST` for pagination (see `examples/api/pagination/`).
- `DE:Region` returns the custom field value as a string; the field must exist on a form attached to the project.
