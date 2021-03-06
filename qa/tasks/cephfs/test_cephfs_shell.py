"""
Before running this testsuite, add path to cephfs-shell module to $PATH and
export $PATH.
"""
from os import path
import crypt
import logging
from tempfile import mkstemp as tempfile_mkstemp
import math
from sys import version_info as sys_version_info
from re import search as re_search
from time import sleep
from StringIO import StringIO
from tasks.cephfs.cephfs_test_case import CephFSTestCase
from tasks.cephfs.fuse_mount import FuseMount
from teuthology.exceptions import CommandFailedError
from teuthology.misc import sudo_write_file

log = logging.getLogger(__name__)

def humansize(nbytes):
    suffixes = ['B', 'K', 'M', 'G', 'T', 'P']
    i = 0
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    nbytes = math.ceil(nbytes)
    f = ('%d' % nbytes).rstrip('.')
    return '%s%s' % (f, suffixes[i])

class TestCephFSShell(CephFSTestCase):
    CLIENTS_REQUIRED = 1

    def run_cephfs_shell_cmd(self, cmd, mount_x=None, opts=None, stdin=None):
        if mount_x is None:
            mount_x = self.mount_a

        if isinstance(cmd, list):
            cmd = " ".join(cmd)

        args = ["cephfs-shell", "-c", mount_x.config_path]
        if opts is not None:
            args.extend(opts)

        args.extend(("--", cmd))

        log.info("Running command: {}".format(" ".join(args)))
        return mount_x.client_remote.run(args=args, stdout=StringIO(),
                                         stderr=StringIO(), stdin=stdin)

    def get_cephfs_shell_cmd_output(self, cmd, mount_x=None, opts=None,
                                    stdin=None):
        return self.run_cephfs_shell_cmd(cmd, mount_x, opts, stdin).stdout.\
            getvalue().strip()

    def get_cephfs_shell_script_output(self, script, mount_x=None, stdin=None):
        return self.run_cephfs_shell_script(script, mount_x, stdin).stdout.\
            getvalue().strip()

    def run_cephfs_shell_script(self, script, mount_x=None, stdin=None):
        if mount_x is None:
            mount_x = self.mount_a

        scriptpath = tempfile_mkstemp(prefix='test-cephfs', text=True)[1]
        with open(scriptpath, 'w') as scriptfile:
            scriptfile.write(script)
        # copy script to the machine running cephfs-shell.
        mount_x.client_remote.put_file(scriptpath, scriptpath)
        mount_x.run_shell('chmod 755 ' + scriptpath)

        args = ["cephfs-shell", "-c", mount_x.config_path, '-b', scriptpath]
        log.info('Running script \"' + scriptpath + '\"')
        return mount_x.client_remote.run(args=args, stdout=StringIO(),
                                         stderr=StringIO(), stdin=stdin)

