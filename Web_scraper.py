import sys, logging, os

import osfclient
import re
import requests

from osfclient.utils import checksum
from tqdm import tqdm

from bs4 import BeautifulSoup
from selenium import webdriver

# used for update argument from user
true_set = {"true", "yes", "y", "t", '1'}

# following variables are used for replacing special characters in regex to escaped sequences
regex_sp_chars = ".^$*+?{}[]\|()"
regex_rep_chars = ["\.", "\^", "\$", "\*", "\+", "\?", "\{", "\}"
    , "\[", "\]", "\\", "\|", "\(", "\)"]

# function to download all files present in the provided url
# download_loc : location on the PC where data is downloaded
# update : when false, then prevent downloading if same files
# are present in the location. When true, replace the files if present.
def download_data(url, download_loc, update):
    split_url = url.split('/')
    project_id = ''

    if not os.path.exists(download_loc):
        os.makedirs(download_loc)

    if len(split_url[-1]) == 0:
        project_id = split_url[-2]
    else:
        project_id = split_url[-1]

    osf = osfclient.OSF()

    # get the project object from osf client
    project = osf.project(project_id)
    local_filename = project.title

    file_path = os.path.join(download_loc, local_filename)

    try:
        # file downloader
        with tqdm(unit='files') as pbar:
            for store in project.storages:
                for file_ in store.files:
                    download_error = False
                    path = file_.path
                    if path.startswith('/'):
                        path = path[1:]

                    path = os.path.join(file_path, path)
                    if os.path.exists(path):
                        if not update and checksum(path) == file_.hashes.get('md5'):
                            print()
                            print("{} is present at location {}".format(file_.path, path))
                            continue
                        elif update and checksum(path) == file_.hashes.get('md5'):
                            print()
                            print("Updating file {} at location {}".format(file_.path, path))
                    directory, _ = os.path.split(path)
                    os.makedirs(directory, exist_ok=True)

                    try:
                        with open(path, "wb") as f:
                            file_.write_to(f)
                    except Exception as e:
                        logging.debug(e)
                        download_error = True

                    if download_error:
                        print()
                        logging.debug("Downloading again: {}".format(file_.path))
                        os.remove(path)
                        resp = requests.get(file_._download_url, stream=True)
                        total_size = int(resp.headers.get('content-length', 0))
                        block_size = 1024 * 1024
                        with tqdm(total=total_size, unit="MiB", unit_scale=True) as bar:
                            with open(path, "wb") as f:
                                for data in resp.iter_content(block_size):
                                    f.write(data)

                    pbar.update()
    except Exception as e:
        logging.debug(e)

# find the dataset given its name, and fetch the URL to it's corresponding project in OSF website
def extract_data(dataset):

    # Url in which all open-source psychometric experiments are present
    url = ("https://airtable.com/appgK8KJ2DzXYcPKG/shr6c9YY6Mmsn22Ib/tblmBVweDFoVSPDIA")
    driver = webdriver.Chrome()
    driver.get(url)
    urls = []

    for i in range(len(regex_sp_chars)):
        c = regex_sp_chars[i]
        dataset = dataset.replace(c, regex_rep_chars[i])

    html = driver.page_source

    # Open page in beautiful soup parser
    parser = BeautifulSoup(html, features="html.parser")
    logging.debug('Parser contents: ')
    logging.debug(parser.contents)

    # get the pane containing experiments name
    left_pane = parser.select('div.dataRow.leftPane')

    # get URLs for experiments on OSF website
    right_pane = parser.select('div.dataRow.rightPane')
    ind = 0
    for element in left_pane:
        logging.debug(element)
        if element.find(string=re.compile(dataset)) is not None:
            break
        ind += 1
    if ind < len(left_pane):
        element = right_pane[ind]
        regex = re.compile(r"https://osf.io")

        # find URLs after finding the required Experiment
        url = element.find(name="span", attrs={"class": "url"}, string=regex)
        if url is None:
            logging.error("No links found for dataset {}".format(dataset))
        else:
            print("links found: " + str(url.text))
            urls.append(url.text)
    else:
        logging.error("No links found for dataset {}".format(dataset))
    driver.quit()

    return urls


if __name__ == '__main__':
    # dataset name
    dataset = sys.argv[1]

    # download location
    download_loc = sys.argv[2]
    update = False
    if len(sys.argv) == 4:

        # update variable
        argument = sys.argv[3]
        if argument.lower() in true_set:
            update = True
    elif len(sys.argv) != 3:
        logging.error("Wrong number of arguments: {}".format(len(sys.argv)))
        logging.error("Correct order of arguments are: dataset name, and download_loc")
        sys.exit(1)
    urls = extract_data(dataset)
    for url in urls:
        download_data(url, download_loc, update)
