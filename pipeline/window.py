"""Makes a window fullscreen on one monitor, through libX11 and libXinerama, with ctypes.

GNOME's window manager places a new window on the main monitor and ignores a
request to move it. It does make a window fullscreen on a given monitor when
asked as a pager would be, with the EWMH messages _NET_WM_FULLSCREEN_MONITORS
and _NET_WM_STATE; GTK's own fullscreen_on_monitor() is ignored.
"""

import ctypes
import ctypes.util

CLIENT_MESSAGE = 33
# SubstructureRedirectMask | SubstructureNotifyMask: how a message reaches the window manager.
TO_WINDOW_MANAGER = (1 << 20) | (1 << 19)
ADD = 1
FROM_PAGER = 2


class _ClientMessage(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int), ("data", ctypes.c_long * 5)]


class _Event(ctypes.Union):
    _fields_ = [("xclient", _ClientMessage), ("pad", ctypes.c_long * 24)]


class _ScreenInfo(ctypes.Structure):
    _fields_ = [("screen_number", ctypes.c_int), ("x_org", ctypes.c_short), ("y_org", ctypes.c_short),
                ("width", ctypes.c_short), ("height", ctypes.c_short)]


def _libraries():
    x11 = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")
    xinerama = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Xinerama") or "libXinerama.so.1")
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xinerama.XineramaQueryScreens.restype = ctypes.POINTER(_ScreenInfo)
    xinerama.XineramaQueryScreens.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    return x11, xinerama


def _monitor_at(xinerama, display, x, y):
    """The number of the Xinerama screen whose top left corner is at x, y, or None."""
    count = ctypes.c_int()
    screens = xinerama.XineramaQueryScreens(display, ctypes.byref(count))
    for i in range(count.value if screens else 0):
        if (screens[i].x_org, screens[i].y_org) == (x, y):
            return screens[i].screen_number
    return None


def _send(x11, display, window, message, data):
    event = _Event()
    event.xclient.type = CLIENT_MESSAGE
    event.xclient.send_event = 1
    event.xclient.display = display
    event.xclient.window = window
    event.xclient.message_type = x11.XInternAtom(display, message, 0)
    event.xclient.format = 32
    for i, value in enumerate(data):
        event.xclient.data[i] = value
    x11.XSendEvent(display, x11.XDefaultRootWindow(display), 0, TO_WINDOW_MANAGER, ctypes.byref(event))


def fullscreen_on(window, x, y):
    """Asks the window manager to make the X window `window` fullscreen on the monitor whose top left corner
    is at x, y. Raises RuntimeError if there is no such monitor."""
    x11, xinerama = _libraries()
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("cannot open the X display")
    try:
        monitor = _monitor_at(xinerama, display, x, y)
        if monitor is None:
            raise RuntimeError(f"no monitor at {x}, {y}")
        _send(x11, display, window, b"_NET_WM_FULLSCREEN_MONITORS", [monitor, monitor, monitor, monitor, FROM_PAGER])
        _send(x11, display, window, b"_NET_WM_STATE",
              [ADD, x11.XInternAtom(display, b"_NET_WM_STATE_FULLSCREEN", 0), 0, FROM_PAGER])
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)
