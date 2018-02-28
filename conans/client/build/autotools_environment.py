import copy
import platform
import os

from conans.client import join_arguments
from conans.tools import environment_append, args_to_string, cpu_count, cross_building, detected_architecture
from conans.client.tools.win import unix_path
from conans.client.tools.oss import OSInfo

sun_cc_libcxx_flags_dict = {"libCstd": "-library=Cstd",
                            "libstdcxx": "-library=stdcxx4",
                            "libstlport": "-library=stlport4",
                            "libstdc++": "-library=stdcpp"}

architecture_dict = {"x86_64": "-m64", "x86": "-m32"}


def stdlib_flags(compiler, libcxx):
    ret = []
    if compiler and "clang" in compiler:
        if libcxx == "libc++":
            ret.append("-stdlib=libc++")
        else:
            ret.append("-stdlib=libstdc++")
    elif compiler == "sun-cc":
        flag = sun_cc_libcxx_flags_dict.get(libcxx, None)
        if flag:
            ret.append(flag)
    return ret


def stdlib_defines(compiler, libcxx):
    ret = []
    if compiler == "gcc" or compiler == "clang":  # Maybe clang is using the standard library from g++
        if libcxx == "libstdc++":
            ret.append("_GLIBCXX_USE_CXX11_ABI=0")
        elif str(libcxx) == "libstdc++11":
            ret.append("_GLIBCXX_USE_CXX11_ABI=1")
    return ret


