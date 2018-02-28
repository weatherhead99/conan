#!/usr/bin/env python
# -*- coding: utf-8 -*-


from conans.tools import unix_path


def rpath_flags(os_build, compiler, lib_paths):
    if not os_build:
        return []
    if compiler in ("clang", "apple-clang", "gcc"):
        rpath_separator = "," if os_build in ["Macos", "iOS", "watchOS", "tvOS"] else "="
        return ['-Wl,-rpath%s"%s"' % (rpath_separator, x.replace("\\", "/"))
                for x in lib_paths if x]
    return []


def architecture_flag(compiler, arch):
    """
    returns flags specific to the target architecture and compiler
    """
    if not compiler or not arch:
        return ""

    if str(compiler) in ['gcc', 'apple-clang', 'clang', 'sun-cc']:
        if str(arch) in ['x86_64', 'sparcv9']:
            return '-m64'
        elif str(arch) in ['x86', 'sparc']:
            return '-m32'
    return ""


def libcxx_define(compiler, libcxx):

    if not compiler or not libcxx:
        return ""

    if str(compiler) in ['gcc', 'clang', 'apple-clang']:
        if str(libcxx) == 'libstdc++':
            return '_GLIBCXX_USE_CXX11_ABI=0'
        elif str(libcxx) == 'libstdc++11':
            return '_GLIBCXX_USE_CXX11_ABI=1'
    return ""


def libcxx_flag(compiler, libcxx):
    """
    returns flag specific to the target C++ standard library
    """
    if not compiler or not libcxx:
        return ""
    if str(compiler) in ['clang', 'apple-clang']:
        if str(libcxx) in ['libstdc++', 'libstdc++11']:
            return '-stdlib=libstdc++'
        elif str(libcxx) == 'libc++':
            return '-stdlib=libc++'
    elif str(compiler) == 'sun-cc':
        return ({"libCstd": "-library=Cstd",
                         "libstdcxx": "-library=stdcxx4",
                         "libstlport": "-library=stlport4",
                         "libstdc++": "-library=stdcpp"}.get(libcxx, ""))
    return ""


def pic_flag(compiler=None):
    """
    returns PIC (position independent code) flags, such as -fPIC
    """
    if not compiler or compiler == 'Visual Studio':
        return ""
    return '-fPIC'


def build_type_flag(compiler, build_type):
    """
    returns flags specific to the build type (Debug, Release, etc.)
    (-s, -g, /Zi, etc.)
    """
    if not compiler or not build_type:
        return ""

    if str(compiler) == 'Visual Studio':
        if build_type == 'Debug':
            return '/Zi'
    else:
        if build_type == 'Debug':
            return '-g'
        elif build_type == 'Release' and str(compiler) == 'gcc':
            return '-s'
    return ""


def build_type_define(build_type=None):
    """
    returns definitions specific to the build type (Debug, Release, etc.)
    like DEBUG, _DEBUG, NDEBUG
    """
    return 'NDEBUG' if build_type == 'Release' else ""


def adjust_path(path, win_bash=False, subsystem=None, compiler=None):
    """
    adjusts path to be safely passed to the compiler command line
    for Windows bash, ensures path is in format according to the subsystem
    for path with spaces, places double quotes around it
    converts slashes to backslashes, or vice versa
    """
    if str(compiler) == 'Visual Studio':
        path = path.replace('/', '\\')
    else:
        path = path.replace('\\', '/')
    if win_bash:
        path = unix_path(path, subsystem)
    return '"%s"' % path if ' ' in path else path


def sysroot_flag(sysroot, win_bash=False, subsystem=None, compiler=None):
    if str(compiler) != 'Visual Studio' and sysroot:
        sysroot = adjust_path(sysroot, win_bash=win_bash, subsystem=subsystem, compiler=compiler)
        return '--sysroot=%s' % sysroot
    return ""


def visual_runtime(runtime):
    if runtime:
       return "/%s" % runtime
    return ""

def _option_char(compiler):
    """-L vs /L"""
    return "-" if compiler != "Visual Studio" else "/"


def format_defines(defines, compiler):
    return ["%sD%s" % (_option_char(compiler), define) for define in defines if define]


def format_include_paths(include_paths, win_bash=False, subsystem=None, compiler=None):
    return ["%sI%s" % (_option_char(compiler),
                       adjust_path(include_path, win_bash=win_bash,
                                   subsystem=subsystem, compiler=compiler))
            for include_path in include_paths if include_path]


def format_library_paths(library_paths, win_bash=False, subsystem=None, compiler=None):

    pattern = "/LIBPATH:%s" if str(compiler) == 'Visual Studio' else "-L%s"
    return [pattern % adjust_path(library_path, win_bash=win_bash,
                                  subsystem=subsystem, compiler=compiler)
            for library_path in library_paths if library_path]


def format_libraries(libraries, compiler=None):
    pattern = "%s.lib" if str(compiler) == 'Visual Studio' else "-l%s"
    return [pattern % library for library in libraries if library]
