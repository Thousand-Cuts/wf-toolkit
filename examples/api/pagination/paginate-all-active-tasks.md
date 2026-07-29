# Pagination: Fetch All Active Tasks with $$FIRST / $$LIMIT

**What this shows:** Use `$$FIRST` and `$$LIMIT` to page through a result set larger than the default 2,000-record cap. Always pair with an `$$ORDER` sort to guarantee stable page boundaries.

## Request (first page)

```
GET https://<domain>.my.workfront.com/attask/api/v17.0/task/search?status=INP&status_Mod=eq&fields=name,status,plannedCompletionDate,project:name&$$FIRST=0&$$LIMIT=200&$$ORDER=plannedCompletionDate:asc
sessionID: <your_session_token>
```

## Loop pattern (pseudo-code)

```
offset = 0
page_size = 200
all_tasks = []

loop:
  response = GET /task/search?...&$$FIRST={offset}&$$LIMIT={page_size}&$$ORDER=plannedCompletionDate:asc
  page = response.data

  all_tasks += page

  if len(page) < page_size:
    break          # last page — fewer results than requested means we're done

  offset += page_size
```

## Notes

- **Always include `$$ORDER`.** Without a stable sort, the API may return the same records on consecutive pages or skip records if the underlying data changes between requests. Sort by a field that doesn't change during your run (e.g., `ID`, `plannedCompletionDate`).
- **`$$LIMIT` max is 2,000 per page.** Values above 2,000 are clamped to 2,000. Use 200–500 for safety margin.
- **`$$FIRST` is 0-indexed.** First page is `$$FIRST=0`, second is `$$FIRST=200` (for a page size of 200), etc.
- **HTTP 429 throttling.** If you hit the concurrency limit, back off and retry. See `09-pagination-and-limits.md` for Workfront's documented concurrency rules.
- **`/count` for totals.** To know how many records you'll be paging through before starting, call `/task/count?status=INP&status_Mod=eq` first. Response is `{ "count": 1842 }`.
