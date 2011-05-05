##
# 	\namespace	blurdev.osystem
#
# 	\remarks	This module provides additional methods that aren't easily found in existing
# 				python or Qt modules for cross-platform usage
#
# 	\author		eric.hulser@blur.com
# 	\author		Blur Studio
# 	\date		04/20/11
#

import os
import subprocess
from blurdev import settings

COMMAND_MAP = {
    'open': ('BDEV_CMD_OPEN', 'xdg-open "%(filepath)s"'),
    'debug': (
        'BDEV_CMD_DEBUG',
        'konsole --noclose --workdir %(basepath)s -e "%(filepath)s"',
    ),
    'console': ('BDEV_CMD_CONSOLE', 'konsole --workdir %(filepath)s'),
    'web': ('BDEV_CMD_WEB', 'firefox %(filepath)s'),
    '.py': ('BDEV_CMD_PYTHON', 'python "%(filepath)s"'),
    '.ui': ('BDEV_CMD_DESIGNER', ''),
}


def console(filename):
    """
        \remarks	starts a console window at the given path
        \param		filename	<str>
        \return		<bool> success
    """
    # pull the filpath from the inputed filename
    fpath = str(filename)
    if not os.path.isdir(fpath):
        fpath = os.path.split(fpath)[0]

    # run the file in windows
    subprocess.Popen(
        os.environ.get(*COMMAND_MAP['console']) % {'filepath': fpath}, shell=True
    )


def explore(filename):
    """
        \remarks	launches the filename given the current platform
        \param		filename	<str>
        \return		<bool> success
    """
    # pull the filpath from the inputed filename
    fpath = str(filename)
    if not os.path.isdir(fpath):
        fpath = os.path.split(fpath)[0]

    # run the file in windows
    if settings.OS_TYPE == 'Windows':
        return os.startfile(fpath)

    # run the file in linux
    elif settings.OS_TYPE == 'Linux':
        subprocess.Popen(
            os.environ.get(*COMMAND_MAP['open']) % {'filepath': fpath}, shell=True
        )


def startfile(filename, debugLevel=None, basePath=''):
    """
        \remarks	runs the filename in a shell with proper commands given
                    the current platform
        \param		filename	<str>
        \param		debugLevel	<blurdev.debug.DebugLevel>
        \param		basePath	<str>
        \return		<bool> success
    """
    # determine the debug level
    import os
    from blurdev import debug
    from PyQt4.QtCore import QProcess
    import subprocess

    success = False
    filename = str(filename)
    if not (os.path.isfile(filename) or filename.startswith('http://')):
        return False

    if debugLevel == None:
        debugLevel = debug.debugLevel()

    # determine the base path for the system
    filename = str(filename)
    if not basePath:
        basePath = os.path.split(filename)[0]

    # strip out the information we need
    ext = os.path.splitext(filename)[1]
    if not ext and filename.startswith('http://'):
        ext = 'web'

    cmd = os.environ.get(*COMMAND_MAP.get(ext, ('BDEV_MISSING_EXTENSION', '')))
    options = {'filepath': filename, 'basepath': basePath}

    # if the debug level is high, run the command with a shell in the background
    if debugLevel == debug.DebugLevel.High:
        # run it in debug mode for windows
        if settings.OS_TYPE == 'Windows':
            if cmd:
                success, value = QProcess.startDetached(
                    'cmd.exe', ['/k', '%s "%s"' % (cmd, filename)], basePath
                )
            else:
                success, value = QProcess.startDetached(
                    'cmd.exe', ['/k', filename], basePath
                )

        # run it for Linux systems
        elif settings.OS_TYPE == 'Linux':
            debugcmd = os.environ.get(*COMMAND_MAP['debug'])

            # if there is a command associated with the inputed file, use that
            if not cmd:
                cmd = os.environ.get(*COMMAND_MAP['open'])

            # create a temp shell file
            temppath = os.environ.get('BDEV_TEMP_PATH', '')
            if not temppath:
                return False

            if not os.path.exists(temppath):
                os.mkdir(temppath)

            # write a temp shell command
            tempfilename = os.path.join(temppath, 'debug.sh')
            tempfile = open(tempfilename, 'w')
            tempfile.write('echo "running command: %s"\n' % (cmd % options))
            tempfile.write(cmd % options)
            tempfile.close()

            # make sure the system can run the file
            os.system('chmod 0755 %s' % tempfilename)

            # run the file
            options['filepath'] = tempfilename
            succes = subprocess.Popen(debugcmd % options, shell=True)

        return success

    # otherwise run it directly
    else:
        # run the command in windows
        if settings.OS_TYPE == 'Windows':
            if cmd and not ext == 'web':
                success, value = QProcess.startDetached(cmd, [filename], basePath)
            else:
                success, value = QProcess.startDetached(filename, [], basePath)

            if not success:
                try:
                    success = os.startfile(filename)
                except:
                    pass

        # in other platforms, we'll use subprocess.Popen
        else:
            if cmd:
                success = subprocess.Popen(cmd % options, shell=True)
            else:
                success = subprocess.Popen(
                    os.environ.get(*COMMAND_MAP['open']) % options, shell=True
                )

    return success
