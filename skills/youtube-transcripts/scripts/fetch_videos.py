# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "youtube-transcript-api==1.2.4",
#   "yt-dlp==2026.8.19",
#   "requests>=2.32,<3",
# ]
# ///
"""Fetch YouTube captions and channel /videos listings without downloading media."""
import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com',
         'youtube-nocookie.com', 'www.youtube-nocookie.com'}


def normalize(value):
    value = value.strip()
    if VIDEO_ID.fullmatch(value):
        return 'video', value
    uri = urlparse(value)
    if uri.scheme not in ('http', 'https') or uri.username or uri.password:
        raise ValueError('Provide a public YouTube URL or video ID.')
    host = uri.hostname
    parts = [unquote(p) for p in uri.path.strip('/').split('/') if p]
    vid = None
    if host in ('youtu.be', 'www.youtu.be') and len(parts) == 1:
        vid = parts[0]
    elif host in HOSTS:
        if parts and parts[0] == 'watch':
            vid = parse_qs(uri.query).get('v', [''])[0]
        elif len(parts) == 2 and parts[0] in ('shorts', 'live', 'embed'):
            vid = parts[1]
        else:
            base_length = 1 if parts and parts[0].startswith('@') else 2
            is_channel = ((base_length == 1 and len(parts[0]) > 1) or
                          (len(parts) >= 2 and parts[0] in ('channel', 'c', 'user')))
            if is_channel and (len(parts) == base_length or
                               (len(parts) == base_length + 1 and parts[-1] == 'videos')):
                return 'channel', 'https://www.youtube.com/' + '/'.join(parts[:base_length]) + '/videos'
    if vid and VIDEO_ID.fullmatch(vid):
        return 'video', vid
    raise ValueError('Only individual videos and channel /videos URLs are supported; not playlists or Shorts/streams tabs.')


def atomic_text(path, content):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(content, encoding='utf-8')
    temp.replace(path)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).replace('|', '\\|')


