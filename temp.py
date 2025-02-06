import os
import re
import sys
import gi
import time
import signal 


gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gdk

month_names = {
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

class GalleryTime(Gtk.Application):
    def __init__(self, base_path):
        print("Program Start\n")
        super().__init__()
        GLib.set_application_name('Gallery Time')
        self.base_path = base_path
        self.images = []
        self.images_by_date = {} 
        self.cont = 0
        self.temp = False
        self.load_images()

    def get_year(self, file):
        return int(file[:4])

    def get_month(self, file):
        return int(file[5:7])

    def is_valid(self, file):
        return file[0:2] == "20" and file[-1] != "4"

    def get_relative_path(self, file):
        year = file[2:4]
        month = file[5:7]
        return year + '/' + year + month + '/'

    def load_images(self):
        print("Loading Images\n")
        for _, _, files in  os.walk(self.base_path):
            for file in files:
                if self.is_valid(file): 
                    self.images.append(file)
        self.images.sort()
    
    def load_image(self, image_path):
        try:
            image_widget = Gtk.Image.new_from_file(image_path)
            image_widget.get_style_context().add_class("image")
            return image_widget
        except Exception as e:
            print(f"Failed to load image {image_path}: {e}")
            return None

    def display_year(self, year, main_box, window):
        year_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        year_label = Gtk.Label(label=str(year))
        year_label.set_markup(f"<b>{year}</b>")
        year_box.append(year_label)
        main_box.append(year_box)
        window.present()

    def display_month(self, month, main_box, window):
        month_name = month_names[month] 
        month_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        month_label = Gtk.Label(label=f"{month_name}")
        month_label.set_markup(f"<i>{month_name}</i>")
        month_box.append(month_label)
        main_box.append(month_box)
        window.present()

 
    def do_activate(self):
        window = Gtk.ApplicationWindow(application=self)
        window.set_title("Gallery Time")
        window.set_default_size(800, 600)

        # Handle window close event
        window.connect("destroy", self.quit_application)

        # Header
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        window.set_titlebar(header)

        # Load CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path("style.css")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Scroll and main container
        scroll = Gtk.ScrolledWindow()
        window.set_child(scroll)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scroll.set_child(main_box)

        # Initialize current year and month
        self.current_year = self.get_year(self.images[0])
        self.current_month = self.get_month(self.images[0])

        # Start incremental processing
        self.stop_processing = False  # Add flag for stopping
        GLib.idle_add(self.process_images, self.images.copy(), main_box, window)

        window.present()

    def quit_application(self, *args):
        """ Gracefully quit the application """
        print("Quitting application...")
        self.stop_processing = True  # Stop processing loop
        self.quit()  # Quit the application
        sys.exit(0)


    def process_images(self, image_list, main_box, window):
        """ Process images one by one with delay """
        if self.stop_processing or not image_list:
            return False  # Stop if requested

        # Get next image
        image = image_list.pop(0)

        # Process the image
        image_year = self.get_year(image)
        image_month = self.get_month(image)

        if image_year != self.current_year:
            self.current_year = image_year
            self.display_year(self.current_year, main_box, window)

        if image_month != self.current_month:
            self.current_month = image_month
            self.display_month(self.current_month, main_box, window)

        time.sleep(0.1)

        GLib.idle_add(self.process_images, image_list, main_box, window)
        return False

if __name__ == "__main__":
    # Handle SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Run application
    photo_directory = "/home/filipe/Pictures/Fotos/"
    app = GalleryTime(photo_directory)
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

