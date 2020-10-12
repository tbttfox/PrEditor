""" LoggerWindow class is an overloaded python interpreter for blurdev

"""

import re
import __main__
import os
import sys
import sip
import subprocess
import time
import traceback

from Qt.QtCore import QObject, QPoint, Qt
from Qt.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument
from Qt.QtWidgets import QAction, QApplication, QTextEdit
from Qt import QtCore

import blurdev
from blurdev import debug
from blurdev.debug import BlurExcepthook
from .completer import PythonCompleter
from blurdev.gui.highlighters.codehighlighter import CodeHighlighter
import blurdev.gui.windows.loggerwindow


SafeOutput = None


class Win32ComFix(object):
    pass


# win32com's redirects all sys.stderr output to sys.stdout if the existing sys.stdout is
# not a instance of its SafeOutput Make our logger classes inherit from SafeOutput so
# they don't get replaced by win32com This is only neccissary for Softimage
if blurdev.core.objectName() == 'softimage':
    try:
        from win32com.axscript.client.framework import SafeOutput

        class Win32ComFix(SafeOutput):  # noqa: F811
            pass

    except ImportError:
        pass


class ErrorLog(QObject, Win32ComFix):
    def flush(self):
        """ flush the logger instance """
        pass

    def write(self, msg):
        """ log an error message """
        self.parent().write(msg, error=True)


