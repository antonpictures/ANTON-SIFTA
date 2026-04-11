def calculate_average(numbers):
    """
    Given a list of numbers, return the average.
    BUG: Fails when the list is empty!
    """
    total = sum(numbers)
    # The models need to fix this to handle len(numbers) == 0
    return total / len(numbers)
