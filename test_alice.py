import sys
from PyQt6.QtWidgets import QApplication
from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget
import time

app = QApplication(sys.argv)
w = TalkToAliceWidget()
w.show()

# Simulate STT
w._on_stt_done("What about Pence, this sniff? That sounds a lot of silly, doesn't it, John? And we don't want to go silly, here we go. No, we don't, John. I didn't polish. Go and put the camera up. It takes you, uh, no thing I get to my...", 0.522)

# Run event loop for 3 seconds
from PyQt6.QtCore import QTimer
QTimer.singleShot(3000, app.quit)
app.exec()
