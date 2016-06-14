#!/usr/bin/python2

# Copyright 2012 Google Inc. All Rights Reserved.
"""Tests for bisecting tool."""

from __future__ import print_function

__author__ = 'shenhan@google.com (Han Shen)'

import os
import random
import sys
import unittest

from utils import command_executer
from binary_search_tool import binary_search_state

import common
import gen_obj


class BisectingUtilsTest(unittest.TestCase):
  """Tests for bisecting tool."""

  def setUp(self):
    """Generate [100-1000] object files, and 1-5% of which are bad ones."""
    obj_num = random.randint(100, 1000)
    bad_obj_num = random.randint(obj_num / 100, obj_num / 20)
    if bad_obj_num == 0:
      bad_obj_num = 1
    gen_obj.Main(['--obj_num', str(obj_num), '--bad_obj_num', str(bad_obj_num)])

    with open('./installed', 'w'):
      pass

    try:
      os.remove(binary_search_state.STATE_FILE)
    except OSError:
      pass

  def tearDown(self):
    """Cleanup temp files."""
    os.remove(common.OBJECTS_FILE)
    os.remove(common.WORKING_SET_FILE)
    print('Deleted "{0}" and "{1}"'.format(common.OBJECTS_FILE,
                                           common.WORKING_SET_FILE))
    try:
      os.remove('./installed')
      os.remove(os.readlink(binary_search_state.STATE_FILE))
      os.remove(binary_search_state.STATE_FILE)
    except OSError:
      pass

  def runTest(self):
    args = ['--get_initial_items', './gen_init_list.py', '--switch_to_good',
            './switch_to_good.py', '--switch_to_bad', './switch_to_bad.py',
            '--test_script', './is_good.py', '--prune', '--file_args']
    binary_search_state.Main(args)
    self.check_output()

  def test_install_script(self):
    args = ['--get_initial_items', './gen_init_list.py', '--switch_to_good',
            './switch_to_good.py', '--switch_to_bad', './switch_to_bad.py',
            '--test_script', './is_good.py', '--prune', '--file_args']

    os.remove('./installed')
    with self.assertRaises(AssertionError):
      binary_search_state.Main(args)

    args += ['--install_script', './install.py']
    binary_search_state.Main(args)
    self.check_output()

  def test_bad_install_script(self):
    args = ['--get_initial_items', './gen_init_list.py', '--switch_to_good',
            './switch_to_good.py', '--switch_to_bad', './switch_to_bad.py',
            '--test_script', './is_good.py', '--prune', '--file_args',
            '--install_script', './install_bad.py']
    with self.assertRaises(AssertionError):
      binary_search_state.Main(args)

  def test_bad_save_state(self):
    state_file = binary_search_state.STATE_FILE

    with open(state_file, 'w') as f:
      f.write('test123')

    bss = binary_search_state.MockBinarySearchState()
    with self.assertRaises(SystemExit):
      bss.SaveState()

    with open(state_file, 'r') as f:
      self.assertEquals(f.read(), 'test123')

    os.remove(state_file)

  def test_save_state(self):
    state_file = binary_search_state.STATE_FILE

    bss = binary_search_state.MockBinarySearchState()
    bss.SaveState()
    self.assertTrue(os.path.exists(state_file))
    first_state = os.readlink(state_file)

    bss.SaveState()
    self.assertTrue(os.path.exists(state_file))
    self.assertTrue(os.readlink(state_file) != first_state)
    self.assertFalse(os.path.exists(first_state))

  def check_output(self):
    _, out, _ = command_executer.GetCommandExecuter().RunCommandWOutput(
        'tail -n 10 logs/binary_search_tool_tester.py.out')
    ls = out.splitlines()
    for l in ls:
      t = l.find('Bad items are: ')
      if t > 0:
        bad_ones = l[(t + len('Bad items are: ')):].split()
        objects_file = common.ReadObjectsFile()
        for b in bad_ones:
          self.assertEqual(objects_file[int(b)], 1)


def Main(argv):
  num_tests = 2
  if len(argv) > 1:
    num_tests = int(argv[1])

  suite = unittest.TestSuite()
  for _ in range(0, num_tests):
    suite.addTest(BisectingUtilsTest())
  suite.addTest(BisectingUtilsTest('test_install_script'))
  suite.addTest(BisectingUtilsTest('test_bad_install_script'))
  suite.addTest(BisectingUtilsTest('test_bad_save_state'))
  suite.addTest(BisectingUtilsTest('test_save_state'))
  runner = unittest.TextTestRunner()
  runner.run(suite)


if __name__ == '__main__':
  Main(sys.argv)
