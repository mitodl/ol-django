import random

from django.utils.cache import get_max_age, patch_cache_control


def cache_control_max_age_jitter(**kwargs):
    def _cache_controller(viewfunc):
        @wraps(viewfunc)
        def _cache_controlled(request, *args, **kwargs):
            # Ensure argument looks like a request.
            if not hasattr(request, "META"):
                raise TypeError(
                    "cache_control_max_age_jitter didn't receive an HttpRequest. If you are "
                    "decorating a classmethod, be sure to use "
                     "@method_decorator."
                )
            response = viewfunc(request, *args, **kwargs)
            max_age = get_max_age(response)
            # add random delay upto 5 minutes
            kwargs["max_age"] = max_age + random.randint(1, 600)
            patch_cache_control(response, **kwargs)
            return response
        return _cache_controlled
    return _cache_controller
