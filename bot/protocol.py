import dataclasses


@dataclasses.dataclass
class FetchEvents:
    """ Fetch and handle fleet events. """
    id: str = None
