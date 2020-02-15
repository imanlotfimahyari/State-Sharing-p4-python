# State Sharing with P4

## Introduction

In this repository a sample solution for State sharing is prepared
by help of the P4 language and the PUBLISH/SUBSCRIBE scheme.

1. By using the internal registers
* [Register-based solution](./pubsub/pubsub_register)

## Presentation

For starting with the P4 language, one can refer to the [P4 tutorial](https://github.com/p4lang/tutorials), prepared by the [P4.ORG](https://p4.org/) as a learning source.

## Obtaining required software

The environment for running and the instructions for this part
is derived from the [P4 tutorial](https://github.com/p4lang/tutorials).

To run the proposed solutions, you will need to either build a
virtual machine or install several dependencies.

To build the virtual machine:
- Install [Vagrant](https://vagrantup.com) and [VirtualBox](https://virtualbox.org)
- Clone the repository
- `cd vm`
- `vagrant up`
- Log in with username `p4` and password `p4` and issue the command `sudo shutdown -r now`
- When the machine reboots, you should have a graphical desktop machine with the required
software pre-installed.

*Note: Before running the `vagrant up` command, make sure you have enabled virtualization in your environment; otherwise you may get a "VT-x is disabled in the BIOS for both all CPU modes" error. Check [this](https://stackoverflow.com/questions/33304393/vt-x-is-disabled-in-the-bios-for-both-all-cpu-modes-verr-vmx-msr-all-vmx-disabl) for enabling it in virtualbox and/or BIOS for different system configurations.

You will need the script to execute to completion before you can see the `p4` login on your virtual machine's GUI. In some cases, the `vagrant up` command brings up only the default `vagrant` login with the password `vagrant`. Dependencies may or may not have been installed for you to proceed with running P4 programs. Please refer the existing issues to help fix your problem or create a new one if your specific problem isn't addressed there.*

To install dependencies by hand, please reference the [vm](../vm) installation scripts.
They contain the dependencies, versions, and installation procedure.
You should be able to run them directly on an Ubuntu 16.04 machine, although note that the scripts currently assume the existence of a directory `/home/vagrant`:
- `sudo ./root-bootstrap.sh`
- `sudo ./user-bootstrap.sh`