class TestMkdir(TestCephFSShell):
    def test_mkdir(self):
        """
        Test that mkdir creates directory
        """
        o = self.get_cephfs_shell_cmd_output("mkdir d1")
        log.info("cephfs-shell output:\n{}".format(o))

        o = self.mount_a.stat('d1')
        log.info("mount_a output:\n{}".format(o))

    def test_mkdir_with_07000_octal_mode(self):
        """
        Test that mkdir fails with octal mode greater than 0777
        """
        o = self.get_cephfs_shell_cmd_output("mkdir -m 07000 d2")
        log.info("cephfs-shell output:\n{}".format(o))

        # mkdir d2 should fail
        try:
            o = self.mount_a.stat('d2')
            log.info("mount_a output:\n{}".format(o))
        except:
            pass

    def test_mkdir_with_negative_octal_mode(self):
        """
        Test that mkdir fails with negative octal mode
        """
        o = self.get_cephfs_shell_cmd_output("mkdir -m -0755 d3")
        log.info("cephfs-shell output:\n{}".format(o))

        # mkdir d3 should fail
        try:
            o = self.mount_a.stat('d3')
            log.info("mount_a output:\n{}".format(o))
        except:
            pass

    def test_mkdir_with_non_octal_mode(self):
        """
        Test that mkdir passes with non-octal mode
        """
        o = self.get_cephfs_shell_cmd_output("mkdir -m u=rwx d4")
        log.info("cephfs-shell output:\n{}".format(o))

        # mkdir d4 should pass
        o = self.mount_a.stat('d4')
        assert((o['st_mode'] & 0o700) == 0o700)

    def test_mkdir_with_bad_non_octal_mode(self):
        """
        Test that mkdir failes with bad non-octal mode
        """
        o = self.get_cephfs_shell_cmd_output("mkdir -m ugx=0755 d5")
        log.info("cephfs-shell output:\n{}".format(o))

        # mkdir d5 should fail
        try:
            o = self.mount_a.stat('d5')
            log.info("mount_a output:\n{}".format(o))
        except:
            pass

    def test_mkdir_path_without_path_option(self):
        """
        Test that mkdir fails without path option for creating path
        """
        o = self.get_cephfs_shell_cmd_output("mkdir d5/d6/d7")
        log.info("cephfs-shell output:\n{}".format(o))

        # mkdir d5/d6/d7 should fail
        try:
            o = self.mount_a.stat('d5/d6/d7')
            log.info("mount_a output:\n{}".format(o))
        except:
            pass

    def test_mkdir_path_with_path_option(self):
        """
        Test that mkdir passes with path option for creating path
        """
        o = self.get_cephfs_shell_cmd_output("mkdir -p d5/d6/d7")
        log.info("cephfs-shell output:\n{}".format(o))

        # mkdir d5/d6/d7 should pass
        o = self.mount_a.stat('d5/d6/d7')
        log.info("mount_a output:\n{}".format(o))

class TestGetAndPut(TestCephFSShell):
    # the 'put' command gets tested as well with the 'get' comamnd
    def test_put_and_get_without_target_directory(self):
        """
        Test that put fails without target path
        """
        # generate test data in a directory
        self.run_cephfs_shell_cmd("!mkdir p1")
        self.run_cephfs_shell_cmd('!dd if=/dev/urandom of=p1/dump1 bs=1M count=1')
        self.run_cephfs_shell_cmd('!dd if=/dev/urandom of=p1/dump2 bs=2M count=1')
        self.run_cephfs_shell_cmd('!dd if=/dev/urandom of=p1/dump3 bs=3M count=1')

        # copy the whole directory over to the cephfs
        o = self.get_cephfs_shell_cmd_output("put p1")
        log.info("cephfs-shell output:\n{}".format(o))

        # put p1 should pass
        o = self.mount_a.stat('p1')
        log.info("mount_a output:\n{}".format(o))
        o = self.mount_a.stat('p1/dump1')
        log.info("mount_a output:\n{}".format(o))
        o = self.mount_a.stat('p1/dump2')
        log.info("mount_a output:\n{}".format(o))
        o = self.mount_a.stat('p1/dump3')
        log.info("mount_a output:\n{}".format(o))

        self.run_cephfs_shell_cmd('!rm -rf p1')
        o = self.get_cephfs_shell_cmd_output("get p1")
        o = self.get_cephfs_shell_cmd_output('!stat p1 || echo $?')
        log.info("cephfs-shell output:\n{}".format(o))
        self.validate_stat_output(o)

        o = self.get_cephfs_shell_cmd_output('!stat p1/dump1 || echo $?')
        log.info("cephfs-shell output:\n{}".format(o))
        self.validate_stat_output(o)

        o = self.get_cephfs_shell_cmd_output('!stat p1/dump2 || echo $?')
        log.info("cephfs-shell output:\n{}".format(o))
        self.validate_stat_output(o)

        o = self.get_cephfs_shell_cmd_output('!stat p1/dump3 || echo $?')
        log.info("cephfs-shell output:\n{}".format(o))
        self.validate_stat_output(o)

    def validate_stat_output(self, s):
        l = s.split('\n')
        log.info("lines:\n{}".format(l))
        rv = l[-1] # get last line; a failed stat will have "1" as the line
        log.info("rv:{}".format(rv))
        r = 0
        try:
            r = int(rv) # a non-numeric line will cause an exception
        except:
            pass
        assert(r == 0)

    def test_get_with_target_name(self):
        """
        Test that get passes with target name
        """
        s = 'C' * 1024
        s_hash = crypt.crypt(s, '.A')
        o = self.get_cephfs_shell_cmd_output("put - dump4", stdin=s)
        log.info("cephfs-shell output:\n{}".format(o))

        # put - dump4 should pass
        o = self.mount_a.stat('dump4')
        log.info("mount_a output:\n{}".format(o))

        o = self.get_cephfs_shell_cmd_output("get dump4 .")
        log.info("cephfs-shell output:\n{}".format(o))

        o = self.get_cephfs_shell_cmd_output("!cat dump4")
        o_hash = crypt.crypt(o, '.A')

        # s_hash must be equal to o_hash
        log.info("s_hash:{}".format(s_hash))
        log.info("o_hash:{}".format(o_hash))
        assert(s_hash == o_hash)

    def test_get_without_target_name(self):
        """
        Test that get passes with target name
        """
        s = 'D' * 1024
        o = self.get_cephfs_shell_cmd_output("put - dump5", stdin=s)
        log.info("cephfs-shell output:\n{}".format(o))

        # put - dump5 should pass
        o = self.mount_a.stat('dump5')
        log.info("mount_a output:\n{}".format(o))

        # get dump5 should fail
        o = self.get_cephfs_shell_cmd_output("get dump5")
        o = self.get_cephfs_shell_cmd_output("!stat dump5 || echo $?")
        log.info("cephfs-shell output:\n{}".format(o))
        l = o.split('\n')
        try:
            ret = int(l[1])
            # verify that stat dump5 passes
            # if ret == 1, then that implies the stat failed
            # which implies that there was a problem with "get dump5"
            assert(ret != 1)
        except ValueError:
            # we have a valid stat output; so this is good
            # if the int() fails then that means there's a valid stat output
            pass

    def test_get_to_console(self):
        """
        Test that get passes with target name
        """
        s = 'E' * 1024
        s_hash = crypt.crypt(s, '.A')
        o = self.get_cephfs_shell_cmd_output("put - dump6", stdin=s)
        log.info("cephfs-shell output:\n{}".format(o))

        # put - dump6 should pass
        o = self.mount_a.stat('dump6')
        log.info("mount_a output:\n{}".format(o))

        # get dump6 - should pass
        o = self.get_cephfs_shell_cmd_output("get dump6 -")
        o_hash = crypt.crypt(o, '.A')
        log.info("cephfs-shell output:\n{}".format(o))

        # s_hash must be equal to o_hash
        log.info("s_hash:{}".format(s_hash))
        log.info("o_hash:{}".format(o_hash))
        assert(s_hash == o_hash)

