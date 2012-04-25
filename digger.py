import os
import sys
import ast

import collections
import itertools as it

from os import path

FunctionEntry = collections.namedtuple('FunctionEntry', 'name node location')


class ModuleEntry(object):
    def __init__(self, module_path):
        self.module_path = module_path
        self.functions = 0
        self.nested_functions = []
        self.classes = 0
        self.methods = 0
        self.lambda_expressions = 0
        self.nested_lambda_expressions = 0

    def add_nested_function(self, function_name, function_node, location):
        self.nested_functions.append(
            FunctionEntry(function_name, function_node, location))
        if isinstance(function_node, ast.Lambda):
            self.nested_lambda_expressions += 1

    def add_function(self, _function_name, _function_node, _location):
        self.functions += 1

    def add_lambda(self, _lambda_name, _lambda_node, _location):
        self.lambda_expressions += 1

    def add_method(self, _method_name, method_node, _location):
        self.methods += 1

    def add_class(self, _class_name, _class_node, _location):
        self.classes += 1

    @property
    def methods_number(self):
        return self.methods

    @property
    def total_functions_number(self):
        return self.functions

    @property
    def nested_functions_number(self):
        return len(self.nested_functions)

    @property
    def classes_number(self):
        return self.classes

    @property
    def lambda_expressions_number(self):
        return self.lambda_expressions

    @property
    def nested_lambda_expressions_number(self):
        return self.nested_lambda_expressions

    def __iter__(self):
        return iter(self.nested_functions)


class Digger(object):
    def __init__(self, module_entry_type=ModuleEntry):
        self.modules = {}
        self.errors = []
        self.module_entry_factory = module_entry_type

    def set_current_module(self, module_path):
        self.current_module = self.module_entry_factory(module_path)
        self.modules[module_path] = self.current_module

    def add_nested_function(self, function_name, function_node, location):
        self.current_module.add_nested_function(
            function_name, function_node, location)

    def add_lambda(self, lambda_name, lambda_node, location):
        self.current_module.add_lambda(
            lambda_name, lambda_node, location)

    def add_function(self, function_name, function_node, location):
        self.current_module.add_function(
            function_name, function_node, location)

    def add_class(self, class_name, class_node, location):
        self.current_module.add_class(
            class_name, class_node, location)

    def add_method(self, method_name, method_node, location):
        self.current_module.add_method(
            method_name, method_node, location)

    def add_error(self, path, exception):
        self.errors.append((path, exception))

    def dig_source(self, source, module_name=''):
        tree = ast.parse(source, filename=module_name)
        digger = DiggingVisitor(self)
        digger.visit(tree)

    def dig_tree(self, path_root):
        for root, _dirs, files in os.walk(path_root):
            for filename in files:
                if filename.endswith('.py'):
                    full_path = path.join(root, filename)
                    try:
                        file_handle = file(full_path)
                        self.set_current_module(full_path)
                        self.dig_source(file_handle.read(), full_path)
                    except Exception as e:
                        self.add_error(full_path, e)

    def nested_functions_iterator(self):
        return it.chain(*self.modules.itervalues())

    @property
    def modules_number(self):
        return len(self.modules)

    def __getattr__(self, name):
        if (name.endswith('number') and 
            hasattr(self.module_entry_factory, name)):
            return sum(getattr(module_entry, name)
                for module_entry in self.modules.itervalues())
        else:
            raise AttributeError(
                "'%s' object has no attribute '%s'" %(
                    type(self), name))


class DiggingVisitor(ast.NodeVisitor):
    def __init__(self, digger):
        self.scope_stack = []
        self.function_scopes = []
        self.function_stack = []
        self.digger = digger
        self.lambda_counter = it.count()

    def lambda_name(self):
        return 'lambda_%d' % next(self.lambda_counter)

    def push_scope(self, node):
        self.scope_stack.append(node)

    def pull_scope(self):
        return self.scope_stack.pop()

    def push_function(self, node):
        self.function_stack.append(node)

    def pull_function(self):
        return self.function_stack.pop()

    def is_class_scope(self):
        try:
            last_scope = self.scope_stack[-1]
        except IndexError:
            return False
        else:
            return isinstance(last_scope, ast.ClassDef)

    def set_new_function_scope(self):
        self.function_scopes.append(self.function_stack)
        self.function_stack = []

    def restore_function_scope(self):
        self.function_stack = self.function_scopes.pop()

    def is_function_scope(self):
        return bool(self.function_stack)

    def also_mark_as_nested(self, name, node, location):
        if self.is_function_scope():
            self.digger.add_nested_function(name, node, location)

    def visit_Lambda(self, node):
        location = self.pretty_stack()
        lambda_name = self.lambda_name()
        self.digger.add_lambda(
            lambda_name, node, location)
        self.also_mark_as_nested(lambda_name, node, location)

    def visit_ClassDef(self, node):
        location = self.pretty_stack()
        self.digger.add_class(node.name, node, location)
        self.push_scope(node)
        self.set_new_function_scope()
        self.generic_visit(node)
        self.restore_function_scope()
        self.pull_scope()

    def visit_FunctionDef(self, node):
        location = self.pretty_stack()
        if self.is_class_scope():
            self.digger.add_method(node.name, node, location)
        else:
            self.digger.add_function(node.name, node, location)
        self.also_mark_as_nested(node.name, node, location)
        self.push_scope(node)
        self.push_function(node)
        self.generic_visit(node)
        self.pull_scope()
        self.pull_function()

    def pretty_stack(self):
        return '.'.join(scope_element.name
            for scope_element in self.scope_stack)


if __name__ == '__main__':
    digger = Digger()
    digger.dig_tree(sys.argv[1])
    print 'Analyzed %d modules.' % digger.modules_number
    print 'Found %d classes,' % digger.classes_number,
    print 'that collectively have %d methods.' % digger.methods_number
    print 'Found %d non-method functions.' % digger.total_functions_number
    print 'Found %d nested functions.' % digger.nested_functions_number
    print 'Found %d lambda expressions,' % digger.lambda_expressions_number,
    print 'of which %d where nested (already counted).' % \
        digger.nested_lambda_expressions_number
    if digger.errors:
        print 'Could not process the following files:'
        for error in digger.errors:
            print '%s: %s' % error
