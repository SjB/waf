#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005 (ita)

import os, string, sys, imp

VERSION = '0.8.7'
cwd = os.getcwd()

# first, we need wafdir otherwise we cannot parse the command-line arguments
# or print the version number

# unpack wafadmin if necessary, developers should use the environment variable "WAFADMIN"
try:
	wafdir = os.environ['WAFDIR']
except:
	if sys.platform == 'win32':
		wafdir='c:\\temp\\waf-%s\\' % VERSION
	else:
		wafdir = '%s/.waf-%s' % (os.environ['HOME'], VERSION)

# look if the wafdir exists
try:
	os.stat(wafdir)
except:
	file = open('woof', 'rb')
	lst = []

	while 1:
		line = file.readline()
		if not line: break
		if line=='""" # ===>BEGIN WOOF<===\n': break

	while 1:
		line = file.readline()
		if line=='""" # ===>END WOOF<===\n': break
		lst.append(line)

	import base64
	cnt = ''.join(lst)
	cnt = base64.decodestring(cnt)

	# create the directory
	try:
		os.makedirs(wafdir)
	except:
		print "could not make ", wafdir

	os.chdir(wafdir)
	file = open('wafadmin.tar.bz2', 'wb')
	file.write(cnt)
	file.close()

	# now we have the tar file to open
	import tarfile
	tar = tarfile.open('wafadmin.tar.bz2')
	for tarinfo in tar:
		tar.extract(tarinfo)
	tar.close()

	# cleanup the tarfile and chdir to the previous directory
	os.chmod('wafadmin', 0755)
	os.chmod('wafadmin'+os.sep+'Tools', 0755)
	os.unlink('wafadmin.tar.bz2')
	os.chdir(cwd)

# now find the wscript file


msg1 = """\033[91mWaf: *** Nothing to do! Please run waf (or ./waf.py) from a directory containing a file named "wscript"\033[0m
"""

# Climb up to the folder containing the main wscript and chdir to it
# It is also possible that the project was configured as a sub-module
# in this case, stop when a ".lock-wscript" file is found
candidate = None
xml = None

# Some people want to configure their projects gcc-style:
# mkdir build && cd build && ../waf.py configure && ../waf.py
# check that this is really what is wanted
build_dir_override = None
candidate = None

#if not os.listdir(cwd):
lst = os.listdir(cwd)
#check if a wscript or a wscript_xml file is in current directory
if (not 'wscript' in lst) and (not 'wscript_xml' in lst):
	#set the build directory with the current directory
	build_dir_override = cwd
else:
	#wscript or wscript_xml is in current directory
	#use this directory as candidate
	candidate = cwd
	#check if wscript_xml is there
	if 'wscript_xml'   in lst:
		xml = 1

try:
	#check the following dirs for wscript or wscript_xml
	
	#check first the calldir if there is wscript or wscript_xml
	#for example: /usr/src/configure the calldir would be /usr/src
	calldir = os.path.abspath(os.path.dirname(sys.argv[0]))
	lst_calldir = os.listdir(calldir)
	if 'wscript'       in lst_calldir: 
		candidate = calldir
	if 'wscript_xml'   in lst_calldir:
		candidate = calldir
		xml = 1
		
	#check all directories above current dir for wscript or
	#wscript_xml if still not found 
	while not candidate:
		if len(cwd) <= 3: 
			break # stop at / or c:
		dirlst = os.listdir(cwd)
		if 'wscript'       in dirlst:
			candidate = cwd
		if 'wscript_xml'   in dirlst:
			candidate = cwd
			xml = 1
			break
		if 'configure'     in sys.argv and candidate:
			break
		if '.lock-wscript' in dirlst:
			break
		cwd = cwd[:cwd.rfind(os.sep)] # climb up
except:
	print msg1
	sys.exit(1)

if not candidate:
	print msg1
	sys.exit(1)

# We have found wscript, but there is no guarantee that it is valid
os.chdir(candidate)

"""
# The following function returns the first wafadmin folder found in the list of candidates
def find_wafdir(lst_cand):
	for cand_dir in lst_cand:
		try:
			os.stat(cand_dir)
			return cand_dir
		except:
			pass
	print msg2
	print "candidates were: ", str(lst_cand)
	sys.exit(1)

wafadmin_dir1 = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'wafadmin')
wafadmin_dir2 = os.path.join(os.path.abspath('.'), 'wafadmin')
if sys.platform == "win32":
	lst = [wafadmin_dir1, wafadmin_dir2]
else:
	lst = [wafadmin_dir1, wafadmin_dir2, '/usr/lib/wafadmin', '/usr/local/lib/wafadmin']

wafadmin_dir = find_wafdir(lst)
"""


# The sys.path is updated, so we can now import our modules
wafadmindir = os.path.join(wafdir, 'wafadmin')
tooldir = os.path.join(wafadmindir, 'Tools')
sys.path = [wafadmindir, tooldir] + sys.path

import Options, Params, Utils

# Set the directory containing the tools
Params.g_tooldir = [tooldir]

# with xml files jump to the parser
if xml:
	from XMLScripting import compile
	compile(candidate+os.sep+'wscript_xml')
else:
	# define the main module containing the functions init, shutdown, ..
	Utils.set_main_module(os.path.join(candidate, 'wscript'))

if build_dir_override:
	try:
		# test if user has set the blddir in wscript.
		blddir = Utils.g_module.blddir
		msg = 'Overriding blddir %s with %s' % (mblddir, bldcandidate)
		Params.niceprint('YELLOW', msg)
	except:
		pass
	Utils.g_module.blddir = build_dir_override

# fix the path of the cachedir - it is mandatory
# untested code (ita)
if sys.platform == 'win32':
	try:
		lst = Utils.g_module.cachedir.split('/')
		Utils.g_module.cachedir = os.sep.join(lst)
	except:
		Params.niceprint('RED', 'No cachedir specified in wscript!')
		raise

# fetch the custom command-line options recursively and in a procedural way
opt_obj = Options.Handler()
opt_obj.sub_options('')
opt_obj.parse_args()

# we use the results of the parser
if Params.g_commands['dist']:
	# try to use the user-defined dist function first, fallback to the waf scheme
	try:
		Utils.g_module.dist()
		sys.exit(0)
	except:
		pass
	appname         = 'noname'
	try:
		appname = Utils.g_module.APPNAME
	except: 
		pass

	version         = '1.0'
	try:
		version = Utils.g_module.VERSION
	except:
		pass

	from Scripting import Dist
	Dist(appname, version)
	sys.exit(0)
elif Params.g_commands['distclean']:
	# try to use the user-defined distclean first, fallback to the waf scheme
	try:
		Utils.g_module.distclean()
		sys.exit(0)
	except:
		pass

	from Scripting import DistClean
	DistClean()
	sys.exit(0)

try:
	fun = None
	try:
		fun = Utils.g_module.init
	except:
		pass
	if fun: 
		fun()
except SystemExit:
	raise

from Scripting import Main
Main()

