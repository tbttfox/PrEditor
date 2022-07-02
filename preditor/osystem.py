"""
This module provides additional methods that aren't easily found in existing
python or Qt modules for cross-platform usage.

The osystem module provides a number of functions to make dealing with
paths and other platform-specific things in a more abstract platform-agnostic
way.

.. data:: EXTENSION_MAP

   Dictionary of (extension: blurdev_enviroment_variable) pairs used by
   :func:`startfile` to execute scripts and other files.
   This allows blurdev to associate filetypes with executable targets outside
   of the normal windows file association mechanism.

"""

from __future__ import print_function
from __future__ import absolute_import
import os
import sys
import types
import subprocess
from builtins import str as text

import preditor
from . import settings
from .enum import Enum, EnumGroup


def getPointerSize():
    import struct

    try:
        size = struct.calcsize('P')
    except struct.error:
        # Older installations can only query longs
        size = struct.calcsize('l')
    size *= 8
    global getPointerSize

    def getPointerSize():
        return size

    return size


# Get the active version of python, not a hard coded value.
def pythonPath(pyw=False, architecture=None):
    if settings.OS_TYPE != 'Windows':
        return 'python'
    from distutils.sysconfig import get_python_inc

    # Unable to pull the path from the registry just use the current python path
    basepath = os.path.split(get_python_inc())[0]
    # build the path to the python executable. If requested use pythonw instead of
    # python
    return os.path.join(basepath, 'python{w}.exe'.format(w=pyw and 'w' or ''))


EXTENSION_MAP = {}


def app_id_for_shortcut(shortcut):
    """Gets the AppUserModel.ID for the given shortcut.

    This will allow windows to group windows with the same app id on a shortcut pinned
    to the taskbar. Use :py:meth:`preditor.setAppUserModelID` to set the app id for a
    running application.
    """
    if os.path.exists(shortcut):
        # These imports won't work inside python 2 DCC's
        from win32com.propsys import propsys

        # Original info from https://stackoverflow.com/a/61714895
        key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
        store = propsys.SHGetPropertyStoreFromParsingName(shortcut)
        return store.GetValue(key).GetValue()


def defaultLogFile(filename='preditorProtocol.log'):
    """Returns a default log file path often used for redirecting stdout/err to.
    Uses the `BDEV_PATH_BLUR` environment variable as the basepath.

    Args:
        filename (str, optional): filename to log to.
    """
    basepath = expandvars(os.environ['BDEV_PATH_BLUR'])
    return os.path.join(basepath, filename)


def expandvars(text, cache=None):
    """
    Recursively expands the text variables, vs. the os.path.expandvars
    method which only works at one level.

    :param text: text string to expand
    :type text: str
    :param cache: used internally during recursion to prevent infinite loop
    :type cache: dict
    :rtype: str

    """
    # make sure we have data
    if not text:
        return ''

    import re

    # check for circular dependencies
    if cache is None:
        cache = {}

    # return the cleaned variable
    output = str(text)
    keys = re.findall(r'\$(\w+)|\${(\w+)\}|\%(\w+)\%', text)

    for first, second, third in keys:
        repl = ''
        key = ''
        if first:
            repl = '$%s' % first
            key = first
        elif second:
            repl = '${%s}' % second
            key = second
        elif third:
            repl = '%%%s%%' % third
            key = third
        else:
            continue

        value = os.environ.get(key)
        if value:
            if key not in cache:
                cache[key] = value
                value = expandvars(value, cache)
            else:
                print(
                    'WARNING! %s environ variable contains a circular dependency' % key
                )
                value = cache[key]
        else:
            value = repl

        output = output.replace(repl, value)

    return output


