# 19 — Rich text fields (Draft.js)

A Workfront custom field of type rich text does not store HTML. It stores a **Draft.js document as
JSON**, and the API hands it to you as a **string containing that JSON**, nested inside
`parameterValues`. Two layers of encoding, which is the first thing that trips people up.

This is the format `workfront-fusion` means when it says raw HTML cannot be written to a rich-text
field. There is no HTML conversion in the platform: you build the Draft.js structure yourself, or
you use Fusion's `Draft.js` tool modules (`HTML to Draft.js`, `Draft.js to HTML`), which exist
precisely because this is tedious by hand. See `../fusion/15-module-index.md` § Draft.js.

## Reading

```bash
bash skills/_shared/scripts/wf-env-curl.sh \
  "/attask/api/v22.0/PROJ/<id>" --data-urlencode "fields=parameterValues"
```

The value at `parameterValues["DE:Field with rich text"]` is a **string**. Parse it, then walk
`blocks`:

```javascript
const doc = JSON.parse(parameterValues["DE:Field with rich text"]);
const plainText = doc.blocks.map(b => b.text).join("\n");
```

Each element of `blocks` is one line. There is no single field holding the whole text, so plain-text
extraction is always this join. Field length limits and text-mode `valuefield` references see the
raw JSON string, not the rendered text, which is why a rich-text field looks enormous in a report
and why matching on its contents in a filter does not behave like matching on a plain text field.

## The block structure

```json
{
  "blocks": [
    {
      "key": "dpfce",
      "text": "Bold text and Italics",
      "type": "unstyled",
      "depth": 0,
      "inlineStyleRanges": [
        { "offset": 0,  "length": 9, "style": "BOLD" },
        { "offset": 14, "length": 7, "style": "ITALIC" }
      ],
      "entityRanges": [],
      "data": {}
    }
  ],
  "entityMap": {}
}
```

| Key | Meaning |
|---|---|
| `key` | Unique identifier for the block. Any distinct string works on write; the UI generates random five-character keys. `entityMap` references it. |
| `text` | The line's text content. |
| `type` | `unstyled` for a normal line. List items carry `unordered-list-item` / `ordered-list-item`, but Adobe documents lists as not supported. |
| `depth` | Nesting depth for list items. `0` otherwise. |
| `inlineStyleRanges` | Character-level formatting over `text`. See below. |
| `entityRanges` | Ranges pointing into `entityMap` (hyperlinks and similar). |
| `data` | Block-level metadata. `{}` in practice. |

**`inlineStyleRanges` is character-indexed into that block's own `text`.** `offset` is a
zero-based character index, `length` is a character count, `style` is `BOLD`, `ITALIC` or
`UNDERLINE` (all three supported since the 20.3 release).

**Combined formatting is expressed as overlapping ranges, not a combined style name.** Bold *and*
italic over the same span is two entries with identical `offset` and `length`. There is no
`"BOLD_ITALIC"`.

**`entityMap` is required on write even though it does nothing.** Adobe's own note says entity
functionality is unsupported, but omitting the key makes the request invalid. Send `"entityMap": {}`.

## Writing

Build the object, stringify it, and send it as the parameter value:

```python
import json
doc = {
    "blocks": [
        {"key": "0", "text": "Hello World!!!", "type": "unstyled", "depth": 0,
         "inlineStyleRanges": [{"offset": 6, "length": 5, "style": "BOLD"}],
         "entityRanges": [], "data": {}},
        {"key": "1", "text": "This is my first Rich Text", "type": "unstyled", "depth": 0,
         "inlineStyleRanges": [{"offset": 17, "length": 9, "style": "BOLD"},
                               {"offset": 17, "length": 9, "style": "ITALIC"}],
         "entityRanges": [], "data": {}}
    ],
    "entityMap": {}
}
updates = json.dumps({"DE:Field with rich text": json.dumps(doc)})
```

then `PUT /attask/api/v22.0/PROJ/<id>` with `updates=<that string>`.

**Adobe's published example has broken offsets, and copying it produces silent corruption.** Their
snippet applies `offset: 6, length: 11` to `"Hello World!!!"`, which is 14 characters, so the range
runs six characters past the end; and `offset: 17, length: 26` to a 26-character string. The example
above is corrected: `offset 6, length 5` bolds `World`, and `offset 17, length 9` bolds `Rich Text`.
Always assert `offset + length <= len(text)` before writing. An out-of-range style range does not
error; it renders wrong.

**Adobe's example also uses `/attask/api-internal/`.** Do not copy that. The internal API is
unversioned, unsupported and can change without notice. Use the versioned public path. The rich-text
format itself is identical on both.

## Round-tripping safely

When you are modifying an existing value rather than replacing it, parse, mutate, re-serialize.
Rebuilding a document from plain text throws away every style range and every block key, and the
loss is invisible until someone opens the record.

If the source content is HTML, do not attempt a hand-rolled conversion. Use Fusion's `HTML to
Draft.js` module, or convert with a Draft.js library on the client side. Regex-to-blocks is the
approach that looks fine on the first three test strings and then mangles nested formatting.

## Sources

Adobe Experience League, `AdobeDocs/workfront.en`
`help/quicksilver/wf-api/general/rich-text-field-api.md` (Adobe's own audit stamp: 5/2025). Read
2026-09-17. The offset corrections and the `api-internal` caution are this toolkit's, not Adobe's.
