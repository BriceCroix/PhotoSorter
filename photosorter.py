from genericpath import isfile
import os
import sys
import glob
import tkinter as tk
import tkinter.filedialog
import exifread
import json
import unidecode

from datetime import datetime
from geopy.geocoders import Nominatim
geolocator = Nominatim(user_agent="photosorter") # Use OpenstreetMap

import argparse
argparser = argparse.ArgumentParser(description='Renames and moves pictures in a directory.', epilog='If no arguments provided, the interface is launched.')
argparser.add_argument('directory', help='Path to directory to be processed.', type=str, nargs='?')
#argparser.add_argument('-g', '--gui', help='Starts User Interface', action='store_true')
argparser.add_argument('-G', '--gps', help='Uses GPS data to rename files.', action='store_true')
argparser.add_argument('-s', '--suffix', help='Adds given suffix to each file.')
argparser.add_argument('-R', '--revert', help='Reverts given directory to original state.', action='store_true')
option_group = argparser.add_mutually_exclusive_group(required=False)
option_group.add_argument('-m', '--month', help='Classify files by month.', action='store_true')
option_group.add_argument('-y', '--year', help='Classify files by year.', action='store_true')
args = argparser.parse_args()


PHOTOSORTER_SUBDIR = '.photosorter'


class PhotoSorterGui:
    SORT_BY_NONE = 0
    SORT_BY_MONTH = 1
    SORT_BY_YEAR = 2

    def __init__(self) -> None:
        self.window = tk.Tk()
        self.window.title('Photo Sorter')
        self.window.geometry('640x480')

        self.directory = tk.StringVar()
        self.revert = tk.BooleanVar()
        self.use_gps = tk.BooleanVar()
        self.suffix = tk.StringVar()
        self.suffix.set('')
        self.sort_by_dir = tk.IntVar()
        self.sort_by_dir.set(PhotoSorterGui.SORT_BY_NONE)

        self.directory_frm = tk.LabelFrame(self.window, text='Directory to process')
        self.directory_frm.pack(fill='both')

        self.directory_lbl = tk.Label(self.directory_frm, textvariable=self.directory)
        self.directory_lbl.pack()

        self.open_dir_btn = tk.Button(self.directory_frm, text="Open Directory", command=self.on_open_dir_btn_click)
        self.open_dir_btn.pack()

        self.options_frm = tk.LabelFrame(self.window, text='Options')
        self.options_frm.pack(fill='both')

        self.gps_chk = tk.Checkbutton(self.options_frm, text="Include GPS data", variable=self.use_gps)
        self.gps_chk.pack()

        self.suffix_entry = tk.Entry(self.options_frm, textvariable=self.suffix, width=30)
        self.suffix_entry.pack()

        self.sort_by_dir_none_radiobtn = tk.Radiobutton(self.options_frm, text="Do not sort", variable=self.sort_by_dir, value=PhotoSorterGui.SORT_BY_NONE)
        self.sort_by_dir_none_radiobtn.pack()
        self.sort_by_dir_year_radiobtn= tk.Radiobutton(self.options_frm, text="Sort by year", variable=self.sort_by_dir, value=PhotoSorterGui.SORT_BY_YEAR)
        self.sort_by_dir_year_radiobtn.pack()
        self.sort_by_dir_month_radiobtn = tk.Radiobutton(self.options_frm, text="Sort by month", variable=self.sort_by_dir, value=PhotoSorterGui.SORT_BY_MONTH)
        self.sort_by_dir_month_radiobtn.pack()

        self.start_frm = tk.LabelFrame(self.window, text='')
        self.start_frm.pack(fill='both')

        self.revert_chx = tk.Checkbutton(self.start_frm, text="Revert", variable=self.revert, command=self.on_revert_changed)
        self.revert_chx.pack()

        start_btn = tk.Button(self.start_frm, text="Start", command=self.on_start_btn_click)
        start_btn.pack()

        self.window.mainloop()

    def on_open_dir_btn_click(self):
        self.directory.set(tk.filedialog.askdirectory())

    def on_start_btn_click(self):
        if self.directory.get() != '':
            if self.revert.get():
                revert_directory(self.directory.get())
            else:
                process_directory(self.directory.get(), self.use_gps.get(), self.suffix.get(),
                    self.sort_by_dir.get()==PhotoSorterGui.SORT_BY_MONTH, self.sort_by_dir.get()==PhotoSorterGui.SORT_BY_YEAR) 
            tk.messagebox.showinfo('Info', 'Operation successful !')
        else:
            tk.messagebox.showerror('Error', 'Please give directory to process')

    def enable_disable(self, element, enabled:bool):
        element['state'] = tk.NORMAL if enabled else tk.DISABLED

    def on_revert_changed(self):
        self.enable_disable(self.gps_chk, not self.revert.get())
        self.enable_disable(self.suffix_entry, not self.revert.get())
        self.enable_disable(self.sort_by_dir_month_radiobtn, not self.revert.get())
        self.enable_disable(self.sort_by_dir_year_radiobtn, not self.revert.get())
        self.enable_disable(self.sort_by_dir_none_radiobtn, not self.revert.get())
        

def start_gui():
    print("Starting GUI...")
    PhotoSorterGui()
    print("GUI closed.")


