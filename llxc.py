#!/usr/bin/python3
"""LLXC Wrapper for LXC Container Managemenr"""

# Copyright (c) 2012 Jonathan Carter
# This file is released under the MIT/expat license.

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# The little perfectionist in me likes to keep this alphabetical.
import argparse
import glob
import gettext
import os
import sys
import time
import tarfile
import shutil
import warnings

# For now we need to filter the warning that python3-lxc produces
with warnings.catch_warnings():
    warnings.filterwarnings("ignore",category=Warning)
    import lxc

from gettext import gettext as _
from subprocess import call

# Set up translations via gettext
gettext.textdomain("llxc")

# Set some variables
CONTAINER_PATH = "/var/lib/lxc/"
AUTOSTART_PATH = "/etc/lxc/auto/"
CGROUP_PATH = "/sys/fs/cgroup/"
ARCHIVE_PATH = CONTAINER_PATH + ".archive/"
LLXCHOME_PATH = "/var/lib/llxc/"

# Set colours, unless llxcmono is set
try:
    if os.environ['llxcmono']:
        GRAY = RED = GREEN = YELLOW = BLUE = \
        PURPLE = CYAN = NORMAL = ""
except KeyError:
    # Light Colour Scheme
    GRAY = "\033[1;30m"
    RED = "\033[1;31m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[1;34m"
    PURPLE = "\033[1;35m"
    CYAN = "\033[1;36m"
    NORMAL = "\033[0m"


def listing():
    """Provides a list of LXC Containers"""
    print ("%s   NAME \tTASKS \t   STATUS \tIP_ADDR_%s%s"
           % (CYAN, args.interface.swapcase(), NORMAL))
    for container in glob.glob(CONTAINER_PATH + '*/config'):
        containername = container.replace(CONTAINER_PATH, "").rstrip("/config")
        cont = lxc.Container(containername)
        try:
            ipaddress = cont.get_ips(protocol="ipv4",
                                     interface="eth0", timeout=0.5)
            ipaddress = ipaddress[0]
        except TypeError:
            ipaddress = "Unavailable"
        except IndexError:
            ipaddress = "Unavailable"
        try:
            tasks = sum(1 for line in open(CGROUP_PATH + "cpuset/lxc/" +
                        containername + "/tasks", 'r'))
        except IOError:
            tasks = "00"
        print ("   %s \t %s \t   %s \t%s" % (containername, tasks,
               cont.state.swapcase(), ipaddress))


def listarchive():
    """Print a list of archived containers"""
    print ("    %sNAME \tSIZE \t     DATE%s" % (CYAN, NORMAL))
    try:
        for container in glob.glob(ARCHIVE_PATH + '*tar.gz'):
            containername = container.replace(ARCHIVE_PATH, "").rstrip(".tar.gz")
            containersize = os.path.getsize(container)
            containerdate = time.ctime(os.path.getctime(container))
            # TODO: Make these dates look less Americ^Wrandom
            print ("    %s \t%.0f MiB\t     %s"
                   % (containername, containersize / 1000 / 1000,
                      containerdate))
    except IOError:
        print ("    Error: Confirm that the archive directory exists"
               "and that it is accessable")


def status():
    """Prints a status report for specified container"""
    # TODO: Add disk usage depending on LVM or plain directory
    # TODO: Add cpuset.cpu - show how many cpus are used
    #test.get_config_item("lxc.rootfs")
    confirm_container_existance()

    # gather some data
    state = lxc.Container(containername).state.swapcase()
    if os.path.lexists(AUTOSTART_PATH + containername):
        autostart = "enabled"
    else:
        autostart = "disabled"
    lxcversion = os.popen("lxc-version | awk {'print $3'}").read()
    lxchost = os.popen("lsb_release -d | awk '{print $2, $3}'").read()
    tasks = sum(1 for line in open(CGROUP_PATH + "cpuset/lxc/" +
                containername + "/tasks", 'r'))
    swappiness = open(CGROUP_PATH + "memory/lxc/" + containername +
                      "/memory.swappiness", 'r').read()
    memusage = int(open(CGROUP_PATH + "memory/lxc/" + containername +
                   "/memory.memsw.usage_in_bytes", 'r').read()) / 1000 / 1000
    init_pid = lxc.Container(containername).init_pid
    config_file = lxc.Container(containername).config_file_name
    # FIXME: Add swap usage
    # swapusage = open(CGROUP_PATH + "memory/lxc/" + containername + "/..."

    print (CYAN + """\
    Status report for container:  """ + containername + NORMAL + """
                         SYSTEM:
                    LXC Version:  %s\
                       LXC Host:  %s\
             Configuration File:  %s

                         MEMORY:
                   Memory Usage:  %s MiB
                     Swap Usage:  Not implemented
                     Swappiness:  %s\

                          STATE:
                       Init PID:  %s
         Autostart on host boot:  %s
                  Current state:  %s
              Running processes:  %s
    """ % (lxcversion, lxchost, config_file, memusage,
           swappiness, init_pid, autostart, state, tasks))
    print (CYAN + "    Tip: " + NORMAL +
           "'llxc status' is experimental and subject to behavioural change")


