import os
import sys
import shlex
import ntpath
import subprocess
import re
import sublime
import sublime_plugin

class PhpunitTestCommand(sublime_plugin.WindowCommand):

    lastTestCommand = False

    def get_setting(self, key, default=None):
        return sublime.load_settings("Preferences.sublime-settings").get(key, default)

    def get_cmd_connector(self):
        if 'fish' == self.get_setting('phpunit-sublime-shell', 'bash'):
            return '; and '
        else:
            return ' && '

    def get_paths(self):
        file_name = self.window.active_view().file_name()
        phpunit_config_path = self.find_phpunit_config(file_name)

        directory = os.path.dirname(os.path.realpath(file_name))

        file_name = file_name.replace(' ', '\ ')
        phpunit_config_path = phpunit_config_path.replace(' ', '\ ')
        phpunit_bin = self.find_phpunit_bin(phpunit_config_path)

        active_view = self.window.active_view()

        return file_name, phpunit_config_path, phpunit_bin, active_view, directory

    def get_current_function(self, view):
        sel = view.sel()[0]
        function_regions = view.find_by_selector('entity.name.function')
        cf = None
        for r in reversed(function_regions):
            if r.a < sel.a:
                cf = view.substr(r)
                self.is_pest_test = False
                break

        if cf is None:
            # Try to get Pest test description
            cf = self.get_current_pest_test_name(view, sel.a)
            if cf:
                self.is_pest_test = True
            else:
                self.is_pest_test = False

        return cf

    def get_current_pest_test_name(self, view, position):
        pattern = r"test\s*\(\s*['\"](.*?)['\"]"
        pest_tests = view.find_all(pattern)
        for r in reversed(pest_tests):
            if r.a < position:
                line_region = view.line(r)
                line_text = view.substr(line_region)
                test_match = re.search(pattern, line_text)
                if test_match:
                    return test_match.group(1)
        return None

    def find_phpunit_config(self, file_name):
        phpunit_config_path = file_name
        found = False
        while not found:
            phpunit_config_path = os.path.abspath(os.path.join(phpunit_config_path, os.pardir))
            found = os.path.isfile(os.path.join(phpunit_config_path, 'phpunit.xml')) or \
                    os.path.isfile(os.path.join(phpunit_config_path, 'phpunit.xml.dist')) or \
                    phpunit_config_path == '/'
            if phpunit_config_path == '/':
                break
        return phpunit_config_path

    def find_phpunit_bin(self, directory):
        search_paths = [
            'vendor/bin/pest',
            'vendor/bin/phpunit',
            'vendor/bin/phpunit/phpunit/phpunit',
        ]

        found = False
        for path in search_paths:
            binpath = os.path.realpath(os.path.join(directory, path))
            if os.path.isfile(binpath):
                found = True
                break

        if not found:
            binpath = 'phpunit'

        return binpath

    def run_in_terminal(self, command):
        osascript_command = 'osascript '

        if self.get_setting('phpunit-sublime-terminal', 'Term') == 'iTerm':
            osascript_command += '"' + os.path.dirname(os.path.realpath(__file__)) + '/open_iterm.applescript"'
            osascript_command += ' "' + command + '"'
        else:
            osascript_command += '"' + os.path.dirname(os.path.realpath(__file__)) + '/run_command.applescript"'
            osascript_command += ' "' + command + '"'
            osascript_command += ' "PHPUnit Tests"'

        self.lastTestCommand = command
        os.system(osascript_command)

class RunPhpunitTestCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        self.run_in_terminal('cd ' + shlex.quote(phpunit_config_path) + self.get_cmd_connector() + shlex.quote(phpunit_bin) + ' ' + shlex.quote(file_name))

class RunAllPhpunitTestsCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        self.run_in_terminal('cd ' + shlex.quote(phpunit_config_path) + self.get_cmd_connector() + shlex.quote(phpunit_bin))

class RunSinglePhpunitTestCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        current_function = self.get_current_function(active_view)
        if not current_function:
            sublime.error_message("Could not determine the current test.")
            return

        if self.is_pest_test:
            filter_param = shlex.quote(current_function)
        else:
            filter_param = shlex.quote('/::' + current_function + '$/')

        command = 'cd ' + shlex.quote(phpunit_config_path) + self.get_cmd_connector() + shlex.quote(phpunit_bin) + ' ' + shlex.quote(file_name) + ' --filter ' + filter_param
        self.run_in_terminal(command)

class RunLastPhpunitTestCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        if 'Test' in file_name:
            RunSinglePhpunitTestCommand.run(self, *args, **kwargs)
        elif self.lastTestCommand:
            self.run_in_terminal(self.lastTestCommand)

class RunPhpunitTestsInDirCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        self.run_in_terminal('cd ' + shlex.quote(phpunit_config_path) + self.get_cmd_connector() + shlex.quote(phpunit_bin) + ' ' + shlex.quote(directory))

class RunSingleDuskTestCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        current_function = self.get_current_function(active_view)
        if not current_function:
            sublime.error_message("Could not determine the current test.")
            return

        command = 'cd ' + shlex.quote(phpunit_config_path) + self.get_cmd_connector() + 'php artisan dusk ' + shlex.quote(file_name) + ' --filter ' + shlex.quote(current_function)
        self.run_in_terminal(command)

class RunAllDuskTestsCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        command = 'cd ' + shlex.quote(phpunit_config_path) + self.get_cmd_connector() + 'php artisan dusk'
        self.run_in_terminal(command)

class RunDuskTestsInDirCommand(PhpunitTestCommand):

    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, phpunit_bin, active_view, directory = self.get_paths()

        command = 'cd ' + shlex.quote(phpunit_config_path) + self.get_cmd_connector() + 'php artisan dusk ' + shlex.quote(directory)
        self.run_in_terminal(command)

class FindMatchingTestCommand(sublime_plugin.WindowCommand):

    def path_leaf(self, path):
        head, tail = ntpath.split(path)
        return tail or ntpath.basename(head)

    def run(self, *args, **kwargs):
        file_name = self.window.active_view().file_name()
        file_name = self.path_leaf(file_name)
        file_name = file_name[0:file_name.find('.')]
        tab_target = 0

        if 'Test' not in file_name:
            file_name = file_name + 'Test'
        else:
            # Strip 'Test' and add '.' to force matching the non-test file
            file_name = file_name[0:file_name.find('Test')] + '.'
            tab_target = 1

        # Big dirty macro-ish hack. Eventually I should just open the file in some sort of
        # logical way.
        self.window.run_command("set_layout", {
            "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
            "cols": [0.0, 0.5, 1.0],
            "rows": [0.0, 1.0]
        })
        self.window.run_command("focus_group", {"group": tab_target})
        self.window.run_command("show_overlay", {
            "overlay": "goto",
            "text": file_name,
            "show_files": "true"
        })
        self.window.run_command("move", {"by": "lines", "forward": False})

        # This is a dirty hack to get it to switch files... Can't simulate 'Enter'
        # but triggering the overlay again to close it seems to have the same effect.
        self.window.run_command("show_overlay", {"overlay": "goto", "show_files": "true"})
        self.window.run_command("focus_group", {"group": 0})
        self.window.run_command("focus_group", {"group": tab_target})
