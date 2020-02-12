# Publish/Subscribe with P4

This repository is made as a proof of concept for my thesis in Master of the science in the Communications and Computer network.

## Introduction

In this repository two sample solutions for State Replication is prepared
by help of the P4 language and the PUBLISH/SUBSCRIBE scheme.
It has two modules:

1. By using the internal registers
* [Register-based solution](./pubsub_register)

2. By using the P4Runtime and the embedded-local Controller and tables
* [Embedded-controller solution](./pubsub_embedded)


## Presentation

For starting with the P4 language, one can refer to the [P4 tutorial](https://github.com/p4lang/tutorials), prepared by the [P4.ORG](https://p4.org/) as a learning source.

The environment for running is captured from the [P4 tutorial](https://github.com/p4lang/tutorials).

## Obtaining required software

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