def kill():
    """Force stop LXC container"""
    requires_root()
    confirm_container_existance()
    print (" * Killing %s..." % (containername))
    cont = lxc.Container(containername)
    if cont.stop():
        print ("   %s%s sucessfully killed%s"
               % (GREEN, containername, NORMAL))


def stop():
    """Displays information about kill and halt"""
    print ("\n"
           "    %sTIP:%s 'stop' is ambiguous, "
           "use one of the following instead:"
           "\n\n"
           "    halt: trigger a shut down in the"
           "container and safely shut down"
           "\n"
           "    kill: stop all processes running"
           "inside the container \n"
           % (CYAN, NORMAL))


def start():
    """Start LXC Container"""
    # TODO: confirm that networking (ie, lxcbr) is available before starting
    requires_root()
    confirm_container_existance()
    print (" * Starting %s..." % (containername))
    cont = lxc.Container(containername)
    if cont.start():
        print ("   %s%s sucessfully started%s"
               % (GREEN, containername, NORMAL))


def halt():
    "Shut Down LXC Container"""
    requires_root()
    confirm_container_existance()
    print (" * Shutting down %s..." % (containername))
    cont = lxc.Container(containername)
    if cont.shutdown():
        print ("   %s%s successfully shut down%s"
               % (GREEN, containername, NORMAL))


def freeze():
    """Freeze LXC Container"""
    requires_root()
    confirm_container_existance()
    if lxc.Container(containername).state == "RUNNING":
        print (" * Freezing container: %s..." % (containername))
        cont = lxc.Container(containername)
        if cont.freeze():
            print ("    %scontainer successfully frozen%s"
                   % (GREEN, NORMAL))
        else:
            print ("    %ERROR:% Something went wrong, please check status."
                   % (RED, NORMAL))
    else:
        print ("   %sERROR:%s The container state is %s,\n"
               "          it needs to be in the 'RUNNING'"
               " state in order to be frozen."
                % (RED, NORMAL, lxc.Container(containername).state))


def unfreeze():
    """Unfreeze LXC Container"""
    requires_root()
    confirm_container_existance()
    if lxc.Container(containername).state == "FROZEN":
        print (" * Unfreezing container: %s..." % (containername))
        cont = lxc.Container(containername)
        if cont.unfreeze():
            print ("    %scontainer successfully unfrozen%s"
                   % (GREEN, NORMAL))
        else:
            print ("    %sERROR:%s Something went wrong, please check status."
                   % (RED, NORMAL))
    else:
        print ("   %sERROR:%s The container state is %s,\n"
               "   it needs to be in the 'FROZEN' state in"
               "order to be unfrozen."
                % (RED, NORMAL, lxc.Container(containername).state))


def toggleautostart():
    """Toggle autostart of LXC Container"""
    requires_root()
    confirm_container_existance()
    if os.path.lexists(AUTOSTART_PATH + containername):
        print ("   %saction:%s disabling autostart for %s..."
               % (GREEN, NORMAL, containername))
        os.unlink(AUTOSTART_PATH + containername)
    else:
        print ("   %saction:%s enabling autostart for %s..."
               % (GREEN, NORMAL, containername))
        os.symlink(CONTAINER_PATH + containername,
                   AUTOSTART_PATH + containername)


def create():
    """Create LXC Container"""
    requires_root()
    # TODO: check that container does not exist
    # TODO: check that we have suficient disk space on LXC partition first
    # TODO: warn at least if we're very low on memory or using a lot of swap
    print (" * Creating container: %s..." % (containername))
    cont = lxc.Container(containername)
    if cont.create('ubuntu'):
        print ("   %scontainer %s successfully created%s"
               % (GREEN, containername, NORMAL))
    else:
        print ("   %ERROR:% Something went wrong, please check status"
               % (RED, NORMAL))
    toggleautostart()
    update_sshkeys()
    start()


