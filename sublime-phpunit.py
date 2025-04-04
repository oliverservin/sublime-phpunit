import os
import sys
import shlex
import ntpath
import subprocess
import sublime
import sublime_plugin
import re

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
        active_view = self.window.active_view()
        is_pest = self.is_pest_test_file(active_view)
        phpunit_config_path = self.find_phpunit_config(file_name)
        directory = os.path.dirname(os.path.realpath(file_name))
        test_bin = self.find_test_bin(phpunit_config_path, is_pest)
        file_name = file_name.replace(' ', '\ ')
        phpunit_config_path = phpunit_config_path.replace(' ', '\ ')
        return file_name, phpunit_config_path, test_bin, active_view, directory, is_pest

    def is_pest_test_file(self, view):
        """Check if the current file is a Pest test file."""
        content = view.substr(sublime.Region(0, view.size()))
        if re.search(r'use function Pest\\', content) or re.search(r'^\s*(it|test)\(', content, re.MULTILINE):
            return True
        return False

    def find_phpunit_config(self, file_name):
        """Find the directory containing the PHPUnit configuration file."""
        phpunit_config_path = file_name
        found = False
        while not found:
            phpunit_config_path = os.path.abspath(os.path.join(phpunit_config_path, os.pardir))
            found = os.path.isfile(os.path.join(phpunit_config_path, 'phpunit.xml')) or \
                    os.path.isfile(os.path.join(phpunit_config_path, 'phpunit.xml.dist')) or \
                    phpunit_config_path == '/'
        return phpunit_config_path

    def find_test_bin(self, directory, is_pest):
        """Locate the test binary (pest or phpunit) based on whether it's a Pest test."""
        if is_pest:
            search_paths = ['vendor/bin/pest']
        else:
            search_paths = ['vendor/bin/phpunit', 'vendor/bin/phpunit/phpunit/phpunit']

        for path in search_paths:
            binpath = os.path.realpath(os.path.join(directory, path))
            if os.path.isfile(binpath.replace("\\", "")):
                return binpath

        return 'pest' if is_pest else 'phpunit'

    def get_current_function(self, view):
        """Get the name of the current PHPUnit test method."""
        sel = view.sel()[0]
        function_regions = view.find_by_selector('entity.name.function')
        cf = None
        for r in reversed(function_regions):
            if r.a < sel.a:
                cf = view.substr(r)
                break
        return cf

    def get_pest_test_description(self, view):
        sel = view.sel()[0]
        search_pos = sel.begin()
        while search_pos > 0:
            it_region = view.find(r'\b(it|test)\s*\(', search_pos, sublime.IGNORECASE)
            if it_region and it_region.a != -1:
                # Check the scope at the start of 'test(' or 'it('
                scope = view.scope_name(it_region.a)
                if 'meta.function' not in scope:
                    # Found a top-level test, extract the description
                    start_pos = it_region.end()
                    quote_region = view.find(r'[\'"]', start_pos)
                    if quote_region and quote_region.a != -1:
                        quote_char = view.substr(quote_region)
                        end_quote_pos = view.find(quote_char, quote_region.end())
                        if end_quote_pos and end_quote_pos.a != -1:
                            description_region = sublime.Region(quote_region.end(), end_quote_pos.begin())
                            description = view.substr(description_region)
                            return description
                # Inside a function, keep searching backwards
                search_pos = it_region.begin() - 1
            else:
                break
        return None

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
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        self.run_in_terminal('cd {0}{1}{2} {3}'.format(phpunit_config_path, self.get_cmd_connector(), test_bin, file_name))

class RunAllPhpunitTestsCommand(PhpunitTestCommand):
    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        self.run_in_terminal('cd {0}{1}{2}'.format(phpunit_config_path, self.get_cmd_connector(), test_bin))

class RunSinglePhpunitTestCommand(PhpunitTestCommand):
    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        if is_pest:
            description = self.get_pest_test_description(active_view)
            filter_option = ' --filter {0}'.format(shlex.quote(description)) if description else ''
        else:
            current_function = self.get_current_function(active_view)
            filter_option = " --filter '/::{0}$/'".format(current_function) if current_function else ''
        command = 'cd {0}{1}{2} {3}{4}'.format(phpunit_config_path, self.get_cmd_connector(), test_bin, file_name, filter_option)
        self.run_in_terminal(command)

class RunLastPhpunitTestCommand(PhpunitTestCommand):
    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        if 'Test' in file_name or is_pest:
            RunSinglePhpunitTestCommand.run(self, *args, **kwargs)
        elif self.lastTestCommand:
            self.run_in_terminal(self.lastTestCommand)

class RunPhpunitTestsInDirCommand(PhpunitTestCommand):
    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        self.run_in_terminal('cd {0}{1}{2} {3}'.format(phpunit_config_path, self.get_cmd_connector(), test_bin, directory))

class RunSingleDuskTestCommand(PhpunitTestCommand):
    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        current_function = self.get_current_function(active_view)
        self.run_in_terminal('cd {0}{1}php artisan dusk {2} --filter {3}'.format(phpunit_config_path, self.get_cmd_connector(), file_name, current_function))

class RunAllDuskTestsCommand(PhpunitTestCommand):
    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        self.run_in_terminal('cd {0}{1}php artisan dusk'.format(phpunit_config_path, self.get_cmd_connector()))

class RunDuskTestsInDirCommand(PhpunitTestCommand):
    def run(self, *args, **kwargs):
        file_name, phpunit_config_path, test_bin, active_view, directory, is_pest = self.get_paths()
        self.run_in_terminal('cd {0}{1}php artisan dusk {2}'.format(phpunit_config_path, self.get_cmd_connector(), directory))

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
            file_name = file_name[0:file_name.find('Test')] + '.'
            tab_target = 1
        self.window.run_command("set_layout", {"cells": [[0, 0, 1, 1], [1, 0, 2, 1]], "cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0]})
        self.window.run_command("focus_group", {"group": tab_target})
        self.window.run_command("show_overlay", {"overlay": "goto", "text": file_name, "show_files": "true"})
        self.window.run_command("move", {"by": "lines", "forward": False})
        self.window.run_command("show_overlay", {"overlay": "goto", "show_files": "true"})
        self.window.run_command("focus_group", {"group": 0})
        self.window.run_command("focus_group", {"group": tab_target})
