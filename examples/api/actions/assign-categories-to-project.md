# Assigning custom forms (categories) via the `assignCategories` action

The custom-form assignment actions are hosted on **`CTGY`** (Category), not on the target object. They take the target via `objCode` + `objID` arguments. The action set covers projects, tasks, issues, portfolios, programs — any object with `catObjCode`.

Verified working v17.0 against a live Workfront sandbox, 2026-05-15.

## Working pattern

```bash
# Attach two custom forms to an issue
curl -X PUT "$$HOST/attask/api/v17.0/ctgy/assignCategories?apiKey=<key>" \
  --data-urlencode 'updates={"objCode":"OPTASK","objID":"<issueID>","categoryIDs":["<ctgyID1>","<ctgyID2>"]}'
```

Success response:
```json
{"data": {"result": null}}
```

## The dispatch shape is strict

Only one shape works. Form-encoded args, GET dispatch, target-object dispatch — all fail:

| Attempted shape | Server response |
|---|---|
| `PUT /ctgy/assignCategories` with `updates=<JSON>` body | ✅ `{"data":{"result":null}}` |
| `PUT /ctgy/assignCategories` with `objCode=...&categoryIDs=...` form params | ❌ `argument type mismatch` |
| `GET /ctgy/assignCategories?...` | ❌ `APIModel V17_0 does not support namedQuery assignCategories (CTGY)` |
| `PUT /optask/<id>/assignCategories` | ❌ `APIModel V17_0 does not support action assignCategories (OPTASK)` |
| `POST /ctgy/assignCategories` | ❌ `unrecognized URI format: too many parts` |
| `PUT /ctgy?action=assignCategories` (form args) | ❌ `argument type mismatch` |

The action is registered on the CTGY metadata object. The argument decoder requires the `updates=<JSON>` envelope because `categoryIDs` is a `string[]` and form-flat decoding can't reconstruct an array.

## Additive — not replace

Unlike `assignMultiple` (replace) and unlike a direct PUT on `objectCategories` (replace), `assignCategories` appends:

- Forms already attached before the call stay attached.
- New forms in the call are added on top.

If any ID in your batch is already attached, the **entire** call rejects:
```json
{"error": {"message": "Categories with the following IDs are already attached: aaaa0001...", "code": 0}}
```

There's no partial success. Pre-check with:
```bash
curl -G "$$HOST/attask/api/v17.0/optask/<issueID>" \
  --data-urlencode "apiKey=<key>" \
  --data-urlencode "fields=objectCategories:categoryID"
```
…and filter out IDs already in the response before sending.

## Sibling actions

All five sibling actions on `CTGY` use the same dispatch shape (`PUT /ctgy/<action>` with `updates=<JSON>`):

| Action | JSON args | Notes |
|---|---|---|
| `assignCategory` | `objCode, objID, categoryID` | Attach one. Same "already attached" rejection. |
| `assignCategories` | `objCode, objID, categoryIDs` | Attach many. |
| `unassignCategory` | `objCode, objID, categoryID` | Detach one. |
| `unassignCategories` | `objCode, objID, categoryIDs` | Detach many. `{"data":{"result":null}}` on success. |
| `getAttachableCategories` | `searchTerm, catObjCode, excludedIDs, limit` | **Not dispatchable on v17.0** — returns `does not support action getAttachableCategories (CTGY)` for every dispatch shape. Use the discovery query below. |

## Discovering attachable categories (workaround for `getAttachableCategories`)

```bash
curl -G "$$HOST/attask/api/v17.0/ctgy/search" \
  --data-urlencode "apiKey=<key>" \
  --data-urlencode "catObjCode=OPTASK" \
  --data-urlencode "fields=name,catObjCode"
```

`catObjCode` is the object type the form is configured for: `PROJ`, `TASK`, `OPTASK` (Issue), `PORT` (Portfolio), `PROG` (Program), `USER`, etc.

## Primary form vs collection

A custom-form-bearing object has two related but independent assignment slots:

- **`categoryID`** scalar on the object — the *primary* (first/featured) form shown in the Workfront UI. Set with a normal field PUT: `categoryID=<ctgyID>`.
- **`objectCategories`** collection on the object (`OBJCAT` junction rows) — every form attached, including the primary. Modified via `assignCategories` / `unassignCategories` actions (additive/subtractive), or via direct collection PUT (full replace).

`assignCategories` modifies the `objectCategories` collection. It does **not** change which form is the primary. If you want to swap the primary form too, also `PUT /<obj>/<id>` with `categoryID=<newPrimary>`.

## When to use which mechanism

| Goal | Mechanism |
|---|---|
| Add one or more forms without affecting existing ones | `assignCategories` action |
| Remove specific forms | `unassignCategories` action |
| Set the *exact* final set of forms in one call (drop any not in the list) | `PUT /<obj>/<id>` with `updates={"objectCategories":[...]}` (replace) |
| Change the primary (featured) form | `PUT /<obj>/<id>` with `categoryID=<newID>` |
| List forms compatible with an object type | `GET /ctgy/search?catObjCode=<OBJCODE>` |
