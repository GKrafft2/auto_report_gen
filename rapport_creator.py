from enum import Enum


class ArticleImportance(Enum):
    LOW = 1  # leads to Other Project
    MEDIUM = 2  # leads to Main Article
    HIGH = 3  # leads to Main Aricle LR


def generate_file_uid():
    pass


def create_new_spread():
    pass


def create_new_story():
    pass


def choose_template(article_importance: ArticleImportance):
    """chooses the best template according to the article importance"""
    pass
