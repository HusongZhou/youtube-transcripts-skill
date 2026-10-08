# Third-party sources

This repository's own source is MIT licensed. Dependencies are downloaded separately by uv; no upstream package source, binaries or virtual environments are bundled.

| Dependency | Source and license | Use |
|---|---|---|
| youtube-transcript-api | [jdepoix/youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api), [MIT](https://github.com/jdepoix/youtube-transcript-api/blob/master/LICENSE) | Available caption tracks, fetch, translation |
| yt-dlp | [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp), [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE) | Enumerate the channel's ordinary videos using its Python API |
| requests | [psf/requests](https://github.com/psf/requests), [Apache-2.0](https://github.com/psf/requests/blob/main/LICENSE) | HTTP timeouts and optional oEmbed metadata |
| uv (external runtime) | [astral-sh/uv](https://github.com/astral-sh/uv), [MIT or Apache-2.0](https://github.com/astral-sh/uv#license) | Isolated script execution and dependency resolution |

yt-dlp's published binaries can include components with other licenses; this package does not redistribute those binaries. Transitive packages carry their own licenses in their distributions.

Fetched video titles and captions belong to their respective sources and are not licensed by this project's MIT license. Tests contain invented short captions. No real third-party transcript is included in the release package.
