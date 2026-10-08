import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import rtl_devices as rtl
from server import Controller, validate_config

LIST = 'Found 2 device(s):\n0: broken, device, SN: \ufffd\x19\n1: Realtek, RTL2838UHIDIR, SN: 00000001 (currently selected)\n'


class DiscoveryTests(unittest.TestCase):
    def test_corrupt_usb_strings_are_not_receiver_identities(self):
        self.assertEqual(rtl.dump_devices(LIST), [{'index': 1, 'serial': '00000001'}])

    def test_empty_serial_does_not_consume_the_next_output_line(self):
        self.assertEqual(rtl.dump_devices('0: R, SDR, SN: \nUsing device 0: RTL-SDR\n'), [])

    @patch.object(rtl, 'run_helper')
    def test_adsb_uses_structured_inventory_not_decoder_output(self, helper):
        device={'index':0,'serial':'00000001'}
        helper.side_effect=[[device],device]
        self.assertEqual(rtl.resolve(Path('/app'),'adsb'),device)
        self.assertTrue(str(helper.call_args.args[0]).endswith('rtl-probe.exe'))
        self.assertEqual(helper.call_args.args[1][:2],['--open','0'])

    @patch.object(rtl, 'run_helper')
    def test_busy_preferred_receiver_falls_back(self, helper):
        a={'index':0,'serial':'A'};b={'index':1,'serial':'B'}
        helper.side_effect=[[a,b],RuntimeError('busy'),b]
        self.assertEqual(rtl.resolve(Path('/app'),'adsb'),b)

    @patch.object(rtl, 'run_helper')
    def test_explicit_missing_serial_never_selects_another_receiver(self, helper):
        helper.return_value=[{'index':0,'serial':'A'}]
        with self.assertRaisesRegex(RuntimeError,'not found'):
            rtl.resolve(Path('/app'),'adsb',serial='B')
        self.assertEqual(helper.call_count,1)

    @patch.object(rtl, 'run_helper')
    def test_duplicate_serial_is_rejected(self, helper):
        helper.return_value=[{'index':0,'serial':'A'},{'index':1,'serial':'A'}]
        with self.assertRaisesRegex(RuntimeError,'ambiguous'):
            rtl.resolve(Path('/app'),'adsb')

    @patch.object(rtl.subprocess, 'run')
    def test_helper_logs_failure_before_raising(self, run):
        run.return_value=Mock(returncode=1,stdout='',stderr='USB access denied')
        with self.assertLogs(level='INFO') as logs:
            with self.assertRaisesRegex(RuntimeError,'USB access denied'):
                rtl.run_helper(Path('/app/rtl-probe.exe'),['--list'])
        self.assertIn('USB access denied',' '.join(logs.output))

    @patch.object(rtl.subprocess, 'run')
    def test_helper_timeout_is_reported(self, run):
        run.side_effect=subprocess.TimeoutExpired('probe',15,output=b'partial',stderr=b'detail')
        with self.assertLogs(level='ERROR') as logs:
            with self.assertRaisesRegex(RuntimeError,'timed out'):
                rtl.run_helper(Path('/app/rtl-probe.exe'),['--list'])
        self.assertIn('partial',' '.join(logs.output))

    @patch.object(rtl.subprocess, 'run')
    def test_helper_rejects_malformed_inventory(self, run):
        run.return_value=Mock(returncode=0,stdout='[{"index":0}]',stderr='')
        with self.assertRaisesRegex(RuntimeError,'Invalid RTL'):
            rtl.run_helper(Path('/app/rtl-probe.exe'),['--list'])

    @patch.object(rtl.subprocess, 'run')
    @patch.object(rtl, 'probe')
    def test_ais_uses_serial_not_dump_index(self, probe, run):
        run.return_value = Mock(returncode=0, stdout=json.dumps({'index': 0, 'serial': '00000001'}))
        probe.return_value = (True, 'receiving')
        self.assertEqual(rtl.resolve(Path('/app'), 'ais', 1, '00000001')['index'], 0)
        command = probe.call_args.args[0]
        self.assertEqual(command[1:3], ['-d', '00000001'])
        self.assertNotIn('-d:1', command)

    @patch.object(rtl.subprocess, 'run')
    def test_native_uses_its_own_index(self, run):
        run.return_value = Mock(returncode=0, stdout='{"index": 0, "serial": "00000001"}')
        self.assertEqual(rtl.resolve(Path('/app'), 'native', 1, '00000001')['index'], 0)
        self.assertEqual(run.call_args.args[0][-2:], ['native', '00000001'])

    @patch.object(rtl.subprocess, 'run')
    def test_dll_failure_reports_backend(self, run):
        run.return_value = Mock(returncode=1, stderr='WinUSB unavailable')
        with self.assertRaisesRegex(RuntimeError, 'native.*WinUSB'):
            rtl.resolve(Path('/app'), 'native')

    @patch.object(rtl.C, 'CDLL')
    @patch.object(rtl.os, 'add_dll_directory', create=True)
    def test_native_skips_busy_device_and_closes_successful_handle(self, dll_dir, load):
        dll_dir.return_value = MagicMock()
        library = load.return_value
        library.rtlsdr_get_device_count.return_value = 2
        def strings(index, manufacturer, product, number):
            number.value = (b'A', b'B')[index]
            return 0
        library.rtlsdr_get_device_usb_strings.side_effect = strings
        def open_device(pointer, index):
            if index == 0:return -6
            pointer._obj.value = 123
            return 0
        library.rtlsdr_open.side_effect = open_device
        result = rtl.resolve_dll(Path('/app/vendor/native'), '')
        self.assertEqual(result, {'index': 1, 'serial': 'B'})
        self.assertEqual(library.rtlsdr_open.call_count, 2)
        library.rtlsdr_close.assert_called_once()
        self.assertEqual(library.rtlsdr_close.call_args.args[0].value, 123)

    @patch.object(rtl, 'run_helper')
    def test_explicit_busy_receiver_does_not_fall_back(self, probe):
        probe.side_effect = [[{'index':0,'serial':'A'},{'index':1,'serial':'B'}],RuntimeError('busy')]
        with self.assertRaisesRegex(RuntimeError, 'could be opened'):
            rtl.resolve(Path('/app'), 'adsb', serial='A')
        self.assertEqual(probe.call_count,2)

    @patch.object(rtl, 'run_helper')
    def test_no_devices_produces_actionable_error(self, probe):
        probe.return_value = []
        with self.assertRaisesRegex(RuntimeError, 'Reconnect'):
            rtl.resolve(Path('/app'), 'adsb')

    @patch.object(rtl.subprocess, 'Popen')
    def test_hung_probe_is_killed_and_reaped(self, popen):
        proc = popen.return_value
        proc.communicate.side_effect = [subprocess.TimeoutExpired('test', 2),
                                       subprocess.TimeoutExpired('test', 3), ('out', 'err')]
        proc.poll.return_value = -1
        self.assertEqual(rtl.probe(['/app/test.exe']), (True, 'out\nerr'))
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        self.assertEqual(proc.communicate.call_count, 3)

    @patch('server.resolve_rtl')
    def test_controller_preserves_identity_between_protocols(self, resolve):
        controller = Controller.__new__(Controller)
        controller.config = {'device_index': 1, 'rtl_serial': ''}
        controller.rtl_selected_serial = ''
        resolve.side_effect = [{'index': 1, 'serial': 'A'}, {'index': 0, 'serial': 'A'}]
        controller.select_rtl('adsb')
        controller.select_rtl('acars')
        self.assertEqual(resolve.call_args.args[1:], ('native', 1, 'A'))

    def test_old_configuration_defaults_to_auto(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'app/config.example.json').read_text())
        config.pop('rtl_serial')
        self.assertEqual(validate_config(config)['rtl_serial'], '')
        config['rtl_serial'] = '\x00invalid'
        with self.assertRaises(ValueError):
            validate_config(config)


if __name__ == '__main__':
    unittest.main()
