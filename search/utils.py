def clamp(n, low, high):
    """ensure that a number n is constrained in a range"""
    return min(high, max(low, n))