class AutoToolsBuildEnvironment(object):
    """
    - CPPFLAGS (C-PreProcesor-Flags NOT related with c++) (-I -D)
    - CFLAGS (not CPPFLAGS nor LDFLAGS, used for optimization or debugging)
    - CXXFLAGS (the CFLAGS for c++)
    - LDFLAGS (-L, others like -m64 -m32) linker
    """

    def __init__(self, conanfile, win_bash=False):
        self._conanfile = conanfile
        self._win_bash = win_bash
        self.subsystem = OSInfo().detect_windows_subsystem() if self._win_bash else None
        self._deps_cpp_info = conanfile.deps_cpp_info
        self._arch = conanfile.settings.get_safe("arch")
        self._build_type = conanfile.settings.get_safe("build_type")
        self._compiler = conanfile.settings.get_safe("compiler")
        self._libcxx = conanfile.settings.get_safe("compiler.libcxx")

        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self.libs = copy.copy(self._deps_cpp_info.libs)
        self.include_paths = copy.copy(self._deps_cpp_info.include_paths)
        self.library_paths = copy.copy(self._deps_cpp_info.lib_paths)

        self.defines = self._configure_defines()
        # Will go to CFLAGS and CXXFLAGS ["-m64" "-m32", "-g", "-s"]
        self.flags = self._configure_flags()
        # Only c++ flags [-stdlib, -library], will go to CXXFLAGS
        self.cxx_flags = self._configure_cxx_flags()
        # Not -L flags, ["-m64" "-m32"]
        self.link_flags = self._configure_link_flags()  # TEST!
        # Not declared by default
        self.fpic = None

    def _get_host_build_target_flags(self, arch_detected, os_detected):
        """Based on google search for build/host triplets, it could need a lot
        and complex verification"""
        if not cross_building(self._conanfile.settings, os_detected, arch_detected):
            return False, False, False

        arch_setting = self._conanfile.settings.get_safe("arch")
        os_setting = self._conanfile.settings.get_safe("os")

        if os_detected == "Windows" and os_setting != "Windows":
            # Don't know what to do with these, even exists? its only for configure
            return None, None, None

        # Building FOR windows
        if os_setting == "Windows":
            build = "i686-w64-mingw32" if arch_detected == "x86" else "x86_64-w64-mingw32"
            host = "i686-w64-mingw32" if arch_setting == "x86" else "x86_64-w64-mingw32"
        else:  # Building for Linux or Android
            build = "%s-%s" % (arch_detected, {"Linux": "linux-gnu",
                                               "Darwin": "apple-darwin"}.get(os_detected,
                                                                            os_detected.lower()))
            if arch_setting == "x86":
                host_arch = "i686"
            elif arch_setting == "armv8":
                host_arch = "aarch64"
            else:
                host_arch = "arm" if "arm" in arch_setting else arch_setting

            host = "%s%s" % (host_arch, {"Linux": "-linux-gnueabi",
                                         "Android": "-linux-android",
                                         "Macos": "-apple-darwin",
                                         "iOS": "-apple-darwin",
                                         "watchOS": "-apple-darwin",
                                         "tvOS": "-apple-darwin"}.get(os_setting, ""))
            if arch_setting == "armv7hf" and os_setting == "Linux":
                host += "hf"
            elif "arm" in arch_setting and arch_setting != "armv8" and os_setting == "Android":
                host += "eabi"

        return build, host, None

    def configure(self, configure_dir=None, args=None, build=None, host=None, target=None,
                  pkg_config_paths=None):
        """
        :param pkg_config_paths: Optional paths to locate the *.pc files
        :param configure_dir: Absolute or relative path to the configure script
        :param args: Optional arguments to pass to configure.
        :param build: In which system the program will be built. "False" skips the --build flag
        :param host: In which system the generated program will run.  "False" skips the --host flag
        :param target: This option is only used to build a cross-compiling toolchain.  "False" skips the --target flag
                       When the tool chain generates executable program, in which target system the program will run.
        :return: None

        http://jingfenghanmax.blogspot.com.es/2010/09/configure-with-host-target-and-build.html
        https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html

        """
        if configure_dir:
            configure_dir = configure_dir.rstrip("/")
        else:
            configure_dir = "."
        auto_build, auto_host, auto_target = None, None, None
        if build is None or host is None or target is None:
            auto_build, auto_host, auto_target = self._get_host_build_target_flags(detected_architecture(),
                                                                                   platform.system())

        triplet_args = []

        if build is not False:  # Skipped by user
            if build or auto_build:  # User specified value or automatic
                triplet_args.append("--build=%s" % (build or auto_build))

        if host is not False:   # Skipped by user
            if host or auto_host:  # User specified value or automatic
                triplet_args.append("--host=%s" % (host or auto_host))

        if target is not False:  # Skipped by user
            if target or auto_target:  # User specified value or automatic
                triplet_args.append("--target=%s" % (target or auto_target))

        if pkg_config_paths:
            pkg_env = {"PKG_CONFIG_PATH": os.pathsep.join(pkg_config_paths)}
        else:
            # If we are using pkg_config generator automate the pcs location, otherwise it could
            # read wrong files
            pkg_env = {"PKG_CONFIG_PATH": self._conanfile.build_folder} \
                if "pkg_config" in self._conanfile.generators else {}

        with environment_append(pkg_env):
            with environment_append(self.vars):
                configure_dir = self._adjust_path(configure_dir)
                self._conanfile.run('%s/configure %s %s'
                                    % (configure_dir, args_to_string(args), " ".join(triplet_args)),
                                    win_bash=self._win_bash,
                                    subsystem=self.subsystem)

    def _adjust_path(self, path):
        if self._win_bash:
            path = unix_path(path, path_flavor=self.subsystem)
        return '"%s"' % path if " " in path else path

    def make(self, args="", make_program=None, target=None):
        make_program = os.getenv("CONAN_MAKE_PROGRAM") or make_program or "make"
        with environment_append(self.vars):
            str_args = args_to_string(args)
            cpu_count_option = ("-j%s" % cpu_count()) if "-j" not in str_args else None
            self._conanfile.run("%s" % join_arguments([make_program, target, str_args, cpu_count_option]),
                                win_bash=self._win_bash, subsystem=self.subsystem)

    @property
    def _sysroot_flag(self):
        if self._compiler == 'Visual Studio':
            return None
        else:
            return "--sysroot=%s" % self._adjust_path(self._deps_cpp_info.sysroot) if self._deps_cpp_info.sysroot else None

    def _configure_link_flags(self):
        """Not the -L"""
        ret = copy.copy(self._deps_cpp_info.sharedlinkflags)
        ret.extend(self._deps_cpp_info.exelinkflags)
        ret.append(self._architecture_flag)
        if self._sysroot_flag:
            ret.append(self._sysroot_flag)
        return ret

    def _configure_flags(self):
        ret = copy.copy(self._deps_cpp_info.cflags)
        ret.append(self._architecture_flag)
        if self._build_type == "Debug" and str(self._compiler) in ['gcc', 'clang', 'apple-clang', 'sun-cc']:
            ret.append("-g")  # default debug information
        elif self._build_type == "Release" and self._compiler == "gcc":
            # Remove all symbol table and relocation information from the executable.
            ret.append("-s")
        if self._sysroot_flag:
            ret.append(self._sysroot_flag)
        return ret

    def _configure_cxx_flags(self):
        ret = copy.copy(self._deps_cpp_info.cppflags)
        ret.extend(stdlib_flags(self._compiler, self._libcxx))
        return ret

    def _configure_defines(self):
        # requires declared defines
        ret = copy.copy(self._deps_cpp_info.defines)

        # Debug definition for GCC
        if self._build_type == "Release" and self._compiler == "gcc":
            ret.append("NDEBUG")

        # CXX11 ABI
        ret.extend(stdlib_defines(self._compiler, self._libcxx))
        return ret

    @property
    def _architecture_flag(self):
        if str(self._compiler) in ['gcc', 'clang', 'apple-clang', 'sun-cc']:
            return architecture_dict.get(self._arch, "")
        return ""

    def _get_vars(self):
        def append(*args):
            ret = []
            for arg in args:
                if arg:
                    if isinstance(arg, list):
                        ret.extend(arg)
                    else:
                        ret.append(arg)
            return ret

        if self._compiler == 'Visual Studio':
            lib_paths = ['/LIBPATH:%s' % x.replace("/", "\\") for x in self.library_paths]
            include_paths = ['-I%s' % x.replace("/", "\\") for x in self.include_paths]
            libs = [lib for lib in self.libs]
        else:
            lib_paths = ['-L%s' % self._adjust_path(x.replace("\\", "/")) for x in self.library_paths]
            include_paths = ['-I%s' % self._adjust_path(x.replace("\\", "/")) for x in self.include_paths]
            libs = ['-l%s' % lib for lib in self.libs]

        ld_flags = append(self.link_flags, lib_paths)

        cpp_flags = append(include_paths, ["-D%s" % x for x in self.defines])

        tmp_compilation_flags = copy.copy(self.flags)
        if self.fpic and not self._compiler == 'Visual Studio':
            tmp_compilation_flags.append("-fPIC")

        cxx_flags = append(tmp_compilation_flags, self.cxx_flags)
        c_flags = tmp_compilation_flags

        return ld_flags, cpp_flags, libs, cxx_flags, c_flags

    @property
    def vars_dict(self):

        ld_flags, cpp_flags, libs, cxx_flags, c_flags = self._get_vars()

        if os.environ.get("CPPFLAGS", None):
            cpp_flags.append(os.environ.get("CPPFLAGS", None))

        if os.environ.get("CXXFLAGS", None):
            cxx_flags.append(os.environ.get("CXXFLAGS", None))

        if os.environ.get("CFLAGS", None):
            c_flags.append(os.environ.get("CFLAGS", None))

        if os.environ.get("LDFLAGS", None):
            ld_flags.append(os.environ.get("LDFLAGS", None))

        if os.environ.get("LIBS", None):
            libs.append(os.environ.get("LIBS", None))

        ret = {"CPPFLAGS": cpp_flags,
               "CXXFLAGS": cxx_flags,
               "CFLAGS": c_flags,
               "LDFLAGS": ld_flags,
               "LIBS": libs,
               }
        return ret

    @property
    def vars(self):

        ld_flags, cpp_flags, libs, cxx_flags, c_flags = self._get_vars()

        cpp_flags = " ".join(cpp_flags) + _environ_value_prefix("CPPFLAGS")
        cxx_flags = " ".join(cxx_flags) + _environ_value_prefix("CXXFLAGS")
        cflags = " ".join(c_flags) + _environ_value_prefix("CFLAGS")
        ldflags = " ".join(ld_flags) + _environ_value_prefix("LDFLAGS")
        libs = " ".join(libs) + _environ_value_prefix("LIBS")

        ret = {"CPPFLAGS": cpp_flags.strip(),
               "CXXFLAGS": cxx_flags.strip(),
               "CFLAGS": cflags.strip(),
               "LDFLAGS": ldflags.strip(),
               "LIBS": libs.strip(),
               }

        return ret


def _environ_value_prefix(var_name, prefix=" "):
    if os.environ.get(var_name, ""):
        return "%s%s" % (prefix, os.environ.get(var_name, ""))
    else:
        return ""
