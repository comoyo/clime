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
        self.errors_by_line = {}
        self.translation_unit = self.index.parse(view.file_name())
        self.calculate_error_regions()

    def reparse(self):
        self.translation_unit.reparse(unsaved_files=[(self.view.file_name(), self.view.substr(sublime.Region(0, self.view.size())))])
        self.calculate_error_regions()

    def calculate_error_regions(self):
        self.error_regions = []
        self.errors_by_line = {}
        for diagnostic in self.translation_unit.diagnostics:
            self.error_regions.append(self.view.full_line(self.view.text_point(diagnostic.location.line - 1, diagnostic.location.column - 1)))
            self.errors_by_line[diagnostic.location.line - 1] = diagnostic.spelling

    def error_for_line(self, line_number):
        if line_number in self.errors_by_line:
            return self.errors_by_line[line_number]
        return None

class SyntaxChecker:
    def __init__(self):
        self.index = clang.cindex.Index.create()
        self.translation_units = {}

    def create_translation_unit(self, view):
        if view.id() in self.translation_units or not view.file_name():
            return

        file_name, file_extension = os.path.splitext(view.file_name())
        if not file_extension in shared_settings.get('file_extensions'):
            return

        self.translation_units[view.id()] = TranslationUnit(view, self.index)
        self.show_diagnostics(view)

    def reparse_translation_unit(self, view):
        if not view.id() in self.translation_units:
            return

        self.translation_units[view.id()].reparse()
        self.show_diagnostics(view)

    def show_diagnostics(self, view):
        if not view.id() in self.translation_units:
            return;

        view.erase_regions('clime_errors')
        error_regions = self.translation_units[view.id()].error_regions
        if error_regions:
            view.add_regions('clime_errors', error_regions, 'error', 'cross', sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.PERSISTENT)
            row, col = view.rowcol(view.sel()[0].begin())
            self.show_status(view, row)

    def show_status(self, view, line_number):
        if not view.id() in self.translation_units:
            return;

        error_status = self.translation_units[view.id()].error_for_line(line_number)
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
        syntax_checker.create_translation_unit(self.view)
        syntax_checker.reparse_translation_unit(self.view)

class ClimeEventListener(sublime_plugin.EventListener):
    def __init__(self):
        self.pendingSyntaxChecks = set()

    def on_modified_async(self, view):
        self.run_syntax_check(view)

    def on_save_async(self, view):
        syntax_checker.create_translation_unit(view)

    def on_load_async(self, view):
        syntax_checker.create_translation_unit(view)

    def on_selection_modified_async(self, view):
        row, col = view.rowcol(view.sel()[0].begin())
        syntax_checker.show_status(view, row)

    def run_syntax_check(self, view):
        if view.id() in self.pendingSyntaxChecks or not view.file_name():
            return

        self.pendingSyntaxChecks.add(view.id())
        sublime.set_timeout(lambda: self.run_syntax_check_callback(view), 1000)

    def run_syntax_check_callback(self, view):
        self.pendingSyntaxChecks.discard(view.id())
        view.run_command('clime_syntax_check')

