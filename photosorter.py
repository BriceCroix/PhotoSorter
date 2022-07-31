from genericpath import isfile
import os
import sys
import glob
import tkinter as tk
import tkinter.filedialog
import exifread
import json

from datetime import datetime
from PIL import Image, ExifTags
from geopy.geocoders import Nominatim
geolocator = Nominatim(user_agent="geoapiExercises")

import argparse
argparser = argparse.ArgumentParser(description='Renames and moves pictures in a directory.', epilog='If no arguments provided, the interface is launched.')
argparser.add_argument('directory', help='Path to directory to be processed.', type=str, nargs='?')
#argparser.add_argument('-g', '--gui', help='Starts User Interface', action='store_true')
argparser.add_argument('-R', '--revert', help='Reverts given directory to original state.', action='store_true')
args = argparser.parse_args()


def start_gui():
    print('Starting gui...')
    window = tk.Tk()
    window.title('Photo Sorter')
    window.geometry('640x480')

    directory = tk.StringVar()
    revert = tk.BooleanVar(window)

    def on_open_dir_btn_click():
        nonlocal directory 
        directory.set(tk.filedialog.askdirectory())

    def on_start_btn_click():
        nonlocal revert
        nonlocal directory
        if directory.get() != '':
            if revert.get():
                revert_directory(directory.get())
            else:
                process_directory(directory.get())
            tk.messagebox.showinfo('Info', 'Operation successful !')
        else:
            tk.messagebox.showerror('Error', 'Please give directory to process')

    directory_frm = tk.LabelFrame(window, text='Directory to process')
    directory_frm.pack(fill='both')

    directory_lbl = tk.Label(directory_frm, textvariable=directory)
    directory_lbl.pack()

    open_dir_btn = tk.Button(directory_frm, text="Open Directory", command=on_open_dir_btn_click)
    open_dir_btn.pack()

    options_frm = tk.LabelFrame(window, text='Options')
    options_frm.pack(fill='both')

    start_frm = tk.LabelFrame(window, text='')
    start_frm.pack(fill='both')

    revert_chx = tk.Checkbutton(start_frm, text="Revert", variable=revert)
    revert_chx.pack()

    start_btn = tk.Button(start_frm, text="Start", command=on_start_btn_click)
    start_btn.pack()

    window.mainloop()


def process_directory(directory:str):
    # Match all jpeg files
    photos = []
    for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
        photos.extend(glob.glob(os.path.join(directory, ext)))
    # For each photo
    json_data = {}
    for i in range(len(photos)):
        # Convert paths to absolute path
        photos[i] = os.path.abspath(photos[i])
        photo = photos[i]

        exif_data = exifread.process_file(open(photo, 'rb'))

        # Recover gps info if present
        # if 'GPS GPSLatitude' in exif_data and 'GPS GPSLongitude' in exif_data:
        #     # TODO : understand why Latitude and Longitude each contain three data https://pixees.fr/informatiquelycee/n_site/snt_photo_exif.html
        #     location = geolocator.reverse(exif_data['GPS GPSLatitude']+','+exif_data['GPS GPSLongitude'])
        # Recover datetime object
        # TODO : fallback to date of creation of file if exif tag absent
        date_time_obj = datetime.strptime(exif_data['Image DateTime'].values, '%Y:%m:%d %H:%M:%S')
        # TODO use location, etc...
        # https://www.geeksforgeeks.org/get-the-city-state-and-country-names-from-latitude-and-longitude-using-python/
        new_name = f'{date_time_obj.year:04}-{date_time_obj.month:02}-{date_time_obj.day:02}'
        new_name += '-'
        new_name += f'{date_time_obj.hour:02}H{date_time_obj.minute:02}'#m{date_time_obj.second:02}s'
        new_name += '-IMG.jpg'
        # Convert to absolute path
        destination_dir = os.path.dirname(photo)
        full_new_name = os.path.join(destination_dir, new_name)
        # Handle photos that are already well named
        if full_new_name != photo:
            # Handle pictures taken same place same minute
            additional_number = 1
            while os.path.isfile(full_new_name):
                new_name_without_ext, ext = os.path.splitext(new_name)
                full_new_name = os.path.join(destination_dir, new_name_without_ext + str(additional_number) + ext)
            # Finally rename picture
            os.rename(photo, full_new_name)
            print(photo + ' -> ' + full_new_name)
            # Add json data
            key = f'file_{i}'
            json_data[key] = {'OldName':photo, 'NewName' : full_new_name}
    # Dump json to file
    if(len(json_data) != 0):
        photosorter_dir = os.path.join(destination_dir, ".photosorter")
        os.makedirs(photosorter_dir, exist_ok=True)
        with open(os.path.join(photosorter_dir, f'{len(os.listdir(photosorter_dir))+1}.json'), 'w') as outfile:
            json.dump(json_data, outfile, indent=4)
    

def revert_directory(directory:str):
    photosorter_dir = os.path.join(directory, ".photosorter")
    reports_filenames = os.listdir(photosorter_dir)
    for report_filename in reversed(reports_filenames):
        full_report_filename = os.path.join(photosorter_dir,report_filename)
        with open(full_report_filename) as json_file:
            report = json.load(json_file)
            for picture_names in report.values():
                if os.path.isfile(picture_names['NewName']):
                    os.rename(picture_names['NewName'], picture_names['OldName'])
                    print(picture_names['NewName'] + ' -> ' + picture_names['OldName'])
        os.remove(full_report_filename)


def main():
    if args.directory is not None:
        directory = args.directory
        if args.revert:
            revert_directory(directory)
        else:
            process_directory(directory)
    else:
        start_gui()

if __name__ == "__main__":
    main()