def destroy():
    """Destroy LXC Container"""
    requires_root()
    confirm_container_existance()
    if lxc.Container(containername).state == "RUNNING":
        print (" * %sWARNING:%s Container is running, stopping before"
               " destroying in 10 seconds..."
               % (YELLOW, NORMAL))
        time.sleep(10)
        kill()
    print (" * Destroying container " + containername + "...")
    cont = lxc.Container(containername)
    if cont.destroy():
        print ("   %s%s successfully destroyed %s"
               % (GREEN, containername, NORMAL))
    else:
        print ("   %sERROR:%s Something went wrong, please check status"
               % (RED, NORMAL))


def clone():
    """Clone LXC container"""
    #TODO: Confirm source container exists, destination one doesn't
    requires_root()
    cont = lxc.Container(args.newcontainername)
    print (" * Cloning %s in to %s..." % (containername, args.newcontainername))
    if cont.clone(containername):
        print ("   %scloning operation succeeded%s"
               % (GREEN, NORMAL))
    else:
        print ("   %serror:%s Something went wrong, "
               "please check list and status"
               % (RED, NORMAL))


def archive():
    """Archive LXC container by tarring it up and removing it."""
    #TODO: check thatthat archivepath exists and create it if not
    requires_root()
    confirm_container_existance()
    halt()
    print (" * Archiving container: %s..." % (containername))
    #TODO: A progress indicator would be nice.
    previous_path = os.getcwd()
    os.chdir(CONTAINER_PATH)
    tar = tarfile.open(ARCHIVE_PATH + containername + ".tar.gz", "w:gz")
    tar.add(containername)
    tar.close
    os.chdir(previous_path)
    print ("   %scontainer archived in to %s%s.tar.gz%s"
           % (GREEN, CONTAINER_PATH, containername, NORMAL))
    print (" * Removing container path %s..."
           % (CONTAINER_PATH + containername))
    if os.path.isdir(CONTAINER_PATH + containername):
        shutil.rmtree(CONTAINER_PATH + containername)
    # TODO: tore the autostart path and restore it in unarchive
    if os.path.lexists(AUTOSTART_PATH + containername):
        print (" * Autostart was enabled for this container, disabling...")
        os.remove(AUTOSTART_PATH + containername)
    print ("   %sarchiving operation complete%s"
           % (GREEN, NORMAL))


def unarchive():
    """Unarchive LXC container"""
    requires_root()
    #TODO: confirm container doesn't exist
    print (" * Unarchiving container: %s..." % (containername))
    previous_path = os.getcwd()
    os.chdir(CONTAINER_PATH)
    tar = tarfile.open(ARCHIVE_PATH + containername + ".tar.gz", "r:gz")
    tar.extractall()
    os.chdir(previous_path)
    print ("   %stip:%s archive file not removed, container not started,\n"
           "        autostart not restored automatically."
           % (CYAN, NORMAL))
    print ("   %scontainer unarchived%s" % (GREEN, NORMAL))


def startall():
    """Start all LXC containers"""
    requires_root()
    print (" * Starting all stopped containers:")
    for container in glob.glob(CONTAINER_PATH + '*/config'):
        global containername
        containername = container.replace(CONTAINER_PATH, "").rstrip("/config")
        if lxc.Container(containername).state.swapcase() == "stopped":
            start()


def haltall():
    """Halt all LXC containers"""
    requires_root()
    print (" * Halting all containers:")
    for container in glob.glob(CONTAINER_PATH + '*/config'):
        global containername
        containername = container.replace(CONTAINER_PATH, "").rstrip("/config")
        if lxc.Container(containername).state.swapcase() == "running":
            halt()


def killall():
    """Kill all LXC containers"""
    print (" * Killing all running containers:")
    for container in glob.glob(CONTAINER_PATH + '*/config'):
        global containername
        containername = container.replace(CONTAINER_PATH, "").rstrip("/config")
        if lxc.Container(containername).state.swapcase() == "running":
            kill()


# Tests

def requires_root():
    """Tests whether the user is root. Required for many functions"""
    if not os.getuid() == 0:
        print(_("   %sERROR 403:%s This function requires root. \
                Further execution has been aborted." % (RED, NORMAL)))
        sys.exit(403)


def confirm_container_existance():
    """Checks whether specified container exists before execution."""
    try:
        if not os.path.exists(CONTAINER_PATH + containername):
            print (_("   %sERROR 404:%s That container (%s)"
                     "could not be found."
                      % (RED, NORMAL, containername)))
            sys.exit(404)
    except NameError:
        print (_("   %sERROR 400:%s You must specify a container."
                  % (RED, NORMAL)))
        sys.exit(404)


