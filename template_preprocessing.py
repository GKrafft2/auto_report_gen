import xml.etree.ElementTree as ET
import os
import json
import re
import logging


TEMPLATE_TOKENS = {
    "MAIN TITLE",
    "MAIN YEAR",
    "CONTENTS",
    "MESSAGE FROM THE PRESIDENT",
    "WHO WE ARE",
    "FIGURES",
    "PROJECTS SUPPORTED INTRO",
    "MAIN ARTICLE 1",
    "MAIN ARTICLE 2",
    "MAIN ARTICLE 3",
    "MAIN ARTICLE 4",
    "MAIN ARTICLE LR 1",
    "OTHER PROJECTS SUPPORTED",
    "OTHER PROJECT 1",
    "OTHER PROJECT 2",
    "OTHER PROJECT 3",
    "OTHER PROJECT 4",
    "COMPLETED PROJECTS",
    "COMPLETED PROJECT 1",
    "COMPLETED PROJECT 2",
    "COMPLTED PROJECT 3",
    "OUTLOOK",
}

logging.basicConfig(level=logging.CRITICAL)


def get_all_text_from_story(story_path: str):
    """Gets all the text contained in a story
    Works by fusing all the elements contained under the Content tags

    Args:
        story_path (str): path to the story xml file

    Returns:
        str: all the text contained in the story as a single string
    """
    logging.info(f"Processing story for text: {story_path}")
    with open(story_path, encoding="utf-8") as f:
        tree = ET.parse(f)
        root = tree.getroot()

    parts = []  # Iterate in document order through Story subtree
    for node in root.iter():
        tag = node.tag.split("}", 1)[-1]  # strip namespace if present
        if tag == "Content":
            if node.text:
                parts.append(node.text)
        elif tag == "Br":
            parts.append("\n")

    text = "".join(parts)
    return text


def get_all_parentstory_from_spread(spread_path: str):
    """Gets all the ParentStory IDs contained in a spread

    Args:
        spread_path (str): path to the spread xml file

    Returns:
        list: list of all the ParentStory IDs contained in the spread
    """
    logging.info(f"Processing story for text: {spread_path}")
    with open(spread_path, encoding="utf-8") as f:
        tree = ET.parse(f)
        root = tree.getroot()

    parts = []  # Iterate in document order through Story subtree
    for node in root.iter():
        tag = node.tag.split("}", 1)[-1]  # strip namespace if present
        if tag == "TextFrame":
            if node.attrib.get("ParentStory"):
                parts.append(node.attrib.get("ParentStory"))

    return parts


def match_tokens_in_text(text: str):
    """Matches the template tokens in the text
    works by using regex to find the tokens in the text, searches for all template tokens defined in TEMPLATE_TOKENS and searches for the matches that includes square braces and text extensions
    it will for exampl match [MAIN ARTICLE 3 - text 1] or [MAIN ARTICLE 3]

    Args:
        text (str): text to search for template tokens

    Returns:
        list: list of matched template tokens
    """
    pattern = re.compile(
        r"\[(?:" + "|".join(map(re.escape, TEMPLATE_TOKENS)) + r").*?\]"
    )
    matches = pattern.findall(text)

    if len(matches) == 0:
        logging.debug(f"No template tokens found in text")

    if len(matches) > 1:
        logging.debug(f"Multiple template tokens found in text")

    return matches


def get_story_uid(story_path: str):
    return story_path.split("/")[-1].split(".")[0].split("_")[-1]


def compute_word_count_per_text():
    """computes the number of words per text by summing up the number of words in the sections that belong to the same text
    Reads from num_words_per_section.json and writes to num_words_per_text.json
    Adds up only the texts and not the titles or contries for example
    """
    num_words_per_text = {}
    text_token = "text"

    with open("num_words_per_section.json", "r") as f:
        num_words_per_block = json.load(f)
        for key, value in num_words_per_block.items():
            for token in TEMPLATE_TOKENS:
                if token in key and text_token in key:
                    if token not in num_words_per_text:
                        num_words_per_text[token] = value
                    else:
                        num_words_per_text[token] += value
                    break
        json.dump(num_words_per_text, open("num_words_per_text.json", "w"), indent=4)


def create_json_ressources(stories_folder: str, spreads_folder: str):
    """creates the following json files:
        - num_words_per_section.json: contains the number of words per section (section identified by tokens based on TEMPLATE_TOKENS - hence finds also the tokesn of texts etc...)
        - story_token_mapping.json: contains a mapping from section token to story uid (to be able to find the story in the xml)

    Args:
        stories_folder (str): folder containing the stories in XML format
    """
    word_count_dict = {}
    story_token_dict = {}

    for story in os.listdir(stories_folder):
        logging.info(f"Processing story: {story}")
        story_path = os.path.join(stories_folder, story)
        text = get_all_text_from_story(story_path)
        matches = match_tokens_in_text(text)
        num_words = len(text.split(" "))
        if len(matches) == 1:
            word_count_dict[matches[0]] = num_words
            story_token_dict[matches[0]] = get_story_uid(story_path)

    word_count_dict = dict(sorted(word_count_dict.items()))
    story_token_dict = dict(sorted(story_token_dict.items()))

    with open("num_words_per_section.json", "w") as f:
        json.dump(word_count_dict, f, indent=4)

    with open("story_token_mapping.json", "w") as f:
        json.dump(story_token_dict, f, indent=4)

    compute_word_count_per_text()

    spread_story_dict = {}

    for spread in os.listdir(spreads_folder):
        spread_path = os.path.join(spreads_folder, spread)
        parent_stories = get_all_parentstory_from_spread(spread_path)
        story_values = set(story_token_dict.values())
        valid_parents = [p for p in parent_stories if p in story_values]
        if valid_parents:
            spread_story_dict[spread.split(".")[0].split("_")[-1]] = valid_parents

    with open("spread_story_mapping.json", "w") as f:
        json.dump(spread_story_dict, f, indent=4)

    logging.info("JSON ressources created")
