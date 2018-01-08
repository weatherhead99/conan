import os
from conans.client.runner import ConanRunner
from conans.client.tools.oss import OSInfo
from conans.errors import ConanException
from io import StringIO

_global_output = None


class SystemPackageTool(object):

    def __init__(self, runner=None, os_info=None, tool=None, recommends=False):
        env_sudo = os.environ.get("CONAN_SYSREQUIRES_SUDO", None)
        self._sudo = (env_sudo != "False" and env_sudo != "0")
        if env_sudo is None and os.name == 'posix' and os.geteuid() == 0:
            self._sudo = False
        if env_sudo is None and os.name == 'nt':
            self._sudo = False
        os_info = os_info or OSInfo()
        self._is_up_to_date = False
        self._tool = tool or self._create_tool(os_info)
        self._tool._sudo_str = "sudo " if self._sudo else ""
        self._tool._runner = runner or ConanRunner()
        self._tool._recommends = recommends

    @staticmethod
    def _create_tool(os_info):
        if os_info.with_apt:
            return AptTool()
        elif os_info.with_yum:
            return YumTool()
        elif os_info.with_pacman:
            return PacManTool()
        elif os_info.is_macos:
            return BrewTool()
        elif os_info.is_freebsd:
            return PkgTool()
        elif os_info.is_solaris:
            return PkgUtilTool()
        elif os_info.with_zypper:
            return ZypperTool()
        else:
            return NullTool()

    def update(self):
        """
            Get the system package tool update command
        """
        self._is_up_to_date = True
        self._tool.update()

    def install(self, packages, update=True, force=False):
        """
            Get the system package tool install command.
        '"""
        packages = [packages] if isinstance(packages, str) else list(packages)
        if not force and self._installed(packages):
            return
        if update and not self._is_up_to_date:
            self.update()
        self._install_any(packages)

    def _installed(self, packages):
        for pkg in packages:
            if self._tool.installed(pkg):
                _global_output.info("Package already installed: %s" % pkg)
                return True
        return False

    def _install_any(self, packages):
        if len(packages) == 1:
            return self._tool.install(packages[0])
        for pkg in packages:
            try:
                return self._tool.install(pkg)
            except ConanException:
                pass
        raise ConanException("Could not install any of %s" % packages)

    def installed_version(self, package):
        if not self._installed([package]):
            raise ConanException("package %s is not installed")
        version = self._tool.installed_version(package)
        return version



class NullTool(object):
    def update(self):
        pass

    def install(self, package_name):
        _global_output.warn("Only available for linux with apt-get, yum, or pacman or OSX with brew or "
                            "FreeBSD with pkg or Solaris with pkgutil")

    def installed(self, package_name):
        return False
    
    def installed_version(self,package_name):
        return None



class AptTool(object):
    def update(self):
        _run(self._runner, "%sapt-get update" % self._sudo_str)

    def install(self, package_name):
        recommends_str = '' if self._recommends else '--no-install-recommends '
        _run(self._runner, "%sapt-get install -y %s%s" % (self._sudo_str, recommends_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner("dpkg -s %s" % package_name, None)
        return exit_code == 0

    def installed_version(self,package_name):
        output = _run_get_output(self._runner, "apt-cache policy %s" % package_name)
        return output.splitlines()[1].split(":")[1].strip()
        

class YumTool(object):
    def update(self):
        _run(self._runner, "%syum check-update" % self._sudo_str, accepted_returns=[0, 100])

    def install(self, package_name):
        _run(self._runner, "%syum install -y %s" % (self._sudo_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner("rpm -q %s" % package_name, None)
        return exit_code == 0
    
    def installed_version(self,package_name):
        output = _run_get_output(self._runner, "rpm -qv %s" % package_name)        
        return ".".join(output.strip(package_name+"-").split(".")[:-1])
    
    

class BrewTool(object):
    def update(self):
        _run(self._runner, "brew update")

    def install(self, package_name):
        _run(self._runner, "brew install %s" % package_name)

    def installed(self, package_name):
        exit_code = self._runner('test -n "$(brew ls --versions %s)"' % package_name, None)
        return exit_code == 0


class PkgTool(object):
    def update(self):
        _run(self._runner, "%spkg update" % self._sudo_str)

    def install(self, package_name):
        _run(self._runner, "%spkg install -y %s" % (self._sudo_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner("pkg info %s" % package_name, None)
        return exit_code == 0


class PkgUtilTool(object):
    def update(self):
        _run(self._runner, "%spkgutil --catalog" % self._sudo_str)

    def install(self, package_name):
        _run(self._runner, "%spkgutil --install --yes %s" % (self._sudo_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner('test -n "`pkgutil --list %s`"' % package_name, None)
        return exit_code == 0


class ChocolateyTool(object):
    def update(self):
        _run(self._runner, "choco outdated")

    def install(self, package_name):
        _run(self._runner, "choco install --yes %s" % package_name)

    def installed(self, package_name):
        exit_code = self._runner('choco search --local-only --exact %s | findstr /c:"1 packages installed."' % package_name, None)
        return exit_code == 0


class PacManTool(object):
    def update(self):
        _run(self._runner, "%spacman -Syyu --noconfirm" % self._sudo_str)

    def install(self, package_name):
        _run(self._runner, "%spacman -S --noconfirm %s" % (self._sudo_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner("pacman -Qi %s" % package_name, None)
        return exit_code == 0


class ZypperTool(object):
    def update(self):
        _run(self._runner, "%szypper --non-interactive ref" % self._sudo_str)

    def install(self, package_name):
        _run(self._runner, "%szypper --non-interactive in %s" % (self._sudo_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner("rpm -q %s" % package_name, None)
        return exit_code == 0
    
    def installed_version(self, package_name):
        output = _run_get_output(self._runner, "rpm -qv %s" % package_name)
        return ".".join(output.strip(package_name+"-").split(".")[:-1])
    

def _run(runner, command, accepted_returns=None):
    accepted_returns = accepted_returns or [0, ]
    _global_output.info("Running: %s" % command)
    if runner(command, True) not in accepted_returns:
        raise ConanException("Command '%s' failed" % command)


def _run_get_output(runner,command,expected_exit_code=0):
    stream = StringIO()
    exit_code = runner(command,stream)
    if exit_code != expected_exit_code:
        raise ConanException("invalid return code %d running command %s" 
                             % (exit_code,command))
    return stream.getvalue()



if __name__ == "__main__":
    import sys
    from conans.client.output import ConanOutput
    _global_output = ConanOutput(sys.stdout)
    spt = SystemPackageTool()
    
    vers = spt.installed_version("cmake")