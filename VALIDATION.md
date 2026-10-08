# Validation record

Local release candidate checked on 2026-10-07 (America/Los_Angeles).

| Check | Result |
|---|---|
| Windows 11, Python 3.12.14, uv 0.12.3 | Passed |
| Fresh dedicated uv cache, declared dependency resolution | Passed; no project virtual environment or global package install |
| 12 offline regression tests | Passed in the release directory and in a copied package |
| Skill Creator frontmatter/scaffold validation | Passed |
| Channel root normalization and Python-library enumeration | Live check passed for the first ordinary video of `@AndrejKarpathy` |
| Caption fetch | `EWvNQjAaOHw`: English automatic captions, 3,475 segments; success manifest |
| Copied skill invoked from another working directory | Existing result returned verified cache SKIP |
| Source inspection | No personal absolute paths, APPDATA runtime lookup, .exe entrypoint or PowerShell requirement |
| macOS/Linux | Offline CI configured; not executed locally or remotely yet |
| Completely new Windows machine | Not tested; isolated dependencies on the existing Windows host were tested |
| Automatic natural-language selection in new Codex/Claude sessions | Not yet independently exercised for this release candidate |

Live output and uv caches are outside the release package. Offline tests contain invented captions and mock external clients. The copied-package test confirms independence from the parent repository layout; it does not prove behavior on another operating system.

The core was adapted from an earlier Windows implementation. Existing user-level tools, shared skills, hooks and agent configuration were not replaced.

Before public release: select the repository owner/name and tag, execute the configured CI after upload, and arrange fresh-machine/client trials. MIT was explicitly selected by the user.
