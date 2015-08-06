#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The label of benchamrks."""

import os

from image_checksummer import ImageChecksummer
from utils.file_utils import FileUtils
from utils import misc


class Label(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args, cache_dir, cache_only, log_level, chrome_src=None):

    self.image_type = self._GetImageType(chromeos_image)

    # Expand ~
    chromeos_root = os.path.expanduser(chromeos_root)
    if self.image_type == "local":
      chromeos_image = os.path.expanduser(chromeos_image)

    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    self.image_args = image_args
    self.cache_dir = cache_dir
    self.cache_only = cache_only
    self.log_level = log_level

    if not chromeos_root:
      if self.image_type == "local":
        chromeos_root = FileUtils().ChromeOSRootFromImage(chromeos_image)
      if not chromeos_root:
        raise Exception("No ChromeOS root given for label '%s' and could not "
                        "determine one from image path: '%s'." %
                        (name, chromeos_image))
    else:
      chromeos_root = FileUtils().CanonicalizeChromeOSRoot(chromeos_root)
      if not chromeos_root:
        raise Exception("Invalid ChromeOS root given for label '%s': '%s'."
                        % (name, chromeos_root))

    self.chromeos_root = chromeos_root
    if not chrome_src:
      self.chrome_src = os.path.join(self.chromeos_root,
          ".cache/distfiles/target/chrome-src-internal")
      if not os.path.exists(self.chrome_src):
        self.chrome_src = os.path.join(self.chromeos_root,
          ".cache/distfiles/target/chrome-src")
    else:
      chromeos_src = misc.CanonicalizePath(chrome_src)
      if not chromeos_src:
        raise Exception("Invalid Chrome src given for label '%s': '%s'."
                        % (name, chrome_src))
      self.chrome_src = chromeos_src

    self._SetupChecksum()

  def _SetupChecksum(self):
    """Compute label checksum only once."""

    self.checksum = None
    if self.image_type == "local":
      self.checksum = ImageChecksummer().Checksum(self, self.log_level)
    elif self.image_type == "trybot":
      self.checksum = hashlib.md5(self.chromeos_image).hexdigest()

  def _GetImageType(self, chromeos_image):
    image_type = None
    if chromeos_image.find("xbuddy://") < 0:
      image_type = "local"
    elif chromeos_image.find("trybot") >= 0:
      image_type = "trybot"
    else:
      image_type = "official"
    return image_type

  def __hash__(self):
      """Label objects are used in a map, so provide "hash" and "equal"."""

      return hash(self.name)

  def __eq__(self, other):
      """Label objects are used in a map, so provide "hash" and "equal"."""

      return isinstance(other, Label) and other.name == self.name

  def __str__(self):
      """For better debugging."""

      return 'label[name="{}"]'.format(self.name)

class MockLabel(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args, cache_dir, cache_only, chrome_src=None):
    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    self.cache_dir = cache_dir
    self.cache_only = cache_only
    if not chromeos_root:
      self.chromeos_root = "/tmp/chromeos_root"
    else:
      self.chromeos_root = chromeos_root
    self.image_args = image_args
    self.chrome_src = chrome_src
    self.image_type = self._GetImageType(chromeos_image)

  def _GetImageType(self, chromeos_image):
    image_type = None
    if chromeos_image.find("xbuddy://") < 0:
      image_type = "local"
    elif chromeos_image.find("trybot") >= 0:
      image_type = "trybot"
    else:
      image_type = "official"
    return image_type