def createShortcut(
    title,
    args,
    startin=None,
    target=None,
    icon=None,
    iconFilename=None,
    path=None,
    description='',
    common=1,
    app_id=None,
):
    """Creates a shortcut.

    Windows: If icon is provided it looks for a .ico file with the same name
    as the provided icon.  If it can't find a .ico file it will attempt to
    create one using ImageMagick(http://www.imagemagick.org/).  ImageMagick
    should be installed to the 32bit program files
    (64Bit Windows: C:\\Program Files (x86)\\ImageMagick,
    32Bit Windows: C:\\Program Files\\ImageMagick)

    Args:
        title (str): the title for the shortcut
        args (str): argument string to pass to target command
        startin (str, optional): path where the shortcut should run target command.
            If None(default) then the dirname for the first argument in args is used.
            If args is empty, then the dirname of target is used.
        target (str or None, optional): the target for the shortcut. If None(default)
            this will default to sys.executable.
        icon (str or None, optional): path to the icon the shortcut should use
        path (str or list, optional): path where the shortcut should be created. On
            windows, if a list is passed it must have at least one string in it and the
            list will be passed to os.path.join. The first string in the list will be
            replaced if a key is used. `start menu` is replaced with the path to the
            start menu. `desktop` is replaced with the path to the desktop. If None the
            desktop path is used.
        description (str, optional): helpful description for the shortcut
        common (int, optional): If auto generating the path, this controls if the path
            is generated for the user or shared. 1(default) is the public shared folde,
            while 0 is the users folder. See path to control if the auto-generated path
            is for the desktop or start menu.
        app_id (bool, str or None): whether to set app ID on shortcut or not
    """
    if settings.OS_TYPE == 'Windows':
        import winshell

        if isinstance(path, (list, tuple)):
            base = path[0]
            if base == 'start menu':
                base = os.path.join(winshell.start_menu(common), 'Programs')
            elif base == 'desktop':
                base = winshell.desktop(common)
            # Add the remaining path structure
            path = os.path.join(base, *path[1:])
        elif not path:
            path = winshell.desktop(common)
        # Create any missing folders in the path structure
        if path and not os.path.exists(path):
            os.makedirs(path)

        if not target:
            target = sys.executable
        if not startin:
            # Set the start in directory to the directory of the first args if passed
            # otherwise use the target directory
            if args:
                if isinstance(args, (list, tuple)):
                    startin = os.path.dirname(args[0])
                else:
                    startin = os.path.dirname(args)
            else:
                startin = os.path.dirname(target)

        if icon:
            # On Windows "PROGRAMDATA" for all users, "APPDATA" for per user.
            # See: https://www.microsoft.com/en-us/wdsi/help/folder-variables
            dirname = 'PROGRAMDATA' if 1 == common else 'APPDATA'
            dirname = os.getenv(dirname)
            dirname = os.path.join(dirname, 'blur', 'icons')
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            output = os.path.abspath(
                os.path.join(dirname, (iconFilename or title) + '.ico')
            )
            basename, extension = os.path.splitext(icon)
            ico = basename + '.ico'
            if os.path.exists(ico):
                import shutil

                shutil.copyfile(ico, output)
            else:
                from PIL import Image

                Image.open(icon).save(output)
            icon = output if os.path.exists(output) else None

        shortcut = os.path.join(path, title + '.lnk')
        # If the shortcut description is longer than 260 characters, the target may end
        # up with random unicode characters, and the icon is not set properly. The
        # Properties dialog only shows 259 characters in the description, so we limit
        # the description to 259 characters.
        description = description[:259]

        # If args is a list, convert it to a string using subprocess
        if not isinstance(args, types.StringTypes):
            args = subprocess.list2cmdline(args)
        if icon:
            winshell.CreateShortcut(
                shortcut,
                target,
                Arguments=args,
                StartIn=startin,
                Icon=(icon, 0),
                Description=description,
            )
        else:
            winshell.CreateShortcut(
                shortcut,
                target,
                Arguments=args,
                StartIn=startin,
                Description=description,
            )
        if app_id is True:
            app_id = 'Blur.%s' % title.replace(' ', '')
        if app_id:
            set_app_id_for_shortcut(shortcut, app_id)

        # Attempt to clear the windows icon cache so icon changes are displayed now
        subprocess.Popen(
            ['ie4uinit.exe', '-ClearIconCache'], env=subprocessEnvironment()
        )


