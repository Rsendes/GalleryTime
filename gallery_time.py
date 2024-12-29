import os
import re
import sys
import gi

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
        super().__init__(application_id="com.example.GalleryTime")
        GLib.set_application_name('Gallery Time')
        self.base_path = base_path
        self.images = []
        self.images_by_date = {} 
        self.load_images()
        self.store_images_by_date()

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
    
    def store_images_by_date(self):
        print("Storing Images")
        for image in self.images:
            year = self.get_year(image)
            if year not in self.images_by_date:
                self.images_by_date[year] = {}
            month = self.get_month(image)
            if month not in self.images_by_date[year]:
                self.images_by_date[year][month] = []
            self.images_by_date[year][month].append(image)

    def load_image(self, image_path):
        try:
            image_widget = Gtk.Image.new_from_file(image_path)
            image_widget.get_style_context().add_class("image")
            return image_widget
        except Exception as e:
            print(f"Failed to load image {image_path}: {e}")
            return None

    def do_activate(self):
        window = Gtk.ApplicationWindow(application=self)
        window.set_title("Gallery Time")
        window.set_default_size(800,600)

        #Header
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        window.set_titlebar(header)

        # Load CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path("style.css")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), 
            css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        #Scroll and main container
        scroll = Gtk.ScrolledWindow()
        window.set_child(scroll)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scroll.set_child(main_box)
 
        for year, months in self.images_by_date.items():
            year_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            year_label = Gtk.Label(label=str(year))
            year_label.set_markup(f"<b>{year}</b>")
            year_box.append(year_label)

            for month, images in months.items():
                month_name = month_names[month] 
                month_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                month_label = Gtk.Label(label=f"{month_name}")
                month_label.set_markup(f"<i>{month_name}</i>")
                month_box.append(month_label)

                image_box = Gtk.FlowBox()
                image_box.set_max_children_per_line(3)
                image_box.set_selection_mode(Gtk.SelectionMode.NONE)

                for image in images:
                    relative_path = self.get_relative_path(image)
                    image_path = os.path.join(self.base_path, relative_path ,image)
                    image_widget = self.load_image(image_path)
                        if image_widget:
                            image_box.insert(image_widget, -1)

                month_box.append(image_box)
                year_box.append(month_box)
            main_box.append(year_box)
        window.present()


if __name__ == "__main__":
    photo_directory = "/home/filipe/Pictures/Fotos/"
    app = GalleryTime(photo_directory)
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