class ConsoleEdit(QTextEdit, Win32ComFix):
    # Ensure the error prompt only shows up once.
    _errorPrompted = False
    # the color error messages are displayed in, can be set by stylesheets
    _errorMessageColor = QColor(Qt.red)

    _errorPattern = "(?P<full>File \"(?P<filepath>.*\..*)\", line (?P<lineNum>\d+).*)"

    def __init__(self, parent):
        super(QTextEdit, self).__init__(parent)
        # store the error buffer
        self._completer = None

        # create the completer
        self.setCompleter(PythonCompleter(self))

        # sys.__stdout__ doesn't work if some third party has implemented their own
        # override. Use these to backup the current logger so the logger displays
        # output, but application specific consoles also get the info.
        self.stdout = None
        self.stderr = None
        self._errorLog = None
        # overload the sys logger (if we are not on a high debugging level)
        if (
            os.path.basename(sys.executable) != 'python.exe'
            or debug.debugLevel() != debug.DebugLevel.High
        ):
            # Store the current outputs
            self.stdout = sys.stdout
            self.stderr = sys.stderr
            # insert our own outputs
            sys.stdout = self
            sys.stderr = ErrorLog(self)
            self._errorLog = sys.stderr
            BlurExcepthook.install()

        # create the highlighter
        highlight = CodeHighlighter(self)
        highlight.setLanguage('Python')
        self.uiCodeHighlighter = highlight

        # If populated, also write to this interface
        self.outputPipe = None

        self._stdoutColor = QColor(17, 154, 255)
        self._commentColor = QColor(0, 206, 52)
        self._keywordColor = QColor(17, 154, 255)
        self._stringColor = QColor(255, 128, 0)
        self._resultColor = QColor(128, 128, 128)
        # These variables are used to enable pdb mode. This is a special mode used by
        # the logger if it is launched externally via getPdb, set_trace, or post_mortem
        # in blurdev.debug.
        self._pdbPrompt = '(Pdb) '
        self._consolePrompt = '>>> '
        # Note: Changing _outputPrompt may require updating resource\lang\python.xml
        # If still using a #
        self._outputPrompt = '#Result: '
        self._pdbMode = False
        # if populated when setPdbMode is called, this action will be enabled and its
        # check state will match the current pdbMode.
        self.pdbModeAction = None
        # Method used to update the gui when pdb mode changes
        self.pdbUpdateVisibility = None
        # Method used to update the gui when code is executed
        self.reportExecutionTime = None

        self._firstShow = True

        # When executing code, that takes longer than this seconds, flash the window
        self.flashTime = 1.0

        # Store previous commands to retrieve easily
        self._prevCommands = []
        self._prevCommandIndex = 0
        self._prevCommandsMax = 100

        self.uiClearToLastPromptACT = QAction('Clear to Last', self)
        self.uiClearToLastPromptACT.triggered.connect(self.clearToLastPrompt)
        self.uiClearToLastPromptACT.setShortcut(Qt.CTRL | Qt.SHIFT | Qt.Key_Backspace)
        self.addAction(self.uiClearToLastPromptACT)

        self.x = 0
        self.clickPos = None

    def mousePressEvent(self, event):
        """Overload of mousePressEvent to capture click position, so on release, we can
        check release position. If it's the same (ie user clicked vs click-drag to
        select text), we check if user clicked an error hyperlink.
        """
        self.clickPos = event.pos()
        return super(ConsoleEdit, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Overload of mouseReleaseEvent to capture if user has left clicked... Check if
        click position is the same as release position, if so, call errorHyperlink.
        """
        releasePos = event.pos()
        if releasePos == self.clickPos:
            left = event.button() == QtCore.Qt.LeftButton
            if left:
                self.errorHyperlink()

        self.clickPos = None
        return super(ConsoleEdit, self).mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Override of wheelEvent to allow for font resizing by holding ctrl while"""
        # scrolling. If used in LoggerWindow, use that wheel event
        # May not want to import LoggerWindow, so perhaps
        # check by str(type())
        ctrlPressed = event.modifiers() == Qt.ControlModifier
        # if ctrlPressed and isinstance(self.window(), "LoggerWindow"):
        if ctrlPressed and "LoggerWindow" in str(type(self.window())):
            self.window().wheelEvent(event)
        else:
            QTextEdit.wheelEvent(self, event)

    def keyReleaseEvent(self, event):
        """Override of keyReleaseEvent to determine when to end navigation of
            previous commands
            """
        if event.key() == Qt.Key_Alt:
            self._prevCommandIndex = 0
        else:
            event.ignore()

    def errorHyperlink(self):
        """Determine if chosen line is an error traceback file-info line, if so, parse
        the filepath and line number, and attempt to open the module file in the user's
        chosen text editor at the relevant line, using specified Command Prompt pattern.

        The text editor defaults to SublimeText3, in the normal install directory
        """
        # Bail if Error Hyperlinks setting is not turned on.
        if not self.window().uiErrorHyperlinksACT.isChecked():
            return

        # Get current line of text
        cursor = self.textCursor()
        cursor.select(QTextCursor.BlockUnderCursor)
        line = cursor.selectedText()

        # Perform regex search
        match = re.search(self.__class__._errorPattern, line)
        if match is None:
            return
        modulePath = match.group('filepath')
        lineNum = match.group('lineNum')

        # fetch info from LoggerWindow
        exePath = ''
        cmdTempl = ''
        window = self.window()
        if hasattr(window, 'textEditorPath'):
            exePath = window.textEditorPath
            cmdTempl = window.textEditorCmdTempl

        # Bail if not setup properly
        if not exePath:
            print("No text editor path defined.")
            return
        if not os.path.exists(exePath):
            print("Text editor executable does not exist: {}".format(exePath))
            return
        if not cmdTempl:
            print("No text editor Command Prompt command template defined.")
            return
        if not os.path.exists(modulePath):
            print("Specified module path does not exist: {}".format(modulePath))
            return

        # Create command list
        cmdList = cmdTempl.split(" ")
        for i in range(len(cmdList)):
            chunk = cmdList[i]
            chunk = chunk.replace("exePath", exePath)
            chunk = chunk.replace("modulePath", modulePath)
            chunk = chunk.replace("lineNum", lineNum)
            cmdList[i] = chunk

        # Attempt to run command
        try:
            subprocess.Popen(cmdList)
        except WindowsError:
            msg = "The provided text editor command template is not valid:\n    {}"
            msg = msg.format(cmdTempl)
            print(msg)

    def getPrevCommand(self):
        """Find and display the previous command in stack"""
        self._prevCommandIndex -= 1

        if abs(self._prevCommandIndex) > len(self._prevCommands):
            self._prevCommandIndex += 1

        if self._prevCommands:
            self.setCommand()

    def getNextCommand(self):
        """Find and display the next command in stack"""
        self._prevCommandIndex += 1
        self._prevCommandIndex = min(self._prevCommandIndex, 0)

        if self._prevCommands:
            self.setCommand()

    def setCommand(self):
        """Do the displaying of currently chosen command"""
        prevCommand = ''
        if self._prevCommandIndex:
            prevCommand = self._prevCommands[self._prevCommandIndex]

        cursor = self.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        if cursor.selectedText().startswith(self._consolePrompt):
            prevCommand = "{}{}".format(self._consolePrompt, prevCommand)
        cursor.insertText(prevCommand)
        self.setTextCursor(cursor)

    def clear(self):
        """ clears the text in the editor """
        QTextEdit.clear(self)
        self.startInputLine()

    def clearToLastPrompt(self):
        # store the current cursor position so we can restore when we are done
        currentCursor = self.textCursor()
        # move to the end of the document so we can search backwards
        cursor = self.textCursor()
        cursor.movePosition(cursor.End)
        self.setTextCursor(cursor)
        # Check if the last line is a empty prompt. If so, then preform two finds so we
        # find the prompt we are looking for instead of this empty prompt
        findCount = (
            2 if self.toPlainText()[-len(self.prompt()):] == self.prompt() else 1
        )
        for i in range(findCount):
            self.find(self.prompt(), QTextDocument.FindBackward)
        # move to the end of the found line, select the rest of the text and remove it
        # preserving history if there is anything to remove.
        cursor = self.textCursor()
        cursor.movePosition(cursor.EndOfLine)
        cursor.movePosition(cursor.End, cursor.KeepAnchor)
        text = cursor.selectedText()
        if text:
            self.setTextCursor(cursor)
            self.insertPlainText('')
        # Restore the cursor position to its original location
        self.setTextCursor(currentCursor)

    def commentColor(self):
        return self._commentColor

    def setCommentColor(self, color):
        self._commentColor = color

    def completer(self):
        """ returns the completer instance that is associated with this editor """
        return self._completer

    def errorMessageColor(self):
        return self.__class__._errorMessageColor

    def setErrorMessageColor(self, color):
        self.__class__._errorMessageColor = color

    def foregroundColor(self):
        return self._foregroundColor

    def setForegroundColor(self, color):
        self._foregroundColor = color

    def executeString(self, commandText, filename='<ConsoleEdit>'):
        cmdresult = None
        # https://stackoverflow.com/a/29456463
        # If you want to get the result of the code, you have to call eval
        # however eval does not accept multiple statements. For that you need
        # exec which has no Return.
        wasEval = False
        startTime = time.time()
        try:
            compiled = compile(commandText, filename, 'eval')
        except Exception:
            compiled = compile(commandText, filename, 'exec')
            exec(compiled, __main__.__dict__, __main__.__dict__)
        else:
            cmdresult = eval(compiled, __main__.__dict__, __main__.__dict__)
            wasEval = True
        # Provide user feedback when running long code execution.
        delta = time.time() - startTime
        if self.flashTime and delta >= self.flashTime:
            blurdev.core.flashWindow()
        # Report the total time it took to execute this code.
        if self.reportExecutionTime is not None:
            self.reportExecutionTime(delta)
        return cmdresult, wasEval

    def executeCommand(self):
        """ executes the current line of code """
        # grab the command from the line
        block = self.textCursor().block().text()
        p = '{prompt}(.*)'.format(prompt=re.escape(self.prompt()))
        results = re.search(p, block)
        if results:
            commandText = results.groups()[0]
            # if the cursor position is at the end of the line
            if self.textCursor().atEnd():
                # insert a new line
                self.insertPlainText('\n')

                # update prevCommands list, but only if commandText is not the most
                # recent prevCommand, or there are no previous commands
                hasText = len(commandText) > 0
                prevCmds = self._prevCommands
                notPrevCmd = not prevCmds or prevCmds[-1] != commandText
                if hasText and notPrevCmd:
                    self._prevCommands.append(commandText)
                # limit length of prevCommand list to max number of prev commands
                self._prevCommands = self._prevCommands[-1 * self._prevCommandsMax:]

                if self._pdbMode:
                    if commandText:
                        self.pdbSendCommand(commandText)
                    else:
                        # Sending a blank line to pdb will cause it to quit raising a
                        # exception. Most likely the user just wants to add some white
                        # space between their commands, so just add a new prompt line.
                        self.startInputLine()
                        self.insertPlainText(commandText)
                else:
                    # evaluate the command
                    cmdresult, wasEval = self.executeString(commandText)

                    # print the resulting commands
                    if cmdresult is not None:
                        # When writing to additional stdout's not including a new line
                        # makes the output not match the formatting you get inside the
                        # console.
                        self.write(u'{}\n'.format(cmdresult))
                        # NOTE: I am using u'' above so unicode strings in python 2
                        # don't get converted to str objects.

                    self.startInputLine()

            # otherwise, move the command to the end of the line
            else:
                self.startInputLine()
                self.insertPlainText(commandText)

        # if no command, then start a new line
        else:
            self.startInputLine()

    def flush(self):
        pass

    def focusInEvent(self, event):
        """ overload the focus in event to ensure the completer has the proper widget
        """
        if self.completer():
            self.completer().setWidget(self)
        QTextEdit.focusInEvent(self, event)

    def insertCompletion(self, completion):
        """ inserts the completion text into the editor """
        if self.completer().widget() == self:
            cursor = self.textCursor()
            cursor.select(QTextCursor.WordUnderCursor)
            cursor.insertText(completion)
            self.setTextCursor(cursor)

    def insertFromMimeData(self, mimeData):
        html = False
        if mimeData.hasHtml():
            text = mimeData.html()
            html = True
        else:
            text = mimeData.text()

        doc = QTextDocument()

        if html:
            doc.setHtml(text)
        else:
            doc.setPlainText(text)

        text = doc.toPlainText()

        exp = re.compile((
            '[^A-Za-z0-9\~\!\@\#\$\%\^\&\*\(\)\_\+\{\}\|\:'
            '\"\<\>\?\`\-\=\[\]\\\;\'\,\.\/ \t\n]'
        ))
        newText = text.encode('utf-8')
        for each in exp.findall(newText):
            newText = newText.replace(each, '?')

        self.insertPlainText(newText)

    def isatty(self):
        """ Return True if the stream is interactive (i.e., connected to a terminal/tty
            device).
        """
        # This method is required for pytest to run in a DCC. Returns False so the
        # output does not contain cursor control characters that disrupt the visual
        # display of the output.
        return False

    def lastError(self):
        try:
            return ''.join(
                traceback.format_exception(
                    sys.last_type, sys.last_value, sys.last_traceback
                )
            )
        except AttributeError:
            # last_traceback, last_type and last_value do not always exist
            return ''

    def keyPressEvent(self, event):
        """ overload the key press event to handle custom events """

        completer = self.completer()

        if completer and event.key() in (
            Qt.Key_Backspace,
            Qt.Key_Delete,
            Qt.Key_Escape,
        ):
            completer.hideDocumentation()

        # enter || return keys will execute the command
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if completer.popup().isVisible():
                completer.clear()
                event.ignore()
            else:
                self.executeCommand()

        # home key will move the cursor to home
        elif event.key() == Qt.Key_Home:
            self.moveToHome()

        # otherwise, ignore the event for completion events
        elif event.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            if not completer.popup().isVisible():
                # The completer does not get updated if its not visible while typing.
                # We are about to complete the text using it so ensure its updated.
                completer.refreshList(scope=__main__.__dict__)
                completer.popup().setCurrentIndex(
                    completer.completionModel().index(0, 0)
                )
            # Insert the correct text and clear the completion model
            index = completer.popup().currentIndex()
            self.insertCompletion(index.data(Qt.DisplayRole))
            completer.clear()

        elif event.key() == Qt.Key_Escape and completer.popup().isVisible():
            completer.clear()

        # other wise handle the keypress
        else:
            # define special key sequences
            modifiers = QApplication.instance().keyboardModifiers()
            ctrlSpace = event.key() == Qt.Key_Space and modifiers == Qt.ControlModifier
            ctrlM = event.key() == Qt.Key_M and modifiers == Qt.ControlModifier
            ctrlI = event.key() == Qt.Key_I and modifiers == Qt.ControlModifier

            # Process all events we do not want to override
            if not (ctrlSpace or ctrlM or ctrlI):
                QTextEdit.keyPressEvent(self, event)

            window = self.window()
            if ctrlI:
                hasToggleCase = hasattr(window, 'toggleCaseSensitive')
                if hasToggleCase:
                    window.toggleCaseSensitive()
            if ctrlM:
                hasCycleMode = hasattr(window, 'cycleCompleterMode')
                if hasCycleMode:
                    window.cycleCompleterMode()

            # check for particular events for the completion
            if completer:
                # look for documentation popups
                if event.key() == Qt.Key_ParenLeft:
                    rect = self.cursorRect()
                    point = self.mapToGlobal(QPoint(rect.x(), rect.y()))
                    completer.showDocumentation(pos=point, scope=__main__.__dict__)

                # hide documentation popups
                elif event.key() == Qt.Key_ParenRight:
                    completer.hideDocumentation()

                # determine if we need to show the popup or if it already is visible, we
                # need to update it
                elif (
                    event.key() == Qt.Key_Period
                    or event.key() == Qt.Key_Escape
                    or completer.popup().isVisible()
                    or ctrlSpace
                    or ctrlI
                    or ctrlM
                ):
                    completer.refreshList(scope=__main__.__dict__)
                    completer.popup().setCurrentIndex(
                        completer.completionModel().index(0, 0)
                    )

                    # show the completer for the rect
                    rect = self.cursorRect()
                    rect.setWidth(
                        completer.popup().sizeHintForColumn(0)
                        + completer.popup().verticalScrollBar().sizeHint().width()
                    )
                    completer.complete(rect)

    def keywordColor(self):
        return self._keywordColor

    def setKeywordColor(self, color):
        self._keywordColor = color

    def moveToHome(self):
        """ moves the cursor to the home location """
        mode = QTextCursor.MoveAnchor
        # select the home
        if QApplication.instance().keyboardModifiers() == Qt.ShiftModifier:
            mode = QTextCursor.KeepAnchor
        # grab the cursor
        cursor = self.textCursor()
        if QApplication.instance().keyboardModifiers() == Qt.ControlModifier:
            # move to the top of the document if control is pressed
            cursor.movePosition(QTextCursor.Start)
        else:
            # Otherwise just move it to the start of the line
            cursor.movePosition(QTextCursor.StartOfBlock, mode)
        # move the cursor to the end of the prompt.
        cursor.movePosition(QTextCursor.Right, mode, len(self.prompt()))
        self.setTextCursor(cursor)

    def outputPrompt(self):
        """ The prompt used to output a result.
        """
        return self._outputPrompt

    def pdbContinue(self):
        self.pdbSendCommand('continue')

    def pdbDown(self):
        self.pdbSendCommand('down')

    def pdbNext(self):
        self.pdbSendCommand('next')

    def pdbStep(self):
        self.pdbSendCommand('step')

    def pdbUp(self):
        self.pdbSendCommand('up')

    def pdbMode(self):
        return self._pdbMode

    def setPdbMode(self, mode):
        if self.pdbModeAction:
            if not self.pdbModeAction.isEnabled():
                # pdbModeAction is disabled by default, enable the action, so the user
                # can switch between pdb and normal mode any time they want. pdbMode
                # does nothing if this instance of python is not the child process of
                # blurdev.external.External, and the parent process is in pdb mode.
                self.pdbModeAction.blockSignals(True)
                self.pdbModeAction.setChecked(mode)
                self.pdbModeAction.blockSignals(False)
                self.pdbModeAction.setEnabled(True)
        self._pdbMode = mode
        if self.pdbUpdateVisibility:
            self.pdbUpdateVisibility(mode)
        self.startInputLine()

    def pdbSendCommand(self, commandText):
        import blurdev.external

        blurdev.external.External(['pdb', '', {'msg': commandText}])

    def prompt(self):
        if self._pdbMode:
            return self._pdbPrompt
        return self._consolePrompt

    def resultColor(self):
        return self._resultColor

    def setResultColor(self, color):
        self._resultColor = color

    def setCompleter(self, completer):
        """ sets the completer instance for this widget """
        if completer:
            self._completer = completer
            completer.setWidget(self)
            completer.activated.connect(self.insertCompletion)

    def showEvent(self, event):
        # _firstShow is used to ensure the first imput prompt is styled by any active
        # stylesheet
        if self._firstShow:
            self.startInputLine()
            self._firstShow = False
        super(ConsoleEdit, self).showEvent(event)

    def startInputLine(self):
        """ create a new command prompt line """
        self.startPrompt(self.prompt())

    def startPrompt(self, prompt):
        """ create a new command prompt line with the given prompt

        Args:
            prompt(str): The prompt to start the line with. If this prompt
                is already the only text on the last line this function does nothing.
        """
        self.moveCursor(QTextCursor.End)

        # if this is not already a new line
        if self.textCursor().block().text() != prompt:
            charFormat = QTextCharFormat()
            self.setCurrentCharFormat(charFormat)

            inputstr = prompt
            if self.textCursor().block().text():
                inputstr = '\n' + inputstr

            self.insertPlainText(inputstr)

    def startOutputLine(self):
        """ Create a new line to show output text. """
        self.startPrompt(self._outputPrompt)

    def stdoutColor(self):
        return self._stdoutColor

    def setStdoutColor(self, color):
        self._stdoutColor = color

    def stringColor(self):
        return self._stringColor

    def setStringColor(self, color):
        self._stringColor = color

    def write(self, msg, error=False):
        """ write the message to the logger """
        if not sip.isdeleted(self):
            self.moveCursor(QTextCursor.End)

            charFormat = QTextCharFormat()
            if not error:
                charFormat.setForeground(self.stdoutColor())
            else:
                charFormat.setForeground(self.errorMessageColor())
            self.setCurrentCharFormat(charFormat)

            try:
                # If showing Error Hyperlinks, display underline output, otherwise
                # display normal output
                match = re.search(self.__class__._errorPattern, msg)
                if match and self.window().uiErrorHyperlinksACT.isChecked():
                    toUnderline = match.group('full')
                    start = msg.find(toUnderline)

                    # self.setFontUnderline(False)
                    self.insertPlainText(msg[:start])
                    self.setFontUnderline(True)
                    self.insertPlainText(msg[start:])
                    self.setFontUnderline(False)
                else:
                    self.insertPlainText(msg)

            except Exception:
                if SafeOutput:
                    # win32com writes to the debugger if it is unable to print, so
                    # ensure it still does this.
                    SafeOutput.write(self, msg)

        else:
            if SafeOutput:
                # win32com writes to the debugger if it is unable to print, so ensure it
                # still does this.
                SafeOutput.write(self, msg)

        # if a outputPipe was provided, write the message to that pipe
        if self.outputPipe:
            self.outputPipe(msg, error=error)

        # Pass data along to the original stdout
        try:
            if sys.stderr and error:
                self.stderr.write(msg)
            elif self.stdout:
                self.stdout.write(msg)
            else:
                sys.__stdout__.write(msg)
        except Exception:
            pass