def explore(filename, dirFallback=False):
    """Launches the provided filename in the prefered editor for the specific platform.

    Args:
        filename (str): The file path to explore to.
        dirFallback (bool): If True, and the file path does not exist, explore to
            the deepest folder that does exist.

    Returns:
        bool: If it was able to explore the filename.
    """
    # pull the file path from the inputed filename
    fpath = os.path.normpath(filename)

    if dirFallback:
        # If the provided filename does not exist, recursively check each parent folder
        # for existence.
        while not os.path.exists(fpath) and not os.path.ismount(fpath):
            fpath = os.path.split(fpath)[0]

    # run the file in windows
    if settings.OS_TYPE == 'Windows':
        env = subprocessEnvironment()
        if os.path.isfile(fpath):
            subprocess.Popen(r'explorer.exe /select, "{}"'.format(fpath), env=env)
            return True
        subprocess.Popen(r'explorer.exe "{}"'.format(fpath), env=env)
        return True

    # run the file in linux
    elif settings.OS_TYPE == 'Linux':
        cmd = expandvars(os.environ.get('BDEV_CMD_BROWSE', ''))
        if not cmd:
            return False
        subprocess.Popen(cmd % {'filepath': fpath}, shell=True)
        return True
    return False


def set_app_id_for_shortcut(shortcut, app_id):
    """Sets AppUserModel.ID info for a windows shortcut.

    Note: This doesn't seem to work on a pinned taskbar shortcut. Set it on a desktop
    shortcut then pin that shortcut.

    This will allow windows to group windows with the same app id on a shortcut pinned
    to the taskbar. Use :py:meth:`preditor.setAppUserModelID` to set the app id for a
    running application.

    Args:
        shortcut (str): The .lnk filename to set the app id on.
        app_id (str): The app id to set on the shortcut
    """
    if os.path.exists(shortcut):
        # Original info from https://stackoverflow.com/a/61714895

        # These imports won't work inside python 2 DCC's
        import pythoncom
        from win32com.propsys import propsys
        from win32com.shell import shellcon

        key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
        store = propsys.SHGetPropertyStoreFromParsingName(
            shortcut, None, shellcon.GPS_READWRITE, propsys.IID_IPropertyStore
        )

        newValue = propsys.PROPVARIANTType(app_id, pythoncom.VT_BSTR)
        store.SetValue(key, newValue)
        store.Commit()


def subprocessEnvironment(env=None):
    """Returns a copy of the environment that will restore a new python instance to
    current state.

    Provides a environment dict that can be passed to subprocess.Popen that will restore
    the current treegrunt environment settings, and blurdev stylesheet. It also resets
    any environment variables set by a dcc that may cause problems when running a
    subprocess.

    Args:

        env (dict, Optional): The base dictionary that is modified with blurdev
            variables. if None(default) it will be populated with a copy of os.environ.

    Returns:
        dict: A list of environment variables to be passed to subprocess's env argument.
    """
    if env is None:
        env = os.environ.copy()

    # Sets the stylesheet env variable so that launched applications can use it.
    stylesheet = preditor.core.styleSheet()
    if stylesheet:
        env['BDEV_STYLESHEET'] = str(stylesheet)

    # By default libstone adds "C:\Windows\System32\blur64" or "C:\blur\common" to
    # QApplication.libraryPaths(), setting this env var to a invalid path disables that.
    # Leaving this set likely will cause the subprocess to not be configured correctly.
    # The subprocess should be responsible for setting this variable
    if 'LIBSTONE_QT_LIBRARY_PATH' in env:
        del env['LIBSTONE_QT_LIBRARY_PATH']

    # If PYTHONPATH is being used, attempt to reset it to the system value.
    # Applications like maya add PYTHONPATH, and this breaks subprocesses.
    if env.get('PYTHONPATH'):
        if settings.OS_TYPE == 'Windows':
            try:
                # Store the 'PYTHONPATH' from the system registry if set
                env['PYTHONPATH'] = getEnvironmentVariable('PYTHONPATH')
            except WindowsError:
                # If the registry is not set, then remove the variable
                del env['PYTHONPATH']

    # If PYTHONHOME is used, just remove it. This variable is supposed to point
    # to a folder relative to the python stdlib
    # Applications like Houdini add PYTHONHOME, and it breaks the subprocesses
    if env.get('PYTHONHOME'):
        if settings.OS_TYPE == 'Windows':
            try:
                # Store the 'PYTHONHOME' from the system registry if set
                env['PYTHONHOME'] = getEnvironmentVariable('PYTHONHOME')
            except WindowsError:
                # If the registry is not set, then remove the variable
                del env['PYTHONHOME']

    # Some DCC's require inserting or appending path variables. When using subprocess
    # these path variables may cause problems with the target application. This allows
    # removing those path variables from the environment being passed to subprocess.
    def normalize(i):
        return os.path.normpath(os.path.normcase(i))

    removePaths = set([normalize(x) for x in preditor.core._removeFromPATHEnv])

    # blurpath records any paths it adds to the PATH variable and other env variable
    # modifications it makes, revert these changes.
    try:
        import blurpath

        # Restore the original environment variables stored by blurpath.
        blurpath.resetEnvVars(env)  # blurpath v0.0.16 or newer
    except ImportError:
        pass
    except AttributeError:
        # TODO: Once blurpath v0.0.16 or newer is passed out, remove the
        # outter AttributeError except block. Its just for backwards compatibility.
        try:
            removePaths.update([normalize(x) for x in blurpath.addedToPathEnv])
        except AttributeError:
            pass

    path = env.get('PATH')
    if path:
        paths = [
            x for x in path.split(os.path.pathsep) if normalize(x) not in removePaths
        ]
        path = os.path.pathsep.join(paths)
        # subprocess does not accept unicode in python 2
        if sys.version_info[0] == 2 and isinstance(path, text):
            path = path.encode('utf8')
        env['PATH'] = path

    # settings.environStr does nothing in python3, so this code only needs
    # to run in python2
    if sys.version_info[0] < 3:
        # subprocess explodes if it receives unicode in Python2 and in Python3,
        # it explodes if it *doesn't* receive unicode.
        temp = {}
        for k, v in env.items():
            # Attempt to remove any unicode objects. Ignore any conversion failures
            try:
                k = settings.environStr(k)
            except Exception:
                pass
            try:
                v = settings.environStr(v)
            except AttributeError:
                pass
            temp[k] = v
        env = temp

    return env


