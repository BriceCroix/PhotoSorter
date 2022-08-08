import os
import sys
import glob
import tkinter as tk
import tkinter.filedialog
import tkinter.ttk
import exifread
import json
import unidecode

from threading import Thread
from enum import Enum
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
#option_group = argparser.add_mutually_exclusive_group(required=False)
argparser.add_argument('-m', '--month', help='Classify files by month.', action='store_true')
argparser.add_argument('-y', '--year', help='Classify files by year.', action='store_true')
argparser.add_argument('-d', '--datetime_fallback', help='Fallback to date of file creation if EXIF is absent.', action='store_true')
args = argparser.parse_args()


################################### Constants & Enums ##############################################

PHOTOSORTER_SUBDIR = '.photosorter'

class SortByDir(Enum):
    SORT_BY_NONE = 0
    SORT_BY_YEAR = SORT_BY_NONE+1
    SORT_BY_MONTH = SORT_BY_YEAR+1
    SORT_BY_YEAR_AND_MONTH = SORT_BY_MONTH+1

class Translator:
    class Language(Enum):
        ENGLISH = -1
        FRENCH = 0

    # To add other languages, create an index, and fill all tuples in TRANSLATIONS at your index
    # In all cases, english is the key to all other languages
    FRENCH_IDX = 0
    TRANSLATIONS = {
        # First entry are the languages available
        'anglais':['francais'],
        'Photo Sorter':['Photo Sorter'],
        'Directory to process':['Dossier à traiter'],
        'Open directory':['Ouvrir dossier'],
        'Options':['Options'],
        'Use GPS data (slow)':['Utiliser données GPS (lent)'],
        'y/n':['o/n'],
        'Optional files suffix':['Suffixe optionnel'],
        'Sort in subdirectories':['Trier en sous-dossiers'],
        'Do not sort':['Ne pas trier'],
        'Year/':['Année/'],
        'Year-Month/':['Année-Mois/'],
        'Year/Month/':['Année/Mois/'],
        'Revert':['Restaurer'],
        'Start':['Start'],
        'App is ready':['Application prête'],
        'APP IS BUSY':['EXECUTION EN COURS'],
        'Info':['Info'],
        'Error':['Erreur'],
        'Please wait until operation is finished':['Merci d\'attendre la fin de l\'execution'],
        'Revert successful !':['Restauration réussie !'],
        'Nothing to revert in this directory':['Rien à restaurer dans ce dossier'],
        'An error occurred':['Une erreur est survenue'],
        'Please give directory to process':['Merci de fournir un dossier à traiter'],
        'Operation successful !':['Traitement réussi !'],
        'Language':['Langue'],
        'Use creation date when EXIF missing':['Utiliser date de creation si EXIF manquant']
    }

    def __init__(self, language:Language = Language.ENGLISH) -> None:
        self.language = language

    def translate(self, message:str) -> str:
        if self.language != Translator.Language.ENGLISH and (message in Translator.TRANSLATIONS.keys()):
            return Translator.TRANSLATIONS[message][self.language.value]
        else:
            return message


################################### GUI ############################################################

