import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from unittest.mock import Mock, patch

from generated_video_store import GeneratedVideoStore
from render_jobs import RenderJobs


class PersistentVideoTests(unittest.TestCase):
    def completed(self, root, lifetime=7*24*3600):
        source=Path(root)/'original.mp4';source.write_bytes(b'example MP4 data')
        manager=RenderJobs(lambda _: (str(source),dict(title='Saved explainer',description='#Shorts',duration=60)),
                           storage_dir=Path(root)/'saved',lifetime=lifetime)
        job=manager.submit(dict(prompt='Explain the circuit'))
        manager.pending.join()
        self.assertEqual(manager.snapshot(job['id'])['state'],'complete')
        return manager,job['id'],source

    def test_completed_video_and_metadata_survive_a_new_manager(self):
        with tempfile.TemporaryDirectory() as root:
            first,token,source=self.completed(root);source.unlink()
            render=Mock(side_effect=AssertionError('Must not regenerate a saved video'))
            restored=RenderJobs(render,storage_dir=Path(root)/'saved',lifetime=7*24*3600)
            status=restored.snapshot(token)
            self.assertEqual(status['metadata']['title'],'Saved explainer')
            self.assertEqual(Path(restored.completed_path(token)).read_bytes(),b'example MP4 data')
            self.assertNotIn('path',status);self.assertNotIn('_generation_payload',status)
            self.assertIsNone(restored.snapshot(token,'different-account'))
            render.assert_not_called()

    def test_interrupted_job_is_restored_as_retryable_failure(self):
        with tempfile.TemporaryDirectory() as root:
            token='a'*32;store=GeneratedVideoStore(root,604800)
            store.save(dict(id=token,state='rendering',owner=None,_generation_payload=dict(prompt='Keep my prompt')))
            renderer=Mock()
            manager=RenderJobs(renderer,storage_dir=root,lifetime=604800)
            status=manager.snapshot(token)
            self.assertEqual(status['state'],'failed');self.assertEqual(status['code'],'GENERATION_INTERRUPTED')
            self.assertIn('prompt is kept',status['error'])
            self.assertEqual(manager.jobs[token]['_generation_payload']['prompt'],'Keep my prompt')
            renderer.assert_not_called()

    def test_failed_generation_does_not_become_a_missing_link_after_restart(self):
        with tempfile.TemporaryDirectory() as root:
            manager=RenderJobs(Mock(side_effect=ValueError('Bad animation plan')),storage_dir=root,lifetime=604800)
            job=manager.submit(dict(prompt='Saved prompt'));manager.pending.join()
            original=manager.snapshot(job['id'])
            restored=RenderJobs(Mock(),storage_dir=root,lifetime=604800)
            self.assertEqual(restored.snapshot(job['id'])['error'],original['error'])
            self.assertEqual(restored.snapshot(job['id'])['state'],'failed')

    def test_wall_clock_retention_survives_restarts_and_exceeds_one_hour(self):
        with tempfile.TemporaryDirectory() as root:
            manager,token,_=self.completed(root)
            current=time.time()
            with patch('generated_video_store.time.time',return_value=current+7200):
                restored=RenderJobs(Mock(),storage_dir=Path(root)/'saved',lifetime=604800)
                self.assertIsNotNone(restored.completed_path(token))
            with patch('generated_video_store.time.time',return_value=current+8*86400):
                expired=RenderJobs(Mock(),storage_dir=Path(root)/'saved',lifetime=604800)
                self.assertIsNone(expired.snapshot(token))
                self.assertFalse((Path(root)/'saved'/(token+'.mp4')).exists())
                self.assertFalse((Path(root)/'saved'/(token+'.json')).exists())

    def test_archived_jobs_do_not_block_more_than_24_generations(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'source.mp4';source.write_bytes(b'video')
            manager=RenderJobs(lambda _:str(source),storage_dir=Path(root)/'saved',lifetime=604800)
            tokens=[]
            for i in range(27):
                job=manager.submit(dict(prompt=str(i)));manager.pending.join();tokens.append(job['id'])
            self.assertLessEqual(len(manager.jobs),24)
            self.assertEqual(manager.snapshot(tokens[0])['state'],'complete')
            self.assertEqual(Path(manager.completed_path(tokens[0])).read_bytes(),b'video')
            restored=RenderJobs(Mock(),storage_dir=Path(root)/'saved',lifetime=604800)
            self.assertEqual(restored.snapshot(tokens[0])['state'],'complete')

    def test_missing_media_restores_as_clear_failure_instead_of_rendering_forever(self):
        with tempfile.TemporaryDirectory() as root:
            manager,token,_=self.completed(root);Path(manager.completed_path(token)).unlink()
            restored=RenderJobs(Mock(),storage_dir=Path(root)/'saved',lifetime=604800)
            self.assertEqual(restored.snapshot(token)['code'],'VIDEO_FILE_MISSING')
            self.assertIsNone(restored.completed_path(token))

    def test_corrupt_records_and_path_traversal_do_not_expose_other_files(self):
        with tempfile.TemporaryDirectory() as root:
            store=GeneratedVideoStore(Path(root)/'saved',604800)
            outside=Path(root)/'secret.mp4';outside.write_bytes(b'private')
            (store.root/('x'*32+'.json')).write_text('invalid JSON',encoding='utf8')
            self.assertIsNone(store.load('../secret'))
            store.delete('../secret')
            self.assertTrue(outside.exists());self.assertEqual(store.restore(),[])
            token='z'*32
            (store.root/(token+'.json')).write_text(json.dumps(dict(id=token,state='complete',saved_at=time.time(),path=str(outside))),encoding='utf8')
            self.assertEqual(store.load(token)['code'],'VIDEO_FILE_MISSING')
            self.assertTrue(outside.exists())

    def test_record_write_failure_keeps_the_original_render_file(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'godd_ai_video_fixture.mp4';source.write_bytes(b'video')
            store=GeneratedVideoStore(Path(root)/'saved',604800);real_replace=__import__('os').replace
            def replace(source,destination):
                if str(destination).endswith('.json'):raise OSError('disk full')
                return real_replace(source,destination)
            with patch('generated_video_store.os.replace',side_effect=replace):
                with self.assertRaises(OSError):store.save(dict(id='b'*32,state='complete',owner=None,path=str(source)))
            self.assertEqual(source.read_bytes(),b'video')

    def test_account_uploads_cannot_store_credentials_in_this_archive(self):
        with tempfile.TemporaryDirectory() as root:
            manager=RenderJobs(Mock(),storage_dir=root)
            with self.assertRaises(ValueError):manager.submit(dict(prompt='Private'),owner='account')
            self.assertEqual(list(Path(root).iterdir()),[])

    def test_restored_http_preview_download_and_youtube_source_work(self):
        import server
        with tempfile.TemporaryDirectory() as root:
            manager,token,_=self.completed(root)
            restored=RenderJobs(Mock(),storage_dir=Path(root)/'saved',lifetime=604800)
            httpd=server.ThreadedHTTPServer(('127.0.0.1',0),server.GoddAIRequestHandler)
            threading.Thread(target=httpd.serve_forever,daemon=True).start()
            base='http://127.0.0.1:'+str(httpd.server_port)
            try:
                with patch.object(server,'AI_VIDEO_JOBS',restored):
                    with urllib.request.urlopen(base+'/api/ai-videos/'+token) as response:
                        self.assertEqual(json.load(response)['state'],'complete')
                    request=urllib.request.Request(base+'/api/ai-videos/'+token+'/video?download=1',headers={'Range':'bytes=8-10'})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status,206);self.assertEqual(response.read(),b'MP4')
                        self.assertIn('attachment',response.headers['Content-Disposition'])
                    exported=Path(server.run_export(dict(generated_video_id=token)))
                    try:self.assertEqual(exported.read_bytes(),b'example MP4 data')
                    finally:exported.unlink(missing_ok=True)
                    for path in ('/api/ai-videos/'+'m'*32,'/.local-data/ai-videos/'+token+'.json'):
                        with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(base+path)
                        self.assertEqual(caught.exception.code,404)
                        if path.startswith('/api/'):
                            self.assertEqual(json.load(caught.exception)['code'],'AI_VIDEO_NOT_FOUND')
            finally:httpd.shutdown();httpd.server_close()


    def test_successful_upload_removes_both_archive_and_publish_copy(self):
        import server
        with tempfile.TemporaryDirectory() as root:
            manager,token,_=self.completed(root)
            archived=Path(manager.completed_path(token));published=Path(root)/'publish.mp4';published.write_bytes(archived.read_bytes())
            with patch.object(server,'AI_VIDEO_JOBS',manager),patch('server.os.scandir',return_value=[]):
                uploads=RenderJobs(lambda _:str(published),publisher=lambda *args:dict(video_id='abcdefghijk',privacy='private'),on_published=server.delete_uploaded_video)
                job=uploads.submit(dict(generated_video_id=token),owner='session');uploads.pending.join()
            self.assertFalse(archived.exists());self.assertFalse(published.exists())
            self.assertTrue(uploads.snapshot(job['id'],'session')['local_copy_deleted'])
            restored=RenderJobs(Mock(),storage_dir=Path(root)/'saved',lifetime=604800)
            self.assertEqual(restored.snapshot(token)['state'],'uploaded')
            self.assertEqual(restored.snapshot(token)['video_id'],'abcdefghijk')
            self.assertIsNone(restored.completed_path(token))

    def test_cleanup_waits_for_thumbnail_and_does_not_repeat_upload_on_thumbnail_error(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'publish.mp4';source.write_bytes(b'video')
            started=threading.Event();release=threading.Event();publisher=Mock(return_value=dict(video_id='abcdefghijk'))
            def thumbnail(*args):
                self.assertTrue(source.is_file());started.set();release.wait(5);return 'Thumbnail unavailable'
            cleanup=Mock(side_effect=lambda *args:source.unlink())
            uploads=RenderJobs(lambda _:str(source),publisher=publisher,thumbnailer=thumbnail,on_published=cleanup)
            job=uploads.submit(dict(thumbnail_time=1),owner='session');uploads.pending.join()
            self.assertTrue(started.wait(2));self.assertTrue(source.exists());cleanup.assert_not_called()
            release.set();uploads.thumbnails.join()
            self.assertFalse(source.exists());publisher.assert_called_once();cleanup.assert_called_once()
            self.assertEqual(uploads.snapshot(job['id'],'session')['state'],'complete')

    def test_failed_upload_keeps_the_video_for_retry(self):
        from api.youtube_upload import YouTubeUploadError
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'publish.mp4';source.write_bytes(b'video');cleanup=Mock()
            uploads=RenderJobs(lambda _:str(source),publisher=Mock(side_effect=YouTubeUploadError('Upload interrupted')),on_published=cleanup)
            job=uploads.submit({},owner='session');uploads.pending.join()
            self.assertTrue(source.is_file());cleanup.assert_not_called()
            self.assertEqual(uploads.snapshot(job['id'],'session')['state'],'failed')


if __name__=='__main__':unittest.main()
