# Static demo (GitHub Pages)

A fully client-side snapshot of the admin graph viewer, published to GitHub
Pages by [`.github/workflows/deploy-demo.yml`](../.github/workflows/deploy-demo.yml).

- `index.html` / `app.js` / `styles.css` — the graph viewer. `app.js` is copied
  from [`admin/graph-viewer/`](../admin/graph-viewer/); when `window.CE_DEMO_BASE`
  is set (see `index.html`), its `apiGet` reads the bundled JSON snapshots below
  instead of calling a live API.
- `data/<tenant>/users.json` — the curated user list per shop.
- `data/<tenant>/<user-slug>/events.json` and `profile.json` — each user's
  recent events and generated profile, captured from a running engine.

Deep links work: `?tenant=<tenantId>&user=<nativeUserId>` opens straight to a
user's view.

## Regenerate the snapshot

With the engine running and the shop data loaded
(`python -m samples.shops.generate load --shop all`):

1. Re-run the capture step that writes `demo/data/**` from the live API, then
2. `cp admin/graph-viewer/app.js admin/graph-viewer/styles.css demo/`

Commit the result; the workflow redeploys on push to `main`.
