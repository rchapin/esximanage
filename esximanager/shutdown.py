import time
from fabric.api import run, env, local, settings

class Shutdown(object):

    DEFAULT_VM_POWEROFF_POLL_SECONDS = 2
    DEFAULT_VM_POWEROFF_TIMEOUT = 60
    RESULT_OK = 'OK'
    RESULT_WAIT = 'WAIT'
    RESULT_TIMEDOUT = 'TIMEDOUT'

    DEFAULT_EXSI_HOST_POWEROFF_POLL_SECONDS = 2
    DEFAULT_EXSI_HOST_POWEROFF_TIMEOUT = 60

    '''
    Amount of time, in seconds, that we will wait to exit the Shutdown.shutdown
    function after we can no longer ping the esxi host . . . giving it a bit
    more time to shutdown before returning to the host that is directly
    issuing the shutdown commands.
    '''
    DEFAULT_ESXI_HOST_POWEROFF_DELAY = 5

    def __init__(
            self,
            args,
            logger,
            vm_poweroff_poll=None,
            vm_poweroff_timeout=None,
            esxi_poweroff_poll=None,
            esxi_poweroff_timeout=None):
        '''
        Providing a value of -1 for poweroff_timeout means we do not timeout
        when attempting to verify that the vms have shutdown.
        '''
        self.esxihost = args.esxihost
        self.dryrun = args.dryrun
        self.logger = logger

        # Do not allow values less then 0
        if vm_poweroff_poll is not None and vm_poweroff_poll > 0:
            self.vm_poweroff_poll = vm_poweroff_poll
        else:
            self.vm_poweroff_poll = Shutdown.DEFAULT_VM_POWEROFF_POLL_SECONDS
        self.vm_poweroff_timeout = vm_poweroff_timeout if vm_poweroff_timeout is not None else Shutdown.DEFAULT_VM_POWEROFF_TIMEOUT

        if esxi_poweroff_poll is not None and esxi_poweroff_poll > 0:
            self.esxi_poweroff_poll = esxi_poweroff_poll
        else:
            self.esxi_poweroff_poll = Shutdown.DEFAULT_EXSI_HOST_POWEROFF_POLL_SECONDS
        self.esxi_poweroff_timeout = esxi_poweroff_timeout if esxi_poweroff_timeout is not None else Shutdown.DEFAULT_EXSI_HOST_POWEROFF_TIMEOUT

        env.user = 'root'
        env.host_string = self.esxihost
        env.shell = '/bin/sh -l -c'

    def fab_get_all_vms(self):
        retval = run('vim-cmd vmsvc/getallvms').stdout.splitlines()
        return retval

    def fab_power_getstate(self, vm_id):
        retval = run(f'vim-cmd vmsvc/power.getstate {vm_id}').stdout.splitlines()
        return retval

    def fab_shutdown_vm(self, vm_id):
        '''
        Issues a graceful shutdown of the vm.
        '''
        return run(f'vim-cmd vmsvc/power.shutdown {vm_id}').succeeded

    def fab_poweroff_vm(self, vm_id):
        '''
        Powers off the vm, NOT a graceful shutdown.
        '''
        return run(f'vim-cmd vmsvc/power.off {vm_id}').succeeded

    def fab_poweroff_esxihost(self):
        if self.dryrun:
            self.logger.info('In dryrun mode, just returning with an OK result')
            return True
        return run(f'poweroff').succeeded

    def get_all_vms(self):
        retval = {}
        fab_result = self.fab_get_all_vms()

        if len(fab_result) == 1:
            return retval

        for line in fab_result[1:]:
            self.logger.info(f'Parsing raw vm output line={line}')
            tokens = line.split()
            vm_data = dict(
                name=tokens[1],
                datastore=tokens[2],
                file=tokens[3],
                guest_os=tokens[4],
                version=tokens[5],
                )
            retval[int(tokens[0])] = vm_data

        return retval

    def get_running_vms(self, vms):
        retval = []
        for vm_id, _ in vms.items():
            if self.is_vm_running(vm_id):
                retval.append(vm_id)
        return retval

    def is_vm_running(self, vm_id):
        fab_output = self.fab_power_getstate(vm_id)
        # If we don't even have two lines of output this vm is considered NOT running
        if len(fab_output) < 2:
            return False

        # Confirm that the first line is what is expected for querying the state of a vm
        expected_first_line = 'Retrieved runtime info'
        if expected_first_line not in fab_output[0]:
            # Probably not a valid vm id so we will consider it NOT running
            return False

        return True if 'Powered on' in fab_output[1] else False

    def shutdown_vms(self, vms):
        for vm_id in vms:
            if self.fab_shutdown_vm(vm_id) is False:
                self.logger.error(f'Unable to issue shutdown command for vm_id={vm_id}')

    def poweroff_vms(self, vms, vm_metadata):
        for vm_id in vms:
            if self.fab_poweroff_vm(vm_id) is False:
                self.logger.error(f'Unable to issue poweroff command for vm_id={vm_id}, metadata={vm_metadata[vm_id]}')

    def fab_ping_esxihost(self):
        with settings(warn_only=True):
            result = local(f'ping -c 1 -w 1 {self.esxihost}', capture=True)
            self.logger.info(f'ping result stdout={result.stdout}, stderr={result.stderr}')
            if result.return_code == 0:
                return True
            else:
                return False

    @staticmethod
    def wait_to_return(logger, funct, polltime, timeout):
        start_time = time.time()
        while True:
            # Determine if we have exceeded the timeout if we are so configured
            if timeout > 0 and  (time.time() - start_time) > timeout:
                return Shutdown.RESULT_TIMEDOUT

            result = funct()
            if result == Shutdown.RESULT_OK:
                return result

            if result == Shutdown.RESULT_WAIT:
                logger.info(f'Sleeping for polltime={polltime}')
                time.sleep(polltime)

    def wait_for_esxihost_to_shutdown(self):
        def wait_funct():
            ping_result = self.fab_ping_esxihost()

            if self.dryrun:
                self.logger.info('In dryrun mode, just ping once and return OK')
                return Shutdown.RESULT_OK

            if ping_result is True:
                return Shutdown.RESULT_WAIT
            else:
                return Shutdown.RESULT_OK

        retval = Shutdown.wait_to_return(
            self.logger, wait_funct, self.esxi_poweroff_poll, self.esxi_poweroff_timeout)
        return retval

    def wait_for_vms_to_shutdown(self, vms):
        '''
        We poll the vms to see if they are powered off, if there were any to
        power on in the first place.

        Will return a tuple that is a message indicating the shutdown result as
        well as the vms that have not yet shutdown if that is the case.  If
        they are all shutdown it will return an appropriate message and an
        empty dict.
        '''
        if len(vms) == 0:
            return Shutdown.RESULT_OK, []

        start_time = time.time()

        wait_to_power_off = True
        while wait_to_power_off is True:
            vm_still_running = False

            # Determine if we have exceeded our timeout if we are so configured
            if self.vm_poweroff_timeout > 0 and (time.time() - start_time) > self.vm_poweroff_timeout:
                return Shutdown.RESULT_TIMEDOUT, vms

            vms_shutdown = set()

            for vm_id in vms:
                if self.is_vm_running(vm_id):
                    vm_still_running = True
                else:
                    vms_shutdown.add(vm_id)

            # Remove shutdown vms from the original running set
            for shutdown_vm_id in vms_shutdown:
                vms.remove(shutdown_vm_id)

            wait_to_power_off = vm_still_running

            # Now wait a bit and then examine the hosts that were still running
            num_vms_still_running = len(vms)
            if num_vms_still_running > 0:
                self.logger.info(f'Sleeping while we wait to for [{num_vms_still_running}] vms to shutdown')
                time.sleep(self.vm_poweroff_poll)

            if self.dryrun:
                self.logger.info('In dryrun mode, just returning with an OK result')
                return Shutdown.RESULT_OK, []

        if vm_still_running is False:
            return Shutdown.RESULT_OK, []

    def shutdown(self):
        vms = self.get_all_vms()
        running_vms = self.get_running_vms(vms)

        if self.dryrun is False:
            self.shutdown_vms(vms=running_vms)

        wait_result, still_running_vms = self.wait_for_vms_to_shutdown(vms=running_vms)
        if wait_result != Shutdown.RESULT_OK:
            self.logger.warn('All vms did not shutdown cleanly, powering them off forcefully')
            # Force power off the vms
            self.poweroff_vms(still_running_vms, vms)
            # Then give them a little time to be powered off
            wait_result, still_running_vms = self.wait_for_vms_to_shutdown(vms)
            self.logger.warn(
                'After forcefully powering off vms '
                f'wait_resut={wait_result} and still_running_vms={still_running_vms}')

        self.logger.info(f'All vms have been shutdown, shutting down the esxihost={self.esxihost}')
        esxihost_poweroff_success = self.fab_poweroff_esxihost()
        if esxihost_poweroff_success is False:
            self.logger.error(
                'Unable to successfully run fab command to poweroff '
                f'esxihost={self.esxihost}.  It is unknown if the '
                'esxi host has been powered off.')
        else:
            self.wait_for_esxihost_to_shutdown()
            self.logger.info(f'esxihost={self.esxihost} is powered off')

        self.logger.info('Exiting esximanager.Shudown.shutdown')
