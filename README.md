# ee-seamarks

Estonian official navigation marks as PMTiles vector tiles.

**Source:** [Transpordiamet NMA](https://nma.vta.ee/) (Estonian Transport Administration, Navigation and Maritime Authority)

**License:** CC BY 4.0 — free to use, share, and adapt. Attribution: `© Transpordiamet NMA (CC BY 4.0)`

**Data:** ~1,650 navigation marks (lighthouses, beacons, buoys, spar buoys, leading lines) in Estonian coastal waters and ports. Updated daily from the official registry.

## Format

- PMTiles vector tiles (MBTiles variant)
- Layer: `seamarks`
- Properties: `seamark:type`, `seamark:name`, `seamark:light:character`, `seamark:light:colour`, `seamark:light:period`, `seamark:light:height`, `seamark:light:range`, `ee:id`, `ee:type`
- Zoom: 0–14
- Compatible with [k-yle/OpenSeaMap-vector](https://github.com/k-yle/OpenSeaMap-vector) style layer definitions

## Usage in Aava

The [`pursiapp/aava`](https://github.com/pursiapp/aava) app downloads `ee_seamarks.pmtiles` from the latest GitHub Release and serves it via `SeamarkTileServer` alongside the global OpenSeaMap PMTiles.

## Generation

A GitHub Action runs monthly to:
1. Fetch data from the NMA X-tee SOAP API
2. Convert to GeoJSON
3. Generate PMTiles via tippecanoe
4. Publish to GitHub Release
