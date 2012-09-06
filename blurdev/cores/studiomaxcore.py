##
# 	\namespace	blurdev.cores.studiomaxcore
#
# 	\remarks	This class is a reimplimentation of the blurdev.cores.core.Core class for running blurdev within Studiomax sessions
#
# 	\author		beta@blur.com
# 	\author		Blur Studio
# 	\date		04/12/10
#

# to be in a 3dsmax session, we need to be able to import the Py3dsMax package
import Py3dsMax
from Py3dsMax import mxs
from blurdev.cores.core import Core

# -------------------------------------------------------------------------------------------------------------

STUDIOMAX_MACRO_TEMPLATE = """
macroscript Blur_%(id)s_Macro
category: "Blur Tools"
toolTip: "%(tooltip)s"
buttonText: "%(displayName)s"
icon:#( "Blur_%(id)s_Macro", 1 )
(
    local blurdev 	= python.import "blurdev"
    blurdev.runTool "%(tool)s" macro:"%(macro)s"
)
"""

# initialize callback scripts
STUDIOMAX_CALLBACK_TEMPLATE = """
global pyblurdev
if ( pyblurdev == undefined ) then ( pyblurdev = python.import "blurdev" )
if ( pyblurdev != undefined ) then ( 
    local ms_args = (callbacks.notificationParam())
    pyblurdev.core.dispatch "%(signal)s" %(args)s 
)
"""


