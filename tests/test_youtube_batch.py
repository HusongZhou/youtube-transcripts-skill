# /// script
# requires-python = ">=3.12"
# dependencies = ["youtube-transcript-api==1.2.4", "yt-dlp==2026.8.19", "requests>=2.32,<3"]
# ///
import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('batch', ROOT / 'skills/youtube-transcripts/scripts/fetch_videos.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
A, B, C = 'aaaaaaaaaaa', 'bbbbbbbbbbb', 'ccccccccccc'


class Track:
    def __init__(self, language='en', generated=True):
        self.language_code = language
        self.is_generated = generated

    def fetch(self):
        return self

    def to_raw_data(self):
        return [{'text': 'hello 测试', 'start': 1.5, 'duration': 2},
                {'text': 'next paragraph', 'start': 65, 'duration': 1}]


class IpBlocked(Exception):
    pass


class TranscriptsDisabled(Exception):
    pass


class FakeAPI:
    responses = {}
    calls = []

    def __init__(self, **kwargs):
        pass

    def list(self, vid):
        self.calls.append(vid)
        value = self.responses.get(vid, [Track()])
        if isinstance(value, BaseException):
            raise value
        return value


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name) / 'Videos'
        self.addCleanup(self.tmp.cleanup)
        self.queue = [{'id': vid, 'title': 'Title ' + vid} for vid in (A, B, C)]
        self.listings = [{'source': 'https://www.youtube.com/@test/videos', 'scope': 'ordinary videos (/videos)', 'complete': True}]
        FakeAPI.calls = []
        FakeAPI.responses = {}
        self.args = argparse.Namespace(url=['https://www.youtube.com/@test'],
            list_transcripts=False, output=str(self.output), translate='',
            limit=None, language=None, kind='any', force=False, delay=0)

    def run_batch(self):
        with patch.object(m, 'enumerate_videos', return_value=(self.queue, self.listings)), patch.object(m, 'YouTubeTranscriptApi', FakeAPI):
            return m.run(self.args)

    def state(self):
        return json.loads((self.output / 'manifest.json').read_text(encoding='utf-8'))

    def test_success_and_verified_resume(self):
        FakeAPI.responses[B] = [Track('ja')]
        self.assertEqual(self.run_batch(), 0)
        state = self.state()
        self.assertEqual(state['counts'], {'success': 3})
        self.assertEqual(state['records'][B]['language'], 'ja')
        self.assertIn('[00:01:05]', (self.output / state['records'][A]['file']).read_text(encoding='utf-8'))
        FakeAPI.calls.clear()
        self.assertEqual(self.run_batch(), 0)
        self.assertEqual(FakeAPI.calls, [])
        self.assertTrue(all(r['cached'] for r in self.state()['records'].values()))

    def test_no_captions_continue(self):
        FakeAPI.responses[B] = TranscriptsDisabled('No captions')
        self.assertEqual(self.run_batch(), 2)
        self.assertEqual(FakeAPI.calls, [A, B, C])
        self.assertEqual(self.state()['counts'], {'success': 2, 'failed': 1})
        self.assertIn('TranscriptsDisabled', self.state()['records'][B]['reason'])

    def test_ip_block_pauses_then_resumes(self):
        FakeAPI.responses[B] = IpBlocked('Blocked')
        self.assertEqual(self.run_batch(), 2)
        self.assertEqual(FakeAPI.calls, [A, B])
        self.assertEqual(self.state()['counts'], {'success': 1, 'pending': 2})
        self.assertEqual(self.state()['run_state'], 'paused')
        FakeAPI.responses.clear()
        FakeAPI.calls.clear()
        self.assertEqual(self.run_batch(), 0)
        self.assertEqual(FakeAPI.calls, [B, C])

    def test_corrupt_cache_refetched(self):
        self.run_batch()
        (self.output / (B + '.json')).write_text('broken', encoding='utf-8')
        FakeAPI.calls.clear()
        self.assertEqual(self.run_batch(), 0)
        self.assertEqual(FakeAPI.calls, [B])

    def test_requested_language_no_silent_fallback(self):
        self.args.language = ['en']
        FakeAPI.responses[B] = [Track('ja')]
        self.assertEqual(self.run_batch(), 2)
        self.assertEqual(self.state()['records'][B]['status'], 'failed')

    def test_interruption_keeps_remaining_queue(self):
        FakeAPI.responses[B] = KeyboardInterrupt()
        self.assertEqual(self.run_batch(), 2)
        self.assertEqual(self.state()['counts'], {'success': 1, 'pending': 2})
        self.assertEqual(self.state()['run_state'], 'paused')

    def test_listing_failure_is_not_all_success(self):
        self.listings[0]['complete'] = False
        self.listings[0]['error'] = 'Network interruption'
        self.assertEqual(self.run_batch(), 2)
        self.assertEqual(self.state()['run_state'], 'incomplete_listing')

    def test_channel_range_and_list_dedup(self):
        self.assertEqual(m.normalize('https://youtube.com/@test?x=1'), ('channel', 'https://www.youtube.com/@test/videos'))
        with self.assertRaises(ValueError):
            m.normalize('https://youtube.com/@test/shorts')
        with self.assertRaises(ValueError):
            m.normalize('https://example.com/watch?v=' + A)
        data = {'entries': [{'id': A, 'title': 'A'}, {'id': A, 'title': 'Duplicate'}, {'id': B, 'title': 'B'}]}
        with patch.object(m, 'YoutubeDL') as factory:
            client = factory.return_value.__enter__.return_value
            client.extract_info.return_value = data
            queue, listings = m.enumerate_videos([('channel', 'https://www.youtube.com/@test/videos')], None)
        self.assertEqual([v['id'] for v in queue], [A, B])
        self.assertTrue(factory.call_args.args[0]['extract_flat'])
        client.extract_info.assert_called_once_with('https://www.youtube.com/@test/videos', download=False)
        self.assertTrue(listings[0]['complete'])

    def test_library_failure_recorded(self):
        with patch.object(m, 'YoutubeDL') as factory:
            factory.return_value.__enter__.return_value.extract_info.side_effect = RuntimeError('Unavailable')
            queue, listings = m.enumerate_videos([('channel', 'https://www.youtube.com/@test/videos')], 2)
        self.assertEqual(queue, [])
        self.assertFalse(listings[0]['complete'])
        self.assertIn('Unavailable', listings[0]['error'])

    def test_library_limit_and_invalid_entry(self):
        with patch.object(m, 'YoutubeDL') as factory:
            factory.return_value.__enter__.return_value.extract_info.return_value = {
                'entries': [{'id': A}, None, {'id': B}]}
            queue, listings = m.enumerate_videos([('channel', 'https://www.youtube.com/@test/videos'), ('video', A)], 1)
        self.assertEqual(factory.call_args.args[0]['playlistend'], 1)
        self.assertEqual([v['id'] for v in queue], [A])
        self.assertFalse(listings[0]['complete'])

    def test_policy_change_refetches(self):
        self.run_batch()
        FakeAPI.calls.clear()
        self.args.language = ['en']
        self.assertEqual(self.run_batch(), 0)
        self.assertEqual(FakeAPI.calls, [A, B, C])

    def test_manual_track_preferred(self):
        manual, generated = Track('en', False), Track('en', True)
        self.assertIs(m.select_track([generated, manual], None, 'any'), manual)
        self.assertIs(m.select_track([generated, manual], ['en'], 'generated'), generated)


if __name__ == '__main__':
    unittest.main()
