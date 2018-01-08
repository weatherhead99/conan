#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan  8 16:43:05 2018

@author: weatherill
"""

from conans.tools import OSInfo
from conans.errors import ConanException
from conans.client.runner import ConanRunner
from conans.client.output import ConanOutput
import os
import io
import sys
import types

class DependencyChecker(object):
    def __init__(self,conanfile=None):
        osi = OSInfo()
        if osi.is_linux:
            self.get_dependencies = types.MethodType(get_dependencies_ldd)
        else:
            raise NotImplemented("only linux supported for dependency checker")
    
        self._conanfile = conanfile
    
    
def ldd_parse_line(line):
    """ returns libname, libpath from an output line of ldd""" 
    tokens = [_.strip() for _ in line.split("=>")]
    
    if len(tokens) == 1:
        #this is ld-linux or similar
        path,name = os.path.split(tokens[0].split("(")[0].strip())
        print(name)
        return name,path
    
    if len(tokens[1].split("(")[0].strip()) == 0:
        #this is linux-vdso
        return tokens[0], None
        
    return tokens[0], os.path.split(tokens[1].split("(")[0])[0]
    
def get_dependencies_ldd(filename,runner=None, output= None):
    if runner is None:
        runner = ConanRunner(log_run_to_output=True)
    
    if output is None:
        output = ConanOutput(sys.stdout,color=True)
    
    op = io.StringIO()
    retcode = runner("ldd %s" % filename, op)
    if retcode != 0 :
        
        raise ConanException("ldd returned code: %s" % retcode)
        
    lines = op.getvalue().splitlines()
    return [ldd_parse_line(_) for _ in lines]
    

if __name__ == "__main__":
    
    dc = DependencyChecker()

    
    dc.get_dependencies("/usr/lib/x86_64-linux-gnu/libavutil.so.52")