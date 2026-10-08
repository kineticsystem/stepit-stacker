"""Shows an image full-screen, pixel for pixel, on the monitor of its size: python3 -m pipeline.viewer image width height.

display.show() runs it, in a process of its own, until the next hologram
replaces it. It says "Showing" once its window covers that monitor exactly.
"""

import sys

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GdkX11, GLib, Gtk  # noqa: E402, F401 - GdkX11 gives get_xid()

from .window import fullscreen_on  # noqa: E402

WAIT_MS = 10000


def main(path, width, height):
    display = Gdk.Display.get_default()
    monitors = [display.get_monitor(i).get_geometry() for i in range(display.get_n_monitors())]
    target = next((m for m in monitors if (m.width, m.height) == (width, height)), None)
    if target is None:
        sizes = ", ".join(f"{m.width} x {m.height}" for m in monitors)
        print(f"No monitor of {width} x {height}, only {sizes}: is the Looking Glass on HDMI and on?", flush=True)
        return 1

    window = Gtk.Window(title="StepIt Stacker")
    window.add(Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file(path)))
    window.connect("destroy", Gtk.main_quit)
    window.connect("map-event", lambda *_: fullscreen_on(window.get_window().get_xid(), target.x, target.y))
    waited = [0]

    def check():
        x, y = window.get_window().get_origin()[1:]
        if (x, y, window.get_allocated_width(), window.get_allocated_height()) == (target.x, target.y, width, height):
            print(f"Showing {path} on the monitor at {target.x}, {target.y}", flush=True)
            return False
        waited[0] += 200
        if waited[0] >= WAIT_MS:
            print(f"The window did not go full-screen on the monitor at {target.x}, {target.y}", flush=True)
            Gtk.main_quit()
            return False
        return True

    window.show_all()
    window.get_window().set_cursor(Gdk.Cursor.new_for_display(display, Gdk.CursorType.BLANK_CURSOR))
    GLib.timeout_add(200, check)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
