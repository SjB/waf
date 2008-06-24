#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005-2008 (ita)

"Main parameters"

import os, sys
import Constants, Utils

# =================================== #
# HELPERS

g_colors = {
'BOLD'  :'\x1b[01;1m',
'RED'   :'\x1b[01;91m',
'REDP'  :'\x1b[01;33m',
'GREEN' :'\x1b[32m',
'YELLOW':'\x1b[33m',
'PINK'  :'\x1b[35m',
'BLUE'  :'\x1b[01;34m',
'CYAN'  :'\x1b[36m',
'NORMAL':'\x1b[0m'
}
"colors used for printing messages"

g_cursor_on ='\x1b[?25h'
g_cursor_off='\x1b[?25l'

def reset_colors():
	global g_colors
	for k in g_colors.keys():
		g_colors[k]=''
		g_cursor_on=''
		g_cursor_off=''

if (sys.platform=='win32') or ('NOCOLOR' in os.environ) \
	or (os.environ.get('TERM', 'dumb') in ['dumb', 'emacs']) \
	or (not sys.stdout.isatty()):
	reset_colors()

