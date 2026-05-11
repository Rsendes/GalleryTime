# GalleryTime
Personal project to store and view pictures with a timeline organization.

## Image source

By default the app still reads:

```bash
python3 gallery_time.py
```

from `/home/filipe/Pictures/Fotos`.

To use a folder from a server filesystem, mount the server folder first with NFS, SMB, sshfs, davfs, or your file manager, then pass that mounted path:

```bash
python3 gallery_time.py --base-path /mnt/photos
```

You can also use environment variables:

```bash
GALLERY_TIME_BASE_PATH=/mnt/photos python3 gallery_time.py
```

To read directly from Nextcloud, use its WebDAV folder URL and an app password:

```bash
GALLERY_TIME_NEXTCLOUD_PASSWORD='your-app-password' \
python3 gallery_time.py \
  --nextcloud-url 'https://cloud.example.com/remote.php/dav/files/username/Photos/' \
  --nextcloud-user username
```

Nextcloud originals are cached in `~/.cache/gallery-time/originals`, and generated thumbnails are cached in `~/.cache/gallery-time/thumbnails`. Override those with `--download-path` and `--thumbnail-path`.

## Wofi launcher

The `run-gallery-time` script mounts the server folder with SSHFS if needed, then starts the app with the mounted folder and local thumbnail cache:

```bash
./run-gallery-time
```

Install `GalleryTime.desktop` into `~/.local/share/applications` so Wofi can find it.

When launched from Wofi, startup progress is shown inside the app window. Logs are written to:

```bash
~/.cache/gallery-time/gallery-time.log
```
