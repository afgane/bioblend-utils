import getopt
import logging as log
import os
import re
import requests
import sys
import yaml

from urllib.parse import urlparse

from bioblend.galaxy import GalaxyInstance

def create_library(gi, lib_name, lib_description):
    """
    Create a data library if one does not exist and return it.

    Check if a library by `lib_name` exists or create a new one. Note that in
    Galaxy multiple libraries can have the same name so this will return the
    first matching one.
    """
    for lib in gi.libraries.get_libraries():
        if lib['name'] == lib_name:
            log.info("Found existing library '%s', id '%s'." % (lib['name'], lib['id']))
            return lib
    log.info("Creating library '%s'..." % lib_name)
    lib = gi.libraries.create_library(lib_name, lib_description)
    log.info("Library '%s' (%s) created." % (lib['name'], lib['id']))
    return lib

def upload_data(gi, lib, data_manifest):
    """
    Upload the data defined in the data manifest.

    The data manifest is a YAML object with the following structure:
    ```
    datasets:
        - name: file_name.txt
          url: https://public-url.org/file1
          folder_name: folder-name-where-to-place-this-file
          folder_description: folder-description
          type: optional-file-type
          dbkey: optional-genome-build-for-the-file
    ```
    """
    def _get_folder(folder_name, folder_description):
        """
        Check if the provided folder exists and create it if not.
        """
        for folder in gi.libraries.get_folders(lib['id']):
            fname = folder['name'].split('/')[-1]
            if fname == folder_name:
                log.info("Found existing folder '%s', id '%s'." % (fname, folder['id']))
                return folder
        log.info("Creating folder '%s'..." % folder_name)
        folder = gi.libraries.create_folder(
            lib['id'], folder_name, folder_description)[0]
        log.info("Folder '%s' (%s) created." % (folder['name'], folder['id']))
        return folder

    def _dataset_missing(folder, dataset):
        datasets = [content for content in gi.libraries.show_library(lib['id'], contents=True) if content['type']=='file']
        path = os.path.join(folder['name'], dataset['name'])
        ds = [dataset for dataset in datasets if dataset['name'] == path]
        if ds:
            log.info("Dataset '%s' already exists." % path)
            return False
        return True

    def _upload_dataset(folder, dataset):
        """
        Upload the supplied dataset to the folder.
        """
        log.info("Uploading file from url %s" % dataset['url'])
        gds = gi.libraries.upload_file_from_url(
            library_id=lib['id'],
            file_url=dataset['url'],
            folder_id=folder['id'],
            file_type=dataset.get('type', 'auto'),
            dbkey=dataset.get('dbkey', '?')
        )[0]
        gi.libraries.wait_for_dataset(
            library_id=lib['id'],
            dataset_id=gds['id'],
            maxwait=600
        )
        log.info("Setting datset '%s' name to '%s'." % (gds['id'], dataset['name']))
        gi.libraries.update_library_dataset(dataset_id=gds['id'], name=dataset['name'])
        log.info("Dataset '%s' (%s) uploaded." % (gds['name'], gds['id']))

    for dataset in data_manifest.get('datasets', []):
        folder = _get_folder(dataset['folder_name'], dataset['folder_description'])
        if _dataset_missing(folder, dataset):
            gds = _upload_dataset(folder, dataset)
    log.info("Done uploading data to library '%s'." % lib['name'])

def is_url(string):
    """
    Check if the provided string is a URL.
    """
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, string) is not None

def print_help():
    script_name = sys.argv[0]
    help = f"""
python {script_name} -g galaxy_server -a api_key -l library_name -d library_description -m manifest_file

Tha manifest file can be either a URL to a file or a local file. Either way,
the format of the manifest file needs to have the following structure:

datasets:
  - name: RefSeq_reference_DSv2.gtf
    url: 'https://ea1-usegvl-org-gvl-data.s3.amazonaws.com/GTFs/RefSeq_reference_DSv2.gtf'
    folder_name: GTFs
    folder_description: A collection of GTF files
    type: gtf
    dbkey: mm10

All listed arguments are required.
    """
    print(help, file=sys.stderr)

class RequiredOptions:
    """
    Keep track of required options.
    """

    def __init__(self, options=[]):
        self.required_options = options

    def resolve(self, option):
        if option in self.required_options:
            self.required_options.remove(option)

    def optionsResolved(self):
        if len(self.required_options):
            return False
        else:
            return True

def main():
    log.basicConfig(stream=sys.stdout, level=log.INFO, format='%(asctime)s - %(message)s')

    short_options = "hg:a:l:d:m:"
    long_options = ["help", "galaxy=", "api_key=", "library_name=", "description=", "manifest="]
    # The following assumes all but the first option lisetd in long_options is requried
    required_options = RequiredOptions([o.rstrip('=') for o in long_options[1:]])
    try:
        arguments, values = getopt.getopt(sys.argv[1:], short_options, long_options)
    except getopt.error as err:
        log.error("Error parsing arguments: %s" % err)
        sys.exit(2)
    for current_argument, current_value in arguments:
        if current_argument in ("-g", "--galaxy"):
            galaxy = current_value
            required_options.resolve('galaxy')
        elif current_argument in ("-a", "--api_key"):
            api_key = current_value
            required_options.resolve('api_key')
        elif current_argument in ("-l", "--library_name"):
            lib_name = current_value
            required_options.resolve('library_name')
        elif current_argument in ("-d", "--library_description"):
            lib_description = current_value
            required_options.resolve('description')
        elif current_argument in ("-m", "--manifest"):
            data_manifest = current_value
            required_options.resolve('manifest')
        elif current_argument in ("-h", "--help"):
            print_help()
            sys.exit(0)
    # Verify that all of the required options have been specified
    if not required_options.optionsResolved():
        print("Required option(s) missing: " + ', '.join(required_options.required_options))
        print_help()
        sys.exit(1)

    if is_url(data_manifest):
        r = requests.get(data_manifest)
        data_manifest = 'dm.yaml'
        with open(data_manifest, 'wb') as f:
            f.write(r.content)
    with open(data_manifest) as f:
        data_manifest = yaml.safe_load(f)
    gi = GalaxyInstance(galaxy, api_key)
    lib_name = lib_name
    lib_description = lib_description

    lib = create_library(gi, lib_name, lib_description)
    upload_data(gi, lib, data_manifest)

if __name__ == "__main__":
    main()