def process_directory(directory:str, use_gps:bool=False, suffix:str='', dir_by_month:bool=False, dir_by_year:bool=False):
    # Match all jpeg files
    photos = []
    for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
        photos.extend(glob.glob(os.path.join(directory, ext)))
    # For each photo
    json_data = {}
    for i in range(len(photos)):
        # Convert paths to absolute path
        photos[i] = os.path.abspath(photos[i])
        photo_path = photos[i]

        exif_data = exifread.process_file(open(photo_path, 'rb'))

        # Recover gps info if present
        country = ''
        town = ''
        if use_gps and 'GPS GPSLatitude' in exif_data.keys() and 'GPS GPSLongitude' in exif_data.keys():
            # Convert latitude & longitude to decimal instead of degrees-minutes-secondes
            longitude_dms = exif_data['GPS GPSLongitude'].values
            longitude_decimal = float(longitude_dms[0] + (longitude_dms[1] / 60) + (longitude_dms[2].real / 3600))
            if 'GPS GPSLongitudeRef' in exif_data.keys() and exif_data['GPS GPSLongitudeRef'].values == 'W':
                longitude_decimal = -longitude_decimal
            latitude_dms = exif_data['GPS GPSLatitude'].values
            latitude_decimal = float(latitude_dms[0] + (latitude_dms[1] / 60) + (latitude_dms[2].real / 3600))
            # Get full adress
            location = geolocator.reverse(f'{latitude_decimal},{longitude_decimal}')
            if location is not None:
                if 'country' in location.raw['address']:
                    country = location.raw['address']['country']
                else:
                    country = ''
                country = unidecode.unidecode(country)
                if 'town' in location.raw['address']:
                    town = location.raw['address']['town']
                elif 'village' in location.raw['address']:
                    town = location.raw['address']['village']
                elif 'municipality' in location.raw['address']:
                    town = location.raw['address']['municipality']
                else:
                    town = ''
                town = unidecode.unidecode(town)

        # Recover datetime object
        # Fallback to date of creation of file if exif tag absent
        if 'Image DateTime' in exif_data.keys():
            date_time_obj = datetime.strptime(exif_data['Image DateTime'].values, '%Y:%m:%d %H:%M:%S')
        else:
            date_time_obj = datetime.fromtimestamp(os.path.getmtime(photo_path))

        # Create new name
        new_name = f'{date_time_obj.year:04}-{date_time_obj.month:02}-{date_time_obj.day:02}'
        new_name += '-'
        new_name += f'{date_time_obj.hour:02}H{date_time_obj.minute:02}'#m{date_time_obj.second:02}s'
        if country != '':
            new_name += f'-{country}'
        if town != '':
            new_name += f'-{town}'
        if suffix != '':
            new_name += f'-{suffix}'
        new_name += '.jpg'
        # Convert to absolute path and create subdirectory if necessary
        destination_dir = os.path.dirname(photo_path)
        subdestination_dir = destination_dir
        if dir_by_year:
            subdir_name = f'{date_time_obj.year:04}'
            subdestination_dir = os.path.join(destination_dir, subdir_name)
        elif dir_by_month:
            subdir_name = f'{date_time_obj.year:04}-{date_time_obj.month:02}'
            subdestination_dir = os.path.join(destination_dir, subdir_name)
        os.makedirs(subdestination_dir, exist_ok=True)
        full_new_name = os.path.join(subdestination_dir, new_name)

        # Handle photos that are already well named
        if full_new_name == photo_path:
            continue

        # Handle pictures taken same place same minute
        additional_number = 1
        while os.path.isfile(full_new_name):
            new_name_without_ext, ext = os.path.splitext(new_name)
            full_new_name = os.path.join(subdestination_dir, new_name_without_ext + f'-{additional_number}{ext}')
            additional_number += 1

        # Finally rename picture
        os.rename(photo_path, full_new_name)
        print(photo_path + ' -> ' + full_new_name)
        # Add json data
        key = f'file_{i}'
        json_data[key] = {'OldName':photo_path, 'NewName' : full_new_name}

    # Dump json to file
    if(len(json_data) != 0):
        photosorter_dir = os.path.join(destination_dir, PHOTOSORTER_SUBDIR)
        os.makedirs(photosorter_dir, exist_ok=True)
        with open(os.path.join(photosorter_dir, f'{len(os.listdir(photosorter_dir))+1}.json'), 'w') as outfile:
            json.dump(json_data, outfile, indent=4)
    

def revert_directory(directory:str):
    photosorter_dir = os.path.join(directory, PHOTOSORTER_SUBDIR)
    reports_filenames = sorted(os.listdir(photosorter_dir))
    for report_filename in reversed(reports_filenames):
        full_report_filename = os.path.join(photosorter_dir,report_filename)
        with open(full_report_filename) as json_file:
            report = json.load(json_file)
            for picture_names in report.values():
                if os.path.isfile(picture_names['NewName']):
                    os.rename(picture_names['NewName'], picture_names['OldName'])
                    print(picture_names['NewName'] + ' -> ' + picture_names['OldName'])
        os.remove(full_report_filename)
    # Remove empty directories left by revert
    for entry in os.scandir(directory):
        if os.path.isdir(entry.path) and not os.listdir(entry.path) :
            os.rmdir(entry.path)


def main():
    if args.directory is not None:
        directory = args.directory
        if args.revert:
            revert_directory(directory)
        else:
            suffix = '' if args.suffix is None else args.suffix
            process_directory(directory, args.gps, suffix, args.month, args.year)
    else:
        start_gui()

if __name__ == "__main__":
    main()