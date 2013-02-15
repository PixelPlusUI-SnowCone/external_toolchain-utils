#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import optparse
import pickle
import signal
from SimpleXMLRPCServer import SimpleXMLRPCServer
import sys

from automation.common import logger
from automation.common.command_executer import CommandExecuter
from automation.server import machine_manager
from automation.server.job_group_manager import JobGroupManager
from automation.server.job_manager import JobManager


class Server(object):
  def __init__(self, machines_file=None, dry_run=False):
    CommandExecuter.Configure(dry_run)

    self.job_manager = JobManager(
        machine_manager.MachineManager.FromMachineListFile(
            machines_file or machine_manager.DEFAULT_MACHINES_FILE))

    self.job_group_manager = JobGroupManager(self.job_manager)

  def ExecuteJobGroup(self, job_group, dry_run=False):
    job_group = pickle.loads(job_group)
    for job in job_group.jobs:
      job.dry_run = dry_run
    return self.job_group_manager.AddJobGroup(job_group)

  def GetAllJobGroups(self):
    return pickle.dumps(self.job_group_manager.GetAllJobGroups())

  def KillJobGroup(self, job_group_id):
    self.job_group_manager.KillJobGroup(pickle.loads(job_group_id))

  def GetJobGroup(self, job_group_id):
    return pickle.dumps(self.job_group_manager.GetJobGroup(job_group_id))

  def GetJob(self, job_id):
    return pickle.dumps(self.job_manager.GetJob(job_id))

  def GetMachineList(self):
    return pickle.dumps(self.job_manager.machine_manager.GetMachineList())

  def StartServer(self):
    logger.GetLogger().LogOutput("Starting server...")
    self.job_manager.StartJobManager()
    logger.GetLogger().LogOutput("Started server...")

  def StopServer(self):
    logger.GetLogger().LogOutput("Stopping server...")
    self.job_manager.StopJobManager()
    self.job_manager.join()
    logger.GetLogger().LogOutput("Stopped server.")


def Main():
  parser = optparse.OptionParser()
  parser.add_option("-m",
                    "--machines-file",
                    dest="machines_file",
                    help="The location of the file "
                    "containing the machines database",
                    default=machine_manager.DEFAULT_MACHINES_FILE)
  parser.add_option("-n",
                    "--dry-run",
                    dest="dry_run",
                    help="Start the server in dry-run mode, where jobs will "
                    "not actually be executed.",
                    action="store_true",
                    default=False)
  options = parser.parse_args()[0]

  server = Server(options.machines_file, options.dry_run)
  server.StartServer()

  def _HandleKeyboardInterrupt(*_):
    server.StopServer()
    sys.exit(1)

  signal.signal(signal.SIGINT, _HandleKeyboardInterrupt)

  try:
    xmlserver = SimpleXMLRPCServer(("localhost", 8000), allow_none=True)
  except Exception as e:
    logger.GetLogger().LogError(str(e))
    server.StopServer()
    sys.exit(1)

  xmlserver.register_instance(server)
  xmlserver.serve_forever()


if __name__ == "__main__":
  Main()
