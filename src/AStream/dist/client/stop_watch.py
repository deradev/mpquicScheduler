import time


class StopWatch():
    """ Implements a stop watch function
        Modified from http://code.activestate.com/recipes/124894-stopwatch-in-tkinter/
    """
    def __init__(self):
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.running = 0

    def start(self):
        """ Start the stopwatch, ignore if running. """
        if not self.running:
            self.start_time = time.time() - self.elapsed_time
            self.running = 1
    
    def pause(self):
        """ Stop the stopwatch, ignore if already paused."""
        if self.running:
            self.elapsed_time = time.time() - self.start_time
            self.running = 0
    
    def reset(self):
        """ Reset the stopwatch. """
        self.start_time = time.time()
        self.elapsed_time = 0.0

    def time(self):
        """
        :return: elapsed time
        """
        if self.running:
            self.elapsed_time = time.time() - self.start_time
        return self.elapsed_time