def gen_sshkeys():
    """Generate SSH keys to access containers with"""
    # m2crypto hasn't been ported to python3 yet
    # so for now we do it via shell
    # TODO: check if keypair already exists
    print (" * Generating ssh keypair...")
    directory = os.path.dirname("/var/lib/llxc/ssh/")
    if not os.path.exists(directory):
        os.makedirs(directory)
    if os.popen("ssh-keygen -f %sssh/container_rsa -N ''"
                % (LLXCHOME_PATH)):
        print ("   %skeypair generated%s" % (GREEN, NORMAL))
    else:
        print ("   %skeypair generation failed%s" % (RED,NORMAL))


def update_sshkeys():
    """Update ssh keys in LXC containers"""
    # TODO: update keys for aware hosts
    print (" * Updating keys...")
    # read public key file:
    pkey = open(LLXCHOME_PATH + "ssh/container_rsa.pub", "r")
    pkeydata = pkey.read()
    pkey.close()
    for container in glob.glob(CONTAINER_PATH + '*/config'):
        containerpath = container.rstrip("/config")
        if not os.path.exists(containerpath + "/rootfs/root/.ssh"):
            os.makedirs(containerpath + "/rootfs/root/.ssh")
        # append public key to authorized_keys in container
        keypresent=False
        try:
            for publickey in open(containerpath +
                                  "/rootfs/root/.ssh/authorized_keys"):
                if pkeydata in publickey:
                    keypresent=True
        except IOError:
            pass
        if not keypresent:
            print ("   %sinstalling key in container: %s%s"
                   % (GREEN, container.replace(CONTAINER_PATH, "").rstrip("/config"), NORMAL))
            fout = open(containerpath + "/rootfs/root/.ssh/authorized_keys", "a+")
            fout.write(pkeydata)
            fout.close()


def execute():
    """Execute a command in a container via SSH"""
    #FIXME: There should be a way to exec commands without having
    #       to enclose it in ticks
    print (" * Executing '%s' in %s..." % (args.command, containername))
    return_code = call("ssh %s %s"
                       % (containername, args.command), shell=True)
    if not return_code == 0:
        print ("    %swarning:%s last exit code in container: %s"
               % (YELLOW, NORMAL, return_code))
    print ("    %sexecution completed for container: %s...%s"
           % (GREEN, containername, NORMAL))


def enter():
    """Enter a container via SSH"""
    print (" * Entering container %s..." % (containername))
    #print (os.popen("ssh %s" % (containername)).read())
    return_code = call("ssh %s" % (containername), shell=True)
    if not return_code == 0:
        print ("    %swarning:%s last exit code in container: %s"
               % (YELLOW, NORMAL, return_code))
    print ("    %sexiting container: %s...%s"
           % (GREEN, containername, NORMAL))


def diagnostics():
    """Prints any information we can provide on the LXC Host system"""
    # TODO: make the capability to use an external config filelike
    #       lxc-checkconfig
    print ("LXC Diagnostics")
    print ("  NAMESPACES:")
    print ("    Namespaces: %s")
    print ("    Utsname namespace: %s")
    print ("    Ipc namespace: %s")
    print ("    Pid namespace: %s")
    print ("    User namespace: %s")
    print ("    Network namespace: %s")
    print ("    Multiple /dev/pts instances: %s")
    print ("  CONTROL GROUPS:")
    print ("    Cgroup: %s")
    print ("    Cgroup clone_children flag: %s")
    print ("    Cgroup device: %s")
    print ("    Cgroup sched: %s")
    print ("    Cgroup cpu account: %s")
    print ("    Cgroup memory controller: %s")
    print ("    Cgroup cpuset: %s")
    print ("  MISC:")
    print ("    Veth pair device: %s")
    print ("    Macvlan: %s")
    print ("    Vlan: %s")
    print ("    File capabilities: %s")


# Argument parsing

parser = argparse.ArgumentParser(
         description=_("LLXC Linux Container Management"),
         formatter_class=argparse.RawTextHelpFormatter)

# Optional arguements

parser.add_argument("-if", "--interface", type=str, default="eth0",
                     help=_("Ethernet Interface, eg: eth0, eth1"))
parser.add_argument("-ip", "--ipstack", type=str, default="ipv4",
                     help=_("Network IP to list, ex: ipv4, ipv6"))

sp = parser.add_subparsers(help='sub command help')

sp_create = sp.add_parser('create', help='Create a container')
sp_create.add_argument('containername', type=str,
                        help='name of the container')
