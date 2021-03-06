#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006 (ita)

"""TeX/LaTeX/PDFLaTeX/XeLaTeX support

Variables passed to bld():

* type -- tex compiler type to use

  type: string, in ["latex", "pdflatex", "xelatex"]
  
  default: pdflatex
  
* prompt -- whether to prompt for errors or use batch mode

  type: boolean

"""

import os, re
from waflib import Utils, Task, Runner, Build, Errors
from waflib.TaskGen import feature, before
from waflib.Logs import error, warn, debug

re_bibunit = re.compile(r'\\(?P<type>putbib)\[(?P<file>[^\[\]]*)\]',re.M)
def bibunitscan(self):
	node = self.inputs[0]
	env = self.env

	nodes = []
	if not node: return nodes

	code = Utils.readf(node.abspath())

	for match in re_bibunit.finditer(code):
		path = match.group('file')
		if path:
			for k in ['', '.bib']:
				# add another loop for the tex include paths?
				debug('tex: trying %s%s' % (path, k))
				fi = node.parent.find_resource(path + k)
				if fi:
					nodes.append(fi)
					# no break, people are crazy
			else:
				debug('tex: could not find %s' % path)

	debug("tex: found the following bibunit files: %s" % nodes)
	return nodes

exts_deps_tex = ['', '.ltx', '.tex', '.bib', '.pdf', '.png', '.eps', '.ps']
re_tex = re.compile(r'\\(?P<type>include|bibliography|putbib|includegraphics|input|import|bringin|lstinputlisting)(\[[^\[\]]*\])?{(?P<file>[^{}]*)}',re.M)
g_bibtex_re = re.compile('bibdata', re.M)

class tex(Task.Task):

	bibtex_fun, _ = Task.compile_fun('${BIBTEX} ${BIBTEXFLAGS} ${SRCFILE}', shell=False)
	makeindex_fun, _ = Task.compile_fun('${MAKEINDEX} ${MAKEINDEXFLAGS} ${SRCFILE}', shell=False)

	def scan(self):
		"""
		A simple regex-based scanner for latex dependencies, uses re_tex from above

		Depending on your needs you might want:

		* to change re_tex

		::

			from waflib.Tools import tex
			tex.re_tex = myregex

		* or to change the method scan from the latex tasks

		::

			from waflib.Task import classes
			classes['latex'].scan = myscanfunction

		"""
		node = self.inputs[0]
		env = self.env

		nodes = []
		names = []
		seen = []
		if not node: return (nodes, names)

		def parse_node(node):
			if node in seen:
				return
			seen.append(node
)
			code = node.read()
			global re_tex
			for match in re_tex.finditer(code):
				path = match.group('file')
				if path:
					add_name = True
					found = None
					for k in exts_deps_tex:
						debug('tex: trying %s%s' % (path, k))
						found = node.parent.find_resource(path + k)
						if found:
							nodes.append(found)
							add_name = False
							if found.name.endswith('.tex') or found.name.endswith('.ltx'):
								parse_node(found)
						# no break, people are crazy
					if add_name:
						names.append(path)
		parse_node(node)

		for x in nodes:
			x.parent.get_bld().mkdir()

		debug("tex: found the following : %s and names %s" % (nodes, names))
		return (nodes, names)

	def check_status(self, msg, retcode):
		if retcode != 0:
			raise Errors.WafError("%r command exit status %r" % (msg, retcode))

	def bibfile(self):
		"""look in the .aux file if there is a bibfile to process"""
		try:
			ct = self.aux_node.read()
		except (OSError, IOError):
			error('error bibtex scan')
		else:
			fo = g_bibtex_re.findall(ct)

			# there is a .aux file to process
			if fo:
				warn('calling bibtex')

				self.env.env = {}
				self.env.env.update(os.environ)
				self.env.env.update({'BIBINPUTS': self.TEXINPUTS, 'BSTINPUTS': self.TEXINPUTS})
				self.env.SRCFILE = self.aux_node.name[:-4]
				self.check_status('error when calling bibtex', self.bibtex_fun())

	def bibunits(self):
		"""look to see if there are any bibunit-style bib files"""
		try:
			bibunits = bibunitscan(self)
		except FSError:
			error('error bibunitscan')
		else:
			if bibunits:
				fn  = ['bu' + str(i) for i in xrange(1, len(bibunits) + 1)]
				if fn:
					warn('calling bibtex on bibunits')

				for f in fn:
					self.env.env = {'BIBINPUTS': self.TEXINPUTS, 'BSTINPUTS': self.TEXINPUTS}
					self.env.SRCFILE = f
					self.check_status('error when calling bibtex', self.bibtex_fun())

	def makeindex(self):
		"""look on the filesystem if there is a .idx file to process"""
		try:
			idx_path = self.idx_node.abspath()
			os.stat(idx_path)
		except OSError:
			warn('index file %s absent, not calling makeindex' % idx_path)
		else:
			warn('calling makeindex')

			self.env.SRCFILE = self.idx_node.name
			self.env.env = {}
			self.check_status('error when calling makeindex %s' % idx_path, self.makeindex_fun())

	def run(self):
		"""
		Runs the LaTeX build process.

		TeX file processing may need multiple passes, depending on the
		usage of cross-references, bibliographies, content susceptible of
		needing such passes.
		The appropriate TeX compiler is called until the .aux file ceases
		changing.

		Makeindex and bibtex are called if necessary.

		"""
		env = self.env
		bld = self.generator.bld

		if not env['PROMPT_LATEX']:
			env.append_value('LATEXFLAGS', '-interaction=batchmode')
			env.append_value('PDFLATEXFLAGS', '-interaction=batchmode')
			env.append_value('XELATEXFLAGS', '-interaction=batchmode')

		fun = self.texfun

		node = self.inputs[0]
		srcfile = node.abspath()
		self.TEXINPUTS = node.parent.get_bld().abspath() + os.pathsep + node.parent.get_src().abspath() + os.pathsep

		self.aux_node = node.change_ext('.aux')
		self.idx_node = node.change_ext('.idx')

		# important, set the cwd for everybody
		self.cwd = self.inputs[0].parent.get_bld().abspath()

		warn('first pass on %s' % self.__class__.__name__)

		self.env.env = {}
		self.env.env.update(os.environ)
		self.env.env.update({'TEXINPUTS': self.TEXINPUTS})
		self.env.SRCFILE = srcfile
		self.check_status('error when calling latex', fun())

		self.bibfile()
		self.bibunits()
		self.makeindex()

		hash = ''
		for i in range(10):
			# prevent against infinite loops - one never knows

			# watch the contents of file.aux and stop if file.aux does not change anymore
			prev_hash = hash
			try:
				hash = Utils.h_file(self.aux_node.abspath())
			except KeyError:
				error('could not read aux.h -> %s' % self.aux_node.abspath())
				pass
			if hash and hash == prev_hash:
				break

			# run the command
			warn('calling %s' % self.__class__.__name__)

			self.env.env = {}
			self.env.env.update(os.environ)
			self.env.env.update({'TEXINPUTS': self.TEXINPUTS})
			self.env.SRCFILE = srcfile
			self.check_status('error when calling %s' % self.__class__.__name__, fun())