def stamp(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'


def markdown(meta, snippets):
    lines = [f"# {clean(meta['title'])}", '', f"- url: {meta['url']}",
             f"- video_id: {meta['id']}", f"- channel: {clean(meta.get('channel')) or 'unknown'}",
             f"- upload_date: {meta.get('upload_date') or 'unknown'}",
             f"- language: {meta['language']}", f"- transcript_type: {meta['transcript_type']}",
             f"- translation: {meta.get('translation') or 'none'}", '', '---', '']
    group, start = [], None
    for s in snippets:
        if start is not None and s['start'] - start >= 60:
            lines += [f'[{stamp(start)}] ' + ' '.join(group), '']
            group, start = [], None
        if start is None:
            start = s['start']
        group.append(re.sub(r'\s+', ' ', s['text']).strip())
    if group:
        lines += [f'[{stamp(start)}] ' + ' '.join(group), '']
    return '\n'.join(lines)


def enumerate_videos(sources, limit):
    videos, listings = {}, []
    for kind, source in sources:
        if kind == 'video':
            videos.setdefault(source, {'id': source, 'title': source})
            listings.append({'source': source, 'scope': 'single video', 'complete': True})
            continue
        options = {'extract_flat': True, 'skip_download': True, 'quiet': True,
                   'socket_timeout': 20, 'retries': 1, 'extractor_retries': 1,
                   'ignoreerrors': False, 'lazy_playlist': False}
        if limit:
            options['playlistend'] = limit
        try:
            # The library does not load CLI config or require an installed CLI.
            with YoutubeDL(options) as ydl:
                data = ydl.extract_info(source, download=False)
        except Exception as exc:
            listings.append({'source': source, 'scope': 'ordinary videos (/videos)',
                             'complete': False, 'limit': limit, 'error': type(exc).__name__ + ': ' + str(exc)})
            continue
        listing = {'source': source, 'scope': 'ordinary videos (/videos)',
                   'complete': True, 'limit': limit}
        if not isinstance(data, dict):
            data = {}
            listing.update(complete=False, error='Listing JSON is not an object')
        listing['title'] = data.get('title')
        entries = data.get('entries')
        if not isinstance(entries, list):
            listing.update(complete=False, error='Listing has no valid entries array')
            entries = []
        listing['entries_found'] = len(entries)
        for entry in entries:
            if not isinstance(entry, dict) or not VIDEO_ID.fullmatch(str(entry.get('id', ''))):
                listing.update(complete=False, error='Listing contained an invalid video entry')
                continue
            vid = entry['id']
            videos.setdefault(vid, {'id': vid, 'title': entry.get('title') or vid,
                                   'channel': entry.get('channel') or data.get('channel'),
                                   'upload_date': entry.get('upload_date'),
                                   'duration': entry.get('duration'), 'live_status': entry.get('live_status')})
        listings.append(listing)
    queue = list(videos.values())
    return (queue[:limit] if limit else queue), listings


def select_track(tracks, languages, kind):
    pool = [t for t in tracks if kind == 'any' or t.is_generated == (kind == 'generated')]
    for code in languages or ['en', 'zh-Hans', 'zh-Hant', 'zh']:
        matches = [t for t in pool if t.language_code == code]
        if matches:
            return sorted(matches, key=lambda t: t.is_generated)[0]
    if pool and not languages:
        return sorted(pool, key=lambda t: t.is_generated)[0]
    raise ValueError('No transcript matches the requested language/type.')


def valid_cached(output, record, policy):
    if record.get('status') != 'success' or record.get('policy') != policy:
        return False
    try:
        # Never accept a path outside the output directory from a modified manifest.
        md = (output / record['file']).resolve()
        if md.parent != output.resolve() or not md.is_file():
            return False
        payload = json.loads((output / (record['id'] + '.json')).read_text(encoding='utf-8'))
        snippets = payload['snippets']
        return (payload['metadata']['id'] == record['id'] and
                payload['metadata']['policy'] == policy and isinstance(snippets, list) and
                bool(snippets) and all(isinstance(s.get('text'), str) and
                                      isinstance(s.get('start'), (int, float)) and
                                      isinstance(s.get('duration'), (int, float)) for s in snippets))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def save_manifest(output, state):
    state['updated_at'] = datetime.now(timezone.utc).isoformat()
    current = [state['records'][vid] for vid in state['selected_ids']]
    state['counts'] = dict(Counter(r['status'] for r in current))
    lines = ['# Videos manifest', '', f"Updated: {state['updated_at']}",
             f"Selected videos: {len(current)}; status: {json.dumps(state['counts'])}",
             f"Run state: {state['run_state']}", '', '## Sources', '']
    for listing in state['listings']:
        lines.append(f"- {clean(listing['source'])}; scope: {listing['scope']}; listing complete: {listing['complete']}; limit: {listing.get('limit') or 'none'}")
        if listing.get('error'):
            lines.append(f"  - Listing error: {clean(listing['error'])}")
    if state.get('stop_reason'):
        lines += ['', f"Stop reason: {clean(state['stop_reason'])}"]
    lines += ['', '## Current selection', '', '| Video | Status | Language / Type | Words | File / Reason |',
              '|---|---|---|---|---|']
    for r in current:
        detail = f"[{clean(r['file'])}](<{r['file']}>)" if r.get('status') == 'success' else clean(r.get('reason'))
        label = 'success (cached)' if r.get('cached') else r['status']
        lines.append(f"| [{clean(r['title'])}](https://www.youtube.com/watch?v={r['id']}) | {label} | {clean(r.get('language'))} / {clean(r.get('transcript_type'))} | {r.get('words', '')} | {detail} |")
    earlier = [r for vid, r in state['records'].items() if vid not in state['selected_ids']]
    if earlier:
        lines += ['', '## Earlier selections (not checked in this run)', '',
                  '| Video | Last recorded status | File / Reason |', '|---|---|---|']
        for r in earlier:
            detail = f"[{clean(r['file'])}](<{r['file']}>)" if r.get('status') == 'success' else clean(r.get('reason'))
            lines.append(f"| {clean(r.get('title', r['id']))} | {r['status']} | {detail} |")
    atomic_text(output / 'manifest.json', json_text(state))
    atomic_text(output / 'MANIFEST.md', '\n'.join(lines) + '\n')


class TimeoutSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault('timeout', 20)
        return super().request(*args, **kwargs)


def run(args):
    sources = [normalize(u) for u in args.url]
    if args.list_transcripts:
        if len(sources) != 1 or sources[0][0] != 'video':
            raise ValueError('--list-transcripts requires one video.')
        print(YouTubeTranscriptApi(http_client=TimeoutSession()).list(sources[0][1]))
        return 0
    output = Path(args.output)
    if args.translate:
        output /= 'translated-' + args.translate
    output.mkdir(parents=True, exist_ok=True)
    old = {}
    if (output / 'manifest.json').exists():
        old = json.loads((output / 'manifest.json').read_text(encoding='utf-8')).get('records', {})
    queue, listings = enumerate_videos(sources, args.limit)
    policy = {'languages': args.language, 'kind': args.kind, 'translate': args.translate}
    state = {'schema': 1, 'listings': listings, 'selected_ids': [v['id'] for v in queue],
             'records': old, 'run_state': 'running'}
    for video in queue:
        vid = video['id']
        prior = old.get(vid, {})
        if not args.force and valid_cached(output, prior, policy):
            prior['cached'] = True
        else:
            state['records'][vid] = dict(video, status='pending', policy=policy)
    save_manifest(output, state)
    api = YouTubeTranscriptApi(http_client=TimeoutSession())
    contacted = False
    try:
        for video in queue:
            vid = video['id']
            record = state['records'][vid]
            if record['status'] == 'success':
                print(f'SKIP {vid} (verified cache)', flush=True)
                continue
            if video.get('live_status') in ('is_live', 'is_upcoming'):
                record.update(status='failed', reason='Video is live or upcoming; no completed transcript requested.')
                save_manifest(output, state)
                continue
            if contacted:
                time.sleep(args.delay)
            contacted = True
            try:
                track = None
                for attempt in range(2):
                    try:
                        track = select_track(list(api.list(vid)), args.language, args.kind)
                        snippets = (track.translate(args.translate) if args.translate else track).fetch().to_raw_data()
                        break
                    except (requests.Timeout, requests.ConnectionError):
                        if attempt:
                            raise
                        time.sleep(max(3, args.delay))
                if not snippets:
                    raise ValueError('Transcript is empty.')
                if video['title'] == vid:
                    try:
                        response = requests.get('https://www.youtube.com/oembed', params={'url': f'https://www.youtube.com/watch?v={vid}', 'format': 'json'}, timeout=10)
                        response.raise_for_status()
                        meta = response.json()
                        record.update(title=meta.get('title') or vid, channel=meta.get('author_name'))
                    except (requests.RequestException, ValueError):
                        pass  # ID is an honest fallback, not a fabricated title.
                record.update(url=f'https://www.youtube.com/watch?v={vid}', language=track.language_code,
                              transcript_type='auto' if track.is_generated else 'manual',
                              translation=args.translate, words=len(' '.join(s['text'] for s in snippets).split()),
                              segments=len(snippets), fetched_at=datetime.now(timezone.utc).isoformat())
                slug = re.sub(r'[^\w-]+', '-', record['title'], flags=re.UNICODE).strip('-')[:70] or 'video'
                filename = f'{vid}_{slug}.md'
                atomic_text(output / filename, markdown(record, snippets))
                saved_meta = dict(record, status='success', file=filename, cached=False)
                saved_meta.pop('reason', None)
                atomic_text(output / f'{vid}.json', json_text({'metadata': saved_meta, 'snippets': snippets}))
                record.update(status='success', file=filename, cached=False)
                record.pop('reason', None)
                print(f'OK {vid}: {record["segments"]} segments, {record["language"]}', flush=True)
            except Exception as exc:
                name = type(exc).__name__
                blocked = name in ('IpBlocked', 'RequestBlocked', 'TooManyRequests') or getattr(getattr(exc, 'response', None), 'status_code', None) == 429
                reason = name + ': ' + str(exc).strip()[:1000]
                if blocked:
                    record.update(status='pending', reason=reason)
                    state.update(run_state='paused', stop_reason=reason)
                    print(f'PAUSED {vid}: {name}', flush=True)
                    break
                record.update(status='failed', reason=reason)
                print(f'FAIL {vid}: {name}', flush=True)
            finally:
                save_manifest(output, state)
    except KeyboardInterrupt:
        state.update(run_state='paused', stop_reason='Interrupted; rerun the same command to resume.')
    if state['run_state'] == 'running':
        state['run_state'] = 'complete' if all(l['complete'] for l in listings) else 'incomplete_listing'
    save_manifest(output, state)
    print(json.dumps({'output': str(output.resolve()), 'run_state': state['run_state'], 'counts': state['counts']}, ensure_ascii=False))
    return 0 if state['run_state'] == 'complete' and not state['counts'].get('failed') else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', action='append', required=True)
    parser.add_argument('--language', action='append')
    parser.add_argument('--kind', choices=['any', 'manual', 'generated'], default='any')
    parser.add_argument('--translate', default='')
    parser.add_argument('--output', default='Videos')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--delay', type=float, default=3)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--list-transcripts', action='store_true')
    args = parser.parse_args()
    if args.delay < 0 or (args.limit is not None and args.limit < 1):
        parser.error('Delay must be nonnegative and limit must be positive.')
    for code in (args.language or []) + ([args.translate] if args.translate else []):
        if not re.fullmatch(r'[A-Za-z0-9-]+', code):
            parser.error('Invalid language code.')
    try:
        return run(args)
    except Exception as exc:
        print(f'ERROR {type(exc).__name__}: {exc}')
        return 1


if __name__ == '__main__':
    # UTF-8 files and console output also work on legacy Windows terminals.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(main())
