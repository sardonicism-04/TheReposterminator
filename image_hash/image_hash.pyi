def compare_hashes(hash1: str, hash2: str) -> float:
    """
    Compares two image hashes and returns a percent similarity

    :param hash1: The first hash to compare
    :type hash1: ``str``

    :param hash2: The second hash to compare
    :type hash2: ``str``

    :return: The percent similarity between the two hashes
    :rtype: ``float``
    """
    ...

def generate_hash(buffer: bytes) -> int:
    """
    Generates a hash of an image

    Given an image's ``bytes``, a difference hash is generated and returned.

    :param buffer: The image to generate a hash of
    :type buffer: ``bytes``

    :return: The generated difference hash
    :rtype: ``int``
    """