class latex(tex):
	texfun, vars = Task.compile_fun('${LATEX} ${LATEXFLAGS} ${SRCFILE}', shell=False)
class pdflatex(tex):
	texfun, vars =  Task.compile_fun('${PDFLATEX} ${PDFLATEXFLAGS} ${SRCFILE}', shell=False)
class xelatex(tex):
	texfun, vars = Task.compile_fun('${XELATEX} ${XELATEXFLAGS} ${SRCFILE}', shell=False)

b = Task.task_factory
b('dvips', '${DVIPS} ${DVIPSFLAGS} ${SRC} -o ${TGT}', color='BLUE', after=["latex", "pdflatex", "tex", "bibtex"], shell=False)
b('dvipdf', '${DVIPDF} ${DVIPDFFLAGS} ${SRC} ${TGT}', color='BLUE', after=["latex", "pdflatex", "tex", "bibtex"], shell=False)
b('pdf2ps', '${PDF2PS} ${PDF2PSFLAGS} ${SRC} ${TGT}', color='BLUE', after=["dvipdf", "xelatex", "pdflatex"], shell=False)

@feature('tex')
@before('process_source')
def apply_tex(self):
	if not getattr(self, 'type', None) in ['latex', 'pdflatex', 'xelatex']:
		self.type = 'pdflatex'

	tree = self.bld
	outs = Utils.to_list(getattr(self, 'outs', []))

	# prompt for incomplete files (else the batchmode is used)
	self.env['PROMPT_LATEX'] = getattr(self, 'prompt', 1)

	deps_lst = []

	if getattr(self, 'deps', None):
		deps = self.to_list(self.deps)
		for filename in deps:
			n = self.path.find_resource(filename)
			if not n in deps_lst: deps_lst.append(n)

	for node in self.to_nodes(self.source):

		if self.type == 'latex':
			task = self.create_task('latex', node, node.change_ext('.dvi'))
		elif self.type == 'pdflatex':
			task = self.create_task('pdflatex', node, node.change_ext('.pdf'))
		elif self.type == 'xelatex':
			task = self.create_task('xelatex', node, node.change_ext('.pdf'))

		task.env = self.env

		# add the manual dependencies
		if deps_lst:
			try:
				lst = tree.node_deps[task.uid()]
				for n in deps_lst:
					if not n in lst:
						lst.append(n)
			except KeyError:
				tree.node_deps[task.uid()] = deps_lst

		if self.type == 'latex':
			if 'ps' in outs:
				tsk = self.create_task('dvips', task.outputs, node.change_ext('.ps'))
				tsk.env.env = {'TEXINPUTS' : node.parent.abspath() + os.pathsep + self.path.abspath() + os.pathsep + self.path.get_bld().abspath()}
			if 'pdf' in outs:
				tsk = self.create_task('dvipdf', task.outputs, node.change_ext('.pdf'))
				tsk.env.env = {'TEXINPUTS' : node.parent.abspath() + os.pathsep + self.path.abspath() + os.pathsep + self.path.get_bld().abspath()}
		elif self.type == 'pdflatex':
			if 'ps' in outs:
				self.create_task('pdf2ps', task.outputs, node.change_ext('.ps'))
	self.source = []

def configure(self):
	v = self.env
	for p in 'tex latex pdflatex xelatex bibtex dvips dvipdf ps2pdf makeindex pdf2ps'.split():
		try:
			self.find_program(p, var=p.upper())
		except self.errors.ConfigurationError:
			pass
	v['DVIPSFLAGS'] = '-Ppdf'


