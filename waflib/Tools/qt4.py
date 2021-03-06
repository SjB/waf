#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006-2010 (ita)

"""
Qt4 support

If QT4_ROOT is given (absolute path), the configuration will look in it first

This module also demonstrates how to add tasks dynamically (when the build has started)
"""

try:
	from xml.sax import make_parser
	from xml.sax.handler import ContentHandler
except ImportError:
	has_xml = False
	ContentHandler = object
else:
	has_xml = True

import os, sys
from waflib.Tools import c_preproc, cxx
from waflib import TaskGen, Task, Utils, Runner, Options, Node, Errors
from waflib.TaskGen import feature, after, extension
from waflib.Logs import error

MOC_H = ['.h', '.hpp', '.hxx', '.hh']
EXT_RCC = ['.qrc']
EXT_UI  = ['.ui']
EXT_QT4 = ['.cpp', '.cc', '.cxx', '.C']

class qxx(cxx.cxx):
	"""
	Each c++ file may have zero or several .moc files to create.
	They are known only when the files are scanned (preprocessor)
	To avoid scanning the c++ files each time (very slow), the results
	are retrieved from the task cache (bld.node_deps/bld.raw_deps).
	The moc tasks are created dynamically during the build
	"""

	def __init__(self, *k, **kw):
		Task.Task.__init__(self, *k, **kw)
		self.moc_done = 0

	def scan(self):
		"""re-use the c/c++ scanner, but process moc files in a different way"""
		(nodes, names) = c_preproc.scan(self)
		# for some reasons (variants) the moc node may end in the list of node deps
		for x in nodes:
			if x.name.endswith('.moc'):
				nodes.remove(x)
				names.append(x.path_from(self.inputs[0].parent.get_bld()))
		return (nodes, names)

	def runnable_status(self):
		if self.moc_done:
			# if there is a moc task, delay the computation of the file signature
			for t in self.run_after:
				if not t.hasrun:
					return Task.ASK_LATER
			# the moc file enters in the dependency calculation
			# so we need to recompute the signature when the moc file is present
			self.signature()
			return Task.Task.runnable_status(self)
		else:
			# yes, really, there are people who generate cxx files
			for t in self.run_after:
				if not t.hasrun:
					return Task.ASK_LATER
			self.add_moc_tasks()
			return Task.ASK_LATER

	def add_moc_tasks(self):

		node = self.inputs[0]
		bld = self.generator.bld

		try:
			# compute the signature once to know if there is a moc file to create
			self.signature()
		except KeyError:
			# the moc file may be referenced somewhere else
			pass
		else:
			# remove the signature, it must be recomputed with the moc task
			delattr(self, 'cache_sig')

		moctasks=[]
		mocfiles=[]
		try:
			tmp_lst = bld.raw_deps[self.uid()]
			bld.raw_deps[self.uid()] = []
		except KeyError:
			tmp_lst = []
		for d in tmp_lst:
			if not d.endswith('.moc'):
				continue
			# paranoid check
			if d in mocfiles:
				error("paranoia owns")
				continue
			# process that base.moc only once
			mocfiles.append(d)

			# find the extension - this search is done only once
			ext = ''
			try: ext = Options.options.qt_header_ext
			except AttributeError: pass

			if not ext:
				base2 = d[:-4]
				for exth in MOC_H:
					k = node.parent.find_node(base2+exth)
					if k:
						break
				else:
					raise Errors.WafError('no header found for %r which is a moc file' % d)

			# next time we will not search for the extension (look at the 'for' loop below)

			h_node = node.parent.find_resource(base2 + exth)
			m_node = h_node.change_ext('.moc')
			bld.node_deps[(self.inputs[0].parent.abspath(), m_node.name)] = h_node

			# create the task
			task = Task.classes['moc'](env=self.env, generator=self.generator)
			task.set_inputs(h_node)
			task.set_outputs(m_node)

			# direct injection in the build phase (safe because called from the main thread)
			gen = bld.producer
			gen.outstanding.insert(0, task)
			gen.total += 1

			moctasks.append(task)

		# remove raw deps except the moc files to save space (optimization)
		tmp_lst = bld.raw_deps[self.uid()] = mocfiles

		# look at the file inputs, it is set right above
		lst = bld.node_deps.get(self.uid(), ())
		for d in lst:
			name = d.name
			if name.endswith('.moc'):
				task = Task.classes['moc'](env=self.env, generator=self.generator)
				task.set_inputs(bld.node_deps[(self.inputs[0].parent.abspath(), name)]) # 1st element in a tuple
				task.set_outputs(d)

				gen = bld.producer
				gen.outstanding.insert(0, task)
				gen.total += 1

				moctasks.append(task)

		# simple scheduler dependency: run the moc task before others
		self.run_after.update(set(moctasks))
		self.moc_done = 1

	run = Task.classes['cxx'].__dict__['run']

