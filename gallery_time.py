import os
import gi
import subprocess
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
ICONS_PATH = os.path.join(os.path.dirname(__file__), "icons")  # Add this line

THUMBNAIL_SIZE = (300, 300)

SCROLL_OFFSET = 60

class Gallery():
    def __init__(self):
        self.images = []
        self.thumbnails = []
        self.load_images()
        self.load_thumbnails()
        self.create_thumbnails()

    def is_valid(self, file):
        return file[0:2] == "20" and file[-3] != "3"

    def get_year(self, file):
        return int(file[:4])

    def get_month(self, file):
        return int(file[4:6])

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
                name, ext = os.path.splitext(image)
                # Check for both regular image and video thumbnail
                thumbnail_exists = (
                    image in self.thumbnails or  # Regular image
                    (ext.lower() == '.mp4' and f"{name}_video.jpg" in self.thumbnails)  # Video thumbnail
                )
                if not thumbnail_exists:
                    self.create_thumbnail(image)
            self.thumbnails.sort(reverse=True)

    def create_thumbnail(self, file):
        """Create thumbnail for both images and videos."""
        full_path = self.get_full_path(file)
        name, ext = os.path.splitext(file)
        ext = ext.lower()
        
        # Set thumbnail path based on file type
        if ext == '.mp4':
            thumbnail_path = os.path.join(THUMBNAILS_PATH, f"{name}_video.jpg")
            print(f"Creating thumbnail for video {file} -> {name}_video.jpg")
        else:
            thumbnail_path = os.path.join(THUMBNAILS_PATH, file)
            print(f"Creating thumbnail for image {file}")
        
        # Process based on file type
        if ext == '.mp4':
            try:
                # ...existing video thumbnail code...
                subprocess.run([
                    'ffmpeg',
                    '-i', full_path,
                    '-vframes', '1',
                    '-an',
                    '-ss', '0',
                    '-y',
                    '-f', 'image2',
                    thumbnail_path
                ], check=True, capture_output=True)
                
                # Create thumbnail with video icon
                img = Image.open(thumbnail_path)
                cropped_thumbnail = ImageOps.fit(img, THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                
                # Open and resize video icon
                icon = Image.open(os.path.join(ICONS_PATH, "video-icon.png"))
                icon_size = (32, 32)
                icon = icon.resize(icon_size)
                
                # Calculate position for bottom-right corner with margin
                icon_x = THUMBNAIL_SIZE[0] - icon_size[0] - 20
                icon_y = THUMBNAIL_SIZE[1] - icon_size[1] - 20
                
                # Paste icon onto thumbnail
                if icon.mode == 'RGBA':
                    cropped_thumbnail.paste(icon, (icon_x, icon_y), icon)
                else:
                    cropped_thumbnail.paste(icon, (icon_x, icon_y))
                
                cropped_thumbnail.save(thumbnail_path)
                self.thumbnails.append(f"{name}_video.jpg")
                
            except subprocess.CalledProcessError as e:
                print(f"Error creating video thumbnail for {file}: {e.stderr.decode()}")
            except Exception as e:
                print(f"Error processing video thumbnail for {file}: {e}")
        else:
            # Handle image thumbnail
            try:
                img = Image.open(full_path)
                exif = img._getexif()

                if exif:
                    orientation = exif.get(274)
                    if orientation == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
                    elif orientation == 3:
                        img = img.rotate(180, expand=True)

                cropped_thumbnail = ImageOps.fit(img, THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                cropped_thumbnail.save(thumbnail_path)
                self.thumbnails.append(file)
            except Exception as e:
                print(f"Error creating image thumbnail for {file}: {e}")

    def get_full_path(self, file):
        return os.path.join(BASE_PATH,  file)

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

        self.gallery = gallery
        self.month_labels = {}
        self.year_labels = {}

        # Cache video icon
        self.video_icon = Gtk.Image.new_from_file(os.path.join(ICONS_PATH, "video-icon.png"))
        self.video_icon.set_size_request(64, 64)

        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        self.set_titlebar(header)

        # Load CSS
        self.load_css()

        # Main horizontal box: sidebar + scrollable main content
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(hbox)

        # Sidebar with scroll
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_size_request(180, -1)
        hbox.append(sidebar_scroll)

        self.sidebar = Gtk.ListBox()
        self.sidebar.set_selection_mode(Gtk.SelectionMode.NONE)
        sidebar_scroll.set_child(self.sidebar)

        # Scroll and main container
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_hexpand(True)
        hbox.append(self.scroll)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.scroll.set_child(self.main_box)

        # Initialize the gallery view
        self.initialize_gallery(gallery)

    def initialize_gallery(self, gallery):
        """Initialize the gallery view with the first image and process all images."""
        # Initialize with first image
        current_year = gallery.get_year(gallery.thumbnails[0])
        current_month = gallery.get_month(gallery.thumbnails[0])
        
        # Create initial year and month containers
        year_box = self.create_year_container(current_year)
        month_box = self.create_month_container(current_month, current_year, year_box)
        image_box = self.create_image_box()
        month_box.append(image_box)

        # Process all images
        for image in gallery.thumbnails:
            image_year = gallery.get_year(image)
            image_month = gallery.get_month(image)

            if current_year != image_year:
                # Handle year change
                current_year = image_year
                current_month = image_month
                year_box = self.create_year_container(current_year)
                month_box = self.create_month_container(current_month, current_year, year_box)
                image_box = self.create_image_box()
                month_box.append(image_box)
            elif current_month != image_month:
                # Handle month change
                current_month = image_month
                month_box = self.create_month_container(current_month, current_year, year_box)
                image_box = self.create_image_box()
                month_box.append(image_box)

            # Add image to current image box
            self.add_image_to_box(image_box, image, gallery)

    def create_year_container(self, year):
        """Create a year container and add it to both main view and sidebar."""
        year_box = self.create_year_box(year)
        self.main_box.append(year_box)
        
        year_row = self.create_year_row(year)
        self.sidebar.append(year_row)

        # Add click handler to year in sidebar
        gesture = Gtk.GestureClick.new()
        gesture.connect("pressed", self.on_year_clicked, year)
        year_row.add_controller(gesture)
        
        return year_box

    def create_month_container(self, month, year, year_box):
        """Create a month container and add it to both main view and sidebar."""
        month_box = self.create_month_box(month, year)
        year_box.append(month_box)
        
        month_row = self.create_month_row(month)
        self.sidebar.append(month_row)
        
        # Add click handler to month in sidebar
        gesture = Gtk.GestureClick.new()
        gesture.connect("pressed", self.on_month_clicked, month, year)
        month_row.add_controller(gesture)
        
        return month_box

    def add_image_to_box(self, image_box, image, gallery):
        """Add an image to the specified image box with proper error handling."""
        try:
            container = Gtk.Overlay()
            
            # Add main image
            image_path = gallery.get_thumbnail_path(image)
            image_widget = Gtk.Image.new_from_file(image_path)
            image_widget.get_style_context().add_class("image")
            container.set_child(image_widget)
            
            gesture = Gtk.GestureClick.new()
            gesture.connect("pressed", self.on_image_clicked, image)
            container.add_controller(gesture)
            
            image_box.insert(container, -1)
        except Exception as e:
            print(f"Error adding image {image}: {e}")

    def on_image_clicked(self, gesture, n_press, x, y, image):
        """Handle image/video click by opening in the default viewer."""
        try:
            name, ext = os.path.splitext(image)
            
            # Check if this is a video thumbnail
            if name.endswith('_video'):
                # Remove _video suffix and add .mp4 extension
                original_name = name[:-6] + '.mp4'
                full_path = self.gallery.get_full_path(original_name)
            else:
                full_path = self.gallery.get_full_path(image)

            # Get clean name for year/month/day (remove _video if present)
            clean_name = name[:-6] if name.endswith('_video') else name
            year = self.gallery.get_year(clean_name)
            month = self.gallery.get_month(clean_name)
            day = clean_name[6:8]
            print(f"Opening file: (Year: {year}, Month: {month} Day: {day})")
            
            # Open file with system default application, redirecting output to /dev/null
            with open(os.devnull, 'w') as devnull:
                subprocess.Popen(
                    ["xdg-open", full_path],
                    stdout=devnull,
                    stderr=devnull
                )
        except Exception as e:
            print(f"Error opening file {image}: {e}")

    def get_month_key(self, year, month):
        """Create a consistent key for the month_labels dictionary."""
        return f"{year}{month:02d}"

    def on_month_clicked(self, gesture, n_press, x, y, month, year):
        """Handle month click events by scrolling to the month's position."""
        try:
            key = self.get_month_key(year, month)
            month_label = self.month_labels[key]
            vadjustment = self.scroll.get_vadjustment()
            (_, y) = month_label.translate_coordinates(self, 0, vadjustment.get_value())
            vadjustment.set_value(y - SCROLL_OFFSET)
        except Exception as e:
            print(f"Error scrolling to month: {e}")

    def on_year_clicked(self, gesture, n_press, x, y, year):
        """Handle year click events by scrolling to the year's position."""
        try:
            year_label = self.year_labels[year]
            vadjustment = self.scroll.get_vadjustment()
            (_, y) = year_label.translate_coordinates(self, 0, vadjustment.get_value())
            vadjustment.set_value(y - SCROLL_OFFSET)
        except Exception as e:
            print(f"Error scrolling to year: {e}")

    def create_image_box(self):
        image_box = Gtk.FlowBox()
        image_box.set_max_children_per_line(5)
        image_box.set_selection_mode(Gtk.SelectionMode.NONE)
        return image_box 

    def create_year_box(self, year):
        year_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=50)
        year_label = Gtk.Label(label=str(year))
        year_label.set_markup(f"<b><span size='20000'>-{year}-</span></b>")
        year_box.append(year_label)

        # Store the label for scroll navigation
        self.year_labels[year] = year_label

        return year_box

    def create_month_box(self, month, year):
        """Create and return a month container with its label."""
        month_name = MONTH_NAMES[month] 
        month_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=25)
        month_label = Gtk.Label(label=f"{month_name} {year}")
        month_label.set_markup(f"<b><span size='15000'>{month_name} {year}</span></b>")
        month_box.append(month_label)
        
        # Store the label for scroll navigation
        key = self.get_month_key(year, month)
        self.month_labels[key] = month_label
        return month_box
    
    def create_year_row(self, year):
        """Create a sidebar entry for the year."""
        year_row = Gtk.ListBoxRow()
        year_label = Gtk.Label(label=f"{year}")
        year_label.set_xalign(0)
        year_label.set_margin_start(10)
        year_label.set_markup(f"<b>{year}</b>")
        year_row.set_child(year_label)
        return year_row
    
    def create_month_row(self, month):
        """Create a sidebar entry for the month."""
        month_name = MONTH_NAMES[month]
        month_row = Gtk.ListBoxRow()
        month_label = Gtk.Label(label=f"{month_name}")
        month_label.set_xalign(0)
        month_label.set_margin_start(10)
        month_label.set_markup(f"<i>{month_name}</i>")
        month_row.set_child(month_label)
        return month_row

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
