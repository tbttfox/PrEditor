##
# 	\namespace	blurdev
#
# 	\remarks	The blurdev package is the core library methods for tools development at Blur Studio
#
# 	\author		beta@blur.com
# 	\author		Blur Studio
# 	\date		06/11/10
#


# include the blur path
from tools import ToolsEnvironment

# register the standard blur path
ToolsEnvironment.registerPath('c:/blur')

# register the beta blur path as an overload for beta tools
ToolsEnvironment.registerPath('c:/blur/beta')


application = None  # create a managed QApplication
core = None  # create a mangaed Core instance


def activeEnvironment():
    from blurdev.tools import ToolsEnvironment

    return ToolsEnvironment.activeEnvironment()


def findTool(name, environment=''):
    init()

    from tools import ToolsEnvironment

    if not environment:
        env = ToolsEnvironment.activeEnvironment()
    else:
        env = ToolsEnvironment.findEnvironment(environment)

    if env:
        return env.index().findTool(name)

    from tools.tool import Tool

    return Tool()


def init():
    global core

    global application
    if not core:
        # create the core instance
        from blurdev.cores import Core

        # create the core
        core = Core()

        # initialize the application
        application = core.init()


def launch(cls, modal=False, coreName=''):
    """
        \remarks	This method is used to create an instance of a widget (dialog/window) to be run inside
                    the trax system.  Using this function call, trax will determine what the application is
                    and how the window should be instantiated, this way if a tool is run as a standalone, a
                    new application instance will be created, otherwise it will run on top of a currently
                    running application.
        
        \sa			trax.api.tools
        
        \param		cls		QWidget 	(Dialog/Window most commonly>
        
        \return		<bool>	success (when exec_ keyword is set) || <cls> instance (when exec_ keyword is not set)
    """
    init()

    # create the app if necessary
    app = None
    from PyQt4.QtGui import QWizard

    from blurdev.cores.core import Core

    if application:
        application.setStyle('Plastique')

        if coreName:
            core.setObjectName(coreName)

        elif core.objectName() == 'blurdev':
            core.setObjectName('external')

    # always run wizards modally
    if issubclass(cls, QWizard):
        modal = True

    # create the output instance from the class
    widget = cls(None)

    # check to see if the tool is running modally and return the result
    if modal:
        return widget.exec_()
    else:
        widget.show()

        if application:
            application.exec_()

        return widget


def registerScriptPath(filename):
    from tools import ToolsEnvironment

    ToolsEnvironment.registerScriptPath(filename)


def relativePath(path, additional):
    import os.path

    return os.path.join(os.path.split(str(path))[0], additional)


def runTool(toolId, macro=""):
    init()

    # special case scenario - treegrunt
    if toolId == 'Treegrunt':
        core.showTreegrunt()

    # otherwise, run the tool like normal
    else:
        from PyQt4.QtGui import QApplication
        from tools import ToolsEnvironment

        # load the tool
        tool = ToolsEnvironment.activeEnvironment().index().findTool(toolId)
        if not tool.isNull():
            tool.exec_(macro)

        # let the user know the tool could not be found
        elif QApplication.instance():
            from PyQt4.QtGui import QMessageBox

            QMessageBox.critical(
                None,
                'Tool Not Found',
                '%s is not a tool in %s environment.'
                % (toolId, ToolsEnvironment.activeEnvironment().objectName()),
            )


def setActiveEnvironment(env):
    from blurdev.tools import ToolsEnvironment

    return ToolsEnvironment.findEnvironment(env).setActive()


# the blurdev system will create and manage a QApplication instance
init()
