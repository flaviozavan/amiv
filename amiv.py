#! /usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf
import sys
import argparse
import tomllib
import os
import platformdirs

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.main_box)

        self.image_area = Gtk.DrawingArea()
        self.image_area.set_hexpand(True)
        self.image_area.set_vexpand(True)
        self.main_box.append(self.image_area)

        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.status_box.set_margin_start(8)
        self.status_box.set_margin_end(8)
        self.main_box.append(self.status_box)

        self.file_label = Gtk.Label(label="No file")
        self.file_label.set_xalign(0)
        self.file_label.set_hexpand(True)
        self.file_label.set_ellipsize(Pango.EllipsizeMode.START)
        self.status_box.append(self.file_label)

        self.status_separator = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL)
        self.status_separator.set_margin_start(32)
        self.status_box.append(self.status_separator)

        self.zoom_label = Gtk.Label()
        self.zoom_label.set_xalign(1)
        self.status_box.append(self.zoom_label)
        self.set_zoom(1)

        self.status_separator = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL)
        self.status_separator.set_margin_start(8)
        self.status_box.append(self.status_separator)

        self.navigation_label = Gtk.Label()
        self.navigation_label.set_xalign(1)
        self.status_box.append(self.navigation_label)
        self.current_file_index = 0
        self.total_files = 0
        self.update_navigation_label()


    def set_zoom(self, zoom):
        zoom = int(round(100*zoom))
        self.zoom_label.set_label(f"{zoom}%")

    def set_total_files(self, total_files):
        self.total_files = total_files
        self.update_navigation_label()

    def set_current_file_index(self, current_file_index):
        self.current_file_index = current_file_index
        self.update_navigation_label()

    def update_navigation_label(self):
        self.navigation_label.set_label(
            f"{self.current_file_index}/{self.total_files}")

    def set_file_label(self, value):
        self.file_label.set_label(value)

    def set_image_area_draw_function(self, function):
        self.image_area.set_draw_func(function)

    def connect_image_area_signal(self, signal, callback):
        self.image_area.connect(signal, callback)

    def queue_draw_image(self):
        self.image_area.queue_draw()


