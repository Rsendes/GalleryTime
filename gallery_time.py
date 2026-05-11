import os
import gi
import subprocess
import argparse
import base64
import logging
import posixpath
import sys
import threading
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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

DEFAULT_BASE_PATH = "/home/filipe/Pictures/Fotos"
APP_CACHE_PATH = os.path.join(GLib.get_user_cache_dir(), "gallery-time")
LOG_PATH = os.path.join(APP_CACHE_PATH, "gallery-time.log")
DEFAULT_THUMBNAILS_PATH = os.path.join(APP_CACHE_PATH, "thumbnails")
DEFAULT_DOWNLOADS_PATH = os.path.join(APP_CACHE_PATH, "originals")
IGNORE_PATH = "Thumbnails"
ICONS_PATH = os.path.join(os.path.dirname(__file__), "icons")  # Add this line

THUMBNAIL_SIZE = (300, 300)

ICON_SIZE = (32, 32)

SCROLL_OFFSET = 60

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.tif', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4'}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def setup_logging():
    os.makedirs(APP_CACHE_PATH, exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.insert(0, logging.FileHandler(LOG_PATH))
    except OSError as error:
        print(f"Could not write log file {LOG_PATH}: {error}", file=sys.stderr)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Browse a timeline gallery from a local path or Nextcloud.")
    parser.add_argument(
        "--base-path",
        default=os.environ.get("GALLERY_TIME_BASE_PATH", DEFAULT_BASE_PATH),
        help="Local folder to scan. This can be a server path mounted with NFS, SMB, sshfs, davfs, or GVFS.",
    )
    parser.add_argument(
        "--thumbnail-path",
        default=os.environ.get("GALLERY_TIME_THUMBNAILS_PATH"),
        help="Folder where generated thumbnails are stored.",
    )
    parser.add_argument(
        "--nextcloud-url",
        default=os.environ.get("GALLERY_TIME_NEXTCLOUD_URL"),
        help="Nextcloud WebDAV folder URL, for example https://cloud.example.com/remote.php/dav/files/user/Photos/",
    )
    parser.add_argument(
        "--nextcloud-user",
        default=os.environ.get("GALLERY_TIME_NEXTCLOUD_USER"),
        help="Nextcloud username for WebDAV.",
    )
    parser.add_argument(
        "--nextcloud-password",
        default=os.environ.get("GALLERY_TIME_NEXTCLOUD_PASSWORD"),
        help="Nextcloud app password for WebDAV. Prefer the environment variable.",
    )
    parser.add_argument(
        "--download-path",
        default=os.environ.get("GALLERY_TIME_DOWNLOAD_PATH", DEFAULT_DOWNLOADS_PATH),
        help="Local cache folder for files downloaded from Nextcloud.",
    )
    return parser.parse_args()


class LocalImageSource:
    def __init__(self, base_path):
        self.base_path = os.path.abspath(os.path.expanduser(base_path))

    def list_files(self):
        files = []
        for root, dirs, filenames in os.walk(self.base_path):
            dirs[:] = [d for d in dirs if d != IGNORE_PATH]
            for filename in filenames:
                files.append((filename, os.path.join(root, filename)))
        return files

    def get_local_path(self, file, source_path):
        return source_path


class NextcloudImageSource:
    def __init__(self, url, username, password, download_path):
        if not username or not password:
            raise ValueError("Nextcloud mode requires --nextcloud-user and --nextcloud-password.")
        self.url = url.rstrip("/") + "/"
        self.username = username
        self.password = password
        self.download_path = os.path.abspath(os.path.expanduser(download_path))
        os.makedirs(self.download_path, exist_ok=True)

    def _request(self, url, method="GET", headers=None):
        headers = headers or {}
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
        request = urllib.request.Request(url, method=method, headers=headers)
        return urllib.request.urlopen(request)

    def list_files(self):
        body = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:">
  <d:prop><d:resourcetype /></d:prop>
</d:propfind>""".encode("utf-8")
        headers = {"Depth": "infinity", "Content-Type": "application/xml"}
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
        request = urllib.request.Request(self.url, data=body, method="PROPFIND", headers=headers)
        with urllib.request.urlopen(request) as response:
            xml_data = response.read()

        namespace = {"d": "DAV:"}
        root = ET.fromstring(xml_data)
        base_path = urllib.parse.urlparse(self.url).path.rstrip("/") + "/"
        files = []
        for item in root.findall("d:response", namespace):
            href = item.findtext("d:href", namespaces=namespace)
            resource_type = item.find(".//d:resourcetype", namespace)
            is_collection = resource_type is not None and resource_type.find("d:collection", namespace) is not None
            if not href or is_collection:
                continue

            path = urllib.parse.unquote(urllib.parse.urlparse(href).path)
            if not path.startswith(base_path):
                continue
            relative_path = path[len(base_path):]
            filename = posixpath.basename(relative_path)
            files.append((filename, urllib.parse.urljoin(self.url, urllib.parse.quote(relative_path, safe="/"))))
        return files

    def get_local_path(self, file, source_url):
        local_path = os.path.join(self.download_path, file)
        if os.path.exists(local_path):
            return local_path

        logging.info("Downloading %s", file)
        with self._request(source_url) as response, open(local_path, "wb") as destination:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                destination.write(chunk)
        return local_path


class Gallery():
    def __init__(self, image_source, thumbnails_path, progress_callback=None):
        self.image_source = image_source
        self.thumbnails_path = os.path.abspath(os.path.expanduser(thumbnails_path))
        os.makedirs(self.thumbnails_path, exist_ok=True)
        self.progress_callback = progress_callback
        self.images = []
        self.image_sources = {}
        self.thumbnails = []
        self.load_images()
        self.load_thumbnails()
        self.create_thumbnails()

    def report(self, message, current=None, total=None):
        logging.info(message)
        if self.progress_callback:
            self.progress_callback(message, current, total)

    def is_valid(self, file):
        name, ext = os.path.splitext(file)
        return (
            len(name) >= 6
            and name[:6].isdigit()
            and name[:2] == "20"
            and ext.lower() in SUPPORTED_EXTENSIONS
        )

    def get_year(self, file):
        return int(file[:4])

    def get_month(self, file):
        return int(file[4:6])

    def is_video(self, ext):
        return ext.lower() in VIDEO_EXTENSIONS

    def get_full_path(self, file):
        source_path = self.image_sources[file]
        return self.image_source.get_local_path(file, source_path)

    def get_thumbnail_path(self, file):
        return os.path.join(self.thumbnails_path, file)

    def get_original_file_for_thumbnail(self, thumbnail):
        name, ext = os.path.splitext(thumbnail)
        if name.endswith('_video'):
            return name[:-6] + '.mp4'
        return thumbnail

    def load_images(self):
        self.report("Loading images...")
        for file, source_path in self.image_source.list_files():
            if self.is_valid(file):
                if file in self.image_sources:
                    self.report(f"Skipping duplicate file name: {file}")
                    continue
                self.images.append(file)
                self.image_sources[file] = source_path
        self.images.sort()
        self.report(f"Loaded {len(self.images)} image/video files.")

    def load_thumbnails(self):
        self.report("Loading existing thumbnails...")
        for _, _, files in  os.walk(self.thumbnails_path):
            for file in files:
                original_file = self.get_original_file_for_thumbnail(file)
                if original_file in self.image_sources:
                    self.thumbnails.append(file)
        self.thumbnails.sort(reverse=True)
        self.report(f"Loaded {len(self.thumbnails)} existing thumbnails.")

    def create_thumbnails(self):
        missing_images = []
        for image in self.images:
            name, ext = os.path.splitext(image)
            # Check for both regular image and video thumbnail
            thumbnail_exists = (
                image in self.thumbnails or  # Regular image
                (ext.lower() == '.mp4' and f"{name}_video.jpg" in self.thumbnails)  # Video thumbnail
            )
            if not thumbnail_exists:
                missing_images.append(image)

        if not missing_images:
            self.report("All thumbnails are already available.", 1, 1)
            return

        total = len(missing_images)
        for index, image in enumerate(missing_images, start=1):
            self.report(f"Creating thumbnail {index}/{total}: {image}", index, total)
            self.create_thumbnail(image)
        self.thumbnails.sort(reverse=True)
        self.report(f"Finished creating {total} thumbnails.", total, total)

    def create_thumbnail(self, file):
        """Create thumbnail for both images and videos."""
        full_path = self.get_full_path(file)
        name, ext = os.path.splitext(file)
        ext = ext.lower()

        if self.is_video(ext):
            self.create_video_thumbnail(full_path, name, file)
        else:
            self.create_image_thumbnail(full_path, name, file)

    def create_video_thumbnail(self, full_path, name, file):
        thumbnail_path = os.path.join(self.thumbnails_path, f"{name}_video.jpg")
        logging.info("Creating thumbnail for video %s -> %s_video.jpg", file, name)
        try:
            subprocess.run(['ffmpeg', '-i', full_path, '-vframes', '1', '-an',
                            '-ss', '0', '-y','-f', 'image2', thumbnail_path], 
                           check=True, capture_output=True)

            # Create thumbnail with video icon
            img = Image.open(thumbnail_path)
            cropped_thumbnail = ImageOps.fit(img, THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Open and resize video icon
            icon = Image.open(os.path.join(ICONS_PATH, "video-icon.png"))
            icon = icon.resize(ICON_SIZE)

            # Calculate position for bottom-right corner with margin
            icon_x = THUMBNAIL_SIZE[0] - ICON_SIZE[0] - 20
            icon_y = THUMBNAIL_SIZE[1] - ICON_SIZE[1] - 20

            # Paste icon onto thumbnail
            if icon.mode == 'RGBA':
                cropped_thumbnail.paste(icon, (icon_x, icon_y), icon)
            else:
                cropped_thumbnail.paste(icon, (icon_x, icon_y))

            cropped_thumbnail.save(thumbnail_path)
            self.thumbnails.append(f"{name}_video.jpg")

        except subprocess.CalledProcessError as e:
            self.report(f"Error creating video thumbnail for {file}: {e.stderr.decode()}")
        except Exception as e:
            self.report(f"Error processing video thumbnail for {file}: {e}")

    def create_image_thumbnail(self, full_path, name, file):
        thumbnail_path = os.path.join(self.thumbnails_path, file)
        logging.info("Creating thumbnail for image %s", file)
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
            self.report(f"Error creating image thumbnail for {file}: {e}")


class App(Gtk.Application):
    def __init__(self, args):
        super().__init__()
        GLib.set_application_name("Gallery Time")
        self.args = args

    def do_activate(self):
        """Called when the application is activated."""
        window = MainWindow(self)
        window.present()
        window.load_gallery_async()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Gallery Time")
        self.set_default_size(800, 600)

        self.gallery = None
        self.month_labels = {}
        self.year_labels = {}

        # Cache video icon
        self.video_icon = Gtk.Image.new_from_file(os.path.join(ICONS_PATH, "video-icon.png"))
        self.video_icon.set_size_request(64, 64)

        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        self.set_titlebar(header)

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

        self.show_loading_view()

    def show_loading_view(self):
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        loading_box.set_margin_top(48)
        loading_box.set_margin_bottom(48)
        loading_box.set_margin_start(32)
        loading_box.set_margin_end(32)

        title = Gtk.Label()
        title.set_xalign(0)
        title.set_markup("<b><span size='16000'>Loading Gallery Time</span></b>")
        loading_box.append(title)

        self.loading_label = Gtk.Label(label="Starting...")
        self.loading_label.set_xalign(0)
        self.loading_label.set_wrap(True)
        loading_box.append(self.loading_label)

        self.loading_progress = Gtk.ProgressBar()
        self.loading_progress.set_show_text(True)
        self.loading_progress.set_text("Preparing")
        loading_box.append(self.loading_progress)

        log_label = Gtk.Label(label=f"Log: {LOG_PATH}")
        log_label.set_xalign(0)
        log_label.set_wrap(True)
        loading_box.append(log_label)

        self.main_box.append(loading_box)

    def clear_container(self, container):
        child = container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            container.remove(child)
            child = next_child

    def update_loading_status(self, message, current=None, total=None):
        self.loading_label.set_text(message)
        if current is not None and total:
            fraction = min(max(current / total, 0), 1)
            self.loading_progress.set_fraction(fraction)
            self.loading_progress.set_text(f"{current}/{total}")
        else:
            self.loading_progress.pulse()
            self.loading_progress.set_text("Working")
        return False

    def load_gallery_async(self):
        def progress(message, current=None, total=None):
            GLib.idle_add(self.update_loading_status, message, current, total)

        def worker():
            try:
                gallery = build_gallery(self.get_application().args, progress)
            except Exception as error:
                logging.exception("Failed to load gallery")
                GLib.idle_add(self.show_load_error, str(error), traceback.format_exc())
                return

            GLib.idle_add(self.show_gallery, gallery)

        threading.Thread(target=worker, daemon=True).start()

    def show_gallery(self, gallery):
        self.gallery = gallery
        self.clear_container(self.main_box)
        self.clear_container(self.sidebar)
        self.month_labels.clear()
        self.year_labels.clear()
        self.initialize_gallery(gallery)
        return False

    def show_load_error(self, message, details):
        self.clear_container(self.main_box)

        error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        error_box.set_margin_top(48)
        error_box.set_margin_start(32)
        error_box.set_margin_end(32)

        title = Gtk.Label()
        title.set_xalign(0)
        title.set_markup("<b><span size='16000'>Could not load gallery</span></b>")
        error_box.append(title)

        message_label = Gtk.Label(label=message)
        message_label.set_xalign(0)
        message_label.set_wrap(True)
        error_box.append(message_label)

        log_label = Gtk.Label(label=f"Details were written to {LOG_PATH}")
        log_label.set_xalign(0)
        log_label.set_wrap(True)
        error_box.append(log_label)

        self.main_box.append(error_box)
        return False

    def initialize_gallery(self, gallery):
        """Initialize the gallery view with the first image and process all images."""
        if not gallery.thumbnails:
            empty_label = Gtk.Label(label="No images found")
            empty_label.set_margin_top(40)
            self.main_box.append(empty_label)
            return

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

        gesture = Gtk.GestureClick.new()
        gesture.connect("pressed", self.on_month_clicked, month, year)
        month_row.add_controller(gesture)

        return month_box

    def add_image_to_box(self, image_box, image, gallery):
        """Add an image to the specified image box with proper error handling."""
        try:
            container = Gtk.Overlay()

            container.set_size_request(THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1])

            # Add main image
            image_path = gallery.get_thumbnail_path(image)
            image_widget = Gtk.Image.new_from_file(image_path)

            image_widget.set_hexpand(True)
            image_widget.set_vexpand(True)
            image_widget.set_pixel_size(THUMBNAIL_SIZE[0]) 

            container.set_child(image_widget)

            gesture = Gtk.GestureClick.new()
            gesture.connect("pressed", self.on_image_clicked, image)
            container.add_controller(gesture)
            image_box.insert(container, -1)

        except Exception as e:
            logging.exception("Error adding image %s: %s", image, e)

    def on_image_clicked(self, gesture, n_press, x, y, image):
        """Handle image/video click by opening in the default viewer."""
        try:
            name, ext = os.path.splitext(image)
            original_name = self.gallery.get_original_file_for_thumbnail(image)
            _, original_ext = os.path.splitext(original_name)
            full_path = self.gallery.get_full_path(original_name)

            # Get clean name for year/month/day (remove _video if present)
            clean_name = name[:-6] if name.endswith('_video') else name
            year = self.gallery.get_year(clean_name)
            month = self.gallery.get_month(clean_name)
            day = clean_name[6:8]
            logging.info("Opening file: Year %s, Month %s, Day %s", year, month, day)

            open_command = "xdg-open" if self.gallery.is_video(original_ext) else "imv-dir"

            # Open file with the configured viewer, redirecting output to /dev/null
            with open(os.devnull, 'w') as devnull:
                subprocess.Popen(
                    [open_command, full_path],
                    stdout=devnull,
                    stderr=devnull
                )
        except Exception as e:
            logging.exception("Error opening file %s: %s", image, e)

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
            logging.exception("Error scrolling to month: %s", e)

    def on_year_clicked(self, gesture, n_press, x, y, year):
        """Handle year click events by scrolling to the year's position."""
        try:
            year_label = self.year_labels[year]
            vadjustment = self.scroll.get_vadjustment()
            (_, y) = year_label.translate_coordinates(self, 0, vadjustment.get_value())
            vadjustment.set_value(y - SCROLL_OFFSET)
        except Exception as e:
            logging.exception("Error scrolling to year: %s", e)

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

def build_gallery(args, progress_callback=None):
    if args.nextcloud_url:
        image_source = NextcloudImageSource(
            args.nextcloud_url,
            args.nextcloud_user,
            args.nextcloud_password,
            args.download_path,
        )
        thumbnails_path = args.thumbnail_path or DEFAULT_THUMBNAILS_PATH
    else:
        image_source = LocalImageSource(args.base_path)
        thumbnails_path = args.thumbnail_path or os.path.join(image_source.base_path, IGNORE_PATH)

    return Gallery(image_source, thumbnails_path, progress_callback)


if __name__ == "__main__":
    args = parse_args()
    setup_logging()
    app = App(args)
    app.run()