class TestCD(TestCephFSShell):
    CLIENTS_REQUIRED = 1

    def test_cd_with_no_args(self):
        """
        Test that when cd is issued without any arguments, CWD is changed
        to root directory.
        """
        path = 'dir1/dir2/dir3'
        self.mount_a.run_shell('mkdir -p ' + path)
        expected_cwd = '/'

        script = 'cd {}\ncd\ncwd\n'.format(path)
        output = self.get_cephfs_shell_script_output(script)
        self.assertEqual(output, expected_cwd)

    def test_cd_with_args(self):
        """
        Test that when cd is issued with an argument, CWD is changed
        to the path passed in the argument.
        """
        path = 'dir1/dir2/dir3'
        self.mount_a.run_shell('mkdir -p ' + path)
        expected_cwd = '/dir1/dir2/dir3'

        script = 'cd {}\ncwd\n'.format(path)
        output = self.get_cephfs_shell_script_output(script)
        self.assertEqual(output, expected_cwd)

class TestDU(TestCephFSShell):
    CLIENTS_REQUIRED = 1

    def test_du_works_for_regfiles(self):
        regfilename = 'some_regfile'
        regfile_abspath = path.join(self.mount_a.mountpoint, regfilename)
        sudo_write_file(self.mount_a.client_remote, regfile_abspath, 'somedata')

        size = humansize(self.mount_a.stat(regfile_abspath)['st_size'])
        expected_output = r'{}{}{}'.format(size, " +", regfilename)

        du_output = self.get_cephfs_shell_cmd_output('du ' + regfilename)
        if sys_version_info.major >= 3:
            self.assertRegex(expected_output, du_output)
        elif sys_version_info.major < 3:
            assert re_search(expected_output, du_output) != None, "\n" + \
                   "expected_output -\n{}\ndu_output -\n{}\n".format(
                   expected_output, du_output)

    def test_du_works_for_non_empty_dirs(self):
        dirname = 'some_directory'
        dir_abspath = path.join(self.mount_a.mountpoint, dirname)
        regfilename = 'some_regfile'
        regfile_abspath = path.join(dir_abspath, regfilename)
        self.mount_a.run_shell('mkdir ' + dir_abspath)
        sudo_write_file(self.mount_a.client_remote, regfile_abspath, 'somedata')

        # XXX: we stat `regfile_abspath` here because ceph du reports a non-empty
        # directory's size as sum of sizes of all files under it.
        size = humansize(self.mount_a.stat(regfile_abspath)['st_size'])
        expected_output = r'{}{}{}'.format(size, " +", dirname)

        sleep(10)
        du_output = self.get_cephfs_shell_cmd_output('du ' + dirname)
        if sys_version_info.major >= 3:
            self.assertRegex(expected_output, du_output)
        elif sys_version_info.major < 3:
            assert re_search(expected_output, du_output) != None, "\n" + \
                   "expected_output -\n{}\ndu_output -\n{}\n".format(
                   expected_output, du_output)

    def test_du_works_for_empty_dirs(self):
        dirname = 'some_directory'
        dir_abspath = path.join(self.mount_a.mountpoint, dirname)
        self.mount_a.run_shell('mkdir ' + dir_abspath)

        size = humansize(self.mount_a.stat(dir_abspath)['st_size'])
        expected_output = r'{}{}{}'.format(size, " +", dirname)

        du_output = self.get_cephfs_shell_cmd_output('du ' + dirname)
        if sys_version_info.major >= 3:
            self.assertRegex(expected_output, du_output)
        elif sys_version_info.major < 3:
            assert re_search(expected_output, du_output) != None, "\n" + \
                   "expected_output -\n{}\ndu_output -\n{}\n".format(
                   expected_output, du_output)

    def test_du_works_for_hardlinks(self):
        regfilename = 'some_regfile'
        regfile_abspath = path.join(self.mount_a.mountpoint, regfilename)
        sudo_write_file(self.mount_a.client_remote, regfile_abspath, 'somedata')
        hlinkname = 'some_hardlink'
        hlink_abspath = path.join(self.mount_a.mountpoint, hlinkname)
        self.mount_a.run_shell(['ln', regfile_abspath, hlink_abspath])

        size = humansize(self.mount_a.stat(hlink_abspath)['st_size'])
        expected_output = r'{}{}{}'.format(size, " +", hlinkname)

        du_output = self.get_cephfs_shell_cmd_output('du ' + hlinkname)
        if sys_version_info.major >= 3:
            self.assertRegex(expected_output, du_output)
        elif sys_version_info.major < 3:
            assert re_search(expected_output, du_output) != None, "\n" + \
                   "expected_output -\n{}\ndu_output -\n{}\n".format(
                   expected_output, du_output)

    def test_du_works_for_softlinks_to_files(self):
        regfilename = 'some_regfile'
        regfile_abspath = path.join(self.mount_a.mountpoint, regfilename)
        sudo_write_file(self.mount_a.client_remote, regfile_abspath, 'somedata')
        slinkname = 'some_softlink'
        slink_abspath = path.join(self.mount_a.mountpoint, slinkname)
        self.mount_a.run_shell(['ln', '-s', regfile_abspath, slink_abspath])

        size = humansize(self.mount_a.lstat(slink_abspath)['st_size'])
        expected_output = r'{}{}{}'.format((size), " +", slinkname)

        du_output = self.get_cephfs_shell_cmd_output('du ' + slinkname)
        if sys_version_info.major >= 3:
            self.assertRegex(expected_output, du_output)
        elif sys_version_info.major < 3:
            assert re_search(expected_output, du_output) != None, "\n" + \
                   "expected_output -\n{}\ndu_output -\n{}\n".format(
                   expected_output, du_output)

    def test_du_works_for_softlinks_to_dirs(self):
        dirname = 'some_directory'
        dir_abspath = path.join(self.mount_a.mountpoint, dirname)
        self.mount_a.run_shell('mkdir ' + dir_abspath)
        slinkname = 'some_softlink'
        slink_abspath = path.join(self.mount_a.mountpoint, slinkname)
        self.mount_a.run_shell(['ln', '-s', dir_abspath, slink_abspath])

        size = humansize(self.mount_a.lstat(slink_abspath)['st_size'])
        expected_output = r'{}{}{}'.format(size, " +", slinkname)

        du_output = self.get_cephfs_shell_cmd_output('du ' + slinkname)
        if sys_version_info.major >= 3:
            self.assertRegex(expected_output, du_output)
        elif sys_version_info.major < 3:
            assert re_search(expected_output, du_output) != None, "\n" + \
                   "expected_output -\n{}\ndu_output -\n{}\n".format(
                   expected_output, du_output)

    # NOTE: tests using these are pretty slow since to this methods sleeps for 15
    # seconds.
    def _setup_files(self, return_path_to_files=False, path_prefix='./'):
        dirname = 'dir1'
        regfilename = 'regfile'
        hlinkname = 'hlink'
        slinkname = 'slink1'
        slink2name = 'slink2'

        dir_abspath = path.join(self.mount_a.mountpoint, dirname)
        regfile_abspath = path.join(self.mount_a.mountpoint, regfilename)
        hlink_abspath = path.join(self.mount_a.mountpoint, hlinkname)
        slink_abspath = path.join(self.mount_a.mountpoint, slinkname)
        slink2_abspath = path.join(self.mount_a.mountpoint, slink2name)

        self.mount_a.run_shell('mkdir ' + dir_abspath)
        self.mount_a.run_shell('touch ' + regfile_abspath)
        self.mount_a.run_shell(['ln', regfile_abspath, hlink_abspath])
        self.mount_a.run_shell(['ln', '-s', regfile_abspath, slink_abspath])
        self.mount_a.run_shell(['ln', '-s', dir_abspath, slink2_abspath])

        dir2_name = 'dir2'
        dir21_name = 'dir21'
        regfile121_name = 'regfile121'
        dir2_abspath = path.join(self.mount_a.mountpoint, dir2_name)
        dir21_abspath = path.join(dir2_abspath, dir21_name)
        regfile121_abspath = path.join(dir21_abspath, regfile121_name)
        self.mount_a.run_shell('mkdir -p ' + dir21_abspath)
        self.mount_a.run_shell('touch ' + regfile121_abspath)

        sudo_write_file(self.mount_a.client_remote, regfile_abspath,
            'somedata')
        sudo_write_file(self.mount_a.client_remote, regfile121_abspath,
            'somemoredata')

        # TODO: is there a way to trigger/force update ceph.dir.rbytes?
        # wait so that attr ceph.dir.rbytes gets a chance to be updated.
        sleep(20)

        expected_patterns = []
        path_to_files = []

        def append_expected_output_pattern(f):
            if f == '/':
                expected_patterns.append(r'{}{}{}'.format(size, " +", '.' + f))
            else:
                expected_patterns.append(r'{}{}{}'.format(size, " +",
                    path_prefix + path.relpath(f, self.mount_a.mountpoint)))

        for f in [dir_abspath, regfile_abspath, regfile121_abspath,
                  hlink_abspath, slink_abspath, slink2_abspath]:
            size = humansize(self.mount_a.stat(f, follow_symlinks=
                                               False)['st_size'])
            append_expected_output_pattern(f)

        # get size for directories containig regfiles within
        for f in [dir2_abspath, dir21_abspath]:
            size = humansize(self.mount_a.stat(regfile121_abspath,
                             follow_symlinks=False)['st_size'])
            append_expected_output_pattern(f)

        # get size for CephFS root
        size = 0
        for f in [regfile_abspath, regfile121_abspath, slink_abspath,
                  slink2_abspath]:
            size += self.mount_a.stat(f, follow_symlinks=False)['st_size']
        size = humansize(size)
        append_expected_output_pattern('/')

        if return_path_to_files:
            for p in [dir_abspath, regfile_abspath, dir2_abspath,
                      dir21_abspath, regfile121_abspath, hlink_abspath,
                      slink_abspath, slink2_abspath]:
                 path_to_files.append(path.relpath(p, self.mount_a.mountpoint))

            return (expected_patterns, path_to_files)
        else:
            return expected_patterns

    def test_du_works_recursively_with_no_path_in_args(self):
        expected_patterns_in_output = self._setup_files()
        du_output = self.get_cephfs_shell_cmd_output('du -r')

        for expected_output in expected_patterns_in_output:
            if sys_version_info.major >= 3:
                self.assertRegex(expected_output, du_output)
            elif sys_version_info.major < 3:
                assert re_search(expected_output, du_output) != None, "\n" + \
                       "expected_output -\n{}\ndu_output -\n{}\n".format(
                       expected_output, du_output)

    def test_du_with_path_in_args(self):
        expected_patterns_in_output, path_to_files = self._setup_files(True,
            path_prefix='')

        args = ['du', '/']
        for path in path_to_files:
            args.append(path)
        du_output = self.get_cephfs_shell_cmd_output(args)

        for expected_output in expected_patterns_in_output:
            if sys_version_info.major >= 3:
                self.assertRegex(expected_output, du_output)
            elif sys_version_info.major < 3:
                assert re_search(expected_output, du_output) != None, "\n" +\
                       "expected_output -\n{}\ndu_output -\n{}\n".format(
                       expected_output, du_output)

    def test_du_with_no_args(self):
        expected_patterns_in_output = self._setup_files()

        du_output = self.get_cephfs_shell_cmd_output('du')

        for expected_output in expected_patterns_in_output:
            # Since CWD is CephFS root and being non-recursive expect only
            # CWD in DU report.
            if expected_output.find('/') == len(expected_output) - 1:
                if sys_version_info.major >= 3:
                    self.assertRegex(expected_output, du_output)
                elif sys_version_info.major < 3:
                    assert re_search(expected_output, du_output) != None, "\n" + \
                        "expected_output -\n{}\ndu_output -\n{}\n".format(
                        expected_output, du_output)

