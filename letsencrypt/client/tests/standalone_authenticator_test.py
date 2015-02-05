#!/usr/bin/env python

"""Tests for standalone_authenticator.py."""

import unittest
import mock
import pkg_resources
from letsencrypt.client.challenge_util import DvsniChall


# ErrorAfter/CallableExhausted from
# http://igorsobreira.com/2013/03/17/testing-infinite-loops.html
# to allow interrupting infinite loop under test after one
# iteration.

class ErrorAfter_socket_accept(object):
    """
    Callable that will raise `CallableExhausted`
    exception after `limit` calls, modified to also return
    a tuple simulating the return values of a socket.accept()
    call
    """
    def __init__(self, limit):
        self.limit = limit
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls > self.limit:
            raise CallableExhausted
        # Modified here for a single use as socket.accept()
        return (mock.MagicMock(), "ignored")

class CallableExhausted(Exception):
    pass


class PackAndUnpackTests(unittest.TestCase):
    def test_pack_and_unpack_bytes(self):
        from letsencrypt.client.standalone_authenticator import \
            unpack_2bytes, unpack_3bytes, pack_2bytes, pack_3bytes
        self.assertEqual(unpack_2bytes("JZ"), 19034)
        self.assertEqual(unpack_2bytes(chr(0)*2), 0)
        self.assertEqual(unpack_2bytes(chr(255)*2), 65535)

        self.assertEqual(unpack_3bytes("abc"), 6382179)
        self.assertEqual(unpack_3bytes(chr(0)*3), 0)
        self.assertEqual(unpack_3bytes(chr(255)*3), 16777215)

        self.assertEqual(pack_2bytes(12), chr(0) + chr(12))
        self.assertEqual(pack_2bytes(1729), chr(6) + chr(193))

        self.assertEqual(pack_3bytes(0), chr(0)*3)
        self.assertEqual(pack_3bytes(12345678), chr(0xbc) + "aN")


class TLSParseClientHelloTest(unittest.TestCase):
    def test_tls_parse_client_hello(self):
        from letsencrypt.client.standalone_authenticator import \
            tls_parse_client_hello
        client_hello = "16030100c4010000c003030cfef9971eda442c60cbb6c397" \
            "7957a81a8ada317e800b7867a8c61f71c40cab000020c02b" \
            "c02fc00ac009c013c014c007c011003300320039002f0035" \
            "000a000500040100007700000010000e00000b7777772e65" \
            "66662e6f7267ff01000100000a0008000600170018001900" \
            "0b00020100002300003374000000100021001f0568322d31" \
            "3408737064792f332e3106737064792f3308687474702f31" \
            "2e31000500050100000000000d0012001004010501020104" \
            "030503020304020202".decode("hex")
        return_value = tls_parse_client_hello(client_hello)
        self.assertEqual(return_value, (chr(0xc0) + chr(0x2b), "www.eff.org"))
        # TODO: The failure cases are extremely numerous and require
        #       constructing TLS ClientHello messages that are individually
        #       defective or surprising in distinct ways. (Each invalid TLS
        #       record is invalid in its own way.)


class TLSGenerateServerHelloTest(unittest.TestCase):
    def test_tls_generate_server_hello(self):
        from letsencrypt.client.standalone_authenticator import \
            tls_generate_server_hello
        server_hello = tls_generate_server_hello("Q!")
        self.assertEqual(server_hello[:11].encode("hex"),
            '160303002a020000260303')
        self.assertEqual(server_hello[43:], chr(0) + 'Q!' + chr(0))


