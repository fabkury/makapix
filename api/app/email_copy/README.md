# Email copy (docs/localized-text/ D6–D7)

One JSON file per locale, named by its BCP 47 tag (`en.json`, `pt-BR.json`,
`zh-Hans.json`, …). `en.json` is the source of truth and the per-key fallback;
translations are supplied by the app team and dropped in here as-is.
Placeholders (`{handle}`, `{code}`, `{count}`, `{expires}`, `{url}`) must
survive translation. Lookup: exact tag → base language file → English.
