from __future__ import absolute_import, print_function

from . import logger

# Override the base logging class.
logger.patchLogger()

import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402

from Qt.QtCore import Qt  # noqa: E402

from . import osystem  # noqa: E402
from .plugins import Plugins  # noqa: E402
from .version import version as __version__  # noqa: E402,F401

core = None  # create a managed Core instance
"""
The blurdev managed :class:`Core` object from the :mod:`blurdev.cores` module.
"""

# Create the root blurdev module logging object.
_logger = logging.getLogger(__name__)

# Add a NullHandler to suppress the "No handlers could be found for _logger"
# warnings from being printed to stderr. Studiomax and possibly other DCC's
# tend to treat any text written to stderr as a error when running headless.
# We also don't want this warning showing up in production anyway.
_logger.addHandler(logging.NullHandler())

plugins = Plugins()


def init():
    os.environ['BDEV_EMAILINFO_PREDITOR_VERSION'] = __version__
    pythonw_print_bugfix()
    global core
    # create the core
    if not core:
        from .cores.core import Core

        objectName = None
        _exe = os.path.basename(sys.executable).lower()
        # Treat designer as a seperate core so it gets its own prefrences.
        if 'designer' in _exe:
            objectName = 'designer'
        elif 'assfreezer' in _exe:
            objectName = 'assfreezer'
        core = Core(objectName=objectName)

    for plugin in plugins.initialize():
        plugin()


def launch(modal=False, run_workbox=False, app_id=None):
    """Launches the preditor gui creating the QApplication instance if not
    already created.

    Args:
        modal (bool, optional): If True, preditor's gui will be created as a
            modal window (ie. blocks current code execution while its shown).
        run_workbox (bool, optional): After preditor's gui is shown, run its
            current workbox text.
        app_id (str, optional): Set the QApplication's applicationName to this
            value. This is normally only used when launching a standalone
            instance of the PrEditor gui.

    Returns:
        preditor.gui.loggerwindow.LoggerWindow: The instance of the PrEditor
            gui that was created.
    """
    from .gui.app import App
    from .gui.loggerwindow import LoggerWindow

    # Check if we can actually run the PrEditor gui and setup Qt if required
    app = App(name=app_id)
    widget = LoggerWindow.instance(run_workbox=run_workbox)

    # check to see if the tool is running modally and return the result
    if modal:
        widget.exec_()
    else:
        widget.show()
        # If the instance was already shown, raise it to the top and make
        # it regain focus.
        widget.raise_()
        widget.setWindowState(
            widget.windowState() & ~Qt.WindowMinimized | Qt.WindowActive
        )
        app.start()

    return widget


def prefPath(relpath, coreName=''):
    # use the core
    if not coreName and core:
        coreName = core.objectName()
    basepath = os.path.join(
        osystem.expandvars(os.environ['BDEV_PATH_PREFS']), 'app_%s/' % coreName
    )
    return os.path.normpath(os.path.join(basepath, relpath))


def pythonw_print_bugfix():
    """
    When running pythonw print statements and file handles tend to have problems
    so, if its pythonw and stderr and stdout haven't been redirected, redirect them
    to os.devnull.
    """
    if os.path.basename(sys.executable) == 'pythonw.exe':
        if sys.stdout == sys.__stdout__:
            sys.stdout = open(os.devnull, 'w')
        if sys.stderr == sys.__stderr__:
            sys.stderr = open(os.devnull, 'w')


def relativePath(path, additional=''):
    """
    Replaces the last element in the path with the passed in additional path.
    :param path: Source path. Generally a file name.
    :param additional: Additional folder/file path appended to the path.
    :return str: The modified path
    """
    return os.path.join(os.path.dirname(path), additional)


def resourcePath(relpath=''):
    """Returns the full path to the file inside the preditor/resource folder

    Args:
        relpath (str, optional): The additional path added to the
            preditor/resource folder path.

    Returns:
        str: The modified path
    """
    return os.path.join(relativePath(__file__), 'resource', relpath)


def connect_preditor(
    parent, sequence='F2', text='Show PrEditor', obj_name='uiShowPreditorACT'
):
    """Creates a QAction that shows the PrEditor gui with a keyboard shortcut.
    This will automatically call `preditor.stream.install_to_std` if it wasn't
    already called capturing any `sys.stdout` and `sys.stderr` writes after
    this call. This does not initialize the PrEditor gui instance until the
    action is actually called.

    Args:
        parent: The parent widget, normally a window
        sequence (str, optional): A string representing the keyboard shortcut
            associated with the QAction.
        text (str, optional): The display text for the QAction.
        obj_name (str, optional): Set the QAction's objectName to this value.

    Returns:
        QAction: The created QAction
    """
    from Qt.QtGui import QKeySequence
    from Qt.QtWidgets import QAction

    from . import stream

    # Install the stream handlers if not already done.
    stream.install_to_std()

    # Create shortcut for launching the PrEditor gui.
    action = QAction(text, parent)
    action.setObjectName(obj_name)
    action.triggered.connect(show)
    action.setShortcut(QKeySequence(sequence))
    parent.addAction(action)
    return action


def instance(parent=None, run_workbox=False, create=True):
    """Returns the existing instance of the PrEditor gui creating it on first call.

    Args:
        parent (QWidget, optional): If the instance hasn't been created yet, create
            it and parent it to this object.
        run_workbox (bool, optional): If the instance hasn't been created yet, this
            will execute the active workbox's code once fully initialized.
        create (bool, optional): Returns None if the instance has not been created.

    Returns:
        Returns a fully initialized instance of the PrEditor gui. If called more
        than once, the same instance will be returned. If create is False, it may
        return None.
    """
    from .gui.loggerwindow import LoggerWindow

    return LoggerWindow.instance(parent=parent, run_workbox=run_workbox, create=create)


def show(parent=None, run_workbox=False, create=True):
    """Display the main instance of the PrEditor gui, creating if required.
    See `preditor.instance` for more details on the arguments."""
    logger = instance(parent=parent, run_workbox=run_workbox, create=create)
    logger.show()
    logger.activateWindow()
    logger.raise_()
    logger.console().setFocus()


def shutdown():
    """Fully close and cleanup the PrEditor gui if it was created.

    Call this when shutting down your application to ensure any unsaved changes
    to the PrEditor gui are saved and the instance is actually closed instead
    of just hidden.

    If the PrEditor gui was never created, this does nothing so its safe to call
    even if the user never showed the gui. It also won't add extra time creating
    the gui just so it can "save any changes".

    Returns:
        bool: If a shutdown was required
    """
    from .gui.loggerwindow import LoggerWindow

    return LoggerWindow.instance_shutdown()


# initialize the core
init()
