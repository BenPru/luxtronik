import time
from threading import Timer

def debounce(wait):
    """ Decorator that will postpone a functions
        execution until after wait seconds
        have elapsed since the last time it was invoked. """
    def decorator(fn):
        def debounced(*args, **kwargs):
            def call_it():
                fn(*args, **kwargs)
            try:
                debounced.t.cancel()
            except(AttributeError):
                pass
            debounced.t = Timer(wait, call_it)
            debounced.t.start()
        return debounced
    return decorator


# def debounce(wait):
#     """ Decorator that will postpone a functions
#         execution until after wait seconds
#         have elapsed since the last time it was invoked. """

#     def decorator(fn):
#         def debounced(*args, **kwargs):
#             def call_it():
#                 debounced._timer = None
#                 debounced._last_call = time.time()
#                 return fn(*args, **kwargs)

#             time_since_last_call = time.time() - debounced._last_call
#             if time_since_last_call >= wait:
#                 return call_it()

#             if debounced._timer is None:
#                 debounced._timer = Timer(wait - time_since_last_call, call_it)
#                 debounced._timer.start()

#         debounced._timer = None
#         debounced._last_call = 0

#         return debounced

#     return decorator
