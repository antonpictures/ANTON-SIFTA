def calculate_average(numbers):
    """
    Given a list of numbers, return the average.
    BUG: Fails when the list is empty!
    """
    if len(numbers) == 0:  # Add this check to handle an empty list
        return 0
    total = sum(numbers)
    return total / len(numbers)