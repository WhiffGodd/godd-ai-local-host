import array
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import video_engine as v


class CaptionsTests(unittest.TestCase):
    def test_bounds_and_absolute_times(self):
        srt = v.generate_srt([], 10, [
            {'text': 'before', 'start': 1, 'end': 2},
            {'text': 'hello', 'start': 9, 'end': 11},
            {'text': 'world', 'start': 11, 'end': 20},
            {'text': 'after', 'start': 22, 'end': 23}], 3)
        self.assertEqual(srt, '1\n00:00:00,000 --> 00:00:01,000\nhello\n\n2\n00:00:01,000 --> 00:00:03,000\nworld\n')

    def test_words_keep_speech_timing(self):
        srt = v.generate_srt([{'word': 'Hi!', 'start': 12, 'end': 12.2},
                              {'word': 'Bye!', 'start': 12.3, 'end': 12.5}], 10, clip_duration=3)
        self.assertIn('00:00:02,000 --> 00:00:02,200', srt)
        self.assertIn('00:00:02,300 --> 00:00:02,500', srt)
        self.assertEqual(v.format_srt_timestamp(59.9999), '00:01:00,000')

    def test_original_audio_over_higher_bitrate_dub(self):
        video = {'url': 'video', 'vcodec': 'h264', 'acodec': 'none', 'height': 720}
        original = {'url': 'original', 'vcodec': 'none', 'acodec': 'aac', 'abr': 64, 'format_note': 'English original'}
        dub = {'url': 'dub', 'vcodec': 'none', 'acodec': 'aac', 'abr': 192}
        self.assertEqual(v.select_export_streams({'formats': [video, original, dub]}), ('video', 'original', True))

    def test_source_word_timestamps_are_not_shortened_or_shifted(self):
        from analyzer import generate_word_subtitles_from_segments
        words = generate_word_subtitles_from_segments([
            {'start': 10, 'end': 12, 'text': 'slow speech', 'words': [
                {'word': 'slow', 'start': 10, 'end': 11.2},
                {'word': 'speech', 'start': 11.4, 'end': 12}]}], 10, 12)
        self.assertEqual([(w['start'], w['end']) for w in words], [(10, 11.2), (11.4, 12)])

    def test_partial_youtube_word_timing_preserves_text_and_known_starts(self):
        from analyzer import generate_word_subtitles_from_segments
        segment = {'start': 10, 'end': 12, 'text': 'One two three four', 'words': [
            {'word': 'One', 'start': None, 'end': None},
            {'word': 'two', 'start': 10.4, 'end': 10.75},
            {'word': 'three', 'start': None},
            {'word': 'four', 'start': 11.4, 'end': None},
        ]}
        words = generate_word_subtitles_from_segments([segment], 10, 12)
        self.assertEqual([word['word'] for word in words], ['One', 'two', 'three', 'four'])
        self.assertEqual([word['start'] for word in words], [10, 10.4, 10.9, 11.4])
        self.assertTrue(all(10 <= word['start'] < word['end'] <= 12 for word in words))
        self.assertIsNone(segment['words'][0]['start'])

    def test_estimated_fast_speech_never_runs_beyond_its_segment(self):
        from analyzer import generate_word_subtitles_from_segments
        words = generate_word_subtitles_from_segments([
            {'start': 10, 'end': 10.2, 'text': 'one two three four five six'}], 10, 10.2)
        self.assertTrue(words)
        self.assertLessEqual(max(w['end'] for w in words), 10.2)

    def test_zero_length_recognized_word_is_retained_until_next_anchor(self):
        words = v.speech_words_for_clip([{'end': 1, 'words': [
            {'word': 'like', 'start': .5, 'end': .5},
            {'word': 'this', 'start': .6, 'end': 1.2}]}], 1)
        self.assertEqual(words, [{'word': 'like', 'start': .5, 'end': .6},
                                 {'word': 'this', 'start': .6, 'end': 1}])


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='godd_test_')
        cls.source = str(Path(cls.tmp.name) / 'two_audio.mkv')
        cls.audio = str(Path(cls.tmp.name) / 'separate.mka')
        # Red video and a tone both begin at source t=2. The second audio
        # track is deliberately always audible, so accidental mixing fails.
        subprocess.run([v.FFMPEG_PATH, '-y', '-f', 'lavfi', '-i',
            "color=c=black:s=320x180:r=25:d=4,drawbox=c=red:t=fill:enable='gte(t,2)'",
            '-f', 'lavfi', '-i', "aevalsrc=if(gte(t\\,2)\\,0.3*sin(2*PI*440*t)\\,0):s=48000:d=4",
            '-f', 'lavfi', '-i', 'sine=frequency=880:duration=4:sample_rate=48000',
            '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'libx264',
            '-preset', 'ultrafast', '-c:a', 'pcm_s16le', cls.source], capture_output=True, check=True)
        subprocess.run([v.FFMPEG_PATH, '-y', '-i', cls.source, '-map', '0:a:0',
                        '-c:a', 'copy', cls.audio], capture_output=True, check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def render(self, separate=False, **kwargs):
        formats = [{'url': self.source, 'vcodec': 'h264', 'acodec': 'pcm_s16le', 'height': 180}]
        if separate:
            formats.append({'url': self.audio, 'vcodec': 'none', 'acodec': 'pcm_s16le', 'format_note': 'original'})
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = {'formats': formats}
        out = str(Path(self.tmp.name) / ('separate.mp4' if separate else 'muxed.mp4'))
        with patch.object(v, 'extract_youtube_info', return_value={'formats': formats}), patch.object(v, 'get_video_encoder_flags', return_value=['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '24']):
            kwargs.setdefault('caption_source', 'provided')
            v.download_and_clip_video('test', 1, 2, layout='fit', output_path=out, **kwargs)
        return out

    def test_single_track_and_sync_for_muxed_and_separate_sources(self):
        for separate in (False, True):
            with self.subTest(separate=separate):
                out = self.render(separate, video_subtitles=[{'text': 'SYNC TEST', 'start': 2, 'end': 2.7}])
                probe = subprocess.run([v.FFMPEG_PATH, '-i', out], capture_output=True, text=True).stderr
                self.assertEqual(probe.count('Audio:'), 1)
                pcm = subprocess.run([v.FFMPEG_PATH, '-i', out, '-map', '0:a:0', '-f', 's16le', '-ac', '1', '-ar', '48000', '-'], capture_output=True, check=True).stdout
                samples = array.array('h', pcm)
                onset = next(i for i, sample in enumerate(samples) if abs(sample) > 1000) / 48000
                self.assertAlmostEqual(onset, 1.0, delta=0.05)
                for at, red in ((0.2, False), (1.2, True)):
                    pixel = subprocess.run([v.FFMPEG_PATH, '-ss', str(at), '-i', out,
                        '-vf', 'crop=2:2:540:960', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
                    self.assertEqual(pixel[0] > 150, red)

    def test_whisper_uses_export_audio_and_relative_word_timing(self):
        speech = [{'text': 'Hello', 'start': 0.5, 'end': 1.0,
                   'words': [{'word': 'Hello', 'start': 0.5, 'end': 1.0}]}]
        original = v.generate_srt
        captured = []
        def capture(*args, **kwargs):
            result = original(*args, **kwargs)
            captured.append(result)
            return result
        with patch.object(v, 'transcribe_audio_with_whisper', return_value=speech) as transcribe, patch.object(v, 'generate_srt', side_effect=capture):
            self.render(True, caption_source='auto', subtitles=[{'word': 'WRONG', 'start': 99, 'end': 100}])
        self.assertEqual(transcribe.call_args.args[1], 0.0)
        self.assertEqual(transcribe.call_args.kwargs['audio_stream_url'], str(Path(self.tmp.name) / 'separate.mp4'))
        self.assertIn('00:00:00,500 --> 00:00:01,000', captured[0])
        self.assertNotIn('WRONG', captured[0])
        sidecar = json.loads((Path(self.tmp.name) / 'separate.mp4.captions.json').read_text(encoding='utf-8'))
        self.assertEqual(sidecar['measured_from'], 'rendered_audio')
        self.assertEqual(sidecar['words'][0]['start'], .5)
        self.assertEqual(sidecar['words'][0]['end'], 1.0)

    def test_uploaded_source_never_calls_youtube(self):
        from source_uploads import validate_uploaded_video
        self.assertEqual(validate_uploaded_video(self.source), self.source)
        out = str(Path(self.tmp.name) / 'uploaded.mp4')
        with patch.object(v, 'extract_youtube_info') as extract, patch.object(v, 'get_video_encoder_flags', return_value=['-c:v','libx264','-preset','ultrafast']):
            v.download_and_clip_video('https://youtu.be/blocked',1,2,layout='fit',subtitle_style='off',
                                      output_path=out,local_source_path=self.source)
        extract.assert_not_called()
        self.assertGreater(os.path.getsize(out),1000)

    def test_split_plays_the_detected_facecam_above_gameplay(self):
        source = str(Path(self.tmp.name) / 'facecam-source.mp4')
        out = str(Path(self.tmp.name) / 'facecam-export.mp4')
        subprocess.run([v.FFMPEG_PATH, '-y', '-f', 'lavfi', '-i',
                        "color=blue:s=320x180:d=2,drawbox=x=240:y=110:w=80:h=70:c=red:t=fill,"
                        "drawbox=x=240:y=110:w=80:h=70:c=lime:t=fill:enable='gte(t,0.5)'",
                        '-f', 'lavfi', '-i', 'sine=duration=2', '-c:v', 'libx264', source],
                       capture_output=True, check=True)
        facecam = {'x': 0.75, 'y': 0.62, 'w': 0.25, 'h': 0.38}
        with patch.object(v, 'detect_facecam_in_stream', return_value=facecam), patch.object(
                v, 'get_video_encoder_flags', return_value=['-c:v', 'libx264', '-preset', 'ultrafast']):
            v.download_and_clip_video('test', 0, 1, layout='split', subtitle_style='off',
                                      output_path=out, local_source_path=source)
        for at, y, channel in ((0.2, 380, 0), (0.8, 380, 1), (0.8, 1000, 2)):
            pixel = subprocess.run([v.FFMPEG_PATH, '-ss', str(at), '-i', out,
                                    '-vf', f'crop=2:2:540:{y}', '-frames:v', '1',
                                    '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                   capture_output=True, check=True).stdout
            self.assertGreater(pixel[channel], 200)

    def test_facecam_candidates_ignore_a_full_frame_host(self):
        faces = [(340, 80, 200, 250, .99), (730, 340, 45, 60, .90)]
        self.assertEqual(len(list(v.facecam_candidates(faces, 960, 540))), 1)

    def test_off_skips_recognition(self):
        with patch.object(v, 'transcribe_audio_with_whisper') as transcribe:
            self.render(subtitle_style='off')
        transcribe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
