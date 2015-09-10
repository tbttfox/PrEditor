import re
import blurdev
import blurdev.tools.tool
from blurdev.cores.core import Core
import nuke
from PyQt4.QtGui import QMainWindow, QApplication
from PyQt4.QtCore import Qt


class NukeCore(Core):
    """
    This class is a reimplimentation of the blurdev.cores.core.Core class for running blurdev within Nuke sessions
    """

    def __init__(self, *args, **kargs):
        kargs['objectName'] = 'nuke'
        super(NukeCore, self).__init__(*args, **kargs)
        # Shutdown blurdev when Nuke closes
        if QApplication.instance():
            QApplication.instance().aboutToQuit.connect(self.shutdown)

    def createToolMacro(self, tool, macro=''):
        """
        Overloads the createToolMacro virtual method from the Core class, this will create a macro for the
        Nuke application for the inputed Core tool. Not Supported currently.
        """
        return False

    @property
    def headless(self):
        """ If true, no Qt gui elements should be used because python is running a QCoreApplication. """
        return not nuke.GUI

    def shouldReportException(self, exctype, value, traceback_):
        """ Allow the core to control if the Python Logger shows the ErrorDialog or a email is sent.
        
        Use this to prevent a exception from prompting the user to open the Python Logger, and 
        prevent sending a error email. This is called after parent eventhandler's are called and
        the traceback will still be printed to the logger after this function is run.
        
        This function returns two boolean values, the first controls if a error email should be sent.
        The second controls if the ErrorDialog should be shown.
        
        Args:
            exctype (type): The Exception class.
            value : The Exception instance.
            traceback_ (traceback): The traceback object.
        
        Returns:
            sendEmail: Should the exception be reported in a error email.
            showPrompt: Should the ErrorDialog be shown if the Python Logger isnt already visible.
        """
        if isinstance(value, RuntimeError) and value.message == 'Cancelled':
            return False, False
        return True, True

    def quitQtOnShutdown(self):
        """ Qt should not be closed when the NukeCore has shutdown called
        """
        return False

    # 	def errorCoreText(self):
    # 		"""
    # 		Returns text that is included in the error email for the active core. Override in subclasses to provide extra data.
    # 		If a empty string is returned this line will not be shown in the error email.
    # 		"""
    # 		return '<i>Open File:</i> %s' % mxs.maxFilePath + mxs.maxFileName

    def lovebar(self, parent=None):
        if parent == None:
            parent = self.rootWindow()
        from blurdev.tools.toolslovebar import ToolsLoveBar

        hasInstance = ToolsLoveBar._instance != None
        lovebar = ToolsLoveBar.instance(parent)
        if not hasInstance and isinstance(parent, QMainWindow):
            parent.addToolBar(Qt.TopToolBarArea, lovebar)
        return lovebar

    def macroName(self):
        """
        Returns the name to display for the create macro action in treegrunt
        """
        return 'Add to Lovebar...'

    def toolTypes(self):
        """
        Overloads the toolTypes method from the Core class to show tool types that are related to
        Nuke applications
        """
        output = blurdev.tools.tool.ToolType.Nuke
        return output

    def recordToolbarXML(self, pref):
        from blurdev.tools.toolstoolbar import ToolsToolBar

        if ToolsToolBar._instance:
            toolbar = ToolsToolBar._instance
            toolbar.toXml(pref.root())
            child = pref.root().addNode('toolbardialog')
            child.setAttribute('visible', toolbar.isVisible())

    def restoreToolbars(self):
        super(NukeCore, self).restoreToolbars()
        # Restore the toolbar positions if they are visible
        # maya.cmds.windowPref(restoreMainWindowState="startupMainWindowState")

    def showLovebar(self, parent=None):
        self.lovebar(parent=parent).show()

    def showToolbar(self, parent=None):
        self.toolbar(parent=parent).show()

    def shutdownToolbars(self):
        """ Closes the toolbars and save their prefs if they are used
        
        This is abstracted from shutdown, so specific cores can control how they shutdown
        """
        from blurdev.tools.toolstoolbar import ToolsToolBar
        from blurdev.tools.toolslovebar import ToolsLoveBar

        ToolsToolBar.instanceShutdown()
        ToolsLoveBar.instanceShutdown()

    def toolbar(self, parent=None):
        if parent == None:
            parent = self.rootWindow()
        from blurdev.tools.toolstoolbar import ToolsToolBar

        hasInstance = ToolsToolBar._instance != None
        toolbar = ToolsToolBar.instance(parent)
        if not hasInstance and isinstance(parent, QMainWindow):
            parent.addToolBar(Qt.TopToolBarArea, toolbar)
        return toolbar

    # Eventually we will overload this to show the logger as a panel.  For now we'll let it be a floating window.
    # def showLogger(self):
    # 	"""
    # 	Creates the python logger and displays it
    # 	"""
