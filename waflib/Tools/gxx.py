#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006-2010 (ita)
# Ralf Habacker, 2006 (rh)
# Yinon Ehrlich, 2009

import os, sys
from waflib import Configure, Options, Utils
from waflib.Tools import ccroot, ar
from waflib.Configure import conf

@conf
def find_gxx(conf):
	cxx = conf.find_program(['g++', 'c++'], var='CXX')
	cxx = conf.cmd_to_list(cxx)
	conf.get_cc_version(cxx, gcc=True)
	conf.env.CXX_NAME = 'gcc'
	conf.env.CXX      = cxx

@conf
def gxx_common_flags(conf):
	v = conf.env

	# CPPFLAGS DEFINES _CXXINCFLAGS _CXXDEFFLAGS
	v['CXXFLAGS_DEBUG'] = ['-g']
	v['CXXFLAGS_RELEASE'] = ['-O2']

	v['CXX_SRC_F']           = ''
	v['CXX_TGT_F']           = ['-c', '-o', ''] # shell hack for -MD

	# linker
	if not v['LINK_CXX']: v['LINK_CXX'] = v['CXX']
	v['CXXLNK_SRC_F']        = ''
	v['CXXLNK_TGT_F']        = ['-o', ''] # shell hack for -MD

	v['LIB_ST']              = '-l%s' # template for adding libs
	v['LIBPATH_ST']          = '-L%s' # template for adding libpaths
	v['STATICLIB_ST']        = '-l%s'
	v['STATICLIBPATH_ST']    = '-L%s'
	v['RPATH_ST']            = '-Wl,-rpath,%s'
	v['DEFINES_ST']       = '-D%s'

	v['SONAME_ST']           = '-Wl,-h,%s'
	v['SHLIB_MARKER']        = '-Wl,-Bdynamic'
	v['STATICLIB_MARKER']    = '-Wl,-Bstatic'
	v['FULLSTATIC_MARKER']   = '-static'

	# program
	v['program_PATTERN']     = '%s'

	# shared library
	v['shlib_CXXFLAGS']      = ['-fPIC']
	v['shlib_LINKFLAGS']     = ['-shared']
	v['shlib_PATTERN']       = 'lib%s.so'

	# static lib
	v['stlib_LINKFLAGS'] = ['-Wl,-Bstatic']
	v['stlib_PATTERN']   = 'lib%s.a'

	# osx stuff
	v['LINKFLAGS_MACBUNDLE'] = ['-bundle', '-undefined', 'dynamic_lookup']
	v['CCFLAGS_MACBUNDLE']   = ['-fPIC']
	v['macbundle_PATTERN']   = '%s.bundle'

@conf
def gxx_modifier_win32(conf):
	v = conf.env
	v['program_PATTERN']     = '%s.exe'

	v['shlib_PATTERN']       = '%s.dll'
	v['implib_PATTERN']      = 'lib%s.dll.a'
	v['IMPLIB_ST']           = '-Wl,--out-implib,%s'

	dest_arch = v['DEST_CPU']
	v['shlib_CXXFLAGS'] = []

	v.append_value('shlib_CXXFLAGS', '-DDLL_EXPORT') # TODO adding nonstandard defines like this DLL_EXPORT is not a good idea

	# Auto-import is enabled by default even without this option,
	# but enabling it explicitly has the nice effect of suppressing the rather boring, debug-level messages
	# that the linker emits otherwise.
	v.append_value('LINKFLAGS', '-Wl,--enable-auto-import')

@conf
def gxx_modifier_cygwin(conf):
	gxx_modifier_win32(conf)
	v = conf.env
	v['shlib_PATTERN']       = 'cyg%s.dll'
	v.append_value('shlib_LINKFLAGS', '-Wl,--enable-auto-image-base')

@conf
def gxx_modifier_darwin(conf):
	v = conf.env
	v['shlib_CXXFLAGS']      = ['-fPIC', '-compatibility_version', '1', '-current_version', '1']
	v['shlib_LINKFLAGS']     = ['-dynamiclib']
	v['shlib_PATTERN']       = 'lib%s.dylib'

	v['stlib_LINKFLAGS'] = []

	v['SHLIB_MARKER']        = ''
	v['STATICLIB_MARKER']    = ''
	v['SONAME_ST']		 = ''

@conf
def gxx_modifier_aix(conf):
	v = conf.env
	v['program_LINKFLAGS']   = ['-Wl,-brtl']

	v['shlib_LINKFLAGS']     = ['-shared', '-Wl,-brtl,-bexpfull']

	v['SHLIB_MARKER']        = ''

@conf
def gxx_modifier_platform(conf):
	# * set configurations specific for a platform.
	# * the destination platform is detected automatically by looking at the macros the compiler predefines,
	#   and if it's not recognised, it fallbacks to sys.platform.
	dest_os = conf.env['DEST_OS'] or Utils.unversioned_sys_platform()
	gxx_modifier_func = globals().get('gxx_modifier_' + dest_os)
	if gxx_modifier_func:
			gxx_modifier_func(conf)

def configure(conf):
	conf.find_gxx()
	conf.find_ar()
	conf.gxx_common_flags()
	conf.gxx_modifier_platform()
	conf.cxx_load_tools()
	conf.cxx_add_flags()
