# 09 — Pagination and Limits

The Workfront API caps how many records it returns per request. To process more, paginate by issuing repeated requests with `$$FIRST` (offset) and `$$LIMIT` (page size) parameters.

## `$$FIRST` and `$$LIMIT`

| Parameter | Meaning | Default | Maximum |
|---|---|---|---|
| `$$LIMIT` | Max records to return per call | 100 | 2,000 |
| `$$FIRST` | Zero-indexed offset (skip this many records) | 0 | No documented cap |

```
GET /attask/api/v17.0/project/search
  ?status=CUR
  &status_Mod=eq
  &fields=name,status
  &$$FIRST=0
  &$$LIMIT=2000
```

If `$$LIMIT` is omitted, the API returns at most 100 records. If you set `$$LIMIT` above 2,000, the API caps it at 2,000.

## Iterating through all pages

Start at `$$FIRST=0` and increment by `$$LIMIT` each call. Stop when:
- The response array length is less than `$$LIMIT`, **or**
- The response array is empty (`"data": []`)

```python
first = 0
limit = 2000
while True:
    page = get("/project/search", $$FIRST=first, $$LIMIT=limit, ...)
    results.extend(page["data"])
    if len(page["data"]) < limit:
        break
    first += limit
```

There is no explicit "total count" field in a paginated response. To get a total before paging, run a count-only query first (see below).

## Count-only queries

Get the total number of matching records without retrieving the rows:

```
GET /attask/api/v17.0/project/count?status=CUR&status_Mod=eq
```

Returns:
```json
{ "count": 347 }
```

Use this to size your pagination loop upfront or to display totals in a UI without fetching data.

## Deterministic ordering (required for safe pagination)

Without an explicit sort, the order of results is not guaranteed to be stable across pages. If records are inserted or updated between your page requests, you can miss records or see duplicates.

**Always sort by a stable field:**
```
GET /attask/api/v17.0/project/search
  ?$$FIRST=0
  &$$LIMIT=2000
  &ID_Sort=asc
```

Sorting by `ID` (the object's GUID) is a safe choice because IDs are immutable. `entryDate_Sort=asc` is another common option. Verify the exact `_Sort` parameter syntax in the API Explorer for your target object.

## Other documented query limits

Beyond `$$LIMIT`, Adobe documents these hard limits per request:

| Limit | Value |
|---|---|
| Max `$$LIMIT` (records per call) | 2,000 |
| Max nested field depth | 4 levels |
| Max combined objects in a result | 50,000 (primary + secondary) |
| Max fields across all objects in a result | 1,000,000 (when result < 50,000 objects) |
| Max objects in a bulk create/update | 100 |
| Max URI length (production, preview, test-drive) | 8,892 bytes |

These limits are documented in Adobe's API basics page as of 2026-05. The `$$LIMIT` cap of 2,000 is **hard-enforced**: empirically verified on v17.0 (2026-05), requesting `$$LIMIT=2001` returns an error:

```json
{"error": {"message": "The requested limit 2001 is greater than the maximum allowed limit of 2000"}}
```

There is no silent truncation — the entire request fails. Always use `$$LIMIT=2000` (or lower) and paginate with `$$FIRST` when you need more.

## Rate limits and concurrency

Workfront limits **concurrent API threads**, not requests per second or per minute. The public documentation says:

> "The Workfront API limits concurrent API threads. This guardrail prevents system problems caused by abusive API calls."

It does not publish a specific concurrent-thread number. Community observations suggest limits in the range of 10 concurrent connections, but this has not been officially confirmed and may vary by instance tier. Verify with your Workfront account team if you're building a high-throughput integration.

**When the limit is hit:** The API returns HTTP `429 Too Many Requests` with the message `"429 Too many concurrent API requests"`. There is no documented `Retry-After` header in the Workfront response — the API does not indicate when capacity will free up.

**Retry strategy:** Implement exponential backoff on `429`. A simple starting pattern:
- On `429`, wait and retry after 1s, then 2s, then 4s (doubles each attempt)
- Cap at a reasonable ceiling (e.g., 30s)
- Log persistent `429` failures so you can diagnose whether the issue is your code or instance-level capacity

The same concurrent-thread limit applies to the Preview Sandbox as to production — it's the correct environment for load-testing your retry logic.

## Workfront Fusion limits

If you're building via Fusion rather than direct API calls, Fusion has its own additional guardrails (operations per minute, active scenarios, etc.) documented separately in the Fusion performance guardrails page. Those are Fusion-layer limits, not Workfront API limits.

## The shape of paginated requests

A paginated search typically looks like:

```
GET /attask/api/v17.0/task/search
  ?status=CUR
  &status_Mod=eq
  &fields=name,status
  &$$FIRST=0
  &$$LIMIT=2000
  &ID_Sort=asc
```

Then increment `$$FIRST` by `$$LIMIT` until the response returns fewer records than `$$LIMIT` or an empty array.

```
$$FIRST=0   → records 1–2000
$$FIRST=2000 → records 2001–4000
$$FIRST=4000 → records 4001–N (stop when count < 2000)
```

## Sources

| URL | What it provided |
|---|---|
| `https://experienceleague.adobe.com/en/docs/workfront/using/adobe-workfront-api/api-general-information/api-basics` | `$$FIRST` and `$$LIMIT` parameters, default (100) and max (2,000) values, all hard query limits table, concurrent thread rate limit mention, count endpoint |
| `https://experienceleague.adobe.com/en/docs/workfront-fusion/using/references/scenarios/fusion-performance-guardrails` | Confirmed Fusion has separate guardrails (context only) |
| `https://experienceleaguecommunities.adobe.com/t5/workfront-questions/is-anyone-else-getting-429-too-many-concurrent-api-requests/td-p/485050` | 429 error message text, community observations on concurrent limit, no Retry-After header |
| `https://experienceleaguecommunities.adobe.com/t5/workfront-ideas/add-api-rate-limit-feedback-to-workfront-api-responses/idi-p/605127` | Confirmed no rate-limit feedback in API responses (community idea thread requesting it) |
