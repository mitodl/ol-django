"""Functions reading and parsing environment variables"""
import importlib
import inspect
import json
import os
from ast import literal_eval
from functools import wraps
from typing import Any, Callable, Dict, List, NamedTuple, Union

from django.core.exceptions import ImproperlyConfigured


class EnvironmentVariableParseException(ImproperlyConfigured):
    """Environment variable was not parsed correctly"""


class EnvVariable(NamedTuple):
    """Representation of an environment variable"""

    name: str
    default: Any
    description: str
    required: bool
    dev_only: bool
    value: Any
    write_app_json: bool


def var_parser(parser_func: Callable):
    """
    Decorator to create a var parser func

    Args:
        parser_func (callable):
            a function that takes one argument which will be the raw value and
            returns a parsed value or raises an error
    """

    @wraps(parser_func)
    def wrapper(
        self,
        *,
        name: str,
        description: str,
        default: Any = None,
        required: bool = False,
        dev_only: bool = False,
        write_app_json: bool = True,
    ) -> EnvVariable:
        """
        Get an environment variable

        Args:
            name (str): An environment variable name
            default (str): The default value to use if the environment variable doesn't exist.
            description (str): The description of how this variable is used
            required (bool): Whether this variable is required at runtime
            dev_only (bool): Whether this variable is only applicable in dev environments
            write_app_json (bool): Whether this variable is written to app.json

        Raises:
            ValueError:
                If the environment variable args are incorrect

        Returns:
            any:
                The raw environment variable value
        """
        configured_envs = self._configured_vars
        environ = self._env

        if name in configured_envs:
            raise ValueError(f"Environment variable '{name}' was used more than once")

        value = environ.get(name, default)
        # attempt to parse the value before we store it in configured_envs
        # this ensures that get_any works since we don't store the various parse attempts until one succeeds
        value = parser_func(name, value, default)

        configured_envs[name] = EnvVariable(
            name, default, description, required, dev_only, value, write_app_json
        )

        return value

    return wrapper


def parse_bool(name: str, value: str, default: bool) -> bool:
    """
    Attempts to parse a bool

    Arguments:
        value (str or bool):
            the value as either an unparsed string or a bool in case of a default value

    Raises:
        EnvironmentVariableParseException:
            raised if the value wasn't parsable

    Returns:
        bool:
            parsed value
    """

    if isinstance(value, bool):
        return value

    parsed_value = value.lower()
    if parsed_value == "true":
        return True
    elif parsed_value == "false":
        return False

    raise EnvironmentVariableParseException(
        "Expected value in {name}={value} to be a boolean".format(
            name=name, value=value
        )
    )


def parse_int(name: str, value: str, default: int) -> int:
    """
    Attempts to parse a int

    Arguments:
        value (str or int):
            the value as either an unparsed string or an int in case of a default value

    Raises:
        EnvironmentVariableParseException:
            raised if the value wasn't parsable

    Returns:
        int:
            parsed value
    """

    if isinstance(value, int) or (value is None and default is None):
        return value

    try:
        parsed_value = int(value)
    except ValueError as ex:
        raise EnvironmentVariableParseException(
            "Expected value in {name}={value} to be an int".format(
                name=name, value=value
            )
        ) from ex

    return parsed_value


def parse_str(name: str, value: str, default: str):
    """
    Parses a str (identity function)

    Arguments:
        value (str):
            the value as either a str

    Returns:
        str:
            parsed value
    """
    return value


def parse_list_literal(
    name: str,
    value: Union[str, List[Any]],
    default: List[Any],
) -> List[str]:
    """
    Parses a comma separated string into a list

    Argumments:
        value (str or List[Any]):
            the value as a string or list of strings

    Returns:
        list[str]:
            the parsed value
    """
    if isinstance(value, list):
        return value

    parse_exception = EnvironmentVariableParseException(
        "Expected value in {name}={value} to be a list literal".format(
            name=name, value=value
        )
    )

    try:
        parsed_value = literal_eval(value)
    except (ValueError, SyntaxError) as ex:
        raise parse_exception from ex

    if not isinstance(parsed_value, list):
        raise parse_exception

    return parsed_value


def parse_delimited_list(name, value, default):
    """
    Parses a comma separated string into a list

    Argumments:
        value (str or list[str]):
            the value as a string or list of strings

    Returns:
        list[str]:
            the parsed value
    """
    parsed_value = value
    if isinstance(value, str):
        parsed_value = value.split(",")

    return [item.strip(" ") for item in parsed_value]