class StudiomaxCore(Core):
    def __init__(self):
        Core.__init__(self)
        self.setObjectName('studiomax')
        self._supportLegacy = False

    def connectAppSignals(self):
        # moved to blur3d
        return

    def allowErrorMessage(self):
        """
            \Remarks	Override this function to disable showing the 'An error has occurred in your Python script.  Would you like to see the log?'
                        messageBox if a error occurs and the LoggerWindow is not open.
            \Return		<bool>
        """
        if mxs.MAXSCRIPTHOST == 1:
            # This is set in startup/blurStartupMaxLib.ms
            # It should signify that max was started with assburner
            return False
        return True

    def connectStudiomaxSignal(self, maxSignal, blurdevSignal, args=''):
        # store the maxscript methods needed
        _n = mxs.pyhelper.namify
        callbacks = mxs.callbacks
        blurdevid = _n('blurdev')

        callbacks.addScript(
            _n(maxSignal),
            STUDIOMAX_CALLBACK_TEMPLATE % {'signal': blurdevSignal, 'args': args},
        )

    def createToolMacro(self, tool, macro=''):
        """
            \remarks	Overloads the createToolMacro virtual method from the Core class, this will create a macro for the
                        Studiomax application for the inputed Core tool
            
            \return		<bool> success
        """
        # create the options for the tool macro to run
        options = {
            'tool': tool.objectName(),
            'displayName': tool.displayName(),
            'macro': macro,
            'tooltip': tool.displayName(),
            'id': str(tool.displayName()).replace(' ', '_').replace('::', '_'),
        }

        # create the macroscript
        filename = mxs.pathConfig.resolvePathSymbols(
            '$usermacros/Blur_%s_Macro.mcr' % options['id']
        )
        f = open(filename, 'w')
        f.write(STUDIOMAX_MACRO_TEMPLATE % options)
        f.close()

        # convert icon files to max standard ...
        from PyQt4.QtCore import Qt, QSize
        from PyQt4.QtGui import QImage

        root = QImage(tool.icon())
        outSize = QSize(24, 24)
        difWidth = root.size().width() - outSize.width()
        difHeight = root.size().height() - outSize.height()
        if difWidth < 0 or difHeight < 0:
            icon24 = root.copy(
                difWidth / 2, difHeight / 2, outSize.width(), outSize.height()
            )
        else:
            icon24 = root.scaled(outSize, Qt.KeepAspectRatio)

        # ... for 24x24 pixels (image & alpha icons)
        basename = mxs.pathConfig.resolvePathSymbols(
            '$usericons/Blur_%s_Macro' % options['id']
        )
        icon24.save(basename + '_24i.bmp')
        icon24.alphaChannel().save(basename + '_24a.bmp')

        # ... and for 16x16 pixels (image & alpha icons)
        icon16 = root.scaled(16, 16)
        icon16.save(basename + '_16i.bmp')
        icon16.alphaChannel().save(basename + '_16a.bmp')

        # run the macroscript & refresh the icons
        mxs.filein(filename)
        mxs.colorman.setIconFolder('.')
        mxs.colorman.setIconFolder('Icons')

        return True

    def disableKeystrokes(self):
        """
            \remarks	[overloaded] disables keystrokes in maxscript
        """
        mxs.enableAccelerators = False

        return Core.disableKeystrokes(self)

    def enableKeystrokes(self):
        """
            \remarks	[overloaded] disables keystrokes in maxscript - max will always try to turn them on
        """
        mxs.enableAccelerators = False

        return Core.enableKeystrokes(self)

    def errorCoreText(self):
        """
            :remarks	Returns text that is included in the error email for the active core. Override in subclasses to provide extra data.
                        If a empty string is returned this line will not be shown in the error email.
            :returns	<str>
        """
        return '<i>Open File:</i> %s' % mxs.maxFilePath + mxs.maxFileName

    def init(self):
        # connect the plugin to 3dsmax
        hInstance = Py3dsMax.GetPluginInstance()
        hwnd = Py3dsMax.GetWindowHandle()

        # create a max plugin connection
        if not self.connectPlugin(hInstance, hwnd):
            from PyQt4.QtGui import QApplication

            # initialize the look for the application instance
            app = QApplication.instance()
            app.setStyle('plastique')

            # we will still need these variables set to work properly
            self.setHwnd(hwnd)
            self._mfcApp = True

            # initialize the logger
            self.logger()

        # init the base class
        return Core.init(self)

    def macroName(self):
        """
            \Remarks	Returns the name to display for the create macro action in treegrunt
        """
        return 'Create Macro...'

    def recordSettings(self):
        pref = self.recordCoreSettings()
        pref.recordProperty('supportLegacy', self._supportLegacy)
        pref.save()

    def restoreSettings(self):
        pref = super(StudiomaxCore, self).restoreSettings()
        self.setSupportLegacy(pref.restoreProperty('supportLegacy', False))

    def registerPaths(self):
        from blurdev.tools import ToolsEnvironment

        env = ToolsEnvironment.activeEnvironment()

        # update the old blur maxscript library system
        envname = env.legacyName()

        # update the old library system
        if self.supportLegacy():
            blurlib = mxs._blurLibrary
            if blurlib:
                blurlib.setCodePath(envname)
                # update the config.ini file so next time we start from the correct environment.
                import blurdev.ini

                if not envname:
                    envname = env.objectName()
                if envname:
                    blurdev.ini.SetINISetting(
                        blurdev.ini.configFile, 'GLOBALS', 'environment', envname
                    )

        # register standard paths
        return Core.registerPaths(self)

    def runScript(self, filename='', scope=None, argv=None, toolType=None):
        """
            \remarks	[overloaded] handle maxscript script running
        """

        if not filename:
            from PyQt4.QtGui import QApplication, QFileDialog

            # make sure there is a QApplication running
            if QApplication.instance():
                filename = str(
                    QFileDialog.getOpenFileName(
                        None,
                        'Select Script File',
                        '',
                        'Python Files (*.py);;Maxscript Files (*.ms);;All Files (*.*)',
                    )
                )
                if not filename:
                    return

        filename = str(filename)

        # run a maxscript file
        import os.path

        if os.path.splitext(filename)[1] in ('.ms', '.mcr'):
            if os.path.exists(filename):
                # try:
                # in max 2012 this would generate a error when processing specific return character of \n which is the linux end line convention.
                # see http://redmine.blur.com/issues/6446 for more details.
                # 	Py3dsMax.runMaxscript(filename)
                # except:
                # 	print 'Except', filename
                return mxs.filein(filename)
            return False

        return Core.runScript(self, filename, scope, argv, toolType)

    def setSupportLegacy(self, state):
        self._supportLegacy = state

    def supportLegacy(self):
        return self._supportLegacy

    def toolTypes(self):
        """
            \remarks	Overloads the toolTypes method from the Core class to show tool types that are related to
                        Studiomax applications
                        
            \return		<blurdev.tools.ToolType>
        """
        from blurdev.tools import ToolsEnvironment, ToolType

        output = ToolType.Studiomax | ToolType.LegacyStudiomax

        return output
