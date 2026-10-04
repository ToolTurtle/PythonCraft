"""Run all the tests:  python3 run_tests.py        (add -v for the names; PYCRAFT_NO_WINDOW=1 skips the tests that open the game)"""
import sys
import unittest

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover('tests', top_level_dir='.')
    result = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
