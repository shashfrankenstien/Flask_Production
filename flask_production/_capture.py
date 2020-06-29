'''
code derived from stdio_proxy package - https://github.com/bonprosoft/stdio_proxy

MIT License

Copyright (c) 2019 Yuki Igarashi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import _pyio
import threading
import sys



class _ThreadSafeTextIOWrapperProxy(_pyio.TextIOWrapper):  # type: ignore
    def __init__(self, *args, **kwargs):  # type: ignore
        self._local_objects = threading.local()
        super().__init__(*args, **kwargs)

    def register(self, new_buffer, no_close=True):
        # type: (BinaryIO, bool) -> None
        self._local_objects.buffer = new_buffer
        self._local_objects.no_close = no_close
        self._local_objects.registered = True

    def unregister(self):
        # type: () -> None
        self._local_objects.buffer = None
        self._local_objects.registered = False

    @property
    def _registered(self):
        # type: () -> bool
        return getattr(self._local_objects, "registered", False)

    @property
    def buffer(self):
        # type: () -> BinaryIO
        if not self._registered:
            return self._buffer

        buf = self._local_objects.buffer
        assert buf is not None
        return buf

    def close(self):
        # type: () -> None
        if self._registered and self._local_objects.no_close:
            self.buffer.flush()
        else:
            super().buffer.flush()

    def write(self, s):
        # type: (str) -> None
        return super().write(s)


def _create_proxy(target):
    # type: (TextIO) -> ThreadSafeTextIOWrapperProxy
    return _ThreadSafeTextIOWrapperProxy(
        target.buffer,
        target.encoding,
        getattr(target, "errors", "strict"),
        getattr(target, "newlines", None),
        getattr(target, "line_buffering", True),
    )



class _redirect_stdout(object):
    """Context manager for temporarily redirecting stdout to an object.

    Note:
        For Python 3 environments, ``dst_obj`` is supposed to handle ``bytes``, not ``str``.
        For Python 2 environments, ``str``, not ``unicode``.
        The easiest way to prepare ``dst_obj`` for both environments is to use an ``io.BytesIO`` object.

        For Python 3 environments, the interface of ``dst_obj`` should be compatible with that of ``io.BufferedWriter``.
        For instance, if you use `sys.stdin.readline`, ``dst_obj`` must have ``write`` method, ``flush`` method, and ``closed`` property.
        Note that the argument of ``write`` method is ``bytes``, not ``str``.

        For Python 2 environments, the interface of ``dst_obj`` should be compatible with that of the Python file object.

    Examples:
        >>> buf = io.BytesIO()
        >>> with redirect_stdout(buf):
        ...     sys.stdout.write("Foo\n")
        >>> print("Redirected: {}".format(buf.getvalue()))
        Redirected: b'Foo\n'

    """

    _lock = threading.Lock()
    _original = None  # type: Dict[str, SysIO]
    _proxy = None  # type: Dict[str, ProxyIO]
    _n_use = 0

    def __init__(self, new_obj):
        self._new_obj = new_obj

    def __enter__(self):
        with _redirect_stdout._lock:
            if _redirect_stdout._n_use == 0:
                if _redirect_stdout._original is None:
                    _redirect_stdout._original = getattr(sys, 'stdout')
                    _redirect_stdout._proxy = _create_proxy(_redirect_stdout._original)

                setattr(sys, 'stdout', _redirect_stdout._proxy)

            _redirect_stdout._n_use += 1
            _redirect_stdout._proxy.register(self._new_obj)

    def __exit__(self, exc_type, exc_val, exc_tb):
        _redirect_stdout._proxy.unregister()
        with _redirect_stdout._lock:
            _redirect_stdout._n_use -= 1

            if _redirect_stdout._n_use == 0:
                setattr(sys, 'stdout', _redirect_stdout._original)


'''
implementing print statement capture using the above thread safe stdout proxy
'''
# from stdio_proxy import redirect_stdout

class _PrintCapture(_pyio.BytesIO):
    '''File-like object that will be the destination of capture'''
    def __init__(self, callback):
        self._buf = b''
        self._write_cb = callback

    def write(self, b):
        self._buf += b
        if b.endswith(b'\n'):
            line = self._buf.decode(errors='ignore')
            self._write_cb(line)
            self._buf = b''

    def capture(self):
        return _redirect_stdout(self)


def print_capture(callback):
    return _PrintCapture(callback).capture()
