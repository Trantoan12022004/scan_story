"""
Worker thread cào truyện và đăng CMS.
"""
from PySide6.QtCore import QThread, Signal
from typing import Optional
from ban_win.core.story_scraper import StoryScraperEngine

class ScraperWorker(QThread):
    logEmitted = Signal(str)
    progressUpdated = Signal(float, str)
    scrapeFinished = Signal(dict)

    def __init__(self,
                 url: str,
                 output_dir: Optional[str] = None,
                 download_images: bool = False,
                 translate_en: bool = False,
                 publish_cms: bool = False,
                 cms_url: str = "",
                 cms_user: str = "",
                 cms_pass: str = "",
                 start_ch: Optional[int] = None,
                 end_ch: Optional[int] = None,
                 delay: float = 1.0,
                 parent=None):
        super().__init__(parent)
        self.url = url
        self.output_dir = output_dir
        self.download_images = download_images
        self.translate_en = translate_en
        self.publish_cms = publish_cms
        self.cms_url = cms_url
        self.cms_user = cms_user
        self.cms_pass = cms_pass
        self.start_ch = start_ch
        self.end_ch = end_ch
        self.delay = delay
        self._cancelled = False

    def run(self):
        engine = StoryScraperEngine(
            on_log=lambda msg: self.logEmitted.emit(msg),
            on_progress=lambda pct, st: self.progressUpdated.emit(pct, st),
            is_cancelled=lambda: self._cancelled
        )

        res = engine.run(
            url=self.url,
            output_dir=self.output_dir,
            download_images=self.download_images,
            translate_en=self.translate_en,
            publish_cms=self.publish_cms,
            cms_url=self.cms_url,
            cms_user=self.cms_user,
            cms_pass=self.cms_pass,
            start_ch=self.start_ch,
            end_ch=self.end_ch,
            delay=self.delay
        )
        self.scrapeFinished.emit(res)

    def cancel(self):
        self._cancelled = True
