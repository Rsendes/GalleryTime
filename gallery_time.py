import os
import gi
import numpy as np
from PIL import Image, ImageOps, ExifTags

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gdk

MONTH_NAMES = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December'
}

BASE_PATH = "/home/filipe/Pictures/Fotos"
THUMBNAILS_PATH = BASE_PATH + "/Thumbnails"
IGNORE_PATH = "Thumbnails"

THUMBNAIL_SIZE = (300, 300)

class Gallery():
    def __init__(self):
        self.images = []
        self.thumbnails = []
        self.load_images()
        self.load_thumbnails()
        self.create_thumbnails()

    def is_valid(self, file):
        return file[0:2] == "20" and file[-1] != "4" and file[-3] != "3"

    def get_year(self, file):
        return int(file[:4])

    def get_month(self, file):
        return int(file[5:7])

    def load_images(self):
        print("Loading Images\n")
        for root, dirs, files in  os.walk(BASE_PATH):
            if os.path.basename(root) == IGNORE_PATH:
                continue  
            for file in files:
                if self.is_valid(file): 
                    self.images.append(file)
        self.images.sort()

    def load_thumbnails(self):
        print("Loading Thumbnails\n")
        for _, _, files in  os.walk(THUMBNAILS_PATH):
            for file in files:
                self.thumbnails.append(file)
        self.thumbnails.sort(reverse=True)

    def create_thumbnails(self):
        if len(self.images) > len(self.thumbnails):
            print("Creating Thumbnails")
            for image in self.images:
                if image not in self.thumbnails:
                    self.create_thumbnail(image)
            self.thumbnails.sort(reverse=True)

    def create_thumbnail(self, image):
        print("Creating thumbnail " + image)
        full_path = self.get_full_path(image)
        img = Image.open(full_path)
        exif = img._getexif()

        if exif:
            orientation = exif.get(274)  # 274 is the Orientation tag
            if orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
            elif orientation == 3:
                img = img.rotate(180, expand=True)

        cropped_thumbnail = ImageOps.fit(img, THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        thumbnail_path = os.path.join(THUMBNAILS_PATH, image)
        cropped_thumbnail.save(thumbnail_path)
        self.thumbnails.append(image)

    def get_full_path(self, file):
        year = file[2:4]
        month = file[5:7]
        relative_path = year + '/' + year + month + '/'
        return os.path.join(BASE_PATH, relative_path, file)

    def get_thumbnail_path(self, file):
        return os.path.join(THUMBNAILS_PATH, file)


class App(Gtk.Application):
    def __init__(self):
        super().__init__()
        GLib.set_application_name("Gallery Time")
        self.gallery = Gallery()

    def do_activate(self):
        """Called when the application is activated."""
        window = MainWindow(self, self.gallery)
        window.present()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app, gallery):
        super().__init__(application=app)
        self.set_title("Gallery Time")
        self.set_default_size(800, 600)

        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        self.set_titlebar(header)

        # Load CSS
        self.load_css()

        # Scroll and main container
        scroll = Gtk.ScrolledWindow()
        self.set_child(scroll)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scroll.set_child(main_box)

        # First Year and Month
        current_year = gallery.get_year(gallery.thumbnails[0]) 
        current_month = gallery.get_month(gallery.thumbnails[0])
        image_box, year_box = self.new_year_month(main_box, None, gallery.thumbnails[0])

        for image in gallery.thumbnails:
            image_year = gallery.get_year(image)
            image_month = gallery.get_month(image)

            # The year changes
            if current_year != image_year:
                current_year = image_year
                image_box, year_box = self.new_year_month(main_box, None, image) 
            
            # Only the month changes
            elif current_month != image_month:
                current_month = image_month
                image_box, _ = self.new_year_month(main_box, year_box, image)

            image_path = gallery.get_thumbnail_path(image)
            image_widget = Gtk.Image.new_from_file(image_path)
            image_widget.get_style_context().add_class("image")
            image_box.insert(image_widget, -1)

    def new_year_month(self, main_box, year_box, image):
        year = Gallery.get_year(None, image)
        month = Gallery.get_month(None, image)

        if not year_box:
            year_box = self.display_year(year) 
            main_box.append(year_box)

        month_box = self.display_month(month, year)
        image_box = self.create_image_box()
        year_box.append(month_box)
        month_box.append(image_box)
        return image_box, year_box

    def create_image_box(self):
        image_box = Gtk.FlowBox()
        image_box.set_max_children_per_line(5)
        image_box.set_selection_mode(Gtk.SelectionMode.NONE)
        return image_box 

    def display_year(self, year):
        year_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=50)
        year_label = Gtk.Label(label=str(year))
        year_label.set_markup(f"<b><span size='20000'>-{year}-</span></b>")
        year_box.append(year_label)
        return year_box

    def display_month(self, month, year):
        month_name = MONTH_NAMES[month] 
        month_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=25)
        month_label = Gtk.Label(label=f"{month_name} {year}")
        #month_box.set_margin_start(100)
        month_label.set_markup(f"<b><span size='15000'>{month_name} {year}</span></b>")
        #month_label.set_xalign(0)
        month_box.append(month_label)
        return month_box

    def load_css(self):
        """Load CSS if available."""
        css_path = "style.css"
        if os.path.exists(css_path):
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        else:
            print("Warning: CSS file not found.")


if __name__ == "__main__":
    app = App()
    app.run()
