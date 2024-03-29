import os
import sys

import sublime
import sublime_plugin

lib_path = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'libs'))
sys.path.append(lib_path)

import clang.cindex

# globals
shared_settings = None
syntax_checker = None

class Settings:
    def __init__(self):
        self.settings = sublime.load_settings('Clime.sublime-settings')

    def get(self, key_name):
        return self.settings.get(key_name)

    def has(self, key_name):
        return self.settings.has(key_name)

class TranslationUnit:
    def __init__(self, view, index):
        self.view = view
        self.index = index
        self.error_regions = []
        self.warning_regions = []
        self.errors_by_line = {}
        self.translation_unit = self.index.parse(view.file_name(), args=['-x', 'c++'], unsaved_files=[(self.view.file_name(), self.view.substr(sublime.Region(0, self.view.size())))])
        self.calculate_error_regions()

    def reparse(self):
        self.translation_unit.reparse(unsaved_files=[(self.view.file_name(), self.view.substr(sublime.Region(0, self.view.size())))])
        self.calculate_error_regions()

    def __node_contains_location(self, node, location):
        # node.location.file can be None while node.extent.start.file is not O_o
        result = (node.extent.start.file is not None and location.file is not None
            and node.extent.start.file.name == location.file.name
            and ((location.line > node.extent.start.line) or (location.line == node.extent.start.line and location.column >= node.extent.start.column))
            and ((location.line < node.extent.end.line) or (location.line == node.extent.end.line and location.column <= node.extent.end.column)))
        return result

    def __find_node_for_diagnostic(self, node, diagnostic):
        if not self.__node_contains_location(node, diagnostic.location):
            return None
        for child in node.get_children():
            n = self.__find_node_for_diagnostic(child, diagnostic)
            if n is not None:
                return n
        return node

    def calculate_error_regions(self):
        self.error_regions = []
        self.warning_regions = []
        self.errors_by_line = {}
        for diagnostic in self.translation_unit.diagnostics:

            regions = self.error_regions if diagnostic.severity > 2 else self.warning_regions

            node = self.__find_node_for_diagnostic(self.translation_unit.cursor, diagnostic)

            # only use nodes that fit on one line. Otherwise it looks better to just use the line from the diagnostic
            if node is not None and node.extent.start.line == node.extent.end.line:
                start_line = node.extent.start.line - 1
                start_column = node.extent.start.column -1
                end_line = node.extent.end.line - 1
                end_column = node.extent.end.column -1
                regions.append(sublime.Region(self.view.text_point(start_line, start_column), self.view.text_point(end_line, end_column)))
            else:
                line = diagnostic.location.line
                column = diagnostic.location.column
                regions.append(self.view.full_line(self.view.text_point(line - 1, column - 1)))

            self.errors_by_line[diagnostic.location.line - 1] = diagnostic.spelling


    def error_for_line(self, line_number):
        if line_number in self.errors_by_line:
            return self.errors_by_line[line_number]
        return None

class SyntaxChecker:
    def __init__(self):
        self.index = clang.cindex.Index.create()
        self.translation_units = {}
        self.warning_icon = 'Packages/clime/icons/warning.png'
        self.error_icon = 'Packages/clime/icons/error.png'

        sublime.load_binary_resource(self.warning_icon)
        sublime.load_binary_resource(self.error_icon)

    def create_translation_unit(self, view):
        if view.id() in self.translation_units:
            return True

        file_name, file_extension = os.path.splitext(view.file_name() or '')
        if not file_extension in shared_settings.get('file_extensions'):
            return False

        self.translation_units[view.id()] = TranslationUnit(view, self.index)
        self.show_diagnostics(view)
        return True

    def reparse_translation_unit(self, view):
        if not view.id() in self.translation_units:
            return

        self.translation_units[view.id()].reparse()
        self.show_diagnostics(view)

    def show_diagnostics(self, view):
        if not view.id() in self.translation_units:
            return;

        view.erase_regions('clime_warnings')
        view.erase_regions('clime_errors')

        warning_regions = self.translation_units[view.id()].warning_regions
        if warning_regions:
            view.add_regions('clime_warnings', warning_regions, 'invalid.deprecated', self.warning_icon, sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.PERSISTENT)
            self.show_status(view)

        error_regions = self.translation_units[view.id()].error_regions
        if error_regions:
            view.add_regions('clime_errors', error_regions, 'invalid', self.error_icon, sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.PERSISTENT)
            self.show_status(view)

    def show_status(self, view):
        if not view.id() in self.translation_units:
            return;

        selection = view.sel()

        # don't attempt to show status if the user is using multi select
        if len(selection) > 1:
            view.erase_status('clime_error')
            return

        row, col = view.rowcol(selection[0].begin())

        error_status = self.translation_units[view.id()].error_for_line(row)
        if (error_status):
            view.set_status('clime_error', error_status)
        else:
            view.erase_status('clime_error')

def plugin_loaded():
    global shared_settings
    global translation_unit_manager
    global syntax_checker

    shared_settings = Settings()

    if not (clang.cindex.Config.library_path or clang.cindex.Config.library_file):
        if shared_settings.has('libclang_path'):
            clang.cindex.Config.set_library_path(shared_settings.get('libclang_path'))
        elif sublime.platform() == 'osx':
            clang.cindex.Config.set_library_file('/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib')

    syntax_checker = SyntaxChecker()

class ClimeSyntaxCheckCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        syntax_checker.reparse_translation_unit(self.view)

class ClimeEventListener(sublime_plugin.EventListener):
    def __init__(self):
        self.pendingSyntaxChecks = set()
        self.should_check_syntax = {}

    def on_modified_async(self, view):
        if not view.id() in self.should_check_syntax:
            self.should_check_syntax[view.id()] = syntax_checker.create_translation_unit(view)
        if self.should_check_syntax[view.id()]:
            self.run_syntax_check(view)

    def on_save_async(self, view):
        self.should_check_syntax[view.id()] = syntax_checker.create_translation_unit(view)

    def on_load_async(self, view):
        self.should_check_syntax[view.id()] = syntax_checker.create_translation_unit(view)

    def on_activated_async(self, view):
        if not view.id() in self.should_check_syntax:
            self.should_check_syntax[view.id()] = syntax_checker.create_translation_unit(view)

    def on_selection_modified_async(self, view):
        syntax_checker.show_status(view)

    def run_syntax_check(self, view):
        if view.id() in self.pendingSyntaxChecks or not view.file_name():
            return

        self.pendingSyntaxChecks.add(view.id())
        sublime.set_timeout(lambda: self.run_syntax_check_callback(view), 1000)

    def run_syntax_check_callback(self, view):
        self.pendingSyntaxChecks.discard(view.id())
        view.run_command('clime_syntax_check')

