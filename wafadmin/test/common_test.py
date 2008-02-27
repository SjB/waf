#! /usr/bin/env python
# encoding: utf-8
# Yinon Ehrlich, 2008

"""
Should be serve as common tester for all waf testers.
"""
import os, sys, unittest, shutil, types

# allow importing from wafadmin dir when ran from sub-directory 
sys.path.append(os.path.abspath(os.path.pardir))
import pproc
import Environment
import Options
from Constants import *


class StartupError(Exception):
	pass

class CommonTester(unittest.TestCase):

	def __init__(self, methodName):
		self._waf_root_dir=os.getcwd()
		self._waf_exe = os.path.join(self._waf_root_dir, "waf")

		# validate current dir is waf directory
		self.validate_waf_path_exist(self._waf_root_dir)
		self.validate_waf_path_exist("waf-light")
		unittest.TestCase.__init__(self, methodName)
		
	def validate_waf_path_exist(self, file_or_directory):
		"""
		raise StartupError if specified file_or_directory not exists
		""" 
		if not os.path.exists(file_or_directory):
			raise StartupError("cannot find '%s', please run tests from waf root directory." % file_or_directory)

	def call(self, commands):
		"""
		call: subprocess call method with (by default) silent stdout and stderr,
				test its return value to make sure it succeeded"
		@param commands [list] commands to run.
		@return: return code that was returned by child process. 
		"""
		kwargs = dict()
		
		# Don't show output, comment-out this line when need to check-out what went wrong...
		kwargs['stdout'] = kwargs['stderr'] = pproc.PIPE
		return pproc.call( commands, **kwargs)
	
	def _copy(self, source, target):
		"""
		"generic" way to copy files/directories. Target must not already exist.
		"""
		if os.path.isfile(source):
			shutil.copy2(source, target)
		else:
			# When copying directory to another directory using shutil.copytree, the directory 
			# name of the source is NOT created in the target 
			src_dirname = os.path.split(source)[-1]
			target_dirname = os.path.split(target)[-1] 
			if src_dirname != target_dirname:
				target = os.path.join(target, src_dirname)
				
			shutil.copytree(source, target)

	def _test_configure(self, test_for_success=True, additionalArgs=[]):
		"""
		test configure
		@param test_for_success [boolean]: test for success/failure ?
			for example: to make sure configure has failed, pass False.
		@param additionalArgs [list]: optional additional arguments to configure.
		"""
		if not isinstance(test_for_success, types.BooleanType):
			raise ValueError("test_for_success must be boolean")

		if not isinstance(additionalArgs, list):
			raise ValueError("additional args must be a list")
		
		if test_for_success:
			test_func = self.failIf # ret val of 0 is False...
			err_msg = "configure failed"
		else:
			test_func = self.assert_ # ret val of NON-Zero is True...
			err_msg = "configure should fail"
			
		args_list = ["python", self._waf_exe, "configure"]
		if additionalArgs: args_list.extend(list(additionalArgs))
		test_func(self.call(args_list), err_msg)

	def _test_build(self, test_for_success=True, additionalArgs=[]):
		"""
		test build
		@param test_for_success [boolean]: test for success/failure ?
			for example: to make sure build has failed, pass False.
		@param additionalArgs [list]: optional additional arguments to build.
		"""
		if not isinstance(additionalArgs, list):
			raise ValueError("additional args must be a list")
		
		if test_for_success:
			test_func = self.failIf # ret val of 0 is False...
			err_msg = "build failed"
		else:
			test_func = self.assert_ # ret val of NON-Zero is True...
			err_msg = "build should fail"
			
		args_list = ["python", self._waf_exe, "build"]
		if additionalArgs: args_list.extend(list(additionalArgs))
		test_func(self.call(args_list), err_msg)

	def _test_run(self, *args_list):
		"""
		test running the generated executable succeed
		@param expected_ret_val [int]: the expected return value of this run,
			by default: 0 (means successful running)  
		@param additionalArgs [tuple]: optional additional arguments
		"""
		self.assertEqual(0, self.call(args_list), "running '%s' failed" % args_list )
		
	def _test_distclean(self, *additionalArgs):
		"""
		test distclean
		@param additionalArgs [tuple]: optional additional arguments
		"""
		args_list = ["python", self._waf_exe, "distclean"]
		if additionalArgs: args_list.extend(list(additionalArgs))
		self.assertEqual(0, self.call(args_list), "distclean failed" )

	def _same_env(self, expected_env, env_name='default'):
		"""
		All parameters decided upon configure are written to cache, then read on build. 
		This function checks that the written environment has the same values for keys given by expected_env
		@param expected_env [dictionary]: a dictionary that contains
					one or more key-value pairs to compare to stored environment
		@return: True if values the same,
				False otherwise
		"""
		if expected_env is None or not expected_env:
			raise ValueError("env must contains at least one key-value pair")
		else:
#			# Environment uses arguments defined by Options 
			opt_obj = Options.Handler()
			opt_obj.parse_args()
			
			stored_env = Environment.Environment()
			stored_env_path = os.path.join(self._blddir, CACHE_DIR, env_name+CACHE_SUFFIX)
			stored_env.load( stored_env_path )
			for key in expected_env:
				self.assertEqual( stored_env[key], expected_env[key], 
								"values of '%s' differ: expected = '%s', stored = '%s'" 
								% (key,expected_env[key], stored_env[key]))
