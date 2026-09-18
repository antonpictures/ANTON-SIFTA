"""Web-family conversation typography shared by Qt transcript renderers."""
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextBlockFormat
from System.sifta_desktop_themes import effective_palette


def body_format(px):
    fmt = QTextCharFormat()
    font = QFont('Avenir Next')
    font.setFamilies(['Avenir Next', 'Helvetica Neue', 'Helvetica', 'Arial'])
    font.setPixelSize(px)
    font.setWeight(QFont.Weight.Normal)
    fmt.setFont(font)
    fmt.setForeground(QColor(effective_palette().text_primary))
    return fmt


def refresh_transcript(edit, px, palette):
    """Restyle existing messages while preserving anchors, selection and scroll."""
    edit.document().setDefaultFont(body_format(px).font())
    saved = edit.textCursor()
    scroll = edit.verticalScrollBar().value()
    cursor = QTextCursor(edit.document())
    cursor.beginEditBlock()
    block = edit.document().begin()
    while block.isValid():
        cursor.setPosition(block.position())
        block_fmt = QTextBlockFormat(block.blockFormat())
        block_fmt.clearBackground()
        block_fmt.setLineHeight(155, 1)
        cursor.setBlockFormat(block_fmt)
        fragment = block.begin()
        while not fragment.atEnd():
            run = fragment.fragment()
            if run.isValid():
                fmt = run.charFormat()
                families = fmt.fontFamilies() or []
                if not any(f in families for f in ['Menlo', 'Monaco', 'Consolas']):
                    fmt.setFontFamilies(['Avenir Next', 'Helvetica Neue', 'Helvetica', 'Arial'])
                    font = fmt.font()
                    font.setPixelSize(px)
                    fmt.setFont(font)
                    fmt.clearProperty(QTextCharFormat.Property.TextOutline)
                    fmt.clearBackground()
                    fmt.setForeground(QColor(palette.accent_primary if fmt.isAnchor() else palette.text_primary))
                    cursor.setPosition(run.position())
                    cursor.setPosition(run.position()+run.length(), QTextCursor.MoveMode.KeepAnchor)
                    cursor.setCharFormat(fmt)
            fragment += 1
        block = block.next()
    cursor.endEditBlock()
    edit.setTextCursor(saved)
    edit.verticalScrollBar().setValue(scroll)
