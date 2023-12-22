# PhotoSorter

## About

PhotoSorter is a very simple desktop app meant to help you sort your pictures
(yes we all have this *temporary* folder).
Simply provide a directory with pictures to sort and let the magic begin !
You can use PhotoSorter with only terminal commands but a simple user
interface is also available when run with no arguments.
Do not be afraid, all the changes made to your pictures (name and subdirectory only)
are revertible using the "Revert" button or the `--revert` option.
For more information please use the `--help` option.

This app does not collect any data and does not modify your files in any way,
it only moves them in adequate directories and gives them meaningful names for us human-being.

## How to use

1. Provide a directory where all your to-be-sorted pictures are located.
2. Select the sorting options you desire.
3. Select whether you want your picture names to include location.
4. Select whether you want the app to use the date of creation of the file if the picture does not contain information about its date.
5. Optionally add a suffix to be added to all of your pictures.
6. Click "Process" and **wait for the app to return**.
7. *Et voilà*
8. Not satisfied ? Click on "Revert" and start over !

## Developer's corner

Configure virtual environment :

- On windows :
```shell
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

- On linux :
```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you need to install new packages, please update and commit the `requirements.txt` as follows :

```shell
pip install my_new_package
pip freeze > requirements.txt
```

You are now ready to execute the GUI with :

```shell
python3 photosorter.py
```

Or directly :
```shell
python3 photosorter.py path/to/my/photos
```


The executable `photosorter` can be compiled to a single executable with [pyinstaller](https://pypi.org/project/pyinstaller/) :

- On linux :
```shell

```

- On windows :
```shell
pyinstaller --clean --onefile --paths .venv\Lib\site-packages --paths . --name "photosorter" photosorter.py
```