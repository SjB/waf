#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006-2010 (ita)
# Ralf Habacker, 2006 (rh)

import os
from waflib import Utils
from waflib.Tools import ccroot, ar
from waflib.Configure import conf

@conf
def find_sxx(conf):
	v = conf.env
	cc = None
	if v['CXX']: cc = v['CXX']
	elif 'CXX' in conf.environ: cc = conf.environ['CXX']
	#if not cc: cc = conf.find_program('g++', var='CXX')
	if not cc: cc = conf.find_program('c++', var='CXX')
	if not cc: cc = conf.find_program('CC', var='CXX') #studio
	if not cc: conf.fatal('sunc++ was not found')

	# TODO FIXME the detection in suncc seems to do more than this

	v['CXX']  = cc
	v['CXX_NAME'] = 'sun'

@conf
def sxx_common_flags(conf):
	v = conf.env

	v['CXX_SRC_F']           = ''
	v['CXX_TGT_F']           = ['-c', '-o', '']

	# linker
	if not v['LINK_CXX']: v['LINK_CXX'] = v['CXX']
	v['CXXLNK_SRC_F']        = ''
	v['CXXLNK_TGT_F']        = ['-o', ''] # solaris hack, separate the -o from the target
	v['CPPPATH_ST'] = '-I%s'
	v['DEFINES_ST'] = '-D%s'

	v['LIB_ST']              = '-l%s' # template for adding libs
	v['LIBPATH_ST']          = '-L%s' # template for adding libpaths
	v['STLIB_ST']        = '-l%s'
	v['STLIBPATH_ST']    = '-L%s'

	v['SONAME_ST']           = '-Wl,-h,%s'
	v['SHLIB_MARKER']        = '-Bdynamic'
	v['STLIB_MARKER']    = '-Bstatic'

	# program
	v['cxxprogram_PATTERN']     = '%s'

	# shared library
	v['CXXFLAGS_cxxshlib']      = ['-Kpic', '-DPIC']
	v['LINKFLAGS_cxxshlib']     = ['-G']
	v['cxxshlib_PATTERN']       = 'lib%s.so'

	# static lib
	v['LINKFLAGS_cxxstlib'] = ['-Bstatic']
	v['cxxstlib_PATTERN']   = 'lib%s.a'

configure = '''
find_sxx
find_ar
sxx_common_flags
cxx_load_tools
cxx_add_flags
link_add_flags
'''
