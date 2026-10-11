print("### EXIF GPS Viewer ###")
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import base64
import mimetypes
from datetime import datetime
from html import escape

import exifread
import folium


# ------------------------------------------------------------
# Select Source Files
# ------------------------------------------------------------
def select_source():
    root = tk.Tk()
    root.withdraw()
    choice = messagebox.askyesnocancel(
        "EXIF GPS Viewer",
        "Yes  = Select a folder\n"
        "No   = Select file(s)\n"
        "Cancel = Abort"
    )

    if choice is None:
        root.destroy()
        return []

    if choice:  # Folder
        folder = filedialog.askdirectory(title="Select folder containing files")
        files = list(Path(folder).iterdir()) if folder else []

    else:  # Single or multiple files
        selected = filedialog.askopenfilenames(title="Select file(s)")
        files = [Path(f) for f in selected]

    root.destroy()

    return [f for f in files if f.is_file()]


SOURCE_FILES = select_source()

if not SOURCE_FILES:
    raise SystemExit("No files selected.")


# ------------------------------------------------------------
# Output File
# ------------------------------------------------------------
root = tk.Tk()
root.withdraw()
output_path = filedialog.asksaveasfilename(
    title="Save EXIF GPS Map",
    defaultextension=".html",
    initialfile="EXIF_GPS_Map.html",
    filetypes=[
        ("HTML files", "*.html"),
        ("All files", "*.*")
    ]
)

root.destroy()

if not output_path:
    raise SystemExit("Save cancelled.")

OUTPUT_HTML = Path(output_path)


# ------------------------------------------------------------
# EXIF GPS
# ------------------------------------------------------------
def dms_to_decimal(values, ref):
    """
    EXIF GPS:
        degrees / minutes / seconds
        + N/S/E/W
    """

    degrees = float(values[0].num) / float(values[0].den)
    minutes = float(values[1].num) / float(values[1].den)
    seconds = float(values[2].num) / float(values[2].den)

    decimal = degrees + minutes / 60 + seconds / 3600

    if ref in ("S", "W"):
        decimal *= -1

    return decimal


def get_gps(path):
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)

        lat = tags.get("GPS GPSLatitude")
        lat_ref = tags.get("GPS GPSLatitudeRef")

        lon = tags.get("GPS GPSLongitude")
        lon_ref = tags.get("GPS GPSLongitudeRef")

        if not all([lat, lat_ref, lon, lon_ref]):
            return None

        latitude = dms_to_decimal(lat.values, str(lat_ref))
        longitude = dms_to_decimal(lon.values, str(lon_ref))

        return latitude, longitude

    except Exception as e:
        print(f"EXIF-Error: {path} -> {e}")
        return None


# ------------------------------------------------------------
# EXIF Date
# ------------------------------------------------------------
def get_date_taken(path):
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)

        date_tag = tags.get("EXIF DateTimeOriginal")
        
        # Fallback
        if not date_tag:
            date_tag = tags.get("Image DateTime")
        if not date_tag:
            return None

        raw_date = str(date_tag)

        try:
            return datetime.strptime(raw_date, "%Y:%m:%d %H:%M:%S").strftime("%d.%m.%Y %H:%M:%S")

        except ValueError:
            return raw_date

    except Exception as e:
        print(f"EXIF-Date-Error: {path} -> {e}")
        return None


# ------------------------------------------------------------
# Thumbnail
# ------------------------------------------------------------
def image_as_data_uri(path):
    try:
        mime, _ = mimetypes.guess_type(path.name)

        if not mime:
            mime = "image/jpeg"

        data = base64.b64encode(
            path.read_bytes()
        ).decode("ascii")

        return f"data:{mime};base64,{data}"

    except Exception:
        return None


# ------------------------------------------------------------
# Main Iteration
# ------------------------------------------------------------
locations = []

for path in SOURCE_FILES:
    if not path.is_file():
        continue

    gps = get_gps(path)

    if gps:
        locations.append({
            "path": path,
            "lat": gps[0],
            "lon": gps[1],
            "date_taken": get_date_taken(path),
            "type": "image"
        })


# ------------------------------------------------------------
# MAP
# ------------------------------------------------------------
if not locations:
    raise RuntimeError("No files with GPS Information found!")

center_lat = sum(x["lat"] for x in locations) / len(locations)
center_lon = sum(x["lon"] for x in locations) / len(locations)

m = folium.Map(
    location=[
        center_lat,
        center_lon
    ],
    zoom_start=12,
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles © Esri"
)

# ------------------------------------------------------------
# Marker
# ------------------------------------------------------------
for item in locations:
    path = item["path"]
    thumbnail = image_as_data_uri(path)
    filename = escape(path.name)

    if item["date_taken"]:
        date_taken = escape(item["date_taken"])
    else:
        date_taken = "n/a"

    popup_html = f"""
    <div style="
        width:300px;
        font-family:Arial;
    ">

        <b>{filename}</b>
        <br><br>
        <div>
            <b>Date: </b>
            {date_taken}
        </div>
        <br>
        <div>
            <b>GPS: </b>
            {item["lat"]:.7f},
            {item["lon"]:.7f}
        </div>
        <br>
        <img
            src="{thumbnail}"
            style="
                max-width:280px;
                max-height:220px;
                object-fit:contain;
            "
        >
    </div>
    """


    folium.Marker(
        location=[item["lat"], item["lon"]],
        tooltip=path.name,
        popup=folium.Popup(
            popup_html,
            max_width=350,
            close_on_click=False, # allow multiple popups
            auto_close=False
        ),
        icon=folium.Icon(icon="camera", prefix="fa")

    ).add_to(m)


# ------------------------------------------------------------
# save
# ------------------------------------------------------------
m.save(OUTPUT_HTML)

print()
print(f"{len(locations)} file/s with GPS Information found.")
print(f"Output saved: {OUTPUT_HTML}")
print()
input("Press any Key to quit...")