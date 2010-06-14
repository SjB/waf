#!/usr/bin/env python
# encoding: utf-8
# andersg at 0x63.nu 2007

import os, subprocess
from waflib import Task, Options, Utils
from waflib.Configure import conf
from waflib.TaskGen import extension, taskgen, feature, before

@before('apply_incpaths', 'apply_lib_vars')
@feature('perlext')
def init_perlext(self):
	self.uselib = self.to_list(getattr(self, 'uselib', ''))
	if not 'PERL' in self.uselib: self.uselib.append('PERL')
	if not 'PERLEXT' in self.uselib: self.uselib.append('PERLEXT')
	self.env['shlib_PATTERN'] = self.env['perlext_PATTERN']

@extension('.xs')
def xsubpp_file(self, node):
	outnode = node.change_ext('.c')
	self.create_task('xsubpp', node, outnode)
	self.source.append(outnode)

class xsubpp(Task.Task):
	run_str = '${PERL} ${XSUBPP} -noprototypes -typemap ${EXTUTILS_TYPEMAP} ${SRC} > ${TGT}'
	color   = 'BLUE'
	ext_out = '.h'

@conf
def check_perl_version(conf, minver=None):
	"""
	Checks if perl is installed.

	If installed the variable PERL will be set in environment.

	Perl binary can be overridden by --with-perl-binary config variable

	"""
	res = True

	if not getattr(Options.options, 'perlbinary', None):
		perl = conf.find_program("perl", var="PERL")
		if not perl:
			return False
	else:
		perl = Options.options.perlbinary
		conf.env['PERL'] = perl

	version = Utils.cmd_output(perl + " -e'printf \"%vd\", $^V'")
	if not version:
		res = False
		version = "Unknown"
	elif not minver is None:
		ver = tuple(map(int, version.split(".")))
		if ver < minver:
			res = False

	if minver is None:
		cver = ""
	else:
		cver = ".".join(map(str,minver))
	conf.check_message("perl", cver, res, version)
	return res

@conf
def check_perl_module(conf, module):
	"""
	Check if specified perlmodule is installed.

	Minimum version can be specified by specifying it after modulename
	like this:

	conf.check_perl_module("Some::Module 2.92")
	"""
	cmd = [conf.env['PERL'], '-e', 'use %s' % module]
	r = subprocess.call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
	conf.check_message("perl module %s" % module, "", r)
	return r

@conf
def check_perl_ext_devel(conf):
	"""
	Check for configuration needed to build perl extensions.

	Sets different xxx_PERLEXT variables in the environment.

	Also sets the ARCHDIR_PERL variable useful as installation path,
	which can be overridden by --with-perl-archdir option.
	"""

	perl = conf.env.PERL
	if not perl:
		conf.fatal('find perl first')

	def read_out(cmd):
		return Utils.to_list(Utils.cmd_output(perl + cmd))

	conf.env["LINKFLAGS_PERLEXT"] = read_out(" -MConfig -e'print $Config{lddlflags}'")
	conf.env["CPPPATH_PERLEXT"] = read_out(" -MConfig -e'print \"$Config{archlib}/CORE\"'")
	conf.env["CCFLAGS_PERLEXT"] = read_out(" -MConfig -e'print \"$Config{ccflags} $Config{cccdlflags}\"'")

	conf.env["XSUBPP"] = read_out(" -MConfig -e'print \"$Config{privlib}/ExtUtils/xsubpp$Config{exe_ext}\"'")
	conf.env["EXTUTILS_TYPEMAP"] = read_out(" -MConfig -e'print \"$Config{privlib}/ExtUtils/typemap\"'")

	if not getattr(Options.options, 'perlarchdir', None):
		conf.env["ARCHDIR_PERL"] = Utils.cmd_output(perl + " -MConfig -e'print $Config{sitearch}'")
	else:
		conf.env["ARCHDIR_PERL"] = getattr(Options.options, 'perlarchdir')

	conf.env['perlext_PATTERN'] = '%s.' + Utils.cmd_output(perl + " -MConfig -e'print $Config{dlext}'")

def options(opt):
	opt.add_option("--with-perl-binary", type="string", dest="perlbinary", help = 'Specify alternate perl binary', default=None)
	opt.add_option("--with-perl-archdir", type="string", dest="perlarchdir", help = 'Specify directory where to install arch specific files', default=None)
