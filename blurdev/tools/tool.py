##
# 	\namespace	blurdev.tools.tool
#
# 	\remarks	Creates the ToolsCategory class for grouping tools together
#
# 	\author		beta@blur.com
# 	\author		Blur Studio
# 	\date		06/11/10
#

import os

from PyQt4.QtCore import QObject

from blurdev.enum import enum

# 					1			2			4			8		  16			32				64					128				256
ToolType = enum(
    'External',
    'Trax',
    'Studiomax',
    'Softimage',
    'Fusion',
    'MotionBuilder',
    'LegacyExternal',
    'LegacyStudiomax',
    'LegacySoftimage',
    AllTools=511,
)


class Tool(QObject):
    def __init__(self):
        QObject.__init__(self)

        self._displayName = ''
        self._path = ''
        self._sourcefile = ''
        self._toolTip = ''
        self._wikiPage = ''
        self._macros = []
        self._version = ''
        self._icon = ''
        self._toolType = 0
        self._favorite = False
        self._favoriteGroup = None
        self._header = None
        self._disabled = False

    def disabled(self):
        return self._disabled

    def displayName(self):
        if self._displayName:
            return self._displayName
        else:
            output = str(self.objectName()).split('::')[-1]
            return output.replace('_', ' ').strip()

    def exec_(self, macro=''):
        """
            \remarks	runs this tool with the inputed macro command
            \param		macro	<str>
        """
        from PyQt4.QtCore import Qt
        from PyQt4.QtGui import QApplication
        import blurdev

        from blurdev import debug

        if QApplication.instance().keyboardModifiers() == Qt.ControlModifier or debug.isDebugLevel(
            debug.DebugLevel.Mid
        ):
            blurdev.activeEnvironment().resetPaths()

        # run standalone
        if self.toolType() & ToolType.LegacyExternal:
            blurdev.core.runStandalone(self.sourcefile())
        else:
            blurdev.core.runScript(self.sourcefile())  # , toolType = self.toolType() )

        # Log what tool was used and when.
        try:
            # uses the environment variable "bdev_use_log_class" to import a module similar to the following
            # import datetime
            # def logEvent(info):
            # 	info.setdefault('created', datetime.datetime.today())
            # 	f = open(r'c:\temp\log.txt', 'w')
            # 	f.write(repr(info))
            # 	f.close()
            # 	return info
            useLogClass = os.environ.get('bdev_use_log_class')
            import importlib

            useLog = importlib.import_module(useLogClass)
            info = {'name': self.objectName()}
            info['miscInfo'] = macro
            useLog.logEvent(info)
        except Exception, e:
            if debug.debugLevel() >= debug.DebugLevel.High:
                raise
            else:
                # If redmine commits fail, allow code to continue.
                console = blurdev.core.logger().console()
                error = ''.join(console.lastError())
                emails = (
                    blurdev.tools.ToolsEnvironment.activeEnvironment().emailOnError()
                )
                console.emailError(emails, error)

    def favoriteGroup(self):
        return self._favoriteGroup

    def header(self):
        if not self._header:
            from toolheader import ToolHeader

            self._header = ToolHeader(self)
        return self._header

    def icon(self):
        path = self.relativePath(self._icon)
        if not (path and os.path.isfile(path)):
            # Return default icon if none was set or exists
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'resource',
                'img',
                'blank.png',
            )
        return path

    def isFavorite(self):
        return self._favorite

    def isNull(self):
        return self.objectName() == ''

    def isLegacy(self):
        return self.toolType() in (
            ToolType.LegacyExternal,
            ToolType.LegacyStudiomax,
            ToolType.LegacySoftimage,
        )

    def index(self):
        """
            \remarks	returns the index from which this category is instantiated
            \return		<blurdev.tools.ToolIndex>
        """
        from toolsindex import ToolsIndex

        output = self.parent()
        while output and not isinstance(output, ToolsIndex):
            output = output.parent()
        return output

    def path(self):
        return self._path

    def projectFile(self):
        return self.relativePath('%s.blurproj' % self.displayName())

    def relativePath(self, relpath):
        import os.path

        output = os.path.join(self.path(), relpath)
        return output

    def setDisabled(self, state):
        self._disabled = state

    def setDisplayName(self, name):
        self._displayName = name

    def setFavorite(self, state=True):
        self._favorite = state

    def setFavoriteGroup(self, favoriteGroup):
        self._favoriteGroup = favoriteGroup
        if favoriteGroup:
            self.setFavorite()

    def setIcon(self, icon):
        self._icon = icon

    def setPath(self, path):
        self._path = str(path).replace(
            str(self.objectName()).lower(), self.objectName()
        )  # ensure that the tool id is properly formated since it is case sensitive

    def setSourcefile(self, sourcefile):
        self._sourcefile = str(sourcefile).replace(
            str(self.objectName()).lower(), self.objectName()
        )  # ensure that the tool id is properly formated since it is case sensitive

    def setToolType(self, toolType):
        """
            \remarks	sets the current tools type
            \param		toolType	<ToolType>
        """
        self._toolType = toolType

    def setVersion(self, version):
        self._version = version

    def setWikiPage(self, wiki):
        self._wikiPage = wiki

    def sourcefile(self):
        return self._sourcefile

    def toolTip(self):
        return self._toolTip

    def toolType(self):
        """
            \remarks	returns the toolType for this category
            \return		<ToolType>
        """
        return self._toolType

    def version(self):
        return self._version

    def wikiPage(self):
        return self._wikiPage

    @staticmethod
    def fromIndex(index, xml):
        """
            \remarks	creates a new tool record based on the inputed xml information for the given index
            \param		index	<ToolsIndex>
            \param		xml		<blurdev.XML.XMLElement>
        """
        output = Tool()
        output.setObjectName(xml.attribute('name'))

        # load modern tools
        loc = xml.attribute('loc')
        import os.path

        if loc:
            output.setPath(os.path.split(index.environment().relativePath(loc))[0])

            # load the meta data
            data = xml.findChild('data')
            if data:
                output.setVersion(data.attribute('version'))
                output.setIcon(data.findProperty('icon'))
                output.setSourcefile(output.relativePath(data.findProperty('src')))
                output.setWikiPage(data.findProperty('wiki'))
                output.setToolType(
                    ToolType.fromString(data.attribute('type', 'AllTools'))
                )
                output.setDisplayName(
                    data.findProperty('displayName', output.objectName())
                )
                output.setDisabled(
                    data.findProperty('disabled', 'false').lower() == 'true'
                )
        else:
            output.setToolType(ToolType.fromString(xml.attribute('type', 'AllTools')))
            filename = xml.attribute('src')
            output.setPath(
                os.path.split(filename)[0]
                + '/%s_resource' % os.path.basename(filename).split('.')[0]
            )
            output.setSourcefile(filename)
            output.setIcon(xml.attribute('icon'))

        # add the tool to the category or index
        category = index.findCategory(xml.attribute('category'))
        if category:
            category.addTool(output)
        else:
            output.setParent(index)

        # cache the tool in the index
        index.cacheTool(output)

        return output