class AmivApp(Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)

    def create_key_map(self):
        possible_key_bindings = {
            "toggle_fullscreen": self.toggle_fullscreen,
            "zoom_in": lambda: self.adjust_zoom(1.1),
            "zoom_out": lambda: self.adjust_zoom(.9),
            "zoom_100": lambda: self.set_zoom(1),
            "fit_to_window": self.set_fit_to_window,
            "rotate_cw": lambda: self.rotate(270),
            "rotate_ccw": lambda: self.rotate(90),
        }

        self.key_map = {}
        for function, key in self.config["keys"].items():
            if function in possible_key_bindings:
                keyval = Gdk.keyval_from_name(key)
                self.key_map[keyval] = possible_key_bindings[function]

    def get_default_config_file_path(self):
        return os.path.join(platformdirs.user_config_dir(),
            "amiv",
            "config.toml")

    def recursive_merge_config(self, new, old):
        if type(new) is not dict or type(old) is not dict:
            return

        for key, val in old.items():
            if key not in new:
                new[key] = val
            else:
                self.recursive_merge_config(new[key], old[key])

    def load_config(self, config_file_path):
        try:
            with open(config_file_path, "rb") as f:
                data = tomllib.load(f)
        except FileNotFoundError:
            data = {}

        self.recursive_merge_config(data, self.get_default_config())
        return data

    def get_default_config(self):
        return {
            "gui": {
                "dark_theme": True,
                "scaling": "bilinear",
                "inhibit_idle_on_fullscreen": True,
            },
            "keys": {
                "toggle_fullscreen": "f",
                "fit_to_window": "W",
                "zoom_in": "plus",
                "zoom_out": "minus",
                "zoom_100": "equal",
                "rotate_cw": "greater",
                "rotate_ccw": "less",
            },
        }

    def get_scaling_from_config(self):
        scaling_types = {
            "nearest": GdkPixbuf.InterpType.NEAREST,
            "tiles": GdkPixbuf.InterpType.TILES,
            "bilinear": GdkPixbuf.InterpType.BILINEAR,
            "hyper": GdkPixbuf.InterpType.HYPER,
        }
        return scaling_types[self.config["gui"]["scaling"]]

    def run(self, argv, **kwargs):
        parser = argparse.ArgumentParser(prog=argv[0])
        parser.add_argument("images", nargs="*")
        parser.add_argument("-c",
            "--config",
            default=self.get_default_config_file_path())
        parser.add_argument("-f",
            "--fullscreen",
            action="store_true")
        self.args = parser.parse_args(args=argv[1:])

        self.config = self.load_config(self.args.config)
        self.scaling = self.get_scaling_from_config()
        self.create_key_map()

        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme",
            self.config["gui"]["dark_theme"])

        self.fit_image = True
        self.image = None
        self.zoom = -1
        self.image_area_width = 0
        self.image_area_height = 0
        self.x = 0
        self.y = 0

        super().run(**kwargs)

    def on_activate(self, app):
        self.win = MainWindow(application=app)

        if self.config["gui"]["inhibit_idle_on_fullscreen"]:
            self.win.connect("notify::fullscreened", self.update_idle_inhibit)

        eck = Gtk.EventControllerKey.new()
        eck.connect("key-pressed", self.handle_key)
        self.win.add_controller(eck)

        ecs = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL |
            Gtk.EventControllerScrollFlags.DISCRETE)
        ecs.connect("scroll", self.handle_scroll)
        self.win.add_controller(ecs)

        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self.handle_drag_begin)
        drag.connect("drag-update", self.handle_drag_update)
        self.win.add_controller(drag)

        if self.args.fullscreen:
            self.set_fullscreen_once_signal_id = self.win.connect(
                "notify::is-active",
                self.set_fullscreen_once)
        self.win.set_image_area_draw_function(self.draw_image)
        self.win.connect_image_area_signal("resize", self.handle_resize)
        self.win.present()

        if self.args.images:
            self.load_image(self.args.images[0])

    def load_image(self, image_path):
        self.image = GdkPixbuf.Pixbuf.new_from_file(image_path)
        self.win.set_file_label(image_path)
        self.x = self.image.get_width()/2
        self.y = self.image.get_height()/2
        self.last_zoom = -1

        self.win.set_total_files(1)
        self.win.set_current_file_index(1)

    def toggle_fullscreen(self):
        if self.win.is_fullscreen():
            self.win.unfullscreen()
        else:
            self.win.fullscreen()

    def handle_key(self, event, keyval, keycode, state):
        if keyval in self.key_map:
            self.key_map[keyval]()

    def set_fullscreen_once(self, win, prop):
        self.win.fullscreen()
        self.win.disconnect(self.set_fullscreen_once_signal_id)

    def fit_to_window(self):
        possibilities = [
            self.image_area_width/self.image.get_width(),
            self.image_area_height/self.image.get_height(),
        ]
        self.update_zoom(min(possibilities))

    def set_fit_to_window(self):
        self.fit_image = True
        self.fit_to_window()
        self.win.queue_draw_image()

    def handle_resize(self, image_area, width, height):
        self.image_area_width = width
        self.image_area_height = height
        if not width or not height or not self.image or not self.fit_image:
            return

        self.fit_to_window()

    def handle_drag_begin(self, drag, x, y):
        self.drag_start_x = self.x
        self.drag_start_y = self.y

    def handle_drag_update(self, drag, x, y):
        if self.fit_image:
            return

        new_x = self.drag_start_x-(x/self.zoom)
        new_y = self.drag_start_y-(y/self.zoom)

        self.set_center_pos(new_x, new_y)
        self.win.queue_draw_image()

    def set_center_pos(self, new_x, new_y):
        new_x = max(self.image_area_width/self.zoom/2,
            min(new_x,
                self.image.get_width()-self.image_area_width/self.zoom/2))
        new_y = max(self.image_area_height/self.zoom/2,
            min(new_y,
                self.image.get_height()-self.image_area_height/self.zoom/2))
        self.x = new_x
        self.y = new_y

    def adjust_zoom(self, ratio):
        self.update_zoom(self.zoom*ratio)

    def set_zoom(self, val):
        self.fit_image = False
        self.update_zoom(val)

    def update_zoom(self, val):
        self.zoom = min(max(val, .1), 8)
        self.win.set_zoom(self.zoom)
        self.set_center_pos(self.x, self.y)
        self.win.queue_draw_image()

    def handle_scroll(self, ecs, dx, dy):
        self.adjust_zoom(1-(dy*.1))

    def rotate(self, angle):
        self.image = self.image.rotate_simple(angle)
        self.last_zoom = -1
        if self.fit_image:
            self.fit_to_window()
        else:
            self.set_center_pos(self.x, self.y)
        self.win.queue_draw_image()

    def update_idle_inhibit(self, win, fullscreened):
        if win.is_fullscreen():
            self.inhibit(self.win,
                Gtk.ApplicationInhibitFlags.IDLE,
                "fullscreen")
        else:
            self.inhibit(self.win, 0, None)

    def draw_image(self, area, cr, width, height):
        if not width or not height or not self.image or self.zoom <= 0:
            return

        if self.zoom != self.last_zoom:
            new_width = self.image.get_width() * self.zoom
            new_height = self.image.get_height() * self.zoom
            self.scaled_buf = self.image.scale_simple(new_width,
                new_height,
                self.scaling)

            self.last_zoom = self.zoom

        sx = max(0, int(self.x * self.zoom - width/2))
        sy = max(0, int(self.y * self.zoom - height/2))
        vw = min(self.scaled_buf.get_width() - sx, width)
        vh = min(self.scaled_buf.get_height() - sy, height)
        subbuf = self.scaled_buf.new_subpixbuf(sx, sy, vw, vh)

        cx = int(width/2 - subbuf.get_width()/2)
        cy = int(height/2 - subbuf.get_height()/2)
        Gdk.cairo_set_source_pixbuf(cr, subbuf, cx, cy)

        cr.paint()

app = AmivApp()
app.run(sys.argv)
