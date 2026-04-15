import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMdiArea, QMdiSubWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout

app = QApplication(sys.argv)
win = QMainWindow()
mdi = QMdiArea()
win.setCentralWidget(mdi)

widget = QWidget()
lay = QVBoxLayout(widget)
lay.addWidget(QLabel("FINANCE CONTENT"))

sub = QMdiSubWindow()
sub.setWidget(widget)
sub.resize(600, 400)  # Call resize BEFORE setWidget(wrapper)

title_bar = QWidget()
title_bar.setFixedHeight(28)
title_layout = QHBoxLayout(title_bar)
title_layout.addWidget(QLabel("Title Bar"))

wrapper = QWidget()
wrapper_layout = QVBoxLayout(wrapper)
wrapper_layout.setContentsMargins(0, 0, 0, 0)
wrapper_layout.setSpacing(0)
wrapper_layout.addWidget(title_bar)
wrapper_layout.addWidget(widget)

sub.setWidget(wrapper) # overwrites the old widget, might trigger resizeToSizeHint!
mdi.addSubWindow(sub)
sub.show()
win.show()

print("Sub size:", sub.size())