def startfile(
    filename, debugLevel=None, basePath='', cmd=None, architecture=None, env=None
):
    """Runs the filename.

    Runs the filename in a shell with proper commands given, or passes the command to
    the shell. (CMD in windows) the current platform

    Args:
        filename (str): path to the file to execute

        debugLevel (preditor.debug.DebugLevel or None, optional): If not None(default),
            override for the current value of preditor.debug.debugLevel(). If
            DebugLevel.High, a persistent terminal will be opened allowing you see the
            output in case of a crash.

        basePath (str, optional): working directory where the command should be called
            from.  If None(default), the current working directory is used.

        cmd (str or list or None, optional): This will be passed to subprocess if
            defined. You can use a couple of % formatting keywords. "%(filepath)s" will
            be filled with filename. "%(basepath)s" will be filled with basePath.

        architecture (int or None, optional): 32 or 64 bit. If None use system default.
            Defaults to None

        env (dict, optional): a copy of the environment variables passed to subprocess.
            If not passed subprocessEnvironment is used.

    Returns: bool or subprocess.Popen: In most cases it should return a Popen object.
        However if it can't run filename for some reason it will return False. On
        Windows if it has to resort to calling os.startfile it will return the state of
        that command.
    """
    # determine the debug level
    debug = blurdev.debug

    success = False
    filename = str(filename)

    # make sure that the code we're running
    if not (os.path.isfile(filename) or filename.startswith('http://')):
        return False

    if debugLevel is None:
        debugLevel = debug.debugLevel()

    # determine the base path for the system
    filename = str(filename)
    if not basePath:
        basePath = os.path.split(filename)[0]

    # strip out the information we need
    ext = os.path.splitext(filename)[1]
    if cmd is None:
        if ext in (".py", ".pyw"):
            cmd = (
                pythonPath(pyw=ext == ".pyw", architecture=architecture)
                + ' "%(filepath)s"'
            )
        else:
            cmd = expandvars(os.environ.get(EXTENSION_MAP.get(ext, ''), ''))

    options = {'filepath': filename, 'basepath': basePath}

    def formatCmd(cmd, options, prefix=None):
        if isinstance(cmd, list):
            if prefix:
                cmd = prefix + cmd
            # Do a string format on all items in the list in case they are present.
            return [c % options for c in cmd]
        if prefix:
            cmd = ' '.join(prefix) + ' ' + cmd
        return cmd % options

    # Pass along the current env and blurdev settings
    if env is None:
        env = subprocessEnvironment()

    # if the debug level is high, run the command with a shell in the background
    if ext == '.sh' or debugLevel == debug.DebugLevel.High:
        # run it in debug mode for windows
        if settings.OS_TYPE == 'Windows':
            if ext == '.pyw':
                # make sure .pyw files are opened with python.exe, not pythonw.exe so we
                # can actually debug problems.
                if isinstance(cmd, list):
                    cmd[0] = cmd[0].replace('pythonw.exe', 'python.exe', 1)
                else:
                    cmd = cmd.replace('pythonw.exe', 'python.exe', 1)
            if cmd:
                # NOTE: cmd.exe ignores anything after a newline character.
                cmd = formatCmd(cmd, options, prefix=['cmd.exe', '/k'])
                success = subprocess.Popen(cmd, env=env, cwd=basePath)
            else:
                success = subprocess.Popen(
                    'cmd.exe /k "%s"' % filename, env=env, cwd=basePath
                )

        # run it for Linux systems
        elif settings.OS_TYPE == 'Linux':
            debugcmd = expandvars(os.environ.get('BDEV_CMD_SHELL_DEBUG', ''))

            # if there is a command associated with the inputed file, use that
            if not cmd:
                cmd = expandvars(os.environ.get('BDEV_CMD_SHELL_EXECFILE', ''))

            # create a temp shell file
            temppath = os.environ.get('BDEV_PATH_TEMP', '')
            if not temppath:
                return False

            if not os.path.exists(temppath):
                os.mkdir(temppath)

            # write a temp shell command
            tempfilename = os.path.join(temppath, 'debug.sh')
            tempfile = open(tempfilename, 'w')
            cmd = formatCmd(cmd, options)
            if isinstance(cmd, list):
                cmd = ' '.join(cmd)
            tempfile.write('echo "running command: %s"\n' % cmd)
            tempfile.write(cmd)
            tempfile.close()

            # make sure the system can run the file
            os.system('chmod 0755 %s' % tempfilename)

            # run the file
            options['filepath'] = tempfilename
            # TODO: I don't think this successfully passses the env var to the final
            # command we should probably debug this
            success = subprocess.Popen(debugcmd % options, env=env, shell=True)

        return success
    # otherwise run it directly
    else:
        # run the command in windows
        if settings.OS_TYPE == 'Windows':
            if cmd:
                success = subprocess.Popen(
                    formatCmd(cmd, options), shell=True, cwd=basePath, env=env
                )
            else:
                success = subprocess.Popen(
                    '"%s"' % filename, cwd=basePath, env=env, shell=True
                )
            if not success:
                try:
                    success = os.startfile(filename)
                except Exception:
                    pass

        # in other platforms, we'll use subprocess.Popen
        else:
            if cmd:
                success = subprocess.Popen(formatCmd(cmd, options), env=env, shell=True)
            else:
                # If the provided file is marked as executable just run it.
                if os.access(filename, os.X_OK):
                    success = subprocess.Popen(filename, env=env, shell=True)
                else:
                    cmd = expandvars(os.environ.get('BDEV_CMD_SHELL_EXECFILE', ''))
                    if not cmd:
                        return False
                    success = subprocess.Popen(
                        formatCmd(cmd, options), env=env, shell=True
                    )
    return success


