"""
Toast notification helpers using QFluentWidgets InfoBar.
"""
from qfluentwidgets import InfoBar, InfoBarPosition
from PySide6.QtWidgets import QWidget

class Toast:
    @staticmethod
    def success(parent: QWidget, title: str, content: str = "", duration: int = 3000):
        InfoBar.success(
            title=title,
            content=content,
            orient=None,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=parent
        )

    @staticmethod
    def error(parent: QWidget, title: str, content: str = "", duration: int = 4000):
        InfoBar.error(
            title=title,
            content=content,
            orient=None,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=parent
        )

    @staticmethod
    def warning(parent: QWidget, title: str, content: str = "", duration: int = 3500):
        InfoBar.warning(
            title=title,
            content=content,
            orient=None,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=parent
        )

    @staticmethod
    def info(parent: QWidget, title: str, content: str = "", duration: int = 2500):
        InfoBar.info(
            title=title,
            content=content,
            orient=None,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=parent
        )
