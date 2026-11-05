from __future__ import absolute_import

import functools
from pathlib import Path

from Qt.QtWidgets import QWidget

from ..prefs import VersionTypes, get_backup_version_info
from .workbox_mixin import WorkboxMixin

# Setters that only apply editor settings. While a workbox is still a placeholder
# these are recorded and replayed on the real editor when it gets created, so
# changing a setting doesn't force every workbox editor to be built.
DEFERRED_SETTERS = (
    "__set_auto_complete_enabled__",
    "__set_copy_indents_as_spaces__",
    "__set_indentations_use_tabs__",
    "__set_font__",
    "__set_margins_font__",
    "__set_tab_width__",
)


def _forwarded(func):
    """Call func on the placeholder until the real editor is created, then
    forward the call to the real editor instead."""
    name = func.__name__

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        editor = self.__dict__.get("_editor")
        if editor is not None:
            return getattr(editor, name)(*args, **kwargs)
        return func(self, *args, **kwargs)

    return wrapper


def _borrow(name):
    """Re-use a WorkboxMixin method that only works with stored data."""
    return _forwarded(getattr(WorkboxMixin, name))


class WorkboxPlaceholder(QWidget):
    """A cheap stand-in for a workbox editor used when restoring prefs.

    Building every workbox editor on startup is slow, so restored tabs start
    out as this widget. It stores the data needed to answer the cheap workbox
    queries (id, name, filename, dirty state, saving prefs, etc.) without an
    editor. The real editor is created and swapped into the tab when the tab is
    shown, or when anything uses editor functionality that this class doesn't
    implement. After that, every call made on this object is forwarded to the
    real editor so any stale references keep working.
    """

    def __init__(
        self,
        parent=None,
        editor_cls=None,
        core_name=None,
        workbox_id=None,
        filename=None,
        backup_file=None,
        tempfile=None,
    ):
        super(WorkboxPlaceholder, self).__init__(parent=parent)
        self._editor = None
        self._materializing = False
        self._editor_cls = editor_cls
        self._pending_settings = {}
        self._cached_text = None

        # Mirror the attributes WorkboxMixin.__init__ sets so its data methods
        # can be re-used on this class.
        self._is_loaded = False
        self._encoding = None
        self.core_name = core_name
        self.shownDialogs = []
        if not workbox_id:
            workbox_id = WorkboxMixin.__create_workbox_id__(core_name)
        self._workbox_id = workbox_id
        self._filename = filename
        self._backup_file = backup_file
        self._tempfile = tempfile
        self._last_saved_text = ""
        self._last_workbox_name = None
        self._promptOnLinkedChange = True
        self._orphaned_by_instance = False
        self._changed_by_instance = False
        self._changed_saved = False

    def __getattr__(self, name):
        # Only called if normal attribute lookup fails. Guard against recursion
        # if this is called before __init__ has set up attributes.
        editor_cls = self.__dict__.get("_editor_cls")
        if editor_cls is None or not hasattr(editor_cls, name):
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(type(self).__name__, name)
            )

        if self.__dict__.get("_editor") is None and name in DEFERRED_SETTERS:
            return functools.partial(self._record_setting, name)

        # This requires the real editor, create it and use it from now on.
        return getattr(self.__materialize__(), name)

    def _record_setting(self, name, *args, **kwargs):
        editor = self._editor
        if editor is not None:
            return getattr(editor, name)(*args, **kwargs)
        self._pending_settings[name] = (args, kwargs)

    def __is_placeholder__(self):
        """Returns True until the real editor has been created."""
        return self._editor is None

    def __editor__(self):
        """Returns the real editor if it has been created, otherwise None."""
        return self._editor

    def __materialize__(self):
        """Create the real editor, swapping it into this placeholder's tab.

        Returns:
            WorkboxMixin: The real editor.
        """
        if self._editor is not None:
            return self._editor

        if self._materializing:
            raise RuntimeError(
                "Recursion while creating the editor for workbox {}. Something "
                "called an editor method on its placeholder while the editor "
                "was being created.".format(self._workbox_id)
            )

        tab_widget = self.__tab_widget__()
        if tab_widget is None:
            raise RuntimeError(
                "Unable to create the editor for workbox {}, it is not in a "
                "tab widget.".format(self._workbox_id)
            )
        self._materializing = True
        try:
            return tab_widget.materialize_placeholder(self)
        finally:
            self._materializing = False

    def __editor_prefs__(self):
        """The kwargs to pass to the editor class to create the real editor."""
        return dict(
            workbox_id=self._workbox_id,
            filename=self._filename,
            backup_file=self._backup_file,
            tempfile=self._tempfile,
        )

    def __transfer_state__(self, editor):
        """Copy state stored on this placeholder to the newly created editor."""
        editor.__set_orphaned_by_instance__(self._orphaned_by_instance)
        editor.__set_changed_by_instance__(self._changed_by_instance)
        editor._changed_saved = self._changed_saved
        editor._last_workbox_name = self._last_workbox_name
        for name, (args, kwargs) in self._pending_settings.items():
            getattr(editor, name)(*args, **kwargs)
        self._pending_settings = {}

    def __set_editor__(self, editor):
        """Mark this placeholder as replaced by editor. From now on, all workbox
        calls made on this placeholder are forwarded to editor."""
        self._editor = editor
        self._cached_text = None

    # Data methods that don't need an editor
    __tab_widget__ = _borrow("__tab_widget__")
    __workbox_name__ = _borrow("__workbox_name__")
    __group_tab_index__ = _borrow("__group_tab_index__")
    __workbox_id__ = _borrow("__workbox_id__")
    __set_workbox_id__ = _borrow("__set_workbox_id__")
    __filename__ = _borrow("__filename__")
    __set_filename__ = _borrow("__set_filename__")
    __backup_file__ = _borrow("__backup_file__")
    __set_backup_file__ = _borrow("__set_backup_file__")
    __tempfile__ = _borrow("__tempfile__")
    __set_tempfile__ = _borrow("__set_tempfile__")
    __last_saved_text__ = _borrow("__last_saved_text__")
    __last_workbox_name__ = _borrow("__last_workbox_name__")
    __set_last_workbox_name__ = _borrow("__set_last_workbox_name__")
    __changed_by_instance__ = _borrow("__changed_by_instance__")
    __set_changed_by_instance__ = _borrow("__set_changed_by_instance__")
    __orphaned_by_instance__ = _borrow("__orphaned_by_instance__")
    __set_orphaned_by_instance__ = _borrow("__set_orphaned_by_instance__")
    __determine_been_changed_by_instance__ = _borrow(
        "__determine_been_changed_by_instance__"
    )
    __is_missing_linked_file__ = _borrow("__is_missing_linked_file__")
    __file_monitoring_enabled__ = _borrow("__file_monitoring_enabled__")
    __set_file_monitoring_enabled__ = _borrow("__set_file_monitoring_enabled__")
    __prompt_on_linked_change__ = _borrow("__prompt_on_linked_change__")
    # The text was never loaded, so this only returns the minimal prefs without
    # writing a backup file, the same as for an editor that was never shown.
    __save_prefs__ = _borrow("__save_prefs__")
    __close__ = _borrow("__close__")

    @_forwarded
    def __set_last_saved_text__(self, text):
        # The placeholder never has unsaved text changes, there is no need to
        # store the text. The real editor sets this when it loads its text.
        tab_widget = self.__tab_widget__()
        if tab_widget is not None:
            tab_widget.tabBar().update()

    @_forwarded
    def __is_dirty__(self):
        # The text was never loaded so it can't have changed, only the name can.
        return self.__workbox_name__(workbox=self) != self.__last_workbox_name__()

    @_forwarded
    def __show__(self):
        """Load and cache this workbox's text from disk without creating the
        editor. Use `__materialize__` to create the editor."""
        if self._cached_text is not None:
            return

        text = ""
        filename = self._filename
        if filename and Path(filename).is_file():
            self._encoding, text = WorkboxMixin.__open_file__(filename)
        else:
            filepath, _idx, count = get_backup_version_info(
                self.core_name, self._workbox_id, VersionTypes.Last, ""
            )
            if count and filepath and Path(filepath).is_file():
                self._encoding, text = WorkboxMixin.__open_file__(str(filepath))
        self._cached_text = text

    @_forwarded
    def __text__(self):
        self.__show__()
        return self._cached_text

    def __reset_cached_text__(self):
        """Discard the cached text, ie if another instance changed the file."""
        self._cached_text = None
