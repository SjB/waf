#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005 (ita)

"base for all c/c++ programs and libraries"

import sys, re, os

# since Python 2.5, hashlib replaces deprecated md5, see: http://docs.python.org/lib/module-md5.html
try: from hashlib import md5
except ImportError: from md5 import md5

import Action, Object, Params, Scan, Common, Utils
from Params import error, debug, fatal, warning

g_prio_link=101
"""default priority for link tasks:
an odd number means one link at a time (no parallelization)"""

g_src_file_ext = ['.c', '.cpp', '.cc']
"default extensions for source files"

def trimquotes(s):
	if not s: return ''
	s = s.rstrip()
	if s[0] == "'" and s[-1] == "'": return s[1:-1]
	return s

class c_scanner(Scan.scanner):
	"scanner for c/c++ files"
	def __init__(self):
		Scan.scanner.__init__(self)

	def scan(self, task, node):
		"look for .h the .cpp need"
		debug("_scan_preprocessor(self, node, env, path_lst)", 'ccroot')
		import preproc
		gruik = preproc.cparse(nodepaths = task.path_lst, defines = task.defines)
		gruik.start(node, task.m_env)
		if Params.g_verbose:
			debug("nodes found for %s: %s %s" % (str(node), str(gruik.m_nodes), str(gruik.m_names)), 'deps')
			debug("deps found for %s: %s" % (str(node), str(gruik.deps)), 'deps')
		return (gruik.m_nodes, gruik.m_names)

g_c_scanner = c_scanner()
"scanner for c programs"


def read_la_file(path):
	sp = re.compile(r'^([^=]+)=\'(.*)\'$')
	dc={}
	file = open(path, "r")
	for line in file.readlines():
		try:
			#print sp.split(line.strip())
			_, left, right, _ = sp.split(line.strip())
			dc[left]=right
		except:
			pass
	file.close()
	return dc

# fake libtool files
fakelibtool_vardeps = ['CXX', 'PREFIX']
def fakelibtool_build(task):
	# Writes a .la file, used by libtool
	dest  = open(task.m_outputs[0].abspath(task.m_env), 'w')
	sname = task.m_inputs[0].m_name
	fu = dest.write
	fu("# Generated by ltmain.sh - GNU libtool 1.5.18 - (pwn3d by BKsys II code name WAF)\n")
	if task.m_env['vnum']:
		nums=task.m_env['vnum'].split('.')
		libname = task.m_inputs[0].m_name
		name3 = libname+'.'+task.m_env['vnum']
		name2 = libname+'.'+nums[0]
		name1 = libname
		fu("dlname='%s'\n" % name2)
		strn = " ".join([name3, name2, name1])
		fu("library_names='%s'\n" % (strn) )
	else:
		fu("dlname='%s'\n" % sname)
		fu("library_names='%s %s %s'\n" % (sname, sname, sname) )
	fu("old_library=''\n")
	vars = ' '.join(task.m_env['libtoolvars']+task.m_env['LINKFLAGS'])
	fu("dependency_libs='%s'\n" % vars)
	fu("current=0\n")
	fu("age=0\nrevision=0\ninstalled=yes\nshouldnotlink=no\n")
	fu("dlopen=''\ndlpreopen=''\n")
	fu("libdir='%s/lib'\n" % task.m_env['PREFIX'])
	dest.close()
	return 0
# TODO move this line out
Action.Action('fakelibtool', vars=fakelibtool_vardeps, func=fakelibtool_build, color='BLUE')

