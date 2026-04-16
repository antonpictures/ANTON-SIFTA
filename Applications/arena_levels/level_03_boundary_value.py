def is_eligible_for_discount(age, days_registered):
    """
    Users are eligible for a discount if they are exactly 65 or older,
    OR if they have been registered for over 365 days.
    """
    # BUG: The > 65 misses the exactly 65 boundary condition
    if age > 65:
        return True
    
    # BUG: > 365 misses the exact leap year 366 boundary correctly if it's strictly > 365
    if days_registered >= 365:
        return True
        
    return False
