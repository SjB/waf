#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006-2008 (ita)
# Ralf Habacker, 2006 (rh)

"ar and ranlib"

import os, sys
import Task, Utils
from Configure import conf

ar_str = '${AR} ${ARFLAGS} ${AR_TGT_F}${TGT} ${AR_SRC_F}${SRC}'
cls = Task.simple_task_type('static_link', ar_str, color='YELLOW', ext_in='.o')
cls.maxjobs = 1
cls.install = Utils.nada

# remove the output in case it already exists
old = cls.run
def wrap(self):
	try: os.remove(self.outputs[0].abspath())
	except OSError: pass
	return old(self)
setattr(cls, 'run', wrap)

@conf
def find_ar(conf):
	conf.check_tool('ar')

def detect(conf):
	conf.find_program('ar', var='AR', mandatory=True)
	conf.env.ARFLAGS = 'rcs'