sp_create.set_defaults(function=create)

sp_destroy = sp.add_parser('destroy', help='Destroy a container')
sp_destroy.add_argument('containername', type=str,
                         help='name of the container')
sp_destroy.set_defaults(function=destroy)

sp_status = sp.add_parser('status', help='Display container status')
sp_status.add_argument('containername', type=str,
                        help='Name of the container')
sp_status.set_defaults(function=status)

sp_stop = sp.add_parser('stop', help='Not used')
sp_stop.add_argument('containername', type=str,
                      help='Name of the container')
sp_stop.set_defaults(function=stop)

sp_start = sp.add_parser('start', help='Starts a container')
sp_start.add_argument('containername', type=str,
                       help='Name of the container')
sp_start.set_defaults(function=start)

sp_kill = sp.add_parser('kill', help='Kills a container')
sp_kill.add_argument('containername', type=str,
                      help='Name of the container to be killed')
sp_kill.set_defaults(function=kill)

sp_halt = sp.add_parser('halt', help='Shuts down a container')
sp_halt.add_argument('containername', type=str,
                          help='Name of the container')
sp_halt.set_defaults(function=halt)

sp_toggleautostart = sp.add_parser('toggleautostart',
    help='Toggles the state of starting up on boot time for a container')
sp_toggleautostart.add_argument('containername', type=str,
                                    help='Name of the container')
sp_toggleautostart.set_defaults(function=toggleautostart)

sp_freeze = sp.add_parser('freeze', help='Freezes a container')
sp_freeze.add_argument('containername', type=str,
                          help='Name of the container')
sp_freeze.set_defaults(function=freeze)

sp_unfreeze = sp.add_parser('unfreeze', help='Unfreezes a container')
sp_unfreeze.add_argument('containername', type=str,
                          help='Name of the container')
sp_unfreeze.set_defaults(function=unfreeze)

sp_list = sp.add_parser('list', help='Displays a list of containers')
sp_list.set_defaults(function=listing)

sp_clone = sp.add_parser('clone', help='Clone a container into a new one')
sp_clone.add_argument('containername', type=str,
                       help='Name of the container to be cloned')
sp_clone.add_argument('newcontainername', type=str,
                       help='Name of the new container to be created')
sp_clone.set_defaults(function=clone)

sp_archive = sp.add_parser('archive', help='Archive a container')
sp_archive.add_argument('containername', type=str,
                        help="Name of the container to be archived")
sp_archive.set_defaults(function=archive)

sp_unarchive = sp.add_parser('unarchive', help='Unarchive a container')
sp_unarchive.add_argument('containername', type=str,
                        help="Name of the container to be unarchived")
sp_unarchive.set_defaults(function=unarchive)

sp_startall = sp.add_parser('startall', help='Start all stopped containers')
sp_startall.set_defaults(function=startall)

sp_haltall = sp.add_parser('haltall', help='Halt all started containers')
sp_haltall.set_defaults(function=haltall)

sp_killall = sp.add_parser('killall', help='Kill all started containers')
sp_killall.set_defaults(function=killall)

sp_gensshkeys = sp.add_parser('gensshkeys', help='Generates new SSH keypair')
sp_gensshkeys.set_defaults(function=gen_sshkeys)

sp_listarchive = sp.add_parser('listarchive', help='List archived containers')
sp_listarchive.set_defaults(function=listarchive)

sp_updatesshkeys = sp.add_parser('updatesshkeys', help='Update SSH public'
                                 'keys in containers')
sp_updatesshkeys.set_defaults(function=update_sshkeys)

sp_exec = sp.add_parser('exec', help='Execute a command in container via SSH')
sp_exec.add_argument('containername', type=str,
                        help="Name of the container to execute command in")
sp_exec.add_argument('command', type=str, nargs='?',
                        help="Command to be executed")
sp_exec.set_defaults(function=execute)

sp_enter = sp.add_parser('enter', help='Log in to a container via SSH')
sp_enter.add_argument('containername', type=str,
                        help="Name of the container to enter")
sp_enter.set_defaults(function=enter)

sp_diagnostics = sp.add_parser('diagnostics',
                               help='Print available diagnostics information')
sp_diagnostics.set_defaults(function=diagnostics)

args = parser.parse_args()

try:
    containername = args.containername
except AttributeError:
    pass

# Run functions
try:
    args.function()
except KeyboardInterrupt:
    print ("\n   %sinfo:%s Aborting operation, at your request"
           % (CYAN, NORMAL))
