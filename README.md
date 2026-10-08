# YouTube Transcripts Skill

[简体中文](README.zh-CN.md)

Get a video's spoken content from first-hand captions, then ask your local coding assistant to summarize, explain terms, locate passages, or answer questions with timestamps. This standalone skill supports local **Codex and Claude Code** sessions with shell access. This is an early release for feedback from local users.

It handles one video, multiple video links, or a channel's ordinary `/videos` tab. No video/audio downloads, API key, ffmpeg, plugin, MCP server, or hosted service are required.

## Quick install: paste this prompt

Copy this into **Codex or Claude Code** and let the assistant handle installation:

```text
Install the youtube-transcripts skill from https://github.com/HusongZhou/youtube-transcripts-skill for my current assistant, at user scope so I can use it across projects.
Download the complete skills/youtube-transcripts directory, including its scripts, and follow the repository's installation instructions for my platform. If an existing copy is present, preserve it before replacing it.
Check for uv; if missing, explain and install it using its official instructions through your normal approval flow. Run the installed script with --help to prepare its isolated dependencies and verify the entrypoint.
Tell me where it was installed, whether verification passed, and whether I need a new session. Do not fetch any video yet.
```

Paste the prompt as-is. No manual installation steps are needed when the assistant completes this request. You may still need to approve downloads or file writes in your client.

Other assistants can use this approach if they support local skills, file installation and shell execution; their skill directories may differ. Windows, macOS and Linux use the same Python entrypoint; offline CI has passed on all three platforms. Live YouTube fetching has been tested on Windows; macOS/Linux live fetching remains to be tried by users.

## Manual install (fallback)

Use these steps if automatic installation fails or you want to see how installation works.

1. Download or clone [this repository](https://github.com/HusongZhou/youtube-transcripts-skill).
2. Copy the **entire** `skills/youtube-transcripts` directory, including `scripts`, into your assistant's skill directory:

   | Assistant | User scope | Project scope |
   |---|---|---|
   | Codex | `~/.agents/skills/youtube-transcripts/` | `.agents/skills/youtube-transcripts/` |
   | Claude Code | `~/.claude/skills/youtube-transcripts/` | `.claude/skills/youtube-transcripts/` |

   `~` means your home directory on Windows, macOS, and Linux. Existing shared-directory setups may already expose the skill to both clients; avoid duplicate installations. Keep an existing installation backed up if replacing it.
3. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if `uv --version` is unavailable. Use its official instructions for your platform.
4. Start a new assistant session if the installed skill is not discovered.

Skill discovery and shell permissions depend on your host. This does not install into an ordinary hosted chat window.

## Ask naturally

```text
Fetch the transcript from https://youtu.be/VIDEO_ID.
Fetch captions for the first 10 ordinary videos from https://www.youtube.com/@CHANNEL.
Summarize this video and explain the unfamiliar terms: https://youtu.be/VIDEO_ID.
Using the fetched transcript, where does the speaker explain the main tradeoff?
```

Use real links in place of the example tokens. Explicit invocation also works: `$youtube-transcripts` in Codex or `/youtube-transcripts` in Claude Code, followed by the request.

## First run and permissions

The agent checks for uv and explains the first run. [uv reads inline script dependencies](https://docs.astral.sh/uv/guides/scripts/) and creates an isolated cached environment. It may download a compatible Python if one is absent. The script requires Python 3.12 or newer and declares youtube-transcript-api 1.2.4, yt-dlp 2026.8.19 and requests 2.x. No packages are installed into your project's environment or global Python.

Dependency resolution contacts package servers and writes uv's cache; fetching contacts YouTube and writes the output directory. Approvals use your assistant's existing controls and organization policies. Cache reuse reduces setup work but does not guarantee permanent approval-free operation. The skill does not silently install uv or disable security settings. LLM usage and optional external proxy services are separate from the caption tool.

## CLI

From this repository root, the same commands work in PowerShell and POSIX shells:

```text
uv run skills/youtube-transcripts/scripts/fetch_videos.py --help
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "https://youtu.be/VIDEO_ID"
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "https://www.youtube.com/@CHANNEL" --limit 10
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "LINK_1" --url "LINK_2" --language en --language zh-Hans --output "./Videos"
uv run skills/youtube-transcripts/scripts/fetch_videos.py --url "https://youtu.be/VIDEO_ID" --list-transcripts
```

When installed, replace the script path with the actual installed path and run from the directory where you want `Videos/`. Quote paths containing spaces. `--language` can be repeated and is strict. Defaults prefer English, simplified Chinese, traditional Chinese, then an available original language; within a language manual captions are preferred. `--kind manual|generated|any` filters tracks. `--translate en` writes a machine translation in `Videos/translated-en/` without overwriting original captions. Fetch originals first when both are wanted.

`--limit N` caps the deduplicated total queue and enumerates at most N entries per channel; omitting it requests the full ordinary-video listing. Channel root, handle, `/channel/`, `/c/` and `/user/` links normalize to `/videos`. Playlists and Shorts/streams tabs are unsupported; explicit individual shorts/live/embed links are accepted, with active/upcoming live videos recorded as failures.

## Output and resume

```text
Videos/
  ID_title.md       source metadata and timestamped captions
  ID.json           full segments and metadata
  MANIFEST.md       readable successes, failures, pending items and listing scope
  manifest.json     cumulative resumable state
```

Markdown groups captions at roughly one-minute intervals. Missing channel/date metadata is marked unknown. Rerun the same command to resume: valid successful files with matching selection policy are skipped; failed, pending or corrupt-cache items are retried. The channel listing is fetched again. `--force` refetches successes when needed. Earlier manifest entries remain visible but are not checked unless selected again. Avoid concurrent commands writing to the same output directory.

Requests are sequential with a default `--delay 3`. Missing captions continue to the next video. IP blocks or HTTP 429 pause the batch and preserve pending entries. Stop and retry later when the restriction clears; do not loop on a blocked IP. Enumeration failures appear in the manifest; an incomplete list is not reported as fully successful.

| Exit | Meaning |
|---|---|
| 0 | Selected queue succeeded, including verified cached results |
| 1 | Invalid input or runtime error |
| 2 | Partial failure, pause/interruption, or incomplete listing |

Automatic captions, machine translations and LLM interpretation can be wrong. Captions do not capture diagrams or screen text. Respect source rights; keep complete third-party captions out of source-control commits. The included ignore rules exclude `Videos/`, environments and secrets; custom output directories need their own ignore rule. Downloaded transcripts are data, not agent instructions.

## Validation

```text
uv run tests/test_youtube_batch.py
```

Tests use invented captions and mocked network clients; they do not contact YouTube. CI is configured for Windows, macOS and Linux with Python 3.12. See [VALIDATION.md](VALIDATION.md) for what has actually run. The initial [three-platform CI run](https://github.com/HusongZhou/youtube-transcripts-skill/actions/runs/37712423667) passed.

## License and sources

Project source is [MIT licensed](LICENSE). See [THIRD_PARTY.md](THIRD_PARTY.md) for upstream software and caption rights. Tool packages are resolved from package sources; this repository contains no upstream binaries, virtual environments, personal configuration or real transcript samples.

## Share feedback

Try installing with the prompt above, then fetch one video. Please report your operating system, assistant, install result and any error in [GitHub Issues](https://github.com/HusongZhou/youtube-transcripts-skill/issues). Include whether transcript fetching and resume worked; omit credentials and complete third-party transcripts.