class FlashTime(Enum):
    pass


class FlashTimes(EnumGroup):
    """Windows arguments for preditor.core.flashWindow().

    https://docs.microsoft.com/en-us/windows/desktop/api/winuser/ns-winuser-flashwinfo
    """

    description = 'Stop flashing. The system restores the window to its original state.'
    FLASHW_STOP = FlashTime(0, description=description)
    FLASHW_CAPTION = FlashTime(0x00000001, description='Flash the window caption.')
    FLASHW_TRAY = FlashTime(0x00000002, description='Flash the taskbar button.')
    FLASHW_ALL = FlashTime(
        0x00000003,
        description=(
            'Flash both the window caption and taskbar button. '
            'This is equivalent to setting the FLASHW_CAPTION | FLASHW_TRAY flags.'
        ),
    )
    FLASHW_TIMER = FlashTime(
        0x00000004, description='Flash continuously, until the FLASHW_STOP flag is set.'
    )
    FLASHW_TIMERNOFG = FlashTime(
        0x0000000C,
        description='Flash continuously until the window comes to the foreground.',
    )


# --------------------------------------------------------------------------------
#                               Read registy values
# --------------------------------------------------------------------------------
def getRegKey(registry, key, architecture=None, write=False):
    """Returns a winreg hkey or none.

    Args: registry (str): The registry to look in. 'HKEY_LOCAL_MACHINE' for example

        key (str): The key to open. r'Software\\Autodesk\\Softimage\\InstallPaths' for
            example

        architecture (int | None): 32 or 64 bit. If None use system default.
            Defaults to None

    Returns:
        A winreg handle object
    """
    # Do not want to import winreg unless it is neccissary
    regKey = None
    import winreg

    aReg = winreg.ConnectRegistry(None, getattr(winreg, registry))
    if architecture == 32:
        sam = winreg.KEY_WOW64_32KEY
    elif architecture == 64:
        sam = winreg.KEY_WOW64_64KEY
    else:
        sam = 0
    access = winreg.KEY_READ
    if write:
        access = winreg.KEY_WRITE
    try:
        regKey = winreg.OpenKey(aReg, key, 0, access | sam)
    except WindowsError:
        pass
    return regKey