class TLSGenerateCertMsgTest(unittest.TestCase):
    def test_tls_generate_cert_msg(self):
        from letsencrypt.client.standalone_authenticator import \
            tls_generate_cert_msg
        cert = pkg_resources.resource_string(__name__,
            'testdata/cert.pem')
        cert_msg = tls_generate_cert_msg(cert)
        self.assertEqual(cert_msg.encode("hex"),
            "16030301ec0b0001e80001e50001e2308201de30820188a0030201020202"
            "0539300d06092a864886f70d01010b05003077310b300906035504061302"
            "55533111300f06035504080c084d6963686967616e311230100603550407"
            "0c09416e6e204172626f72312b3029060355040a0c22556e697665727369"
            "7479206f66204d6963686967616e20616e64207468652045464631143012"
            "06035504030c0b6578616d706c652e636f6d301e170d3134313231313232"
            "333434355a170d3134313231383232333434355a3077310b300906035504"
            "06130255533111300f06035504080c084d6963686967616e311230100603"
            "5504070c09416e6e204172626f72312b3029060355040a0c22556e697665"
            "7273697479206f66204d6963686967616e20616e64207468652045464631"
            "14301206035504030c0b6578616d706c652e636f6d305c300d06092a8648"
            "86f70d0101010500034b003048024100ac7573b451ed1fddae705243fcdf"
            "c75bd02c751b14b875010410e51f036545dddfa79f34aefdbee90584df47"
            "1681d9894bce8e6d1cfa9544e8af84744fedc2e50203010001300d06092a"
            "864886f70d01010b05000341002db8cf421dc0854a4a59ed92c965bebeb3"
            "25ea411f97cc9dd7e4dd7269d748d3e9513ed7828db63874d9ae7a1a8ada"
            "02f2404f9fc7ebb13c1af27fa1c36707fa")


class TLSServerHelloDoneTest(unittest.TestCase):
    def test_tls_generate_server_hello_done(self):
        from letsencrypt.client.standalone_authenticator import \
            tls_generate_server_hello_done
        self.assertEqual(tls_generate_server_hello_done().encode("hex"), \
            "16030300040e000000")


class ChallPrefTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        self.authenticator = StandaloneAuthenticator()

    def test_chall_pref(self):
        self.assertEqual(self.authenticator.get_chall_pref("example.com"),
                    ["dvsni"])


class SNICallbackTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        from letsencrypt.client.challenge_util import dvsni_gen_cert
        from letsencrypt.client import le_util
        import OpenSSL.crypto
        self.authenticator = StandaloneAuthenticator()
        r = "x" * 32
        name, r_b64 = "example.com", le_util.jose_b64encode(r)
        RSA256_KEY = pkg_resources.resource_string(__name__,
            'testdata/rsa256_key.pem')
        nonce, key = "abcdef", le_util.Key("foo", RSA256_KEY)
        self.cert = dvsni_gen_cert(name, r_b64, nonce, key)[0]
        self.authenticator.private_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, key.pem)
        self.authenticator.tasks = {"abcdef.acme.invalid": self.cert}
        self.authenticator.child_pid = 12345

    def test_real_servername(self):
        import OpenSSL.SSL
        connection = mock.MagicMock()
        connection.get_servername.return_value = "abcdef.acme.invalid"
        self.authenticator.sni_callback(connection)
        self.assertEqual(connection.set_context.call_count, 1)
        called_ctx = connection.set_context.call_args[0][0]
        self.assertIsInstance(called_ctx, OpenSSL.SSL.Context)


class ClientSignalHandlerTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        self.authenticator = StandaloneAuthenticator()
        self.authenticator.tasks = {"foononce.acme.invalid": "stuff"}
        self.authenticator.child_pid = 12345

    def test_client_signal_handler(self):
        import signal
        self.assertFalse(self.authenticator.subproc_ready)
        self.assertFalse(self.authenticator.subproc_inuse)
        self.assertFalse(self.authenticator.subproc_cantbind)
        self.authenticator.client_signal_handler(signal.SIGIO, None)
        self.assertTrue(self.authenticator.subproc_ready)

        self.authenticator.client_signal_handler(signal.SIGUSR1, None)
        self.assertTrue(self.authenticator.subproc_inuse)

        self.authenticator.client_signal_handler(signal.SIGUSR2, None)
        self.assertTrue(self.authenticator.subproc_cantbind)

class SubprocSignalHandlerTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        self.authenticator = StandaloneAuthenticator()
        self.authenticator.tasks = {"foononce.acme.invalid": "stuff"}
        self.authenticator.child_pid = 12345
        self.authenticator.parent_pid = 23456

    @mock.patch("letsencrypt.client.standalone_authenticator.os.kill")
    @mock.patch("letsencrypt.client.standalone_authenticator.sys.exit")
    def test_subproc_signal_handler(self, mock_exit, mock_kill):
        import signal
        self.authenticator.ssl_conn = mock.MagicMock()
        self.authenticator.connection = mock.MagicMock()
        self.authenticator.sock = mock.MagicMock()
        self.authenticator.subproc_signal_handler(signal.SIGINT, None)
        self.assertEquals(self.authenticator.ssl_conn.shutdown.call_count, 1)
        self.assertEquals(self.authenticator.ssl_conn.close.call_count, 1)
        self.assertEquals(self.authenticator.connection.close.call_count, 1)
        self.assertEquals(self.authenticator.sock.close.call_count, 1)
        # TODO: We should test that we correctly survive each of the above
        #       raising an exception of some kind (since they're likely to
        #       do so in practice if there's no live TLS connection at the
        #       time the subprocess is told to clean up).
        mock_kill.assert_called_once_with(self.authenticator.parent_pid,
            signal.SIGUSR1)
        mock_exit.assert_called_once_with(0)


class PerformTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        self.authenticator = StandaloneAuthenticator()

    def test_can_perform(self):
        """What happens if start_listener() returns True."""
        from letsencrypt.client import le_util
        RSA256_KEY = pkg_resources.resource_string(__name__,
            'testdata/rsa256_key.pem')
        key = le_util.Key("something", RSA256_KEY)
        chall1 = DvsniChall("foo.example.com", "whee", "foononce", key)
        chall2 = DvsniChall("bar.example.com", "whee", "barnonce", key)
        bad_chall = ("This", "Represents", "A Non-DVSNI", "Challenge")
        self.authenticator.start_listener = mock.Mock()
        self.authenticator.start_listener.return_value = True
        result = self.authenticator.perform([chall1, chall2, bad_chall])
        self.assertEqual(len(self.authenticator.tasks), 2)
        self.assertTrue(
            self.authenticator.tasks.has_key("foononce.acme.invalid"))
        self.assertTrue(
            self.authenticator.tasks.has_key("barnonce.acme.invalid"))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], dict)
        self.assertIsInstance(result[1], dict)
        self.assertFalse(result[2])
        self.assertTrue(result[0].has_key("s"))
        self.assertTrue(result[1].has_key("s"))
        self.authenticator.start_listener.assert_called_once_with(443, key)

    def test_cannot_perform(self):
        """What happens if start_listener() returns False."""
        from letsencrypt.client import le_util
        RSA256_KEY = pkg_resources.resource_string(__name__,
            'testdata/rsa256_key.pem')
        key = le_util.Key("something", RSA256_KEY)
        chall1 = DvsniChall("foo.example.com", "whee", "foononce", key)
        chall2 = DvsniChall("bar.example.com", "whee", "barnonce", key)
        bad_chall = ("This", "Represents", "A Non-DVSNI", "Challenge")
        self.authenticator.start_listener = mock.Mock()
        self.authenticator.start_listener.return_value = False
        result = self.authenticator.perform([chall1, chall2, bad_chall])
        self.assertEqual(len(self.authenticator.tasks), 2)
        self.assertTrue(
            self.authenticator.tasks.has_key("foononce.acme.invalid"))
        self.assertTrue(
            self.authenticator.tasks.has_key("barnonce.acme.invalid"))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertEqual(result, [None, None, False])
        self.authenticator.start_listener.assert_called_once_with(443, key)

class StartListenerTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        self.authenticator = StandaloneAuthenticator()

    @mock.patch("letsencrypt.client.standalone_authenticator.Crypto.Random.atfork")
    @mock.patch("letsencrypt.client.standalone_authenticator.os.fork")
    def test_start_listener_fork_parent(self, mock_fork, mock_atfork):
        self.authenticator.do_parent_process = mock.Mock()
        mock_fork.return_value = 22222
        self.authenticator.start_listener(1717, "key")
        self.assertEqual(self.authenticator.child_pid, 22222)
        self.authenticator.do_parent_process.assert_called_once_with(1717)
        mock_atfork.assert_called_once_with()

    @mock.patch("letsencrypt.client.standalone_authenticator.Crypto.Random.atfork")
    @mock.patch("letsencrypt.client.standalone_authenticator.os.fork")
    def test_start_listener_fork_child(self, mock_fork, mock_atfork):
        import os
        self.authenticator.do_parent_process = mock.Mock()
        self.authenticator.do_child_process = mock.Mock()
        mock_fork.return_value = 0
        self.authenticator.start_listener(1717, "key")
        self.assertEqual(self.authenticator.child_pid, os.getpid())
        self.authenticator.do_child_process.assert_called_once_with(1717,
            "key")
        mock_atfork.assert_called_once_with()

class DoParentProcessTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        self.authenticator = StandaloneAuthenticator()

    @mock.patch("letsencrypt.client.standalone_authenticator.signal.signal")
    @mock.patch("letsencrypt.client.standalone_authenticator.zope.component.getUtility")
    def test_do_parent_process_ok(self, mock_getUtility, mock_signal):
        self.authenticator.subproc_ready = True
        result = self.authenticator.do_parent_process(1717)
        self.assertTrue(result)
        self.assertEqual(mock_signal.call_count, 3)

    @mock.patch("letsencrypt.client.standalone_authenticator.signal.signal")
    @mock.patch("letsencrypt.client.standalone_authenticator.zope.component.getUtility")
    def test_do_parent_process_inuse(self, mock_getUtility, mock_signal):
        self.authenticator.subproc_inuse = True
        result = self.authenticator.do_parent_process(1717)
        self.assertFalse(result)
        self.assertEqual(mock_signal.call_count, 3)

    @mock.patch("letsencrypt.client.standalone_authenticator.signal.signal")
    @mock.patch("letsencrypt.client.standalone_authenticator.zope.component.getUtility")
    def test_do_parent_process_cantbind(self, mock_getUtility, mock_signal):
        self.authenticator.subproc_cantbind = True
        result = self.authenticator.do_parent_process(1717)
        self.assertFalse(result)
        self.assertEqual(mock_signal.call_count, 3)

    @mock.patch("letsencrypt.client.standalone_authenticator.signal.signal")
    @mock.patch("letsencrypt.client.standalone_authenticator.zope.component.getUtility")
    def test_do_parent_process_timeout(self, mock_getUtility, mock_signal):
        # Times out in 5 seconds and returns False.
        result = self.authenticator.do_parent_process(1717)
        self.assertFalse(result)
        self.assertEqual(mock_signal.call_count, 3)


class DoChildProcessTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        from letsencrypt.client.challenge_util import dvsni_gen_cert
        from letsencrypt.client import le_util
        import OpenSSL.crypto
        self.authenticator = StandaloneAuthenticator()
        r = "x" * 32
        name, r_b64 = "example.com", le_util.jose_b64encode(r)
        RSA256_KEY = pkg_resources.resource_string(__name__,
            'testdata/rsa256_key.pem')
        nonce, key = "abcdef", le_util.Key("foo", RSA256_KEY)
        self.key = key
        self.cert = dvsni_gen_cert(name, r_b64, nonce, key)[0]
        self.authenticator.private_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, key.pem)
        self.authenticator.tasks = {"abcdef.acme.invalid": self.cert}
        self.authenticator.parent_pid = 12345

    @mock.patch("letsencrypt.client.standalone_authenticator.socket.socket")
    @mock.patch("letsencrypt.client.standalone_authenticator.os.kill")
    @mock.patch("letsencrypt.client.standalone_authenticator.sys.exit")
    def test_do_child_process_cantbind1(self, mock_exit, mock_kill, mock_socket):
        import socket, signal
        mock_exit.side_effect = IndentationError("subprocess would exit here")
        eaccess = socket.error(socket.errno.EACCES, "Permission denied")
        sample_socket = mock.MagicMock()
        sample_socket.bind.side_effect = eaccess
        mock_socket.return_value = sample_socket
        # Using the IndentationError as an error that cannot easily be
        # generated at runtime, to indicate the behavior of sys.exit has
        # taken effect without actually causing the test process to exit.
        # (Just replacing it with a no-op causes logic errors because the
        # do_child_process code assumes that calling sys.exit() will
        # cause subsequent code not to be executed.)
        with self.assertRaises(IndentationError):
            result = self.authenticator.do_child_process(1717, self.key)
        mock_exit.assert_called_once_with(1)
        mock_kill.assert_called_once_with(12345, signal.SIGUSR2)

    @mock.patch("letsencrypt.client.standalone_authenticator.socket.socket")
    @mock.patch("letsencrypt.client.standalone_authenticator.os.kill")
    @mock.patch("letsencrypt.client.standalone_authenticator.sys.exit")
    def test_do_child_process_cantbind2(self, mock_exit, mock_kill, mock_socket):
        import socket, signal
        mock_exit.side_effect = IndentationError("subprocess would exit here")
        eaccess = socket.error(socket.errno.EADDRINUSE, "Port already in use")
        sample_socket = mock.MagicMock()
        sample_socket.bind.side_effect = eaccess
        mock_socket.return_value = sample_socket
        with self.assertRaises(IndentationError):
            result = self.authenticator.do_child_process(1717, self.key)
        mock_exit.assert_called_once_with(1)
        mock_kill.assert_called_once_with(12345, signal.SIGUSR1)

    @mock.patch("letsencrypt.client.standalone_authenticator.OpenSSL.SSL.Connection")
    @mock.patch("letsencrypt.client.standalone_authenticator.socket.socket")
    @mock.patch("letsencrypt.client.standalone_authenticator.os.kill")
    def test_do_child_process_success(self, mock_kill, mock_socket, mock_Connection):
        import socket, signal
        sample_socket = mock.MagicMock()
        sample_socket.accept.side_effect = ErrorAfter_socket_accept(2)
        mock_socket.return_value = sample_socket
        mock_Connection.return_value = mock.MagicMock()
        with self.assertRaises(CallableExhausted):
            result = self.authenticator.do_child_process(1717, self.key)
        mock_socket.assert_called_once_with()
        sample_socket.bind.assert_called_once_with(("0.0.0.0", 1717))
        sample_socket.listen.assert_called_once_with(1)
        self.assertEqual(sample_socket.accept.call_count, 3)
        mock_kill.assert_called_once_with(12345, signal.SIGIO)
        # TODO: We could have some tests about the fact that the listener
        #       asks OpenSSL to negotiate a TLS connection (and correctly
        #       sets the SNI callback function).


class CleanupTest(unittest.TestCase):
    def setUp(self):
        from letsencrypt.client.standalone_authenticator import \
            StandaloneAuthenticator
        self.authenticator = StandaloneAuthenticator()
        self.authenticator.tasks = {"foononce.acme.invalid": "stuff"}
        self.authenticator.child_pid = 12345

    @mock.patch("letsencrypt.client.standalone_authenticator.os.kill")
    @mock.patch("letsencrypt.client.standalone_authenticator.time.sleep")
    def test_cleanup(self, mock_sleep, mock_kill):
        import signal
        mock_sleep.return_value = None
        mock_kill.return_value = None
        chall = DvsniChall("foo.example.com", "whee", "foononce", "key")
        self.authenticator.cleanup([chall])
        mock_kill.assert_called_once_with(12345, signal.SIGINT)
        mock_sleep.assert_called_once_with(1)

    def test_bad_cleanup(self):
        chall = DvsniChall("bad.example.com", "whee", "badnonce", "key")
        with self.assertRaises(ValueError):
            self.authenticator.cleanup([chall])


if __name__ == '__main__':
    unittest.main()