def translation_update(task):
	outs = [a.abspath() for a in task.outputs]
	outs = " ".join(outs)
	lupdate = task.env['QT_LUPDATE']

	for x in task.inputs:
		file = x.abspath()
		cmd = "%s %s -ts %s" % (lupdate, file, outs)
		Logs.pprint('BLUE', cmd)
		task.generator.bld.exec_command(cmd)

class XMLHandler(ContentHandler):
	def __init__(self):
		self.buf = []
		self.files = []
	def startElement(self, name, attrs):
		if name == 'file':
			self.buf = []
	def endElement(self, name):
		if name == 'file':
			self.files.append(str(''.join(self.buf)))
	def characters(self, cars):
		self.buf.append(cars)

@extension(*EXT_RCC)
def create_rcc_task(self, node):
	"hook for rcc files"
	rcnode = node.change_ext('_rc.cpp')
	rcctask = self.create_task('rcc', node, rcnode)
	cpptask = self.create_task('cxx', rcnode, rcnode.change_ext('.o'))
	self.compiled_tasks.append(cpptask)
	return cpptask

@extension(*EXT_UI)
def create_uic_task(self, node):
	"hook for uic tasks"
	uictask = self.create_task('ui4', node)
	uictask.outputs = [self.path.find_or_declare(self.env['ui_PATTERN'] % node.name[:-3])]

@extension('.ts')
def add_lang(self, node):
	"""add all the .ts file into self.lang"""
	self.lang = self.to_list(getattr(self, 'lang', [])) + [node]

@feature('qt4')
@after('apply_link')
def apply_qt4(self):
	if getattr(self, 'lang', None):
		update = getattr(self, 'update', None)
		lst=[]
		trans=[]
		for l in self.to_list(self.lang):

			if not isinstance(l, Node.Node):
				l = self.path.find_resource(l+'.ts')

			t = self.create_task('ts2qm', l, l.change_ext('.qm'))
			lst.append(t.outputs[0])

			if update:
				trans.append(t.inputs[0])

		if update and Options.options.trans_qt4:
			# we need the cpp files given, except the rcc task we create after
			# FIXME may be broken
			u = Task.TaskCmd(translation_update, self.env, 2)
			u.inputs = [a.inputs[0] for a in self.compiled_tasks]
			u.outputs = trans

		if getattr(self, 'langname', None):
			t = Task.classes['qm2rcc'](self.env)
			t.set_inputs(lst)
			t.set_outputs(self.path.find_or_declare(self.langname+'.qrc'))
			t.path = self.path
			k = create_rcc_task(self, t.outputs[0])
			self.link_task.inputs.append(k.outputs[0])

	lst = []
	for flag in self.to_list(self.env['CXXFLAGS']):
		if len(flag) < 2: continue
		if flag[0:2] == '-D' or flag[0:2] == '-I':
			lst.append(flag)
	self.env['MOC_FLAGS'] = lst

@extension(*EXT_QT4)
def cxx_hook(self, node):
	return self.create_compiled_task('qxx', node)

class rcc(Task.Task):
	color   = 'BLUE'
	run_str = '${QT_RCC} -name ${SRC[0].name} ${SRC[0].abspath()} ${RCC_ST} -o ${TGT}'
	ext_out = ['.h']

	def scan(self):
		"""add the dependency on the files referenced in the qrc"""
		node = self.inputs[0]
		parser = make_parser()
		curHandler = XMLHandler()
		parser.setContentHandler(curHandler)
		fi = open(self.inputs[0].abspath())
		parser.parse(fi)
		fi.close()

		nodes = []
		names = []
		root = self.inputs[0].parent
		for x in curHandler.files:
			nd = root.find_resource(x)
			if nd: nodes.append(nd)
			else: names.append(x)
		return (nodes, names)

