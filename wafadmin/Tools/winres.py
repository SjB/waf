#! /usr/bin/env python
# encoding: utf-8
# Brant Young, 2007

"This hook is called when the class cpp/cc task generator encounters a '.rc' file: X{.rc -> [.res|.rc.o]}"

import os, sys
import TaskGen, Task
from Utils import quote_whitespace
from TaskGen import extension

EXT_WINRC = ['.rc']

winrc_str = '${WINRC} ${_CPPDEFFLAGS} ${_CXXDEFFLAGS} ${_CCDEFFLAGS} ${WINRCFLAGS} ${_CPPINCFLAGS} ${_CXXINCFLAGS} ${_CCINCFLAGS} ${WINRC_TGT_F}${TGT} ${WINRC_SRC_F}${SRC}'

@extension(EXT_WINRC)
def rc_file(self, node):
	obj_ext = '.rc.o'
	if self.env['WINRC_TGT_F'] == '/fo ': obj_ext = '.res'

	rctask = self.create_task('winrc')
	rctask.set_inputs(node)
	rctask.set_outputs(node.change_ext(obj_ext))

	# make linker can find compiled resource files
	self.compiled_tasks.append(rctask)

# create our action, for use with rc file
Task.simple_task_type('winrc', winrc_str, color='BLUE', prio=40)

def detect(conf):
	v = conf.env

	cc = os.path.basename(''.join(v['CC']).lower())
	cxx = os.path.basename(''.join(v['CXX']).lower())

	# find rc.exe
	if cc in ['gcc', 'cc', 'g++', 'c++']:
		winrc = conf.find_program('windres', var='WINRC')
		v['WINRC_TGT_F'] = '-o '
		v['WINRC_SRC_F'] = '-i '
	elif cc == 'cl.exe' or cxx == 'cl.exe':
		winrc = conf.find_program('RC', var='WINRC')
		v['WINRC_TGT_F'] = '/fo '
		v['WINRC_SRC_F'] = ' '
	else:
		return 0

	if not winrc:
		conf.fatal('winrc was not found!!')
	else:
		v['WINRC'] = quote_whitespace(winrc)

	v['WINRCFLAGS'] = ''

