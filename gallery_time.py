import os
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

class Gallery():
    def __init__(self):
        print("Program Start")
        self.base_path = "/home/filipe/Pictures/Fotos"
        self.images = []
        self.load_images()

    def is_valid(self, file):
        return file[0:2] == "20" and file[-1] != "4"

    def get_year(self, file):
        return int(file[:4])

    def get_month(self, file):
        return int(file[5:7])

    def load_images(self):
        print("Loading Images\n")
        for _, _, files in  os.walk(self.base_path):
            for file in files:
                if self.is_valid(file): 
                    self.images.append(file)
        self.images.sort()

    def get_full_path(self, file):
        year = file[2:4]
        month = file[5:7]
        relative_path = year + '/' + year + month + '/'
        return os.path.join(self.base_path, relative_path, file)

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
        current_year = gallery.get_year(gallery.images[0]) 
        current_month = gallery.get_month(gallery.images[0])
        image_box, _ = self.new_year_month(main_box, None, gallery.images[0])

        for image in gallery.images:
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

            image_path = gallery.get_full_path(image)
            image_widget = Gtk.Image.new_from_file(image_path)
            image_widget.get_style_context().add_class("image")
            image_box.insert(image_widget, -1)

    def new_year_month(self, main_box, year_box, image):
        if not year_box:
            year_box = self.display_year(Gallery.get_year(None, image)) 
            main_box.append(year_box)

        month_box = self.display_month(Gallery.get_month(None, image))
        image_box = self.create_image_box()
        year_box.append(month_box)
        month_box.append(image_box)
        return image_box, year_box

    def create_image_box(self):
        image_box = Gtk.FlowBox()
        image_box.set_max_children_per_line(3)
        image_box.set_selection_mode(Gtk.SelectionMode.NONE)
        return image_box 

    def display_year(self, year):
        year_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        year_label = Gtk.Label(label=str(year))
        year_label.set_markup(f"<b>{year}</b>")
        year_box.append(year_label)
        return year_box

    def display_month(self, month):
        month_name = month_names[month] 
        month_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        month_label = Gtk.Label(label=f"{month_name}")
        month_label.set_markup(f"<i>{month_name}</i>")
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
