#!/usr/bin/env python
# encoding: utf-8
# Tom Wambold tom5760 gmail.com 2009
# Thomas Nagy 2010

"""
go language support

The methods apply_link and apply_incpaths from ccroot.py are re-used
"""

import os, platform

import Utils, Task
from TaskGen import feature, extension, after
from waflib.Tools.ccroot import link_task, static_link

class go(Task.Task):
	run_str = '${GOC} ${GOCFLAGS} ${_INCFLAGS} -o ${TGT} ${SRC}'

class gopackage(static_link):
	run_str = '${GOP} grc ${TGT} ${SRC}'

class goprogram(link_task):
	run_str = '${GOL} ${GOLFLAGS} -o ${TGT} ${SRC}'
	inst_to = '${BINDIR}'

@extension('.go')
def compile_go(self, node):
	return self.create_compiled_task('go', node)

@feature('gopackage', 'goprogram')
@after('process_source', 'apply_incpaths')
def go_local_libs(self):
	names = self.to_list(getattr(self, 'uselib_local', []))
	for name in names:
		tg = self.bld.name_to_obj(name)
		if not tg:
			raise Utils.WafError('no target of name %r necessary for %r in go uselib local' % (name, self))
		tg.post()
		for tsk in self.tasks:
			if isinstance(tsk, go):
				tsk.set_run_after(tg.link_task)
				tsk.deps_nodes.extend(tg.link_task.outputs)
		path = tg.link_task.outputs[0].parent.abspath()
		self.env.append_unique('GOCFLAGS', ['-I%s' % path])
		self.env.append_unique('GOLFLAGS', ['-L%s' % path])

def configure(conf):

	def set_def(var, val):
		if not conf.env[var]:
			conf.env[var] = val

	goarch = os.getenv('GOARCH')
	if goarch == '386':
		set_def('GO_PLATFORM', 'i386')
	elif goarch == 'amd64':
		set_def('GO_PLATFORM', 'x86_64')
	elif goarch == 'arm':
		set_def('GO_PLATFORM', 'arm')
	else:
		set_def('GO_PLATFORM', platform.machine())

	if conf.env.GO_PLATFORM == 'x86_64':
		set_def('GO_COMPILER', '6g')
		set_def('GO_LINKER', '6l')
	elif conf.env.GO_PLATFORM in ['i386', 'i486', 'i586', 'i686']:
		set_def('GO_COMPILER', '8g')
		set_def('GO_LINKER', '8l')
	elif conf.env.GO_PLATFORM == 'arm':
		set_def('GO_COMPILER', '5g')
		set_def('GO_LINKER', '5l')
		set_def('GO_EXTENSION', '.5')

	if not (conf.env.GO_COMPILER or conf.env.GO_LINKER):
		raise conf.fatal('Unsupported platform ' + platform.machine())

	set_def('GO_PACK', 'gopack')
	set_def('gopackage_PATTERN', '%s.a')

	conf.find_program(conf.env.GO_COMPILER, var='GOC')
	conf.find_program(conf.env.GO_LINKER,   var='GOL')
	conf.find_program(conf.env.GO_PACK,     var='GOP')

	# no cgo support unless it stops hardcoding all absolute paths
	# http://groups.google.com/group/golang-nuts/browse_thread/thread/20ff377c05e49a5e?pli=1
	conf.find_program('cgo',                var='CGO')

