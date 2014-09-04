import os
import sys

import sublime
import sublime_plugin

lib_path = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'libs'))
sys.path.append(lib_path)

import clang.cindex

class Settings:
    def __init__(self):
        self.settings = {}

    def load(self):
        self.settings = sublime.load_settings('Clime.sublime-settings')

    def get(self, key_name):
        return self.settings.get(key_name)

    def has(self, key_name):
        return self.settings.has(key_name)

class SyntaxChecker:
    def __init__(self):
        pass

    def check_syntax(self, view):
        print('checking stuff now')
        index = clang.cindex.Index.create()
        print(index)

shared_settings = Settings()
syntax_checker = SyntaxChecker()

def plugin_loaded():
    shared_settings.load()

    print('plugin_is_loaded' not in globals())

    if shared_settings.has('libclang_path'):
        clang.cindex.Config.set_library_path(shared_settings.get('libclang_path'))
    elif sublime.platform() == 'osx':
        clang.cindex.Config.set_library_file('/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib')

class ClimeSyntaxCheckCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        syntax_checker.check_syntax(self.view)

class ClimeEventListener(sublime_plugin.EventListener):
    def __init__(self):
        self.pendingSyntaxChecks = set()

    def on_modified_async(self, view):
        self.run_syntax_check(view)

    def on_save_async(self, view):
        self.run_syntax_check(view)

    def on_load_async(self, view):
        self.run_syntax_check(view)

    def run_syntax_check(self, view):
        if view.id() in self.pendingSyntaxChecks or not view.file_name():
            return

        self.pendingSyntaxChecks.add(view.id())
        sublime.set_timeout(lambda: self.run_syntax_check_callback(view), 3000)

    def run_syntax_check_callback(self, view):
        self.pendingSyntaxChecks.discard(view.id())

        file_name, file_extension = os.path.splitext(view.file_name())
        if file_extension in shared_settings.get('file_extensions'):
            view.run_command('clime_syntax_check')

