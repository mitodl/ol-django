"""Collections utilities"""
from collections.abc import Iterable
from itertools import groupby, islice, tee


def dict_without_keys(d, *omitkeys):
    """
    Returns a copy of a dict without the specified keys

    Args:
        d (dict): A dict that to omit keys from
        *omitkeys: Variable length list of keys to omit

    Returns:
        dict: A dict with omitted keys
    """
    return {key: d[key] for key in d.keys() if key not in omitkeys}


def filter_dict_by_key_set(dict_to_filter, key_set):
    """Takes a dictionary and returns a copy with only the keys that exist in the given set"""
    return {key: dict_to_filter[key] for key in dict_to_filter.keys() if key in key_set}


def first_matching_item(iterable, predicate):
    """
    Gets the first item in an iterable that matches a predicate (or None if nothing matches)

    Returns:
        Matching item or None
    """
    return next(filter(predicate, iterable), None)


def find_object_with_matching_attr(iterable, attr_name, value):
    """
    Finds the first item in an iterable that has an attribute with the given name and value. Returns
    None otherwise.

    Returns:
        Matching item or None
    """
    for item in iterable:
        try:
            if getattr(item, attr_name) == value:
                return item
        except AttributeError:
            pass
    return None


def has_equal_properties(obj, property_dict):
    """
    Returns True if the given object has the properties indicated by the keys of the given dict, and the values
    of those properties match the values of the dict
    """
    for field, value in property_dict.items():
        try:
            if getattr(obj, field) != value:
                return False
        except AttributeError:
            return False
    return True


def first_or_none(iterable):
    """
    Returns the first item in an iterable, or None if the iterable is empty

    Args:
        iterable (iterable): Some iterable
    Returns:
        first item or None
    """
    return next((x for x in iterable), None)


def max_or_none(iterable):
    """
    Returns the max of some iterable, or None if the iterable has no items

    Args:
        iterable (iterable): Some iterable
    Returns:
        max item or None
    """
    try:
        return max(iterable)
    except ValueError:
        return None


def partition(items, predicate=bool):
    """
    Partitions an iterable into two different iterables - the first does not match the given condition, and the second
    does match the given condition.

    Args:
        items (iterable): An iterable of items to partition
        predicate (function): A function that takes each item and returns True or False
    Returns:
        tuple of iterables: An iterable of non-matching items, paired with an iterable of matching items
    """
    a, b = tee((predicate(item), item) for item in items)
    return (item for pred, item in a if not pred), (item for pred, item in b if pred)


def partition_to_lists(items, predicate=bool):
    """
    Partitions an iterable into two different lists - the first does not match the given condition, and the second
    does match the given condition.

    Args:
        items (iterable): An iterable of items to partition
        predicate (function): A function that takes each item and returns True or False
    Returns:
        tuple of lists: A list of non-matching items, paired with a list of matching items
    """
    a, b = partition(items, predicate=predicate)
    return list(a), list(b)


def unique(iterable):
    """
    Returns a generator containing all unique items in an iterable

    Args:
        iterable (iterable): An iterable of any hashable items
    Returns:
        generator: Unique items in the given iterable
    """
    seen = set()
    return (x for x in iterable if x not in seen and not seen.add(x))


def unique_ignore_case(strings):
    """
    Returns a generator containing all unique strings (coerced to lowercase) in a given iterable

    Args:
        strings (iterable of str): An iterable of strings
    Returns:
        generator: Unique lowercase strings in the given iterable
    """
    seen = set()
    return (s for s in map(str.lower, strings) if s not in seen and not seen.add(s))


def item_at_index_or_none(indexable, index):
    """
    Returns the item at a certain index, or None if that index doesn't exist

    Args:
        indexable (list or tuple):
        index (int): The index in the list or tuple

    Returns:
        The item at the given index, or None
    """
    try:
        return indexable[index]
    except IndexError:
        return None


def item_at_index_or_blank(indexable, index):
    """
    Returns the item at a certain index, or a blank string if that index doesn't exist

    Args:
        indexable (List[str]): A list of strings
        index (int): The index in the list or tuple

    Returns:
        str: The item at the given index, or a blank string
    """
    return item_at_index_or_none(indexable, index) or ""


def all_equal(*args):
    """
    Returns True if all of the provided args are equal to each other

    Args:
        *args (hashable): Arguments of any hashable type

    Returns:
        bool: True if all of the provided args are equal, or if the args are empty
    """
    return len(set(args)) <= 1


def all_unique(iterable):
    """
    Returns True if all of the provided args are equal to each other

    Args:
        iterable: An iterable of hashable items

    Returns:
        bool: True if all of the provided args are equal
    """
    return len(set(iterable)) == len(iterable)


def has_all_keys(dict_to_scan, keys):
    """
    Returns True if the given dict has all of the given keys

    Args:
        dict_to_scan (dict):
        keys (iterable of str): Iterable of keys to check for

    Returns:
        bool: True if the given dict has all of the given keys
    """
    return all(key in dict_to_scan for key in keys)


def group_into_dict(items, key_fn):
    """
    Groups items into a dictionary based on a key generated by a given function

    Examples:
        items = [
            Car(make="Honda", model="Civic"),
            Car(make="Honda", model="Accord"),
            Car(make="Ford", model="F150"),
            Car(make="Ford", model="Focus"),
        ]
        group_into_dict(items, lambda car: car.make) == {
            "Honda": [Car(make="Honda", model="Civic"), Car(make="Honda", model="Accord")],
            "Ford": [Car(make="Ford", model="F150"), Car(make="Ford", model="Focus")],
        }

    Args:
        items (Iterable[T]): An iterable of objects to group into a dictionary
        key_fn (Callable[[T], Any]): A function that will take an individual item and produce a dict key

    Returns:
        Dict[Any, T]: A dictionary with keys produced by the key function paired with a list of all the given
            items that produced that key.
    """
    sorted_items = sorted(items, key=key_fn)
    return {
        key: list(values_iter) for key, values_iter in groupby(sorted_items, key=key_fn)
    }


def chunks(iterable: Iterable, *, chunk_size: int = 20):
    """
    Yields chunks of an iterable as sub lists each of max size chunk_size.

    Args:
        iterable (iterable): iterable of elements to chunk
        chunk_size (int): Max size of each sublist

    Yields:
        list: List containing a slice of list_to_chunk
    """
    chunk_size = max(1, chunk_size)
    iterable = iter(iterable)
    chunk = list(islice(iterable, chunk_size))

    while len(chunk) > 0:
        yield chunk
        chunk = list(islice(iterable, chunk_size))


def matching_item_index(iterable, value_to_match):
    """
    Returns the index of the given value in the iterable

    Args:
        iterable (Iterable): The iterable to search
        value_to_match (Any): The value to match

    Returns:
        int: The index of the matching value

    Raises:
        StopIteration: Raised if the value is not found in the iterable
    """
    return next(i for i, value in enumerate(iterable) if value == value_to_match)