#    def test_ls(self):
#        """
#        Test that ls passes
#        """
#        o = self.get_cephfs_shell_cmd_output("ls")
#        log.info("cephfs-shell output:\n{}".format(o))
#
#        o = self.mount_a.run_shell(['ls']).stdout.getvalue().strip().replace("\n", " ").split()
#        log.info("mount_a output:\n{}".format(o))
#
#        # ls should not list hidden files without the -a switch
#        if '.' in o or '..' in o:
#            log.info('ls failed')
#        else:
#            log.info('ls succeeded')
#
#    def test_ls_a(self):
#        """
#        Test that ls -a passes
#        """
#        o = self.get_cephfs_shell_cmd_output("ls -a")
#        log.info("cephfs-shell output:\n{}".format(o))
#
#        o = self.mount_a.run_shell(['ls', '-a']).stdout.getvalue().strip().replace("\n", " ").split()
#        log.info("mount_a output:\n{}".format(o))
#
#        if '.' in o and '..' in o:
#            log.info('ls -a succeeded')
#        else:
#            log.info('ls -a failed')

class TestMisc(TestCephFSShell):
    def test_issue_cephfs_shell_cmd_at_invocation(self):
        """
        Test that `cephfs-shell -c conf cmd` works.
        """
        # choosing a long name since short ones have a higher probability
        # of getting matched by coincidence.
        dirname = 'somedirectory'
        self.run_cephfs_shell_cmd(['mkdir', dirname])

        # TODO: Once cephfs-shell can pickup its config variables from
        # ceph.conf, set colors Never there and get rid of the same in
        # following comamnd.
        output = self.mount_a.client_remote.run(args=['cephfs-shell', '-c',
            self.mount_a.config_path, 'set colors Never, ls'],
            stdout=StringIO()).stdout.getvalue().strip()

        if sys_version_info.major >= 3:
            self.assertRegex(dirname, output)
        elif sys_version_info.major < 3:
            assert re_search(dirname, output) != None, "\n" + \
                   "expected_output -\n{}\ndu_output -\n{}\n".format(
                   dirname, output)

    def test_help(self):
        """
        Test that help outputs commands.
        """
        o = self.get_cephfs_shell_cmd_output("help all")
        log.info("output:\n{}".format(o))
