#
# Copyright 2019 Ramble Lab
#


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False