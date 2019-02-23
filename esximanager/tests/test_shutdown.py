import unittest
from unittest.mock import patch, Mock
from esximanager.shutdown import Shutdown
from esximanager.tests.dotteddict import DottedDict

TEST_ESXI_HOST = 'esxi.example.com'
MOCK_LOGGER = Mock()
MOCK_LOGGER.info = Mock(side_effect=None)
GETALLVMS_HDR = 'Vmid      Name                        File                       Guest OS       Version   Annotation'

POWER_GETSTATE_ERR = [
    '(vim.fault.NotFound) {',
    '   faultCause = (vmodl.MethodFault) null,',
    '   faultMessage = <unset>',
    '   msg = "Unable to find a VM corresponding to "2""',
    '}',
    ]
POWER_GETSTATE_ON = [ 'Retrieved runtime info', 'Powered on' ]
POWER_GETSTATE_OFF = [ 'Retrieved runtime info', 'Powered off' ]

VM_1 = dict(
    name='R10_V4_Base',
    datastore='[ds-500gb]',
    file='R10_V4_Base/R10_V4_Base.vmx',
    guest_os='centos7_64Guest',
    version='vmx-14',
    )
VM_4 = dict(
    name='load_balancer',
    datastore='[ds-500gb]',
    file='load_balancer/load_balancer.vmx',
    guest_os='centos7_64Guest',
    version='vmx-14',
    )
VM_5 = dict(
    name='web_server',
    datastore='[ds-500gb]',
    file='web_server/web_server.vmx',
    guest_os='centos7_64Guest',
    version='vmx-14',
    )

