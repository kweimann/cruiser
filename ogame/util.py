import re
from datetime import datetime

from bs4 import BeautifulSoup


def find_first_between(string, left, right):
    """ Find first string in `string` that is between two strings `left` and `right`. """
    start = string.find(left)
    if start != -1:
        end = string.find(right, start + len(left))
        if end != -1:
            return string[start + len(left):end]


def find_unique(item, iterable, key=None):
    """ Get item from iterable if it is unique. """
    if key is None:
        def key(e): return e
    items = []
    for e in iterable:
        if key(e) == item:
            items.append(e)
    if len(items) == 1:
        return items[0]


def parse_html(html):
    """ Parse html string with BeautifulSoup. """
    return BeautifulSoup(html, 'html.parser')


def join_digits(string):
    """ Join all digits in a string together to make a number. Negative numbers are supported. """
    number = re.sub('[^-?\\d+]', '', string)
    return int(number) if number else None


def extract_numbers(string):
    """ Find and return all numbers within a string. """
    return tuple(int(number) for number in re.findall('-?\\d+', string))


def str2bool(string):
    """ Convert string to boolean. """
    return string in ['true', 'True', '1', 'yes'] if string else None


def tuple2timestamp(date_tuple, tzinfo=None, tz_offset=None):
    """ Convert tuple (day, month, year, hour, minute, second) to timestamp. """
    day, month, year, hour, minute, second = date_tuple
    if tzinfo is None and tz_offset is not None:
        tzinfo = parse_tzinfo(tz_offset)
    dt = datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        tzinfo=tzinfo)
    return int(dt.timestamp())


def str2int(string):
    """ Safely convert string to int or return None. """
    return int(string) if string else None


def ftime(timestamp: int):
    """ Format time. """
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def parse_tzinfo(timezone_offset):
    """ Get tzinfo object from a timezone offset e.g. +02:00 """
    return datetime.strptime(timezone_offset, '%z').tzinfo
