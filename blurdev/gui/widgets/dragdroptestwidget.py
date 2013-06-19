##
# 	:namespace	blurdev.gui.widgets
#
# 	:remarks	Contains classes for generic widget controls
#
# 	:author		beta@blur.com
# 	:author		Blur Studio
# 	:date		07/09/10
#

from PyQt4.QtGui import QTextEdit, QDropEvent
from PyQt4.QtCore import QString, Qt, QMimeData
from xml.sax.saxutils import escape


class DragDropTestWidget(QTextEdit):
    def insertFromMimeData(self, mimeData):
        self.logEvent(mimeData)

    def logEvent(self, event):
        html = []
        if isinstance(event, QDropEvent):
            html.append(
                '<h1>Drop Event</h1><small><b>source:</b></small> %s' % event.source()
            )
            html.append(
                '<small><b>proposed action:</b></small> %s' % event.proposedAction()
            )
            possibleActions = event.possibleActions().__int__()
            html.append('<small><b>possible actions:</b></small> %i' % possibleActions)
            actions = {
                Qt.CopyAction: 'Copy',
                Qt.MoveAction: 'Move',
                Qt.LinkAction: 'Link',
                Qt.ActionMask: 'action Mask',
                Qt.IgnoreAction: 'ignore',
                Qt.TargetMoveAction: 'target move action',
            }
            for key in sorted(actions.keys()):
                if possibleActions & key and key <= possibleActions:
                    html.append(
                        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<small><b>%s</b></small> %i'
                        % (actions[key], key)
                    )
            data = event.mimeData()
        elif isinstance(event, QMimeData):
            html.append('<h1>insertFromMimeData Event</h1><small><b></b></small>')
            data = event
        # Mime Data
        html.append(
            '<hr><h1>Mime Data</h1><small><b>has color:</b></small> %s'
            % data.hasColor()
        )
        html.append('<small><b>has html:</b></small> %s' % data.hasHtml())
        html.append('<small><b>has image:</b></small> %s' % data.hasImage())
        html.append('<small><b>has text:</b></small> %s' % data.hasText())
        html.append('<small><b>has urls:</b></small> %s' % data.hasUrls())
        html.append('<br>')
        html.append('<small><b>text:</b></small> %s' % unicode(data.text()))
        html.append('<small><b>html:</b></small> %s' % escape(unicode(data.html())))
        html.append(
            '<small><b>urls:</b></small><br> %s'
            % '<br>'.join([unicode(url.toString()) for url in data.urls()])
        )
        html.append('<small><b>Additional Formats:</b></small>')
        excludeFormats = set(
            [
                QString('text/plain'),
                QString('text/uri-list'),
                QString('text/html'),
                QString('text/uri-lis'),
                QString('application/x-color'),
            ]
        )
        for f in data.formats():
            if not f in excludeFormats:
                try:
                    html.append(
                        '&nbsp;&nbsp;&nbsp;&nbsp;<small><b>%s: </b></small>%s'
                        % (f, data.data(f))
                    )
                except UnicodeDecodeError:
                    html.append(
                        '&nbsp;&nbsp;&nbsp;&nbsp;<small><b>%s: </b></small><b>UnicodeDecodeError</b>'
                        % f
                    )

        self.setText('<br>'.join(html))

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        self.logEvent(event)

    @staticmethod
    def runTest():
        from blurdev.gui import Dialog
        from PyQt4.QtGui import QVBoxLayout

        dlg = Dialog()
        dlg.setWindowTitle('Drag Drop Test')

        widget = DragDropTestWidget(dlg)

        layout = QVBoxLayout()
        layout.addWidget(widget)
        dlg.setLayout(layout)

        dlg.show()
        return dlg