class moc(Task.Task):
	color   = 'BLUE'
	run_str = '${QT_MOC} ${MOC_FLAGS} ${SRC} ${MOC_ST} ${TGT}'

class ui4(Task.Task):
	color   = 'BLUE'
	run_str = '${QT_UIC} ${SRC} -o ${TGT}'
	ext_out = ['.h']

class ts2qm(Task.Task):
	color   = 'BLUE'
	run_str = '${QT_LRELEASE} ${QT_LRELEASE_FLAGS} ${SRC} -qm ${TGT}'

class qm2rcc(Task.Task):
	color = 'BLUE'
	after = 'ts2qm'
	before = 'rcc'

	def process_qm2rcc(self):
		"""TODO try to see if it works"""
		txt = '\n'.join(['<file>%s</file>' % k.path_from(self.path) for k in self.inputs])
		code = '<!DOCTYPE RCC><RCC version="1.0">\n<qresource>\n%s\n</qresource>\n</RCC>' % txt
		task.outputs[0].write(code)

#Task.task_factory('qm2rcc', vars=[], func=process_qm2rcc, color='BLUE', before='rcc', after='ts2qm')

def configure(self):
	env = self.env
	opt = Options.options

	qtdir = getattr(opt, 'qtdir', '')
	qtbin = getattr(opt, 'qtbin', '')
	qtlibs = getattr(opt, 'qtlibs', '')
	useframework = getattr(opt, 'use_qt4_osxframework', True)

	paths = []

	# the path to qmake has been given explicitely
	if qtbin:
		paths = [qtbin]

	# the qt directory has been given - we deduce the qt binary path
	if not qtdir:
		qtdir = self.environ.get('QT4_ROOT', '')
		qtbin = os.path.join(qtdir, 'bin')
		paths = [qtbin]

	# no qtdir, look in the path and in /usr/local/Trolltech
	if not qtdir:
		paths = os.environ.get('PATH', '').split(os.pathsep)
		paths.append('/usr/share/qt4/bin/')
		try:
			lst = os.listdir('/usr/local/Trolltech/')
		except OSError:
			pass
		else:
			if lst:
				lst.sort()
				lst.reverse()

				# keep the highest version
				qtdir = '/usr/local/Trolltech/%s/' % lst[0]
				qtbin = os.path.join(qtdir, 'bin')
				paths.append(qtbin)

	# at the end, try to find qmake in the paths given
	# keep the one with the highest version
	cand = None
	prev_ver = ['4', '0', '0']
	for qmk in ['qmake-qt4', 'qmake4', 'qmake']:
		try:
			qmake = self.find_program(qmk, path_list=paths)
		except self.errors.ConfigurationError:
			pass
		else:
			try:
				version = self.cmd_and_log([qmake, '-query', 'QT_VERSION']).strip()
			except self.errors.ConfigurationError:
				pass
			else:
				if version:
					new_ver = version.split('.')
					if new_ver > prev_ver:
						cand = qmake
						prev_ver = new_ver
	if cand:
		qmake = cand
	else:
		self.fatal('could not find qmake for qt4')

	self.env.QMAKE = qmake
	qtincludes = self.cmd_and_log([qmake, '-query', 'QT_INSTALL_HEADERS']).strip()
	qtdir = self.cmd_and_log([qmake, '-query', 'QT_INSTALL_PREFIX']).strip() + os.sep
	qtbin = self.cmd_and_log([qmake, '-query', 'QT_INSTALL_BINS']).strip() + os.sep

	if not qtlibs:
		try:
			qtlibs = self.cmd_and_log([qmake, '-query', 'QT_INSTALL_LIBS']).strip()
		except Errors.WafError:
			qtlibs = os.path.join(qtdir, 'lib')

	def find_bin(lst, var):
		for f in lst:
			try:
				ret = self.find_program(f, path_list=paths)
			except self.errors.ConfigurationError:
				pass
			else:
				env[var]=ret
				break

	find_bin(['uic-qt3', 'uic3'], 'QT_UIC3')
	find_bin(['uic-qt4', 'uic'], 'QT_UIC')
	if not env['QT_UIC']:
		self.fatal('cannot find the uic compiler for qt4')

	try:
		version = self.cmd_and_log(env['QT_UIC'] + " -version 2>&1").strip()
	except self.errors.ConfigurationError:
		self.fatal('your uic compiler is for qt3, add uic for qt4 to your path')

	version = version.replace('Qt User Interface Compiler ','')
	version = version.replace('User Interface Compiler for Qt', '')
	if version.find(' 3.') != -1:
		self.msg('Checking for uic version', '(%s: too old)' % version, False)
		self.fatal('uic is too old')
	self.msg('Checking for uic version', '(%s)'%version)

	find_bin(['moc-qt4', 'moc'], 'QT_MOC')
	find_bin(['rcc'], 'QT_RCC')
	find_bin(['lrelease-qt4', 'lrelease'], 'QT_LRELEASE')
	find_bin(['lupdate-qt4', 'lupdate'], 'QT_LUPDATE')

	env['UIC3_ST']= '%s -o %s'
	env['UIC_ST'] = '%s -o %s'
	env['MOC_ST'] = '-o'
	env['ui_PATTERN'] = 'ui_%s.h'
	env['QT_LRELEASE_FLAGS'] = ['-silent']

	vars = "QtCore QtGui QtUiTools QtNetwork QtOpenGL QtSql QtSvg QtTest QtXml QtWebKit Qt3Support".split()
	vars_debug = [a+'_debug' for a in vars]

	if not 'PKG_CONFIG_PATH' in os.environ:
		os.environ['PKG_CONFIG_PATH'] = '%s:%s/pkgconfig:/usr/lib/qt4/lib/pkgconfig:/opt/qt4/lib/pkgconfig:/usr/lib/qt4/lib:/opt/qt4/lib pkg-config --silence-errors' % (qtlibs, qtlibs)

	pkgconfig = env['pkg-config'] or 'pkg-config'
	for i in vars_debug+vars:
		try:
			self.check_cfg(package=i, args='--cflags --libs', path=pkgconfig)
		except self.errors.ConfigurationError:
			pass

	# the libpaths make really long command-lines
	# remove the qtcore ones from qtgui, etc
	def process_lib(vars_, coreval):
		for d in vars_:
			var = d.upper()
			if var == 'QTCORE':
				continue

			value = env['LIBPATH_'+var]
			if value:
				core = env[coreval]
				accu = []
				for lib in value:
					if lib in core:
						continue
					accu.append(lib)
				env['LIBPATH_'+var] = accu

	process_lib(vars, 'LIBPATH_QTCORE')
	process_lib(vars_debug, 'LIBPATH_QTCORE_DEBUG')

	# rpath if wanted
	if Options.options.want_rpath:
		def process_rpath(vars_, coreval):
			for d in vars_:
				var = d.upper()
				value = env['LIBPATH_'+var]
				if value:
					core = env[coreval]
					accu = []
					for lib in value:
						if var != 'QTCORE':
							if lib in core:
								continue
						accu.append('-Wl,--rpath='+lib)
					env['RPATH_'+var] = accu
		process_rpath(vars, 'LIBPATH_QTCORE')
		process_rpath(vars_debug, 'LIBPATH_QTCORE_DEBUG')

def options(opt):
	opt.add_option('--want-rpath', action='store_true', default=False, dest='want_rpath', help='enable the rpath for qt libraries')

	opt.add_option('--header-ext',
		type='string',
		default='',
		help='header extension for moc files',
		dest='qt_header_ext')

	for i in 'qtdir qtbin qtlibs'.split():
		opt.add_option('--'+i, type='string', default='', dest=i)

	if sys.platform == "darwin":
		opt.add_option('--no-qt4-framework', action="store_false", help='do not use the framework version of Qt4 in OS X', dest='use_qt4_osxframework',default=True)

	opt.add_option('--translate', action="store_true", help="collect translation strings", dest="trans_qt4", default=False)

