#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2010 (ita)

"""
Base classes (mostly abstract)
"""

import traceback, os, imp, sys
from Constants import *

g_module = None
"""
wscript file representing the entry point of the project
"""


def readf(fname, m='r'):
	"""
	Read an entire file into a string.
	@type  fname: string
	@param fname: Path to file
	@type  m: string
	@param m: Open mode
	@rtype: string
	@return: Content of the file
	"""
	f = open(fname, m)
	try:
		txt = f.read()
	finally:
		f.close()
	return txt

class WafError(Exception):
	def __init__(self, *args):
		self.args = args
		try:
			self.stack = traceback.extract_stack()
		except:
			pass
		Exception.__init__(self, *args)
	def __str__(self):
		return str(len(self.args) == 1 and self.args[0] or self.args)

class WscriptError(WafError):
	def __init__(self, message, wscript_file=None):
		if wscript_file:
			self.wscript_file = wscript_file
			self.wscript_line = None
		else:
			try:
				(self.wscript_file, self.wscript_line) = self.locate_error()
			except:
				(self.wscript_file, self.wscript_line) = (None, None)

		msg_file_line = ''
		if self.wscript_file:
			msg_file_line = "%s:" % self.wscript_file
			if self.wscript_line:
				msg_file_line += "%s:" % self.wscript_line
		err_message = "%s error: %s" % (msg_file_line, message)
		WafError.__init__(self, err_message)

	def locate_error(self):
		stack = traceback.extract_stack()
		stack.reverse()
		for frame in stack:
			file_name = os.path.basename(frame[0])
			is_wscript = (file_name == WSCRIPT_FILE or file_name == WSCRIPT_BUILD_FILE)
			if is_wscript:
				return (frame[0], frame[1])
		return (None, None)

context_dict = {}
def create_context(cmd_name, *k, **kw):
	try:
		return context_dict[cmd_name](*k, **kw)
	except KeyError:
		ctx = Context(*k, **kw)
		ctx.function_name = cmd_name
		return ctx

class command_context(object):
	"""
	Command context decorator. Indicates which command should receive
	this context as its argument (first arg), and which function should be
	executed in user scripts (second arg).
	"""
	def __init__(self, command_name, function_name=None):
		self.command_name = command_name
		self.function_name = function_name if function_name else command_name
	def __call__(self, cls):
		context_dict[self.command_name] = cls
		setattr(cls, 'function_name', self.function_name)
		return cls

class Context(object):
	"""
	Base class for command contexts. Those objects are passed as the arguments
	of user functions (commands) defined in Waf scripts.
	"""
	def __init__(self, start=None):
		if not start:
			import Options
			start = Options.run_dir
		self.curdir = start

	def pre_recurse(self, obj, f, d):
		pass

	def post_recurse(self, obj, f, d):
		pass

	def user_function_name(self):
		"""
		Get the user function name. First use an instance variable, then
		try the class variable. The instance variable will be set by
		Scripting.py if the class variable is not set.
		"""
		name = getattr(self, 'function_name', None)
		if not name:
			name = getattr(self.__class__, 'function_name', None)
		if not name:
			raise WafError('%s does not have an associated user function name.' % self.__class__.__name__)
		return name

	def recurse(self, dirs, name=None):
		"""
		Run user code from the supplied list of directories.
		The directories can be either absolute, or relative to the directory
		of the wscript file.
		@param dirs: List of directories to visit
		@type  name: string
		@param name: Name of function to invoke from the wscript
		"""
		function_name = name or self.user_function_name()

		# convert to absolute paths
		dirs = to_list(dirs)
		dirs = [x if os.path.isabs(x) else os.path.join(self.curdir, x) for x in dirs]

		for d in dirs:
			wscript_file = os.path.join(d, WSCRIPT_FILE)
			partial_wscript_file = wscript_file + '_' + function_name

			# if there is a partial wscript with the body of the user function,
			# use it in preference
			if os.path.exists(partial_wscript_file):
				exec_dict = {'ctx':self, 'conf':self, 'bld':self, 'opt':self}
				function_code = readf(partial_wscript_file, m='rU')

				self.pre_recurse(function_code, partial_wscript_file, d)
				old_dir = self.curdir
				self.curdir = d
				try:
					exec(function_code, exec_dict)
				except Exception:
					raise WscriptError(traceback.format_exc(), d)
				finally:
					self.curdir = old_dir
				self.post_recurse(function_code, partial_wscript_file, d)

			# if there is only a full wscript file, use a suitably named
			# function from it
			elif os.path.exists(wscript_file):
				# do not catch any exceptions here
				wscript_module = load_module(wscript_file)
				user_function = getattr(wscript_module, function_name, None)
				if not user_function:
					raise WscriptError('No function %s defined in %s'
						% (function_name, wscript_file))
				self.pre_recurse(user_function, wscript_file, d)
				old_dir = self.curdir
				self.curdir = d
				try:
					user_function(self)
				except TypeError:
					user_function()
				finally:
					self.curdir = old_dir
				self.post_recurse(user_function, wscript_file, d)

			# no wscript file - raise an exception
			else:
				raise WscriptError('No wscript file in directory %s' % d)

	def prepare(self):
		"""Executed before the context is passed to the user function."""
		pass

	def run_user_code(self):
		"""Call the user function to which this context is bound."""
		f = getattr(g_module, self.user_function_name(), None)
		if f is None:
			raise WscriptError('Undefined command: %s' % self.user_function_name())
		try:
			f(self)
		except TypeError:
			f()

	def finalize(self):
		"""Executed after the user function finishes."""
		pass

	def execute(self):
		"""Run the command represented by this context."""
		self.prepare()
		self.run_user_code()
		self.finalize()

g_loaded_modules = {}
"""
Dictionary holding already loaded modules, keyed by their absolute path.
private cache
"""
def load_module(file_path, name=WSCRIPT_FILE):
	"""
	Load a Python source file containing user code.
	@type  file_path: string
	@param file_path: Directory of the python file
	@type  name: string
	@param name: Basename of file with user code (default: "wscript")
	@rtype: module
	@return: Loaded Python module
	"""
	try:
		return g_loaded_modules[file_path]
	except KeyError:
		pass

	module = imp.new_module(name)

	try:
		code = readf(file_path, m='rU')
	except (IOError, OSError):
		raise WscriptError('Could not read the file %r' % file_path)

	module.waf_hash_val = code

	module_dir = os.path.dirname(file_path)
	sys.path.insert(0, module_dir)
	try:
		exec(code, module.__dict__)
	except Exception as e:
		try:
			raise WscriptError(traceback.format_exc(), file_path)
		except:
			raise e
	sys.path.remove(module_dir)

	g_loaded_modules[file_path] = module

	return module

def load_tool(tool, tooldir=None):
	"""
	Import the Python module that contains the specified tool from
	the tools directory.
	@type  tool: string
	@param tool: Name of the tool
	@type  tooldir: list
	@param tooldir: List of directories to search for the tool module
	"""
	if tooldir:
		assert isinstance(tooldir, list)
		sys.path = tooldir + sys.path
	try:
		try:
			return __import__(tool)
		except ImportError as e:
			raise WscriptError('Could not load the tool %r in %r' % (tool, sys.path))
	finally:
		if tooldir:
			for d in tooldir:
				sys.path.remove(d)


