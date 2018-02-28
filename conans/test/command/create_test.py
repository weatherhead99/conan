from conans.test.utils.tools import TestClient
import unittest


class CreateTest(unittest.TestCase):

    def transitive_same_name_test(self):
        # https://github.com/conan-io/conan/issues/1366
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "HelloBar"
    version = "0.1"
'''
        test_package = '''
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "HelloBar/0.1@lasote/testing"
    def test(self):
        pass
'''
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("create . lasote/testing")
        self.assertIn("HelloBar/0.1@lasote/testing: WARN: Forced build from source",
                      client.user_io.out)
        client.save({"conanfile.py": conanfile.replace("HelloBar", "Hello") +
                     "    requires='HelloBar/0.1@lasote/testing'",
                     "test_package/conanfile.py": test_package.replace("HelloBar", "Hello")})
        client.run("create . lasote/stable")
        self.assertNotIn("HelloBar/0.1@lasote/testing: WARN: Forced build from source",
                         client.user_io.out)

    def keep_build_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    exports_sources = "*.h"
    def source(self):
        self.output.info("mysource!!")
    def build(self):
        self.output.info("mybuild!!")
    def package(self):
        self.output.info("mypackage!!")
        self.copy("*.h")
"""
        client.save({"conanfile.py": conanfile,
                     "header.h": ""})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)
        # keep the source
        client.save({"conanfile.py": conanfile + " "})
        client.run("create . Pkg/0.1@lasote/testing --keep-source")
        self.assertIn("A new conanfile.py version was exported", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)
        # keep build
        client.run("create . Pkg/0.1@lasote/testing --keep-build")
        self.assertIn("Pkg/0.1@lasote/testing: Won't be built as specified by --keep-build", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)

        # Changes in the recipe again
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing --keep-build")
        # The source folder is removed, but not necessary, as it will reuse build
        self.assertNotIn("Pkg/0.1@lasote/testing: Removing 'source' folder", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Won't be built as specified by --keep-build", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)

    def partial_keep_build_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    exports_sources = "*.h"
    def source(self):
        self.output.info("mysource!!")
    def build(self):
        self.output.info("mybuild!!")
    def package(self):
        self.output.info("mypackage!!")
        self.copy("*.h")
"""
        test_conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "header.h": "",
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)
        # keep the source
        client.save({"conanfile.py": conanfile + " "})
        client.run("create . Pkg/0.1@lasote/testing --keep-source")
        self.assertIn("A new conanfile.py version was exported", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)
        # keep build
        client.run("create . Pkg/0.1@lasote/testing --keep-build")
        self.assertIn("Pkg/0.1@lasote/testing: Won't be built as specified by --keep-build", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)

        # Changes in the recipe again
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing --keep-build")
        # The source folder is removed, but not necessary, as it will reuse build
        self.assertNotIn("Pkg/0.1@lasote/testing: Removing 'source' folder", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Won't be built as specified by --keep-build", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Copied 1 '.h' files: header.h", client.out)

    def keep_build_error_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        error = client.run("create . Pkg/0.1@lasote/testing --keep-build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: --keep-build specified, but build folder not found", client.out)

    def create_test(self):
        client = TestClient()
        client.save({"conanfile.py": """
import os
from conans import ConanFile
class MyPkg(ConanFile):
    def source(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")

    def configure(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def build(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package_info(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
"""})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

        # Create with only user will raise an error because of no name/version
        error = client.run("create conanfile.py lasote/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conanfile.py doesn't declare package name or version", client.out)
        # Same with only user, (default testing)
        error = client.run("create . lasote", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    def create_werror_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    pass
        """})
        client.run("export . LibA/0.1@user/channel")
        client.run("export conanfile.py LibA/0.2@user/channel")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    requires = "LibA/0.1@user/channel"
        """})
        client.run("export ./ LibB/0.1@user/channel")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    requires = "LibA/0.2@user/channel"
        """})
        client.run("export . LibC/0.1@user/channel")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    requires = "LibB/0.1@user/channel", "LibC/0.1@user/channel"
        """})
        error = client.run("create ./conanfile.py Consumer/0.1@lasote/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Conflict in LibC/0.1@user/channel",
                      client.out)

    def test_error_create_name_version(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Hello/1.2@lasote/stable")
        error = client.run("create ./ Pkg/1.2@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe exported with name Pkg!=Hello", client.out)
        error = client.run("create . Hello/1.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe exported with version 1.1!=1.2", client.out)

    def create_user_channel_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
"""})
        client.run("create . lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

        error = client.run("create . lasote", ignore_error=True)  # testing default
        self.assertTrue(error)
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    def create_in_subfolder_test(self):
        client = TestClient()
        client.save({"subfolder/conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
"""})
        client.run("create subfolder lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

    def create_in_subfolder_with_different_name_test(self):
        # Now with a different name
        client = TestClient()
        client.save({"subfolder/CustomConanFile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
"""})
        client.run("create subfolder/CustomConanFile.py lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

    def create_test_package_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
""", "test_package/conanfile.py": """from conans import ConanFile
class MyTest(ConanFile):
    def test(self):
        self.output.info("TESTING!!!")
"""})
        client.run("create . lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): TESTING!!!", client.out)

    def create_skip_test_package_test(self):
        """
        Skip the test package stage if explicitly disabled with --test-folder=None
        """
        # https://github.com/conan-io/conan/issues/2355
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
""", "test_package/conanfile.py": """from conans import ConanFile
class MyTest(ConanFile):
    def test(self):
        self.output.info("TESTING!!!")
"""})
        client.run("create . lasote/testing --test-folder=None")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing (test package): TESTING!!!", client.out)

    def create_test_package_requires(self):
        client = TestClient()
        dep_conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    pass
    """
        client.save({"conanfile.py": dep_conanfile})
        client.run("create . Dep/0.1@user/channel")
        client.run("create . Other/1.0@user/channel")

        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    requires = "Dep/0.1@user/channel"
    """
        test_conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    requires = "Other/1.0@user/channel"
    def build(self):
        for r in self.requires.values():
            self.output.info("build() Requires: %s" % str(r.conan_reference))
        import os
        for dep in self.deps_cpp_info.deps:
            self.output.info("build() cpp_info dep: %s" % dep)
        self.output.info("build() cpp_info: %s"
                         % os.path.basename(self.deps_cpp_info["Pkg"].includedirs[0]))
        self.output.info("build() cpp_info: %s"
                         % os.path.basename(self.deps_cpp_info["Dep"].includedirs[0]))
    def test(self):
        pass
        """
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})

        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info: include", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() "
                      "Requires: Other/1.0@user/channel", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() "
                      "Requires: Pkg/0.1@lasote/testing", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Other",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Dep",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Pkg",
                      client.out)

    def create_with_tests_and_build_requires_test(self):
        client = TestClient()
        # Generate and export the build_require recipe
        client.save({"conanfile.py": """from conans import ConanFile
class MyBuildRequire(ConanFile):
    name = "BuildRequire"
    version = "0.1"

    def package_info(self):
        self.env_info.MYVAR="1"
"""})
        client.run("export . conan/stable")

        # Create a recipe that will use a profile requiring the build_require
        client.save({"conanfile.py": """from conans import ConanFile
import os

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"

    def build(self):
        assert(os.environ['MYVAR']=='1')

""", "myprofile": '''
[build_requires]
BuildRequire/0.1@conan/stable
''',
                    "test_package/conanfile.py": """from conans import ConanFile
import os

class MyTest(ConanFile):
    def build(self):
        assert(os.environ['MYVAR']=='1')
    def test(self):
        self.output.info("TESTING!!!")
"""}, clean_first=True)

        # Test that the build require is applyed to testing
        client.run("create . conan/stable --profile ./myprofile --build missing")
        self.assertIn("TESTING!!", client.user_io.out)

    def build_policy_test(self):
        # https://github.com/conan-io/conan/issues/1956
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "HelloBar"
    version = "0.1"
    build_policy = "always"
'''
        test_package = '''
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "HelloBar/0.1@lasote/testing"
    def test(self):
        pass
'''
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("create . lasote/testing")
        self.assertIn("HelloBar/0.1@lasote/testing: WARN: Forced build from source",
                      client.out)
        client.save({"conanfile.py": conanfile.replace("HelloBar", "Hello") +
                     "    requires='HelloBar/0.1@lasote/testing'",
                     "test_package/conanfile.py": test_package.replace("HelloBar", "Hello")})
        client.run("create . lasote/stable")
        self.assertIn("HelloBar/0.1@lasote/testing: WARN: Forced build from source",
                      client.out)
