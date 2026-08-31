# Assigning custom forms (categories) via the `assignCategories` action

The custom-form assignment actions are hosted on **`CTGY`** (Category), not on the target object. They take the target via `objCode` + `objID` arguments. The action set covers projects, tasks, issues, portfolios, programs — any object with `catObjCode`.

Verified working v17.0 on a live production tenant, 2026-05-15.

## Working pattern

```bash
# Attach two custom forms to an issue
curl -X PUT "$$HOST/attask/api/v22.0/ctgy/assignCategories?apiKey=<key>" \
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
{"error": {"message": "Categories with the following IDs are already attached: 662c0281...", "code": 0}}
```

There's no partial success. Pre-check with:
```bash
curl -G "$$HOST/attask/api/v22.0/optask/<issueID>" \
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
curl -G "$$HOST/attask/api/v22.0/ctgy/search" \
  --data-urlencode "apiKey=<key>" \
  --data-urlencode "catObjCode=OPTASK" \
  --data-urlencode "fields=name,catObjCode"
```

`catObjCode` is the object type the form is configured for: `PROJ`, `TASK`, `OPTASK` (Issue), `PORT` (Portfolio), `PROG` (Program), `USER`, etc.

## Primary form vs collection

A custom-form-bearing object has two related assignment slots:

- **`categoryID`** scalar on the object — the *primary* (first/featured) form shown in the Workfront UI. Set with a normal field PUT: `categoryID=<ctgyID>`.
- **`objectCategories`** collection on the object (`OBJCAT` junction rows): every form attached, including the primary, each with a `categoryOrder` (0-indexed). Modified via `assignCategories` / `unassignCategories` actions (additive/subtractive), `reorderCategories` (order only), or a direct collection PUT (full replace).

`assignCategories` appends: new forms land after the existing ones and the primary is untouched. Verified on the surveyed sandbox tenant v17.0, 2026-08-27: attaching a fourth form to a three-form issue put it at `categoryOrder` 3 and left `categoryID` alone.

**But the two slots are not independent when order changes.** The form at `categoryOrder` 0 *is* the primary `categoryID`, and writing either one updates the other:

- `reorderCategories` (or a collection-replace PUT) puts its first array entry at position 0, and `categoryID` follows it there.
- `PUT /<obj>/<id>` with `categoryID=<newPrimary>` pulls that form to position 0 and shifts the rest down, preserving their relative order.

So "swap the primary form" and "move a form to the front" are the same operation, and a reorder intended as cosmetic re-points anything filtering on `categoryID`. See `knowledge/custom-forms/09-gotchas.md` § 36.

## When to use which mechanism

| Goal | Mechanism |
|---|---|
| Add one or more forms without affecting existing ones | `assignCategories` action |
| Remove specific forms | `unassignCategories` action |
| Set the *exact* final set of forms in one call (drop any not in the list) | `PUT /<obj>/<id>` with `updates={"objectCategories":[...]}` (replace) |
| Change the order forms render in | `reorderCategories` action. Pass the **complete** attached set, or it 400s |
| Change the primary (featured) form | `PUT /<obj>/<id>` with `categoryID=<newID>` (also moves it to the front) |
| Find every record a form is attached to | `GET /<obj>/search?objectCategories:categoryID=<id>`, **not** `categoryID=`, which finds only records where it is primary |
| List forms compatible with an object type | `GET /ctgy/search?catObjCode=<OBJCODE>` |
