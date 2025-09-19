from enum import Enum
import json
import random
import string
import os
import logging
from bidict import bidict
import shutil
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.DEBUG)

LOW_ARTICLES = [
    "OTHER PROJECT 1",
    "OTHER PROJECT 2",
    "OTHER PROJECT 3",
    "OTHER PROJECT 4",
]

MEDIUM_ARTICLES = [
    "MAIN ARTICLE 1",
    "MAIN ARTICLE 2",
    "MAIN ARTICLE 3",
    "MAIN ARTICLE 4",
]

HIGH_ARTICLES = [
    "MAIN ARTICLE LR 1",
]

IDPKG_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
SPREAD_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/Spread"

ET.register_namespace("idPkg", IDPKG_NS)
ET.register_namespace("", SPREAD_NS)


class ArticleImportance(Enum):
    LOW = 1  # leads to Other Project
    MEDIUM = 2  # leads to Main Article
    HIGH = 3  # leads to Main Aricle LR


def generate_file_uid(stories_folder_path: str, spreads_folder_path: str):
    """creates a random uid for new story or spread
    makes sure there is no collision with already existing uids

    Args:
        stories_folder_path (str): path to the stories folder
        spreads_folder_path (str): path to the spreads folder

    Returns:
        str: a unique random uid
    """

    already_existing_uids = set()
    for folder in [stories_folder_path, spreads_folder_path]:
        for filename in os.listdir(folder):
            if filename.endswith(".xml"):
                uid = filename.split(".")[0].split("_")[-1]
                already_existing_uids.add(uid)

    length = 4
    random_uid = "u" + "".join(
        random.choices(string.ascii_letters + string.digits, k=length)
    )

    while random_uid in already_existing_uids:
        random_uid = "u" + "".join(
            random.choices(string.ascii_letters + string.digits, k=length)
        )

    return random_uid


def get_current_number_of_pages(spreads_folder_path: str):

    n_spreads = len(
        [name for name in os.listdir(spreads_folder_path) if os.path.isfile(name)]
    )
    logging.debug("Number of spreads: %d", n_spreads)
    is_multiple_of_8 = n_spreads % 8 == 0
    logging.debug("Is this a multiple of 8? %s", is_multiple_of_8)
    return n_spreads


def create_new_spread(
    spreads_folder_path: str,
    new_spread_uid: str,
    selected_template: str,
):
    # TODO: make sure that the .json are all up to date
    story_token_mapping = json.loads("story_token_mapping.json")
    spread_story_mapping = bidict(json.loads("spread_story_mapping.json"))
    story_spread_mapping = spread_story_mapping.inverse

    relevant_story_uid = story_token_mapping["[" + selected_template + "]"]
    relevant_spread_uid = story_spread_mapping[relevant_story_uid]

    # create a copy of the spread with a new uid
    template_spread_path = (
        spreads_folder_path + "/Spread_" + relevant_spread_uid + ".xml"
    )
    new_spread_path = spreads_folder_path + "/Spread_" + new_spread_uid + ".xml"
    shutil.copyfile(
        template_spread_path,
        new_spread_path,
    )

    # count number of pages in the new doc
    tree = ET.parse(new_spread_path)
    page_count = len(tree.findall(".//Page"))
    logging.debug("Number of Page tags: %d", page_count)

    # update designmap.xml
    tree = ET.parse("designmap.xml")
    root = tree.getroot()


def create_new_stories():
    pass


def choose_template(article_importance: ArticleImportance):
    """chooses the best template according to the article importance"""
    match article_importance:
        case ArticleImportance.LOW:
            return random.choice(LOW_ARTICLES)
        case ArticleImportance.MEDIUM:
            return random.choice(MEDIUM_ARTICLES)
        case ArticleImportance.HIGH:
            return random.choice(HIGH_ARTICLES)


def create_new_page():
    pass