class PhotoSorterGui(tk.Tk):
    def __init__(self) -> None:
        self.translator = Translator(Translator.Language.ENGLISH)

        # Main window
        tk.Tk.__init__(self)
        self.title('Photo Sorter')
        self.geometry('640x480')
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Variables
        self.directory = tk.StringVar()
        self.language = tk.IntVar()
        self.language.set(Translator.Language.ENGLISH.value)
        self.fallback_datetime = tk.BooleanVar()
        self.fallback_datetime.set(False)
        self.use_gps = tk.BooleanVar()
        self.use_gps.set(True)
        self.suffix = tk.StringVar()
        self.suffix.set('')
        self.sort_by_dir = tk.IntVar()
        self.sort_by_dir.set(SortByDir.SORT_BY_NONE.value)
        self.busy = tk.BooleanVar()
        self.busy.set(False)

        # Directory frame
        self.directory_lblfrm = tk.LabelFrame(self)
        self.directory_lblfrm.pack(fill='x')

        self.directory_lbl = tk.Label(self.directory_lblfrm, textvariable=self.directory, relief='sunken')
        self.directory_lbl.pack(side=tk.RIGHT, fill='x', padx=10, pady=10, expand=True)
        self.open_dir_btn = tk.Button(self.directory_lblfrm, command=self.on_open_dir_btn_click)
        self.open_dir_btn.pack(side=tk.LEFT, pady=10)

        # Options frame
        self.options_lblfrm = tk.LabelFrame(self)
        self.options_lblfrm.pack(fill='both', pady=10)

        self.language_frm = tk.Frame(self.options_lblfrm)
        self.language_frm.pack(side=tk.TOP, fill='x')
        self.language_lbl = tk.Label(self.language_frm)
        self.language_lbl.pack(side=tk.LEFT)
        self.language_english_radiobtn = tk.Radiobutton(self.language_frm, text='english', variable=self.language, value=Translator.Language.ENGLISH.value, command=self.translate)
        self.language_english_radiobtn.pack(side=tk.RIGHT, padx=10)
        self.language_french_radiobtn = tk.Radiobutton(self.language_frm, text='francais', variable=self.language, value=Translator.Language.FRENCH.value, command=self.translate)
        self.language_french_radiobtn.pack(side=tk.RIGHT, padx=10)

        self.fallback_datetime_frm = tk.Frame(self.options_lblfrm)
        self.fallback_datetime_frm.pack(side=tk.TOP, fill='x')
        self.fallback_datetime_lbl = tk.Label(self.fallback_datetime_frm)
        self.fallback_datetime_lbl.pack(side=tk.LEFT)
        self.fallback_datetime_chk = tk.Checkbutton(self.fallback_datetime_frm, variable=self.fallback_datetime)
        self.fallback_datetime_chk.pack(side=tk.RIGHT, expand=True)

        self.gps_frm = tk.Frame(self.options_lblfrm)
        self.gps_frm.pack(side=tk.TOP, fill='x')
        self.gps_lbl = tk.Label(self.gps_frm)
        self.gps_lbl.pack(side=tk.LEFT)
        self.gps_chk = tk.Checkbutton(self.gps_frm, variable=self.use_gps)
        self.gps_chk.pack(side=tk.RIGHT, expand=True)

        self.suffix_frm = tk.Frame(self.options_lblfrm)
        self.suffix_frm.pack(side=tk.TOP, fill='x')
        self.suffix_lbl = tk.Label(self.suffix_frm)
        self.suffix_lbl.pack(side=tk.LEFT)
        self.suffix_entry = tk.Entry(self.suffix_frm, textvariable=self.suffix, width=50)
        self.suffix_entry.pack(side=tk.RIGHT, fill='x', expand=True, padx=10)

        self.sort_by_dir_frm = tk.Frame(self.options_lblfrm)
        self.sort_by_dir_frm.pack(side=tk.TOP, fill='x')
        self.sort_by_dir_lbl = tk.Label(self.sort_by_dir_frm)
        self.sort_by_dir_lbl.pack(side=tk.LEFT)
        self.sort_by_dir_none_radiobtn = tk.Radiobutton(self.sort_by_dir_frm, variable=self.sort_by_dir, value=SortByDir.SORT_BY_NONE.value)
        self.sort_by_dir_none_radiobtn.pack(side=tk.RIGHT, padx=10)
        self.sort_by_dir_year_radiobtn= tk.Radiobutton(self.sort_by_dir_frm, variable=self.sort_by_dir, value=SortByDir.SORT_BY_YEAR.value)
        self.sort_by_dir_year_radiobtn.pack(side=tk.RIGHT, padx=10)
        self.sort_by_dir_month_radiobtn = tk.Radiobutton(self.sort_by_dir_frm, variable=self.sort_by_dir, value=SortByDir.SORT_BY_MONTH.value)
        self.sort_by_dir_month_radiobtn.pack(side=tk.RIGHT, padx=10)
        self.sort_by_dir_year_and_month_radiobtn = tk.Radiobutton(self.sort_by_dir_frm, variable=self.sort_by_dir, value=SortByDir.SORT_BY_YEAR_AND_MONTH.value)
        self.sort_by_dir_year_and_month_radiobtn.pack(side=tk.RIGHT, padx=10)

        # Start frame
        self.start_lblfrm = tk.LabelFrame(self, text='')
        self.start_lblfrm.pack(side=tk.BOTTOM, fill='x')
        
        self.start_frm = tk.Frame(self.start_lblfrm)
        self.start_frm.pack(side=tk.TOP, fill='x')
        self.revert_btn = tk.Button(self.start_lblfrm, command=self.on_revert_btn_click)
        self.revert_btn.pack(side=tk.LEFT, padx=10, pady=10)
        self.start_btn = tk.Button(self.start_lblfrm, command=self.on_start_btn_click)
        self.start_btn.pack(side=tk.RIGHT, padx=10, pady=10)
        self.busy_lbl = tk.Label(self.start_lblfrm, bg='green', borderwidth=2, relief="sunken")
        self.busy_lbl.pack(side=tk.BOTTOM, fill='both', expand=True)

        # Launch mainloop
        self.translate()
        self.mainloop()

    def translate(self):
        self.translator.language = Translator.Language(self.language.get())
        self.directory_lblfrm.config(text=self.translator.translate('Directory to process'))
        self.open_dir_btn.config(text=self.translator.translate('Open directory'))
        self.options_lblfrm.config(text=self.translator.translate('Options'))
        self.language_lbl.config(text=self.translator.translate('Language'))
        self.fallback_datetime_lbl.config(text=self.translator.translate('Use creation date when EXIF missing'))
        self.fallback_datetime_chk.config(text=self.translator.translate('y/n'))
        self.gps_lbl.config(text=self.translator.translate('Use GPS data (slow)'))
        self.gps_chk.config(text=self.translator.translate('y/n'))
        self.suffix_lbl.config(text=self.translator.translate('Optional files suffix'))
        self.sort_by_dir_lbl.config(text=self.translator.translate('Sort in subdirectories'))
        self.sort_by_dir_month_radiobtn.config(text=self.translator.translate('Year-Month/'))
        self.sort_by_dir_year_radiobtn.config(text=self.translator.translate('Year/'))
        self.sort_by_dir_year_and_month_radiobtn.config(text=self.translator.translate('Year/Month/'))
        self.sort_by_dir_none_radiobtn.config(text=self.translator.translate('Do not sort'))
        self.revert_btn.config(text=self.translator.translate('Revert'))
        self.start_btn.config(text=self.translator.translate('Start'))
        self.busy_lbl.config(text=self.translator.translate('App is ready' if not self.busy.get() else 'APP IS BUSY'))


    def on_exit(self):
        if self.busy.get():
            tk.messagebox.showinfo(self.translator.translate('Info'), self.translator.translate('Please wait until operation is finished'))
        else:
            self.destroy()

    def on_open_dir_btn_click(self):
        self.directory.set(tk.filedialog.askdirectory())

    def on_revert_btn_click(self):
        if self.directory.get() != '':
            self.enable_disable(self.start_btn, False)
            self.enable_disable(self.revert_btn, False)
            self.busy_lbl.config(bg='red', text=self.translator.translate('APP IS BUSY'))
            self.busy.set(True)
            job = Thread(target=self.revert_directory_thread)
            job.start()
            # res = revert_directory(self.directory.get())
            # self.enable_disable(self.start_btn, True)
            # self.enable_disable(self.revert_btn, True)
            # self.busy_lbl.config(bg='green', text=self.translator.translate('App is ready'))
            # self.busy.set(False)
            # if res == 0:
            #     tk.messagebox.showinfo(self.translator.translate('Info'), self.translator.translate('Revert successful !'))
            # elif res == 1:
            #     tk.messagebox.showerror(self.translator.translate('Error'), self.translator.translate('Nothing to revert in this directory'))
            # else:
            #     tk.messagebox.showerror(self.translator.translate('Error'), self.translator.translate('An error occurred'))
        else:
            tk.messagebox.showerror(self.translator.translate('Error'), self.translator.translate('Please give directory to process'))

    def revert_directory_thread(self):
        res = revert_directory(self.directory.get())
        self.enable_disable(self.start_btn, True)
        self.enable_disable(self.revert_btn, True)
        self.busy_lbl.config(bg='green', text=self.translator.translate('App is ready'))
        self.busy.set(False)
        if res == 0:
            tk.messagebox.showinfo(self.translator.translate('Info'), self.translator.translate('Revert successful !'))
        elif res == 1:
            tk.messagebox.showerror(self.translator.translate('Error'), self.translator.translate('Nothing to revert in this directory'))
        else:
            tk.messagebox.showerror(self.translator.translate('Error'), self.translator.translate('An error occurred'))

    def on_start_btn_click(self):
        if self.directory.get() != '':
            self.enable_disable(self.start_btn, False)
            self.enable_disable(self.revert_btn, False)
            self.busy_lbl.config(bg='red', text=self.translator.translate('APP IS BUSY'))
            self.busy.set(True)
            job = Thread(target=self.process_directory_thread)
            job.start()
            #process_directory(self.directory.get(), self.use_gps.get(), self.suffix.get(), SortByDir(self.sort_by_dir.get()))
            #self.enable_disable(self.start_btn, True)
            #self.enable_disable(self.revert_btn, True)
            #self.busy_lbl.config(bg='green', text=self.translator.translate('App is ready'))
            #self.busy.set(False)
            #tk.messagebox.showinfo(self.translator.translate('Info'), self.translator.translate('Operation successful !'))
        else:
            tk.messagebox.showerror(self.translator.translate('Error'), self.translator.translate('Please give directory to process'))
        
    def process_directory_thread(self):
        process_directory(self.directory.get(), self.use_gps.get(), self.suffix.get(), SortByDir(self.sort_by_dir.get()), self.fallback_datetime.get())
        self.enable_disable(self.start_btn, True)
        self.enable_disable(self.revert_btn, True)
        self.busy_lbl.config(bg='green', text=self.translator.translate('App is ready'))
        self.busy.set(False)
        tk.messagebox.showinfo(self.translator.translate('Info'), self.translator.translate('Operation successful !'))

    def enable_disable(self, element, enabled:bool):
        element['state'] = tk.NORMAL if enabled else tk.DISABLED
        