class EnvParser:
    """Stateful tracker for environment variable parsing"""

    _env: Dict[str, str]
    _configured_vars: Dict[str, EnvVariable]
    _imported_modules: List[str]

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the state"""
        self._env = dict(os.environ)
        self._configured_vars = {}
        self._imported_modules = []

    def reload(self):
        """Reloads the environment"""
        # reset the internal state since we're reloading everything that created it
        self.reset()

        # reload the modules we've imported
        for mod in [
            # this needs to be dynamic and inlined because settings.py will import this module
            importlib.import_module(os.environ.get("DJANGO_SETTINGS_MODULE")),
            *self._imported_modules,
        ]:
            importlib.reload(mod)

    def validate(self):
        """
        Validates the current configuration

        Raises:
            ImproperlyConfigured:
                If any settings are missing
        """
        missing_settings = []

        for env_var in self._configured_vars.values():
            if env_var.required and env_var.value in (None, ""):
                missing_settings.append(env_var.name)

        if missing_settings:
            raise ImproperlyConfigured(
                "The following settings are missing: {}. You need to add these environment variables in .env file.".format(
                    ", ".join(missing_settings)
                )
            )

    def list_environment_vars(self) -> List[EnvVariable]:
        """
        Get the list of EnvVariables

        Returns:
            list of EnvVariable:
                the list of available env vars
        """
        return self._configured_vars.values()

    def get_features(self, prefix: str = "FEATURE_") -> Dict[str, bool]:
        """
        Get the list of features enabled for this app

        Args:
            prefix (str):
                feature prefix string

        Returns:
            dict of bool:
                dictionary of feature flags
        """
        return {
            key[len(prefix) :]: self.get_bool(
                name=key,
                default=False,
                description=f"Feature {key}",
                write_app_json=False,
            )
            for key in list(self._env.keys())
            if key.startswith(prefix)
        }

    def init_app_settings(self, *, namespace: str, site_name: str, **kwargs):
        """
        Configure the app static settings

        Args:
            namespace (str):
                the app settings namespace
            site_name (str):
                The name of the site
        """

        # an optional scope can be passed, or this will default to the calling scope's globals
        scope = kwargs.pop("scope", inspect.currentframe().f_back.f_globals)

        scope["APP_SETTINGS_NAMESPACE"] = self.get_string(
            name="APP_SETTINGS_NAMESPACE",
            default=namespace,
            description="App environment variable namespace",
            write_app_json=False,
        )
        scope["SITE_NAME"] = self.get_string(
            name="SITE_NAME", default=site_name, description="Site name"
        )

    def get_site_name(self):
        """Return the site name"""
        site_name = self._configured_vars.get("SITE_NAME")
        if not site_name:
            raise ImproperlyConfigured(
                "Site name isn't set, add a call to init_app_settings()"
            )
        return site_name.value

    def app_namespaced(self, setting_key: str) -> str:
        """
        Return a namespaced setting key

        Example: app_namespaced("KEY") -> "APP_KEY"
        """
        namespace = self._configured_vars.get("APP_SETTINGS_NAMESPACE")
        if not namespace:
            raise ImproperlyConfigured(
                "App settings namespace isn't set, add a call to init_app_settings()"
            )
        return f"{namespace.value}_{setting_key}"

    def import_settings_modules(self, *module_names: str, **kwargs):
        """
        Import settings from modules

        Usage:
            import_settings_modules("module1.settings", "module2.settings")
            import_settings_modules("module1.settings", "module2.settings", scope=globals())
        """

        # an optional scope can be passed, or this will default to the calling scope's globals
        scope = kwargs.pop("scope", inspect.currentframe().f_back.f_globals)

        # this function imports modules and then walks each, adding uppercased vars
        # to the calling settings module (typically settings.py in a django project)
        for module_name in module_names:
            mod = importlib.import_module(module_name)

            # track this module to support reloading
            self._imported_modules.append(mod)

            # walk the module and get only the constant-cased variables
            for setting_name in dir(mod):
                if setting_name.isupper():
                    setting_value = getattr(mod, setting_name)
                    scope[setting_name] = setting_value

    get_string = var_parser(parse_str)
    get_bool = var_parser(parse_bool)
    get_int = var_parser(parse_int)
    get_list_literal = var_parser(parse_list_literal)
    get_delimited_list = var_parser(parse_delimited_list)


env = EnvParser()

# methods below are our exported module interface
get_string = env.get_string
get_int = env.get_int
get_bool = env.get_bool
get_list_literal = env.get_list_literal
get_delimited_list = env.get_delimited_list
reload = env.reload
validate = env.validate
list_environment_vars = env.list_environment_vars
get_features = env.get_features
init_app_settings = env.init_app_settings
app_namespaced = env.app_namespaced
get_site_name = env.get_site_name
import_settings_modules = env.import_settings_modules


def generate_app_json():
    """
    Generate a new app.json data structure in-memory using app.base.json and settings.py

    Returns:
        dict:
            object that can be serialized to JSON for app.json
    """
    with open("app.base.json") as app_template_json:
        config = json.load(app_template_json)

    for env_var in list_environment_vars():
        if env_var.dev_only or not env_var.write_app_json:
            continue

        if env_var.name not in config["env"]:
            config["env"][env_var.name] = {}

        config["env"][env_var.name].update(
            {"description": env_var.description, "required": env_var.required}
        )

    return config
