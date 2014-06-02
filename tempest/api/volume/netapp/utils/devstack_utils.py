# Copyright (c) 2014 NetApp, Inc.
# All Rights Reserved.
"""
This file house some utilities that are related to using OpenStack in a
devstack environment.

@author: Glenn M. Gobeli
@author: Andrew D. Kerr
"""

import os
import subprocess

import paramiko
from tempest.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class SSH:
    """
    This is a generic SSH client that a user can invoke to obtain
    ssh connectivity in their Python module.
    """
    def __init__(self, host, username, password, timeout=600, port=22):
        # Assign the class variables.
        self.host_ip = host
        self.host_username = username
        self.host_pw = password
        self.timeout = timeout
        self.port = port
        self.cmd = ""
        self.stdout = []
        self.stderr = []

        # Create the SSH client.
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.host_ip,
                            self.port,
                            self.host_username,
                            self.host_pw,
                            timeout=self.timeout)

    def run_cmd(self, cmd, echocmd=True):
        self.cmd = cmd
        if echocmd:
            LOG.info("ssh %s@%s \'%s\'" % (self.host_username,
                                           self.host_ip,
                                           self.cmd))

        (stdin, stdout, stderr) = self.client.exec_command(cmd)
        stdin.close()

        # Save off command output.
        self.stdout = stdout.readlines()
        self.stderr = stderr.readlines()

    def close(self):
        # Close SSH connection
        self.client.close()

    def output(self):
        return self.stdout

    def error(self):
        return self.stderr


def start_cinder_volume():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-vol",
                           "-X", "stuff", "!!\n"])


def stop_cinder_volume():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-volume"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid], stdout=open(os.devnull),
                        stderr=open(os.devnull))


def restart_cinder_volume():
    stop_cinder_volume()
    start_cinder_volume()


def start_cinder_scheduler():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-sch",
                           "-X", "stuff", "!!\n"])


def stop_cinder_scheduler():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-scheduler"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid], stdout=open(os.devnull),
                        stderr=open(os.devnull))


def restart_cinder_scheduler():
    stop_cinder_scheduler()
    start_cinder_scheduler()


def start_cinder_backup():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-bak",
                           "-X", "stuff", "!!\n"])


def stop_cinder_backup():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-backup"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid], stdout=open(os.devnull),
                        stderr=open(os.devnull))


def restart_cinder_backup():
    stop_cinder_backup()
    start_cinder_backup()


def start_cinder_api():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-api",
                           "-X", "stuff", "!!\n"])


def stop_cinder_api():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-api"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid], stdout=open(os.devnull),
                        stderr=open(os.devnull))


def restart_cinder_api():
    stop_cinder_api()
    start_cinder_api()


def restart_cinder():
    restart_cinder_volume()
    restart_cinder_backup()
    restart_cinder_scheduler()
    restart_cinder_api()


def stop_glance_api():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "glance-api"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid], stdout=open(os.devnull),
                        stderr=open(os.devnull))


def start_glance_api():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "g-api",
                           "-X", "stuff", "!!\n"])


def restart_glance_api():
    stop_glance_api()
    start_glance_api()


def stop_glance_reg():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "glance-registry"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid], stdout=open(os.devnull),
                        stderr=open(os.devnull))


def start_glance_reg():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "g-reg",
                           "-X", "stuff", "!!\n"])


def restart_glance_reg():
    stop_glance_reg()
    start_glance_reg()


def restart_glance():
    restart_glance_api()
    restart_glance_reg()
