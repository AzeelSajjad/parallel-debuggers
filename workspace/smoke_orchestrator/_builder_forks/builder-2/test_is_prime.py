from is_prime import is_prime

def test_two_is_prime():
    assert is_prime(2)

def test_three_is_prime():
    assert is_prime(3)

def test_four_is_not_prime():
    assert not is_prime(4)

def test_seven_is_prime():
    assert is_prime(7)

def test_one_is_not_prime():
    assert not is_prime(1)

def test_zero_is_not_prime():
    assert not is_prime(0)

def test_negatives_are_not_prime():
    assert not is_prime(-5)
    assert not is_prime(-2)