class Testshutdown(unittest.TestCase):

    def test_get_all_vms_no_vms(self):
        get_all_vms_just_hdr = [ GETALLVMS_HDR ]
        expected_result = {}
        self.exec_get_all_vms_test(get_all_vms_just_hdr, expected_result)

    def test_get_all_vms_only_one(self):
        getallvms_one_vm = [
            GETALLVMS_HDR,
            '1      R10_V4_Base   [ds-500gb] R10_V4_Base/R10_V4_Base.vmx   centos7_64Guest   vmx-14',
            ]
        expected_result = { 1: VM_1 }
        self.exec_get_all_vms_test(getallvms_one_vm, expected_result)

    def test_get_all_vms_multiple(self):
        getallvms_mock_result = [
            GETALLVMS_HDR,
            '1      R10_V4_Base   [ds-500gb] R10_V4_Base/R10_V4_Base.vmx   centos7_64Guest   vmx-14',
            '4      load_balancer   [ds-500gb] load_balancer/load_balancer.vmx   centos7_64Guest   vmx-14',
            '5      web_server   [ds-500gb] web_server/web_server.vmx   centos7_64Guest   vmx-14',
            ]
        expected_result = { 1: VM_1, 4: VM_4, 5: VM_5 }
        self.exec_get_all_vms_test(getallvms_mock_result, expected_result)

    @patch('esximanager.shutdown.Shutdown.fab_get_all_vms')
    def exec_get_all_vms_test(self, mock_fab_get_all_vms_result, expected_result, mock_fab_get_all_vms):
        mock_fab_get_all_vms.return_value = mock_fab_get_all_vms_result
        shutdown = self.get_default_out()
        actual_result = shutdown.get_all_vms()
        self.assertDictEqual(expected_result, actual_result)

    def get_default_out(
            self,
            vm_poweroff_poll=None,
            vm_poweroff_timeout=None,
            esxi_poweroff_poll=None,
            esxi_poweroff_timeout=None):

        args = DottedDict()
        args.esxihost = TEST_ESXI_HOST
        args.dryrun = False

        shutdown = Shutdown(
            args,
            logger=MOCK_LOGGER,
            vm_poweroff_poll=vm_poweroff_poll,
            vm_poweroff_timeout=vm_poweroff_timeout,
            esxi_poweroff_poll=esxi_poweroff_poll,
            esxi_poweroff_timeout=esxi_poweroff_timeout)
        return shutdown

    def test_is_vm_running_is_on(self):
        self.exec_is_vm_running_test(POWER_GETSTATE_ON, True)

    def test_is_vm_running_is_off(self):
        self.exec_is_vm_running_test(POWER_GETSTATE_OFF, False)

    def test_is_vm_running_returns_err(self):
        self.exec_is_vm_running_test(POWER_GETSTATE_ERR, False)

    @patch('esximanager.shutdown.Shutdown.fab_power_getstate')
    def exec_is_vm_running_test(self, mock_fab_power_getstate_result, expected_result, mock_fab_power_getstate):
        mock_fab_power_getstate.return_value = mock_fab_power_getstate_result
        shutdown = self.get_default_out()
        '''
        It doesn't matter what vm_id we pass in to the function, as it will just
        get passed to the mock.
        '''
        actual_result = shutdown.is_vm_running(1)
        self.assertEqual(expected_result, actual_result)

    def test_wait_for_vms_to_shutdown(self):
        '''
        Tests a happy path where we attempt to shutdown 2 vms and one shutsdown
        in the first poll attempt, and the other is down by the 2nd polling.
        '''
        vms = [ 1, 4 ]

        '''
        A dictionary of successive results that should be returned for a given
        vm when the is_vm_running command is called for it.
        '''
        mock_is_vm_running_result = { 1: [True, False], 4: [True, True, False] }

        self.exec_wait_for_vms_to_shutdown_test(
            vms,
            (Shutdown.RESULT_OK, []),
            mock_is_vm_running_result,
            0.01, # quick poll time to keep the tests short
            -1, # no timeout setting for this test
            5)

    def test_wait_for_vms_to_shutdown_force_poweroff(self):
        '''
        For this test, we will include 3 vms.  The first two shutdown within the
        first polling window.  The third, given the timeout configs that we will
        pass to the Shutdown object under test, will effectively never indicate
        that it has shutdown and will test whether or not we call the
        fab task to force the vm to power off.
        '''
        vms = [ 1, 4, 5 ]
        mock_is_vm_running_result = {
            1: [True, False],
            4: [True, False],
            5: None }
        self.exec_wait_for_vms_to_shutdown_test(
            vms,
            (Shutdown.RESULT_TIMEDOUT, [5]),
            mock_is_vm_running_result,
            0.01, # quick poll time to keep the tests short
            0.05, # 1 second timeout
            -1) # We don't care how many times this is called, just that we validate it is called at least once.

    @patch('esximanager.shutdown.Shutdown.is_vm_running')
    def exec_wait_for_vms_to_shutdown_test(
            self,
            vms,
            expected_result,
            mock_is_vm_running_result,
            vm_poweroff_poll,
            vm_poweroff_timeout,
            expected_is_vm_running_call_count,
            mock_is_vm_running):

        def mock_is_vm_running_funct(vm_id):
            retvals = mock_is_vm_running_result[vm_id]
            if retvals is not None:
                # Then we have specified a value to be returned
                retval = retvals.pop(0)
            else:
                '''
                Then we are mocking a situation where the VM never reports that
                is has shutdown and thus always returns True; that it is still
                running.
                '''
                retval = True

            return retval

        # Set up the mocks to return the defined values
        mock_is_vm_running.side_effect = mock_is_vm_running_funct

        shutdown = self.get_default_out(vm_poweroff_poll=vm_poweroff_poll, vm_poweroff_timeout=vm_poweroff_timeout)
        actual_result = shutdown.wait_for_vms_to_shutdown(vms)

        actual_mock_is_vm_running_call_count = mock_is_vm_running.call_count
        if expected_is_vm_running_call_count > 0:
            self.assertEqual(expected_is_vm_running_call_count, actual_mock_is_vm_running_call_count)
        else:
            # Just check that it was called at least once
            self.assertTrue(
                actual_mock_is_vm_running_call_count > 0,
                'The mock_is_vm_running function was never called')
        self.assertEqual(expected_result, actual_result)

    def test_wait_to_return(self):
        mock_funct = Mock(side_effect=[Shutdown.RESULT_WAIT, Shutdown.RESULT_OK])
        actual_result = Shutdown.wait_to_return(MOCK_LOGGER, mock_funct, 0.01, 1)
        self.assertEqual(Shutdown.RESULT_OK, actual_result)
        self.assertEqual(2, mock_funct.call_count)

    def test_wait_to_return_timeout(self):
        mock_funct = Mock(return_value=Shutdown.RESULT_WAIT)
        actual_result = Shutdown.wait_to_return(MOCK_LOGGER, mock_funct, 0.01, 0.05)
        self.assertEqual(Shutdown.RESULT_TIMEDOUT, actual_result)
        self.assertTrue(mock_funct.call_count > 1)
