#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for updating LLVM hashes."""

from __future__ import print_function

from collections import namedtuple
from datetime import datetime
import os
import re
import subprocess
import unittest
import unittest.mock as mock

from failure_modes import FailureModes
from test_helpers import CreateTemporaryJsonFile
import llvm_patch_management
import update_chromeos_llvm_hash

# These are unittests; protected access is OK to a point.
# pylint: disable=protected-access


class UpdateLLVMHashTest(unittest.TestCase):
  """Test class for updating LLVM hashes of packages."""

  @mock.patch.object(update_chromeos_llvm_hash, 'ChrootRunCommand')
  def testSucceedsToGetChrootPathForPackage(self, mock_chroot_command):
    package_chroot_path = '/chroot/path/to/package.ebuild'

    # Emulate ChrootRunCommandWOutput behavior when a chroot path is found for
    # a valid package.
    mock_chroot_command.return_value = package_chroot_path

    chroot_path = '/test/chroot/path'
    package_list = ['new-test/package']

    self.assertEqual(
        update_chromeos_llvm_hash.GetChrootBuildPaths(
            chroot_path, package_list), [package_chroot_path])

    mock_chroot_command.assert_called_once()

  def testFailedToConvertChrootPathWithInvalidPrefixToSymlinkPath(self):
    chroot_path = '/path/to/chroot'
    chroot_file_path = '/src/package.ebuild'

    # Verify the exception is raised when a symlink does not have the prefix
    # '/mnt/host/source/'.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash._ConvertChrootPathsToSymLinkPaths(
          chroot_path, [chroot_file_path])

    self.assertEqual(
        str(err.exception), 'Invalid prefix for the chroot path: '
        '%s' % chroot_file_path)

  def testSucceedsToConvertChrootPathToSymlinkPath(self):
    chroot_path = '/path/to/chroot'
    chroot_file_paths = ['/mnt/host/source/src/package.ebuild']

    expected_symlink_path = '/path/to/chroot/src/package.ebuild'

    self.assertEqual(
        update_chromeos_llvm_hash._ConvertChrootPathsToSymLinkPaths(
            chroot_path, chroot_file_paths), [expected_symlink_path])

  # Simulate 'os.path.islink' when a path is not a symbolic link.
  @mock.patch.object(os.path, 'islink', return_value=False)
  def testFailedToGetEbuildPathFromInvalidSymlink(self, mock_islink):
    symlink_path = '/symlink/path/src/to/package-r1.ebuild'

    # Verify the exception is raised when the argument is not a symbolic link.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.GetEbuildPathsFromSymLinkPaths([symlink_path])

    self.assertEqual(
        str(err.exception), 'Invalid symlink provided: %s' % symlink_path)

    mock_islink.assert_called_once_with(symlink_path)

  # Simulate 'os.path.islink' when a path is a symbolic link.
  @mock.patch.object(os.path, 'islink', return_value=True)
  @mock.patch.object(os.path, 'realpath')
  def testSucceedsToGetEbuildPathFromValidSymlink(self, mock_realpath,
                                                  mock_islink):

    symlink_path = '/path/to/chroot/src/package-r1.ebuild'
    abs_path_to_package = '/abs/path/to/src/package.ebuild'
    mock_realpath.return_value = abs_path_to_package

    expected_resolved_paths = {symlink_path: abs_path_to_package}

    self.assertEqual(
        update_chromeos_llvm_hash.GetEbuildPathsFromSymLinkPaths(
            [symlink_path]), expected_resolved_paths)

    mock_realpath.assert_called_once_with(symlink_path)

    mock_islink.assert_called_once_with(symlink_path)

  # Simulate behavior of 'os.path.isfile()' when the ebuild path to a package
  # does not exist.
  @mock.patch.object(os.path, 'isfile', return_value=False)
  def testFailedToUpdateLLVMHashForInvalidEbuildPath(self, mock_isfile):
    ebuild_path = '/some/path/to/package.ebuild'
    llvm_variant = update_chromeos_llvm_hash.LLVMVariant.current
    git_hash = 'a123testhash1'
    svn_version = 1000

    # Verify the exception is raised when the ebuild path does not exist.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UpdateEbuildLLVMHash(ebuild_path, llvm_variant,
                                                     git_hash, svn_version)

    self.assertEqual(
        str(err.exception), 'Invalid ebuild path provided: %s' % ebuild_path)

    mock_isfile.assert_called_once()

  # Simulate 'os.path.isfile' behavior on a valid ebuild path.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  def testFailedToUpdateLLVMHash(self, mock_isfile):
    # Create a temporary file to simulate an ebuild file of a package.
    with CreateTemporaryJsonFile() as ebuild_file:
      with open(ebuild_file, 'w') as f:
        f.write('\n'.join([
            'First line in the ebuild', 'Second line in the ebuild',
            'Last line in the ebuild'
        ]))

      llvm_variant = update_chromeos_llvm_hash.LLVMVariant.current
      git_hash = 'a123testhash1'
      svn_version = 1000

      # Verify the exception is raised when the ebuild file does not have
      # 'LLVM_HASH'.
      with self.assertRaises(ValueError) as err:
        update_chromeos_llvm_hash.UpdateEbuildLLVMHash(
            ebuild_file, llvm_variant, git_hash, svn_version)

        self.assertEqual(
            str(err.exception), ('Failed to update %s.', 'LLVM_HASH'))

      llvm_variant = update_chromeos_llvm_hash.LLVMVariant.next

    self.assertEqual(mock_isfile.call_count, 2)

  # Simulate 'os.path.isfile' behavior on a valid ebuild path.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  def testFailedToUpdateLLVMNextHash(self, mock_isfile):
    # Create a temporary file to simulate an ebuild file of a package.
    with CreateTemporaryJsonFile() as ebuild_file:
      with open(ebuild_file, 'w') as f:
        f.write('\n'.join([
            'First line in the ebuild', 'Second line in the ebuild',
            'Last line in the ebuild'
        ]))

      llvm_variant = update_chromeos_llvm_hash.LLVMVariant.next
      git_hash = 'a123testhash1'
      svn_version = 1000

      # Verify the exception is raised when the ebuild file does not have
      # 'LLVM_NEXT_HASH'.
      with self.assertRaises(ValueError) as err:
        update_chromeos_llvm_hash.UpdateEbuildLLVMHash(
            ebuild_file, llvm_variant, git_hash, svn_version)

        self.assertEqual(
            str(err.exception), ('Failed to update %s.', 'LLVM_NEXT_HASH'))

    self.assertEqual(mock_isfile.call_count, 2)

  # Simulate 'os.path.isfile' behavior on a valid ebuild path.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  # Simulate 'ExecCommandAndCaptureOutput()' when successfully staged the
  # ebuild file for commit.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyStageTheEbuildForCommitForLLVMHashUpdate(
      self, mock_stage_commit_command, mock_isfile):

    # Create a temporary file to simulate an ebuild file of a package.
    with CreateTemporaryJsonFile() as ebuild_file:
      # Updates LLVM_HASH to 'git_hash' and revision to
      # 'svn_version'.
      llvm_variant = update_chromeos_llvm_hash.LLVMVariant.current
      git_hash = 'a123testhash1'
      svn_version = 1000

      with open(ebuild_file, 'w') as f:
        f.write('\n'.join([
            'First line in the ebuild', 'Second line in the ebuild',
            'LLVM_HASH=\"a12b34c56d78e90\" # r500', 'Last line in the ebuild'
        ]))

      update_chromeos_llvm_hash.UpdateEbuildLLVMHash(ebuild_file, llvm_variant,
                                                     git_hash, svn_version)

      expected_file_contents = [
          'First line in the ebuild\n', 'Second line in the ebuild\n',
          'LLVM_HASH=\"a123testhash1\" # r1000\n', 'Last line in the ebuild'
      ]

      # Verify the new file contents of the ebuild file match the expected file
      # contents.
      with open(ebuild_file) as new_file:
        file_contents_as_a_list = [cur_line for cur_line in new_file]
        self.assertListEqual(file_contents_as_a_list, expected_file_contents)

    self.assertEqual(mock_isfile.call_count, 2)

    mock_stage_commit_command.assert_called_once()

  # Simulate 'os.path.isfile' behavior on a valid ebuild path.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  # Simulate 'ExecCommandAndCaptureOutput()' when successfully staged the
  # ebuild file for commit.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyStageTheEbuildForCommitForLLVMNextHashUpdate(
      self, mock_stage_commit_command, mock_isfile):

    # Create a temporary file to simulate an ebuild file of a package.
    with CreateTemporaryJsonFile() as ebuild_file:
      # Updates LLVM_NEXT_HASH to 'git_hash' and revision to
      # 'svn_version'.
      llvm_variant = update_chromeos_llvm_hash.LLVMVariant.next
      git_hash = 'a123testhash1'
      svn_version = 1000

      with open(ebuild_file, 'w') as f:
        f.write('\n'.join([
            'First line in the ebuild', 'Second line in the ebuild',
            'LLVM_NEXT_HASH=\"a12b34c56d78e90\" # r500',
            'Last line in the ebuild'
        ]))

      update_chromeos_llvm_hash.UpdateEbuildLLVMHash(ebuild_file, llvm_variant,
                                                     git_hash, svn_version)

      expected_file_contents = [
          'First line in the ebuild\n', 'Second line in the ebuild\n',
          'LLVM_NEXT_HASH=\"a123testhash1\" # r1000\n',
          'Last line in the ebuild'
      ]

      # Verify the new file contents of the ebuild file match the expected file
      # contents.
      with open(ebuild_file) as new_file:
        file_contents_as_a_list = [cur_line for cur_line in new_file]
        self.assertListEqual(file_contents_as_a_list, expected_file_contents)

    self.assertEqual(mock_isfile.call_count, 2)

    mock_stage_commit_command.assert_called_once()

  @mock.patch.object(os.path, 'islink', return_value=False)
  def testFailedToUprevEbuildToVersionForInvalidSymlink(self, mock_islink):
    symlink_path = '/path/to/chroot/package/package.ebuild'
    svn_version = 1000

    # Verify the exception is raised when a invalid symbolic link is passed in.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UprevEbuildToVersion(symlink_path, svn_version)

    self.assertEqual(
        str(err.exception), 'Invalid symlink provided: %s' % symlink_path)

    mock_islink.assert_called_once()

  @mock.patch.object(os.path, 'islink', return_value=False)
  def testFailedToUprevEbuildSymlinkForInvalidSymlink(self, mock_islink):
    symlink_path = '/path/to/chroot/package/package.ebuild'

    # Verify the exception is raised when a invalid symbolic link is passed in.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UprevEbuildSymlink(symlink_path)

    self.assertEqual(
        str(err.exception), 'Invalid symlink provided: %s' % symlink_path)

    mock_islink.assert_called_once()

  # Simulate 'os.path.islink' when a symbolic link is passed in.
  @mock.patch.object(os.path, 'islink', return_value=True)
  # Simulate 'os.path.realpath' when a symbolic link is passed in.
  @mock.patch.object(os.path, 'realpath', return_value=True)
  def testFailedToUprevEbuildToVersion(self, mock_realpath, mock_islink):
    symlink_path = '/path/to/chroot/llvm/llvm_pre123_p.ebuild'
    mock_realpath.return_value = '/abs/path/to/llvm/llvm_pre123_p.ebuild'
    svn_version = 1000

    # Verify the exception is raised when the symlink does not match the
    # expected pattern
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UprevEbuildToVersion(symlink_path, svn_version)

    self.assertEqual(str(err.exception), 'Failed to uprev the ebuild.')

    mock_islink.assert_called_once_with(symlink_path)

  # Simulate 'os.path.islink' when a symbolic link is passed in.
  @mock.patch.object(os.path, 'islink', return_value=True)
  def testFailedToUprevEbuildSymlink(self, mock_islink):
    symlink_path = '/path/to/chroot/llvm/llvm_pre123_p.ebuild'

    # Verify the exception is raised when the symlink does not match the
    # expected pattern
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UprevEbuildSymlink(symlink_path)

    self.assertEqual(str(err.exception), 'Failed to uprev the symlink.')

    mock_islink.assert_called_once_with(symlink_path)

  # Simulate 'os.path.islink' when a valid symbolic link is passed in.
  @mock.patch.object(os.path, 'islink', return_value=True)
  @mock.patch.object(os.path, 'realpath')
  # Simulate 'RunCommandWOutput' when successfully added the upreved symlink
  # for commit.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyUprevEbuildToVersion(self, mock_command_output,
                                           mock_realpath, mock_islink):
    symlink = '/symlink/to/llvm/llvm_pre3_p2-r10.ebuild'
    ebuild = '/abs/path/to/llvm_pre3_p2.ebuild'
    mock_realpath.return_value = ebuild
    svn_version = 1000

    update_chromeos_llvm_hash.UprevEbuildToVersion(symlink, svn_version)

    mock_islink.assert_called()

    mock_realpath.assert_called_once_with(symlink)

    mock_command_output.assert_called()

    # Verify commands
    symlink_dir = os.path.dirname(symlink)
    new_ebuild, _is_changed = re.subn(
        r'pre([0-9]+)_p([0-9]+)',
        'pre%s_p%s' % (svn_version, \
            datetime.today().strftime('%Y%m%d')),
        ebuild,
        count=1)
    new_symlink = new_ebuild[:-len('.ebuild')] + '-r1.ebuild'

    expected_cmd = ['git', '-C', symlink_dir, 'mv', ebuild, new_ebuild]
    self.assertEqual(mock_command_output.call_args_list[0],
                     mock.call(expected_cmd, verbose=False))

    expected_cmd = ['ln', '-s', '-r', new_ebuild, new_symlink]
    self.assertEqual(mock_command_output.call_args_list[1],
                     mock.call(expected_cmd, verbose=False))

    expected_cmd = ['git', '-C', symlink_dir, 'add', new_symlink]
    self.assertEqual(mock_command_output.call_args_list[2],
                     mock.call(expected_cmd, verbose=False))

    expected_cmd = ['git', '-C', symlink_dir, 'rm', symlink]
    self.assertEqual(mock_command_output.call_args_list[3],
                     mock.call(expected_cmd, verbose=False))

  # Simulate 'os.path.islink' when a valid symbolic link is passed in.
  @mock.patch.object(os.path, 'islink', return_value=True)
  # Simulate 'RunCommandWOutput' when successfully added the upreved symlink
  # for commit.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyUprevEbuildSymlink(self, mock_command_output,
                                         mock_islink):
    symlink_to_uprev = '/symlink/to/package-r1.ebuild'

    update_chromeos_llvm_hash.UprevEbuildSymlink(symlink_to_uprev)

    mock_islink.assert_called_once_with(symlink_to_uprev)

    mock_command_output.assert_called_once()

  # Simulate behavior of 'os.path.isdir()' when the path to the repo is not a

  # directory.

  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testFailedToCreateRepoForInvalidDirectoryPath(self, mock_isdir):
    path_to_repo = '/path/to/repo'
    branch = 'update-LLVM_NEXT_HASH-a123testhash1'

    # Verify the exception is raised when provided an invalid directory path.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash._CreateRepo(path_to_repo, branch)

    self.assertEqual(
        str(err.exception),
        'Invalid directory path provided: %s' % path_to_repo)

    mock_isdir.assert_called_once()

  # Simulate 'os.path.isdir' when a valid repo path is provided.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  # Simulate behavior of 'ExecCommandAndCaptureOutput()' when successfully reset
  # changes and created a repo.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyCreatedRepo(self, mock_command_output, mock_isdir):
    path_to_repo = '/path/to/repo'
    branch = 'update-LLVM_NEXT_HASH-a123testhash1'

    update_chromeos_llvm_hash._CreateRepo(path_to_repo, branch)

    mock_isdir.assert_called_once_with(path_to_repo)

    self.assertEqual(mock_command_output.call_count, 2)

  # Simulate behavior of 'os.path.isdir()' when the path to the repo is not a
  # directory.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testFailedToDeleteRepoForInvalidDirectoryPath(self, mock_isdir):
    path_to_repo = '/some/path/to/repo'
    branch = 'update-LLVM_NEXT_HASH-a123testhash2'

    # Verify the exception is raised on an invalid repo path.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash._DeleteRepo(path_to_repo, branch)

    self.assertEqual(
        str(err.exception),
        'Invalid directory path provided: %s' % path_to_repo)

    mock_isdir.assert_called_once()

  # Simulate 'os.path.isdir' on valid directory path.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  # Simulate 'ExecCommandAndCaptureOutput()' when successfully checkout to
  # cros/master, reset changes, and deleted the repo.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyDeletedRepo(self, mock_command_output, mock_isdir):
    path_to_repo = '/some/path/to/repo'
    branch = 'update-LLVM_NEXT_HASH-a123testhash2'

    update_chromeos_llvm_hash._DeleteRepo(path_to_repo, branch)

    mock_isdir.assert_called_once_with(path_to_repo)

    self.assertEqual(mock_command_output.call_count, 3)

  def testFailedToFindChangeListURL(self):
    repo_upload_contents = 'remote:   https://some_url'

    # Verify the exception is raised when failed to find the Gerrit URL when
    # parsing the 'repo upload' contents.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.GetGerritRepoUploadContents(
          repo_upload_contents)

    self.assertEqual(str(err.exception), 'Failed to find change list URL.')

  def testSuccessfullyGetGerritRepoUploadContents(self):
    repo_upload_contents = ('remote:   https://chromium-review.googlesource.com'
                            '/c/chromiumos/overlays/chromiumos-overlay/+/'
                            '193147 Some commit header')

    change_list = update_chromeos_llvm_hash.GetGerritRepoUploadContents(
        repo_upload_contents)

    self.assertEqual(
        change_list.url,
        'https://chromium-review.googlesource.com/c/chromiumos/overlays/'
        'chromiumos-overlay/+/193147')

    self.assertEqual(change_list.cl_number, 193147)

  # Simulate behavior of 'os.path.isdir()' when the path to the repo is not a
  # directory.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testFailedToUploadChangesForInvalidPathDirectory(self, mock_isdir):
    path_to_repo = '/some/path/to/repo'
    branch = 'update-LLVM_NEXT_HASH-a123testhash3'
    commit_messages = ['Test message']

    # Verify exception is raised when on an invalid repo path.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UploadChanges(path_to_repo, branch,
                                              commit_messages)

    self.assertEqual(
        str(err.exception),
        'Invalid directory path provided: %s' % path_to_repo)

    mock_isdir.assert_called_once()

  # Simulate 'os.path.isdir' on a valid repo path.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  # Simulate behavior of 'ExecCommandAndCaptureOutput()' when successfully
  # committed the changes.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  @mock.patch.object(subprocess, 'Popen')
  def testFailedToUploadChangesForReview(self, mock_repo_upload,
                                         mock_command_output, mock_isdir):

    # Simulate the behavior of 'subprocess.Popen()' when uploading the changes
    # for review
    #
    # `Popen.communicate()` returns a tuple of `stdout` and `stderr`.
    mock_repo_upload.return_value.communicate.return_value = (
        None, 'Branch does not exist.')

    # Exit code of 1 means failed to upload changes for review.
    mock_repo_upload.return_value.returncode = 1

    path_to_repo = '/some/path/to/repo'
    branch = 'update-LLVM_NEXT_HASH-a123testhash3'
    commit_messages = ['Test message']

    # Verify exception is raised when failed to upload the changes for review.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UploadChanges(path_to_repo, branch,
                                              commit_messages)

    self.assertEqual(str(err.exception), 'Failed to upload changes for review')

    mock_isdir.assert_called_once_with(path_to_repo)

    mock_command_output.assert_called_once()
    mock_command_output_args = mock_command_output.call_args_list[0][0][0]
    expected_mock_command_output_prefix = ['git', 'commit', '-F']
    self.assertEqual(
        mock_command_output_args[:len(expected_mock_command_output_prefix)],
        expected_mock_command_output_prefix)

    mock_repo_upload.assert_called_once()

  # Simulate 'os.path.isdir' when a valid repo path is passed in.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  # Simulate behavior of 'ExecCommandAndCaptureOutput()' when successfully
  # committed the changes.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  @mock.patch.object(subprocess, 'Popen')
  def testSuccessfullyUploadedChangesForReview(self, mock_repo_upload,
                                               mock_command_output, mock_isdir):

    # A test CL generated by `repo upload`.
    repo_upload_contents = ('remote: https://chromium-review.googlesource.'
                            'com/c/chromiumos/overlays/chromiumos-overlay/'
                            '+/193147 Fix stdout')

    # Simulate the behavior of 'subprocess.Popen()' when uploading the changes
    # for review
    #
    # `Popen.communicate()` returns a tuple of `stdout` and `stderr`.
    mock_repo_upload.return_value.communicate.return_value = (
        repo_upload_contents, None)

    # Exit code of 0 means successfully uploaded changes for review.
    mock_repo_upload.return_value.returncode = 0

    path_to_repo = '/some/path/to/repo'
    branch = 'update-LLVM_NEXT_HASH-a123testhash3'
    commit_messages = ['Test message']

    change_list = update_chromeos_llvm_hash.UploadChanges(
        path_to_repo, branch, commit_messages)

    self.assertEqual(
        change_list.url,
        'https://chromium-review.googlesource.com/c/chromiumos/overlays/'
        'chromiumos-overlay/+/193147')

    self.assertEqual(change_list.cl_number, 193147)

    mock_isdir.assert_called_once_with(path_to_repo)

    mock_command_output.assert_called_once()

    mock_repo_upload.assert_called_once()

  @mock.patch.object(update_chromeos_llvm_hash, 'GetChrootBuildPaths')
  @mock.patch.object(update_chromeos_llvm_hash,
                     '_ConvertChrootPathsToSymLinkPaths')
  def testExceptionRaisedWhenCreatingPathDictionaryFromPackages(
      self, mock_chroot_paths_to_symlinks, mock_get_chroot_paths):

    chroot_path = '/some/path/to/chroot'

    package_name = 'test-pckg/package'
    package_chroot_path = '/some/chroot/path/to/package-r1.ebuild'

    # Test function to simulate '_ConvertChrootPathsToSymLinkPaths' when a
    # symlink does not start with the prefix '/mnt/host/source'.
    def BadPrefixChrootPath(_chroot_path, _chroot_file_paths):
      raise ValueError('Invalid prefix for the chroot path: '
                       '%s' % package_chroot_path)

    # Simulate 'GetChrootBuildPaths' when valid packages are passed in.
    #
    # Returns a list of chroot paths.
    mock_get_chroot_paths.return_value = [package_chroot_path]

    # Use test function to simulate '_ConvertChrootPathsToSymLinkPaths'
    # behavior.
    mock_chroot_paths_to_symlinks.side_effect = BadPrefixChrootPath

    # Verify exception is raised when for an invalid prefix in the symlink.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.CreatePathDictionaryFromPackages(
          chroot_path, [package_name])

    self.assertEqual(
        str(err.exception), 'Invalid prefix for the chroot path: '
        '%s' % package_chroot_path)

    mock_get_chroot_paths.assert_called_once_with(chroot_path, [package_name])

    mock_chroot_paths_to_symlinks.assert_called_once_with(
        chroot_path, [package_chroot_path])

  @mock.patch.object(update_chromeos_llvm_hash, 'GetChrootBuildPaths')
  @mock.patch.object(update_chromeos_llvm_hash,
                     '_ConvertChrootPathsToSymLinkPaths')
  @mock.patch.object(update_chromeos_llvm_hash,
                     'GetEbuildPathsFromSymLinkPaths')
  def testSuccessfullyCreatedPathDictionaryFromPackages(
      self, mock_ebuild_paths_from_symlink_paths, mock_chroot_paths_to_symlinks,
      mock_get_chroot_paths):

    package_chroot_path = '/mnt/host/source/src/path/to/package-r1.ebuild'

    # Simulate 'GetChrootBuildPaths' when returning a chroot path for a valid
    # package.
    #
    # Returns a list of chroot paths.
    mock_get_chroot_paths.return_value = [package_chroot_path]

    package_symlink_path = '/some/path/to/chroot/src/path/to/package-r1.ebuild'

    # Simulate '_ConvertChrootPathsToSymLinkPaths' when returning a symlink to
    # a chroot path that points to a package.
    #
    # Returns a list of symlink file paths.
    mock_chroot_paths_to_symlinks.return_value = [package_symlink_path]

    chroot_package_path = '/some/path/to/chroot/src/path/to/package.ebuild'

    # Simulate 'GetEbuildPathsFromSymlinkPaths' when returning a dictionary of
    # a symlink that points to an ebuild.
    #
    # Returns a dictionary of a symlink and ebuild file path pair
    # where the key is the absolute path to the symlink of the ebuild file
    # and the value is the absolute path to the ebuild file of the package.
    mock_ebuild_paths_from_symlink_paths.return_value = {
        package_symlink_path: chroot_package_path
    }

    chroot_path = '/some/path/to/chroot'
    package_name = 'test-pckg/package'

    self.assertEqual(
        update_chromeos_llvm_hash.CreatePathDictionaryFromPackages(
            chroot_path, [package_name]),
        {package_symlink_path: chroot_package_path})

    mock_get_chroot_paths.assert_called_once_with(chroot_path, [package_name])

    mock_chroot_paths_to_symlinks.assert_called_once_with(
        chroot_path, [package_chroot_path])

    mock_ebuild_paths_from_symlink_paths.assert_called_once_with(
        [package_symlink_path])

  # Simulate behavior of 'ExecCommandAndCaptureOutput()' when successfully
  # removed patches.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyRemovedPatchesFromFilesDir(self, mock_run_cmd):
    patches_to_remove_list = [
        '/abs/path/to/filesdir/cherry/fix_output.patch',
        '/abs/path/to/filesdir/display_results.patch'
    ]

    update_chromeos_llvm_hash.RemovePatchesFromFilesDir(patches_to_remove_list)

    self.assertEqual(mock_run_cmd.call_count, 2)

  # Simulate behavior of 'os.path.isfile()' when the absolute path to the patch
  # metadata file does not exist.
  @mock.patch.object(os.path, 'isfile', return_value=False)
  def testInvalidPatchMetadataFileStagedForCommit(self, mock_isfile):
    patch_metadata_path = '/abs/path/to/filesdir/PATCHES'

    # Verify the exception is raised when the absolute path to the patch
    # metadata file does not exist or is not a file.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.StagePatchMetadataFileForCommit(
          patch_metadata_path)

    self.assertEqual(
        str(err.exception), 'Invalid patch metadata file provided: '
        '%s' % patch_metadata_path)

    mock_isfile.assert_called_once()

  # Simulate the behavior of 'os.path.isfile()' when the absolute path to the
  # patch metadata file exists.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  # Simulate the behavior of 'ExecCommandAndCaptureOutput()' when successfully
  # staged the patch metadata file for commit.
  @mock.patch.object(
      update_chromeos_llvm_hash,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyStagedPatchMetadataFileForCommit(self, mock_run_cmd,
                                                       _mock_isfile):

    patch_metadata_path = '/abs/path/to/filesdir/PATCHES.json'

    update_chromeos_llvm_hash.StagePatchMetadataFileForCommit(
        patch_metadata_path)

    mock_run_cmd.assert_called_once()

  def testNoPatchResultsForCommit(self):
    package_1_patch_info_dict = {
        'applied_patches': ['display_results.patch'],
        'failed_patches': ['fixes_output.patch'],
        'non_applicable_patches': [],
        'disabled_patches': [],
        'removed_patches': [],
        'modified_metadata': None
    }

    package_2_patch_info_dict = {
        'applied_patches': ['redirects_stdout.patch', 'fix_display.patch'],
        'failed_patches': [],
        'non_applicable_patches': [],
        'disabled_patches': [],
        'removed_patches': [],
        'modified_metadata': None
    }

    test_package_info_dict = {
        'test-packages/package1': package_1_patch_info_dict,
        'test-packages/package2': package_2_patch_info_dict
    }

    test_commit_message = ['Updated packages']

    self.assertListEqual(
        update_chromeos_llvm_hash.StagePackagesPatchResultsForCommit(
            test_package_info_dict, test_commit_message), test_commit_message)

  @mock.patch.object(update_chromeos_llvm_hash,
                     'StagePatchMetadataFileForCommit')
  @mock.patch.object(update_chromeos_llvm_hash, 'RemovePatchesFromFilesDir')
  def testAddedPatchResultsForCommit(self, mock_remove_patches,
                                     mock_stage_patches_for_commit):

    package_1_patch_info_dict = {
        'applied_patches': [],
        'failed_patches': [],
        'non_applicable_patches': [],
        'disabled_patches': ['fixes_output.patch'],
        'removed_patches': [],
        'modified_metadata': '/abs/path/to/filesdir/PATCHES.json'
    }

    package_2_patch_info_dict = {
        'applied_patches': ['fix_display.patch'],
        'failed_patches': [],
        'non_applicable_patches': [],
        'disabled_patches': [],
        'removed_patches': ['/abs/path/to/filesdir/redirect_stdout.patch'],
        'modified_metadata': '/abs/path/to/filesdir/PATCHES.json'
    }

    test_package_info_dict = {
        'test-packages/package1': package_1_patch_info_dict,
        'test-packages/package2': package_2_patch_info_dict
    }

    test_commit_message = ['Updated packages']

    expected_commit_messages = [
        'Updated packages', '\nFor the package test-packages/package1:',
        'The patch metadata file PATCHES.json was modified',
        'The following patches were disabled:', 'fixes_output.patch',
        '\nFor the package test-packages/package2:',
        'The patch metadata file PATCHES.json was modified',
        'The following patches were removed:', 'redirect_stdout.patch'
    ]

    self.assertListEqual(
        update_chromeos_llvm_hash.StagePackagesPatchResultsForCommit(
            test_package_info_dict, test_commit_message),
        expected_commit_messages)

    path_to_removed_patch = '/abs/path/to/filesdir/redirect_stdout.patch'

    mock_remove_patches.assert_called_once_with([path_to_removed_patch])

    self.assertEqual(mock_stage_patches_for_commit.call_count, 2)

  @mock.patch.object(update_chromeos_llvm_hash,
                     'CreatePathDictionaryFromPackages')
  @mock.patch.object(update_chromeos_llvm_hash, '_CreateRepo')
  @mock.patch.object(update_chromeos_llvm_hash, 'UpdateEbuildLLVMHash')
  @mock.patch.object(update_chromeos_llvm_hash, 'UprevEbuildSymlink')
  @mock.patch.object(update_chromeos_llvm_hash, 'UploadChanges')
  @mock.patch.object(update_chromeos_llvm_hash, '_DeleteRepo')
  @mock.patch.object(os.path, 'realpath')
  def testExceptionRaisedWhenUpdatingPackages(
      self, mock_realpath, mock_delete_repo, mock_upload_changes,
      mock_uprev_symlink, mock_update_llvm_next, mock_create_repo,
      mock_create_path_dict):

    abs_path_to_package = '/some/path/to/chroot/src/path/to/package.ebuild'

    symlink_path_to_package = \
        '/some/path/to/chroot/src/path/to/package-r1.ebuild'

    path_to_package_dir = '/some/path/to/chroot/src/path/to'

    # Test function to simulate '_CreateRepo' when successfully created the
    # repo on a valid repo path.
    def SuccessfullyCreateRepoForChanges(_repo_path, branch):
      self.assertEqual(branch, 'update-LLVM_NEXT_HASH-a123testhash4')
      return

    # Test function to simulate 'UpdateEbuildLLVMHash' when successfully
    # updated the ebuild's 'LLVM_NEXT_HASH'.
    def SuccessfullyUpdatedLLVMHash(ebuild_path, _, git_hash, svn_version):
      self.assertEqual(ebuild_path, abs_path_to_package)
      self.assertEqual(git_hash, 'a123testhash4')
      self.assertEqual(svn_version, 1000)
      return

    # Test function to simulate 'UprevEbuildSymlink' when the symlink to the
    # ebuild does not have a revision number.
    def FailedToUprevEbuildSymlink(_symlink_path):
      # Raises a 'ValueError' exception because the symlink did not have have a
      # revision number.
      raise ValueError('Failed to uprev the ebuild.')

    # Test function to fail on 'UploadChanges' if the function gets called
    # when an exception is raised.
    def ShouldNotExecuteUploadChanges(_repo_path, _git_hash, _commit_messages):
      # Test function should not be called (i.e. execution should resume in the
      # 'finally' block) because 'UprevEbuildSymlink' raised an
      # exception.
      assert False, 'Failed to go to "finally" block ' \
          'after the exception was raised.'

    test_package_path_dict = {symlink_path_to_package: abs_path_to_package}

    # Simulate behavior of 'CreatePathDictionaryFromPackages()' when
    # successfully created a dictionary where the key is the absolute path to
    # the symlink of the package and value is the absolute path to the ebuild of
    # the package.
    mock_create_path_dict.return_value = test_package_path_dict

    # Use test function to simulate behavior.
    mock_create_repo.side_effect = SuccessfullyCreateRepoForChanges
    mock_update_llvm_next.side_effect = SuccessfullyUpdatedLLVMHash
    mock_uprev_symlink.side_effect = FailedToUprevEbuildSymlink
    mock_upload_changes.side_effect = ShouldNotExecuteUploadChanges
    mock_realpath.return_value = '/abs/path/to/test-packages/package1.ebuild'

    packages_to_update = ['test-packages/package1']
    llvm_variant = update_chromeos_llvm_hash.LLVMVariant.next
    git_hash = 'a123testhash4'
    svn_version = 1000
    chroot_path = '/some/path/to/chroot'
    patch_metadata_file = 'PATCHES.json'
    git_hash_source = 'google3'
    branch = 'update-LLVM_NEXT_HASH-a123testhash4'
    extra_commit_msg = None

    # Verify exception is raised when an exception is thrown within
    # the 'try' block by UprevEbuildSymlink function.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_hash.UpdatePackages(
          packages_to_update, llvm_variant, git_hash, svn_version, chroot_path,
          patch_metadata_file, FailureModes.FAIL, git_hash_source,
          extra_commit_msg)

    self.assertEqual(str(err.exception), 'Failed to uprev the ebuild.')

    mock_create_path_dict.assert_called_once_with(chroot_path,
                                                  packages_to_update)

    mock_create_repo.assert_called_once_with(path_to_package_dir, branch)

    mock_update_llvm_next.assert_called_once_with(
        abs_path_to_package, llvm_variant, git_hash, svn_version)

    mock_uprev_symlink.assert_called_once_with(symlink_path_to_package)

    mock_upload_changes.assert_not_called()

    mock_delete_repo.assert_called_once_with(path_to_package_dir, branch)

  @mock.patch.object(update_chromeos_llvm_hash,
                     'CreatePathDictionaryFromPackages')
  @mock.patch.object(update_chromeos_llvm_hash, '_CreateRepo')
  @mock.patch.object(update_chromeos_llvm_hash, 'UpdateEbuildLLVMHash')
  @mock.patch.object(update_chromeos_llvm_hash, 'UprevEbuildSymlink')
  @mock.patch.object(update_chromeos_llvm_hash, 'UploadChanges')
  @mock.patch.object(update_chromeos_llvm_hash, '_DeleteRepo')
  @mock.patch.object(llvm_patch_management, 'UpdatePackagesPatchMetadataFile')
  @mock.patch.object(update_chromeos_llvm_hash,
                     'StagePatchMetadataFileForCommit')
  def testSuccessfullyUpdatedPackages(
      self, mock_stage_patch_file, mock_update_package_metadata_file,
      mock_delete_repo, mock_upload_changes, mock_uprev_symlink,
      mock_update_llvm_next, mock_create_repo, mock_create_path_dict):

    abs_path_to_package = '/some/path/to/chroot/src/path/to/package.ebuild'

    symlink_path_to_package = \
        '/some/path/to/chroot/src/path/to/package-r1.ebuild'

    path_to_package_dir = '/some/path/to/chroot/src/path/to'

    # Test function to simulate '_CreateRepo' when successfully created the repo
    # for the changes to be made to the ebuild files.
    def SuccessfullyCreateRepoForChanges(_repo_path, branch):
      self.assertEqual(branch, 'update-LLVM_NEXT_HASH-a123testhash5')
      return

    # Test function to simulate 'UploadChanges' after a successfull update of
    # 'LLVM_NEXT_HASH" of the ebuild file.
    def SuccessfullyUpdatedLLVMHash(ebuild_path, _, git_hash, svn_version):
      self.assertEqual(ebuild_path,
                       '/some/path/to/chroot/src/path/to/package.ebuild')
      self.assertEqual(git_hash, 'a123testhash5')
      self.assertEqual(svn_version, 1000)
      return

    # Test function to simulate 'UprevEbuildSymlink' when successfully
    # incremented the revision number by 1.
    def SuccessfullyUprevedEbuildSymlink(symlink_path):
      self.assertEqual(symlink_path,
                       '/some/path/to/chroot/src/path/to/package-r1.ebuild')

      return

    # Test function to simulate 'UpdatePackagesPatchMetadataFile()' when the
    # patch results contains a disabled patch in 'disable_patches' mode.
    def RetrievedPatchResults(chroot_path, svn_version, patch_metadata_file,
                              packages, mode):

      self.assertEqual(chroot_path, '/some/path/to/chroot')
      self.assertEqual(svn_version, 1000)
      self.assertEqual(patch_metadata_file, 'PATCHES.json')
      self.assertListEqual(packages, ['path/to'])
      self.assertEqual(mode, FailureModes.DISABLE_PATCHES)

      PatchInfo = namedtuple('PatchInfo', [
          'applied_patches', 'failed_patches', 'non_applicable_patches',
          'disabled_patches', 'removed_patches', 'modified_metadata'
      ])

      package_patch_info = PatchInfo(
          applied_patches=['fix_display.patch'],
          failed_patches=['fix_stdout.patch'],
          non_applicable_patches=[],
          disabled_patches=['fix_stdout.patch'],
          removed_patches=[],
          modified_metadata='/abs/path/to/filesdir/%s' % patch_metadata_file)

      package_info_dict = {'path/to': package_patch_info._asdict()}

      # Returns a dictionary where the key is the package and the value is a
      # dictionary that contains information about the package's patch results
      # produced by the patch manager.
      return package_info_dict

    # Test function to simulate 'UploadChanges()' when successfully created a
    # commit for the changes made to the packages and their patches and
    # retrieved the change list of the commit.
    def SuccessfullyUploadedChanges(_repo_path, _branch, _commit_messages):
      commit_url = 'https://some_name/path/to/commit/+/12345'

      return update_chromeos_llvm_hash.CommitContents(
          url=commit_url, cl_number=12345)

    test_package_path_dict = {symlink_path_to_package: abs_path_to_package}

    # Simulate behavior of 'CreatePathDictionaryFromPackages()' when
    # successfully created a dictionary where the key is the absolute path to
    # the symlink of the package and value is the absolute path to the ebuild of
    # the package.
    mock_create_path_dict.return_value = test_package_path_dict

    # Use test function to simulate behavior.
    mock_create_repo.side_effect = SuccessfullyCreateRepoForChanges
    mock_update_llvm_next.side_effect = SuccessfullyUpdatedLLVMHash
    mock_uprev_symlink.side_effect = SuccessfullyUprevedEbuildSymlink
    mock_update_package_metadata_file.side_effect = RetrievedPatchResults
    mock_upload_changes.side_effect = SuccessfullyUploadedChanges

    packages_to_update = ['test-packages/package1']
    llvm_variant = update_chromeos_llvm_hash.LLVMVariant.next
    git_hash = 'a123testhash5'
    svn_version = 1000
    chroot_path = '/some/path/to/chroot'
    patch_metadata_file = 'PATCHES.json'
    git_hash_source = 'tot'
    branch = 'update-LLVM_NEXT_HASH-a123testhash5'
    extra_commit_msg = '\ncommit-message-end'

    change_list = update_chromeos_llvm_hash.UpdatePackages(
        packages_to_update, llvm_variant, git_hash, svn_version, chroot_path,
        patch_metadata_file, FailureModes.DISABLE_PATCHES, git_hash_source,
        extra_commit_msg)

    self.assertEqual(change_list.url,
                     'https://some_name/path/to/commit/+/12345')

    self.assertEqual(change_list.cl_number, 12345)

    mock_create_path_dict.assert_called_once_with(chroot_path,
                                                  packages_to_update)

    mock_create_repo.assert_called_once_with(path_to_package_dir, branch)

    mock_update_llvm_next.assert_called_once_with(
        abs_path_to_package, llvm_variant, git_hash, svn_version)

    mock_uprev_symlink.assert_called_once_with(symlink_path_to_package)

    expected_commit_messages = [
        'llvm-next/tot: upgrade to a123testhash5 (r1000)\n',
        'The following packages have been updated:', 'path/to',
        '\nFor the package path/to:',
        'The patch metadata file PATCHES.json was modified',
        'The following patches were disabled:', 'fix_stdout.patch',
        '\ncommit-message-end'
    ]

    mock_update_package_metadata_file.assert_called_once()

    mock_stage_patch_file.assert_called_once_with(
        '/abs/path/to/filesdir/PATCHES.json')

    mock_upload_changes.assert_called_once_with(path_to_package_dir, branch,
                                                expected_commit_messages)

    mock_delete_repo.assert_called_once_with(path_to_package_dir, branch)


if __name__ == '__main__':
  unittest.main()