class ccroot(Object.genobj):
	"Parent class for programs and libraries in languages c, c++ and moc (Qt)"
	s_default_ext = []
	def __init__(self, type='program', subtype=None):
		Object.genobj.__init__(self, type)

		self.env = Params.g_build.m_allenvs['default'].copy()
		if not self.env['tools']: fatal('no tool selected')

		self.install_var = ''
		self.install_subdir = ''

		# includes, seen from the current directory
		self.includes=''

		## list of directories to enable when scanning
		## #include directives in source files for automatic
		## dependency tracking.  If left empty, scanning the
		## whole project tree is enabled.  If non-empty, only
		## the indicated directories (which must be relative
		## paths), plus the directories in obj.includes, are
		## scanned for #includes.
		self.dependencies = ''

		self.defines=''
		self.rpaths=''

		self.uselib=''

		# new scheme: provide the names of the local libraries to link with
		# the objects found will be post()-ed
		self.uselib_local=''


		# add .o files produced by another Object subclass
		self.add_objects = ''

		self.m_linktask=None

		# libtool emulation
		self.want_libtool=0 # -1: fake; 1: real
		self.vnum=''

		self.p_compiletasks=[]

		# do not forget to set the following variables in a subclass
		self.p_flag_vars = []
		self.p_type_vars = []

		# TODO ???
		self.m_type_initials = ''

		self.chmod = 0755

		# these are kind of private, do not touch
		self._incpaths_lst=[]
		self.inc_paths = []
		self.scanner_defines = {}
		self._bld_incpaths_lst=[]

		# the subtype, used for all sorts of things
		self.subtype = subtype
		if not self.subtype:
			if self.m_type == 'program':
				self.subtype = 'program'
			elif self.m_type == 'staticlib':
				self.subtype = 'staticlib'
			elif self.m_type == 'plugin':
				self.subtype = 'plugin'
			else:
				self.subtype = 'shlib'

	def create_task(self, type, env=None, nice=100):
		"overrides Object.create_task to catch the creation of cpp tasks"
		task = Object.genobj.create_task(self, type, env, nice)
		if type == self.m_type_initials:
			self.p_compiletasks.append(task)
		return task

	def apply(self):
		"adding some kind of genericity is tricky subclass this method if it does not suit your needs"
		debug("apply called for "+self.m_type_initials, 'ccroot')

		if not (self.source or self.add_objects) and not hasattr(self, 'nochecks'):
			fatal('no source files specified for %s' % self)
		if not self.target and self.m_type != 'objects' and not hasattr(self, 'nochecks'):
			fatal('no target for %s' % self)

		self.apply_type_vars()
		self.apply_incpaths()
		self.apply_dependencies()
		self.apply_defines()

		self.apply_core()

		self.apply_lib_vars()
		self.apply_obj_vars()
		if self.m_type != 'objects': self.apply_objdeps()

	def apply_core(self):
		if self.want_libtool and self.want_libtool>0:
			self.apply_libtool()

		if self.m_type == 'objects':
			type = 'program' # TODO: incorrect for shlibs
		else:
			type = self.m_type

		obj_ext = self.env[type+'_obj_ext'][0]
		pre = self.m_type_initials

		# get the list of folders to use by the scanners
		# all our objects share the same include paths anyway
		tree = Params.g_build

		lst = self.to_list(self.source)
		find_source_lst = self.path.find_source_lst
		for filename in lst:
			node = find_source_lst(Utils.split_path(filename))
			if not node: fatal("source not found: %s in %s" % (filename, str(self.path)))

			# Extract the extension and look for a handler hook.
			k = max(0, filename.rfind('.'))
			try:
				self.get_hook(filename[k:])(self, node)
				continue
			except TypeError:
				pass

			# create the compilation task: cpp or cc
			task = self.create_task(self.m_type_initials, self.env)

			task.m_scanner        = g_c_scanner
			task.path_lst = self.inc_paths
			task.defines  = self.scanner_defines

			task.m_inputs = [node]
			task.m_outputs = [node.change_ext(obj_ext)]

		# if we are only building .o files, tell which ones we built
		if self.m_type=='objects':
			outputs = []
			app = outputs.append
			for t in self.p_compiletasks: app(t.m_outputs[0])
			self.out_nodes = outputs
			return

		# and after the objects, the remaining is the link step
		# link in a lower priority (101) so it runs alone (default is 10)
		global g_prio_link
		if self.m_type=='staticlib':
			linktask = self.create_task('ar_link_static', self.env, g_prio_link)
		else:
			linktask = self.create_task(pre+'_link', self.env, g_prio_link)
		outputs = []
		app = outputs.append
		for t in self.p_compiletasks: app(t.m_outputs[0])
		linktask.set_inputs(outputs)
		linktask.set_outputs(self.path.find_build(self.get_target_name()))

		self.m_linktask = linktask

		if self.m_type != 'program' and self.want_libtool:
			latask = self.create_task('fakelibtool', self.env, 200)
			latask.set_inputs(linktask.m_outputs)
			latask.set_outputs(linktask.m_outputs[0].change_ext('.la'))
			self.m_latask = latask

	def get_target_name(self, ext=None):
		return self.get_library_name(self.target, ext)

	def get_library_name(self, name, ext=None):
		v = self.env

		prefix = v[self.m_type+'_PREFIX']
		if self.subtype+'_PREFIX' in v.m_table:
			prefix = v[self.subtype+'_PREFIX']

		suffix = v[self.m_type+'_SUFFIX']
		if self.subtype+'_SUFFIX' in v.m_table:
			suffix = v[self.subtype+'_SUFFIX']

		if ext: suffix = ext
		if not prefix: prefix=''
		if not suffix: suffix=''

		# Handle the case where the name contains a directory src/mylib
		k=name.rfind('/')
		if k == -1:
			return ''.join([prefix, name, suffix])
		else:
			return name[0:k+1] + ''.join([prefix, name[k+1:], suffix])

	def apply_defines(self):
		"subclass me"
		pass

	def apply_incpaths(self):
		lst = []
		for i in self.to_list(self.uselib):
			if self.env['CPPPATH_'+i]:
				lst += self.to_list(self.env['CPPPATH_'+i])
		inc_lst = self.to_list(self.includes) + lst
		lst = self._incpaths_lst

		# add the build directory
		self._incpaths_lst.append(Params.g_build.m_bldnode)
		self._incpaths_lst.append(Params.g_build.m_srcnode)

		# now process the include paths
		tree = Params.g_build
		for dir in inc_lst:
			if os.path.isabs(dir):
				self.env.append_value('CPPPATH', dir)
				continue

			node = self.path.find_dir_lst(Utils.split_path(dir))
			if not node:
				debug("node not found in ccroot:apply_incpaths "+str(dir), 'ccroot')
				continue
			if not node in lst: lst.append(node)
			Params.g_build.rescan(node)
			self._bld_incpaths_lst.append(node)
		# now the nodes are added to self._incpaths_lst

	def apply_dependencies(self):
		if self.dependencies:
			dep_lst = (self.to_list(self.dependencies)
				   + self.to_list(self.includes))
			self.inc_paths = []
			for directory in dep_lst:
				if os.path.isabs(directory):
					Params.fatal("Absolute paths not allowed in obj.dependencies")
					return

				node = self.path.find_dir_lst(Utils.split_path(directory))
				if not node:
					Params.fatal("node not found in ccroot:apply_dependencies "
						     + str(directory), 'ccroot')
					return
				if node not in self.inc_paths:
					self.inc_paths.append(node)
		else:
			## by default, we include the whole project tree
			lst = [self.path]
			for obj in Object.g_allobjs:
				if obj.path not in lst:
					lst.append(obj.path)
			self.inc_paths = lst + self._incpaths_lst

	def apply_type_vars(self):
		debug('apply_type_vars called', 'ccroot')
		# if the subtype defines uselib to add, add them
		st = self.env[self.subtype+'_USELIB']
		if st: self.uselib = self.uselib + ' ' + st

		# each compiler defines variables like 'shlib_CXXFLAGS', 'shlib_LINKFLAGS', etc
		# so when we make a cppobj of the type shlib, CXXFLAGS are modified accordingly
		for var in self.p_type_vars:
			compvar = '_'.join([self.m_type, var])
			#print compvar
			value = self.env[compvar]
			if value: self.env.append_value(var, value)

	def apply_obj_vars(self):
		debug('apply_obj_vars called for cppobj', 'ccroot')
		cpppath_st       = self.env['CPPPATH_ST']
		lib_st           = self.env['LIB_ST']
		staticlib_st     = self.env['STATICLIB_ST']
		libpath_st       = self.env['LIBPATH_ST']
		staticlibpath_st = self.env['STATICLIBPATH_ST']

		self.addflags('CXXFLAGS', self.cxxflags)
		self.addflags('CPPFLAGS', self.cppflags)

		app = self.env.append_unique

		# local flags come first
		# set the user-defined includes paths
		if not self._incpaths_lst: self.apply_incpaths()
		for i in self._bld_incpaths_lst:
			app('_CXXINCFLAGS', cpppath_st % i.bldpath(self.env))
			app('_CXXINCFLAGS', cpppath_st % i.srcpath(self.env))

		# set the library include paths
		for i in self.env['CPPPATH']:
			app('_CXXINCFLAGS', cpppath_st % i)
			#print self.env['_CXXINCFLAGS']
			#print " appending include ",i

		# this is usually a good idea
		app('_CXXINCFLAGS', cpppath_st % '.')
		app('_CXXINCFLAGS', cpppath_st % self.env.variant())
		tmpnode = Params.g_build.m_curdirnode
		app('_CXXINCFLAGS', cpppath_st % tmpnode.bldpath(self.env))
		app('_CXXINCFLAGS', cpppath_st % tmpnode.srcpath(self.env))

		for i in self.env['RPATH']:
			app('LINKFLAGS', i)

		for i in self.env['LIBPATH']:
			app('LINKFLAGS', libpath_st % i)

		for i in self.env['LIBPATH']:
			app('LINKFLAGS', staticlibpath_st % i)

		if self.env['STATICLIB']:
			self.env.append_value('LINKFLAGS', self.env['STATICLIB_MARKER'])
			# WARNING: ld wants the static libs in reverse order
			k = [(staticlib_st % i) for i in self.env['STATICLIB']]
			k.reverse()
			app('LINKFLAGS', k)

		# fully static binaries ?
		if not self.env['FULLSTATIC']:
			if self.env['STATICLIB'] or self.env['LIB']:
				self.env.append_value('LINKFLAGS', self.env['SHLIB_MARKER'])

		app('LINKFLAGS', [lib_st % i for i in self.env['LIB']])

	def install(self):
		if not (Params.g_commands['install'] or Params.g_commands['uninstall']): return

		dest_var    = self.install_var
		dest_subdir = self.install_subdir
		if dest_var == 0: return

		if not dest_var:
			dest_var = self.env[self.subtype+'_INST_VAR']
			dest_subdir = self.env[self.subtype+'_INST_DIR']

		if self.m_type == 'program':
			self.install_results(dest_var, dest_subdir, self.m_linktask, chmod=self.chmod)
		elif self.m_type == 'shlib' or self.m_type == 'plugin':
			if self.want_libtool:
				self.install_results(dest_var, dest_subdir, self.m_latask)
			if sys.platform=='win32' or not self.vnum:
				self.install_results(dest_var, dest_subdir, self.m_linktask)
			else:
				libname = self.m_linktask.m_outputs[0].m_name

				nums=self.vnum.split('.')
				name3 = libname+'.'+self.vnum
				name2 = libname+'.'+nums[0]
				name1 = libname

				filename = self.m_linktask.m_outputs[0].relpath_gen(Params.g_build.m_curdirnode)
				Common.install_as(dest_var, dest_subdir+'/'+name3, filename, env=self.env)

				#print 'lib/'+name2, '->', name3
				#print 'lib/'+name1, '->', name2

				Common.symlink_as(dest_var, name3, dest_subdir+'/'+name2)
				Common.symlink_as(dest_var, name2, dest_subdir+'/'+name1)
		else:
			self.install_results(dest_var, dest_subdir, self.m_linktask, chmod=0644)

	# This piece of code must suck, no one uses it
	def apply_libtool(self):
		self.env['vnum']=self.vnum

		paths=[]
		libs=[]
		libtool_files=[]
		libtool_vars=[]

		for l in self.env['LINKFLAGS']:
			if l[:2]=='-L':
				paths.append(l[2:])
			elif l[:2]=='-l':
				libs.append(l[2:])

		for l in libs:
			for p in paths:
				try:
					dict = read_la_file(p+'/lib'+l+'.la')
					linkflags2 = dict['dependency_libs']
					for v in linkflags2.split():
						if v[-3:] == '.la':
							libtool_files.append(v)
							libtool_vars.append(v)
							continue
						self.env.append_unique('LINKFLAGS', v)
					break
				except:
					pass

		self.env['libtoolvars']=libtool_vars

		while libtool_files:
			file = libtool_files.pop()
			dict = read_la_file(file)
			for v in dict['dependency_libs'].split():
				if v[-3:] == '.la':
					libtool_files.append(v)
					continue
				self.env.append_unique('LINKFLAGS', v)

	def apply_lib_vars(self):
		debug('apply_lib_vars called', 'ccroot')
		env=self.env

		# 1. override if necessary
		self.process_vnum()

		# 2. the case of the libs defined in the project (visit ancestors first)
		# the ancestors external libraries (uselib) will be prepended
		uselib = self.to_list(self.uselib)
		seen = []
		names = self.to_list(self.uselib_local) # consume the list of names
		while names:
			x = names[0]

			# visit dependencies only once
			if x in seen:
				names = names[1:]
				continue

			# object does not exist ?
			y = Object.name_to_obj(x)
			if not y:
				fatal('object not found in uselib_local: obj %s uselib %s' % (self.name, x))
				names = names[1:]
				continue

			# object has ancestors to process first ? update the list of names
			if y.uselib_local:
				added = 0
				lst = y.to_list(y.uselib_local)
				lst.reverse()
				for u in lst:
					if u in seen: continue
					added = 1
					names = [u]+names
				if added: continue # list of names modified, loop

			# safe to process the current object
			if not y.m_posted: y.post()
			seen.append(x)

			if y.m_type == 'shlib':
				env.append_value('LIB', y.target)
			elif y.m_type == 'plugin':
				if sys.platform == 'darwin': env.append_value('PLUGIN', y.target)
				else: env.append_value('LIB', y.target)
			elif y.m_type == 'staticlib':
				env.append_value('STATICLIB', y.target)
			elif y.m_type == 'objects':
				pass
			else:
				error('%s has unknown object type %s, in apply_lib_vars, uselib_local.'
				      % (y.name, y.m_type))

			# add the link path too
			tmp_path = y.path.bldpath(self.env)
			if not tmp_path in env['LIBPATH']: env.prepend_value('LIBPATH', tmp_path)

			# set the dependency over the link task
			if y.m_linktask is not None:
				self.m_linktask.set_run_after(y.m_linktask)
				dep_nodes = getattr(self.m_linktask, 'dep_nodes', [])
				dep_nodes += y.m_linktask.m_outputs
				self.m_linktask.dep_nodes = dep_nodes

			# add ancestors uselib too
			# TODO potential problems with static libraries ?
			morelibs = y.to_list(y.uselib)
			for v in morelibs:
				if v in uselib: continue
				uselib = [v]+uselib
			names = names[1:]

		# 3. the case of the libs defined outside
		for x in uselib:
			for v in self.p_flag_vars:
				val = self.env[v+'_'+x]
				if val: self.env.append_value(v, val)
	def process_vnum(self):
		if self.vnum and sys.platform != 'darwin' and sys.platform != 'win32':
			nums=self.vnum.split('.')
			# this is very unix-specific
			try: name3 = self.soname
			except: name3 = self.m_linktask.m_outputs[0].m_name+'.'+self.vnum.split('.')[0]
			self.env.append_value('LINKFLAGS', '-Wl,-h,'+name3)

	def apply_objdeps(self):
		"add the .o files produced by some other object files in the same manner as uselib_local"
		seen = []
		names = self.to_list(self.add_objects)
		while names:
			x = names[0]

			# visit dependencies only once
			if x in seen:
				names = names[1:]
				continue

			# object does not exist ?
			y = Object.name_to_obj(x)
			if not y:
				error('object not found in add_objects: obj %s add_objects %s' % (self.name, x))
				names = names[1:]
				continue

			# object has ancestors to process first ? update the list of names
			if y.add_objects:
				added = 0
				lst = y.to_list(y.add_objects)
				lst.reverse()
				for u in lst:
					if u in seen: continue
					added = 1
					names = [u]+names
				if added: continue # list of names modified, loop

			# safe to process the current object
			if not y.m_posted: y.post()
			seen.append(x)

			self.m_linktask.m_inputs += y.out_nodes


	def addflags(self, var, value):
		"utility function for cc.py and ccroot.py: add self.cxxflags to CXXFLAGS"
		self.env.append_value(var, self.to_list(value))