def registryValue(registry, key, value_name, architecture=None):
    """Returns the value and type of the provided registry key's value name.

    Args:

        registry (str): The registry to look in. 'HKEY_LOCAL_MACHINE' for example

        key (str): The key to open. r'Software\\Autodesk\\Softimage\\InstallPaths' for
            example

        value_name (str): The name of the value to read. To read the '(Default)' key
            pass a empty string.

        architecture (int | None): 32 or 64 bit. If None use system default.
            Defaults to None.

    Returns:
        object: Value stored in key
        int: registry type for value. See winreg's Value Types
    """
    # Do not want to import winreg unless it is neccissary
    regKey = getRegKey(registry, key, architecture=architecture)
    if regKey:
        import winreg

        return winreg.QueryValueEx(regKey, value_name)
    return '', 0


def getEnvironmentRegKey(machine=False):
    """Get the Registry Path and Key for the environment, either of the current
    user or the system.

    Args:
        machine (bool, optional): If True, the system Environment location will
            be returned.  Otherwise, the Environment location for the current
            user will be returned.  Defaults to False.

    Returns:
        tuple: Returns a tuple of two strings (registry path, key).
    """
    registry = 'HKEY_CURRENT_USER'
    key = r'Environment'
    # Replace {PATH} with the existing path variable.
    if machine:
        registry = 'HKEY_LOCAL_MACHINE'
        key = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
    return registry, key


def getEnvironmentVariable(value_name, system=None, default=None, architecture=None):
    """Returns the environment variable stored in the windows registry.

    Args:
        value_name (str): The name of the environment variable to get the value of.
        system (bool or None, optional): If True, then only look in the system
            environment variables. If False, then only look at the user
            environment variables. If None(default), then return the user value
            if set, otherwise return the system value.
        default: If the variable is not set, return this value.
            If None(default) then a WindowsError is raised.
        architecture (int or None): 32 or 64 bit. If None use system default.
            Defaults to None.

    Raises:
        WindowsError: [Error 2] is returned if the environment variable is not
            stored in the requested registry. If you pass a default value other
            than None this will not be raised.
    """
    if system is None and value_name.lower() == 'path':
        msg = "PATH is a special environment variable, set system to True or False."
        raise ValueError(msg)

    if not system:
        # system is None or False, so check user variables.
        registry, key = getEnvironmentRegKey(False)
        try:
            return registryValue(registry, key, value_name, architecture=architecture)[
                0
            ]
        except WindowsError:
            pass
        if system is False:
            # If system is False, then return the default.
            # If None, then check the system.
            if default is None:
                raise
            return default

    registry, key = getEnvironmentRegKey(True)
    try:
        return registryValue(registry, key, value_name, architecture=architecture)[0]
    except WindowsError:
        if default is None:
            raise
        return default
