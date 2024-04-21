#! /usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf, GLib
import sys
import argparse
import tomllib
import os
import platformdirs
import mimetypes
import random

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

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_margin_start(32)
        self.status_box.append(separator)

        self.delay_label = Gtk.Label()
        self.delay_label.set_xalign(1)
        self.status_box.append(self.delay_label)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_margin_start(8)
        self.status_box.append(separator)

        self.zoom_label = Gtk.Label()
        self.zoom_label.set_xalign(1)
        self.status_box.append(self.zoom_label)
        self.set_zoom(1)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_margin_start(8)
        self.status_box.append(separator)

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

    def set_delay_label(self, delay_type, seconds):
        if seconds:
            self.delay_label.set_label(f"{delay_type} {seconds}s")
        else:
            self.delay_label.set_label("")


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
            "next": lambda: self.skip(1),
            "previous": lambda: self.skip(-1),
            "delay_up": lambda: self.adjust_delay(1),
            "delay_down": lambda: self.adjust_delay(-1),
            "next_dir": lambda: self.skip_dir(1),
            "previous_dir": lambda: self.skip_dir(-1),
        }

        self.key_map = {}
        for function, keys in self.config["keys"].items():
            if function in possible_key_bindings:
                for key in keys.split(","):
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
            "general": {
                "load_directory": True,
                "filter_extensions": True,
            },
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
                "next": "Right",
                "previous": "Left",
                "delay_up": "Up",
                "delay_down": "Down",
                "next_dir": "Page_Up,End",
                "previous_dir": "Page_Down,Home",
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
        parser.add_argument("-r",
            "-R",
            "--recursive",
            action="store_true")
        parser.add_argument("--ignore-links",
            action="store_true")
        self.args = parser.parse_args(args=argv[1:])

        self.config = self.load_config(self.args.config)
        self.scaling = self.get_scaling_from_config()
        self.create_key_map()

        self.images, self.first_image_index = self.compile_image_list()

        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme",
            self.config["gui"]["dark_theme"])

        self.fit_image = True
        self.image = None
        self.frame = None
        self.zoom = -1
        self.image_area_width = 0
        self.image_area_height = 0
        self.x = 0
        self.y = 0
        self.delay = 0
        self.timeout_source = None
        self.animation_source = None

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

        self.win.set_total_files(len(self.images))
        self.current_image = -1
        self.skip(self.first_image_index+1)

    def compile_image_list(self):
        if not self.config["general"]["load_directory"]:
            return self.args.images

        images = []
        first_filename = None
        visited = set()
        for path in self.args.images:
            triggering_filename = None
            path = path.rstrip(os.path.sep)
            if not os.path.isdir(path):
                if not os.path.isfile(path):
                    continue
                triggering_filename = path
                path = os.path.split(path)[0]
                if not path:
                    path = "."
                    triggering_filename = os.path.join(".",
                        triggering_filename)


            new_images = []
            for dirpath, _, filenames in \
                os.walk(path, followlinks=not self.args.ignore_links):

                if dirpath in visited:
                    continue
                visited.add(dirpath)

                for entry in filenames:
                    mimetype = mimetypes.guess_type(entry)[0]
                    if not self.config["general"]["filter_extensions"] or \
                        (mimetype and mimetype.startswith("image/")):

                        filepath = os.path.join(dirpath, entry)
                        if first_filename is None and \
                            filepath == triggering_filename:
                            first_filename = filepath

                        new_images.append(filepath)

                if not self.args.recursive:
                    break

            images += sorted(new_images,
                key=lambda x: (x.count(os.path.sep), x))

        if first_filename is None:
            first_image_index = 0
        else:
            first_image_index = images.index(first_filename)

        return images, first_image_index

    def load_image(self):
        if not self.images:
            self.image = None
            self.win.set_current_file_index(0)
            self.win.set_file_label("No image")
            return True

        image_path = self.images[self.current_image]
        try:
            self.image = GdkPixbuf.PixbufAnimation.new_from_file(image_path)
        except GLib.GError:
            return False

        if self.animation_source is not None:
            GLib.source_remove(self.animation_source)
            self.animation_source = None
        self.image_it = self.image.get_iter(None)
        self.get_next_frame(False)

        self.win.set_file_label(image_path)
        self.win.set_current_file_index(self.current_image+1)
        self.x = self.frame.get_width()/2
        self.y = self.frame.get_height()/2

        if self.fit_image:
            self.fit_to_window()

        return True

    def get_next_frame(self, display):
        self.image_it.advance()
        self.frame = self.image_it.get_pixbuf()
        self.last_zoom = -1
        delay_to_next = self.image_it.get_delay_time()

        if delay_to_next != -1:
            self.animation_source = GLib.timeout_add(
                delay_to_next,
                self.get_next_frame,
                True)
        else:
            self.animation_source = None

        if display:
            self.win.queue_draw_image()

        return GLib.SOURCE_REMOVE

    def skip(self, count, try_multiple=True):
        initial_image = self.current_image

        ok = False
        while not ok:
            if not self.images:
                self.current_image = -1
            else:
                self.current_image = \
                    (initial_image+count) % len(self.images)

            if self.current_image == initial_image or self.load_image():
                ok = True
            else:
                self.images.pop(self.current_image)
                self.win.set_total_files(len(self.images))
                if self.current_image < initial_image:
                    initial_image -= 1

            if not try_multiple:
                break

        if ok:
            self.win.queue_draw_image()
        else:
            self.current_image = initial_image

        return ok

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
            self.image_area_width/self.frame.get_width(),
            self.image_area_height/self.frame.get_height(),
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
                self.frame.get_width()-self.image_area_width/self.zoom/2))
        new_y = max(self.image_area_height/self.zoom/2,
            min(new_y,
                self.frame.get_height()-self.image_area_height/self.zoom/2))
        self.x = new_x
        self.y = new_y

    def adjust_zoom(self, ratio):
        self.fit_image = False
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
        self.frame= self.frame.rotate_simple(angle)
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
        if not width or not height or not self.frame or self.zoom <= 0:
            return

        if self.zoom != self.last_zoom:
            new_width = self.frame.get_width() * self.zoom
            new_height = self.frame.get_height() * self.zoom
            self.scaled_buf = self.frame.scale_simple(new_width,
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

    def skip_dir(self, count):
        step = 1 if count > 0 else -1
        diff = 0
        starting_image = self.current_image
        for _ in range(abs(count)):
            for i in range(1, len(self.images)):
                candidate = (starting_image + step*i) % len(self.images)
                candidate_dir = os.path.split(self.images[candidate])[0]
                dir_before_candidate = os.path.split(
                    self.images[(candidate-1) % len(self.images)])[0]
                if candidate_dir != dir_before_candidate:
                    diff += step*i
                    starting_image = candidate
                    break
        self.skip(diff)

    def advance_slideshow(self, random_next):
        if not random_next:
            self.skip(1)
        else:
            # Manual retry, ensuring we never skip to the same image
            ok = False
            while not ok and len(self.images) > 1:
                ok = self.skip(random.randint(1, len(self.images)-1), False)

        return GLib.SOURCE_CONTINUE

    def adjust_delay(self, step):
        self.delay += step

        if self.timeout_source is not None:
            GLib.source_remove(self.timeout_source)
            self.timeout_source = None

        if self.delay:
            self.timeout_source = GLib.timeout_add_seconds(
                abs(self.delay),
                self.advance_slideshow,
                self.delay > 0)

        if not self.delay:
            self.win.set_delay_label("", 0)
        elif self.delay > 0:
            self.win.set_delay_label("Random", self.delay)
        else:
            self.win.set_delay_label("Sequential", abs(self.delay))


app = AmivApp()
app.run(sys.argv)
