# ESXi Management Utility

Originally written to enable the integration with an apcupsd managed server to facilitate cleanly shutting down VMs and the esxi host during a power outage.

The current version uses Python Fabric as opposed to some other abstraction layer such a PyVmomi as the primary requirement was to be able to ```poweroff``` the esxi host itself too.

## Running tests

```
python -m unittest
```

## Generating a Distribution Archive

Create a virtual environment from which you can package the distro.

```
python36 -mvenv ~/.virtualenv/esximanager_build
source ~/.virtualenv/esximanager_build/bin/activate
pip install -U pip setuptools wheel
python setup.py sdist bdist_wheel
```

The tarball should be in ```dist/```.


## Installation

### SSH Keys

Install ssh keys for the user that will be running the esximanager commands such that you can connect to the esxi host as the root user.

### Installing the Python Package

It is recommended that you create a virtual environment (python 3.6) into which you will pip install the package and then just pip install the local tarball:

```
mkdir /usr/local/esximanager
python36 -mvenv /usr/local/esximanager/
source /usr/local/esximanager/bin/activate
pip install -U pip setuptools
pip install file:///path/to/tar.gz
```

## Running

There is a command line entry point configured in setup.py.  Such that once you pip install the distro into your virtual environment you can simply run as follows:

```
/path/to/virtenv/bin/esximanager shutdown --esxihost esxihost.example.com
```

The path to the python binary is to the one in the virtual environment such that you will be running in the correct context.
