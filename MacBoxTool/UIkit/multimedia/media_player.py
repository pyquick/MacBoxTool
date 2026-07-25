# coding:utf-8
from PySide2.QtCore import Qt, Signal, QObject, QUrl
from PySide2.QtMultimedia import QMediaPlayer, QMediaContent


class MediaPlayerBase(QObject):
    """ Media player base class """

    mediaStatusChanged = Signal(QMediaPlayer.MediaStatus)
    playbackRateChanged = Signal(float)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    sourceChanged = Signal(QUrl)
    volumeChanged = Signal(int)
    mutedChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def isPlaying(self):
        """ Whether the media is playing """
        raise NotImplementedError

    def mediaStatus(self) -> QMediaPlayer.MediaStatus:
        """ Return the status of the current media stream """
        raise NotImplementedError

    def state(self) -> QMediaPlayer.State:
        """ Return the playback status of the current media stream """
        raise NotImplementedError

    def duration(self):
        """ Returns the duration of the current media in ms """
        raise NotImplementedError

    def position(self):
        """ Returns the current position inside the media being played back in ms """
        raise NotImplementedError

    def volume(self):
        """ Return the volume of player """
        raise NotImplementedError

    def source(self) -> QUrl:
        """ Return the active media source being used """
        raise NotImplementedError

    def pause(self):
        """ Pause playing the current source """
        raise NotImplementedError

    def play(self):
        """ Start or resume playing the current source """
        raise NotImplementedError

    def stop(self):
        """ Stop playing, and reset the play position to the beginning """
        raise NotImplementedError

    def playbackRate(self) -> float:
        """ Return the playback rate of the current media """
        raise NotImplementedError

    def setPosition(self, position: int):
        """ Sets the position of media in ms """
        raise NotImplementedError

    def setSource(self, media: QUrl):
        """ Sets the current source """
        raise NotImplementedError

    def setPlaybackRate(self, rate: float):
        """ Sets the playback rate of player """
        raise NotImplementedError

    def setVolume(self, volume: int):
        """ Sets the volume of player """
        raise NotImplementedError

    def setMuted(self, isMuted: bool):
        raise NotImplementedError

    def videoOutput(self) -> QObject:
        """ Return the video output to be used by the media player """
        raise NotImplementedError

    def setVideoOutput(self, output: QObject) -> None:
        """ Sets the video output to be used by the media player """
        raise NotImplementedError


class MediaPlayer(QMediaPlayer):
    """ Media player - adapted for PySide2/Qt5 QMediaPlayer API """

    # Qt5 QMediaPlayer does not have a sourceChanged signal; we add it
    sourceChanged = Signal(QUrl)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Qt5 QMediaPlayer has integrated audio (no separate QAudioOutput)
        self.setVolume(30)

    def isPlaying(self):
        # Qt5 uses state() instead of playbackState()
        return self.state() == QMediaPlayer.PlayingState

    def volume(self):
        """ Return the volume of player (0-100) """
        return super().volume()

    def setVolume(self, volume: int):
        """ Sets the volume of player """
        if volume == super().volume():
            return

        super().setVolume(volume)
        self.volumeChanged.emit(volume)

    def setMuted(self, isMuted: bool):
        if isMuted == self.isMuted():
            return

        super().setMuted(isMuted)
        self.mutedChanged.emit(isMuted)

    def setSource(self, media: QUrl):
        """ Sets the current source (Qt6-style API, bridges to Qt5 setMedia) """
        self.setMedia(QMediaContent(media))
        self.sourceChanged.emit(media)