################################### Methods ########################################################

def start_gui():
    print("Starting GUI...")
    PhotoSorterGui()
    print("GUI closed.")


def path_safe_name(name:str):
    # Remove accents on letters
    result = unidecode.unidecode(name)
    # Choose first name in case of two choices 'NameA / NameB'
    result = result.split('/')[0]
    # Remove unwanted characters
    for char in '-:,. ':
        result = result.replace(char, '')
    return result


def process_directory(directory:str, use_gps:bool=False, suffix:str='', sort_by_dir:SortByDir=SortByDir.SORT_BY_NONE, datetime_fallback_os:bool=False):
    # Match all jpeg files
    photo_pathnames = []
    for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
        photo_pathnames.extend(glob.glob(os.path.join(directory, ext)))
    photo_pathnames = sorted(photo_pathnames)
    # For each photo
    # 0 : list of old paths, 1 : list of new paths
    name_pairs = [[],[]]
    for i in range(len(photo_pathnames)):
        # Convert paths to absolute path
        photo_pathnames[i] = os.path.abspath(photo_pathnames[i])
        photo_pathname = photo_pathnames[i]

        try:
            exif_data = exifread.process_file(open(photo_pathname, 'rb'))

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
                    # Make name path-proof
                    country = path_safe_name(country)
                    if 'town' in location.raw['address']:
                        town = location.raw['address']['town']
                    elif 'village' in location.raw['address']:
                        town = location.raw['address']['village']
                    elif 'municipality' in location.raw['address']:
                        town = location.raw['address']['municipality']
                    else:
                        town = ''
                    town = path_safe_name(town)

            # Recover datetime object, fallback to date of creation of file if exif tag absent
            if 'Image DateTime' in exif_data.keys():
                date_time_obj = datetime.strptime(exif_data['Image DateTime'].values, '%Y:%m:%d %H:%M:%S')
            else:
                print('Missing datetime EXIF for ' + photo_pathname)
                if datetime_fallback_os:
                    date_time_obj = datetime.fromtimestamp(os.path.getmtime(photo_pathname))
                else:
                    continue

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
            destination_dir = os.path.dirname(photo_pathname)
            subdestination_dir = destination_dir
            if sort_by_dir == SortByDir.SORT_BY_YEAR:
                subdir_name = f'{date_time_obj.year:04}'
                subdestination_dir = os.path.join(destination_dir, subdir_name)
            elif sort_by_dir == SortByDir.SORT_BY_MONTH:
                subdir_name = f'{date_time_obj.year:04}-{date_time_obj.month:02}'
                subdestination_dir = os.path.join(destination_dir, subdir_name)
            elif sort_by_dir == SortByDir.SORT_BY_YEAR_AND_MONTH:
                subdir_name = os.path.join(f'{date_time_obj.year:04}', f'{date_time_obj.month:02}')
                subdestination_dir = os.path.join(destination_dir, subdir_name)
            os.makedirs(subdestination_dir, exist_ok=True)
            new_pathname = os.path.join(subdestination_dir, new_name)
            # Same pair oldname->newname
            name_pairs[0].append(photo_pathname)
            name_pairs[1].append(new_pathname)
        except Exception as e:
            print(e, file=sys.stderr)

    # Handle name duplicates
    for i in range(len(name_pairs[1])):
        new_pathname = name_pairs[1][i]
        # Count number of photos meant to be renamed with identical name
        new_pathname_occurences = name_pairs[1].count(new_pathname)
        # Each path should be unical
        if new_pathname_occurences == 1:
            continue
        else:
            # Recover indices of matching pathnames
            indices_of_matching_pathnames = []
            for k in range(len(name_pairs[1])):
                if name_pairs[1][k] == new_pathname:
                    indices_of_matching_pathnames.append(k)
            # For each of these files sharing same name, recover a 'second of creation'
            creation_second = []
            for matching_index in indices_of_matching_pathnames:
                old_pathname = name_pairs[0][matching_index]
                # recover exact moment of creation according to exif data and os
                exif_data = exifread.process_file(open(old_pathname, 'rb'))
                if 'Image DateTime' in exif_data.keys():
                    date_time_exif = datetime.strptime(exif_data['Image DateTime'].values, '%Y:%m:%d %H:%M:%S')
                else:
                    date_time_exif = datetime.fromtimestamp(os.path.getmtime(photo_pathname))
                date_time_os = datetime.fromtimestamp(os.path.getmtime(photo_pathname))
                creation_second.append(date_time_exif.second + 0.01*(date_time_os.second + 1e-3 * date_time_os.microsecond))
            # Now order these files
            order_integer_suffix = 1
            while len(indices_of_matching_pathnames) != 0:
                index_of_index_of_first_pic = creation_second.index(min(creation_second))
                index_of_first_pic = indices_of_matching_pathnames[index_of_index_of_first_pic]
                new_pathname_to_be_revised = name_pairs[1][index_of_first_pic]
                new_pathname_without_ext, ext = os.path.splitext(new_pathname_to_be_revised)
                name_pairs[1][index_of_first_pic] = new_pathname_without_ext + f'-{order_integer_suffix}' + ext
                indices_of_matching_pathnames.pop(index_of_index_of_first_pic)
                creation_second.pop(index_of_index_of_first_pic)
                order_integer_suffix += 1
    # Finally rename files
    json_data = {}
    for i in range(len(name_pairs[1])):
        try:
            old_pathname = name_pairs[0][i]
            new_pathname = name_pairs[1][i]
            if old_pathname != new_pathname: 
                if not os.path.isfile(new_pathname):
                    os.rename(old_pathname, new_pathname)
                    print('Renamed : ' +  old_pathname + ' -> ' + new_pathname)
                    # Add json data
                    key = f'file_{i}'
                    json_data[key] = {'OldName' : old_pathname, 'NewName' : new_pathname}
                else:
                    print("Error : new name already exists : " + old_pathname + ' -> ' + new_pathname, file=sys.stderr)
        except Exception as e:
            print(e, file=sys.stderr)
    
    # Dump json to file
    if(len(json_data) != 0):
        photosorter_dir = os.path.join(destination_dir, PHOTOSORTER_SUBDIR)
        os.makedirs(photosorter_dir, exist_ok=True)
        with open(os.path.join(photosorter_dir, f'{len(os.listdir(photosorter_dir))+1}.json'), 'w') as outfile:
            json.dump(json_data, outfile, indent=4)
    

