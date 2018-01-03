import platform
import logging
import re
import os
import sys

from contextlib import contextmanager
from patch import fromfile, fromstring

from conans.client.output import ConanOutput
from conans.errors import ConanException
from conans.util.files import load, save, _generic_algorithm_sum

import gnupg
from gnupg._util import find_encodings

#create a GPG object. If gpg not available on the system, catch the error
#and the method will fail later
try:
    _gpg = gnupg.GPG()
except RuntimeError as err:
    _gpg = None
    _gpg_error = err.args[0]


#this is a "monkey-patch" which fixes python-gnupg for binary file 
#comparisons in python 3. It has been submitted upstream at 
# https://github.com/isislovecruft/python-gnupg/pull/218
def fixed_binary(data):
    coder = find_encodings()
    if isinstance(data, str):
        encoded = coder.encode(data)[0]
    else:
        encoded = data
    return encoded    

if sys.version_info.major == 3:
    gnupg._util.binary = fixed_binary



_global_output = None


@contextmanager
def chdir(newdir):
    old_path = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(old_path)


def human_size(size_bytes):
    """
    format a size in bytes into a 'human' file size, e.g. B, KB, MB, GB, TB, PB
    Note that bytes will be reported in whole numbers but KB and above will have
    greater precision.  e.g. 43 B, 443 KB, 4.3 MB, 4.43 GB, etc
    """

    suffixes_table = [('B', 0), ('KB', 1), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

    num = float(size_bytes)
    for suffix, precision in suffixes_table:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s%s" % (formatted_size, suffix)


def unzip(filename, destination=".", keep_permissions=False):
    """
    Unzip a zipped file
    :param filename: Path to the zip file
    :param destination: Destination folder
    :param keep_permissions: Keep the zip permissions. WARNING: Can be dangerous if the zip was not created in a NIX
    system, the bits could produce undefined permission schema. Use only this option if you are sure that the
    zip was created correctly.
    :return:
    """
    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination)
    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        def print_progress(the_size, uncomp_size):
            the_size = (the_size * 100.0 / uncomp_size) if uncomp_size != 0 else 0
            if the_size > print_progress.last_size + 1:
                txt_msg = "Unzipping %d %%" % the_size
                _global_output.rewrite_line(txt_msg)
                print_progress.last_size = the_size
    else:
        def print_progress(_, __):
            pass

    with zipfile.ZipFile(filename, "r") as z:
        uncompress_size = sum((file_.file_size for file_ in z.infolist()))
        if uncompress_size > 100000:
            _global_output.info("Unzipping %s, this can take a while" % human_size(uncompress_size))
        else:
            _global_output.info("Unzipping %s" % human_size(uncompress_size))
        extracted_size = 0

        print_progress.last_size = -1
        if platform.system() == "Windows":
            for file_ in z.infolist():
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                except Exception as e:
                    _global_output.error("Error extract %s\n%s" % (file_.filename, str(e)))
        else:  # duplicated for, to avoid a platform check for each zipped file
            for file_ in z.infolist():
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                    if keep_permissions:
                        # Could be dangerous if the ZIP has been created in a non nix system
                        # https://bugs.python.org/issue15795
                        perm = file_.external_attr >> 16 & 0xFFF
                        os.chmod(os.path.join(full_path, file_.filename), perm)
                except Exception as e:
                    _global_output.error("Error extract %s\n%s" % (file_.filename, str(e)))


def untargz(filename, destination="."):
    import tarfile
    with tarfile.TarFile.open(filename, 'r:*') as tarredgzippedFile:
        tarredgzippedFile.extractall(destination)


def check_with_algorithm_sum(algorithm_name, file_path, signature):
    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature:
        raise ConanException("%s signature failed for '%s' file. \n"
                             " Provided signature: %s  \n"
                             " Computed signature: %s" % (algorithm_name,
                                                          os.path.basename(file_path),
                                                          signature,
                                                          real_signature))


def check_sha1(file_path, signature):
    check_with_algorithm_sum("sha1", file_path, signature)


def check_md5(file_path, signature):
    check_with_algorithm_sum("md5", file_path, signature)


def check_sha256(file_path, signature):
    check_with_algorithm_sum("sha256", file_path, signature)


def patch(base_path=None, patch_file=None, patch_string=None, strip=0, output=None):
    """Applies a diff from file (patch_file)  or string (patch_string)
    in base_path directory or current dir if None"""

    class PatchLogHandler(logging.Handler):
        def __init__(self):
            logging.Handler.__init__(self, logging.DEBUG)
            self.output = output or ConanOutput(sys.stdout, True)
            self.patchname = patch_file if patch_file else "patch"

        def emit(self, record):
            logstr = self.format(record)
            if record.levelno == logging.WARN:
                self.output.warn("%s: %s" % (self.patchname, logstr))
            else:
                self.output.info("%s: %s" % (self.patchname, logstr))

    patchlog = logging.getLogger("patch")
    if patchlog:
        patchlog.handlers = []
        patchlog.addHandler(PatchLogHandler())

    if not patch_file and not patch_string:
        return
    if patch_file:
        patchset = fromfile(patch_file)
    else:
        patchset = fromstring(patch_string.encode())

    if not patchset:
        raise ConanException("Failed to parse patch: %s" % (patch_file if patch_file else "string"))

    # account for new and deleted files, upstream dep won't fix them
    items = []
    for p in patchset:
        source = p.source.decode("utf-8")
        if source.startswith("a/"):
            source = source[2:]
        target = p.target.decode("utf-8")
        if target.startswith("b/"):
            target = target[2:]
        if "dev/null" in source:
            if base_path:
                target = os.path.join(base_path, target)
            hunks = [s.decode("utf-8") for s in p.hunks[0].text]
            new_file = "".join(hunk[1:] for hunk in hunks)
            save(target, new_file)
        elif "dev/null" in target:
            if base_path:
                source = os.path.join(base_path, source)
            os.unlink(source)
        else:
            items.append(p)
    patchset.items = items

    if not patchset.apply(root=base_path, strip=strip):
        raise ConanException("Failed to apply patch: %s" % patch_file)


