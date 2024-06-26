import json
import glob
import threading

import pytesseract
from PIL import ImageGrab, ImageOps
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtTextToSpeech import QTextToSpeech
from deep_translator import (GoogleTranslator,
                             PonsTranslator,
                             MyMemoryTranslator,
                             LingueeTranslator)
import pyautogui

locales = open('languageLists/locales.json', 'r')
locales_json = json.load(locales)
locales.close()

mutex = QtCore.QMutex()


def get_locale(lang):
    output = None
    if 'zh' in lang:
        output = lang.replace('-', '_')
    if lang in locales_json:
        output = lang + '_' + locales_json[lang][0]
    return QtCore.QLocale(output)

class Worker(QtCore.QObject):
    finished = QtCore.pyqtSignal()

    def __init__(self, snip_window, image_lang_code, trans_lang_code, is_text2speech_enabled, ui, translator_engine,
                 img_lang, trans_lang):
        super().__init__()
        self.engine = None
        self.x1 = min(snip_window.begin.x(), snip_window.end.x())
        self.y1 = min(snip_window.begin.y(), snip_window.end.y())
        self.x2 = max(snip_window.begin.x(), snip_window.end.x())
        self.y2 = max(snip_window.begin.y(), snip_window.end.y())
        self.image_lang_code = image_lang_code
        self.trans_lang_code = trans_lang_code
        self.is_text2speech_enabled = is_text2speech_enabled
        self.ui = ui
        self.running = True
        self.translator_engine = translator_engine
        self.current_extracted_text = None
        self.img_lang = img_lang.lower()
        self.trans_lang = trans_lang.lower()

    def stop_running(self):
        self.running = False

    def start_running(self):
        self.running = True

    def sstop(self):
        try:
            if self.engine:
                self.engine.stop()
        except AttributeError as e:
            print(f"Unable to stop engine: {e}")

    def run(self):
        while self.running:
            mutex.lock()
            try:
                print(f'enabled: {self.is_text2speech_enabled}')
                img = ImageGrab.grab(bbox=(self.x1, self.y1, self.x2, self.y2))
                img = ImageOps.grayscale(img)

                new_extracted_text = pytesseract.image_to_string(img, lang=self.image_lang_code).strip()
                new_extracted_text = " ".join(new_extracted_text.split())
                print(f"EXTRACTED TEXT: [{new_extracted_text}]")

                if len(new_extracted_text) < 1 or len(new_extracted_text) > 4999:
                    continue

                if self.current_extracted_text != new_extracted_text and new_extracted_text:
                    print(f"Translating: [{new_extracted_text}] of len[{len(new_extracted_text)}]")
                    self.current_extracted_text = new_extracted_text

                    translated_text = ""
                    print(self.img_lang, self.trans_lang)
                    try:
                        if self.translator_engine == "GoogleTranslator":
                            translated_text = GoogleTranslator(source='auto', target=self.trans_lang_code).translate(new_extracted_text)
                        elif self.translator_engine == "PonsTranslator":
                            translated_text = PonsTranslator(source=self.img_lang, target=self.trans_lang).translate(new_extracted_text)
                        elif self.translator_engine == "LingueeTranslator":
                            translated_text = LingueeTranslator(source=self.img_lang, target=self.trans_lang).translate(new_extracted_text)
                        else:
                            translated_text = MyMemoryTranslator(source=self.img_lang, target=self.trans_lang).translate(new_extracted_text)
                        print(f"TRANSLATED TEXT: [{translated_text}]")
                    except Exception as e:
                        print(f"Translation error: {e}")

                    self.ui.translated_text_label.setText(translated_text)
                    if self.is_text2speech_enabled:
                        print('🔊')
                        self.engine = QTextToSpeech(QTextToSpeech.availableEngines()[0])
                        self.engine.setLocale(get_locale(self.trans_lang_code))
                        self.engine.say(translated_text)
            finally:
                mutex.unlock()
        self.finished.emit()

class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        screen_width, screen_height = pyautogui.size()
        self.setGeometry(0, 0, screen_width, screen_height)
        self.setWindowTitle(' ')
        self.begin = QtCore.QPoint()
        self.end = QtCore.QPoint()
        self.setWindowOpacity(0.3)
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.show()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        qp.setPen(QtGui.QPen(QtGui.QColor('black'), 3))
        qp.setBrush(QtGui.QColor(128, 128, 255, 128))
        qp.drawRect(QtCore.QRect(self.begin, self.end))

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.close()

    def closeEvent(self, event):
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.ArrowCursor))

if __name__ == '__main__':
    app = QtWidgets.QApplication([""])
    window = MyWidget()
    QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.CrossCursor))
    window.show()

    # Set up and start the worker thread
    worker = Worker(window, "eng", "de", True, window, "GoogleTranslator", "en", "de")
    thread = QtCore.QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()

    app.aboutToQuit.connect(app.deleteLater)
    app.exec()