def remove_empty_directories(directory:str):
    for entry in os.scandir(directory):
        if os.path.isdir(entry.path):
            remove_empty_directories(entry.path)
            if not os.listdir(entry.path):
                os.rmdir(entry.path)


def revert_directory(directory:str) -> int:
    """
    @return 0 for success, 1 if cannot find .photosorter directory, -1 for unknown error.
    """
    try:
        photosorter_dir = os.path.join(directory, PHOTOSORTER_SUBDIR)
        if not os.path.isdir(photosorter_dir):
            return 1
        reports_filenames = sorted(os.listdir(photosorter_dir))
        for report_filename in reversed(reports_filenames):
            full_report_filename = os.path.join(photosorter_dir,report_filename)
            with open(full_report_filename) as json_file:
                report = json.load(json_file)
                for picture_names in report.values():
                    try:
                        if os.path.isfile(picture_names['NewName']):
                            os.rename(picture_names['NewName'], picture_names['OldName'])
                            print(picture_names['NewName'] + ' -> ' + picture_names['OldName'])
                    except Exception as e:
                        print(e, file=sys.stderr)
            try:
                os.remove(full_report_filename)
            except Exception as e:
                print(e, file=sys.stderr)

        # Remove empty directories left by revert
        remove_empty_directories(directory)
        return 0
    except Exception as e:
        print(e, file=sys.stderr)
        return -1


################################### Main ###########################################################

def main():
    if args.directory is not None:
        directory = args.directory
        if args.revert:
            revert_directory(directory)
        else:
            suffix = '' if args.suffix is None else args.suffix
            sort_by_dir = SortByDir.SORT_BY_NONE
            if args.year and args.month:
                sort_by_dir = SortByDir.SORT_BY_YEAR_AND_MONTH
            elif args.year:
                sort_by_dir = SortByDir.SORT_BY_YEAR
            elif args.month:
                sort_by_dir = SortByDir.SORT_BY_MONTH
            process_directory(directory, args.gps, suffix, sort_by_dir, datetime_fallback_os=args.datetime_fallback)
    else:
        start_gui()

if __name__ == "__main__":
    main()