def replace_in_file(file_path, search, replace, strict=True):
    content = load(file_path)
    if -1 == content.find(search):
        message = "replace_in_file didn't find pattern '%s' in '%s' file." % (search, file_path)
        if strict:
            raise ConanException(message)
        else:
            _global_output.warn(message)
    content = content.replace(search, replace)
    content = content.encode("utf-8")
    with open(file_path, "wb") as handle:
        handle.write(content)


def replace_prefix_in_pc_file(pc_file, new_prefix):
    content = load(pc_file)
    lines = []
    for line in content.splitlines():
        if line.startswith("prefix="):
            lines.append('prefix=%s' % new_prefix)
        else:
            lines.append(line)
    save(pc_file, "\n".join(lines))


MSYS2 = 'msys2'
MSYS = 'msys'
CYGWIN = 'cygwin'
WSL = 'wsl'  # Windows Subsystem for Linux
SFU = 'sfu'  # Windows Services for UNIX


def unix_path(path, path_flavor=None):
    """"Used to translate windows paths to MSYS unix paths like
    c/users/path/to/file. Not working in a regular console or MinGW!"""
    if not path:
        return None
    from conans.client.tools.oss import os_info
    path_flavor = path_flavor or os_info.detect_windows_subsystem() or MSYS2
    path = path.replace(":/", ":\\")
    pattern = re.compile(r'([a-z]):\\', re.IGNORECASE)
    path = pattern.sub('/\\1/', path).replace('\\', '/')
    if path_flavor in (MSYS, MSYS2):
        return path.lower()
    elif path_flavor == CYGWIN:
        return '/cygdrive' + path.lower()
    elif path_flavor == WSL:
        return '/mnt' + path[0:2].lower() + path[2:]
    elif path_flavor == SFU:
        path = path.lower()
        return '/dev/fs' + path[0] + path[1:].capitalize()
    return None


def collect_libs(conanfile, folder="lib"):
    if not conanfile.package_folder:
        return []
    lib_folder = os.path.join(conanfile.package_folder, folder)
    if not os.path.exists(lib_folder):
        conanfile.output.warn("Lib folder doesn't exist, can't collect libraries: {0}".format(lib_folder))
        return []
    files = os.listdir(lib_folder)
    result = []
    for f in files:
        name, ext = os.path.splitext(f)
        if ext in (".so", ".lib", ".a", ".dylib"):
            if ext != ".lib" and name.startswith("lib"):
                name = name[3:]
            result.append(name)
    return result


def which(filename):
    """ same affect as posix which command or shutil.which from python3 """
    def verify(filepath):
        if os.path.exists(filepath) and os.access(filepath, os.X_OK):
            return os.path.join(path, filename)
        return None

    def _get_possible_filenames(filename):
        extensions_win = os.getenv("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if not "." in filename else []
        extensions = [".sh"] if platform.system() != "Windows" else extensions_win
        extensions.insert(1, "")  # No extension
        return ["%s%s" % (filename, entry.lower()) for entry in extensions]

    possible_names = _get_possible_filenames(filename)
    for path in os.environ["PATH"].split(os.pathsep):
        for name in possible_names:
            filepath = os.path.abspath(os.path.join(path, name))
            if verify(filepath):
                return filepath
            if platform.system() == "Windows":
                filepath = filepath.lower()
                if "system32" in filepath:  # python return False for os.path.exists of exes in System32 but with SysNative
                    trick_path = filepath.replace("system32", "sysnative")
                    if verify(trick_path):
                        return trick_path

    return None


def verify_gpg_sig(data_file, pubkey,sig_file=None,delete_after=True):
    """ verify a supplied GPG signature for a file.
        
        data_file: filename of the data to verify, e.g. "awesome-lib-v1.tar.gz"
        
        pubkey: either a filename or key fingerprint / keyid of the public key
        e.g. "developer_pubkey.txt" or "0B8DA90F"
        
        sig_file: file name of detached signature, e.g. 
        "awesome-lib-v1.tar.gz.sig" or "awesome-lib-v1.tar.gz.asc"
        if not provided, assume a signature is present in the file itself
    
        
    """
    if not _gpg:
        raise ConanException("pygnupg was unable to find GPG binary. Reported error was: %s"
                             % _gpg_error)

    #import pubkey from a file
    if os.path.isfile(pubkey):
        with open(pubkey, "r") as f:
            import_key_result = _gpg.import_keys(f.read())
    else:
        import_key_result = _gpg.recv_keys(pubkey)

    #check if key was imported correctly
    fingerprint = import_key_result.results[0]["fingerprint"]
    if fingerprint is None:
        raise ConanException("failed to import public key from file")

    try:
        with open(data_file,"rb") as f:
            
            if sig_file is None:
                verify_result = _gpg.verify_file(f)
            else:
                verify_result = _gpg.verify_file(f,sig_file=sig_file)
                
    finally:
        #cleanup 
        delete_result = _gpg.delete_keys(fingerprint)
        if delete_result.status != 'ok':
            ConanOutput(sys.stdout).warn("couldn't cleanup GPG keyring")

    if not verify_result.valid:
        raise ConanException("""GPG signature verification failed for file: %s
                                using pubkey with fingerprint : %s. 
                                status message is: %s 
                                """ % (data_file,fingerprint,verify_result.status))

    

