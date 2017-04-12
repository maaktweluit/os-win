# Copyright 2016 Cloudbase Solutions Srl
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import ctypes

import ddt
import mock

from os_win import constants
from os_win import exceptions
from os_win.tests.unit import test_base
from os_win.utils.compute import _clusapi_utils


@ddt.ddt
class ClusApiUtilsTestCase(test_base.OsWinBaseTestCase):
    _LIVE_MIGRATION_TYPE = 4

    def setUp(self):
        super(ClusApiUtilsTestCase, self).setUp()

        self._clusapi = mock.patch.object(
            _clusapi_utils, 'clusapi', create=True).start()

        self._clusapi_utils = _clusapi_utils.ClusApiUtils()

        self._run_patcher = mock.patch.object(self._clusapi_utils,
                                              '_run_and_check_output')
        self._mock_run = self._run_patcher.start()

    def _mock_ctypes(self):
        self._ctypes = mock.Mock()
        # This is used in order to easily make assertions on the variables
        # passed by reference.
        self._ctypes.byref = lambda x: (x, "byref")
        self._ctypes.c_wchar_p = lambda x: (x, 'c_wchar_p')
        self._ctypes.sizeof = lambda x: (x, 'sizeof')
        self._ctypes.c_ulong = lambda x: (x, 'c_ulong')

        mock.patch.object(_clusapi_utils, 'ctypes', self._ctypes).start()

    def test_run_and_check_output(self):
        self._clusapi_utils._win32utils = mock.Mock()
        self._clusapi_utils._run_and_check_output = (
            self._run_patcher.temp_original)

        mock_win32utils_run_and_check_output = (
            self._clusapi_utils._win32utils.run_and_check_output)

        ret_val = self._clusapi_utils._run_and_check_output(
            mock.sentinel.func,
            mock.sentinel.arg,
            fake_kwarg=mock.sentinel.kwarg)

        mock_win32utils_run_and_check_output.assert_called_once_with(
            mock.sentinel.func,
            mock.sentinel.arg,
            fake_kwarg=mock.sentinel.kwarg,
            failure_exc=exceptions.ClusterWin32Exception)
        self.assertEqual(mock_win32utils_run_and_check_output.return_value,
                         ret_val)

    def test_dword_align(self):
        self.assertEqual(8, self._clusapi_utils._dword_align(5))
        self.assertEqual(4, self._clusapi_utils._dword_align(4))

    def test_get_clusprop_value_struct(self):
        val_type = ctypes.c_ubyte * 3
        expected_padding_sz = 1

        clusprop_val_struct = self._clusapi_utils._get_clusprop_value_struct(
            val_type)

        expected_fields = [('syntax', _clusapi_utils.DWORD),
                           ('length', _clusapi_utils.DWORD),
                           ('value', val_type),
                           ('_padding', ctypes.c_ubyte * expected_padding_sz)]
        self.assertEqual(expected_fields, clusprop_val_struct._fields_)

    def test_get_property_list_entry(self):
        fake_prop_name = 'fake prop name'
        fake_prop_syntax = 1
        fake_prop_val = (ctypes.c_wchar * 10)()
        fake_prop_val.value = 'fake prop'

        entry = self._clusapi_utils.get_property_list_entry(
            name=fake_prop_name,
            syntax=fake_prop_syntax,
            value=fake_prop_val)

        self.assertEqual(_clusapi_utils.CLUSPROP_SYNTAX_NAME,
                         entry.name.syntax)
        self.assertEqual(fake_prop_name,
                         entry.name.value)
        self.assertEqual(
            ctypes.sizeof(ctypes.c_wchar) * (len(fake_prop_name) + 1),
            entry.name.length)

        self.assertEqual(fake_prop_syntax,
                         entry.value.syntax)
        self.assertEqual(bytearray(fake_prop_val),
                         bytearray(entry.value.value))
        self.assertEqual(
            ctypes.sizeof(fake_prop_val),
            entry.value.length)

        self.assertEqual(_clusapi_utils.CLUSPROP_SYNTAX_ENDMARK,
                         entry._endmark)

    def test_get_property_list(self):
        entry_0 = self._clusapi_utils.get_property_list_entry(
            name='fake prop name',
            syntax=1,
            value=ctypes.c_uint(2))
        entry_1 = self._clusapi_utils.get_property_list_entry(
            name='fake prop name',
            syntax=2,
            value=ctypes.c_ubyte(5))

        prop_list = self._clusapi_utils.get_property_list(
            [entry_0, entry_1])

        self.assertEqual(2, prop_list.count)
        self.assertEqual(bytearray(entry_0) + bytearray(entry_1),
                         prop_list.entries_buff)

    @ddt.data('fake cluster name', None)
    def test_open_cluster(self, cluster_name):
        self._mock_ctypes()

        handle = self._clusapi_utils.open_cluster(cluster_name)

        expected_handle_arg = (
            self._ctypes.c_wchar_p(cluster_name)
            if cluster_name else None)
        self._mock_run.assert_called_once_with(
            self._clusapi.OpenCluster,
            expected_handle_arg,
            **self._clusapi_utils._open_handle_check_flags)

        self.assertEqual(self._mock_run.return_value, handle)

    def test_open_cluster_group(self):
        self._mock_ctypes()

        handle = self._clusapi_utils.open_cluster_group(
            mock.sentinel.cluster_handle,
            mock.sentinel.group_name)

        self._mock_run.assert_called_once_with(
            self._clusapi.OpenClusterGroup,
            mock.sentinel.cluster_handle,
            self._ctypes.c_wchar_p(mock.sentinel.group_name),
            **self._clusapi_utils._open_handle_check_flags)

        self.assertEqual(self._mock_run.return_value, handle)

    def test_open_cluster_node(self):
        self._mock_ctypes()

        handle = self._clusapi_utils.open_cluster_node(
            mock.sentinel.cluster_handle,
            mock.sentinel.node_name)

        self._mock_run.assert_called_once_with(
            self._clusapi.OpenClusterNode,
            mock.sentinel.cluster_handle,
            self._ctypes.c_wchar_p(mock.sentinel.node_name),
            **self._clusapi_utils._open_handle_check_flags)

        self.assertEqual(self._mock_run.return_value, handle)

    def test_close_cluster(self):
        self._clusapi_utils.close_cluster(mock.sentinel.handle)
        self._clusapi.CloseCluster.assert_called_once_with(
            mock.sentinel.handle)

    def test_close_cluster_group(self):
        self._clusapi_utils.close_cluster_group(mock.sentinel.handle)
        self._clusapi.CloseClusterGroup.assert_called_once_with(
            mock.sentinel.handle)

    def test_close_cluster_node(self):
        self._clusapi_utils.close_cluster_node(mock.sentinel.handle)
        self._clusapi.CloseClusterNode.assert_called_once_with(
            mock.sentinel.handle)

    @ddt.data(0, _clusapi_utils.ERROR_IO_PENDING)
    def test_cancel_cluster_group_operation(self, cancel_ret_val):
        self._mock_run.return_value = cancel_ret_val

        expected_ret_val = cancel_ret_val != _clusapi_utils.ERROR_IO_PENDING
        ret_val = self._clusapi_utils.cancel_cluster_group_operation(
            mock.sentinel.group_handle)

        self.assertEqual(expected_ret_val, ret_val)

        self._mock_run.assert_called_once_with(
            self._clusapi.CancelClusterGroupOperation,
            mock.sentinel.group_handle,
            0,
            ignored_error_codes=[_clusapi_utils.ERROR_IO_PENDING])

    @ddt.data(mock.sentinel.prop_list, None)
    def test_move_cluster_group(self, prop_list):
        self._mock_ctypes()

        expected_prop_list_arg = (
            self._ctypes.byref(prop_list) if prop_list else None)
        expected_prop_list_sz = (
            self._ctypes.sizeof(prop_list) if prop_list else 0)

        self._clusapi_utils.move_cluster_group(
            mock.sentinel.group_handle,
            mock.sentinel.dest_node_handle,
            mock.sentinel.move_flags,
            prop_list)

        self._mock_run.assert_called_once_with(
            self._clusapi.MoveClusterGroupEx,
            mock.sentinel.group_handle,
            mock.sentinel.dest_node_handle,
            mock.sentinel.move_flags,
            expected_prop_list_arg,
            expected_prop_list_sz,
            ignored_error_codes=[_clusapi_utils.ERROR_IO_PENDING])

    def test_get_cluster_group_state(self):
        owner_node = 'fake owner node'

        def fake_get_state(inst,
                           group_handle, node_name_buff, node_name_len,
                           error_ret_vals, error_on_nonzero_ret_val,
                           ret_val_is_err_code):
            self.assertEqual(mock.sentinel.group_handle, group_handle)

            # Those arguments would not normally get to the ClusApi
            # function, instead being used by the helper invoking
            # it and catching errors. For convenience, we validate
            # those arguments at this point.
            self.assertEqual([constants.CLUSTER_GROUP_STATE_UNKNOWN],
                             error_ret_vals)
            self.assertFalse(error_on_nonzero_ret_val)
            self.assertFalse(ret_val_is_err_code)

            node_name_len_arg = ctypes.cast(
                node_name_len,
                ctypes.POINTER(_clusapi_utils.DWORD)).contents
            self.assertEqual(self._clusapi_utils._MAX_NODE_NAME,
                             node_name_len_arg.value)

            node_name_arg = ctypes.cast(
                node_name_buff,
                ctypes.POINTER(
                    ctypes.c_wchar *
                    self._clusapi_utils._MAX_NODE_NAME)).contents
            node_name_arg.value = owner_node
            return mock.sentinel.group_state

        self._mock_run.side_effect = fake_get_state

        state_info = self._clusapi_utils.get_cluster_group_state(
            mock.sentinel.group_handle)
        expected_state_info = dict(state=mock.sentinel.group_state,
                                   owner_node=owner_node)
        self.assertEqual(expected_state_info, state_info)

    @ddt.data({'notif_filters': (_clusapi_utils.NOTIFY_FILTER_AND_TYPE * 2)(),
               'exp_notif_filters_len': 2},
              {'notif_filters': _clusapi_utils.NOTIFY_FILTER_AND_TYPE(),
               'notif_port_h': mock.sentinel.notif_port_h,
               'notif_key': mock.sentinel.notif_key})
    @ddt.unpack
    def test_create_cluster_notify_port(self, notif_filters,
                                        exp_notif_filters_len=1,
                                        notif_port_h=None,
                                        notif_key=None):
        self._mock_ctypes()
        self._ctypes.Array = ctypes.Array

        self._clusapi_utils.create_cluster_notify_port_v2(
            mock.sentinel.cluster_handle,
            notif_filters,
            notif_port_h,
            notif_key)

        exp_notif_key_p = self._ctypes.byref(notif_key) if notif_key else None
        exp_notif_port_h = notif_port_h or _clusapi_utils.INVALID_HANDLE_VALUE

        self._mock_run.assert_called_once_with(
            self._clusapi.CreateClusterNotifyPortV2,
            exp_notif_port_h,
            mock.sentinel.cluster_handle,
            self._ctypes.byref(notif_filters),
            self._ctypes.c_ulong(exp_notif_filters_len),
            exp_notif_key_p,
            **self._clusapi_utils._open_handle_check_flags)

    def test_close_cluster_notify_port(self):
        self._clusapi_utils.close_cluster_notify_port(mock.sentinel.handle)
        self._clusapi.CloseClusterNotifyPort.assert_called_once_with(
            mock.sentinel.handle)

    def test_get_cluster_notify_v2(self):
        fake_notif_key = 1
        fake_notif_port_h = 2
        fake_notif_type = 3
        fake_filter_flags = 4
        fake_clus_obj_name = 'fake-changed-clus-object'
        fake_event_buff = 'fake-event-buff'

        notif_key = ctypes.c_ulong(fake_notif_key)
        requested_buff_sz = 1024

        def fake_get_cluster_notify(func, notif_port_h, pp_notif_key,
                                    p_filter_and_type,
                                    p_buff, p_buff_sz,
                                    p_obj_id_buff, p_obj_id_buff_sz,
                                    p_parent_id_buff, p_parent_id_buff_sz,
                                    p_obj_name_buff, p_obj_name_buff_sz,
                                    p_obj_type, p_obj_type_sz,
                                    timeout_ms):
            self.assertEqual(self._clusapi.GetClusterNotifyV2, func)
            self.assertEqual(fake_notif_port_h, notif_port_h)

            obj_name_buff_sz = ctypes.cast(
                p_obj_name_buff_sz,
                ctypes.POINTER(_clusapi_utils.DWORD)).contents
            buff_sz = ctypes.cast(
                p_buff_sz,
                ctypes.POINTER(_clusapi_utils.DWORD)).contents

            # We'll just request the tested method to pass us
            # a buffer this large.
            if (buff_sz.value < requested_buff_sz or
                    obj_name_buff_sz.value < requested_buff_sz):
                buff_sz.value = requested_buff_sz
                obj_name_buff_sz.value = requested_buff_sz
                raise exceptions.ClusterWin32Exception(
                    error_code=_clusapi_utils.ERROR_MORE_DATA,
                    func_name='GetClusterNotify',
                    error_message='error more data')

            pp_notif_key = ctypes.cast(pp_notif_key, ctypes.c_void_p)
            p_notif_key = ctypes.c_void_p.from_address(pp_notif_key.value)
            p_notif_key.value = ctypes.addressof(notif_key)

            filter_and_type = ctypes.cast(
                p_filter_and_type,
                ctypes.POINTER(_clusapi_utils.NOTIFY_FILTER_AND_TYPE)).contents
            filter_and_type.dwObjectType = fake_notif_type
            filter_and_type.FilterFlags = fake_filter_flags

            obj_name_buff = ctypes.cast(
                p_obj_name_buff,
                ctypes.POINTER(
                    ctypes.c_wchar *
                    (requested_buff_sz // ctypes.sizeof(ctypes.c_wchar))))
            obj_name_buff = obj_name_buff.contents
            ctypes.memset(obj_name_buff, 0, obj_name_buff_sz.value)
            obj_name_buff.value = fake_clus_obj_name

            buff = ctypes.cast(
                p_buff,
                ctypes.POINTER(
                    ctypes.c_wchar *
                    (requested_buff_sz // ctypes.sizeof(ctypes.c_wchar))))
            buff = buff.contents
            ctypes.memset(buff, 0, buff_sz.value)
            buff.value = fake_event_buff

            self.assertEqual(mock.sentinel.timeout_ms, timeout_ms)

        self._mock_run.side_effect = fake_get_cluster_notify

        event = self._clusapi_utils.get_cluster_notify_v2(
            fake_notif_port_h, mock.sentinel.timeout_ms)
        w_event_buff = ctypes.cast(
            event['buff'],
            ctypes.POINTER(
                ctypes.c_wchar *
                (requested_buff_sz // ctypes.sizeof(ctypes.c_wchar))))
        w_event_buff = w_event_buff.contents[:]
        event['buff'] = w_event_buff.split('\x00')[0]

        expected_event = dict(cluster_object_name=fake_clus_obj_name,
                              object_type=fake_notif_type,
                              filter_flags=fake_filter_flags,
                              buff=fake_event_buff,
                              buff_sz=requested_buff_sz,
                              notif_key=fake_notif_key)
        self.assertEqual(expected_event, event)

    def _get_fake_prop_list(self):
        syntax = _clusapi_utils.CLUSPROP_SYNTAX_LIST_VALUE_DWORD
        migr_type = _clusapi_utils.DWORD(self._LIVE_MIGRATION_TYPE)

        prop_entries = [
            self._clusapi_utils.get_property_list_entry(
                _clusapi_utils.CLUSPROP_NAME_VM, syntax, migr_type),
            self._clusapi_utils.get_property_list_entry(
                _clusapi_utils.CLUSPROP_NAME_VM_CONFIG, syntax, migr_type),
            self._clusapi_utils.get_property_list_entry(
                _clusapi_utils.CLUSPROP_GROUP_STATUS_INFO,
                _clusapi_utils.CLUSPROP_SYNTAX_LIST_VALUE_ULARGE_INTEGER,
                ctypes.c_ulonglong(_clusapi_utils.
                    CLUSGRP_STATUS_WAITING_IN_QUEUE_FOR_MOVE))  # noqa
        ]

        prop_list = self._clusapi_utils.get_property_list(prop_entries)
        return prop_list

    def test_get_prop_list_entry_p_not_found(self):
        prop_list = self._get_fake_prop_list()

        self.assertRaises(exceptions.ClusterPropertyListEntryNotFound,
                          self._clusapi_utils.get_prop_list_entry_p,
                          ctypes.byref(prop_list),
                          ctypes.sizeof(prop_list),
                          'InexistentProperty')

    def test_get_prop_list_entry_p_parsing_error(self):
        prop_list = self._get_fake_prop_list()

        prop_entry_name_len_addr = ctypes.addressof(
            prop_list.entries_buff) + ctypes.sizeof(ctypes.c_ulong)
        prop_entry_name_len = ctypes.c_ulong.from_address(
            prop_entry_name_len_addr)
        prop_entry_name_len.value = ctypes.sizeof(prop_list)

        self.assertRaises(exceptions.ClusterPropertyListParsingError,
                          self._clusapi_utils.get_prop_list_entry_p,
                          ctypes.byref(prop_list),
                          ctypes.sizeof(prop_list),
                          _clusapi_utils.CLUSPROP_NAME_VM)

    def test_get_prop_list_entry_p(self):
        prop_list = self._get_fake_prop_list()

        prop_entry = self._clusapi_utils.get_prop_list_entry_p(
            ctypes.byref(prop_list),
            ctypes.sizeof(prop_list),
            _clusapi_utils.CLUSPROP_NAME_VM_CONFIG)

        self.assertEqual(
            _clusapi_utils.CLUSPROP_SYNTAX_LIST_VALUE_DWORD,
            prop_entry['syntax'])
        self.assertEqual(
            ctypes.sizeof(ctypes.c_ulong),
            prop_entry['length'])

        val = ctypes.c_ulong.from_address(prop_entry['val_p'].value).value
        self.assertEqual(self._LIVE_MIGRATION_TYPE, val)

    def test_cluster_group_control(self):
        fake_out_buff = 'fake-event-buff'

        requested_buff_sz = 1024

        def fake_cluster_group_ctrl(func, group_handle, node_handle,
                                    control_code,
                                    in_buff_p, in_buff_sz,
                                    out_buff_p, out_buff_sz,
                                    requested_buff_sz_p):
            self.assertEqual(self._clusapi.ClusterGroupControl, func)
            self.assertEqual(mock.sentinel.group_handle, group_handle)
            self.assertEqual(mock.sentinel.node_handle, node_handle)
            self.assertEqual(mock.sentinel.control_code, control_code)
            self.assertEqual(mock.sentinel.in_buff_p, in_buff_p)
            self.assertEqual(mock.sentinel.in_buff_sz, in_buff_sz)

            req_buff_sz = ctypes.cast(
                requested_buff_sz_p,
                ctypes.POINTER(_clusapi_utils.DWORD)).contents
            req_buff_sz.value = requested_buff_sz

            # We'll just request the tested method to pass us
            # a buffer this large.
            if (out_buff_sz.value < requested_buff_sz):
                raise exceptions.ClusterWin32Exception(
                    error_code=_clusapi_utils.ERROR_MORE_DATA,
                    func_name='ClusterGroupControl',
                    error_message='error more data')

            out_buff = ctypes.cast(
                out_buff_p,
                ctypes.POINTER(
                    ctypes.c_wchar *
                    (requested_buff_sz // ctypes.sizeof(ctypes.c_wchar))))
            out_buff = out_buff.contents
            out_buff.value = fake_out_buff

        self._mock_run.side_effect = fake_cluster_group_ctrl

        out_buff, out_buff_sz = self._clusapi_utils.cluster_group_control(
            mock.sentinel.group_handle, mock.sentinel.control_code,
            mock.sentinel.node_handle, mock.sentinel.in_buff_p,
            mock.sentinel.in_buff_sz)

        self.assertEqual(requested_buff_sz, out_buff_sz)
        wp_out_buff = ctypes.cast(
            out_buff,
            ctypes.POINTER(ctypes.c_wchar * requested_buff_sz))
        self.assertEqual(fake_out_buff,
                         wp_out_buff.contents[:len(fake_out_buff)])

    def test_get_cluster_group_status_info(self):
        prop_list = self._get_fake_prop_list()

        status_info = self._clusapi_utils.get_cluster_group_status_info(
            ctypes.byref(prop_list), ctypes.sizeof(prop_list))
        self.assertEqual(
            _clusapi_utils.CLUSGRP_STATUS_WAITING_IN_QUEUE_FOR_MOVE,
            status_info)
